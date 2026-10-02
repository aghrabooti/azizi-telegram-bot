# ربات تلگرام آکادمی استاد مهدی عزیزی

ربات رسمی [mahdiazizi.com](https://www.mahdiazizi.com) — نمایش دوره‌ها، جزوه‌ها و کتاب‌ها
با همان فیلترهای سایت (پایه و رشته)، صفحات رسمی استاد، ارسال پیام ناشناس و پنل مدیریت کامل.

```
Python 3.10+   python-telegram-bot 22.8 (پین‌شده)   SQLite   بدون فریم‌ورک اضافه
```

---

## فهرست

1. [امکانات](#امکانات)
2. [معماری](#معماری)
3. [نصب سریع (لوکال / ویندوز)](#نصب-سریع)
4. [استقرار روی هاست cPanel — روش توصیه‌شده (polling)](#استقرار-روی-cpanel--polling)
5. [استقرار روی VPS با systemd](#استقرار-روی-vps-با-systemd)
6. [حالت وب‌هوک (فقط اگر مجبور شدید)](#حالت-وبهوک)
7. [کاتالوگ محصولات (اتصال به Supabase سایت)](#کاتالوگ-محصولات)
8. [پنل ادمین](#پنل-ادمین)
9. [سایت پیش‌نمایش زنده](#سایت-پیشنمایش-زنده)
10. [تست و کیفیت کد](#تست-و-کیفیت-کد)
11. [امنیت — قوانینی که نباید شکسته شوند](#امنیت)
12. [عیب‌یابی](#عیبیابی)

---

## امکانات

| بخش | توضیح |
|---|---|
| 📱 شماره‌ی اجباری | در اولین `/start` فقط دکمه‌ی بومی «ارسال شماره» وجود دارد؛ هیچ گزینه‌ی «بعداً» نیست. گیت سه‌لایه (متن نامعتبر / دکمه‌ی قدیمی / پیام غیرمتنی) |
| 🎓 دوره‌ها، 📝 جزوه‌ها، 📚 کتاب‌ها | دقیقاً مثل سایت: انتخاب نوع → پایه (نهم/دهم/یازدهم/دوازدهم) → رشته (ریاضی فیزیک/تجربی/انسانی) → لیست صفحه‌بندی‌شده با قیمت واقعی و لینک مستقیم خرید |
| 🌐 ورود به سایت | دکمه‌ی سبز مستقیم به `mahdiazizi.com` |
| 👤 صفحات استاد | همان چهار صفحه‌ی رسمی صفحه‌ی «درباره ما»: تلگرام، بله، آپارات، اینستاگرام |
| 🕵️ پیام ناشناس | کاملاً ناشناس (فقط کد `#A7F3`)؛ ادمین داخل پنل همه را می‌بیند و با دکمه یا Reply پاسخ می‌دهد |
| 🛠 پنل ادمین | آمار، کاربران + CSV با BOM، لاگ‌ها + دانلود، پشتیبان و بازیابی DB، ویرایش زنده‌ی محتوا، وضعیت کاتالوگ |
| 🎨 رنگ دکمه‌ها | همه‌ی دکمه‌ها `primary`، اقدام‌ها/لینک‌ها `success`، عملیات مخرب `danger` |
| 🧭 ناوبری | همه‌ی منوها inline و روی همان پیام (`editMessageText`)، هر صفحه والدش را می‌شناسد (state-less) |
| 📋 لاگ | کنسول + `data/bot.log` چرخشی + حذف خودکار توکن از لاگ |

---

## معماری

```
bot/
├── config/
│   ├── settings.py        # فقط متغیرهای محیطی (هیچ متنی اینجا نیست)
│   ├── content.py         # تمام متن‌ها، لینک‌ها و ساختار صفحات
│   └── catalog_seed.json  # snapshot پشتیبان کاتالوگ (از JSON-LD سایت)
├── constants.py           # تمام callback dataها + patternهای regex
├── keyboards/             # ساخت دکمه (استایل، محدودیت ۶۴ بایت)
├── handlers/              # start / phone_gate / navigation / anonymous / admin / router / errors
├── services/              # database, analytics, catalog, navigation, content_store, admin_view
├── utils/                 # phone, text, logging
├── webhook/app.py         # رانتایم WSGI (فقط برای Passenger)
├── app.py                 # ساخت Application (مشترک polling و webhook)
└── main.py                # اجرای polling  (python -m bot یا python bot/main.py)

scripts/     set_webhook.py · diagnose.py · probe_supabase.py · sync_catalog.py
             demo.py · make_zip.py · keepalive.sh · start_polling.sh · stop_polling.sh
dev/preview/ سایت پیش‌نمایش زنده (build.py + server.py + rebuild.sh)
deploy/      azizi-bot.service (systemd)
tests/       ۱۰۳ تست بدون شبکه
```

**قاعده‌ی طلایی:** صفحه‌ها «داده» هستند، نه کد. `bot/services/navigation.py` یک
`Page(text, rows, parent)` برمی‌گرداند که هم هندلرهای تلگرام و هم سایت پیش‌نمایش از آن
استفاده می‌کنند — به همین دلیل پیش‌نمایش هیچ‌وقت با ربات واقعی تفاوت پیدا نمی‌کند.

---

## نصب سریع

```bash
git clone <repo> azizi-telegram-bot && cd azizi-telegram-bot
python -m venv .venv
.venv/bin/pip install -r requirements.txt       # ویندوز: .venv\Scripts\pip install -r requirements.txt
cp .env.example .env                            # و مقادیر را پر کنید
python -m bot                                   # یا: python bot/main.py
```

> روی ویندوز `python bot/main.py` هم کار می‌کند (bootstrap مسیر داخل فایل انجام شده است).

حداقل مقادیر `.env`:

```
BOT_TOKEN=123456:AA...
ADMIN_IDS=123456789
```

آیدی عددی خودتان را با فرستادن `/id` به ربات بگیرید.

---

## استقرار روی cPanel — polling

> تجربه‌ی واقعی: **وب‌هوک روی Passenger شکست می‌خورد** (بوت پروسه کند است، تلگرام
> `Read timeout expired` می‌دهد و هیچ آپدیتی نمی‌رسد؛ POST دستی هم ۲۰۰ می‌دهد ولی کُند).
> روی هاست اشتراکی مستقیم سراغ polling بروید.

### ۱) آپلود و نصب

```bash
# SSH به هاست
cd ~
# فایل‌ها را در ~/azizi-telegram-bot بگذارید (بدون .env و بدون data/)
cd azizi-telegram-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env         # فقط خطوط KEY=value
```

اگر cPanel شما «Setup Python App» دارد، می‌توانید از همان virtualenv استفاده کنید؛
مسیرش معمولاً `/home/USER/virtualenv/azizi-telegram-bot/3.11/bin/python` است.

### ۲) تست اتصال (حتماً قبل از اجرا)

```bash
.venv/bin/python scripts/diagnose.py
```

اگر در بخش «دسترسی شبکه» ❌ گرفتید یعنی هاست به `api.telegram.org` نمی‌رسد
(روی هاست‌های داخل ایران طبیعی است). دو راه دارید:

* یک VPS خارج بگیرید (بهترین حالت)، یا
* یک رله/میرور HTTPS از Bot API داشته باشید و در `.env` بگذارید:
  `TELEGRAM_API_ROOT=https://your-relay.example.com`

### ۳) اجرای دائمی

```bash
bash scripts/start_polling.sh      # معادل: nohup python -m bot >> data/polling.log 2>&1 &
tail -f data/polling.log
```

### ۴) keepalive با کران

در cPanel → Cron Jobs → هر ۵ دقیقه، **دقیقاً همین خط** (نه چیز بیشتری):

```
*/5 * * * * bash /home/USER/azizi-telegram-bot/scripts/keepalive.sh
```

> ⚠️ الگوی `pgrep` عمداً **داخل فایل اسکریپت** است. اگر الگو را داخل خط کران بنویسید،
> خودِ پروسه‌ی کران با الگو match می‌شود (false positive اثبات‌شده) و ربات هرگز
> ری‌استارت نمی‌شود.

لاگ keepalive: `data/keepalive.log`

### ۵) توقف

```bash
bash scripts/stop_polling.sh
```

---

## استقرار روی VPS با systemd

```bash
sudo useradd -r -s /bin/false azizi
sudo mkdir -p /opt/azizi-telegram-bot && sudo chown -R azizi /opt/azizi-telegram-bot
# کد را آنجا بگذارید، venv بسازید، .env را پر کنید
sudo cp deploy/azizi-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now azizi-bot
journalctl -u azizi-bot -f
```

سرویس با `Restart=always` و `StartLimitIntervalSec=0` تنظیم شده است تا هرگز
«خسته» نشود و برای همیشه تلاش کند.

---

## حالت وب‌هوک

فقط اگر واقعاً لازم شد. چک‌لیست پیاده‌سازی‌شده در `bot/webhook/app.py`:

| # | مورد | وضعیت |
|---|---|---|
| ۱ | `passenger_wsgi.py` با `load_dotenv()` و اولویت متغیرهای cPanel | ✅ |
| ۲ | `secret_token` در setWebhook + بررسی هدر در هر درخواست (مقایسه‌ی constant-time) | ✅ |
| ۳ | `allowed_updates` شامل `callback_query` | ✅ (`bot/app.py`) |
| ۴ | رانتایم خوداستارت، مقاوم به fork با `_owner_pid` | ✅ |
| ۵ | `Update.de_json(payload, app.bot)` — هرگز `None` | ✅ |
| ۶ | `Application.start()` بعد از `initialize()` | ✅ |
| ۷ | `/healthz` سه‌حالته با نسخه + گرفتن `SystemExit` | ✅ |
| ۸ | تایم‌اوت ۶۰ ثانیه‌ای برای `initialize` | ✅ (`BOOT_TIMEOUT`) |
| ۹ | صبر تا ۲۰ ثانیه برای بوت قبل از ۵۰۳ | ✅ |
| ۱۰ | `TELEGRAM_API_ROOT` برای رله/میرور | ✅ |

تنظیم:

```bash
# در .env
WEBHOOK_SECRET=<یک رشته‌ی تصادفی بلند>
WEBHOOK_PATH=/telegram/webhook

python scripts/set_webhook.py --url https://your-domain.com/telegram/webhook
curl -s https://your-domain.com/healthz
```

برگشت به polling:

```bash
python scripts/set_webhook.py --delete
```

---

## کاتالوگ محصولات

کاتالوگ از همان منبعی خوانده می‌شود که سایت می‌خواند: **Supabase REST** با کلید عمومی
`anon` (همان کلیدی که داخل جاوااسکریپت سایت هست).

```
SUPABASE_URL=https://qbsfotperzzhuimnpmto.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_TABLE_COURSES=courses
SUPABASE_TABLE_BOOKS=books
SUPABASE_TABLE_NOTES=notes
```

کلید را از DevTools سایت بردارید: `Network` → هر درخواست به `supabase.co` → هدر `apikey`.

نام و ساختار جدول‌ها را حدس نزنید؛ اندازه بگیرید:

```bash
python scripts/probe_supabase.py                 # لیست جدول‌ها و ستون‌ها
python scripts/probe_supabase.py --table courses # نمونه‌ی ردیف + نگاشت ربات
```

**ترتیب منابع (fallback زنجیره‌ای):**

1. Supabase (زنده، کش ۱۰ دقیقه‌ای — `CATALOG_TTL`)
2. `data/catalog_cache.json` — آخرین دریافت موفق
3. `bot/config/catalog_seed.json` — snapshot گرفته‌شده از JSON-LD عمومی سایت

وضعیت فعلی همیشه در پنل ادمین → «🗂 وضعیت کاتالوگ» دیده می‌شود (منبع، تعداد، آخرین خطا).

به‌روزرسانی دستی snapshot:

```bash
python scripts/sync_catalog.py                # از Supabase
python scripts/sync_catalog.py --from-site    # از JSON-LD سایت (بدون کلید)
python scripts/sync_catalog.py --write-seed   # به‌روزرسانی فایل همراه ربات
```

> نکته: JSON-LD سایت «نوع» محصول (دوره/کتاب/جزوه) را منتشر نمی‌کند، بنابراین در حالت
> `--from-site` نوع از روی عنوان حدس زده می‌شود. برای داده‌ی دقیق، کلید anon را تنظیم کنید.

---

## پنل ادمین

`/admin` — فقط برای آیدی‌های داخل `ADMIN_IDS`.

* **📊 آمار** — کل/امروز، کاربران فعال، پربازدیدترین صفحات (کل و امروز)، پاک‌کردن آمار (دکمه‌ی قرمز)
* **👥 کاربران و شماره‌ها** — لیست صفحه‌بندی‌شده + خروجی CSV با BOM (اکسل فارسی درست باز می‌کند)
* **📨 پیام‌های ناشناس** — همه‌ی پیام‌ها، خوانده/نخوانده، مشاهده، پاسخ (یا Reply روی اعلان)
* **📋 لاگ‌ها** — ۲۵ خط آخر + دانلود فایل کامل
* **💾 پشتیبان دیتابیس** — online backup رسمی SQLite + بازیابی با آپلود فایل `.db`
* **✏️ ویرایش محتوا** — تغییر متن صفحات از داخل تلگرام، ذخیره در SQLite (بعد از ری‌استارت می‌ماند)
* **🗂 وضعیت کاتالوگ** — منبع داده، تعداد، آخرین خطا، دریافت دوباره

---

## سایت پیش‌نمایش زنده

```bash
bash dev/preview/rebuild.sh        # build + zip + اجرای سرور روی :8080
# یا دستی:
python dev/preview/build.py
python dev/preview/server.py
```

سایت روی `http://0.0.0.0:8080` بالا می‌آید و شامل این بخش‌هاست:

* **💬 شبیه‌ساز ربات** — همه‌ی صفحه‌ها از روی سورس واقعی ساخته می‌شوند (`build.py` ماژول‌های
  ربات را import می‌کند). اگر حتی یک دکمه به صفحه‌ای اشاره کند که وجود ندارد، **build شکست می‌خورد**.
* **🛠 پنل ادمین** با داده‌ی نمونه
* **📂 مرور سورس** — تک‌تک فایل‌های پروژه
* **✅ راستی‌آزمایی** — سرور به خودش HTTP می‌زند و نتیجه را نشان می‌دهد
* **⬇️ دانلود** — زیپ نسخه‌دار ضد کش با `BUILD_INFO.txt` و حجم دقیق بایت (بدون `.env` و `data/`)

---

## تست و کیفیت کد

```bash
.venv/bin/python -m pytest -q      # ۱۰۳ تست، بدون شبکه و بدون توکن
.venv/bin/ruff check .             # F,E,W,I — line-length 100
python scripts/demo.py --admin     # دیدن همه‌ی صفحه‌ها در ترمینال
```

پوشش تست‌ها: شروع، همه‌ی بخش‌ها، Back/Main، دکمه‌ی منقضی، متن نامعتبر در انتظار شماره،
فرار از گیت با دکمه‌ی قدیمی، شماره‌ی بین‌المللی، پنل ادمین، پیام ناشناس و پاسخ،
امنیت وب‌هوک (راز غلط/ناقص/مسیر اشتباه)، مهاجرت دیتابیس قدیمی، نشتی زیپ.

---

## امنیت

* `.env` فقط `KEY=value`. هیچ دستور شل، هیچ خروجی ترمینال. (یک خط paste‌شده = parse error = ربات مرده)
  — `scripts/diagnose.py` این فایل را چک می‌کند و خط خراب را نشان می‌دهد.
* **توکن را هیچ‌جا paste نکنید** — نه در چت، نه در issue، نه در اسکرین‌شات.
  اگر لو رفت تنها راه‌حل `/revoke` در [@BotFather](https://t.me/BotFather) است؛
  تلگرام هرگز نمی‌گوید چه کسی توکن را در دست دارد.
* لاگ‌ها خودکار توکن را پاک می‌کنند؛ برای اشتراک‌گذاری فایل‌های قدیمی:
  ```bash
  sed 's/bot[0-9]*:[A-Za-z0-9_-]*/bot***:***REDACTED***/g' data/bot.log > safe.log
  ```
* `.env` و `data/` در `.gitignore` هستند و هرگز داخل زیپ دانلودی نمی‌روند (تست دارد).
* وب‌هوک بدون `secret_token` هشدار می‌دهد و با راز اشتباه ۴۰۳ برمی‌گرداند.
* هویت فرستنده‌ی پیام ناشناس در هیچ جای ربات نمایش داده نمی‌شود (تست دارد).

---

## عیب‌یابی

### قدم اول همیشه

```bash
python scripts/diagnose.py
```

این دستور به‌ترتیب بررسی می‌کند: سلامت `.env` → DNS/TLS به API → `getMe` →
`getWebhookInfo` → دیتابیس → کاتالوگ → ۱۵ خط آخر لاگ. خروجی‌اش بدون توکن است و
می‌توانید مستقیم برای من بفرستید.

### جدول مشکلات رایج

| نشانه | علت محتمل | راه‌حل |
|---|---|---|
| ربات اصلاً جواب نمی‌دهد | هاست به `api.telegram.org` نمی‌رسد | `python scripts/diagnose.py` → بخش شبکه. VPS خارج یا `TELEGRAM_API_ROOT` |
| `InvalidToken` / 401 | توکن اشتباه یا revoke شده | توکن جدید از @BotFather، `.env` را اصلاح کنید |
| ربات بالا می‌آید ولی دکمه‌ها کار نمی‌کنند | در وب‌هوک: `allowed_updates` بدون `callback_query` | `python scripts/set_webhook.py --url ...` (خودش درست ست می‌کند) |
| تلگرام می‌گوید `Read timeout expired` | بوت کند Passenger | روی هاست اشتراکی سراغ polling بروید |
| `/healthz` همیشه `starting` | پروسه‌ی worker در حال مرگ است | لاگ `data/bot.log` را ببینید؛ `SystemExit` هم گرفته و لاگ می‌شود |
| دکمه‌ها خاکستری و پریده‌اند | کتابخانه‌ی قدیمی بدون پارامتر `style` | `pip install -U "python-telegram-bot==22.8"` |
| خطای 400 هنگام ارسال منو | مقدار استایل غیرمجاز | فقط `primary` / `success` / `danger` مجاز است (کد خودش اصلاح می‌کند و لاگ می‌دهد) |
| کران اجرا می‌شود ولی ربات ری‌استارت نمی‌شود | الگوی pgrep داخل خط کران نوشته شده | فقط `bash /path/scripts/keepalive.sh` در کران |
| لیست دوره‌ها خالی است | کلید Supabase تنظیم نشده یا نام جدول فرق دارد | پنل ادمین → وضعیت کاتالوگ، سپس `scripts/probe_supabase.py` |
| `.env` خوانده نمی‌شود | خط غیر KEY=value داخل آن | `python scripts/diagnose.py` خط خراب را می‌گوید |
| کاربر قدیمی شماره ندارد | نسخه‌ی قدیمی اجازه‌ی skip می‌داد | مهاجرت خودکار انجام می‌شود و دوباره شماره پرسیده می‌شود |

### ترتیب دستی (اگر خواستید خودتان چک کنید)

```bash
curl -I https://api.telegram.org                                   # ۱) دسترسی
curl -s "https://api.telegram.org/bot<TOKEN>/getMe"                # ۲) توکن
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"       # ۳) وب‌هوک
curl -s -X POST https://your-domain/telegram/webhook \
     -H "X-Telegram-Bot-Api-Secret-Token: <SECRET>" \
     -H "Content-Type: application/json" -d '{"update_id":1}'      # ۴) POST دستی
tail -n 100 data/bot.log                                           # ۵) لاگ
```

> اگر چیزی را نمی‌دانید، حدس نزنید: `scripts/diagnose.py` و `/healthz` را اجرا کنید و
> خروجی را بفرستید.
