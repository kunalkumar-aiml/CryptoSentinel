"""
Database models — SQLAlchemy 2.0 async
Tables: users, portfolios, trades, automation_rules
"""
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone:        Mapped[str]      = mapped_column(String(15), unique=True, nullable=False, index=True)
    name:         Mapped[str]      = mapped_column(String(100), nullable=False)
    password_hash:Mapped[str]      = mapped_column(String(255), nullable=False)
    is_active:    Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    portfolio:    Mapped["Portfolio"] = relationship("Portfolio", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id:              Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:         Mapped[int]   = mapped_column(Integer, ForeignKey("users.id"), unique=True)
    virtual_inr:     Mapped[float] = mapped_column(Float, default=100000.0)   # ₹1,00,000 starting balance
    virtual_usd:     Mapped[float] = mapped_column(Float, default=0.0)
    total_invested:  Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl:       Mapped[float] = mapped_column(Float, default=0.0)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user:    Mapped["User"]    = relationship("User", back_populates="portfolio")
    holdings:Mapped[list["Holding"]] = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")
    trades:  Mapped[list["Trade"]]   = relationship("Trade",   back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holdings"

    id:           Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int]   = mapped_column(Integer, ForeignKey("portfolios.id"))
    coin_id:      Mapped[str]   = mapped_column(String(50), nullable=False)
    symbol:       Mapped[str]   = mapped_column(String(20), nullable=False)
    quantity:     Mapped[float] = mapped_column(Float, default=0.0)
    avg_buy_price:Mapped[float] = mapped_column(Float, default=0.0)
    total_invested:Mapped[float]= mapped_column(Float, default=0.0)
    updated_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")


class Trade(Base):
    __tablename__ = "trades"

    id:           Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int]   = mapped_column(Integer, ForeignKey("portfolios.id"))
    coin_id:      Mapped[str]   = mapped_column(String(50), nullable=False)
    symbol:       Mapped[str]   = mapped_column(String(20), nullable=False)
    side:         Mapped[str]   = mapped_column(String(4), nullable=False)   # BUY / SELL
    quantity:     Mapped[float] = mapped_column(Float, nullable=False)
    price_inr:    Mapped[float] = mapped_column(Float, nullable=False)
    total_inr:    Mapped[float] = mapped_column(Float, nullable=False)
    order_type:   Mapped[str]   = mapped_column(String(10), default="MARKET")  # MARKET / LIMIT
    status:       Mapped[str]   = mapped_column(String(10), default="FILLED")
    note:         Mapped[str]   = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="trades")
