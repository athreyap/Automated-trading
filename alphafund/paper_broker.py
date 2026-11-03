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
                notional REAL NOT NULL
            )
        """)

def list_trades():
    initialize_ledger()
    with _connect() as con:
        return con.execute(
            "SELECT timestamp, symbol, side, quantity, price, notional FROM trades ORDER BY id DESC"
        ).fetchall()

def record_paper_trade(symbol: str, side: str, quantity: int, price: float,
                       available_cash: float, allocation_limit: float = 900.0):
    initialize_ledger()
    symbol = symbol.strip().upper()
    side = side.strip().upper()
    if not symbol or side not in {"BUY", "SELL"}:
        raise ValueError("Provide a symbol and BUY or SELL side.")
    if quantity <= 0 or price <= 0:
        raise ValueError("Quantity and price must be positive.")
    notional = quantity * price
    if side == "BUY" and notional > min(available_cash, allocation_limit):
        raise ValueError("Trade exceeds available paper cash or the allocation limit.")
    if side == "SELL":
        raise ValueError("V1 ledger accepts BUY entries only; position accounting is not yet enabled.")
    with _connect() as con:
        con.execute(
            "INSERT INTO trades(timestamp,symbol,side,quantity,price,notional) VALUES(?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), symbol, side, quantity, price, notional)
        )
    return notional

def paper_cash(initial_cash: float = 900.0) -> float:
    initialize_ledger()
    with _connect() as con:
        spent = con.execute("SELECT COALESCE(SUM(notional),0) FROM trades WHERE side='BUY'").fetchone()[0]
    return max(0.0, initial_cash - float(spent))
