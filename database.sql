-- ============================================================================
-- database.sql — Student Learning & Services Platform (Merged Edition)
-- قاعدة بيانات منصة تعليمية وخدمات طلابية تُقدَّم عبر بوت تيليجرام
-- PostgreSQL 16+ (مُختبَرة على 17.x) — UTF-8 — تشغيل مرة واحدة على قاعدة فارغة
-- ----------------------------------------------------------------------------
-- اتفاقيات التصميم:
--   * المعرّفات: UUID للكيانات التجارية، BIGINT IDENTITY للسجلات الملحقة،
--     TEXT للأكواد المرجعية. معرّفات تيليجرام BIGINT (تتجاوز 32 بت) في
--     external_identities لتوحيد وسائل الدخول.
--   * المبالغ: BIGINT بوحدات العملة الصغرى (minor units). ممنوع FLOAT. XTR
--     بلا كسور. لقطة السعر تُثبَّت في order_items ولا تُحدَّث بعد الخروج
--     من draft (مشغل guard_order_financial_snapshot).
--   * الحالات: جداول مرجعية + مصفوفة انتقالات للطلب؛ إضافة حالة = INSERT.
--   * منع التكرار: idempotency_records، webhook_inbox، dedup_key، فهارس
--     فريدة جزئية (حجز نشط واحد لكل مزود، اشتراك نشط واحد لكل عرض...).
--   * الحذف: RESTRICT افتراضيًا للسجلات المالية، CASCADE فقط للمحتوى
--     التابع (ملفات، بنود خطة، جلسات). المستخدم يُخفى هويته عبر
--     fn_anonymize_user لا يُحذف فيزيائيًا.
--   * JSONB لكائنات مرنة فقط مع CHECK jsonb_typeof='object'.
--   * audit_events: append-only بمشغل يمنع UPDATE/DELETE.
--   * ما يبقى مسؤولية التطبيق: التحقق من صحة الويبهوك خارجيًا، تسلسل
--     استدعاء الدفع، تنفيذ المعاملات المركبة (دفع → منح → تسليم) في
--     معاملة تطبيقية واحدة. القاعدة تفرض الضمانات النهائية فقط.
-- ============================================================================

SET client_encoding = 'UTF8';

BEGIN;

CREATE SCHEMA IF NOT EXISTS student_platform;
SET LOCAL search_path TO student_platform, public;

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;

-- ============================================================================
-- 0. Metadata & settings
-- ============================================================================
CREATE TABLE schema_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE schema_meta IS 'إصدار المخطط — نقطة انطلاق أنظمة الترحيل المستقبلية';

CREATE TABLE platform_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE platform_settings IS 'إعدادات تشغيلية غير سرية فقط؛ الأسرار في مدير أسرار خارجي';

-- ============================================================================
-- 1. Currencies & reference statuses
-- ============================================================================
CREATE TABLE currencies (
    code                CHAR(3) PRIMARY KEY CHECK (code ~ '^[A-Z]{3}$'),
    name_ar             TEXT NOT NULL,
    minor_unit_digits   SMALLINT NOT NULL CHECK (minor_unit_digits BETWEEN 0 AND 6),
    is_fiat             BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON COLUMN currencies.minor_unit_digits IS '0=XTR (Telegram Stars), 2=USD/SAR, 3=KWD/BHD';

CREATE TABLE order_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE order_status_transitions (
    from_status TEXT NOT NULL REFERENCES order_statuses(code) ON DELETE RESTRICT,
    to_status   TEXT NOT NULL REFERENCES order_statuses(code) ON DELETE RESTRICT,
    PRIMARY KEY (from_status, to_status)
);
COMMENT ON TABLE order_status_transitions IS 'مصفوفة الانتقالات؛ تُفرض بمشغل validate_order_transition';

CREATE TABLE payment_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE subscription_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE request_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE booking_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE delivery_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE catalog_lifecycle_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);
CREATE TABLE refund_statuses (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT NOT NULL DEFAULT 0
);

-- ============================================================================
-- 2. Users, identity, profiles, consent, privacy
-- ============================================================================
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name        TEXT CHECK (display_name IS NULL OR char_length(display_name) <= 200),
    preferred_language  TEXT NOT NULL DEFAULT 'ar' CHECK (preferred_language ~ '^[a-z]{2}(-[A-Z]{2})?$'),
    time_zone           TEXT NOT NULL DEFAULT 'UTC',
    account_status      TEXT NOT NULL DEFAULT 'active'
        CHECK (account_status IN ('active','restricted','suspended','pending_deletion','anonymized')),
    last_seen_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    anonymized_at       TIMESTAMPTZ,
    CHECK (account_status <> 'anonymized' OR anonymized_at IS NOT NULL)
);
COMMENT ON TABLE users IS 'المستخدمون؛ هوية تيليجرام في external_identities. إخفاء الهوية عبر fn_anonymize_user لا حذف فيزيائي';

-- sequence لتوليد معرفات تيليجرام اصطناعية سالبة بعد إخفاء الهوية
CREATE SEQUENCE seq_anonymized_telegram_id
    AS BIGINT START WITH -1000000000 INCREMENT BY -1
    MINVALUE -9223372036854775807 NO MAXVALUE;

CREATE TABLE external_identities (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    provider              TEXT NOT NULL CHECK (provider IN ('telegram','google','apple','email','web','other')),
    provider_subject      TEXT NOT NULL,
    telegram_user_id      BIGINT,
    provider_username     TEXT,
    linked_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_authenticated_at TIMESTAMPTZ,
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT uq_ext_identity_provider_subject UNIQUE (provider, provider_subject),
    CONSTRAINT ck_ext_identity_telegram CHECK (
        (provider = 'telegram' AND telegram_user_id IS NOT NULL AND telegram_user_id <> 0) OR
        (provider <> 'telegram' AND telegram_user_id IS NULL)
    )
);
CREATE UNIQUE INDEX uq_ext_identities_telegram_user ON external_identities (telegram_user_id)
    WHERE telegram_user_id IS NOT NULL;
CREATE INDEX ix_ext_identities_user ON external_identities (user_id);
COMMENT ON COLUMN external_identities.telegram_user_id IS 'BIGINT لأن معرفات تيليجرام تتجاوز 32 بت؛ القيم السالبة مخصصة للهويات المخفاة';

CREATE TABLE education_levels (
    id          SMALLINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name_ar     TEXT NOT NULL,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE subjects (
    subject_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT UNIQUE,
    name_ar     TEXT NOT NULL,
    name_en     TEXT,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_subjects_name ON subjects (name_ar);

CREATE TABLE user_learning_profiles (
    user_id             UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT,
    education_level_id  SMALLINT REFERENCES education_levels(id) ON DELETE SET NULL,
    institution_name    TEXT,
    major_or_track      TEXT,
    study_year          TEXT,
    country_code        CHAR(2),
    goals               TEXT,
    preferences         JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(preferences) = 'object'),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE consent_types (
    code                     TEXT PRIMARY KEY,
    name_ar                  TEXT NOT NULL,
    description_ar           TEXT,
    requires_explicit_opt_in BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE consent_documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consent_type  TEXT NOT NULL REFERENCES consent_types(code) ON DELETE RESTRICT,
    version       TEXT NOT NULL,
    title         TEXT NOT NULL,
    document_url  TEXT,
    content_sha256 CHAR(64) CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-fA-F]{64}$'),
    effective_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at    TIMESTAMPTZ,
    CONSTRAINT uq_consent_doc_version UNIQUE (consent_type, version),
    CHECK (retired_at IS NULL OR retired_at >= effective_at)
);

CREATE TABLE user_consents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    consent_document_id UUID NOT NULL REFERENCES consent_documents(id) ON DELETE RESTRICT,
    decision            TEXT NOT NULL CHECK (decision IN ('granted','declined','withdrawn')),
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    context             JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(context) = 'object')
);
CREATE INDEX ix_user_consents_user_time ON user_consents (user_id, decided_at DESC);

CREATE TABLE privacy_requests (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    request_type     TEXT NOT NULL CHECK (request_type IN ('access','export','delete','anonymize','rectify','restrict')),
    status           TEXT NOT NULL DEFAULT 'received'
                     CHECK (status IN ('received','verifying','in_progress','completed','rejected','cancelled')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    decision_reason  TEXT,
    details          JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    CHECK (completed_at IS NULL OR completed_at >= requested_at)
);
CREATE INDEX ix_privacy_requests_status ON privacy_requests (status, requested_at);

-- ============================================================================
-- 3. RBAC & organizations
-- ============================================================================
CREATE TABLE roles (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code           TEXT NOT NULL UNIQUE,
    name_ar        TEXT NOT NULL,
    scope          TEXT NOT NULL DEFAULT 'platform' CHECK (scope IN ('platform','organization')),
    description    TEXT,
    is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,
    module      TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE role_permissions (
    role_id       UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
CREATE TABLE user_role_assignments (
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    role_id     UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    assigned_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ,
    PRIMARY KEY (user_id, role_id),
    CHECK (expires_at IS NULL OR expires_at > assigned_at)
);

CREATE TABLE organizations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    organization_type TEXT NOT NULL CHECK (organization_type IN ('school','university','training_center','company','nonprofit','other')),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','suspended','closed')),
    country_code      CHAR(2) CHECK (country_code IS NULL OR country_code = upper(country_code)),
    time_zone         TEXT,
    billing_email     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    member_status   TEXT NOT NULL DEFAULT 'active' CHECK (member_status IN ('invited','active','suspended','left')),
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    invited_by      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT uq_org_member UNIQUE (organization_id, user_id),
    CONSTRAINT uq_org_member_id_org UNIQUE (id, organization_id)
);
CREATE INDEX ix_org_members_user_status ON organization_members (user_id, member_status);

CREATE TABLE organization_member_roles (
    organization_member_id UUID NOT NULL REFERENCES organization_members(id) ON DELETE CASCADE,
    role_id                UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    assigned_by            UUID REFERENCES users(user_id) ON DELETE SET NULL,
    assigned_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_member_id, role_id)
);

-- ============================================================================
-- 4. Catalog: categories, definitions, offers, bundles, prices, price history
-- ============================================================================
CREATE TABLE service_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,
    name_ar     TEXT NOT NULL,
    description TEXT,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE service_definitions (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_item_number       SMALLINT UNIQUE CHECK (source_item_number BETWEEN 1 AND 153),
    category_id              UUID NOT NULL REFERENCES service_categories(id) ON DELETE RESTRICT,
    code                     TEXT NOT NULL UNIQUE,
    title_ar                 TEXT NOT NULL CHECK (char_length(btrim(title_ar)) > 0),
    summary_ar               TEXT NOT NULL,
    lifecycle_status         TEXT NOT NULL DEFAULT 'draft' REFERENCES catalog_lifecycle_statuses(code) ON DELETE RESTRICT,
    default_delivery_mode    TEXT NOT NULL DEFAULT 'configurable'
                             CHECK (default_delivery_mode IN ('automated','human','hybrid','digital_product','channel_access','configurable')),
    input_schema             JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(input_schema) = 'object'),
    output_schema            JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(output_schema) = 'object'),
    data_sensitivity         TEXT NOT NULL DEFAULT 'standard'
                             CHECK (data_sensitivity IN ('public','standard','sensitive','highly_sensitive')),
    requires_explicit_consent BOOLEAN NOT NULL DEFAULT FALSE,
    requires_upload          BOOLEAN NOT NULL DEFAULT FALSE,
    includes                 TEXT,
    excludes                 TEXT,
    integrity_policy_notes   TEXT,
    created_by               UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_service_defs_category_status ON service_definitions (category_id, lifecycle_status);
CREATE INDEX ix_service_defs_title ON service_definitions USING gin (to_tsvector('simple', title_ar));
COMMENT ON COLUMN service_definitions.integrity_policy_notes IS 'حدود الاستخدام الأخلاقي: منع حل اختبار جارٍ أو تسليم واجب نيابة عن الطالب';

CREATE TABLE product_offers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                  TEXT NOT NULL UNIQUE,
    offer_type            TEXT NOT NULL CHECK (offer_type IN ('service','digital_product','subscription','bundle','institutional_license')),
    primary_service_id    UUID REFERENCES service_definitions(id) ON DELETE RESTRICT,
    title_ar              TEXT NOT NULL CHECK (char_length(btrim(title_ar)) > 0),
    description_ar        TEXT NOT NULL DEFAULT '',
    includes_description  TEXT NOT NULL DEFAULT '',
    excludes_description  TEXT NOT NULL DEFAULT '',
    delivery_sla_minutes  INTEGER CHECK (delivery_sla_minutes IS NULL OR delivery_sla_minutes > 0),
    revision_limit        SMALLINT CHECK (revision_limit IS NULL OR revision_limit >= 0),
    status                TEXT NOT NULL DEFAULT 'draft' REFERENCES catalog_lifecycle_statuses(code) ON DELETE RESTRICT,
    sale_channel          TEXT NOT NULL DEFAULT 'telegram' CHECK (sale_channel IN ('telegram','web','institutional','any')),
    billing_interval_unit TEXT CHECK (billing_interval_unit IN ('day','week','month','quarter','year')),
    billing_interval_count SMALLINT CHECK (billing_interval_count IS NULL OR billing_interval_count > 0),
    audience              TEXT NOT NULL DEFAULT 'individual' CHECK (audience IN ('individual','institution','both')),
    granted_channel_ref   TEXT,
    terms_version         TEXT,
    published_at          TIMESTAMPTZ,
    archived_at           TIMESTAMPTZ,
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_by            UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((offer_type = 'bundle' AND primary_service_id IS NULL) OR offer_type <> 'bundle'),
    CHECK ((billing_interval_unit IS NULL) = (billing_interval_count IS NULL)),
    CHECK (status <> 'published' OR offer_type <> 'subscription' OR billing_interval_unit IS NOT NULL),
    CHECK (archived_at IS NULL OR status = 'archived')
);
CREATE INDEX ix_product_offers_status_type ON product_offers (status, offer_type);
CREATE INDEX ix_product_offers_service ON product_offers (primary_service_id) WHERE primary_service_id IS NOT NULL;
COMMENT ON COLUMN product_offers.granted_channel_ref IS 'معرف قناة تيليجرام (مرجع خارجي نصي) لا يقبل مفتاح خارجي';

CREATE TABLE product_offer_components (
    bundle_offer_id    UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    component_offer_id UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    quantity           INTEGER NOT NULL DEFAULT 1 CHECK (quantity BETWEEN 1 AND 100),
    sort_order         SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (bundle_offer_id, component_offer_id),
    CHECK (bundle_offer_id <> component_offer_id)
);

CREATE TABLE offer_prices (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id      UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    currency_code CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    amount_minor  BIGINT NOT NULL CHECK (amount_minor >= 0),
    valid_from    TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until   TIMESTAMPTZ,
    price_label   TEXT,
    created_by    UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);
CREATE UNIQUE INDEX uq_offer_current_price ON offer_prices (offer_id, currency_code) WHERE valid_until IS NULL;
CREATE INDEX ix_offer_prices_history ON offer_prices (offer_id, currency_code, valid_from DESC);
ALTER TABLE offer_prices ADD CONSTRAINT ex_offer_price_periods
    EXCLUDE USING gist (offer_id WITH =, currency_code WITH =, tstzrange(valid_from, valid_until, '[)') WITH &&);
COMMENT ON COLUMN offer_prices.amount_minor IS 'سعر بوحدات العملة الصغرى؛ التغيير ينشئ حقبة جديدة ولا يمس الطلبات السابقة';

-- ============================================================================
-- 5. Idempotency, orders, order items, order events
-- ============================================================================
CREATE TABLE idempotency_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope               TEXT NOT NULL,
    idempotency_key     TEXT NOT NULL,
    actor_user_id       UUID REFERENCES users(user_id) ON DELETE SET NULL,
    request_fingerprint CHAR(64) CHECK (request_fingerprint IS NULL OR request_fingerprint ~ '^[0-9a-fA-F]{64}$'),
    response_status     SMALLINT,
    response_body       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ,
    CONSTRAINT uq_idem_scope_key UNIQUE (scope, idempotency_key),
    CHECK (expires_at IS NULL OR expires_at > created_at)
);

CREATE TABLE orders (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number          BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    user_id               UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    organization_id       UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    status                TEXT NOT NULL DEFAULT 'draft' REFERENCES order_statuses(code) ON DELETE RESTRICT,
    currency_code         CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    subtotal_minor        BIGINT NOT NULL DEFAULT 0 CHECK (subtotal_minor >= 0),
    discount_total_minor  BIGINT NOT NULL DEFAULT 0 CHECK (discount_total_minor >= 0),
    tax_total_minor       BIGINT NOT NULL DEFAULT 0 CHECK (tax_total_minor >= 0),
    total_minor           BIGINT NOT NULL DEFAULT 0 CHECK (total_minor >= 0),
    idempotency_record_id UUID UNIQUE REFERENCES idempotency_records(id) ON DELETE RESTRICT,
    customer_note         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at               TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    cancelled_at          TIMESTAMPTZ,
    CHECK (discount_total_minor <= subtotal_minor),
    CHECK (total_minor = subtotal_minor - discount_total_minor + tax_total_minor),
    CHECK (paid_at IS NULL OR paid_at >= created_at),
    CHECK (completed_at IS NULL OR completed_at >= created_at),
    CONSTRAINT uq_order_id_user UNIQUE (id, user_id)
);
CREATE INDEX ix_orders_user_created ON orders (user_id, created_at DESC);
CREATE INDEX ix_orders_status_created ON orders (status, created_at);
CREATE INDEX ix_orders_org_created ON orders (organization_id, created_at DESC) WHERE organization_id IS NOT NULL;

CREATE TABLE order_items (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id               UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    offer_id               UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    offer_price_id         UUID REFERENCES offer_prices(id) ON DELETE RESTRICT,
    service_definition_id  UUID REFERENCES service_definitions(id) ON DELETE RESTRICT,
    product_title_snapshot TEXT NOT NULL,
    product_code_snapshot  TEXT NOT NULL,
    currency_code          CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    quantity               INTEGER NOT NULL DEFAULT 1 CHECK (quantity BETWEEN 1 AND 100),
    unit_price_minor       BIGINT NOT NULL CHECK (unit_price_minor >= 0),
    line_discount_minor    BIGINT NOT NULL DEFAULT 0 CHECK (line_discount_minor >= 0),
    line_total_minor       BIGINT NOT NULL CHECK (line_total_minor >= 0),
    billing_period_snapshot TEXT CHECK (billing_period_snapshot IN ('weekly','monthly','quarterly','term','annual') OR billing_period_snapshot IS NULL),
    line_metadata          JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(line_metadata) = 'object'),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_order_item_id_order UNIQUE (id, order_id),
    CHECK (line_discount_minor <= (unit_price_minor::numeric * quantity)),
    CHECK (line_total_minor = (unit_price_minor::numeric * quantity - line_discount_minor)::bigint)
);
CREATE INDEX ix_order_items_order ON order_items (order_id);
CREATE INDEX ix_order_items_offer ON order_items (offer_id, created_at DESC);
COMMENT ON COLUMN order_items.unit_price_minor IS 'لقطة سعر الشراء الثابتة؛ لا تُحدَّث بعد draft';

CREATE TABLE order_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    previous_status TEXT REFERENCES order_statuses(code) ON DELETE RESTRICT,
    new_status      TEXT NOT NULL REFERENCES order_statuses(code) ON DELETE RESTRICT,
    actor_user_id   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    actor_type      TEXT NOT NULL DEFAULT 'system' CHECK (actor_type IN ('system','user','admin','payment_provider','webhook')),
    reason_code     TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_order_events_order_time ON order_events (order_id, created_at);
CREATE INDEX ix_order_events_status_time ON order_events (new_status, created_at);

