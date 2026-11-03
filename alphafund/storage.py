"""SQLAlchemy storage foundation for AlphaFund's single-user portfolio ledger."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, create_engine, select
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///data/alphafund.db").strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    as_of_date: Mapped[Any | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="manual")
    masked_reference: Mapped[str | None] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("instrument_type", "identifier", name="uq_instrument_type_identifier"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    identifier: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    exchange: Mapped[str | None] = mapped_column(String(20))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("account_id", "instrument_id", "as_of_date", name="uq_holding_snapshot"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_cost: Mapped[float | None] = mapped_column(Float)
    as_of_date: Mapped[Any] = mapped_column(Date, nullable=False)
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    source: Mapped[str] = mapped_column(String(40), default="manual")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_date: Mapped[Any] = mapped_column(Date, nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    external_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class Valuation(Base):
    __tablename__ = "valuations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    valuation_date: Mapped[Any] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    observation_type: Mapped[str] = mapped_column(String(30), default="market_value")
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    quality: Mapped[str] = mapped_column(String(20), default="reported")


class CashFlow(Base):
    __tablename__ = "cash_flows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    flow_date: Mapped[Any] = mapped_column(Date, nullable=False)
    flow_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))


class PortfolioStore:
    """Small repository facade; accepts SQLite or PostgreSQL DATABASE_URL."""
    def __init__(self, url: str | None = None):
        self.url = url or _database_url()
        if self.url.startswith("sqlite:///"):
            db_path = self.url.removeprefix("sqlite:///")
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"check_same_thread": False} if self.url.startswith("sqlite") else {}
        self.engine = create_engine(self.url, future=True, connect_args=kwargs)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def create_import_batch(self, source_type: str, filename: str | None = None,
                            checksum: str | None = None, as_of_date=None,
                            row_count: int = 0, notes: str | None = None) -> int:
        allowed = {"groww", "csv", "excel", "cas", "manual", "pms", "aif"}
        if source_type not in allowed:
            raise ValueError(f"Unsupported import source: {source_type}")
        if row_count < 0:
            raise ValueError("row_count cannot be negative")
        self.initialize()
        with self.Session.begin() as session:
            batch = ImportBatch(source_type=source_type, filename=filename, checksum=checksum,
                                as_of_date=as_of_date, row_count=row_count,
                                status="validated", notes=notes)
            session.add(batch)
            session.flush()
            return batch.id

    def add_account(self, name: str, account_type: str, provider: str = "manual",
                    currency: str = "INR", masked_reference: str | None = None) -> int:
        if not name.strip() or not account_type.strip():
            raise ValueError("Account name and type are required.")
        self.initialize()
        with self.Session.begin() as session:
            item = Account(name=name.strip(), account_type=account_type.strip().lower(),
                           provider=provider.strip(), currency=currency.upper(),
                           masked_reference=masked_reference)
            session.add(item)
            session.flush()
            return item.id

    def add_instrument(self, instrument_type: str, name: str, identifier: str,
                       currency: str = "INR", exchange: str | None = None,
                       metadata: dict | None = None) -> int:
        if not all(x.strip() for x in (instrument_type, name, identifier)):
            raise ValueError("Instrument type, name and identifier are required.")
        self.initialize()
        with self.Session.begin() as session:
            item = Instrument(instrument_type=instrument_type.strip().lower(),
                              name=name.strip(), identifier=identifier.strip().upper(),
                              currency=currency.upper(), exchange=exchange,
                              metadata_json=metadata or {})
            session.add(item)
            session.flush()
            return item.id

    def add_holding(self, account_id: int, instrument_id: int, quantity: float,
                    as_of_date, average_cost: float | None = None,
                    source: str = "manual", source_batch_id: int | None = None) -> int:
        if quantity < 0 or (average_cost is not None and average_cost < 0):
            raise ValueError("Quantity and average cost cannot be negative.")
        self.initialize()
        with self.Session.begin() as session:
            item = Holding(account_id=account_id, instrument_id=instrument_id,
                           quantity=quantity, average_cost=average_cost,
                           as_of_date=as_of_date, source=source,
                           source_batch_id=source_batch_id)
            session.add(item)
            session.flush()
            return item.id

    def list_accounts(self) -> list[dict]:
        self.initialize()
        with self.Session() as session:
            return [{"id": x.id, "name": x.name, "account_type": x.account_type,
                     "provider": x.provider, "currency": x.currency}
                    for x in session.scalars(select(Account).order_by(Account.name)).all()]

    def list_holdings(self) -> list[dict]:
        self.initialize()
        with self.Session() as session:
            rows = session.execute(
                select(Holding, Account, Instrument)
                .join(Account, Holding.account_id == Account.id)
                .join(Instrument, Holding.instrument_id == Instrument.id)
                .order_by(Holding.as_of_date.desc(), Instrument.name)
            ).all()
            return [{"account": a.name, "instrument": i.name, "identifier": i.identifier,
                     "asset_type": i.instrument_type, "quantity": h.quantity,
                     "average_cost": h.average_cost, "as_of_date": h.as_of_date.isoformat(),
                     "source": h.source} for h, a, i in rows]
