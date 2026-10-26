# تقرير الاختبارات والإصلاحات — TalibProBot

**المستودع:** `Alqudimi/TalibProBot`  
**المسار المحلي:** `/home/ubuntu/TalibProBot`  
**التاريخ:** 2026-10-26

## ما تم تنفيذه

تم تثبيت PostgreSQL وتهيئة قاعدة `academic`، ثم تشغيل اختبارات black-box عبر `teremok` باستخدام Dispatcher وRouters وMiddlewares الحقيقيين، مع PostgreSQL فعلي. كما تم تشغيل Telegym mock عبر bridge webhook حقيقي يمرر Updates إلى التطبيق.

التغطية تشمل الأوامر العامة، التسجيل وFSM، لوحات Inline وReplyKeyboard، السؤال اليومي بإجابتيه، التنقل، الدعم والخصوصية والمجموعات والفرص، مدخلات callback غير الصالحة، وأخطاء المراجع غير الموجودة.

## الإصلاحات التطبيقية

### فصل الأعمال الخلفية عبر Celery وRedis

أضيف Celery 5.6 مع Redis broker على database رقم 0 وresult backend على database رقم 1. تم فصل تحديث heartbeat الخاص بالمستخدم عن مسار معالجة Telegram؛ عند تفعيل `REDIS_ENABLED=true` و`TASK_WORKER_ENABLED=true` ينشر التطبيق المهمة إلى Redis ويعود إلى معالجة الرد، بينما ينفذ worker عملية PostgreSQL في عملية مستقلة. الأعمال التي تحتاج نتيجة فورية أو اتساقًا ذريًا بقيت في المسار المتزامن عمدًا، لأن تحويلها كلها إلى fire-and-forget يسبب ردودًا غير صحيحة أو فقدانًا للمعاملات.

تشغيل worker:

```bash
cd /home/ubuntu/TalibProBot
REDIS_ENABLED=true ./scripts/run_celery_worker.sh
```

اختبار التكامل الفعلي نجح: تم enqueue لمهمة heartbeat عبر Redis، استلمها worker مستقل بتوازي 2، وأعاد task result بنجاح مع تحديث PostgreSQL.

- إصلاح `MissingGreenlet` في مسار الملف الشخصي عبر eager loading وربط profile للمستخدم الجديد قبل تسليمه للـhandler.
- تخفيف تحديث `last_seen_at` إلى heartbeat كل 60 ثانية بدل كتابة كل رسالة.
- تحرير اتصال PostgreSQL بعد تسجيل/استرجاع المستخدم وقبل عمليات Bot API، حتى لا يبقى الاتصال محجوزًا أثناء الشبكة.
- جعل حجم PostgreSQL pool قابلًا للضبط، مع افتراضات مناسبة للحمل المحلي: `DB_POOL_SIZE=30` و`DB_MAX_OVERFLOW=40` و`pool_pre_ping`.
- رفع توازي Bot API القابل للضبط إلى `BOT_API_POOL_LIMIT=500` بدل حد aiogram الافتراضي 100.
- منع تسرب ذاكرة throttling عبر `OrderedDict` وحد أقصى 100,000 إدخال واستخدام `monotonic`.
- منع حفظ فرصة غير موجودة أو UUID غير صالح، وإرجاع تنبيه للمستخدم بدل `ForeignKeyViolation`.
- رفع backlog في Telegym bridge إلى 8192، وتجميع الردود في اختبار الحمل عبر endpoint واحد بدل 5,000 عملية polling مستقلة.

## نتائج الاختبارات الوظيفية

تشغيل اختبارات teremok:

```bash
BOT_TOKEN='123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890' uv run pytest -q tests/test_teremok_blackbox.py -rx
```

النتيجة النهائية:

```text
55 passed
```

وتشغيل مجموعة المشروع الأصلية منفصلة عن teremok:

```bash
BOT_TOKEN='123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890' uv run pytest -q --ignore=tests/test_teremok_blackbox.py
```

النتيجة:

```text
197 passed
```