-- ============================================================================
-- 6. Payments, webhook inbox, refunds
-- ============================================================================
CREATE TABLE payment_transactions (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id                   UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    user_id                    UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    provider                   TEXT NOT NULL DEFAULT 'telegram_stars' CHECK (provider IN ('telegram_stars','manual','external_provider','institutional_invoice')),
    status                     TEXT NOT NULL DEFAULT 'pending' REFERENCES payment_statuses(code) ON DELETE RESTRICT,
    currency_code              CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    amount_minor               BIGINT NOT NULL CHECK (amount_minor > 0),
    invoice_payload            TEXT NOT NULL UNIQUE,
    telegram_payment_charge_id TEXT UNIQUE,
    provider_payment_charge_id TEXT UNIQUE,
    external_transaction_id    TEXT,
    failure_code               TEXT,
    failure_message_safe       TEXT,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    succeeded_at               TIMESTAMPTZ,
    CONSTRAINT uq_payment_id_order UNIQUE (id, order_id),
    CHECK (provider <> 'telegram_stars' OR currency_code = 'XTR'),
    CHECK (telegram_payment_charge_id IS NULL OR length(telegram_payment_charge_id) > 0)
);
CREATE INDEX ix_payment_tx_order ON payment_transactions (order_id, created_at DESC);
CREATE INDEX ix_payment_tx_user ON payment_transactions (user_id, created_at DESC);
CREATE INDEX ix_payment_tx_status ON payment_transactions (status, created_at);
CREATE UNIQUE INDEX uq_order_single_settled_payment ON payment_transactions (order_id)
    WHERE status IN ('succeeded','partially_refunded','refunded');
COMMENT ON COLUMN payment_transactions.telegram_payment_charge_id IS 'معرف الشحنة من تيليجرام — فريد: نفس الدفعة لا تُسجل مرتين';

CREATE TABLE webhook_inbox (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source            TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_status TEXT NOT NULL DEFAULT 'received'
                      CHECK (processing_status IN ('received','processing','processed','retry','dead_letter','ignored')),
    attempts          INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    next_attempt_at   TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ,
    payload           JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
    last_error_safe   TEXT,
    CONSTRAINT uq_webhook_source_event UNIQUE (source, external_event_id),
    CHECK (processed_at IS NULL OR processed_at >= received_at)
);
CREATE INDEX ix_webhook_inbox_pending ON webhook_inbox (processing_status, next_attempt_at, received_at)
    WHERE processing_status IN ('received','retry','dead_letter');
COMMENT ON COLUMN webhook_inbox.last_error_safe IS 'رسالة خطأ آمنة للعرض؛ لا تحوي بيانات حساسة أو أسرار';

CREATE TABLE payment_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id        UUID REFERENCES payment_transactions(id) ON DELETE RESTRICT,
    webhook_inbox_id  UUID UNIQUE REFERENCES webhook_inbox(id) ON DELETE RESTRICT,
    provider          TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    event_type        TEXT NOT NULL CHECK (event_type IN ('pre_checkout_query','successful_payment','refunded_payment','failed_payment','other')),
    verified          BOOLEAN NOT NULL DEFAULT FALSE,
    currency_code     CHAR(3) REFERENCES currencies(code) ON DELETE RESTRICT,
    amount_minor      BIGINT CHECK (amount_minor IS NULL OR amount_minor >= 0),
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    handled_at        TIMESTAMPTZ,
    handling_result   TEXT,
    CONSTRAINT uq_payment_provider_event UNIQUE (provider, external_event_id),
    CHECK (handled_at IS NULL OR handled_at >= received_at)
);
CREATE INDEX ix_payment_events_payment ON payment_events (payment_id, received_at DESC);

CREATE TABLE refunds (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id           UUID NOT NULL REFERENCES payment_transactions(id) ON DELETE RESTRICT,
    order_id             UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    requested_by         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    status               TEXT NOT NULL DEFAULT 'requested' REFERENCES refund_statuses(code) ON DELETE RESTRICT,
    currency_code        CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    amount_minor         BIGINT NOT NULL CHECK (amount_minor > 0),
    reason_code          TEXT,
    external_refund_id   TEXT UNIQUE,
    requested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at         TIMESTAMPTZ,
    failure_message_safe TEXT,
    CHECK (completed_at IS NULL OR completed_at >= requested_at)
);
CREATE INDEX ix_refunds_payment_status ON refunds (payment_id, status);
CREATE INDEX ix_refunds_order ON refunds (order_id);

-- ============================================================================
-- 7. Subscriptions, licenses, entitlements, usage
-- ============================================================================
CREATE TABLE subscriptions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    plan_offer_id               UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    originating_order_item_id   UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    status                      TEXT NOT NULL DEFAULT 'pending' REFERENCES subscription_statuses(code) ON DELETE RESTRICT,
    current_period_start        TIMESTAMPTZ,
    current_period_end          TIMESTAMPTZ,
    started_at                  TIMESTAMPTZ,
    cancel_at_period_end        BOOLEAN NOT NULL DEFAULT FALSE,
    cancelled_at                TIMESTAMPTZ,
    ended_at                    TIMESTAMPTZ,
    external_subscription_id    TEXT UNIQUE,
    metadata                    JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (current_period_end IS NULL OR current_period_start IS NULL OR current_period_end > current_period_start),
    CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX ix_subscriptions_user_status ON subscriptions (user_id, status, current_period_end);
CREATE INDEX ix_subscriptions_due ON subscriptions (current_period_end) WHERE status IN ('active','trialing','past_due');
CREATE UNIQUE INDEX uq_subscriptions_active_per_offer ON subscriptions (user_id, plan_offer_id)
    WHERE status IN ('trialing','active','past_due');

CREATE TABLE subscription_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE RESTRICT,
    previous_status TEXT REFERENCES subscription_statuses(code) ON DELETE RESTRICT,
    new_status      TEXT NOT NULL REFERENCES subscription_statuses(code) ON DELETE RESTRICT,
    event_type      TEXT NOT NULL CHECK (event_type IN ('created','renewed','period_extended','paused','resumed','cancelled','expired','plan_changed','auto_renew_toggled','status_changed')),
    actor_user_id   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    details         JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_subscription_events_time ON subscription_events (subscription_id, created_at);

CREATE TABLE organization_licenses (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    offer_id                    UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    status                      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','suspended','expired','cancelled')),
    starts_at                   TIMESTAMPTZ NOT NULL,
    ends_at                     TIMESTAMPTZ,
    seat_limit                  INTEGER CHECK (seat_limit IS NULL OR seat_limit >= 0),
    usage_limit                 BIGINT CHECK (usage_limit IS NULL OR usage_limit >= 0),
    external_contract_reference TEXT,
    created_by                  UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ends_at IS NULL OR ends_at > starts_at),
    CHECK (seat_limit IS NOT NULL OR usage_limit IS NOT NULL),
    CONSTRAINT uq_org_license_id_org UNIQUE (id, organization_id)
);
CREATE INDEX ix_org_licenses_org_status ON organization_licenses (organization_id, status, ends_at);

CREATE TABLE organization_license_assignments (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_license_id  UUID NOT NULL,
    organization_member_id   UUID NOT NULL,
    organization_id          UUID NOT NULL,
    status                   TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','released')),
    assigned_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at              TIMESTAMPTZ,
    CONSTRAINT fk_license_assign_license_org FOREIGN KEY (organization_license_id, organization_id)
        REFERENCES organization_licenses(id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_license_assign_member_org FOREIGN KEY (organization_member_id, organization_id)
        REFERENCES organization_members(id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_license_member_assignment UNIQUE (organization_license_id, organization_member_id),
    CHECK (released_at IS NULL OR released_at >= assigned_at)
);
CREATE INDEX ix_license_assignments_member ON organization_license_assignments (organization_member_id, status);

CREATE TABLE entitlement_definitions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,
    name_ar     TEXT NOT NULL,
    description TEXT,
    unit        TEXT NOT NULL DEFAULT 'access'
                CHECK (unit IN ('access','request','minute','session','page','file','token','seat','other')),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE entitlement_grants (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entitlement_id                UUID NOT NULL REFERENCES entitlement_definitions(id) ON DELETE RESTRICT,
    user_id                       UUID REFERENCES users(user_id) ON DELETE RESTRICT,
    organization_id               UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    source_order_item_id          UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    source_subscription_id        UUID REFERENCES subscriptions(id) ON DELETE RESTRICT,
    source_organization_license_id UUID REFERENCES organization_licenses(id) ON DELETE RESTRICT,
    service_id                    UUID REFERENCES service_definitions(id) ON DELETE RESTRICT,
    status                        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending','active','suspended','revoked','expired')),
    starts_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at                       TIMESTAMPTZ,
    revoked_at                    TIMESTAMPTZ,
    revoke_reason                 TEXT,
    limit_amount                  BIGINT CHECK (limit_amount IS NULL OR limit_amount >= 0),
    metadata                      JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(user_id, organization_id) = 1),
    CHECK (num_nonnulls(source_order_item_id, source_subscription_id, source_organization_license_id) = 1),
    CHECK (ends_at IS NULL OR ends_at > starts_at),
    CHECK (revoked_at IS NULL OR revoked_at >= starts_at)
);
CREATE INDEX ix_ent_grant_user_live ON entitlement_grants (user_id, entitlement_id, starts_at, ends_at)
    WHERE user_id IS NOT NULL AND status = 'active';
CREATE INDEX ix_ent_grant_org_live ON entitlement_grants (organization_id, entitlement_id, starts_at, ends_at)
    WHERE organization_id IS NOT NULL AND status = 'active';
CREATE UNIQUE INDEX uq_ent_grant_order_item ON entitlement_grants (entitlement_id, source_order_item_id)
    WHERE source_order_item_id IS NOT NULL;
CREATE UNIQUE INDEX uq_ent_grant_subscription ON entitlement_grants (entitlement_id, source_subscription_id)
    WHERE source_subscription_id IS NOT NULL;
CREATE UNIQUE INDEX uq_ent_grant_org_license ON entitlement_grants (entitlement_id, source_organization_license_id)
    WHERE source_organization_license_id IS NOT NULL;

CREATE TABLE entitlement_usage_buckets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id        UUID NOT NULL REFERENCES entitlement_grants(id) ON DELETE RESTRICT,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    limit_amount    BIGINT NOT NULL CHECK (limit_amount > 0),
    consumed_amount BIGINT NOT NULL DEFAULT 0 CHECK (consumed_amount >= 0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ent_usage_period UNIQUE (grant_id, period_start, period_end),
    CHECK (period_end > period_start),
    CHECK (consumed_amount <= limit_amount)
);
CREATE INDEX ix_ent_usage_buckets_period ON entitlement_usage_buckets (period_end, grant_id);
COMMENT ON TABLE entitlement_usage_buckets IS 'تحديث ذري: UPDATE ... WHERE consumed + delta <= limit';

CREATE TABLE entitlement_usage_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usage_bucket_id  UUID NOT NULL REFERENCES entitlement_usage_buckets(id) ON DELETE RESTRICT,
    idempotency_key  TEXT NOT NULL UNIQUE,
    amount           BIGINT NOT NULL CHECK (amount > 0),
    operation        TEXT NOT NULL CHECK (operation IN ('consume','adjustment','reversal')),
    reference_code   TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ent_usage_events_bucket ON entitlement_usage_events (usage_bucket_id, created_at DESC);

CREATE TABLE product_offer_entitlements (
    offer_id             UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    entitlement_id       UUID NOT NULL REFERENCES entitlement_definitions(id) ON DELETE RESTRICT,
    limit_amount         BIGINT CHECK (limit_amount IS NULL OR limit_amount >= 0),
    reset_interval_unit  TEXT CHECK (reset_interval_unit IN ('day','week','month','quarter','year')),
    reset_interval_count SMALLINT CHECK (reset_interval_count IS NULL OR reset_interval_count > 0),
    access_days          INTEGER CHECK (access_days IS NULL OR access_days > 0),
    PRIMARY KEY (offer_id, entitlement_id),
    CHECK ((reset_interval_unit IS NULL) = (reset_interval_count IS NULL))
);

-- ============================================================================
-- 8. Digital assets & uploads
-- ============================================================================
CREATE TABLE stored_assets (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id    UUID REFERENCES users(user_id) ON DELETE RESTRICT,
    organization_id  UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    storage_backend  TEXT NOT NULL,
    storage_key      TEXT NOT NULL UNIQUE,
    original_filename TEXT,
    media_type       TEXT NOT NULL,
    byte_size        BIGINT NOT NULL CHECK (byte_size > 0),
    sha256           CHAR(64) CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-fA-F]{64}$'),
    asset_kind       TEXT NOT NULL CHECK (asset_kind IN ('user_upload','product_content','request_output','certificate','evidence','other')),
    sensitivity      TEXT NOT NULL DEFAULT 'standard' CHECK (sensitivity IN ('public','standard','sensitive','highly_sensitive')),
    license_type     TEXT NOT NULL DEFAULT 'proprietary' CHECK (license_type IN ('proprietary','licensed','cc_by','public_domain','user_owned')),
    license_note     TEXT,
    uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_until  TIMESTAMPTZ,
    deleted_at       TIMESTAMPTZ,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (retention_until IS NULL OR retention_until >= uploaded_at),
    CHECK (deleted_at IS NULL OR deleted_at >= uploaded_at),
    CHECK (owner_user_id IS NOT NULL OR organization_id IS NOT NULL OR asset_kind IN ('product_content','other'))
);
CREATE INDEX ix_stored_assets_owner ON stored_assets (owner_user_id, uploaded_at DESC) WHERE owner_user_id IS NOT NULL;
CREATE INDEX ix_stored_assets_retention ON stored_assets (retention_until) WHERE deleted_at IS NULL AND retention_until IS NOT NULL;
CREATE INDEX ix_stored_assets_org ON stored_assets (organization_id, uploaded_at DESC) WHERE organization_id IS NOT NULL;
COMMENT ON COLUMN stored_assets.storage_key IS 'مفتاح تخزين خاص غير عام؛ لا يحتوي أسرارًا أو روابط عامة';

CREATE TABLE offer_assets (
    offer_id      UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    asset_id      UUID NOT NULL REFERENCES stored_assets(id) ON DELETE RESTRICT,
    content_role  TEXT NOT NULL DEFAULT 'deliverable' CHECK (content_role IN ('preview','deliverable','supporting_material','license_document')),
    access_days   INTEGER CHECK (access_days IS NULL OR access_days > 0),
    sort_order    SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (offer_id, asset_id, content_role)
);

-- ============================================================================
-- 9. Service requests, attachments, events, execution, AI, deliveries
-- ============================================================================
CREATE TABLE service_requests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_number        BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    user_id               UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    organization_id       UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    service_definition_id UUID NOT NULL REFERENCES service_definitions(id) ON DELETE RESTRICT,
    offer_id              UUID REFERENCES product_offers(id) ON DELETE RESTRICT,
    order_item_id         UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    status                TEXT NOT NULL DEFAULT 'submitted' REFERENCES request_statuses(code) ON DELETE RESTRICT,
    priority              SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    fulfillment_mode      TEXT NOT NULL DEFAULT 'hybrid' CHECK (fulfillment_mode IN ('automated','human','hybrid')),
    request_brief         TEXT,
    input_payload         JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(input_payload) = 'object'),
    requested_due_at      TIMESTAMPTZ,
    assigned_to_user_id   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    revisions_allowed     SMALLINT NOT NULL DEFAULT 0 CHECK (revisions_allowed >= 0),
    revisions_used        SMALLINT NOT NULL DEFAULT 0 CHECK (revisions_used >= 0),
    policy_rejection_reason TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    cancelled_at          TIMESTAMPTZ,
    CHECK (revisions_used <= revisions_allowed),
    CHECK (completed_at IS NULL OR completed_at >= created_at),
    CONSTRAINT ck_request_policy_reason CHECK (status <> 'rejected_policy' OR policy_rejection_reason IS NOT NULL)
);
CREATE INDEX ix_service_req_user_status ON service_requests (user_id, status, created_at DESC);
CREATE INDEX ix_service_req_queue ON service_requests (status, priority, created_at) WHERE status IN ('submitted','queued','assigned','needs_info');
CREATE INDEX ix_service_req_assignee ON service_requests (assigned_to_user_id, status, priority) WHERE assigned_to_user_id IS NOT NULL;
CREATE INDEX ix_service_req_org ON service_requests (organization_id, status, created_at DESC) WHERE organization_id IS NOT NULL;
COMMENT ON COLUMN service_requests.input_payload IS 'حقول منظمة صغيرة فقط؛ الملفات في stored_assets';
COMMENT ON COLUMN service_requests.policy_rejection_reason IS 'سبب الرفض عند مخالفة سياسة النزاهة الأكاديمية';

CREATE TABLE service_request_attachments (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id    UUID NOT NULL REFERENCES service_requests(id) ON DELETE RESTRICT,
    asset_id              UUID NOT NULL REFERENCES stored_assets(id) ON DELETE RESTRICT,
    attached_by_user_id   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    attachment_role       TEXT NOT NULL CHECK (attachment_role IN ('input','reference','output_evidence')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_request_attachment UNIQUE (service_request_id, asset_id, attachment_role)
);
CREATE INDEX ix_request_attachments_request ON service_request_attachments (service_request_id, created_at);

CREATE TABLE service_request_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE RESTRICT,
    previous_status    TEXT REFERENCES request_statuses(code) ON DELETE RESTRICT,
    new_status         TEXT NOT NULL REFERENCES request_statuses(code) ON DELETE RESTRICT,
    actor_user_id      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    actor_type         TEXT NOT NULL DEFAULT 'system' CHECK (actor_type IN ('system','user','provider','admin')),
    note_safe          TEXT,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_service_req_events_time ON service_request_events (service_request_id, created_at);

CREATE TABLE service_execution_attempts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id UUID NOT NULL REFERENCES service_requests(id) ON DELETE RESTRICT,
    attempt_number     SMALLINT NOT NULL CHECK (attempt_number > 0),
    execution_mode     TEXT NOT NULL CHECK (execution_mode IN ('automated','human','hybrid')),
    status             TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','cancelled','retry_scheduled')),
    started_at         TIMESTAMPTZ,
    finished_at        TIMESTAMPTZ,
    error_code         TEXT,
    error_message_safe TEXT,
    metrics            JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metrics) = 'object'),
    CONSTRAINT uq_exec_attempt UNIQUE (service_request_id, attempt_number),
    CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);

CREATE TABLE service_request_revisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id  UUID NOT NULL REFERENCES service_requests(id) ON DELETE RESTRICT,
    requested_by_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    revision_number     SMALLINT NOT NULL CHECK (revision_number > 0),
    request_text        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','accepted','in_progress','completed','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    CONSTRAINT uq_request_revision_number UNIQUE (service_request_id, revision_number)
);

CREATE TABLE ai_tasks (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    service_request_id UUID REFERENCES service_requests(id) ON DELETE RESTRICT,
    task_type          TEXT NOT NULL,
    provider_code      TEXT NOT NULL,
    model_name         TEXT NOT NULL,
    model_version      TEXT,
    status             TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    input_asset_id     UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    output_asset_id    UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    input_tokens       BIGINT CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens      BIGINT CHECK (output_tokens IS NULL OR output_tokens >= 0),
    estimated_cost     NUMERIC(20,8) CHECK (estimated_cost IS NULL OR estimated_cost >= 0),
    cost_currency      CHAR(3) REFERENCES currencies(code) ON DELETE RESTRICT,
    latency_ms         INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    started_at         TIMESTAMPTZ,
    finished_at        TIMESTAMPTZ,
    error_code         TEXT,
    error_message_safe TEXT,
    review_required    BOOLEAN NOT NULL DEFAULT FALSE,
    human_reviewed_by  UUID REFERENCES users(user_id) ON DELETE SET NULL,
    human_reviewed_at  TIMESTAMPTZ,
    ai_consent_id      UUID REFERENCES user_consents(id) ON DELETE RESTRICT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at),
    CHECK ((estimated_cost IS NULL AND cost_currency IS NULL) OR (estimated_cost IS NOT NULL AND cost_currency IS NOT NULL))
);
CREATE INDEX ix_ai_tasks_status_created ON ai_tasks (status, created_at);
CREATE INDEX ix_ai_tasks_request ON ai_tasks (service_request_id, created_at DESC) WHERE service_request_id IS NOT NULL;
COMMENT ON COLUMN ai_tasks.ai_consent_id IS 'الموافقة الصريحة على المعالجة بالذكاء الاصطناعي لهذه المهمة';

