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
            existing = session.scalar(select(Account).where(
                Account.name == name.strip(),
                Account.account_type == account_type.strip().lower(),
                Account.provider == provider.strip()))
            if existing:
                return existing.id
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
            existing = session.scalar(select(Instrument).where(
                Instrument.instrument_type == instrument_type.strip().lower(),
                Instrument.identifier == identifier.strip().upper()))
            if existing:
                return existing.id
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

    def sync_groww_holdings(self, records: list[dict], as_of_date=None) -> dict:
        """Persist a Groww Demat snapshot; update same-day rows and retain dated history."""
        from datetime import date
        from sqlalchemy import and_

        snapshot_date = as_of_date or date.today()
        self.initialize()
        inserted = updated = skipped = 0
        with self.Session.begin() as session:
            account = session.scalar(select(Account).where(and_(
                Account.name == "Groww Demat",
                Account.account_type == "broker",
                Account.provider == "groww")))
            if account is None:
                account = Account(name="Groww Demat", account_type="broker",
                                  provider="groww", currency="INR")
                session.add(account)
                session.flush()

            batch = ImportBatch(source_type="groww", filename="Groww API sync",
                                as_of_date=snapshot_date, row_count=len(records),
                                status="syncing", notes="Read-only Groww Demat holdings snapshot.")
            session.add(batch)
            session.flush()
            previous_rows = session.scalars(select(Holding).where(
                Holding.account_id == account.id
            ).order_by(Holding.as_of_date.desc(), Holding.id.desc())).all()
            latest_by_instrument = {}
            for previous in previous_rows:
                latest_by_instrument.setdefault(previous.instrument_id, previous)
            seen_instrument_ids = set()

            for row in records:
                if not isinstance(row, dict):
                    skipped += 1
                    continue
                symbol = str(row.get("trading_symbol") or row.get("tradingSymbol") or "").strip()
                isin = str(row.get("isin") or row.get("ISIN") or "").strip()
                exchange = str(row.get("exchange") or "").strip().upper() or None
                identifier = isin or (f"{exchange}:{symbol}" if exchange and symbol else symbol)
                if not identifier:
                    skipped += 1
                    continue
                name = str(row.get("company_name") or row.get("companyName") or
                           row.get("name") or symbol or identifier).strip()
                try:
                    quantity = float(row.get("quantity") or 0)
                    average = row.get("average_price", row.get("averagePrice",
                                  row.get("average_cost", row.get("averageCost"))))
                    average_cost = float(average) if average not in (None, "") else None
                except (TypeError, ValueError):
                    skipped += 1
                    continue
                if quantity < 0 or (average_cost is not None and average_cost < 0):
                    skipped += 1
                    continue

                instrument = session.scalar(select(Instrument).where(and_(
                    Instrument.instrument_type == "equity",
                    Instrument.identifier == identifier.upper())))
                if instrument is None:
                    instrument = Instrument(instrument_type="equity", name=name,
                        identifier=identifier.upper(), currency="INR", exchange=exchange,
                        metadata_json={"trading_symbol": symbol, "isin": isin, "source": "Groww API"})
                    session.add(instrument)
                    session.flush()
                else:
                    instrument.name = name or instrument.name
                    instrument.exchange = exchange or instrument.exchange

                seen_instrument_ids.add(instrument.id)
                existing = session.scalar(select(Holding).where(and_(
                    Holding.account_id == account.id,
                    Holding.instrument_id == instrument.id,
                    Holding.as_of_date == snapshot_date)))
                if existing:
                    existing.quantity = quantity
                    existing.average_cost = average_cost
                    existing.source = "Groww API"
                    existing.source_batch_id = batch.id
                    updated += 1
                else:
                    session.add(Holding(account_id=account.id, instrument_id=instrument.id,
                        quantity=quantity, average_cost=average_cost,
                        as_of_date=snapshot_date, source_batch_id=batch.id, source="Groww API"))
                    inserted += 1

            # A missing symbol in a successful broker snapshot means it is no
            # longer held. Write a zero-quantity dated row so stale positions do
            # not remain in the current portfolio view.
            for instrument_id, previous in latest_by_instrument.items():
                if instrument_id in seen_instrument_ids:
                    continue
                same_day = session.scalar(select(Holding).where(and_(
                    Holding.account_id == account.id,
                    Holding.instrument_id == instrument_id,
                    Holding.as_of_date == snapshot_date)))
                if same_day:
                    same_day.quantity = 0.0
                    same_day.average_cost = previous.average_cost
                    same_day.source = "Groww API"
                    same_day.source_batch_id = batch.id
                    updated += 1
                else:
                    session.add(Holding(account_id=account.id, instrument_id=instrument_id,
                        quantity=0.0, average_cost=previous.average_cost,
                        as_of_date=snapshot_date, source_batch_id=batch.id, source="Groww API"))
                    inserted += 1

            batch.status = "completed"
            batch.notes = f"Groww API snapshot: {inserted} inserted, {updated} updated, {skipped} skipped."
        return {"inserted": inserted, "updated": updated, "skipped": skipped,
                "as_of_date": snapshot_date.isoformat()}

    def get_last_groww_sync(self) -> str | None:
        """Return the latest successful Groww snapshot timestamp in ISO format."""
        self.initialize()
        with self.Session() as session:
            batch = session.scalar(select(ImportBatch).where(
                ImportBatch.source_type == "groww",
                ImportBatch.status == "completed"
            ).order_by(ImportBatch.imported_at.desc()))
            return batch.imported_at.isoformat() if batch and batch.imported_at else None

    def import_holdings(self, records: list[dict], filename: str, checksum: str) -> dict:
        """Import a validated holdings snapshot; skip previously imported files/rows."""
        from sqlalchemy import and_

        if not records:
            raise ValueError("There are no holding records to import.")
        self.initialize()
        with self.Session.begin() as session:
            existing_batch = session.scalar(select(ImportBatch).where(ImportBatch.checksum == checksum))
            if existing_batch:
                return {"batch_id": existing_batch.id, "inserted": 0, "skipped": len(records),
                        "duplicate_file": True}
            batch = ImportBatch(source_type="csv", filename=filename, checksum=checksum,
                                row_count=len(records), status="importing")
            session.add(batch)
            session.flush()
            inserted = skipped = 0
            for row in records:
                account = session.scalar(select(Account).where(and_(
                    Account.name == row["account_name"],
                    Account.account_type == row["account_type"].lower(),
                    Account.provider == row["provider"])))
                if account is None:
                    account = Account(name=row["account_name"], account_type=row["account_type"].lower(),
                                      provider=row["provider"], currency=row["currency"])
                    session.add(account)
                    session.flush()
                instrument = session.scalar(select(Instrument).where(and_(
                    Instrument.instrument_type == row["asset_type"].lower(),
                    Instrument.identifier == row["identifier"].upper())))
                if instrument is None:
                    instrument = Instrument(instrument_type=row["asset_type"].lower(),
                                             name=row["instrument_name"],
                                             identifier=row["identifier"].upper(),
                                             exchange=row.get("exchange"), currency=row["currency"])
                    session.add(instrument)
                    session.flush()
                duplicate = session.scalar(select(Holding.id).where(and_(
                    Holding.account_id == account.id, Holding.instrument_id == instrument.id,
                    Holding.as_of_date == row["as_of_date"])))
                if duplicate:
                    skipped += 1
                    continue
                cost = row.get("average_cost")
                session.add(Holding(account_id=account.id, instrument_id=instrument.id,
                                    quantity=float(row["quantity"]),
                                    average_cost=float(cost) if cost is not None else None,
                                    as_of_date=row["as_of_date"], source_batch_id=batch.id,
                                    source=filename))
                inserted += 1
            batch.status = "completed"
            batch.notes = f"Inserted {inserted}; skipped existing snapshots {skipped}."
            return {"batch_id": batch.id, "inserted": inserted, "skipped": skipped,
                    "duplicate_file": False}


    def import_transactions(self, records: list[dict], filename: str, checksum: str) -> dict:
        """Import transaction ledger rows with checksum and external-ID deduplication."""
        from sqlalchemy import and_
        if not records:
            raise ValueError("There are no transaction records to import.")
        self.initialize()
        with self.Session.begin() as session:
            existing_batch = session.scalar(select(ImportBatch).where(ImportBatch.checksum == checksum))
            if existing_batch:
                return {"inserted": 0, "skipped": len(records), "duplicate_file": True}
            batch = ImportBatch(source_type="csv", filename=filename, checksum=checksum,
                                row_count=len(records), status="importing")
            session.add(batch)
            session.flush()
            inserted = skipped = 0
            for row in records:
                account = session.scalar(select(Account).where(and_(
                    Account.name == row["account_name"], Account.provider == row["provider"])))
                if account is None:
                    account = Account(name=row["account_name"], account_type=row.get("account_type", "broker"),
                                      provider=row["provider"], currency=row["currency"])
                    session.add(account)
                    session.flush()
                instrument = session.scalar(select(Instrument).where(and_(
                    Instrument.instrument_type == row["asset_type"].lower(),
                    Instrument.identifier == row["identifier"].upper())))
                if instrument is None:
                    instrument = Instrument(instrument_type=row["asset_type"].lower(),
                                             name=row["instrument_name"], identifier=row["identifier"].upper(),
                                             currency=row["currency"])
                    session.add(instrument)
                    session.flush()
                external_id = row.get("external_id")
                duplicate = None
                if external_id:
                    duplicate = session.scalar(select(Transaction.id).where(Transaction.external_id == external_id))
                else:
                    duplicate = session.scalar(select(Transaction.id).where(and_(
                        Transaction.account_id == account.id, Transaction.instrument_id == instrument.id,
                        Transaction.transaction_type == row["transaction_type"],
                        Transaction.transaction_date == row["transaction_date"],
                        Transaction.amount == float(row["amount"]),
                        Transaction.quantity == (float(row["quantity"]) if row.get("quantity") is not None else None))))
                if duplicate:
                    skipped += 1
                    continue
                session.add(Transaction(account_id=account.id, instrument_id=instrument.id,
                    transaction_type=row["transaction_type"], transaction_date=row["transaction_date"],
                    quantity=float(row["quantity"]) if row.get("quantity") is not None else None,
                    price=float(row["price"]) if row.get("price") is not None else None,
                    amount=float(row["amount"]), currency=row["currency"], external_id=external_id,
                    source_batch_id=batch.id, notes=row.get("notes")))
                inserted += 1
            batch.status = "completed"
            batch.notes = f"Inserted {inserted}; skipped duplicates {skipped}."
            return {"inserted": inserted, "skipped": skipped, "duplicate_file": False}

    def import_valuations(self, records: list[dict], filename: str, checksum: str) -> dict:
        """Append dated valuation observations; do not overwrite historical values."""
        from sqlalchemy import and_
        if not records:
            raise ValueError("There are no valuation records to import.")
        self.initialize()
        with self.Session.begin() as session:
            existing_batch = session.scalar(select(ImportBatch).where(ImportBatch.checksum == checksum))
            if existing_batch:
                return {"inserted": 0, "skipped": len(records), "duplicate_file": True}
            batch = ImportBatch(source_type="csv", filename=filename, checksum=checksum,
                                row_count=len(records), status="importing")
            session.add(batch)
            session.flush()
            inserted = skipped = 0
            for row in records:
                account = session.scalar(select(Account).where(and_(
                    Account.name == row["account_name"], Account.provider == row["provider"])))
                if account is None:
                    account = Account(name=row["account_name"], account_type=row.get("account_type", "broker"),
                                      provider=row["provider"], currency=row["currency"])
                    session.add(account)
                    session.flush()
                instrument = session.scalar(select(Instrument).where(and_(
                    Instrument.instrument_type == row["asset_type"].lower(),
                    Instrument.identifier == row["identifier"].upper())))
                if instrument is None:
                    instrument = Instrument(instrument_type=row["asset_type"].lower(),
                        name=row["instrument_name"], identifier=row["identifier"].upper(),
                        currency=row["currency"])
                    session.add(instrument)
                    session.flush()
                duplicate = session.scalar(select(Valuation.id).where(and_(
                    Valuation.instrument_id == instrument.id, Valuation.account_id == account.id,
                    Valuation.valuation_date == row["valuation_date"],
                    Valuation.observation_type == row["observation_type"],
                    Valuation.source == row["source"], Valuation.value == float(row["value"]))))
                if duplicate:
                    skipped += 1
                    continue
                session.add(Valuation(instrument_id=instrument.id, account_id=account.id,
                    valuation_date=row["valuation_date"], value=float(row["value"]),
                    currency=row["currency"], observation_type=row["observation_type"],
                    source=row["source"], quality=row["quality"]))
                inserted += 1
            batch.status = "completed"
            batch.notes = f"Inserted {inserted}; skipped duplicates {skipped}."
            return {"inserted": inserted, "skipped": skipped, "duplicate_file": False}

    def list_valuations(self) -> list[dict]:
        self.initialize()
        with self.Session() as session:
            rows = session.execute(select(Valuation, Instrument, Account)
                .join(Instrument, Valuation.instrument_id == Instrument.id)
                .outerjoin(Account, Valuation.account_id == Account.id)
                .order_by(Valuation.valuation_date)).all()
            return [{"account": a.name if a else "Unassigned", "instrument": i.name,
                "identifier": i.identifier, "asset_type": i.instrument_type,
                "valuation_date": v.valuation_date.isoformat(), "value": v.value,
                "currency": v.currency, "observation_type": v.observation_type,
                "source": v.source, "quality": v.quality} for v, i, a in rows]

    def list_transactions(self) -> list[dict]:
        self.initialize()
        with self.Session() as session:
            rows = session.execute(select(Transaction, Account, Instrument)
                .join(Account, Transaction.account_id == Account.id)
                .outerjoin(Instrument, Transaction.instrument_id == Instrument.id)
                .order_by(Transaction.transaction_date)).all()
            return [{"account": a.name, "instrument": i.name if i else "Cash",
                "identifier": i.identifier if i else "", "transaction_type": t.transaction_type,
                "transaction_date": t.transaction_date.isoformat(), "quantity": t.quantity,
                "price": t.price, "amount": t.amount, "currency": t.currency,
                "external_id": t.external_id} for t, a, i in rows]

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
                select(Holding, Account, Instrument, ImportBatch)
                .join(Account, Holding.account_id == Account.id)
                .join(Instrument, Holding.instrument_id == Instrument.id)
                .outerjoin(ImportBatch, Holding.source_batch_id == ImportBatch.id)
                .order_by(Holding.as_of_date.desc(), Instrument.name)
            ).all()
            return [{"account": a.name, "provider": a.provider, "instrument": i.name, "identifier": i.identifier,
                     "asset_type": i.instrument_type, "quantity": h.quantity,
                     "average_cost": h.average_cost, "as_of_date": h.as_of_date.isoformat(),
                     "source": h.source,
                     "channel": "Groww" if str(a.provider).strip().lower() == "groww" else (batch.filename if batch and batch.filename else h.source),
                     "source_file": batch.filename if batch and batch.filename and batch.source_type != "groww" else None}
                    for h, a, i, batch in rows]
