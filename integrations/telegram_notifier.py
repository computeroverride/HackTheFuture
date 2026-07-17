from pathlib import Path
import urllib.parse
import urllib.request

from app.settings import Settings


class TelegramNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, text: str) -> None:
        if not self.settings.telegram_enabled:
            return

        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            print("Telegram is enabled but TELEGRAM_BOT_TOKEN/CHAT_ID is missing.")
            return

        data = urllib.parse.urlencode(
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
            }
        ).encode("utf-8")

        url = (
            "https://api.telegram.org/bot"
            f"{self.settings.telegram_bot_token}/sendMessage"
        )

        try:
            urllib.request.urlopen(url, data=data, timeout=5).read()
        except Exception as error:
            print(f"Telegram text send failed: {error}")

    def send_photo(self, image_path: Path, caption: str) -> None:
        if not self.settings.telegram_enabled:
            return

        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            print("Telegram is enabled but TELEGRAM_BOT_TOKEN/CHAT_ID is missing.")
            return

        url = (
            "https://api.telegram.org/bot"
            f"{self.settings.telegram_bot_token}/sendPhoto"
        )

        boundary = "----ChatGPTBoundary"

        with open(image_path, "rb") as file:
            image_bytes = file.read()

        body = b""

        def add_field(name: str, value: str) -> None:
            nonlocal body
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            body += f"{value}\r\n".encode()

        add_field("chat_id", self.settings.telegram_chat_id)
        add_field("caption", caption)

        body += f"--{boundary}\r\n".encode()
        body += (
            'Content-Disposition: form-data; name="photo"; '
            f'filename="{image_path.name}"\r\n'
        ).encode()
        body += b"Content-Type: image/jpeg\r\n\r\n"
        body += image_bytes
        body += b"\r\n"
        body += f"--{boundary}--\r\n".encode()

        request = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            urllib.request.urlopen(request, timeout=10).read()
        except Exception as error:
            print(f"Telegram photo send failed: {error}")

    def faulty_pill_detected(
        self,
        product_id: int,
        confidence: float,
        image_path: Path,
    ) -> None:
        caption = (
            f"⚠️ Faulty pill detected\n"
            f"ID: P{product_id:03d}\n"
            f"Confidence: {confidence:.2f}\n"
            f"Image: sharpest of 3 captured frames"
        )

        self.send_photo(image_path=image_path, caption=caption)

    def alarm(self, message: str) -> None:
        self.send(f"🚨 Conveyor alarm: {message}")