CREATE TABLE deliveries (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_item_id      UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    service_request_id UUID REFERENCES service_requests(id) ON DELETE RESTRICT,
    asset_id           UUID NOT NULL REFERENCES stored_assets(id) ON DELETE RESTRICT,
    idempotency_key    TEXT NOT NULL UNIQUE,
    status             TEXT NOT NULL DEFAULT 'pending' REFERENCES delivery_statuses(code) ON DELETE RESTRICT,
    available_at       TIMESTAMPTZ,
    expires_at         TIMESTAMPTZ,
    first_delivered_at TIMESTAMPTZ,
    last_attempt_at    TIMESTAMPTZ,
    attempts           SMALLINT NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 100),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(order_item_id, service_request_id) >= 1),
    CHECK (expires_at IS NULL OR available_at IS NULL OR expires_at > available_at),
    CHECK (first_delivered_at IS NULL OR first_delivered_at >= created_at)
);
CREATE INDEX ix_deliveries_order_item ON deliveries (order_item_id, created_at) WHERE order_item_id IS NOT NULL;
CREATE INDEX ix_deliveries_request ON deliveries (service_request_id, created_at) WHERE service_request_id IS NOT NULL;
CREATE INDEX ix_deliveries_pending ON deliveries (status, created_at) WHERE status IN ('queued','failed');

CREATE TABLE delivery_attempts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id        UUID NOT NULL REFERENCES deliveries(id) ON DELETE RESTRICT,
    attempt_number     SMALLINT NOT NULL CHECK (attempt_number > 0),
    channel            TEXT NOT NULL CHECK (channel IN ('telegram','web','email','manual','other')),
    status             TEXT NOT NULL CHECK (status IN ('started','succeeded','failed','retry_scheduled')),
    external_message_id TEXT,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at        TIMESTAMPTZ,
    error_code         TEXT,
    error_message_safe TEXT,
    CONSTRAINT uq_delivery_attempt UNIQUE (delivery_id, attempt_number),
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

-- ============================================================================
-- 10. Providers, availability, bookings, reviews
-- ============================================================================
CREATE TABLE provider_profiles (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE RESTRICT,
    public_name          TEXT NOT NULL,
    headline             TEXT,
    bio                  TEXT,
    country_code         CHAR(2) CHECK (country_code IS NULL OR country_code = upper(country_code)),
    verification_status  TEXT NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending','verified','rejected','suspended')),
    provider_status      TEXT NOT NULL DEFAULT 'inactive' CHECK (provider_status IN ('active','inactive','suspended')),
    default_time_zone    TEXT NOT NULL DEFAULT 'UTC',
    default_commission_rate NUMERIC(5,4) NOT NULL DEFAULT 0.2000 CHECK (default_commission_rate BETWEEN 0 AND 1),
    years_experience     SMALLINT CHECK (years_experience IS NULL OR years_experience BETWEEN 0 AND 80),
    verified_at          TIMESTAMPTZ,
    verification_notes   TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_provider_profiles_status ON provider_profiles (verification_status, provider_status);

CREATE TABLE provider_qualifications (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id           UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE CASCADE,
    title                 TEXT NOT NULL,
    issuing_organization  TEXT,
    issued_on             DATE,
    expires_on            DATE,
    evidence_asset_id     UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    verification_status   TEXT NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending','verified','rejected')),
    reviewed_by           UUID REFERENCES users(user_id) ON DELETE SET NULL,
    reviewed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on)
);

CREATE TABLE provider_subjects (
    provider_id       UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE CASCADE,
    subject_id        UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    proficiency_level TEXT CHECK (proficiency_level IN ('beginner','intermediate','advanced','expert')),
    PRIMARY KEY (provider_id, subject_id)
);

CREATE TABLE provider_offer_assignments (
    provider_id      UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE CASCADE,
    offer_id         UUID NOT NULL REFERENCES product_offers(id) ON DELETE RESTRICT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    agreed_rate_minor BIGINT CHECK (agreed_rate_minor IS NULL OR agreed_rate_minor >= 0),
    rate_currency    CHAR(3) REFERENCES currencies(code) ON DELETE RESTRICT,
    assigned_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider_id, offer_id),
    CHECK ((agreed_rate_minor IS NULL AND rate_currency IS NULL) OR (agreed_rate_minor IS NOT NULL AND rate_currency IS NOT NULL))
);

CREATE TABLE provider_availability_rules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id   UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE CASCADE,
    weekday       SMALLINT NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    local_start   TIME NOT NULL,
    local_end     TIME NOT NULL,
    valid_from    DATE,
    valid_until   DATE,
    time_zone     TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (local_end > local_start),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from)
);
CREATE INDEX ix_provider_availability_active ON provider_availability_rules (provider_id, weekday) WHERE is_active;

CREATE TABLE provider_time_off (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id  UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE CASCADE,
    starts_at    TIMESTAMPTZ NOT NULL,
    ends_at      TIMESTAMPTZ NOT NULL,
    reason_code  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at)
);
CREATE INDEX ix_provider_time_off_range ON provider_time_off USING gist (provider_id, tstzrange(starts_at, ends_at, '[)'));

CREATE TABLE bookings (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id        UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE RESTRICT,
    offer_id           UUID REFERENCES product_offers(id) ON DELETE RESTRICT,
    order_item_id      UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    session_title      TEXT NOT NULL,
    booking_kind       TEXT NOT NULL DEFAULT 'individual' CHECK (booking_kind IN ('individual','group','office_hours','workshop')),
    status             TEXT NOT NULL DEFAULT 'pending_confirmation' REFERENCES booking_statuses(code) ON DELETE RESTRICT,
    starts_at          TIMESTAMPTZ NOT NULL,
    ends_at            TIMESTAMPTZ NOT NULL,
    capacity           INTEGER NOT NULL DEFAULT 1 CHECK (capacity > 0),
    commission_rate    NUMERIC(5,4) NOT NULL CHECK (commission_rate BETWEEN 0 AND 1),
    commission_amount_minor BIGINT,
    currency_code      CHAR(3) REFERENCES currencies(code) ON DELETE RESTRICT,
    meeting_reference  TEXT,
    cancellation_reason TEXT,
    created_by         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ,
    CHECK (ends_at > starts_at),
    CHECK (booking_kind <> 'individual' OR capacity = 1),
    CHECK ((commission_amount_minor IS NULL) = (currency_code IS NULL))
);
ALTER TABLE bookings ADD CONSTRAINT ex_bookings_provider_no_overlap
    EXCLUDE USING gist (provider_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)
    WHERE (status IN ('pending_confirmation','confirmed','in_progress'));
CREATE INDEX ix_bookings_provider_time ON bookings (provider_id, starts_at);
CREATE INDEX ix_bookings_status_start ON bookings (status, starts_at);
CREATE INDEX ix_bookings_order_item ON bookings (order_item_id) WHERE order_item_id IS NOT NULL;
COMMENT ON CONSTRAINT ex_bookings_provider_no_overlap ON bookings IS 'الحماية الجوهرية من السباق على الحجز: لا تداخل زمني لنفس المزود';

CREATE TABLE booking_participants (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id        UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    participant_status TEXT NOT NULL DEFAULT 'booked' CHECK (participant_status IN ('waitlisted','booked','attended','no_show','cancelled')),
    joined_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at      TIMESTAMPTZ,
    attendee_note     TEXT,
    CONSTRAINT uq_booking_participant UNIQUE (booking_id, user_id),
    CHECK (cancelled_at IS NULL OR cancelled_at >= joined_at)
);
CREATE INDEX ix_booking_participants_user ON booking_participants (user_id, participant_status);

CREATE TABLE booking_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      UUID NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
    previous_status TEXT REFERENCES booking_statuses(code) ON DELETE RESTRICT,
    new_status      TEXT NOT NULL REFERENCES booking_statuses(code) ON DELETE RESTRICT,
    actor_user_id   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    note_safe       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE provider_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      UUID NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE RESTRICT,
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    rating          SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text     TEXT,
    provider_reply  TEXT,
    moderation_status TEXT NOT NULL DEFAULT 'pending' CHECK (moderation_status IN ('pending','approved','hidden','rejected')),
    moderated_by    UUID REFERENCES users(user_id) ON DELETE SET NULL,
    moderated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_provider_reviews_published ON provider_reviews (moderation_status, created_at);

-- ============================================================================
-- 11. Opportunities, applications, local resources
-- ============================================================================
CREATE TABLE opportunity_types (
    type_id    SMALLINT PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    name_ar    TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE opportunities (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_id              SMALLINT NOT NULL REFERENCES opportunity_types(type_id) ON DELETE RESTRICT,
    title                TEXT NOT NULL,
    description          TEXT,
    organization         TEXT,
    country_code         CHAR(2) CHECK (country_code IS NULL OR country_code = upper(country_code)),
    city                 TEXT,
    level                TEXT NOT NULL DEFAULT 'any' CHECK (level IN ('high_school','bachelor','master','phd','professional','any')),
    eligibility_summary  TEXT NOT NULL,
    eligibility_details  TEXT,
    source_url           TEXT NOT NULL,
    source_name          TEXT NOT NULL,
    opens_at             TIMESTAMPTZ,
    deadline_at          TIMESTAMPTZ,
    last_verified_at     TIMESTAMPTZ,
    verification_status  TEXT NOT NULL DEFAULT 'unverified' CHECK (verification_status IN ('unverified','verified','stale','closed')),
    status               TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','closed','archived')),
    created_by           UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (verification_status <> 'verified' OR last_verified_at IS NOT NULL),
    CHECK (deadline_at IS NULL OR opens_at IS NULL OR deadline_at >= opens_at)
);
CREATE INDEX ix_opportunities_search ON opportunities (type_id, status, deadline_at);
CREATE INDEX ix_opportunities_verify ON opportunities (verification_status, last_verified_at);

CREATE TABLE opportunity_fields (
    opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    subject_id     UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    PRIMARY KEY (opportunity_id, subject_id)
);

CREATE TABLE saved_opportunities (
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    saved_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_note      TEXT,
    PRIMARY KEY (user_id, opportunity_id)
);

CREATE TABLE opportunity_applications (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    opportunity_id     UUID REFERENCES opportunities(id) ON DELETE SET NULL,
    title              TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'considering'
                       CHECK (status IN ('considering','preparing','submitted','assessment','interview','offered','rejected','withdrawn','accepted','closed')),
    deadline_snapshot  TIMESTAMPTZ,
    applied_at         TIMESTAMPTZ,
    next_action        TEXT,
    next_action_at     TIMESTAMPTZ,
    private_notes      TEXT,
    document_asset_id  UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_opp_apps_user_status ON opportunity_applications (user_id, status);
CREATE INDEX ix_opp_apps_next_action ON opportunity_applications (next_action_at) WHERE next_action_at IS NOT NULL;

CREATE TABLE opportunity_application_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES opportunity_applications(id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status      TEXT NOT NULL,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_opp_app_events_time ON opportunity_application_events (application_id, created_at);

CREATE TABLE local_resources (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type     TEXT NOT NULL CHECK (resource_type IN ('housing','transport','library','clinic','food','book','accessibility','community','student_service','other')),
    title             TEXT NOT NULL,
    description       TEXT,
    country_code      CHAR(2) CHECK (country_code IS NULL OR country_code = upper(country_code)),
    city              TEXT,
    address_or_area   TEXT,
    source_url        TEXT,
    contact_reference TEXT,
    price_amount_minor BIGINT CHECK (price_amount_minor IS NULL OR price_amount_minor >= 0),
    price_currency    CHAR(3) REFERENCES currencies(code) ON DELETE RESTRICT,
    last_verified_at  TIMESTAMPTZ,
    status            TEXT NOT NULL DEFAULT 'unverified' CHECK (status IN ('unverified','active','inactive','reported','archived')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((price_amount_minor IS NULL AND price_currency IS NULL) OR (price_amount_minor IS NOT NULL AND price_currency IS NOT NULL))
);
CREATE INDEX ix_local_resources_type_location ON local_resources (resource_type, country_code, city, status);

-- ============================================================================
-- 12. Education: courses, quizzes, questions, flashcards
-- ============================================================================
CREATE TABLE courses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    subject_id          UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    course_code         TEXT,
    title               TEXT NOT NULL,
    description         TEXT,
    education_level_id  SMALLINT REFERENCES education_levels(id) ON DELETE SET NULL,
    syllabus_asset_id   UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    status              TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    created_by          UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_course_org_code UNIQUE (organization_id, course_code)
);

CREATE TABLE course_topics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id           UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    parent_topic_id     UUID REFERENCES course_topics(id) ON DELETE RESTRICT,
    title               TEXT NOT NULL,
    description         TEXT,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    estimated_minutes   INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_course_topic_id UNIQUE (id, course_id)
);

CREATE TABLE course_enrollments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','withdrawn','suspended')),
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT uq_course_enrollment UNIQUE (course_id, user_id),
    CHECK (completed_at IS NULL OR completed_at >= enrolled_at)
);

CREATE TABLE topic_progress (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    topic_id          UUID NOT NULL REFERENCES course_topics(id) ON DELETE CASCADE,
    mastery_score     NUMERIC(5,2) CHECK (mastery_score IS NULL OR mastery_score BETWEEN 0 AND 100),
    status            TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started','in_progress','needs_review','mastered')),
    attempts_count    INTEGER NOT NULL DEFAULT 0 CHECK (attempts_count >= 0),
    last_activity_at  TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_topic_progress_user UNIQUE (user_id, topic_id)
);

-- بنك الأسئلة مع إصدارات (يمنع تعديل السؤال الجوهري؛ أي تغيير ينشئ نسخة مشتقة)
CREATE TABLE quiz_banks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id        UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    organization_id   UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    title             TEXT NOT NULL,
    description       TEXT,
    ownership_status  TEXT NOT NULL DEFAULT 'owned_or_licensed'
                      CHECK (ownership_status IN ('owned','licensed','open_license','owned_or_licensed','restricted')),
    status            TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    created_by        UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id                UUID NOT NULL REFERENCES quiz_banks(id) ON DELETE RESTRICT,
    created_by             UUID REFERENCES users(user_id) ON DELETE SET NULL,
    current_version_number INTEGER NOT NULL DEFAULT 1 CHECK (current_version_number > 0),
    derived_from_question_id UUID REFERENCES questions(id) ON DELETE RESTRICT,
    source_citation        TEXT,
    is_original            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_question_bank_pair UNIQUE (id, bank_id),
    CHECK (is_original OR source_citation IS NOT NULL)
);
COMMENT ON COLUMN questions.is_original IS 'الأسئلة أصلية أو مرخصة موثقة المصدر فقط (التزام حقوق النشر)';

CREATE TABLE question_versions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id        UUID NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    version_number     INTEGER NOT NULL CHECK (version_number > 0),
    question_type      TEXT NOT NULL CHECK (question_type IN ('single_choice','multiple_choice','short_text','numeric','true_false','open')),
    prompt             TEXT NOT NULL,
    explanation        TEXT,
    difficulty         SMALLINT CHECK (difficulty IS NULL OR difficulty BETWEEN 1 AND 5),
    points             NUMERIC(9,3) NOT NULL DEFAULT 1 CHECK (points > 0),
    source_reference   TEXT,
    is_published       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_question_version UNIQUE (question_id, version_number),
    CONSTRAINT uq_question_version_id_pair UNIQUE (id, question_id)
);

CREATE TABLE question_options (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_version_id UUID NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
    option_text         TEXT NOT NULL,
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    is_correct          BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_question_option_order UNIQUE (question_version_id, sort_order),
    CONSTRAINT uq_question_option_id_version UNIQUE (id, question_version_id)
);

CREATE TABLE quizzes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    subject_id      UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    linked_service_id UUID REFERENCES service_definitions(id) ON DELETE RESTRICT,
    title           TEXT NOT NULL,
    description     TEXT,
    quiz_type       TEXT NOT NULL DEFAULT 'practice' CHECK (quiz_type IN ('practice','diagnostic','mock_exam','oral_practice','language_test','other')),
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    time_limit_seconds INTEGER CHECK (time_limit_seconds IS NULL OR time_limit_seconds > 0),
    created_by      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE quiz_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id         UUID NOT NULL REFERENCES quizzes(id) ON DELETE RESTRICT,
    version_number  INTEGER NOT NULL CHECK (version_number > 0),
    instructions    TEXT,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_quiz_version UNIQUE (quiz_id, version_number),
    CONSTRAINT uq_quiz_version_id_quiz UNIQUE (id, quiz_id)
);

CREATE TABLE quiz_version_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_version_id     UUID NOT NULL REFERENCES quiz_versions(id) ON DELETE RESTRICT,
    question_version_id UUID NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
    sort_order          SMALLINT NOT NULL CHECK (sort_order >= 0),
    points              NUMERIC(9,3) NOT NULL CHECK (points > 0),
    CONSTRAINT uq_quiz_question_version UNIQUE (quiz_version_id, question_version_id),
    CONSTRAINT uq_quiz_item_sort UNIQUE (quiz_version_id, sort_order),
    CONSTRAINT uq_quiz_item_id_qv UNIQUE (id, question_version_id)
);

CREATE TABLE quiz_attempts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    quiz_version_id     UUID NOT NULL REFERENCES quiz_versions(id) ON DELETE RESTRICT,
    attempt_number      SMALLINT NOT NULL CHECK (attempt_number > 0),
    status              TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','submitted','graded','abandoned')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at        TIMESTAMPTZ,
    score               NUMERIC(12,3) CHECK (score IS NULL OR score >= 0),
    maximum_score       NUMERIC(12,3) CHECK (maximum_score IS NULL OR maximum_score > 0),
    error_analysis      JSONB CHECK (error_analysis IS NULL OR jsonb_typeof(error_analysis) = 'object'),
    feedback            TEXT,
    CONSTRAINT uq_quiz_attempt_number UNIQUE (user_id, quiz_version_id, attempt_number),
    CHECK (submitted_at IS NULL OR submitted_at >= started_at),
    CHECK (score IS NULL OR maximum_score IS NULL OR score <= maximum_score)
);
COMMENT ON TABLE quiz_attempts IS 'الدرجة تُثبَّت عند الإكمال؛ لا تتأثر بأي تعديل لاحق على الأسئلة';

CREATE TABLE quiz_attempt_answers (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_attempt_id    UUID NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    quiz_version_item_id UUID NOT NULL REFERENCES quiz_version_items(id) ON DELETE RESTRICT,
    question_version_id UUID NOT NULL,
    selected_option_id UUID REFERENCES question_options(id) ON DELETE RESTRICT,
    answer_text        TEXT,
    answer_numeric     NUMERIC(24,8),
    answer_snapshot    TEXT,
    is_correct         BOOLEAN,
    awarded_points     NUMERIC(9,3) CHECK (awarded_points IS NULL OR awarded_points >= 0),
    answered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_attempt_answer_item UNIQUE (quiz_attempt_id, quiz_version_item_id),
    CONSTRAINT fk_answer_item_qv FOREIGN KEY (quiz_version_item_id, question_version_id)
        REFERENCES quiz_version_items(id, question_version_id) ON DELETE RESTRICT,
    CONSTRAINT fk_answer_option_qv FOREIGN KEY (selected_option_id, question_version_id)
        REFERENCES question_options(id, question_version_id) ON DELETE RESTRICT,
    CHECK (num_nonnulls(selected_option_id, answer_text, answer_numeric) <= 1)
);
COMMENT ON COLUMN quiz_attempt_answers.is_correct IS 'تقييم يثبت وقت المحاولة (متطلب صريح)';

