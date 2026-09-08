#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "فایل .env ساخته شد. توکن‌ها را داخل آن بگذار و دوباره اجرا کن."
  exit 1
fi

python test_connection.py
python bot.py
