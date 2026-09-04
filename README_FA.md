# NetYar — تست پرداخت سیزپی ۱۰۰٬۰۰۰ تومان

این نسخه یک پروژه مستقل و تمیز برای تست زنجیره زیر است:

`Telegram /start → دکمه پرداخت → سیزپی → Callback → Confirm`

> این بسته جایگزین امکانات قدیمی NetYar نیست؛ برای اینکه اول پرداخت را قطعی و جداگانه تست کنیم ساخته شده است.

## 1) آپلود به GitHub

محتویات همین پوشه را در ریشه Repository گیت‌هاب قرار بده؛ یعنی فایل `requirements.txt` و `Procfile` و پوشه `app` مستقیماً در ریشه Repository باشند.

## 2) اتصال به Railway

Railway → New Project → Deploy from GitHub Repo → Repository را انتخاب کن.

فایل `railway.toml` خودش Start Command را تنظیم می‌کند.

## 3) Variables

در Railway → Service → Variables این موارد را بساز:

- `BOT_TOKEN` = توکن ربات تلگرام
- `SIZPAY_USERNAME` = مقدار «کلید ۱ / نام کاربری» سیزپی
- `SIZPAY_PASSWORD` = مقدار «کلید ۲ / رمز» سیزپی
- `SIZPAY_MERCHANT_ID` = کد پذیرنده
- `SIZPAY_TERMINAL_ID` = کد ترمینال

`DB_PATH` را لازم نیست تغییر بدهی؛ مقدار پیش‌فرض `netyar.sqlite3` است.

### PUBLIC_BASE_URL چیست؟

فعلاً لازم نیست آن را دستی وارد کنی. Railway بعد از ساخت دامنه عمومی، متغیر `RAILWAY_PUBLIC_DOMAIN` را خودش در اختیار سرویس می‌گذارد و برنامه از آن استفاده می‌کند.

اگر خواستی دستی تنظیم کنی، مقدارش باید دقیقاً آدرس عمومی برنامه باشد، مثل:

`https://my-app-production-1234.up.railway.app`

بدون `/` در انتها.

## 4) ساخت آدرس HTTPS در Railway

بعد از Deploy:

`Service → Settings → Networking → Public Networking → Generate Domain`

Railway یک دامنه شبیه `xxxx.up.railway.app` می‌دهد و HTTPS/SSL را خودش فعال می‌کند.

آدرس Callback برنامه این خواهد بود:

`https://xxxx.up.railway.app/sizpay/callback`

## 5) تست سلامت

دامنه را در مرورگر باز کن:

`https://xxxx.up.railway.app/health`

باید JSON شبیه این ببینی:

`{"ok":true,"service":"NetYar SIZPay Test"}`

## 6) تست ربات

در تلگرام `/start` بزن. باید دکمه زیر را ببینی:

`💳 پرداخت تست — ۱۰۰٬۰۰۰ تومان`

با زدن دکمه، سیستم از سیزپی Token می‌گیرد و لینک پرداخت را می‌سازد.

بعد از پرداخت، سیزپی به Callback برمی‌گردد و سیستم `ConfirmSimple` را اجرا می‌کند.

## 7) نکته امنیتی

کلیدهای سیزپی را داخل GitHub نگذار. فقط در Railway Variables وارد کن.

## 8) اگر /start کار نکرد

اول Railway → Deployments → View Logs را باز کن. باید خطای دقیق را ببینیم. همچنین `/health` را تست کن.

## 9) مبلغ

۱۰۰٬۰۰۰ تومان = ۱٬۰۰۰٬۰۰۰ ریال و همین مقدار به API سیزپی ارسال می‌شود.