CREATE TABLE flashcard_decks (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id      UUID REFERENCES users(user_id) ON DELETE CASCADE,
    organization_id    UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    subject_id         UUID REFERENCES subjects(subject_id) ON DELETE SET NULL,
    linked_service_id  UUID REFERENCES service_definitions(id) ON DELETE RESTRICT,
    title              TEXT NOT NULL,
    description        TEXT,
    visibility         TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','organization','public')),
    access             TEXT NOT NULL DEFAULT 'private' CHECK (access IN ('private','free','paid','subscription')),
    status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (owner_user_id IS NOT NULL OR organization_id IS NOT NULL OR visibility = 'public')
);

CREATE TABLE flashcards (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deck_id        UUID NOT NULL REFERENCES flashcard_decks(id) ON DELETE CASCADE,
    front_text     TEXT NOT NULL CHECK (char_length(btrim(front_text)) > 0),
    back_text      TEXT NOT NULL CHECK (char_length(btrim(back_text)) > 0),
    explanation    TEXT,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    version_number INTEGER NOT NULL DEFAULT 1 CHECK (version_number > 0),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE flashcard_reviews (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    flashcard_id          UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    card_version_snapshot INTEGER NOT NULL CHECK (card_version_snapshot > 0),
    rating                SMALLINT NOT NULL CHECK (rating BETWEEN 0 AND 5),
    result                TEXT CHECK (result IN ('again','hard','good','easy')),
    elapsed_milliseconds  INTEGER CHECK (elapsed_milliseconds IS NULL OR elapsed_milliseconds >= 0),
    reviewed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_review_at        TIMESTAMPTZ,
    review_metadata       JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(review_metadata) = 'object')
);
CREATE INDEX ix_flashcard_reviews_next ON flashcard_reviews (user_id, next_review_at) WHERE next_review_at IS NOT NULL;
CREATE INDEX ix_flashcard_reviews_history ON flashcard_reviews (user_id, flashcard_id, reviewed_at DESC);

-- ============================================================================
-- 13. Study planning, tasks, sessions, budgets
-- ============================================================================
CREATE TABLE learning_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    course_id           UUID REFERENCES courses(id) ON DELETE RESTRICT,
    title               TEXT NOT NULL CHECK (char_length(btrim(title)) > 0),
    goal_description    TEXT,
    plan_type           TEXT NOT NULL DEFAULT 'study' CHECK (plan_type IN ('study','exam_revision','language','career','habit','other')),
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','completed','paused','cancelled')),
    starts_on           DATE,
    target_date         DATE,
    daily_minutes_goal  INTEGER CHECK (daily_minutes_goal IS NULL OR daily_minutes_goal > 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    CHECK (target_date IS NULL OR starts_on IS NULL OR target_date >= starts_on)
);
CREATE INDEX ix_learning_plans_user_status ON learning_plans (user_id, status, target_date);

CREATE TABLE learning_plan_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id           UUID NOT NULL REFERENCES learning_plans(id) ON DELETE CASCADE,
    topic_id          UUID REFERENCES course_topics(id) ON DELETE RESTRICT,
    title             TEXT NOT NULL,
    description       TEXT,
    planned_for       DATE,
    estimated_minutes INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes BETWEEN 5 AND 480),
    sort_order        INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','skipped','rescheduled')),
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (status <> 'completed' OR completed_at IS NOT NULL)
);
CREATE INDEX ix_learning_plan_items_due ON learning_plan_items (plan_id, planned_for, status);

CREATE TABLE academic_tasks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    course_id         UUID REFERENCES courses(id) ON DELETE RESTRICT,
    topic_id          UUID REFERENCES course_topics(id) ON DELETE RESTRICT,
    plan_item_id      UUID REFERENCES learning_plan_items(id) ON DELETE SET NULL,
    title             TEXT NOT NULL,
    task_type         TEXT NOT NULL DEFAULT 'study' CHECK (task_type IN ('study','assignment_reminder','exam','reading','application','work','personal','other')),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','cancelled','overdue')),
    due_at            TIMESTAMPTZ,
    estimated_minutes INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (completed_at IS NULL OR completed_at >= created_at)
);
CREATE INDEX ix_academic_tasks_user_due ON academic_tasks (user_id, status, due_at);

CREATE TABLE study_sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    course_id         UUID REFERENCES courses(id) ON DELETE SET NULL,
    topic_id          UUID REFERENCES course_topics(id) ON DELETE SET NULL,
    plan_item_id      UUID REFERENCES learning_plan_items(id) ON DELETE SET NULL,
    started_at        TIMESTAMPTZ NOT NULL,
    ended_at          TIMESTAMPTZ,
    duration_seconds  INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    session_type      TEXT NOT NULL DEFAULT 'study' CHECK (session_type IN ('study','focus','review','reading','practice','other')),
    self_rating       SMALLINT CHECK (self_rating IS NULL OR self_rating BETWEEN 1 AND 5),
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX ix_study_sessions_user_time ON study_sessions (user_id, started_at DESC);

CREATE TABLE focus_sessions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    study_session_id   UUID REFERENCES study_sessions(id) ON DELETE RESTRICT,
    focus_minutes      SMALLINT NOT NULL CHECK (focus_minutes BETWEEN 1 AND 240),
    break_minutes      SMALLINT NOT NULL CHECK (break_minutes BETWEEN 0 AND 120),
    status             TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','running','completed','abandoned')),
    started_at         TIMESTAMPTZ,
    ended_at           TIMESTAMPTZ,
    interruptions_count SMALLINT NOT NULL DEFAULT 0 CHECK (interruptions_count >= 0),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE budget_categories (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    category_kind  TEXT NOT NULL DEFAULT 'expense' CHECK (category_kind IN ('income','expense')),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_budget_category_name UNIQUE (user_id, name, category_kind)
);

CREATE TABLE budget_entries (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id    UUID REFERENCES budget_categories(id) ON DELETE RESTRICT,
    entry_kind     TEXT NOT NULL CHECK (entry_kind IN ('income','expense')),
    amount_minor   BIGINT NOT NULL CHECK (amount_minor > 0),
    currency_code  CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    occurred_on    DATE NOT NULL,
    description    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_budget_entries_user_date ON budget_entries (user_id, occurred_on DESC);

-- ============================================================================
-- 14. Notifications, reminders, outbox
-- ============================================================================
CREATE TABLE notification_kinds (
    code        TEXT PRIMARY KEY,
    name_ar     TEXT NOT NULL,
    description TEXT
);

CREATE TABLE notification_preferences (
    user_id           UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel           TEXT NOT NULL CHECK (channel IN ('telegram','email','web','push')),
    notification_type TEXT NOT NULL REFERENCES notification_kinds(code) ON DELETE CASCADE,
    is_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_hours_start TIME,
    quiet_hours_end   TIME,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, channel, notification_type),
    CHECK ((quiet_hours_start IS NULL) = (quiet_hours_end IS NULL))
);

CREATE TABLE notifications (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    organization_id    UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    notification_type  TEXT NOT NULL REFERENCES notification_kinds(code) ON DELETE RESTRICT,
    channel            TEXT NOT NULL CHECK (channel IN ('telegram','email','web','push')),
    title              TEXT NOT NULL,
    body               TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sending','sent','failed','cancelled','suppressed')),
    deduplication_key  TEXT UNIQUE,
    scheduled_at       TIMESTAMPTZ DEFAULT now(),
    sent_at            TIMESTAMPTZ,
    attempts           SMALLINT NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 100),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE INDEX ix_notifications_dispatch ON notifications (status, scheduled_at, created_at) WHERE status IN ('queued','failed');
CREATE INDEX ix_notifications_user ON notifications (user_id, created_at DESC);
COMMENT ON COLUMN notifications.deduplication_key IS 'مفتاح منع تكرار الإرسال (مثل: order_id + event_id)';

CREATE TABLE notification_attempts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id     UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    attempt_number      SMALLINT NOT NULL CHECK (attempt_number > 0),
    status              TEXT NOT NULL CHECK (status IN ('started','sent','failed','retry_scheduled')),
    external_message_id TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    error_code          TEXT,
    error_message_safe  TEXT,
    CONSTRAINT uq_notification_attempt UNIQUE (notification_id, attempt_number)
);

CREATE TABLE scheduled_reminders (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    academic_task_id       UUID REFERENCES academic_tasks(id) ON DELETE CASCADE,
    plan_item_id           UUID REFERENCES learning_plan_items(id) ON DELETE CASCADE,
    opportunity_id         UUID REFERENCES opportunities(id) ON DELETE CASCADE,
    booking_id             UUID REFERENCES bookings(id) ON DELETE CASCADE,
    subscription_id        UUID REFERENCES subscriptions(id) ON DELETE CASCADE,
    reminder_type          TEXT NOT NULL CHECK (reminder_type IN ('study_plan_item','opportunity_deadline','application_stage','booking','subscription_renewal','custom')),
    scheduled_for          TIMESTAMPTZ NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','queued','sent','cancelled','failed','dismissed')),
    notification_id        UUID REFERENCES notifications(id) ON DELETE RESTRICT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(academic_task_id, plan_item_id, opportunity_id, booking_id, subscription_id) <= 1)
);
CREATE INDEX ix_reminders_due ON scheduled_reminders (scheduled_for, status) WHERE status IN ('scheduled','queued');

CREATE TABLE transactional_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key       TEXT NOT NULL UNIQUE,
    event_type      TEXT NOT NULL,
    aggregate_type  TEXT NOT NULL,
    aggregate_id    UUID NOT NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    payload         JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','published','retry','dead_letter')),
    attempt_count   INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ,
    last_error_safe TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (published_at IS NULL OR published_at >= created_at)
);
CREATE INDEX ix_outbox_dispatch ON transactional_outbox (status, available_at, created_at) WHERE status IN ('pending','retry');

-- ============================================================================
-- 15. Institutional: articles, workshops, surveys
-- ============================================================================
CREATE TABLE knowledge_articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    language_code   TEXT NOT NULL DEFAULT 'ar',
    article_type    TEXT NOT NULL DEFAULT 'faq' CHECK (article_type IN ('faq','guide','policy','help','accessibility_resource')),
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    published_at    TIMESTAMPTZ,
    reviewed_by     UUID REFERENCES users(user_id) ON DELETE SET NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_knowledge_articles_org ON knowledge_articles (organization_id, status, language_code);

CREATE TABLE workshops (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id          UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    title                    TEXT NOT NULL,
    description              TEXT,
    host_user_id             UUID REFERENCES users(user_id) ON DELETE SET NULL,
    starts_at                TIMESTAMPTZ NOT NULL,
    ends_at                  TIMESTAMPTZ NOT NULL,
    location                 TEXT,
    online_url               TEXT,
    capacity                 INTEGER CHECK (capacity IS NULL OR capacity > 0),
    registration_deadline    TIMESTAMPTZ,
    status                   TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','full','completed','cancelled')),
    certificate_asset_id     UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    CHECK (registration_deadline IS NULL OR registration_deadline <= starts_at)
);

CREATE TABLE workshop_registrations (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workshop_id           UUID NOT NULL REFERENCES workshops(id) ON DELETE CASCADE,
    user_id               UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    status                TEXT NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','waitlisted','attended','no_show','cancelled')),
    registered_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    certificate_asset_id  UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    certificate_issued_at TIMESTAMPTZ,
    CONSTRAINT uq_workshop_registration UNIQUE (workshop_id, user_id)
);

CREATE TABLE surveys (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    title                    TEXT NOT NULL,
    description              TEXT,
    anonymous_responses      BOOLEAN NOT NULL DEFAULT TRUE,
    allow_multiple_responses BOOLEAN NOT NULL DEFAULT FALSE,
    status                   TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','closed','archived')),
    opens_at                 TIMESTAMPTZ,
    closes_at                TIMESTAMPTZ,
    created_by               UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (closes_at IS NULL OR opens_at IS NULL OR closes_at > opens_at)
);

CREATE TABLE survey_questions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id     UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL CHECK (question_type IN ('single_choice','multiple_choice','free_text','rating','boolean','scale_1_5','text')),
    required      BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order    SMALLINT NOT NULL DEFAULT 0,
    CONSTRAINT uq_survey_question_order UNIQUE (survey_id, sort_order)
);

CREATE TABLE survey_question_options (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    CONSTRAINT uq_survey_option_order UNIQUE (question_id, sort_order),
    CONSTRAINT uq_survey_option_id_q UNIQUE (id, question_id)
);

CREATE TABLE survey_responses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id             UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    respondent_user_id    UUID REFERENCES users(user_id) ON DELETE SET NULL,
    organization_member_id UUID REFERENCES organization_members(id) ON DELETE RESTRICT,
    submitted_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    response_metadata     JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(response_metadata) = 'object'),
    CHECK (respondent_user_id IS NULL OR organization_member_id IS NULL)
);
CREATE INDEX ix_survey_responses_survey_time ON survey_responses (survey_id, submitted_at);

CREATE TABLE survey_answers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    response_id         UUID NOT NULL REFERENCES survey_responses(id) ON DELETE CASCADE,
    question_id         UUID NOT NULL REFERENCES survey_questions(id) ON DELETE RESTRICT,
    selected_option_id  UUID REFERENCES survey_question_options(id) ON DELETE RESTRICT,
    answer_text         TEXT,
    answer_rating       SMALLINT CHECK (answer_rating IS NULL OR answer_rating BETWEEN 1 AND 5),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_survey_answer_question UNIQUE (response_id, question_id),
    CONSTRAINT fk_survey_selected_option_question FOREIGN KEY (selected_option_id, question_id)
        REFERENCES survey_question_options(id, question_id) ON DELETE RESTRICT,
    CHECK (num_nonnulls(selected_option_id, answer_text, answer_rating) <= 1)
);

-- ============================================================================
-- 16. Support, reviews, disputes, integrity cases
-- ============================================================================
CREATE TABLE support_tickets (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_number               BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    user_id                     UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    organization_id             UUID REFERENCES organizations(id) ON DELETE SET NULL,
    related_order_id            UUID REFERENCES orders(id) ON DELETE SET NULL,
    related_service_request_id  UUID REFERENCES service_requests(id) ON DELETE SET NULL,
    category                    TEXT NOT NULL CHECK (category IN ('billing','delivery','technical','account','service_quality','privacy','institutional','other')),
    priority                    SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    status                      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','waiting_user','waiting_staff','in_progress','resolved','closed','reopened')),
    subject                     TEXT NOT NULL,
    assigned_to                 UUID REFERENCES users(user_id) ON DELETE SET NULL,
    sla_due_at                  TIMESTAMPTZ,
    first_response_at           TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at                 TIMESTAMPTZ,
    closed_at                   TIMESTAMPTZ
);
CREATE INDEX ix_support_tickets_queue ON support_tickets (status, priority, created_at);
CREATE INDEX ix_support_tickets_user ON support_tickets (user_id, created_at DESC);

CREATE TABLE support_ticket_messages (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id          UUID NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    sender_user_id     UUID REFERENCES users(user_id) ON DELETE SET NULL,
    sender_kind        TEXT NOT NULL CHECK (sender_kind IN ('customer','staff','system')),
    body               TEXT NOT NULL,
    attachment_asset_id UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    internal_note      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_support_ticket_messages_time ON support_ticket_messages (ticket_id, created_at);

CREATE TABLE service_reviews (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    order_item_id      UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    booking_id         UUID REFERENCES bookings(id) ON DELETE RESTRICT,
    rating             SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text        TEXT,
    moderation_status  TEXT NOT NULL DEFAULT 'pending' CHECK (moderation_status IN ('pending','approved','hidden','rejected')),
    moderated_by       UUID REFERENCES users(user_id) ON DELETE SET NULL,
    moderated_at       TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(order_item_id, booking_id) = 1)
);
CREATE UNIQUE INDEX uq_review_user_order_item ON service_reviews (user_id, order_item_id) WHERE order_item_id IS NOT NULL;
CREATE UNIQUE INDEX uq_review_user_booking ON service_reviews (user_id, booking_id) WHERE booking_id IS NOT NULL;

CREATE TABLE disputes (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opened_by          UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    order_id           UUID REFERENCES orders(id) ON DELETE RESTRICT,
    payment_id         UUID REFERENCES payment_transactions(id) ON DELETE RESTRICT,
    service_request_id UUID REFERENCES service_requests(id) ON DELETE RESTRICT,
    ticket_id          UUID REFERENCES support_tickets(id) ON DELETE RESTRICT,
    dispute_type       TEXT NOT NULL CHECK (dispute_type IN ('payment','refund','quality','delivery','booking','policy','other')),
    status             TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','investigating','awaiting_evidence','resolved_customer','resolved_platform','closed')),
    summary            TEXT NOT NULL,
    resolution         TEXT,
    assigned_to        UUID REFERENCES users(user_id) ON DELETE SET NULL,
    opened_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at        TIMESTAMPTZ,
    CHECK (num_nonnulls(order_id, payment_id, service_request_id, ticket_id) >= 1),
    CHECK (resolved_at IS NULL OR resolved_at >= opened_at)
);

CREATE TABLE dispute_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispute_id         UUID NOT NULL REFERENCES disputes(id) ON DELETE CASCADE,
    actor_user_id      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    event_type         TEXT NOT NULL,
    description        TEXT,
    evidence_asset_id  UUID REFERENCES stored_assets(id) ON DELETE RESTRICT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE policy_cases (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reported_by        UUID REFERENCES users(user_id) ON DELETE SET NULL,
    subject_user_id    UUID REFERENCES users(user_id) ON DELETE RESTRICT,
    service_request_id UUID REFERENCES service_requests(id) ON DELETE RESTRICT,
    case_type          TEXT NOT NULL CHECK (case_type IN ('academic_integrity','copyright','abuse','privacy','safety','fraud','other')),
    reason             TEXT NOT NULL CHECK (reason IN ('exam_impersonation','contract_cheating','fabricated_references','plagiarized_content','leaked_materials','credential_request','abuse','fraud','other')),
    status             TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','triage','reviewing','actioned','dismissed','appealed','closed')),
    severity           SMALLINT NOT NULL DEFAULT 2 CHECK (severity BETWEEN 1 AND 5),
    policy_code        TEXT,
    evidence_summary   TEXT,
    decision           TEXT,
    decision_reason    TEXT,
    reviewed_by        UUID REFERENCES users(user_id) ON DELETE SET NULL,
    reviewed_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (reviewed_at IS NULL OR reviewed_at >= created_at),
    CONSTRAINT ck_policy_case_target CHECK (subject_user_id IS NOT NULL OR service_request_id IS NOT NULL)
);
CREATE INDEX ix_policy_cases_queue ON policy_cases (status, severity DESC, created_at);
COMMENT ON TABLE policy_cases IS 'سجل النزاهة الأكاديمية: انتحال، غش تعاقدي، مراجع مختلقة، مواد مسربة — مع القرار الإداري';

CREATE TABLE policy_case_events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_case_id UUID NOT NULL REFERENCES policy_cases(id) ON DELETE CASCADE,
    actor_user_id  UUID REFERENCES users(user_id) ON DELETE SET NULL,
    event_type     TEXT NOT NULL,
    note           TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 17. Study groups (peer support)
