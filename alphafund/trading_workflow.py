"""Deterministic, proposal-only trading workflow primitives.

This module borrows the staged workflow concept from day-trader-skill but is
implemented for AlphaFund's supported NSE/BSE/US research markets. It never
connects to a broker or places an order. All monetary values are expressed in
the instrument's quote currency; callers must not mix currencies.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    market: str
    side: str
    entry: float
    stop: float
    target: float
    setup: str = "manual"
    timeframe: str = "1d"
    as_of: str | None = None

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_per_unit(self) -> float:
        return abs(self.target - self.entry)

    @property
    def reward_risk(self) -> float:
        return self.reward_per_unit / self.risk_per_unit if self.risk_per_unit else 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(
            risk_per_unit=self.risk_per_unit,
            reward_per_unit=self.reward_per_unit,
            reward_risk=self.reward_risk,
        )
        return result


def create_trade_plan(
    symbol: str, market: str, side: str, entry: float, stop: float,
    target: float, setup: str = "manual", timeframe: str = "1d",
    as_of: str | None = None,
) -> TradePlan:
    """Validate and create a directional long/short research plan."""
    symbol = str(symbol).strip().upper()
    market = str(market).strip().upper()
    side = str(side).strip().upper()
    if not symbol:
        raise ValueError("A ticker symbol is required.")
    if market not in {"NSE", "BSE", "US"}:
        raise ValueError("Market must be NSE, BSE or US.")
    if side not in {"LONG", "SHORT"}:
        raise ValueError("Side must be LONG or SHORT.")
    values = [float(entry), float(stop), float(target)]
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError("Entry, stop and target must be finite positive prices.")
    entry, stop, target = values
    if side == "LONG" and not stop < entry < target:
        raise ValueError("For a LONG plan, stop < entry < target is required.")
    if side == "SHORT" and not target < entry < stop:
        raise ValueError("For a SHORT plan, target < entry < stop is required.")
    return TradePlan(symbol, market, side, entry, stop, target, setup, timeframe, as_of)


def size_position(
    plan: TradePlan, *, budget: float, max_loss: float,
    max_position_pct: float = 25.0, max_order_value: float | None = None,
    cash_available: float | None = None, cash_buffer_pct: float = 10.0,
    fractional: bool = False,
) -> dict[str, Any]:
    """Size a proposal using the tightest of risk, allocation, order and cash caps."""
    if budget <= 0 or max_loss <= 0:
        raise ValueError("Budget and max_loss must be positive.")
    if not 0 < max_position_pct <= 100 or not 0 <= cash_buffer_pct < 100:
        raise ValueError("Invalid allocation or cash-buffer percentage.")
    if plan.risk_per_unit <= 0:
        raise ValueError("The plan has no measurable stop risk.")
    caps: dict[str, float] = {
        "max_loss": max_loss / plan.risk_per_unit,
        "position_cap": budget * max_position_pct / 100 / plan.entry,
        "cash_buffer": budget * (1 - cash_buffer_pct / 100) / plan.entry,
    }
    if max_order_value is not None:
        if max_order_value <= 0:
            raise ValueError("max_order_value must be positive.")
        caps["max_order"] = max_order_value / plan.entry
    if cash_available is not None:
        if cash_available < 0:
            raise ValueError("cash_available cannot be negative.")
        caps["available_cash"] = cash_available / plan.entry
    raw_units = min(caps.values())
    units = raw_units if fractional else math.floor(raw_units)
    if units <= 0:
        return {
            "approved": False, "units": 0, "notional": 0.0,
            "max_loss_at_stop": 0.0, "binding_limit": min(caps, key=caps.get),
            "limits": caps, "reason": "No whole unit fits the configured risk and cash limits.",
        }
    notional = units * plan.entry
    return {
        "approved": True, "units": float(units) if fractional else int(units),
        "notional": notional, "max_loss_at_stop": units * plan.risk_per_unit,
        "binding_limit": min(caps, key=caps.get), "limits": caps,
        "reason": "Sizing proposal only; not an order.",
    }


def check_risk(
    plan: TradePlan, sizing: dict[str, Any], *,
    max_loss_per_trade: float, min_reward_risk: float = 1.5,
    max_daily_loss: float = 0.0, daily_risk_committed: float = 0.0,
    max_trades_per_day: int = 3, trades_today: int = 0,
    blocked_symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Return PASS/BLOCK with reasons. PASS never authorizes execution."""
    reasons: list[str] = []
    warnings: list[str] = []
    if not sizing.get("approved") or float(sizing.get("units", 0)) <= 0:
        reasons.append(str(sizing.get("reason") or "Position sizing did not approve a quantity."))
    if float(sizing.get("max_loss_at_stop", 0)) > max_loss_per_trade + 1e-9:
        reasons.append("Maximum loss at the planned stop exceeds the per-trade limit.")
    if plan.reward_risk < min_reward_risk:
        reasons.append(f"Reward/risk {plan.reward_risk:.2f} is below the minimum {min_reward_risk:.2f}.")
    if max_daily_loss > 0 and daily_risk_committed + float(sizing.get("max_loss_at_stop", 0)) > max_daily_loss + 1e-9:
        reasons.append("This proposal would exceed the remaining daily risk budget.")
    if trades_today >= max_trades_per_day:
        reasons.append("The configured daily trade-count limit has been reached.")
    if plan.symbol.upper() in {s.upper() for s in (blocked_symbols or [])}:
        reasons.append("The symbol is on the blocked list.")
    if plan.timeframe.endswith("m"):
        warnings.append("Intraday bar availability and timestamps must be verified for the selected exchange.")
    return {
        "status": "BLOCK" if reasons else "PASS",
        "reasons": reasons,
        "warnings": warnings,
        "max_loss_at_stop": float(sizing.get("max_loss_at_stop", 0)),
        "reward_risk": plan.reward_risk,
        "is_execution_authorization": False,
    }


