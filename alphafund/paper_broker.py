"""Position-aware paper ledger. This module has no broker connectivity."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/alphafund.db")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def initialize_ledger():
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                price REAL NOT NULL CHECK(price > 0),
                notional REAL NOT NULL,
                fees REAL NOT NULL DEFAULT 0
            )
        """)
        columns = {row[1] for row in con.execute("PRAGMA table_info(trades)").fetchall()}
        if "fees" not in columns:
            con.execute("ALTER TABLE trades ADD COLUMN fees REAL NOT NULL DEFAULT 0")


def _positions_from_rows(rows):
    positions = {}
    for symbol, side, quantity, price, notional, fees in rows:
        item = positions.setdefault(symbol, {"quantity": 0, "average_cost": 0.0, "realized_pnl": 0.0})
        quantity = int(quantity)
        price = float(price)
        fees = float(fees or 0)
        if side == "BUY":
            old_qty = item["quantity"]
            new_qty = old_qty + quantity
            item["average_cost"] = (
                (old_qty * item["average_cost"] + float(notional) + fees) / new_qty
            )
            item["quantity"] = new_qty
        else:
            if quantity > item["quantity"]:
                # Historical data should never create a short position. Ignore
                # malformed legacy rows in the derived view, while preserving
                # the original ledger for inspection.
                continue
            item["realized_pnl"] += quantity * (price - item["average_cost"]) - fees
            item["quantity"] -= quantity
            if item["quantity"] == 0:
                item["average_cost"] = 0.0
    return {symbol: item for symbol, item in positions.items() if item["quantity"] > 0 or item["realized_pnl"] != 0}


def list_trades():
    initialize_ledger()
    with _connect() as con:
        return con.execute(
            "SELECT timestamp, symbol, side, quantity, price, notional, fees FROM trades ORDER BY id DESC"
        ).fetchall()


def paper_positions():
    initialize_ledger()
    with _connect() as con:
        rows = con.execute(
            "SELECT symbol, side, quantity, price, notional, fees FROM trades ORDER BY id ASC"
        ).fetchall()
    positions = _positions_from_rows(rows)
    return [
        {"symbol": symbol, **values}
        for symbol, values in sorted(positions.items())
    ]


def record_paper_trade(symbol: str, side: str, quantity: int, price: float,
                       available_cash: float, allocation_limit: float = 900.0,
                       fee_bps: float = 0.0):
    initialize_ledger()
    symbol = (symbol or "").strip().upper()
    side = (side or "").strip().upper()
    if not symbol or side not in {"BUY", "SELL"}:
        raise ValueError("Provide a symbol and BUY or SELL side.")
    if quantity <= 0 or price <= 0:
        raise ValueError("Quantity and price must be positive.")
    if not 0 <= fee_bps <= 1000:
        raise ValueError("Fee must be between 0 and 1000 basis points.")
    notional = float(quantity) * float(price)
    fees = notional * float(fee_bps) / 10000.0

    with _connect() as con:
        rows = con.execute(
            "SELECT symbol, side, quantity, price, notional, fees FROM trades ORDER BY id ASC"
        ).fetchall()
        positions = _positions_from_rows(rows)
        if side == "BUY":
            spent = sum(float(row[4]) + float(row[5] or 0) for row in rows if row[1] == "BUY")
            proceeds = sum(float(row[4]) - float(row[5] or 0) for row in rows if row[1] == "SELL")
            ledger_cash = max(0.0, float(allocation_limit) - spent + proceeds)
            effective_cash = min(float(available_cash), ledger_cash, float(allocation_limit))
            if notional + fees > effective_cash + 1e-9:
                raise ValueError("Trade including fees exceeds available paper cash or the allocation limit.")
        else:
            held = positions.get(symbol, {}).get("quantity", 0)
            if quantity > held:
                raise ValueError(f"Cannot paper-sell {quantity} {symbol}; only {held} units are held.")
            if fees >= notional:
                raise ValueError("Fees cannot be greater than or equal to sale proceeds.")

        con.execute(
            "INSERT INTO trades(timestamp,symbol,side,quantity,price,notional,fees) VALUES(?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), symbol, side, int(quantity),
             float(price), notional, fees)
        )
    return {"notional": notional, "fees": fees, "cash_effect": -(notional + fees) if side == "BUY" else (notional - fees)}


def paper_cash(initial_cash: float = 900.0) -> float:
    initialize_ledger()
    with _connect() as con:
        rows = con.execute(
            "SELECT side, COALESCE(SUM(notional),0), COALESCE(SUM(fees),0) FROM trades GROUP BY side"
        ).fetchall()
    totals = {row[0]: (float(row[1]), float(row[2])) for row in rows}
    buy_notional, buy_fees = totals.get("BUY", (0.0, 0.0))
    sell_notional, sell_fees = totals.get("SELL", (0.0, 0.0))
    return max(0.0, float(initial_cash) - buy_notional - buy_fees + sell_notional - sell_fees)