-- ============================================================================
CREATE TABLE study_groups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    created_by      UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    subject_id      UUID REFERENCES subjects(subject_id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    group_rules     TEXT NOT NULL,
    invite_code     TEXT UNIQUE,
    visibility      TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','organization','listed')),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','closed','moderated')),
    capacity        SMALLINT CHECK (capacity IS NULL OR capacity BETWEEN 2 AND 100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE study_group_members (
    group_id         UUID NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    member_role      TEXT NOT NULL DEFAULT 'member' CHECK (member_role IN ('owner','moderator','member')),
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','muted','removed','left')),
    joined_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    rules_accepted_at TIMESTAMPTZ,
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE study_group_messages (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id       UUID NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
    sender_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    body           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'visible' CHECK (status IN ('visible','hidden','removed','under_review')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    edited_at      TIMESTAMPTZ
);

-- ============================================================================
-- 18. Provider earnings & payouts (marketplace accounting)
-- ============================================================================
CREATE TABLE provider_earnings (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id            UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE RESTRICT,
    source_order_item_id   UUID REFERENCES order_items(id) ON DELETE RESTRICT,
    source_booking_id      UUID REFERENCES bookings(id) ON DELETE RESTRICT,
    currency_code          CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    gross_amount_minor     BIGINT NOT NULL CHECK (gross_amount_minor >= 0),
    platform_commission_minor BIGINT NOT NULL CHECK (platform_commission_minor >= 0),
    net_amount_minor       BIGINT NOT NULL CHECK (net_amount_minor >= 0),
    status                 TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','payable','in_payout','paid','void')),
    recognized_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at                TIMESTAMPTZ,
    CHECK (num_nonnulls(source_order_item_id, source_booking_id) = 1),
    CHECK (platform_commission_minor <= gross_amount_minor),
    CHECK (net_amount_minor = gross_amount_minor - platform_commission_minor),
    CHECK (paid_at IS NULL OR paid_at >= recognized_at)
);
CREATE UNIQUE INDEX uq_provider_earning_order ON provider_earnings (provider_id, source_order_item_id) WHERE source_order_item_id IS NOT NULL;
CREATE UNIQUE INDEX uq_provider_earning_booking ON provider_earnings (provider_id, source_booking_id) WHERE source_booking_id IS NOT NULL;
CREATE INDEX ix_provider_earnings_payable ON provider_earnings (provider_id, currency_code, status, recognized_at)
    WHERE status IN ('pending','payable','in_payout');

CREATE TABLE provider_payouts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id           UUID NOT NULL REFERENCES provider_profiles(id) ON DELETE RESTRICT,
    currency_code         CHAR(3) NOT NULL REFERENCES currencies(code) ON DELETE RESTRICT,
    total_amount_minor    BIGINT NOT NULL CHECK (total_amount_minor > 0),
    status                TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','approved','processing','succeeded','failed','cancelled')),
    external_reference    TEXT UNIQUE,
    requested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at          TIMESTAMPTZ,
    failure_reason_safe   TEXT,
    CHECK (processed_at IS NULL OR processed_at >= requested_at)
);

CREATE TABLE provider_payout_items (
    payout_id    UUID NOT NULL REFERENCES provider_payouts(id) ON DELETE RESTRICT,
    earning_id   UUID NOT NULL UNIQUE REFERENCES provider_earnings(id) ON DELETE RESTRICT,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    PRIMARY KEY (payout_id, earning_id)
);

-- ============================================================================
-- 19. Audit (append-only)
-- ============================================================================
CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    action_code     TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       UUID,
    target_kind     TEXT,
    target_id       TEXT,
    outcome         TEXT NOT NULL DEFAULT 'success' CHECK (outcome IN ('success','denied','failure')),
    request_id      TEXT,
    ip_hash         CHAR(64) CHECK (ip_hash IS NULL OR ip_hash ~ '^[0-9a-fA-F]{64}$'),
    change_summary  JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(change_summary) = 'object'),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_events_actor_time ON audit_events (actor_user_id, occurred_at DESC);
CREATE INDEX ix_audit_events_entity_time ON audit_events (entity_type, entity_id, occurred_at DESC);
CREATE INDEX ix_audit_events_target ON audit_events (target_kind, target_id);
CREATE INDEX ix_audit_events_org_time ON audit_events (organization_id, occurred_at DESC) WHERE organization_id IS NOT NULL;
COMMENT ON TABLE audit_events IS 'append-only بمشغل يمنع UPDATE/DELETE؛ ضمانة تشغيلية: لا تُمنح صلاحيات تعديل لأي دور تطبيقي';

-- ============================================================================
-- 20. FUNCTIONS & TRIGGERS
-- ============================================================================
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN NEW.updated_at := clock_timestamp(); RETURN NEW; END $$;

-- Order status transition enforced from reference table (db1 pattern)
CREATE FUNCTION validate_order_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM order_status_transitions t
        WHERE t.from_status = OLD.status AND t.to_status = NEW.status
    ) THEN
        RAISE EXCEPTION 'انتقال حالة طلب غير مسموح: % -> %', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Order totals recalculated from lines
CREATE FUNCTION recalculate_order_totals() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_order_id UUID;
    v_subtotal NUMERIC(30,0);
    v_discount NUMERIC(30,0);
    v_tax BIGINT;
BEGIN
    v_order_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
    SELECT COALESCE(SUM(quantity::numeric * unit_price_minor::numeric), 0),
           COALESCE(SUM(line_discount_minor::numeric), 0)
      INTO v_subtotal, v_discount
      FROM student_platform.order_items WHERE order_id = v_order_id;
    SELECT tax_total_minor INTO v_tax FROM student_platform.orders WHERE id = v_order_id FOR UPDATE;
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;
    IF v_subtotal > 9223372036854775807 OR v_discount > 9223372036854775807 THEN
        RAISE EXCEPTION 'Order totals exceed BIGINT for order %', v_order_id;
    END IF;
    UPDATE student_platform.orders
       SET subtotal_minor = v_subtotal::bigint,
           discount_total_minor = v_discount::bigint,
           total_minor = (v_subtotal - v_discount + v_tax)::bigint,
           updated_at = clock_timestamp()
     WHERE id = v_order_id;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

-- Order totals validator (defense in depth)
CREATE FUNCTION validate_order_totals() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_subtotal NUMERIC(30,0);
    v_discount NUMERIC(30,0);
BEGIN
    SELECT COALESCE(SUM(quantity::numeric * unit_price_minor::numeric), 0),
           COALESCE(SUM(line_discount_minor::numeric), 0)
      INTO v_subtotal, v_discount
      FROM student_platform.order_items WHERE order_id = NEW.id;
    IF v_subtotal <> NEW.subtotal_minor OR v_discount <> NEW.discount_total_minor THEN
        RAISE EXCEPTION 'Order subtotal/discount must match its immutable line items';
    END IF;
    IF NEW.total_minor::numeric <> v_subtotal - v_discount + NEW.tax_total_minor::numeric THEN
        RAISE EXCEPTION 'Order total must equal subtotal - discounts + tax';
    END IF;
    RETURN NEW;
END $$;

-- Guard: order items immutable after draft
CREATE FUNCTION guard_order_item_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_order_id UUID;
    v_currency CHAR(3);
    v_status TEXT;
    v_price_currency CHAR(3);
    v_price_amount BIGINT;
    v_price_offer UUID;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.order_id IS DISTINCT FROM OLD.order_id THEN
        RAISE EXCEPTION 'An order item cannot be moved to another order';
    END IF;
    v_order_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.order_id ELSE NEW.order_id END;
    SELECT status, currency_code INTO v_status, v_currency
      FROM student_platform.orders WHERE id = v_order_id FOR UPDATE;
    IF v_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Order items can only be changed while the order is draft';
    END IF;
    IF TG_OP <> 'DELETE' THEN
        IF NEW.currency_code <> v_currency THEN
            RAISE EXCEPTION 'Order item currency must match order currency';
        END IF;
        IF NEW.offer_price_id IS NOT NULL THEN
            SELECT currency_code, amount_minor, offer_id INTO v_price_currency, v_price_amount, v_price_offer
              FROM student_platform.offer_prices
             WHERE id = NEW.offer_price_id
               AND valid_from <= now()
               AND (valid_until IS NULL OR valid_until > now());
            IF NOT FOUND OR v_price_currency <> NEW.currency_code
               OR v_price_amount <> NEW.unit_price_minor
               OR v_price_offer <> NEW.offer_id THEN
                RAISE EXCEPTION 'Order item price snapshot does not match a current price for that offer';
            END IF;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

-- Guard: financial fields of order immutable after draft
CREATE FUNCTION guard_order_financial_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'draft' AND (
        NEW.user_id IS DISTINCT FROM OLD.user_id OR
        NEW.organization_id IS DISTINCT FROM OLD.organization_id OR
        NEW.currency_code IS DISTINCT FROM OLD.currency_code OR
        NEW.subtotal_minor IS DISTINCT FROM OLD.subtotal_minor OR
        NEW.discount_total_minor IS DISTINCT FROM OLD.discount_total_minor OR
        NEW.tax_total_minor IS DISTINCT FROM OLD.tax_total_minor OR
        NEW.total_minor IS DISTINCT FROM OLD.total_minor
    ) THEN
        RAISE EXCEPTION 'Financial and ownership fields are immutable after order draft';
    END IF;
    RETURN NEW;
END $$;

-- Payment order match + status transitions
CREATE FUNCTION validate_payment_order() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_user UUID;
    v_currency CHAR(3);
    v_total BIGINT;
    v_order_status TEXT;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT (
            (OLD.status = 'pending' AND NEW.status IN ('succeeded','failed','cancelled','expired')) OR
            (OLD.status = 'succeeded' AND NEW.status IN ('partially_refunded','refunded')) OR
            (OLD.status = 'partially_refunded' AND NEW.status = 'refunded')
        ) THEN
            RAISE EXCEPTION 'Invalid payment status transition: % -> %', OLD.status, NEW.status;
        END IF;
    END IF;
    SELECT user_id, currency_code, total_minor, status
      INTO v_user, v_currency, v_total, v_order_status
      FROM student_platform.orders WHERE id = NEW.order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Payment references an unknown order'; END IF;
    IF NEW.user_id <> v_user OR NEW.currency_code <> v_currency OR NEW.amount_minor <> v_total THEN
        RAISE EXCEPTION 'Payment payer, currency, and amount must match the order';
    END IF;
    IF v_order_status NOT IN ('pending_payment','paid','in_fulfillment','completed','refund_pending','refunded','partially_refunded') THEN
        RAISE EXCEPTION 'Order status % does not permit a payment attempt', v_order_status;
    END IF;
    IF NEW.provider = 'telegram_stars' AND NEW.currency_code <> 'XTR' THEN
        RAISE EXCEPTION 'Telegram Stars payments must use XTR';
    END IF;
    IF NEW.status = 'succeeded' AND NEW.provider = 'telegram_stars' AND NEW.telegram_payment_charge_id IS NULL THEN
        RAISE EXCEPTION 'A successful Telegram Stars payment must retain telegram_payment_charge_id';
    END IF;
    IF NEW.status = 'succeeded' THEN NEW.succeeded_at := COALESCE(NEW.succeeded_at, now()); END IF;
    RETURN NEW;
END $$;

-- Refund validation on INSERT OR UPDATE (db2 pattern)
CREATE FUNCTION validate_refund() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_currency CHAR(3);
    v_paid_amount BIGINT;
    v_status TEXT;
    v_existing NUMERIC(30,0);
BEGIN
    SELECT currency_code, amount_minor, status
      INTO v_currency, v_paid_amount, v_status
      FROM student_platform.payment_transactions WHERE id = NEW.payment_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Refund references an unknown payment'; END IF;
    IF NEW.currency_code <> v_currency THEN
        RAISE EXCEPTION 'Refund currency must match payment currency';
    END IF;
    IF v_status NOT IN ('succeeded','partially_refunded','refunded') AND NEW.status IN ('processing','succeeded') THEN
        RAISE EXCEPTION 'Only a successful payment can be refunded';
    END IF;
    SELECT COALESCE(SUM(amount_minor), 0) INTO v_existing
      FROM student_platform.refunds
     WHERE payment_id = NEW.payment_id
       AND status IN ('requested','processing','succeeded')
       AND id <> NEW.id;
    IF v_existing + (CASE WHEN NEW.status IN ('requested','processing','succeeded') THEN NEW.amount_minor ELSE 0 END) > v_paid_amount THEN
        RAISE EXCEPTION 'Total active refunds cannot exceed the captured payment amount';
    END IF;
    RETURN NEW;
END $$;

-- Bundle: kind check + cycle check
CREATE FUNCTION prevent_bundle_cycle() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_bundle_kind TEXT;
    v_component_kind TEXT;
    v_cycle BOOLEAN;
BEGIN
    PERFORM pg_advisory_xact_lock(712361842::bigint);
    SELECT offer_type INTO v_bundle_kind FROM student_platform.product_offers WHERE id = NEW.bundle_offer_id FOR UPDATE;
    SELECT offer_type INTO v_component_kind FROM student_platform.product_offers WHERE id = NEW.component_offer_id FOR UPDATE;
    IF v_bundle_kind IS NULL OR v_component_kind IS NULL THEN
        RAISE EXCEPTION 'Offer not found in bundle component' USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF v_bundle_kind <> 'bundle' THEN
        RAISE EXCEPTION 'Only bundle offers may contain components' USING ERRCODE = 'check_violation';
    END IF;
    IF v_component_kind = 'bundle' THEN
        RAISE EXCEPTION 'Nested bundles are not allowed' USING ERRCODE = 'check_violation';
    END IF;
    WITH RECURSIVE descendants(offer_id) AS (
        SELECT component_offer_id FROM student_platform.product_offer_components
         WHERE bundle_offer_id = NEW.component_offer_id
        UNION
        SELECT c.component_offer_id FROM student_platform.product_offer_components c
          JOIN descendants d ON c.bundle_offer_id = d.offer_id
    )
    SELECT EXISTS (SELECT 1 FROM descendants WHERE offer_id = NEW.bundle_offer_id) INTO v_cycle;
    IF v_cycle THEN RAISE EXCEPTION 'Bundle component would introduce a cycle'; END IF;
    RETURN NEW;
END $$;

-- Booking capacity guard
CREATE FUNCTION validate_booking_capacity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_capacity INTEGER;
    v_active_count BIGINT;
BEGIN
    SELECT capacity INTO v_capacity FROM student_platform.bookings WHERE id = NEW.booking_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Booking does not exist'; END IF;
    IF NEW.participant_status IN ('booked','attended','no_show') THEN
        SELECT count(*) INTO v_active_count
          FROM student_platform.booking_participants
         WHERE booking_id = NEW.booking_id
           AND participant_status IN ('booked','attended','no_show')
           AND id <> NEW.id;
        IF v_active_count >= v_capacity THEN
            RAISE EXCEPTION 'Booking capacity reached';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Provider time off vs booking conflict
CREATE FUNCTION validate_booking_time_off() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM student_platform.provider_profiles WHERE id = NEW.provider_id FOR UPDATE;
    IF EXISTS (
        SELECT 1 FROM student_platform.provider_time_off pto
         WHERE pto.provider_id = NEW.provider_id
           AND tstzrange(pto.starts_at, pto.ends_at, '[)') && tstzrange(NEW.starts_at, NEW.ends_at, '[)')
    ) AND NEW.status IN ('pending_confirmation','confirmed','in_progress') THEN
        RAISE EXCEPTION 'Provider has blocked this time range';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION validate_provider_time_off() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM student_platform.provider_profiles WHERE id = NEW.provider_id FOR UPDATE;
    IF EXISTS (
        SELECT 1 FROM student_platform.bookings b
         WHERE b.provider_id = NEW.provider_id
           AND b.status IN ('pending_confirmation','confirmed','in_progress')
           AND tstzrange(b.starts_at, b.ends_at, '[)') && tstzrange(NEW.starts_at, NEW.ends_at, '[)')
    ) THEN
        RAISE EXCEPTION 'Time off conflicts with an active booking';
    END IF;
    RETURN NEW;
END $$;

-- Provider review: completed booking + participant
CREATE FUNCTION validate_provider_review() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_status TEXT;
BEGIN
    SELECT b.status INTO v_status FROM student_platform.bookings b WHERE b.id = NEW.booking_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Booking not found'; END IF;
    IF v_status <> 'completed' THEN
        RAISE EXCEPTION 'Provider review requires a completed booking';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM student_platform.booking_participants bp
        WHERE bp.booking_id = NEW.booking_id AND bp.user_id = NEW.user_id
    ) THEN
        RAISE EXCEPTION 'Reviewer must be a participant in the booking';
    END IF;
    RETURN NEW;
END $$;

-- Service review: verified purchase
CREATE FUNCTION validate_service_review() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_order_user UUID;
    v_order_status TEXT;
    v_booking_status TEXT;
    v_participant_status TEXT;
BEGIN
    IF NEW.order_item_id IS NOT NULL THEN
        SELECT o.user_id, o.status INTO v_order_user, v_order_status
          FROM student_platform.order_items oi
          JOIN student_platform.orders o ON o.id = oi.order_id
         WHERE oi.id = NEW.order_item_id;
        IF NOT FOUND OR v_order_user <> NEW.user_id OR v_order_status NOT IN ('completed','partially_refunded') THEN
            RAISE EXCEPTION 'A product review requires a completed purchase by the reviewing user';
        END IF;
    ELSE
        SELECT b.status, bp.participant_status INTO v_booking_status, v_participant_status
          FROM student_platform.bookings b
          JOIN student_platform.booking_participants bp ON bp.booking_id = b.id
         WHERE b.id = NEW.booking_id AND bp.user_id = NEW.user_id;
        IF NOT FOUND OR v_booking_status <> 'completed' OR v_participant_status <> 'attended' THEN
            RAISE EXCEPTION 'A session review requires an attended, completed booking';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Entitlement source validation
CREATE FUNCTION validate_entitlement_source() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_source_user UUID;
    v_source_org UUID;
    v_order_status TEXT;
BEGIN
    IF NEW.source_order_item_id IS NOT NULL THEN
        SELECT o.user_id, o.organization_id, o.status INTO v_source_user, v_source_org, v_order_status
          FROM student_platform.order_items oi
          JOIN student_platform.orders o ON o.id = oi.order_id
         WHERE oi.id = NEW.source_order_item_id;
        IF NOT FOUND OR v_order_status NOT IN ('paid','in_fulfillment','completed','partially_refunded') THEN
            RAISE EXCEPTION 'Entitlement order source must reference a paid order';
        END IF;
        IF NEW.user_id IS NOT NULL AND NEW.user_id <> v_source_user THEN
            RAISE EXCEPTION 'User entitlement must belong to the purchasing user';
        END IF;
        IF NEW.organization_id IS NOT NULL AND NEW.organization_id IS DISTINCT FROM v_source_org THEN
            RAISE EXCEPTION 'Organization entitlement must match the purchasing organization';
        END IF;
    ELSIF NEW.source_subscription_id IS NOT NULL THEN
        SELECT user_id INTO v_source_user FROM student_platform.subscriptions WHERE id = NEW.source_subscription_id;
        IF NOT FOUND OR NEW.user_id IS DISTINCT FROM v_source_user OR NEW.organization_id IS NOT NULL THEN
            RAISE EXCEPTION 'Subscription entitlements must belong to the subscription user';
        END IF;
    ELSIF NEW.source_organization_license_id IS NOT NULL THEN
        SELECT organization_id INTO v_source_org FROM student_platform.organization_licenses WHERE id = NEW.source_organization_license_id;
        IF NOT FOUND OR NEW.organization_id IS DISTINCT FROM v_source_org OR NEW.user_id IS NOT NULL THEN
            RAISE EXCEPTION 'License entitlements must belong to the licensed organization';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- License seat guard
CREATE FUNCTION validate_license_assignment() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_seat_limit INTEGER;
    v_license_status TEXT;
    v_starts_at TIMESTAMPTZ;
    v_ends_at TIMESTAMPTZ;
    v_current_seats BIGINT;
    v_member_status TEXT;
BEGIN
    SELECT member_status INTO v_member_status
      FROM student_platform.organization_members WHERE id = NEW.organization_member_id;
    IF NEW.status = 'active' AND v_member_status IS DISTINCT FROM 'active' THEN
        RAISE EXCEPTION 'Only active organization members can hold an active seat';
    END IF;
    IF NEW.status = 'released' AND NEW.released_at IS NULL THEN
        NEW.released_at := now();
    ELSIF NEW.status <> 'released' AND NEW.released_at IS NOT NULL THEN
        RAISE EXCEPTION 'released_at must be NULL unless assignment status is released';
    END IF;
    SELECT seat_limit, status, starts_at, ends_at
      INTO v_seat_limit, v_license_status, v_starts_at, v_ends_at
      FROM student_platform.organization_licenses WHERE id = NEW.organization_license_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Organization license not found'; END IF;
    IF NEW.status = 'active' THEN
        IF v_license_status <> 'active' OR v_starts_at > now() OR (v_ends_at IS NOT NULL AND v_ends_at <= now()) THEN
            RAISE EXCEPTION 'Cannot assign a seat on an inactive or out-of-period license';
        END IF;
        SELECT count(*) INTO v_current_seats
          FROM student_platform.organization_license_assignments
         WHERE organization_license_id = NEW.organization_license_id
           AND status = 'active' AND id <> NEW.id;
        IF v_seat_limit IS NOT NULL AND v_current_seats >= v_seat_limit THEN
            RAISE EXCEPTION 'Organization license seat limit reached';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Survey response single-response limit
