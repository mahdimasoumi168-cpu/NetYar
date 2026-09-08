import requests


class TelegramAPI:
    """کلاینت ساده برای Bot API تلگرام."""

    def __init__(self, token: str, api_base: str = "https://api.telegram.org", timeout: int = 35):
        token = (token or "").strip()
        if not token:
            raise ValueError("توکن تلگرام خالی است.")
        self.base_url = f"{api_base.rstrip('/')}/bot{token}"
        self.timeout = timeout
        self.session = requests.Session()

    def call(self, method: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}/{method}"
        try:
            response = self.session.post(url, json=payload or {}, timeout=self.timeout)
        except requests.exceptions.RequestException as error:
            raise ConnectionError(
                "به API تلگرام وصل نشد. از ایران معمولاً باید پروکسی یا TELEGRAM_API_BASE بگذاری."
            ) from error

        if response.status_code == 401:
            raise PermissionError("توکن تلگرام غلط یا باطل شده است.")
        if response.status_code >= 400:
            raise RuntimeError(f"خطای تلگرام {response.status_code}: {response.text[:300]}")

        data = response.json()
        if not data.get("ok", True):
            raise RuntimeError(data.get("description", "خطای تلگرام"))
        return data.get("result", data)

    def get_me(self) -> dict:
        return self.call("getMe")

    def get_updates(self, offset: int | None = None, timeout_long: int = 25) -> list:
        payload = {"timeout": timeout_long}
        if offset is not None:
            payload["offset"] = offset
        result = self.call("getUpdates", payload)
        return result if isinstance(result, list) else []

    def send_message(self, chat_id: int | str, text: str) -> dict:
        return self.call("sendMessage", {"chat_id": chat_id, "text": text})
