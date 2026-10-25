import uuid
from datetime import date, datetime, time
from typing import Optional
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.app.shared.models import Base, utc_now


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    public_name: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    verification_status: Mapped[str] = mapped_column(Text, default="pending")
    provider_status: Mapped[str] = mapped_column(Text, default="inactive")
    default_time_zone: Mapped[str] = mapped_column(Text, default="UTC")
    default_commission_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0.2000)
    years_experience: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    availability_rules: Mapped[list["ProviderAvailabilityRule"]] = relationship(
        "ProviderAvailabilityRule", back_populates="provider", cascade="all, delete-orphan"
    )
    time_offs: Mapped[list["ProviderTimeOff"]] = relationship(
        "ProviderTimeOff", back_populates="provider", cascade="all, delete-orphan"
    )


class ProviderAvailabilityRule(Base):
    __tablename__ = "provider_availability_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    local_start: Mapped[time] = mapped_column(Time, nullable=False)
    local_end: Mapped[time] = mapped_column(Time, nullable=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    time_zone: Mapped[str] = mapped_column(Text, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    provider: Mapped["ProviderProfile"] = relationship("ProviderProfile", back_populates="availability_rules")


class ProviderTimeOff(Base):
    __tablename__ = "provider_time_off"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    provider: Mapped["ProviderProfile"] = relationship("ProviderProfile", back_populates="time_offs")
