import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.app.shared.models import Base, utc_now


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    services: Mapped[list["ServiceDefinition"]] = relationship("ServiceDefinition", back_populates="category")


class ServiceDefinition(Base):
    __tablename__ = "service_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_item_number: Mapped[Optional[int]] = mapped_column(SmallInteger, unique=True, nullable=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_categories.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_ar: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(50), default="draft")
    default_delivery_mode: Mapped[str] = mapped_column(String(50), default="configurable")
    input_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    data_sensitivity: Mapped[str] = mapped_column(String(50), default="standard")
    requires_explicit_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_upload: Mapped[bool] = mapped_column(Boolean, default=False)
    includes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    excludes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    integrity_policy_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    category: Mapped["ServiceCategory"] = relationship("ServiceCategory", back_populates="services")
    offers: Mapped[list["ProductOffer"]] = relationship("ProductOffer", back_populates="primary_service")


class ProductOffer(Base):
    __tablename__ = "product_offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    offer_type: Mapped[str] = mapped_column(String(50), default="service")
    primary_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_definitions.id", ondelete="RESTRICT"), nullable=True
    )
    title_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, default="")
    includes_description: Mapped[str] = mapped_column(Text, default="")
    excludes_description: Mapped[str] = mapped_column(Text, default="")
    delivery_sla_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revision_limit: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    sale_channel: Mapped[str] = mapped_column(String(50), default="telegram")
    billing_interval_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    billing_interval_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    audience: Mapped[str] = mapped_column(String(50), default="individual")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    primary_service: Mapped[Optional["ServiceDefinition"]] = relationship("ServiceDefinition", back_populates="offers")
    prices: Mapped[list["OfferPrice"]] = relationship("OfferPrice", back_populates="offer", cascade="all, delete-orphan")


class OfferPrice(Base):
    __tablename__ = "offer_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_offers.id", ondelete="RESTRICT"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    price_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    offer: Mapped["ProductOffer"] = relationship("ProductOffer", back_populates="prices")