CREATE FUNCTION validate_survey_response() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_multiple BOOLEAN;
BEGIN
    SELECT allow_multiple_responses INTO v_multiple
      FROM student_platform.surveys WHERE id = NEW.survey_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Survey does not exist'; END IF;
    IF NOT v_multiple AND NEW.respondent_user_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM student_platform.survey_responses sr
         WHERE sr.survey_id = NEW.survey_id
           AND sr.respondent_user_id = NEW.respondent_user_id
           AND sr.id <> NEW.id
    ) THEN
        RAISE EXCEPTION 'This survey accepts only one response per identified user';
    END IF;
    RETURN NEW;
END $$;

-- Survey answer consistency
CREATE FUNCTION validate_survey_answer() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_response_survey UUID;
    v_question_survey UUID;
BEGIN
    SELECT survey_id INTO v_response_survey FROM student_platform.survey_responses WHERE id = NEW.response_id;
    SELECT survey_id INTO v_question_survey FROM student_platform.survey_questions WHERE id = NEW.question_id;
    IF v_response_survey IS NULL OR v_question_survey IS NULL OR v_response_survey <> v_question_survey THEN
        RAISE EXCEPTION 'Survey answer question must belong to the response survey';
    END IF;
    RETURN NEW;
END $$;

-- Service request linkage
CREATE FUNCTION validate_service_request_linkage() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_order_user UUID;
    v_item_offer UUID;
    v_item_service UUID;
    v_offer_service UUID;
    v_item_order_status TEXT;
BEGIN
    IF NEW.order_item_id IS NOT NULL THEN
        SELECT o.user_id, oi.offer_id, oi.service_definition_id, o.status
          INTO v_order_user, v_item_offer, v_item_service, v_item_order_status
          FROM student_platform.order_items oi
          JOIN student_platform.orders o ON o.id = oi.order_id
         WHERE oi.id = NEW.order_item_id;
        IF NOT FOUND OR v_order_user <> NEW.user_id THEN
            RAISE EXCEPTION 'Service request order item must belong to the requesting user';
        END IF;
        IF NEW.offer_id IS NOT NULL AND NEW.offer_id <> v_item_offer THEN
            RAISE EXCEPTION 'Service request offer must match purchased item';
        END IF;
        IF NEW.service_definition_id IS DISTINCT FROM v_item_service AND v_item_service IS NOT NULL THEN
            RAISE EXCEPTION 'Service request definition must match purchased line';
        END IF;
        IF v_item_order_status NOT IN ('paid','in_fulfillment','completed','partially_refunded') THEN
            RAISE EXCEPTION 'A paid order is required before linking a paid service request';
        END IF;
    END IF;
    IF NEW.offer_id IS NOT NULL THEN
        SELECT primary_service_id INTO v_offer_service FROM student_platform.product_offers WHERE id = NEW.offer_id;
        IF v_offer_service IS NOT NULL AND v_offer_service <> NEW.service_definition_id THEN
            RAISE EXCEPTION 'Service definition does not match the selected offer';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Audit immutability (append-only)
CREATE FUNCTION reject_audit_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events are append-only; create a correcting event instead';
END $$;

-- State history loggers (transparent)
CREATE FUNCTION log_order_state() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO student_platform.order_events (order_id, previous_status, new_status, actor_type)
        VALUES (NEW.id, CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END, NEW.status,
            CASE COALESCE(NULLIF(current_setting('app.actor_type', true), ''),
                CASE COALESCE(NULLIF(current_setting('app.change_source', true), ''), 'system')
                    WHEN 'telegram' THEN 'user'
                    WHEN 'webhook' THEN 'payment_provider'
                    WHEN 'admin' THEN 'admin'
                    WHEN 'user' THEN 'user'
                    ELSE 'system' END)
                WHEN 'user' THEN 'user'
                WHEN 'admin' THEN 'admin'
                WHEN 'payment_provider' THEN 'payment_provider'
                WHEN 'webhook' THEN 'payment_provider'
                ELSE 'system' END);
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION log_service_request_state() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO student_platform.service_request_events
            (service_request_id, previous_status, new_status, actor_user_id, note_safe)
        VALUES (NEW.id, CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END, NEW.status,
            NULLIF(current_setting('app.actor_user_id', true), '')::uuid, 'state changed');
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION log_subscription_state() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO student_platform.subscription_events
            (subscription_id, previous_status, new_status, event_type)
        VALUES (NEW.id, CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END, NEW.status,
            CASE WHEN TG_OP = 'INSERT' THEN 'created' ELSE 'status_changed' END);
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION log_booking_state() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO student_platform.booking_events
            (booking_id, previous_status, new_status, note_safe)
        VALUES (NEW.id, CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END, NEW.status, 'state changed');
    END IF;
    RETURN NEW;
END $$;

-- Payment success → order paid
CREATE FUNCTION mark_order_paid_on_payment_success() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'succeeded' AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status) THEN
        UPDATE student_platform.orders
           SET status = CASE WHEN status = 'pending_payment' THEN 'paid' ELSE status END,
               paid_at = COALESCE(paid_at, NEW.succeeded_at, now()),
               updated_at = clock_timestamp()
         WHERE id = NEW.order_id AND status IN ('pending_payment','paid');
    END IF;
    RETURN NEW;
END $$;

-- Refund succeeded → payment & order refunded
CREATE FUNCTION update_refunded_status() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_payment_amount BIGINT;
    v_refunded NUMERIC(30,0);
    v_order_id UUID;
    v_order_total BIGINT;
    v_order_refunded NUMERIC(30,0);
BEGIN
    IF NEW.status = 'succeeded' OR (TG_OP = 'UPDATE' AND OLD.status = 'succeeded' AND NEW.status <> 'succeeded') THEN
        SELECT amount_minor, order_id INTO v_payment_amount, v_order_id
          FROM student_platform.payment_transactions WHERE id = NEW.payment_id FOR UPDATE;
        SELECT COALESCE(SUM(amount_minor), 0) INTO v_refunded
          FROM student_platform.refunds WHERE payment_id = NEW.payment_id AND status = 'succeeded';
        UPDATE student_platform.payment_transactions
           SET status = CASE WHEN v_refunded = 0 THEN 'succeeded'
                             WHEN v_refunded >= v_payment_amount THEN 'refunded'
                             ELSE 'partially_refunded' END,
               updated_at = clock_timestamp()
         WHERE id = NEW.payment_id;
        SELECT total_minor INTO v_order_total FROM student_platform.orders WHERE id = v_order_id FOR UPDATE;
        SELECT COALESCE(SUM(r.amount_minor), 0) INTO v_order_refunded
          FROM student_platform.refunds r
          JOIN student_platform.payment_transactions p ON p.id = r.payment_id
         WHERE p.order_id = v_order_id AND r.status = 'succeeded';
        UPDATE student_platform.orders
           SET status = CASE WHEN v_order_refunded = 0 THEN status
                             WHEN v_order_refunded >= v_order_total THEN 'refunded'
                             ELSE 'partially_refunded' END,
               updated_at = clock_timestamp()
         WHERE id = v_order_id
           AND status IN ('paid','in_fulfillment','completed','refund_pending','partially_refunded','refunded');
    END IF;
    RETURN NEW;
END $$;

-- Payout validation
CREATE FUNCTION validate_provider_payout_item() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_earning_provider UUID;
    v_earning_currency CHAR(3);
    v_earning_net BIGINT;
    v_earning_status TEXT;
    v_payout_provider UUID;
    v_payout_currency CHAR(3);
    v_payout_total BIGINT;
    v_payout_status TEXT;
    v_allocated NUMERIC(30,0);
BEGIN
    SELECT provider_id, currency_code, net_amount_minor, status
      INTO v_earning_provider, v_earning_currency, v_earning_net, v_earning_status
      FROM student_platform.provider_earnings WHERE id = NEW.earning_id FOR UPDATE;
    SELECT provider_id, currency_code, total_amount_minor, status
      INTO v_payout_provider, v_payout_currency, v_payout_total, v_payout_status
      FROM student_platform.provider_payouts WHERE id = NEW.payout_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Provider payout does not exist'; END IF;
    IF v_earning_provider <> v_payout_provider OR v_earning_currency <> v_payout_currency THEN
        RAISE EXCEPTION 'Payout and earning provider/currency must match';
    END IF;
    IF v_earning_status NOT IN ('pending','payable') THEN
        RAISE EXCEPTION 'Only unpaid earnings can be assigned to a payout';
    END IF;
    IF NEW.amount_minor <> v_earning_net THEN
        RAISE EXCEPTION 'Payout item must settle the earning net amount exactly';
    END IF;
    IF v_payout_status IN ('succeeded','cancelled') THEN
        RAISE EXCEPTION 'Cannot add an earning to a completed or cancelled payout';
    END IF;
    SELECT COALESCE(SUM(amount_minor), 0) INTO v_allocated
      FROM student_platform.provider_payout_items
     WHERE payout_id = NEW.payout_id AND earning_id <> NEW.earning_id;
    IF v_allocated + NEW.amount_minor > v_payout_total THEN
        RAISE EXCEPTION 'Payout items exceed the payout header total';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION validate_provider_payout_state() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_items_total NUMERIC(30,0);
BEGIN
    IF NEW.status = 'succeeded' AND OLD.status IS DISTINCT FROM NEW.status THEN
        SELECT COALESCE(SUM(amount_minor), 0) INTO v_items_total
          FROM student_platform.provider_payout_items WHERE payout_id = NEW.id;
        IF v_items_total <> NEW.total_amount_minor OR v_items_total = 0 THEN
            RAISE EXCEPTION 'Successful payout total must equal its payout items';
        END IF;
        NEW.processed_at := COALESCE(NEW.processed_at, now());
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION mark_earnings_paid() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'succeeded' AND OLD.status IS DISTINCT FROM NEW.status THEN
        UPDATE student_platform.provider_earnings e
           SET status = 'paid', paid_at = COALESCE(paid_at, NEW.processed_at, now())
          FROM student_platform.provider_payout_items i
         WHERE i.payout_id = NEW.id AND i.earning_id = e.id
           AND e.status IN ('pending','payable');
    END IF;
    RETURN NEW;
END $$;

-- Anonymize user (db1 pattern) — keeps financial/history records intact
CREATE FUNCTION fn_anonymize_user(p_user_id UUID, p_actor_user_id UUID DEFAULT NULL)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE v_new_telegram_id BIGINT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM student_platform.users u WHERE u.user_id = p_user_id) THEN
        RAISE EXCEPTION 'المستخدم غير موجود: %', p_user_id USING ERRCODE = 'foreign_key_violation';
    END IF;
    v_new_telegram_id := nextval('student_platform.seq_anonymized_telegram_id');

    UPDATE student_platform.users SET
        display_name = NULL,
        account_status = 'anonymized',
        last_seen_at = NULL,
        anonymized_at = now(),
        updated_at = now()
    WHERE user_id = p_user_id AND account_status <> 'anonymized';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'المستخدم غير موجود أو هوية مخفاة مسبقًا: %', p_user_id;
    END IF;

    UPDATE student_platform.external_identities SET
        telegram_user_id = CASE WHEN provider = 'telegram' THEN v_new_telegram_id ELSE telegram_user_id END,
        provider_username = NULL,
        provider_subject = CASE WHEN provider = 'telegram' THEN 'anonymized:' || v_new_telegram_id::text ELSE provider_subject END,
        metadata = '{}'::jsonb
    WHERE user_id = p_user_id;

    UPDATE student_platform.user_learning_profiles SET
        institution_name = NULL, major_or_track = NULL, study_year = NULL,
        country_code = NULL, goals = NULL, preferences = '{}'::jsonb, updated_at = now()
    WHERE user_id = p_user_id;

    UPDATE student_platform.stored_assets SET
        deleted_at = COALESCE(deleted_at, now()),
        metadata = '{}'::jsonb
    WHERE owner_user_id = p_user_id AND asset_kind = 'user_upload';

    INSERT INTO student_platform.audit_events
        (actor_user_id, action_code, entity_type, entity_id, target_kind, target_id, change_summary)
    VALUES (p_actor_user_id, 'user.anonymized', 'user', p_user_id, 'user', p_user_id::text,
            jsonb_build_object('reason', 'anonymization_requested'));
END $$;

COMMENT ON FUNCTION fn_anonymize_user(UUID, UUID) IS
    'إخفاء هوية المستخدم مع الحفاظ على سلامة السجلات المالية والتاريخية (بديل الحذف)';

-- ============================================================================
-- 20b. Attach triggers
-- ============================================================================
-- updated_at automatic
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users','user_learning_profiles','organizations','service_definitions',
        'product_offers','orders','payment_transactions','subscriptions',
        'provider_profiles','bookings','opportunities','opportunity_applications',
        'courses','topic_progress','flashcards','learning_plans','academic_tasks',
        'support_tickets','refunds','organization_licenses','platform_settings'
    ] LOOP
        EXECUTE format('CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON student_platform.%I FOR EACH ROW EXECUTE FUNCTION student_platform.set_updated_at()', 'u_' || t, t);
    END LOOP;
END $$;

-- Order guards
CREATE TRIGGER trg_orders_transition BEFORE UPDATE OF status ON orders
    FOR EACH ROW EXECUTE FUNCTION validate_order_transition();
CREATE TRIGGER trg_orders_totals_validate BEFORE INSERT OR UPDATE OF subtotal_minor, discount_total_minor, tax_total_minor, total_minor, status ON orders
    FOR EACH ROW EXECUTE FUNCTION validate_order_totals();
CREATE TRIGGER trg_orders_financial_guard BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION guard_order_financial_snapshot();
CREATE TRIGGER trg_order_items_guard BEFORE INSERT OR UPDATE OR DELETE ON order_items
    FOR EACH ROW EXECUTE FUNCTION guard_order_item_mutation();
CREATE TRIGGER trg_order_items_totals AFTER INSERT OR UPDATE OR DELETE ON order_items
    FOR EACH ROW EXECUTE FUNCTION recalculate_order_totals();
CREATE TRIGGER trg_order_state_history AFTER INSERT OR UPDATE OF status ON orders
    FOR EACH ROW EXECUTE FUNCTION log_order_state();

-- Payment guards
CREATE TRIGGER trg_payment_matches_order BEFORE INSERT OR UPDATE OF order_id, user_id, currency_code, amount_minor, provider, status, telegram_payment_charge_id ON payment_transactions
    FOR EACH ROW EXECUTE FUNCTION validate_payment_order();
CREATE TRIGGER trg_payment_success_paid AFTER INSERT OR UPDATE OF status ON payment_transactions
    FOR EACH ROW EXECUTE FUNCTION mark_order_paid_on_payment_success();

-- Refunds
CREATE TRIGGER trg_refunds_validate BEFORE INSERT OR UPDATE OF payment_id, currency_code, amount_minor, status ON refunds
    FOR EACH ROW EXECUTE FUNCTION validate_refund();
CREATE TRIGGER trg_refund_state AFTER INSERT OR UPDATE OF status ON refunds
    FOR EACH ROW EXECUTE FUNCTION update_refunded_status();

-- Bundle
CREATE TRIGGER trg_bundle_cycle_guard BEFORE INSERT OR UPDATE OF bundle_offer_id, component_offer_id ON product_offer_components
    FOR EACH ROW EXECUTE FUNCTION prevent_bundle_cycle();

-- Booking
CREATE TRIGGER trg_booking_capacity BEFORE INSERT OR UPDATE OF booking_id, participant_status ON booking_participants
    FOR EACH ROW EXECUTE FUNCTION validate_booking_capacity();
CREATE TRIGGER trg_booking_time_off_guard BEFORE INSERT OR UPDATE OF provider_id, starts_at, ends_at, status ON bookings
    FOR EACH ROW EXECUTE FUNCTION validate_booking_time_off();
CREATE TRIGGER trg_provider_time_off_guard BEFORE INSERT OR UPDATE OF provider_id, starts_at, ends_at ON provider_time_off
    FOR EACH ROW EXECUTE FUNCTION validate_provider_time_off();
CREATE TRIGGER trg_booking_state_history AFTER INSERT OR UPDATE OF status ON bookings
    FOR EACH ROW EXECUTE FUNCTION log_booking_state();

-- Reviews
CREATE TRIGGER trg_provider_review_guard BEFORE INSERT OR UPDATE OF user_id, booking_id ON provider_reviews
    FOR EACH ROW EXECUTE FUNCTION validate_provider_review();
CREATE TRIGGER trg_service_review_guard BEFORE INSERT OR UPDATE OF user_id, order_item_id, booking_id ON service_reviews
    FOR EACH ROW EXECUTE FUNCTION validate_service_review();

-- Entitlements, licenses
CREATE TRIGGER trg_entitlement_source_validate BEFORE INSERT OR UPDATE OF entitlement_id, user_id, organization_id, source_order_item_id, source_subscription_id, source_organization_license_id ON entitlement_grants
    FOR EACH ROW EXECUTE FUNCTION validate_entitlement_source();
CREATE TRIGGER trg_license_assignment_validate BEFORE INSERT OR UPDATE OF organization_license_id, organization_member_id, organization_id, status ON organization_license_assignments
    FOR EACH ROW EXECUTE FUNCTION validate_license_assignment();

-- Surveys
CREATE TRIGGER trg_survey_response_limit BEFORE INSERT OR UPDATE OF survey_id, respondent_user_id ON survey_responses
    FOR EACH ROW EXECUTE FUNCTION validate_survey_response();
CREATE TRIGGER trg_survey_answer_consistency BEFORE INSERT OR UPDATE OF response_id, question_id, selected_option_id ON survey_answers
    FOR EACH ROW EXECUTE FUNCTION validate_survey_answer();

-- Service requests
CREATE TRIGGER trg_service_request_linkage BEFORE INSERT OR UPDATE OF user_id, service_definition_id, offer_id, order_item_id ON service_requests
    FOR EACH ROW EXECUTE FUNCTION validate_service_request_linkage();
CREATE TRIGGER trg_service_request_state_history AFTER INSERT OR UPDATE OF status ON service_requests
    FOR EACH ROW EXECUTE FUNCTION log_service_request_state();

-- Subscriptions
CREATE TRIGGER trg_subscription_state_history AFTER INSERT OR UPDATE OF status ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION log_subscription_state();

-- Audit
CREATE TRIGGER trg_audit_no_update_delete BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();

-- Payouts
CREATE TRIGGER trg_payout_item_validate BEFORE INSERT OR UPDATE OF payout_id, earning_id, amount_minor ON provider_payout_items
    FOR EACH ROW EXECUTE FUNCTION validate_provider_payout_item();
CREATE TRIGGER trg_payout_state_validate BEFORE UPDATE OF status ON provider_payouts
    FOR EACH ROW EXECUTE FUNCTION validate_provider_payout_state();
CREATE TRIGGER trg_payout_mark_earnings AFTER UPDATE OF status ON provider_payouts
    FOR EACH ROW EXECUTE FUNCTION mark_earnings_paid();