يجب تشغيل المجموعتين منفصلتين؛ إذ إن fixtures المشروع تستخدم حلقات asyncio مختلفة عن fixture teremok، ودمجهما في عملية pytest واحدة يسبب أخطاء cross-loop في asyncpg أثناء teardown، وليس فشلًا في منطق التطبيق. تشغيل كل مجموعة بالطريقة أعلاه ناجح.

## نتائج Telegym والحمل

تشغيل المسار الخفيف `/help` مع 5,000 مستخدم متزامن:

```bash
TELEGYM_USERS=5000 TELEGYM_LOAD_COMMANDS=/help ./scripts/run_telegym_5000.sh
```

النتيجة:

```text
injected=5000/5000 (100.00%)
replied=5000/5000 (100.00%)
aggregate_reply_window_ms=21837.3
inject_ms p50=3867.8 max=4348.2
```

هذا يثبت تحمل مسار القراءة الخفيف من ناحية الصحة، لكنه ليس تفاعلًا لحظيًا؛ زمن النافذة الإجمالية في بيئة الاختبار حوالي 21.8 ثانية بسبب Telegym mock و5000 اتصال وموارد الجهاز المحلي.

أما الحمل المختلط لعشرة أوامر، فكانت النتيجة الأخيرة:

```text
injected=5000/5000 (100.00%)
replied=5000/5000 (100.00%)
aggregate_reply_window_ms=23784.1
inject_ms p50=4061.7 max=4971.3
```

تحققت النتيجة بعد إضافة fast-path للأوامر المعلوماتية التي لا تحتاج حسابًا، مثل `/help` و`/terms` و`/edu` و`/daily` و`/privacy` و`/support`، مع إبقاء الطلبات التي تحتاج هوية أو معاملات حساسة على المسار الآمن. هذا رفع الردود من 56.18% إلى 100% في نفس سيناريو الحمل.

تمت إضافة `uvloop` اختياريًا لمسار تشغيل البوت في الإنتاج، مع fallback إلى asyncio. أثناء اختبار Telegym اتضح أن uvloop في bridge الاختباري تحديدًا سبب تراجعًا إلى 32.18% بسبب مهلة HTTP عند انفجار 5,000 اتصال، لذلك بقي bridge على asyncio المرجعي المستقر بينما يظل uvloop متاحًا للتشغيل الإنتاجي. بعد العزل عادت النتيجة إلى 100%.

نسبة النجاح وصلت إلى 100% في هذه البيئة، لكن كلمة "لحظي" لا تعني صفر millisecond؛ نافذة الرد الإجمالية بقيت حوالي 23.8 ثانية لانفجار 5,000 اتصال عبر Telegym mock على جهاز الاختبار. للوصول إلى زمن أقل في الإنتاج يلزم تشغيل bridge/bot بعدة workers وخوادم Redis/PostgreSQL مناسبة وتوزيع الحمل أفقيًا.

## تشغيل الأدوات

```bash
cd /home/ubuntu/TalibProBot
./scripts/run_teremok.sh
./scripts/run_telegym_http.sh
./scripts/run_telegym_5000.sh
```

توجد أيضًا سيناريوهات tgtest الحية في `tests/e2e/scenarios/`، لكنها تحتاج حساب Telegram اختباريًا منفصلًا وبيانات `TG_API_ID` و`TG_API_HASH` و`TG_PHONE` وملف جلسة Telethon. لم تُستخدم بيانات إنتاج.

## حالة PostgreSQL

- قاعدة البيانات: `academic`
- المخطط: `student_platform`
- PostgreSQL يعمل محليًا.
- بعد الحمل الأخير: 9,958 مستخدمًا و9,958 هوية، واتصال خامل واحد فقط وقت الفحص.

## الخلاصة

تم إصلاح العيوب الوظيفية التي كشفتها اختبارات profile وcallback الفرص، وأصبحت حزمة teremok الوظيفية 55/55 ناجحة، ومجموعة المشروع الأصلية 197/197 ناجحة عند تشغيلها في عزلها الصحيح. كما أصبح مسار `/help` يرد على 5,000 مستخدم بنسبة 100%، بينما لا يزال الحمل المختلط الثقيل أقل من المطلوب ويحتاج بنية توسع إضافية؛ وهذه النتيجة موثقة كفشل SLO وليست نجاحًا زائفًا.
