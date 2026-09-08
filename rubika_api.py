import requests


class RubikaAPI:
    """کلاینت ساده برای Bot API رسمی روبیکا."""

    def __init__(self, token: str, timeout: int = 30):
        token = (token or "").strip()
        if not token:
            raise ValueError("توکن روبیکا خالی است.")
        self.base_url = f"https://botapi.rubika.ir/v3/{token}"
        self.timeout = timeout
        self.session = requests.Session()

    def call(self, method: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}/{method}"
        try:
            response = self.session.post(
                url,
                json=payload or {},
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.RequestException as error:
            raise ConnectionError(
                "به API روبیکا وصل نشد. اگر بیرون از ایران هستی ممکن است این آدرس بسته باشد."
            ) from error

        if response.status_code == 401:
            raise PermissionError("توکن روبیکا غلط یا باطل شده است.")
        if response.status_code >= 400:
            raise RuntimeError(f"خطای روبیکا {response.status_code}: {response.text[:300]}")

        data = response.json()
        if isinstance(data, dict) and data.get("status") in {"ERROR", "error"}:
            raise RuntimeError(data.get("status_det") or data.get("error") or data)
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    def get_me(self) -> dict:
        return self.call("getMe")

    def get_updates(self, offset_id: str | None = None, limit: int = 10) -> dict:
        payload = {"limit": limit}
        if offset_id:
            payload["offset_id"] = offset_id
        return self.call("getUpdates", payload)

    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> dict:
        payload = {"chat_id": chat_id, "text": text}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        return self.call("sendMessage", payload)
