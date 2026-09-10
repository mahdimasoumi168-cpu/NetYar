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

# Use the same production entrypoint as Railway so local and production
# execute the same Telegram/Rubika webhook architecture.
python entrypoint.py