-- ============================================================================
-- 21. SEED DATA
-- ============================================================================
-- Currencies
INSERT INTO currencies (code, name_ar, minor_unit_digits, is_fiat) VALUES
    ('XTR', 'نجوم تيليجرام', 0, FALSE),
    ('USD', 'دولار أمريكي', 2, TRUE),
    ('EUR', 'يورو', 2, TRUE),
    ('SAR', 'ريال سعودي', 2, TRUE),
    ('AED', 'درهم إماراتي', 2, TRUE),
    ('EGP', 'جنيه مصري', 2, TRUE),
    ('QAR', 'ريال قطري', 2, TRUE),
    ('KWD', 'دينار كويتي', 3, TRUE),
    ('BHD', 'دينار بحريني', 3, TRUE),
    ('OMR', 'ريال عماني', 3, TRUE),
    ('JOD', 'دينار أردني', 3, TRUE),
    ('MAD', 'درهم مغربي', 2, TRUE),
    ('DZD', 'دينار جزائري', 2, TRUE),
    ('TND', 'دينار تونسي', 3, TRUE),
    ('IQD', 'دينار عراقي', 3, TRUE),
    ('LYD', 'دينار ليبي', 3, TRUE),
    ('YER', 'ريال يمني', 2, TRUE);

-- Order statuses
INSERT INTO order_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('draft',              'مسودة',                   FALSE, 1),
    ('pending_payment',    'بانتظار الدفع',           FALSE, 2),
    ('paid',               'مدفوع',                   FALSE, 3),
    ('in_fulfillment',     'قيد التنفيذ',             FALSE, 4),
    ('completed',          'مكتمل',                   TRUE,  5),
    ('cancelled',          'ملغى',                    TRUE,  6),
    ('refund_pending',     'بانتظار الاسترداد',       FALSE, 7),
    ('refunded',           'مسترد كاملًا',            TRUE,  8),
    ('partially_refunded', 'مسترد جزئيًا',            FALSE, 9),
    ('failed',             'فاشل',                    TRUE, 10);

INSERT INTO order_status_transitions (from_status, to_status) VALUES
    ('draft','pending_payment'),
    ('draft','cancelled'),
    ('pending_payment','paid'),
    ('pending_payment','cancelled'),
    ('pending_payment','failed'),
    ('paid','in_fulfillment'),
    ('paid','refund_pending'),
    ('in_fulfillment','completed'),
    ('in_fulfillment','refund_pending'),
    ('completed','refund_pending'),
    ('refund_pending','refunded'),
    ('refund_pending','partially_refunded'),
    ('refund_pending','in_fulfillment'),
    ('refund_pending','completed'),
    ('partially_refunded','refund_pending'),
    ('partially_refunded','refunded');

INSERT INTO payment_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('pending','معلقة',FALSE,1),
    ('succeeded','ناجحة',FALSE,2),
    ('failed','فاشلة',TRUE,3),
    ('cancelled','ملغاة',TRUE,4),
    ('expired','منتهية',TRUE,5),
    ('refunded','مستردة كاملًا',TRUE,6),
    ('partially_refunded','مستردة جزئيًا',FALSE,7);

INSERT INTO subscription_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('pending','معلقة',FALSE,1),
    ('trialing','تجريبية',FALSE,2),
    ('active','نشطة',FALSE,3),
    ('past_due','متأخرة التجديد',FALSE,4),
    ('paused','موقوفة مؤقتًا',FALSE,5),
    ('cancelled','ملغاة',FALSE,6),
    ('expired','منتهية',TRUE,7),
    ('incomplete','غير مكتملة',FALSE,8);

INSERT INTO request_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('submitted','مستلم',FALSE,1),
    ('awaiting_payment','بانتظار الدفع',FALSE,2),
    ('queued','في الطابور',FALSE,3),
    ('assigned','معيَّن لمنفذ',FALSE,4),
    ('in_progress','قيد التنفيذ',FALSE,5),
    ('needs_info','بحاجة معلومات',FALSE,6),
    ('review','قيد المراجعة',FALSE,7),
    ('completed','مكتمل',TRUE,8),
    ('cancelled','ملغى',TRUE,9),
    ('failed','فاشل',TRUE,10),
    ('rejected_policy','مرفوض لأسباب السياسة',TRUE,11);

INSERT INTO booking_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('pending_confirmation','بانتظار التأكيد',FALSE,1),
    ('confirmed','مؤكد',FALSE,2),
    ('in_progress','الجلسة جارية',FALSE,3),
    ('completed','مكتمل',TRUE,4),
    ('cancelled_by_user','ملغى من المستخدم',TRUE,5),
    ('cancelled_by_provider','ملغى من مقدم الخدمة',TRUE,6),
    ('no_show','عدم حضور',TRUE,7),
    ('cancelled','ملغى',TRUE,8),
    ('rescheduled','أعيدت جدولته',TRUE,9),
    ('rejected','مرفوض',TRUE,10);

INSERT INTO delivery_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('queued','في الطابور',FALSE,1),
    ('pending','معلّق',FALSE,2),
    ('available','متاح',FALSE,3),
    ('sending','قيد الإرسال',FALSE,4),
    ('sent','أُرسل',FALSE,5),
    ('delivered','تم التسليم',FALSE,6),
    ('failed','فشل',FALSE,7),
    ('resent','أُعيد الإرسال',FALSE,8),
    ('expired','انتهت صلاحيته',TRUE,9),
    ('revoked','مسحوب',TRUE,10);

INSERT INTO catalog_lifecycle_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('draft','مسودة',FALSE,1),
    ('review','قيد المراجعة',FALSE,2),
    ('published','منشور',FALSE,3),
    ('active','نشط',FALSE,4),
    ('paused','موقوف مؤقتًا',FALSE,5),
    ('archived','مؤرشف',TRUE,6),
    ('retired','مسحوب',TRUE,7);

INSERT INTO refund_statuses (code, name_ar, is_terminal, sort_order) VALUES
    ('requested','مطلوب',FALSE,1),
    ('approved','معتمد',FALSE,2),
    ('processing','قيد المعالجة',FALSE,3),
    ('succeeded','ناجح',TRUE,4),
    ('failed','فاشل',TRUE,5),
    ('rejected','مرفوض',TRUE,6),
    ('cancelled','ملغى',TRUE,7);

-- Consent types
INSERT INTO consent_types (code, name_ar, description_ar, requires_explicit_opt_in) VALUES
    ('privacy_policy','سياسة الخصوصية','موافقة على معالجة البيانات وفق السياسة المعلنة',FALSE),
    ('terms_of_service','شروط الاستخدام','الشروط العامة للخدمة',FALSE),
    ('educational_use_policy','سياسة الاستخدام التعليمي','الالتزام بحدود الدعم التعليمي دون غش تعاقدي',TRUE),
    ('ai_processing','معالجة بالذكاء الاصطناعي','موافقة صريحة لمعالجة المدخلات بالأنظمة الآلية',TRUE),
    ('file_processing','معالجة الملفات المرفوعة','السماح بمعالجة الملفات لتنفيذ الخدمة المطلوبة',TRUE),
    ('marketing','الرسائل الترويجية','استقبال العروض والتحديثات التسويقية (اختياري)',TRUE),
    ('age_verification','التحقق العمري','إقرار تجاوز الحد العمري المطلوب للسوق',TRUE),
    ('parental_consent','موافقة ولي الأمر','موافقة ولي الأمر للمستخدمين القاصرين',TRUE),
    ('data_retention_notice','إشعار مدة الاحتفاظ','إقرار بفهم سياسة الاحتفاظ بالبيانات وحذفها',FALSE);

-- Notification kinds
INSERT INTO notification_kinds (code, name_ar, description) VALUES
    ('order_updates','تحديثات الطلبات','تغيرات حالة الطلب والدفع والتسليم'),
    ('subscription_updates','تحديثات الاشتراك','تجديد وإيقاف وانتهاء الاشتراكات'),
    ('session_reminders','تذكير الجلسات','مواعيد الجلسات مع المدرسين'),
    ('study_reminders','تذكيرات المذاكرة','بنود خطة المذاكرة والمواعيد النهائية'),
    ('daily_question','السؤال اليومي','سؤال تدريبي يومي مع تفسير الإجابة'),
    ('opportunity_alerts','تنبيهات الفرص','منح وتدريب ووظائف مطابقة بعد التحقق'),
    ('workshop_updates','تحديثات الورش','تسجيل الورش وحضورها وشهاداتها'),
    ('support_replies','ردود الدعم','ردود فريق الدعم على التذاكر'),
    ('marketing','رسائل ترويجية','عروض وخصومات (تحتاج موافقة اختيارية)'),
    ('security_notices','إشعارات أمنية','تنبيهات متعلقة بحماية الحساب');

-- Education levels
INSERT INTO education_levels (code, name_ar, sort_order) VALUES
    ('school','مدرسة',10),
    ('high_school','ثانوية',15),
    ('university','جامعة',20),
    ('postgraduate','دراسات عليا',30),
    ('job_seeker','باحث عن عمل',40),
    ('professional','محترف',50),
    ('other','أخرى',90);

-- Subjects
INSERT INTO subjects (code, name_ar, name_en) VALUES
    ('math','الرياضيات','Mathematics'),
    ('physics','الفيزياء','Physics'),
    ('chemistry','الكيمياء','Chemistry'),
    ('biology','الأحياء','Biology'),
    ('arabic','اللغة العربية','Arabic Language'),
    ('english','اللغة الإنجليزية','English Language'),
    ('cs','علوم الحاسب','Computer Science'),
    ('programming','البرمجة','Programming'),
    ('statistics','الإحصاء','Statistics'),
    ('economics','الاقتصاد','Economics'),
    ('business','إدارة الأعمال','Business Administration'),
    ('law','القانون','Law'),
    ('medicine','الطب','Medicine'),
    ('engineering','الهندسة','Engineering'),
    ('media','الإعلام','Media');

-- Opportunity types
INSERT INTO opportunity_types (type_id, code, name_ar) VALUES
    (1,'scholarship','منحة دراسية'),
    (2,'grant','منحة مالية/بحثية'),
    (3,'internship','تدريب'),
    (4,'job','وظيفة'),
    (5,'competition','مسابقة'),
    (6,'fellowship','زمالة'),
    (7,'admission','قبول جامعي'),
    (8,'exam','اختبار معياري');

-- Roles
INSERT INTO roles (code, name_ar, scope, description, is_system_role) VALUES
    ('student','طالب/مستخدم','platform','المستخدم النهائي للخدمات',TRUE),
    ('platform_admin','مدير النظام','platform','إدارة كاملة',TRUE),
    ('moderator','مشرف','platform','مراجعة المحتوى والسياسات',TRUE),
    ('support_agent','موظف دعم','platform','معالجة التذاكر',TRUE),
    ('finance_officer','مسؤول مالية','platform','المدفوعات والاستردادات',TRUE),
    ('service_provider','مقدم خدمة','platform','مدرس أو مدقق أو مرشد',TRUE),
    ('org_owner','مالك مؤسسة','organization','مالك نطاق المؤسسة',TRUE),
    ('org_admin','مدير مؤسسة','organization','إدارة المؤسسة',TRUE),
    ('org_staff','موظف مؤسسة','organization','موظف في المؤسسة',TRUE);

-- Permissions
INSERT INTO permissions (code, module, description) VALUES
    ('catalog.read','catalog','قراءة الكتالوج'),
    ('catalog.manage','catalog','إدارة الكتالوج والعروض'),
    ('orders.read','orders','قراءة الطلبات'),
    ('orders.manage','orders','إدارة دورة حياة الطلبات'),
    ('payments.read','payments','قراءة المدفوعات والاستردادات'),
    ('payments.refund','payments','إدارة الاستردادات'),
    ('subscriptions.manage','subscriptions','إدارة الاشتراكات'),
    ('entitlements.grant','entitlements','منح وإلغاء الاستحقاقات'),
    ('requests.read_assigned','requests','قراءة الطلبات المعينة'),
    ('requests.execute','requests','تنفيذ وتسليم الطلبات'),
    ('requests.assign','requests','تعيين الطلبات'),
    ('providers.view','providers','عرض مقدمي الخدمات'),
    ('providers.verify','providers','توثيق مقدمي الخدمات'),
    ('bookings.view','bookings','عرض الحجوزات'),
    ('bookings.manage','bookings','إدارة الحجوزات'),
    ('surveys.manage','surveys','إدارة الاستبيانات'),
    ('reports.read','reports','قراءة التقارير'),
    ('institutions.manage','institutions','إدارة المؤسسات'),
    ('licenses.manage','institutions','إدارة التراخيص'),
    ('opportunities.manage','opportunities','إدارة الفرص'),
    ('opportunities.verify','opportunities','التحقق من روابط الفرص'),
    ('tickets.handle','support','معالجة التذاكر'),
    ('disputes.resolve','support','حل النزاعات'),
    ('policy.review','integrity','مراجعة النزاهة'),
    ('users.view','users','عرض المستخدمين'),
    ('users.manage','users','إدارة حالات المستخدمين'),
    ('users.anonymize','users','إخفاء الهوية'),
    ('audit.read','audit','قراءة سجل التدقيق'),
    ('settings.manage','settings','تعديل إعدادات المنصة'),
    ('content.manage','content','إدارة المحتوى التعليمي');

-- Role → permissions
INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.code = 'platform_admin';
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN
        ('catalog.read','orders.read','requests.read_assigned','requests.assign','providers.view','bookings.view','surveys.manage','opportunities.manage','opportunities.verify','tickets.handle','policy.review','users.view','reports.read')
        WHERE r.code = 'moderator';
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN ('orders.read','payments.read','tickets.handle','users.view') WHERE r.code = 'support_agent';
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN ('payments.read','payments.refund','disputes.resolve','reports.read','orders.read') WHERE r.code = 'finance_officer';
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN ('catalog.read','requests.read_assigned','requests.execute','bookings.view','bookings.manage') WHERE r.code = 'service_provider';
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN ('catalog.read','orders.read','institutions.manage','licenses.manage','reports.read','bookings.manage','surveys.manage') WHERE r.code IN ('org_owner','org_admin');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN ('catalog.read','orders.read','bookings.manage','surveys.manage') WHERE r.code = 'org_staff';

-- Entitlement definitions
INSERT INTO entitlement_definitions (code, name_ar, description, unit) VALUES
    ('service.request','حق طلب خدمة','إذن تقديم طلب خدمة مدفوع أو مشمول','request'),
    ('question_bank.access','الوصول لبنك الأسئلة','الوصول لبنك أسئلة معد','access'),
    ('study_plan.access','الوصول لخطة المذاكرة','الوصول لميزات تخطيط المذاكرة','access'),
    ('tutoring.session','جلسات تدريس','عدد جلسات التدريس المشمولة','session'),
    ('tutoring.minutes','دقائق التدريس','عدد دقائق التدريس المشمولة','minute'),
    ('digital.download','تنزيل منتج رقمي','الوصول لمنتج رقمي مشترى','file'),
    ('channel.access','الوصول لقناة تيليجرام','الوصول لقناة مشمولة في الاشتراك','access'),
    ('organization.seat','مقعد ترخيص مؤسسي','مقعد داخل ترخيص مؤسسة','seat');

-- Service categories (from db1: 10 categories)
INSERT INTO service_categories (code, name_ar, description, sort_order) VALUES
    ('instant_auto','خدمات فورية آلية وشبه آلية','يقدم الطلب ويحصل على النتيجة خلال دقائق (1-20)',1),
    ('human_expert','خدمات بشرية ومراجعة خبراء','جلسات ومراجعات يقودها مدرسون ومدققون (21-35)',2),
    ('subscriptions','اشتراكات شهرية وفصلية','منافع متجددة أسبوعيًا عبر عضويات وقنوات (36-48)',3),
    ('digital_goods','منتجات رقمية تباع مرة واحدة','قوالب وكتيبات وبنوك أسئلة وملفات (49-65)',4),
    ('institutional','خدمات الجامعات والمعلمين ومراكز التدريب','بوتات واستبيانات وأنظمة للمؤسسات (66-78)',5),
    ('ai_skills','الذكاء الاصطناعي والمهارات التقنية','تدريب على الأدوات والمهارات الرقمية (79-93)',6),
    ('employment','التوظيف والتدريب والانتقال للعمل','فجوة المهارات والسيرة والمقابلات (94-108)',7),
    ('scholarships','المنح والقبول والاختبارات المعيارية','مطابقة المنح والاستعداد للاختبارات (109-123)',8),
    ('tutoring','دروس خصوصية وتخصيص أكاديمي','مطابقة مدرسين وجلسات متابعة (124-138)',9),
    ('wellbeing','الرفاه الدراسي والإتاحة','تنظيم وإحالة وخدمات دعم غير علاجية (139-153)',10);

