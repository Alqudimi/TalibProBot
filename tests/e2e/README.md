# Telegram E2E with tgtest

هذه الحزمة تستخدم `tgtest` لتشغيل البوت كما يستخدمه مستخدم Telegram حقيقي عبر Telethon/MTProto. يجب استخدام بوت اختبار منفصل وحساب مستخدم اختبار منفصل، وليس حساب الإنتاج.

يتطلب التشغيل الحي:

```bash
cp tests/e2e/.env.tgtest.example tests/e2e/.env.tgtest
# املأ TG_API_ID وTG_API_HASH وTG_PHONE وTG_DEFAULT_BOT
/home/ubuntu/tgtest-venv/bin/python -m tgtest run tests/e2e/scenarios/public_user.yaml --env tests/e2e/.env.tgtest
```

في أول تشغيل، يجب إنشاء جلسة Telethon بطريقة تفاعلية من حساب الاختبار، ثم ستُعاد استخدام الجلسة في التشغيلات التالية. يجب أن يكون البوت مفعّلًا على نفس قاعدة اختبار PostgreSQL وأن يكون قيد التشغيل:

```bash
cd /home/ubuntu/TalibProBot
BOT_TOKEN="$TEST_BOT_TOKEN" uv run python -m src.app.main
```

لتشغيل سيناريو الإدارة، يجب أن يكون رقم حساب Telegram التجريبي مضافًا إلى `ADMIN_TELEGRAM_IDS` في إعدادات البوت، ثم يُشغّل الملف `admin_user.yaml` منفصلًا.

الاختبارات الحية قد ترسل رسائل حقيقية وتغيّر بيانات قاعدة الاختبار. لا تستخدم أبدًا توكن الإنتاج أو حسابًا شخصيًا.