def historical_trade_replay(
    plan: TradePlan, history: pd.DataFrame, *, max_bars: int = 30,
) -> dict[str, Any]:
    """Replay a fixed plan over historical close paths; stop wins ambiguous bars.

    Each eligible historical close is used as a hypothetical signal anchor.
    Subsequent close prices are inspected for stop/target crossings. This is a
    conservative close-only approximation, not intrabar execution simulation.
    """
    if "Close" not in history or len(history) < 3:
        raise ValueError("At least three historical Close observations are required.")
    closes = pd.to_numeric(history["Close"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(closes) < 3 or not np.isfinite(closes).all():
        raise ValueError("Historical closes are invalid or incomplete.")
    outcomes: list[str] = []
    returns_r: list[float] = []
    horizon = max(1, min(int(max_bars), len(closes) - 1))
    for start in range(len(closes) - horizon):
        anchor = closes[start]
        if anchor <= 0:
            continue
        scale = plan.entry / anchor
        future = closes[start + 1:start + 1 + horizon] * scale
        outcome = "OPEN"
        exit_price = float(future[-1])
        for price in future:
            if plan.side == "LONG":
                if price <= plan.stop:
                    outcome, exit_price = "STOP", plan.stop
                    break
                if price >= plan.target:
                    outcome, exit_price = "TARGET", plan.target
                    break
            else:
                if price >= plan.stop:
                    outcome, exit_price = "STOP", plan.stop
                    break
                if price <= plan.target:
                    outcome, exit_price = "TARGET", plan.target
                    break
        signed_move = (exit_price - plan.entry) if plan.side == "LONG" else (plan.entry - exit_price)
        outcomes.append(outcome)
        returns_r.append(signed_move / plan.risk_per_unit)
    counts = {key: outcomes.count(key) for key in ("TARGET", "STOP", "OPEN")}
    total = len(outcomes)
    return {
        "method": "historical close-only replay; stop-first conservative rule",
        "observations": total,
        "target_first_pct": counts["TARGET"] / total * 100 if total else None,
        "stop_first_pct": counts["STOP"] / total * 100 if total else None,
        "open_at_horizon_pct": counts["OPEN"] / total * 100 if total else None,
        "average_r": float(np.mean(returns_r)) if returns_r else None,
        "outcome_counts": counts,
        "warning": "Historical replay is not a forecast. It excludes intrabar path, slippage, fees, liquidity and corporate actions.",
    }


def build_workflow_snapshot(
    *, scanner_rows: list[dict[str, Any]] | None = None,
    news_items: list[dict[str, Any]] | None = None,
    plan: TradePlan | None = None, sizing: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None, replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stable, serialisable hand-off object for the UI and AI analyst."""
    return {
        "scanner": scanner_rows or [],
        "news": news_items or [],
        "trade_plan": plan.to_dict() if plan else None,
        "sizing": sizing,
        "risk_gate": risk,
        "historical_replay": replay,
        "execution": {"enabled": False, "broker_connected": False, "orders_sent": False},
        "disclaimer": "Research and paper-workflow output only; no trade has been placed.",
    }