-- 153 services (draft)
INSERT INTO service_definitions (source_item_number, category_id, code, title_ar, summary_ar, lifecycle_status, default_delivery_mode)
SELECT v.num, c.id, v.code, v.title_ar, v.summary_ar, 'draft', 'configurable'
FROM (VALUES
    (1::smallint,'instant_auto'::text,'svc_001'::text,'شرح مفهوم دراسي'::text,'شرح مبسط ومثال وسؤال تحقق'::text),
    (2,'instant_auto','svc_002','تفكيك سؤال صعب','تحويل السؤال إلى معطيات ومطلوب وفكرة وخطوات إرشادية دون إنجاز نيابة عن الطالب'),
    (3,'instant_auto','svc_003','مصحح خطوات الرياضيات والفيزياء','تحديد موضع الخطأ واقتراح المحاولة التالية'),
    (4,'instant_auto','svc_004','مولد أسئلة تدريبية','أسئلة حسب المادة والموضوع مع إجابات تفسيرية'),
    (5,'instant_auto','svc_005','اختبار قصير مخصص','5-20 سؤالًا مع درجة وتوصية'),
    (6,'instant_auto','svc_006','بطاقات مراجعة','تحويل نص إلى بطاقات سؤال/جواب'),
    (7,'instant_auto','svc_007','تلخيص محاضرة','استخراج نقاط ومصطلحات وأسئلة'),
    (8,'instant_auto','svc_008','تحويل المحاضرة إلى أسئلة شفوية','محاكاة أسئلة المدرس'),
    (9,'instant_auto','svc_009','إنشاء خطة مراجعة قبل الاختبار','جدول يومي مخصص'),
    (10,'instant_auto','svc_010','مؤقت مذاكرة بنظام التركيز','جلسات تركيز واستراحة مع سجل'),
    (11,'instant_auto','svc_011','محلل أخطاء الاختبارات','تصنيف الأخطاء إلى فهم/حفظ/قراءة/إدارة وقت'),
    (12,'instant_auto','svc_012','قاموس تخصصي عربي/إنجليزي','تعريف ونطق ومثال'),
    (13,'instant_auto','svc_013','مدقق اقتباس أولي','فحص بيانات المصدر دون اختلاق مراجع'),
    (14,'instant_auto','svc_014','مساعد تحويل الوحدات','شرح العملية لا رقم نهائي فقط'),
    (15,'instant_auto','svc_015','تحويل PDF إلى ملاحظات منظمة','استخراج عناوين ونقاط'),
    (16,'instant_auto','svc_016','تحويل صورة السبورة إلى نص','OCR مع تنبيه للمراجعة'),
    (17,'instant_auto','svc_017','مولد أمثلة إضافية','أمثلة جديدة بتدرج صعوبة'),
    (18,'instant_auto','svc_018','شرح كود برمجي','شرح وتمارين مع منع تسليم مشروع كامل'),
    (19,'instant_auto','svc_019','مراجعة سريعة قبل الاختبار','قائمة «ما يجب أن أعرفه»'),
    (20,'instant_auto','svc_020','خدمة سؤال يومي','سؤال يومي مع تفسير'),
    (21,'human_expert','svc_021','جلسة تدريس فردية','25 أو 50 دقيقة مع مدرس'),
    (22,'human_expert','svc_022','جلسة حل مشكلات موجّهة','توجيه بأسئلة لا إجابة جاهزة'),
    (23,'human_expert','svc_023','مراجعة خطة مذاكرة','تعديل حمل وأولويات'),
    (24,'human_expert','svc_024','تصحيح اختبار تجريبي يدوي','ملاحظات على المنهجية'),
    (25,'human_expert','svc_025','شرح عملي للبرمجة أو الإحصاء','تطبيق على بيانات/كود الطالب'),
    (26,'human_expert','svc_026','تدريب عرض تقديمي','مراجعة شرائح وإلقاء'),
    (27,'human_expert','svc_027','محاكاة مناقشة أو دفاع','أسئلة متوقعة وتغذية راجعة'),
    (28,'human_expert','svc_028','تدقيق لغوي لبحث الطالب','تحسين مع حفظ أفكار الطالب'),
    (29,'human_expert','svc_029','مراجعة بنية البحث','تقييم فرضية ومنهج واستنتاج'),
    (30,'human_expert','svc_030','مراجعة مراجع وتنسيقها','APA/MLA/Chicago دون اختلاق'),
    (31,'human_expert','svc_031','مراجعة سيرة ذاتية لطالب','نسخة أولى مع ملاحظات'),
    (32,'human_expert','svc_032','تدقيق رسالة دافع','تحسين الصياغة دون اختلاق إنجازات'),
    (33,'human_expert','svc_033','جلسة إرشاد اختيار تخصص','خيارات وأسئلة بحث لا تشخيص'),
    (34,'human_expert','svc_034','مدرس محادثة لغة','محادثة صوتية مع واجب'),
    (35,'human_expert','svc_035','تدريب مقابلة بالإنجليزية','محاكاة وتقييم نطق وبنية'),
    (36,'subscriptions','svc_036','عضوية بنك أسئلة حسب المرحلة','تحديث أسبوعي وتصنيف'),
    (37,'subscriptions','svc_037','نادي مذاكرة يومي','خطة اليوم وتقرير أسبوعي'),
    (38,'subscriptions','svc_038','قناة ملخصات أصلية','ملخصات يملكها المشروع أو مرخصة'),
    (39,'subscriptions','svc_039','اشتراك مراجعة قبل الاختبارات','محتوى مكثف 30/60 يومًا'),
    (40,'subscriptions','svc_040','عضوية دعم واجبات','شرح وتلميحات ومراجعة محاولات'),
    (41,'subscriptions','svc_041','عضوية لغة','مفردات يومية واختبار وجلسة'),
    (42,'subscriptions','svc_042','عضوية برمجة','تمارين ومراجعة كود ولقاء أسبوعي'),
    (43,'subscriptions','svc_043','اشتراك تنبيهات الفرص','فرص مع تحقق بشري'),
    (44,'subscriptions','svc_044','اشتراك ملخصات أخبار التخصص','روابط مصادر'),
    (45,'subscriptions','svc_045','اشتراك مجموعة دراسة صغيرة','تقسيم حسب المادة ومشرف'),
    (46,'subscriptions','svc_046','اشتراك مرشد شخصي خفيف','مراجعة أسبوعية دون علاج نفسي'),
    (47,'subscriptions','svc_047','حزمة مراجعة شهرية للأهل','تقرير بموافقة صريحة'),
    (48,'subscriptions','svc_048','لوحة متابعة تقدم','رسوم لمعدلات وموضوعات ضعيفة'),
    (49,'digital_goods','svc_049','قوالب Notion/Google Sheets للمذاكرة','قوالب جاهزة للتنظيم'),
    (50,'digital_goods','svc_050','قالب جدول فصل دراسي','حساب ساعات وأولوية'),
    (51,'digital_goods','svc_051','حزم بطاقات مراجعة','مصطلحات طبية أو قواعد'),
    (52,'digital_goods','svc_052','كتيبات مراجعة أصلية','من إعداد المشروع أو مرخصة'),
    (53,'digital_goods','svc_053','بنوك أسئلة أصلية','حلول تفسيرية'),
    (54,'digital_goods','svc_054','قوالب كتابة بحث','صفحة عنوان ومخطط ومراجع'),
    (55,'digital_goods','svc_055','قوالب عروض تعليمية','مع إرشادات'),
    (56,'digital_goods','svc_056','حزمة مختبر أو مشروع برمجي','لا تصلح للتسليم كما هي'),
    (57,'digital_goods','svc_057','دليل Zotero وأدوات المراجع','دليل عملي'),
    (58,'digital_goods','svc_058','دليل مهارات الدراسة','استرجاع نشط وتكرار متباعد'),
    (59,'digital_goods','svc_059','دليل الاستعداد لاختبار معياري','خطة وتمارين أصلية'),
    (60,'digital_goods','svc_060','ملفات صوتية لنطق المصطلحات','تسجيلات نطق'),
    (61,'digital_goods','svc_061','نماذج سيرة وبريد أكاديمي','نماذج قابلة للتعديل'),
    (62,'digital_goods','svc_062','قائمة فحص التقديم','مستندات ومواعيد'),
    (63,'digital_goods','svc_063','حزمة أسئلة مقابلات التدريب','طريقة بناء الإجابة'),
    (64,'digital_goods','svc_064','قوالب توثيق المصادر','أنماط الاقتباس الشائعة'),
    (65,'digital_goods','svc_065','حزمة قابلية الوصول','تحويل مواد مرخصة إلى صوت/نص'),
    (66,'institutional','svc_066','بوت أسئلة شائعة للطلاب الجدد','تسجيل وجداول وخدمات'),
    (67,'institutional','svc_067','نظام حجز الساعات المكتبية','للمدرسين والمرشدين'),
    (68,'institutional','svc_068','بوت تذكير بالمواعيد والواجبات','عند توفر التقويم'),
    (69,'institutional','svc_069','استبيان رضا الطلاب','تقارير مجمعة مجهلة'),
    (70,'institutional','svc_070','توزيع اختبارات تدريبية','تحليل إجمالي'),
    (71,'institutional','svc_071','مساعد استقبال طلبات الدعم','تحويل للقسم المناسب'),
    (72,'institutional','svc_072','دليل رقمي للمنح داخل المؤسسة','فرص داخلية محدثة'),
    (73,'institutional','svc_073','بوت تسجيل ورش العمل','شهادات أو روابط تسجيل'),
    (74,'institutional','svc_074','تحويل مواد المدرس إلى اختبارات','بمراجع واضحة'),
    (75,'institutional','svc_075','تدريب المعلمين على AI المسؤول','تخطيط وتغذية راجعة'),
    (76,'institutional','svc_076','لوحة إنذار مبكر اختيارية','مؤشرات يوافق عليها الطالب'),
    (77,'institutional','svc_077','نظام تذاكر للدعم التقني','داخل تيليجرام'),
    (78,'institutional','svc_078','قنوات مواد خاصة بمؤسسة','صلاحيات واشتراكات داخلية'),
    (79,'ai_skills','svc_079','مدرب استخدام AI للطالب','صياغة طلبات وتوثيق الاستخدام'),
    (80,'ai_skills','svc_080','مراجع جودة مخرجات AI','فحص أخطاء وهلوسة وتحيز'),
    (81,'ai_skills','svc_081','حزمة AI حسب التخصص','سيناريوهات آمنة'),
    (82,'ai_skills','svc_082','مساعد بناء ملف أعمال','تحويل مشاريع إلى صفحة'),
    (83,'ai_skills','svc_083','تدقيق معلومات مضللة','فحص ادعاءات دون ضمان زائف'),
    (84,'ai_skills','svc_084','مدرب تحليل بيانات للمبتدئين','تمارين وتفسير رسوم'),
    (85,'ai_skills','svc_085','مسار Python لغير المتخصصين','دروس قصيرة وتصحيح كود'),
    (86,'ai_skills','svc_086','مسار SQL/Excel للتوظيف','حالات عمل حقيقية'),
    (87,'ai_skills','svc_087','مدرب Git/GitHub','مستودع وREADME وفروع'),
    (88,'ai_skills','svc_088','مراجع مشروع برمجي','تصميم واختبارات دون بناء كامل'),
    (89,'ai_skills','svc_089','محاكي مقابلة تقنية','تقييم طريقة التفكير'),
    (90,'ai_skills','svc_090','مدرب أمن سيبراني','مختبرات آمنة دون إرشادات ضارة'),
    (91,'ai_skills','svc_091','مساعد التحول الرقمي','أدوات رقمية للتخصصات غير التقنية'),
    (92,'ai_skills','svc_092','اختبار مهارات رقمية','تشخيص فجوات ومسار تعلم'),
    (93,'ai_skills','svc_093','نشرة أسبوعية لمهارات التخصص','روابط ومهام تطبيقية'),
    (94,'employment','svc_094','محلل فجوة المهارات','مقارنة سيرة بإعلان وظيفة'),
    (95,'employment','svc_095','محسن سيرة ATS','كلمات مفتاحية دون اختلاق خبرة'),
    (96,'employment','svc_096','مولد إنجازات قابلة للإثبات','أرقام وأدلة لا تضخيم'),
    (97,'employment','svc_097','مدرب مقابلة STAR','موقف/مهمة/فعل/نتيجة'),
    (98,'employment','svc_098','محاكي مقابلة أول وظيفة','تقييم وخطة تحسين'),
    (99,'employment','svc_099','مدرب مقابلة بالإنجليزية','تصحيح مفردات ونطق'),
    (100,'employment','svc_100','مراجع LinkedIn للطلاب','عنوان ونبذة ومشاريع'),
    (101,'employment','svc_101','بناء صفحة Portfolio','قالب مع أدلة ونتائج'),
    (102,'employment','svc_102','مولد خطة مشاريع','3 مشاريع صغيرة مرتبطة بالوظيفة'),
    (103,'employment','svc_103','متتبع طلبات التدريب','حالة وموعد متابعة'),
    (104,'employment','svc_104','تنبيهات وظائف مفلترة','تحقق من المصدر'),
    (105,'employment','svc_105','مراجعة رسالة التقديم','تخصيص لكل إعلان'),
    (106,'employment','svc_106','مدرب تواصل مهني','قوالب محترمة'),
    (107,'employment','svc_107','دليل الرواتب والمهارات','مصادر عامة دون ضمان'),
    (108,'employment','svc_108','تحدي 30 يومًا للجاهزية','مهمة يومية'),
    (109,'scholarships','svc_109','محرك منح مخصص','مطابقة حسب البلد والتخصص'),
    (110,'scholarships','svc_110','تقويم مواعيد المنح','تنبيهات 30/14/3 أيام'),
    (111,'scholarships','svc_111','فاحص أهلية أولي','شرح سبب المطابقة دون وعد'),
    (112,'scholarships','svc_112','مراجع نموذج طلب جامعة','اكتمال ووضوح دون انتحال'),
    (113,'scholarships','svc_113','مدرب مقال شخصي','استخراج قصة وبناء مخطط'),
    (114,'scholarships','svc_114','مراجع خطاب دافع','مطابقة معايير المنحة'),
    (115,'scholarships','svc_115','محاكي مقابلة منحة','دافع وأثر وخطة'),
    (116,'scholarships','svc_116','حزمة ترجمة ملف قبول','قاموس ومراجعة تنسيق'),
    (117,'scholarships','svc_117','مساعد معادلة شهادات','خطوات وروابط رسمية'),
    (118,'scholarships','svc_118','مساعد اختيار الجامعة','مقارنة عوامل معلنة'),
    (119,'scholarships','svc_119','مخطط اختبار لغة','خطة يومية شاملة'),
    (120,'scholarships','svc_120','اختبارات IELTS/TOEFL أصلية','أسئلة غير مسربة'),
    (121,'scholarships','svc_121','مصحح كتابة لغة','rubric معلن'),
    (122,'scholarships','svc_122','مدرب GRE/GMAT/SAT','بنك أصلي وتحليل وقت'),
    (123,'scholarships','svc_123','محاكي اختبار كامل','تقرير نقاط ضعف'),
    (124,'tutoring','svc_124','مطابقة مع مدرس موثوق','حسب مادة ووقت وميزانية'),
    (125,'tutoring','svc_125','مجموعات صغيرة 2-4','تكلفة أقل من الفردي'),
    (126,'tutoring','svc_126','برنامج مدرس ثابت','سجل أهداف ومراجعة أسبوعية'),
    (127,'tutoring','svc_127','تدريس قصير متكرر','15 دقيقة × 3 أسبوعيًا'),
    (128,'tutoring','svc_128','خطة تعويض فجوة أساسية','تشخيص ووحدات تأسيسية'),
    (129,'tutoring','svc_129','انتقال مدرسة إلى جامعة','مهارات وبحث عن دعم'),
    (130,'tutoring','svc_130','مراقب حضور جلسات','تذكير وتقرير التزام'),
    (131,'tutoring','svc_131','ربط دروس بمنهج المقرر','رفع خطة المقرر'),
    (132,'tutoring','svc_132','مدرس نظير Peer Tutor','مطابقة طالب متفوق'),
    (133,'tutoring','svc_133','ساعات مكتبية جماعية','قائمة انتظار وإجابة مدرس'),
    (134,'tutoring','svc_134','نادي مراجعة شفوية','أسئلة سريعة وسجل تقدم'),
    (135,'tutoring','svc_135','اختبار طريقة تعلم عملية','لا ادعاء تشخيص علمي'),
    (136,'tutoring','svc_136','تحدي الاسترجاع المتباعد','مواعيد ذكية بناءً على الإجابات'),
    (137,'tutoring','svc_137','منبه خطر تأخر دراسي','مؤشرات يختارها الطالب'),
    (138,'tutoring','svc_138','خطة دراسة للطلاب العاملين','موازنة عمل/نوم/دراسة'),
    (139,'wellbeing','svc_139','مخطط إدارة ضغط الاختبارات','تقسيم عمل وراحة دون علاج'),
    (140,'wellbeing','svc_140','دليل إحالة لخدمات الدعم','توجيه للمرشد/العيادة/الطوارئ'),
    (141,'wellbeing','svc_141','رفيق عادات نوم ومذاكرة','تذكيرات عامة لا طبية'),
    (142,'wellbeing','svc_142','مساعد مكافحة التسويف','أول خطوة 5 دقائق'),
    (143,'wellbeing','svc_143','منظم المصروف الدراسي','ميزانية وتنبيهات'),
    (144,'wellbeing','svc_144','مقارن أدوات وكتب منخفضة التكلفة','بدائل قانونية'),
    (145,'wellbeing','svc_145','مساعد البحث عن سكن','تنبيه للتحقق من الاحتيال'),
    (146,'wellbeing','svc_146','دليل مواصلات الطالب','وقت وتكلفة وجدول'),
    (147,'wellbeing','svc_147','قارئ نصوص لصعوبات القراءة','تحويل مواد لصوت/تنسيق'),
    (148,'wellbeing','svc_148','تفريغ محاضرات بإذن','نص قابل للبحث'),
    (149,'wellbeing','svc_149','ترجمة فورية تعليمية','ترجمة مفهوم لا امتحان جارٍ'),
    (150,'wellbeing','svc_150','مساعدة لغة إشارة ووصف نصي','موارد ومراجعة مختص'),
    (151,'wellbeing','svc_151','منظم رعاية الطالب الدولي','مواعيد تأمين/إقامة'),
    (152,'wellbeing','svc_152','دليل خدمات الطالب الدولي','مكتبات ونقل وعيادات'),
    (153,'wellbeing','svc_153','مجموعة دعم زملاء مضبوطة','مراقبة إساءة وإحالة خطرة')
) AS v(num, category_code, code, title_ar, summary_ar)
JOIN service_categories c ON c.code = v.category_code;

-- Integrity policy notes
UPDATE service_definitions SET integrity_policy_notes =
    'يُمنع حل الاختبار الجاري أو إنجاز واجب نيابة عن الطالب؛ يُسمح بالشرح والتلميح فقط'
WHERE code IN ('svc_002','svc_018','svc_040','svc_022');
UPDATE service_definitions SET integrity_policy_notes =
    'يُمنع كتابة البحث باسم الطالب أو اختلاق مراجع؛ التدقيق يُظهر التعديلات ويحفظ أفكار الطالب'
WHERE code IN ('svc_028','svc_029','svc_030','svc_013');
UPDATE service_definitions SET integrity_policy_notes =
    'يُمنع انتحال شخصية الطالب أو كتابة إنجازات غير حقيقية'
WHERE code IN ('svc_032','svc_033','svc_095','svc_096','svc_112','svc_113','svc_114');
UPDATE service_definitions SET integrity_policy_notes =
    'تُمنع أسئلة الامتحانات المسربة والمواد المحمية بحقوق نشر؛ المحتوى أصلي أو مرخص موثق'
WHERE code IN ('svc_120','svc_122','svc_053','svc_036','svc_038');
UPDATE service_definitions SET integrity_policy_notes =
    'إحالة وتنظيم فقط دون تشخيص أو علاج نفسي؛ الحالات الخطرة تُحال للمختصين'
WHERE code IN ('svc_139','svc_140','svc_141','svc_153','svc_046');

-- Starter offers (3 draft, no prices)
INSERT INTO product_offers (code, offer_type, primary_service_id, title_ar, description_ar, status, sale_channel)
SELECT 'starter-guided-question', 'service', id, title_ar, summary_ar, 'draft', 'telegram'
FROM service_definitions WHERE code = 'svc_002';
INSERT INTO product_offers (code, offer_type, primary_service_id, title_ar, description_ar, status, sale_channel)
SELECT 'starter-personal-study-plan', 'service', id, title_ar, summary_ar, 'draft', 'telegram'
FROM service_definitions WHERE code = 'svc_009';
INSERT INTO product_offers (code, offer_type, primary_service_id, title_ar, description_ar, status, sale_channel, billing_interval_unit, billing_interval_count)
SELECT 'starter-question-bank-membership', 'subscription', id, title_ar, summary_ar, 'draft', 'telegram', 'month', 1
FROM service_definitions WHERE code = 'svc_036';

-- Platform settings
INSERT INTO platform_settings (key, value, description) VALUES
    ('upload_retention_days','30','المدة القصوى للاحتفاظ بملفات المستخدمين قبل الحذف المنطقي'),
    ('ai_outputs_retention_days','90','مدة الاحتفاظ بمخرجات مهام الذكاء الاصطناعي'),
    ('notification_max_attempts','5','أقصى محاولات إرسال الإشعار'),
    ('default_commission_rate','0.2000','نسبة عمولة المنصة الافتراضية'),
    ('free_sample_quiz_questions','5','عدد أسئلة العينة المجانية'),
    ('support_sla_hours','48','الساعات المستهدفة للاستجابة الأولى'),
    ('price_snapshot_policy','order_time','تثبيت لقطة السعر عند إنشاء الطلب لا قبله');

-- Schema meta
INSERT INTO schema_meta (key, value) VALUES
    ('schema_version','1.0.0-merged'),
    ('target_engine','PostgreSQL 16+'),
    ('reference_document','Project-Jobs.md (153 services)'),
    ('installed_at', to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"'));

-- Sanity checks
DO $$
DECLARE v_count INT;
BEGIN
    SELECT count(*) INTO v_count FROM service_definitions;
    IF v_count <> 153 THEN
        RAISE EXCEPTION 'Expected 153 seeded services, found %', v_count;
    END IF;
    IF (SELECT count(*) FROM product_offers WHERE code LIKE 'starter-%') <> 3 THEN
        RAISE EXCEPTION 'Expected 3 starter offers';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- ملاحظات تشغيلية أخيرة:
--   1) المهام الدورية المطلوبة من التطبيق: كنس الإشعارات المعلقة، تجديد
--      الاشتراكات، كنس الملفات المنتهية، إعادة محاولة التسليمات الفاشلة،
--      ومعالجة transactional_outbox.
--   2) إخفاء الهوية عبر fn_anonymize_user(user_id, actor_id) هو المسار
--      المعتمد «للحذف»؛ لا حذف فيزيائي للمستخدمين لديهم سجل مالي.
--   3) معالجة أحداث تيليجرام: استخدم webhook_inbox و payment_events (كلاهما
--      مفاتيح فريدة) في معاملات قصيرة.
--   4) توصيات الأدوار: bot_app_rw (SELECT/INSERT/UPDATE على جداول الأعمال)،
--      reporting_ro (SELECT فقط)، migrator (مالك المخطط). لا تمنح
--      UPDATE/DELETE على audit_events لأي دور تشغيلي.
--   5) RLS غير مفعلة في هذه الإصدارة؛ عند تعدد مستهلكي القاعدة مباشرة
--      فعّل سياسات RLS على الجداول ذات organization_id.
-- ============================================================================
