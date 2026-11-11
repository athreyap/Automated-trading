"""Historical portfolio risk analytics and threshold-alert evaluation.

All calculations use supplied adjusted close series. This is descriptive risk,
not a forecast, VaR guarantee, or order instruction.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from alphafund.market_research import fetch_market_history


def parse_weighted_symbols(raw: str) -> dict[str, float]:
    """Parse SYMBOL:WEIGHT entries separated by commas or newlines."""
    weights: dict[str, float] = {}
    for part in (raw or "").replace("\n", ",").split(","):
        token = part.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"Use SYMBOL:WEIGHT format for '{token}'.")
        symbol, value = token.rsplit(":", 1)
        symbol = symbol.strip().upper()
        try:
            weight = float(value.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid weight for {symbol or token}.") from exc
        if not symbol or not np.isfinite(weight) or weight <= 0:
            raise ValueError("Symbols must be non-empty and weights must be positive finite numbers.")
        if symbol in weights:
            raise ValueError(f"Duplicate symbol: {symbol}.")
        weights[symbol] = weight
    if not weights:
        raise ValueError("Enter at least one SYMBOL:WEIGHT pair.")
    return weights


def fetch_price_matrix(weights: Mapping[str, float], market: str, period: str = "2y") -> pd.DataFrame:
    """Fetch adjusted close prices for a bounded watchlist (max 20)."""
    if len(weights) > 20:
        raise ValueError("Risk analysis is limited to 20 securities per run.")
    prices = {}
    failures = {}
    for symbol in weights:
        try:
            _, history = fetch_market_history(symbol, market, period=period)
            prices[symbol] = history["Close"].rename(symbol)
        except Exception as exc:
            failures[symbol] = str(exc)
    if not prices:
        detail = "; ".join(f"{key}: {value}" for key, value in failures.items())
        raise ValueError("No price histories could be loaded. " + detail)
    matrix = pd.concat(prices.values(), axis=1).sort_index().dropna(how="all")
    matrix.attrs["failures"] = failures
    return matrix


def calculate_portfolio_risk(price_matrix: pd.DataFrame, weights: Mapping[str, float],
                             confidence: float = 0.95, periods: int = 252) -> dict:
    """Compute weighted historical daily risk using common complete observations."""
    if not 0.90 <= confidence <= 0.99:
        raise ValueError("Confidence must be between 90% and 99%.")
    if price_matrix is None or price_matrix.empty:
        raise ValueError("Price history is empty.")
    missing = [symbol for symbol in weights if symbol not in price_matrix.columns]
    if missing:
        raise ValueError("Missing price columns: " + ", ".join(missing))
    selected = price_matrix[list(weights)].apply(pd.to_numeric, errors="coerce")
    returns = selected.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if len(returns) < 30:
        raise ValueError(f"Only {len(returns)} common daily returns; at least 30 are required.")
    raw_weights = pd.Series(weights, dtype=float)
    if not np.isfinite(raw_weights.to_numpy()).all() or (raw_weights <= 0).any():
        raise ValueError("All weights must be positive finite numbers.")
    normalized = raw_weights / raw_weights.sum()
    normalized = normalized.reindex(returns.columns)
    portfolio_returns = returns.mul(normalized, axis=1).sum(axis=1)
    wealth = (1 + portfolio_returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1
    tail_cutoff = float(portfolio_returns.quantile(1 - confidence))
    tail = portfolio_returns[portfolio_returns <= tail_cutoff]
    asset_vol = returns.std() * np.sqrt(periods) * 100
    correlation = returns.corr()
    contribution = {}
    portfolio_vol_daily = float(portfolio_returns.std())
    if portfolio_vol_daily > 0:
        cov = returns.cov()
        marginal = cov.dot(normalized)
        component = normalized * marginal
        total = float(component.sum())
        for symbol, value in component.items():
            contribution[symbol] = float(value / total * 100) if total > 0 else 0.0
    else:
        contribution = {symbol: 0.0 for symbol in returns.columns}
    return {
        "observations": int(len(returns)),
        "start_date": str(returns.index[0].date()),
        "end_date": str(returns.index[-1].date()),
        "confidence": confidence,
        "annualised_volatility_pct": float(portfolio_vol_daily * np.sqrt(periods) * 100),
        "historical_var_pct": max(0.0, -tail_cutoff * 100),
        "historical_cvar_pct": max(0.0, -float(tail.mean()) * 100),
        "max_drawdown_pct": float(drawdown.min() * 100),
        "best_day_pct": float(portfolio_returns.max() * 100),
        "worst_day_pct": float(portfolio_returns.min() * 100),
        "weights_pct": (normalized * 100).to_dict(),
        "asset_volatility_pct": asset_vol.to_dict(),
        "risk_contribution_pct": contribution,
        "correlation": correlation,
        "daily_returns": portfolio_returns,
        "equity_curve": wealth,
        "price_failures": price_matrix.attrs.get("failures", {}),
    }


def evaluate_price_alert(last_price: float, previous_price: float, target_price: float,
                         direction: str) -> dict:
    """Evaluate whether a threshold was crossed on the latest observation."""
    values = [last_price, previous_price, target_price]
    if not all(np.isfinite(float(x)) and float(x) > 0 for x in values):
        raise ValueError("Prices and target must be positive finite numbers.")
    direction = direction.strip().lower()
    if direction not in {"above", "below"}:
        raise ValueError("Direction must be 'above' or 'below'.")
    if direction == "above":
        crossed = previous_price < target_price <= last_price
        currently_met = last_price >= target_price
    else:
        crossed = previous_price > target_price >= last_price
        currently_met = last_price <= target_price
    return {
        "direction": direction,
        "target_price": float(target_price),
        "last_price": float(last_price),
        "previous_price": float(previous_price),
        "triggered": bool(crossed),
        "currently_met": bool(currently_met),
    }
