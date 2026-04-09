from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    category = Column(String, nullable=False)
    side = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    contracts = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)
    edge_at_entry = Column(Float, nullable=False)
    signal_type = Column(String, nullable=False)
    order_id = Column(String)
    status = Column(String, nullable=False, default="open")
    opened_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime)
    pnl_usd = Column(Float)
    mode = Column(String, nullable=False, default="dry_run")


class PnlDaily(Base):
    __tablename__ = "pnl_daily"
    date = Column(Date, primary_key=True)
    trades_count = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    pnl_usd = Column(Float, default=0.0)
    ending_balance = Column(Float)
    max_drawdown = Column(Float, default=0.0)


class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False)
    edge_score = Column(Float, nullable=False)
    gate_passed = Column(Boolean, nullable=False)
    blocked_by = Column(String)
    fired_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    mode = Column(String, nullable=False, default="dry_run")


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    occurred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db(url: str = "sqlite:///kalshi_bot.db") -> Session:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def get_session(url: str = "sqlite:///kalshi_bot.db") -> Session:
    return init_db(url)
