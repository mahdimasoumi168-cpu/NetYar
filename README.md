# NetYar — ربات خدمات مهاجر

ربات NetYar برای Telegram و Rubika با یک FastAPI server و webhook اجرا می‌شود.

## معماری اجرا

Railway و اجرای محلی هر دو از `entrypoint.py` استفاده می‌کنند. این فایل لایه‌های سازگاری را قبل از اجرای `server.py` نصب می‌کند تا Telegram و Rubika از یک runtime مشترک استفاده کنند.

## اجرا روی Railway

1. Repository را به Railway متصل کنید.
2. در Variables این موارد را تنظیم کنید:

```text
RUBIKA_BOT_TOKEN=توکن_روبیکا
TELEGRAM_BOT_TOKEN=توکن_تلگرام
TELEGRAM_API_BASE=https://api.telegram.org
```

در صورت استفاده از دامنه عمومی Railway، مقدار `PUBLIC_BASE_URL` را نیز تنظیم کنید.

3. Deploy را اجرا کنید.
4. وضعیت سرویس را از `/health` بررسی کنید.
5. سپس در Telegram یا Rubika به ربات `/start` بفرستید.

## اجرای محلی

```bash
bash start.sh
```

`start.sh` همان `entrypoint.py` را اجرا می‌کند که Railway اجرا می‌کند؛ بنابراین رفتار محیط محلی و production یکسان است.

## نکته امنیتی

توکن‌ها، رمزها، اطلاعات کارت و سایر Secrets را داخل GitHub قرار ندهید و فقط از Environment Variables استفاده کنید.
