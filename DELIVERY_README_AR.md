# حزمة تسليم TalibProBot

هذه الحزمة تحتوي نسخة المشروع الحالية مع كود البوت، مخطط PostgreSQL، اختبارات pytest، اختبارات Telegym، ملفات التشغيل، Dockerfile، وملف Docker Compose الإنتاجي.

## التشغيل المحلي

انسخ `.env.example` إلى `.env` وعدّل إعدادات PostgreSQL و`BOT_TOKEN`، ثم شغّل:

```bash
uv sync
uv run pytest -q
```

## تشغيل اختبارات Telegym

يتطلب المشغل نسخة Telegym المبنية خارجيًا. شغّل:

```bash
bash scripts/run_telegym_http.sh
```

أو مرّر متغيرات البيئة الخاصة بالاختبار كما هو موضح في `tests/e2e/README.md`.

## تشغيل Docker الإنتاجي

أنشئ ملف `.env.production` خارج Git، وضع فيه الأسرار الحقيقية، ثم شغّل:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

لا تستخدم قيم `.env.example` في الإنتاج، ولا تضع token أو كلمات مرور حقيقية داخل المستودع.

## التحقق الذي تم قبل التسليم

- 253 اختبار pytest ناجح.
- فحص compilation ناجح.
- فحص `git diff --check` ناجح.
- حزمة Telegym HTTP E2E الموسعة نجحت في البيئة المحلية السابقة.
- PostgreSQL استُخدم في المسارات الحساسة للدفع والطلبات والصلاحيات.
