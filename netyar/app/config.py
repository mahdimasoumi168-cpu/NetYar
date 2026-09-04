import os

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()}
DB_PATH = os.getenv('DB_PATH', 'netyar.sqlite3')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip().strip('/')
SIZPAY_USERNAME = os.getenv('SIZPAY_USERNAME', '').strip()
SIZPAY_PASSWORD = os.getenv('SIZPAY_PASSWORD', '').strip()
SIZPAY_MERCHANT_ID = os.getenv('SIZPAY_MERCHANT_ID', '').strip()
SIZPAY_TERMINAL_ID = os.getenv('SIZPAY_TERMINAL_ID', '').strip()
SIZPAY_IPG_ID = os.getenv('SIZPAY_IPG_ID', '').strip()
SIZPAY_MODE = os.getenv('SIZPAY_MODE', 'rest').strip().lower()  # rest | paylink
TEST_AMOUNT_TOMAN = 100_000
REQUEST_TIMEOUT = float(os.getenv('REQUEST_TIMEOUT', '20'))

if SIZPAY_MODE not in {'rest', 'paylink'}:
    SIZPAY_MODE = 'rest'
