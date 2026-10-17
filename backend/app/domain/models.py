"""Fatima's schema fragment. Host owns migrations, transactions and reset orchestration."""
from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Sport(Base):
    __tablename__ = 'domain_sports'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config: Mapped[dict] = mapped_column(JSON)


class League(Base):
    __tablename__ = 'domain_leagues'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey('domain_sports.id'))
    config: Mapped[dict] = mapped_column(JSON)


class Match(Base):
    __tablename__ = 'domain_matches'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey('domain_sports.id'))
    league_id: Mapped[str | None] = mapped_column(ForeignKey('domain_leagues.id'), nullable=True)
    home: Mapped[str] = mapped_column(String(64))
    away: Mapped[str] = mapped_column(String(64))


class Event(Base):
    __tablename__ = 'domain_events'
    __table_args__ = (UniqueConstraint('match_id', 'sequence'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey('domain_matches.id'), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    request: Mapped[dict] = mapped_column(JSON)
    signature: Mapped[str] = mapped_column(String(64))


class Setting(Base):
    __tablename__ = 'domain_settings'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Outbox(Base):
    __tablename__ = 'domain_outbox'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Competition(Base):
    __tablename__ = 'domain_competitions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict] = mapped_column(JSON)


class ScheduledMatch(Base):
    __tablename__ = 'domain_scheduled_matches'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict] = mapped_column(JSON)
