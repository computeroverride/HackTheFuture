from __future__ import annotations

import json
import mimetypes
import shutil
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.settings import Settings


# These should match the class names used by your trained model.
FEEDBACK_LABELS = (
    "good",
    "fail_different",
    "fail_defect",
)

LABEL_DISPLAY_NAMES = {
    "good": "Good",
    "fail_different": "Different pill",
    "fail_defect": "Defective pill",
}

# The ML may report "good", while this project's training folder is "pass".
DATASET_FOLDER_BY_LABEL = {
    "good": "pass",
    "fail_different": "fail_different",
    "fail_defect": "fail_defect",
}

# integrations/telegram_notifier.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TelegramNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.last_update_id: int | None = None

        # Telegram feedback records are kept under the existing storage tree.
        self.feedback_root = PROJECT_ROOT / "storage" / "feedback"
        self.feedback_log_path = self.feedback_root / "feedback.jsonl"
        self.pending_feedback_path = self.feedback_root / "pending.json"

        # Thumbs-up images enter the matching class folder and will be
        # included automatically the next time training.py is run.
        self.training_dataset_dir = PROJECT_ROOT / "storage" / "datasets"

        # Thumbs-down only means "wrong"; it does not identify the correct
        # class, so those images wait here for manual relabelling.
        self.incorrect_feedback_dir = (
            PROJECT_ROOT
            / "storage"
            / "failures"
            / "incorrect_predictions"
        )

        self.pending_feedback = self._load_pending_feedback()

        # Completed Telegram feedback events wait here until main.py
        # publishes them to EdgeHub.
        self.completed_feedback_events: list[
            dict[str, object]
        ] = []

        # Optional comma-separated Telegram user IDs.
        #
        # Example:
        # TELEGRAM_FEEDBACK_USER_IDS=123456789,987654321
        #
        # If empty, anyone who can see the channel can press the buttons.
        raw_user_ids = str(
            getattr(
                self.settings,
                "telegram_feedback_user_ids",
                "",
            )
            or ""
        )

        self.allowed_feedback_user_ids: set[int] = set()

        for value in raw_user_ids.split(","):
            value = value.strip()

            if not value:
                continue

            try:
                self.allowed_feedback_user_ids.add(int(value))
            except ValueError:
                print(
                    "Ignoring invalid TELEGRAM_FEEDBACK_USER_IDS "
                    f"value: {value}"
                )

    def _chat_id(self) -> str:
      
        if self.settings.telegram_feedback_chat_id:
            return self.settings.telegram_feedback_chat_id

        return self.settings.telegram_chat_id

    def _api_url(self, method: str) -> str:
        return (
            "https://api.telegram.org/bot"
            f"{self.settings.telegram_bot_token}/{method}"
        )

    @staticmethod
    def _encode_form_value(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, (dict, list)):
            return json.dumps(
                value,
                separators=(",", ":"),
            )

        return str(value)

    def _post_form(
        self,
        method: str,
        fields: dict[str, object],
        timeout: float = 5,
    ) -> dict[str, Any]:
        encoded_fields = {
            key: self._encode_form_value(value)
            for key, value in fields.items()
        }

        data = urllib.parse.urlencode(
            encoded_fields
        ).encode("utf-8")

        request = urllib.request.Request(
            url=self._api_url(method),
            data=data,
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )

        if not payload.get("ok"):
            raise RuntimeError(
                f"Telegram API {method} failed: {payload}"
            )

        return payload

    def send(self, text: str) -> None:
        if not self.settings.telegram_enabled:
            return

        if (
            not self.settings.telegram_bot_token
            or not self.settings.telegram_chat_id
        ):
            print(
                "Telegram is enabled but "
                "TELEGRAM_BOT_TOKEN/CHAT_ID is missing."
            )
            return

        try:
            self._post_form(
                method="sendMessage",
                fields={
                    "chat_id": self.settings.telegram_chat_id,
                    "text": text,
                },
            )
        except Exception as error:
            print(f"Telegram text send failed: {error}")

    def send_photo(
        self,
        image_path: Path,
        caption: str,
        reply_markup: dict[str, object] | None = None,
    ) -> dict[str, Any] | None:
       
        if not self.settings.telegram_enabled:
            return None

        if (
            not self.settings.telegram_bot_token
            or not self.settings.telegram_chat_id
        ):
            print(
                "Telegram is enabled but "
                "TELEGRAM_BOT_TOKEN/CHAT_ID is missing."
            )
            return None

        image_path = Path(image_path)

        if not image_path.exists():
            print(f"Telegram image does not exist: {image_path}")
            return None

        boundary = f"----Boundary{uuid.uuid4().hex}"

        body = bytearray()

        def add_field(name: str, value: str) -> None:
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                (
                    f'Content-Disposition: form-data; '
                    f'name="{name}"\r\n\r\n'
                ).encode("utf-8")
            )
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")

        add_field(
            "chat_id",
            str(self.settings.telegram_chat_id),
        )
        add_field("caption", caption)

        if reply_markup is not None:
            add_field(
                "reply_markup",
                json.dumps(
                    reply_markup,
                    separators=(",", ":"),
                ),
            )

        mime_type, _ = mimetypes.guess_type(
            image_path.name
        )
        mime_type = mime_type or "application/octet-stream"

        try:
            image_bytes = image_path.read_bytes()
        except OSError as error:
            print(f"Unable to read Telegram image: {error}")
            return None

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                'Content-Disposition: form-data; '
                'name="photo"; '
                f'filename="{image_path.name}"\r\n'
            ).encode("utf-8")
        )
        body.extend(
            f"Content-Type: {mime_type}\r\n\r\n".encode(
                "utf-8"
            )
        )
        body.extend(image_bytes)
        body.extend(b"\r\n")
        body.extend(
            f"--{boundary}--\r\n".encode("utf-8")
        )

        request = urllib.request.Request(
            url=self._api_url("sendPhoto"),
            data=bytes(body),
            headers={
                "Content-Type": (
                    f"multipart/form-data; boundary={boundary}"
                ),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=10,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )

            if not payload.get("ok"):
                raise RuntimeError(
                    f"Telegram sendPhoto failed: {payload}"
                )

            result = payload.get("result")

            if isinstance(result, dict):
                return result

            return None

        except Exception as error:
            print(f"Telegram photo send failed: {error}")
            return None

    @staticmethod
    def _format_confidence(confidence: float) -> str:
       
        if 0 <= confidence <= 1:
            return f"{confidence:.1%}"

        return f"{confidence:.1f}%"

    @staticmethod
    def _feedback_keyboard(
        product_id: int,
    ) -> dict[str, object]:
    
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅",
                        "callback_data": (
                            f"actual:{product_id}:good"
                        ),
                    },
                    {
                        "text": "🟨",
                        "callback_data": (
                            f"actual:{product_id}:fail_defect"
                        ),
                    },
                    {
                        "text": "🟥",
                        "callback_data": (
                            f"actual:{product_id}:fail_different"
                        ),
                    },
                ]
            ]
        }

    @staticmethod
    def _correction_keyboard(
        product_id: int,
        predicted_label: str,
    ) -> dict[str, object]:
        rows: list[list[dict[str, str]]] = []

        for label in FEEDBACK_LABELS:
            # The prediction was already marked as wrong, so do not
            # display the same class as a correction.
            if label == predicted_label:
                continue

            rows.append(
                [
                    {
                        "text": (
                            "Actual: "
                            f"{LABEL_DISPLAY_NAMES.get(label, label)}"
                        ),
                        "callback_data": (
                            f"actual:{product_id}:{label}"
                        ),
                    }
                ]
            )

        return {"inline_keyboard": rows}

    def send_inspection_result(
        self,
        product_id: int,
        predicted_label: str,
        confidence: float,
        image_path: Path,
    ) -> None:
        
        predicted_label = predicted_label.strip().lower()

        # The three buttons record the ACTUAL class. Therefore an unusual
        # prediction such as fail_uncertain must not suppress the buttons.
        result_name = LABEL_DISPLAY_NAMES.get(
            predicted_label,
            predicted_label.replace("_", " "),
        )

        icon = (
            "✅"
            if predicted_label == "good"
            else "⚠️"
        )

        caption = (
            f"{icon} Product inspection result\n"
            f"Product ID: P{product_id:03d}\n"
            f"ML prediction: {result_name}\n"
            f"Confidence: "
            f"{self._format_confidence(confidence)}\n"
            f"Image: sharpest of 3 captured frames\n\n"
            f"Select the actual class:\n"
            f"✅ Pass   🟨 Defect   🟥 Different"
        )

        try:
            image_path = self._rename_product_image(
                image_path=image_path,
                product_id=product_id,
            )
        except (OSError, FileNotFoundError) as error:
            print(f"Unable to rename inspection image: {error}")
            return

        message = self.send_photo(
            image_path=image_path,
            caption=caption,
            reply_markup=self._feedback_keyboard(
                product_id
            ),
        )

        if not message:
            return

        chat = message.get("chat") or {}
        chat_id = str(
            chat.get(
                "id",
                self.settings.telegram_chat_id,
            )
        )
        message_id = int(message.get("message_id", 0))

        if message_id <= 0:
            print(
                "Telegram photo sent but no message ID "
                "was returned."
            )
            return

        pending_key = self._message_key(
            chat_id,
            message_id,
        )

        self.pending_feedback[pending_key] = {
            "product_id": product_id,
            "predicted_label": predicted_label,
            "confidence": confidence,
            "image_path": str(image_path),
            "telegram_chat_id": chat_id,
            "telegram_message_id": message_id,
            "sent_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        self._save_pending_feedback()

    def faulty_pill_detected(
        self,
        product_id: int,
        confidence: float,
        image_path: Path,
        predicted_label: str = "fail_defect",
    ) -> None:
       
        self.send_inspection_result(
            product_id=product_id,
            predicted_label=predicted_label,
            confidence=confidence,
            image_path=image_path,
        )

    @staticmethod
    def _message_key(
        chat_id: str,
        message_id: int,
    ) -> str:
        return f"{chat_id}:{message_id}"

    def _load_pending_feedback(
        self,
    ) -> dict[str, dict[str, object]]:
        if not self.pending_feedback_path.exists():
            return {}

        try:
            payload = json.loads(
                self.pending_feedback_path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(payload, dict):
                return payload

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(
                "Unable to read pending Telegram "
                f"feedback: {error}"
            )

        return {}

    def _save_pending_feedback(self) -> None:
        self.pending_feedback_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.pending_feedback_path.with_suffix(
                ".tmp"
            )
        )

        temporary_path.write_text(
            json.dumps(
                self.pending_feedback,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(
            self.pending_feedback_path
        )

    def _rename_product_image(
        self,
        image_path: Path,
        product_id: int,
    ) -> Path:
       
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(
                f"Image does not exist: {image_path}"
            )

        timestamp = datetime.now().astimezone().strftime(
            "%Y%m%d_%H%M%S"
        )

        extension = image_path.suffix

        if not extension:
            extension = ".jpg"

        new_filename = (
            f"P{product_id:03d}_{timestamp}"
            f"{extension.lower()}"
        )

        new_path = image_path.parent / new_filename

        # Prevent accidental overwriting when two files are created
        # within the same second.
        counter = 1

        while new_path.exists() and new_path != image_path:
            new_filename = (
                f"P{product_id:03d}_{timestamp}_{counter}"
                f"{extension.lower()}"
            )
            new_path = image_path.parent / new_filename
            counter += 1

        if new_path != image_path:
            image_path.rename(new_path)

        return new_path

    def _append_feedback_log(
        self,
        record: dict[str, object],
    ) -> None:
        self.feedback_log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.feedback_log_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )
            file.write("\n")

    def _copy_confirmed_image(
        self,
        pending: dict[str, object],
        actual_label: str,
    ) -> str | None:
        source_path = Path(
            str(pending.get("image_path", ""))
        )

        if not source_path.exists():
            print(
                "Feedback recorded, but source image "
                f"was not found: {source_path}"
            )
            return None

        product_id = int(
            pending.get("product_id", 0)
        )
        message_id = int(
            pending.get("telegram_message_id", 0)
        )

        dataset_folder = DATASET_FOLDER_BY_LABEL.get(
            actual_label
        )

        if dataset_folder is None:
            print(
                "No training-dataset folder mapping for "
                f"feedback label: {actual_label}"
            )
            return None

        destination_dir = (
            self.training_dataset_dir
            / dataset_folder
        )

        destination_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination_path = destination_dir / (
            f"P{product_id:03d}_"
            f"telegram_{message_id}_"
            f"{source_path.name}"
        )

        try:
            shutil.copy2(
                source_path,
                destination_path,
            )
            return str(destination_path)

        except OSError as error:
            print(
                "Unable to copy confirmed feedback "
                f"image: {error}"
            )
            return None

    def _copy_incorrect_image(
        self,
        pending: dict[str, object],
    ) -> str | None:
       
        source_path = Path(str(pending.get("image_path", "")))

        if not source_path.exists():
            print(
                "Incorrect feedback recorded, but source image "
                f"was not found: {source_path}"
            )
            return None

        self.incorrect_feedback_dir.mkdir(parents=True, exist_ok=True)

        product_id = int(pending.get("product_id", 0))
        message_id = int(pending.get("telegram_message_id", 0))
        predicted_label = str(
            pending.get("predicted_label", "unknown")
        )

        destination_path = self.incorrect_feedback_dir / (
            f"P{product_id:03d}_telegram_{message_id}_"
            f"predicted_{predicted_label}_{source_path.name}"
        )

        counter = 1
        while destination_path.exists():
            destination_path = self.incorrect_feedback_dir / (
                f"P{product_id:03d}_telegram_{message_id}_{counter}_"
                f"predicted_{predicted_label}_{source_path.name}"
            )
            counter += 1

        try:
            shutil.copy2(source_path, destination_path)

            metadata_path = destination_path.with_suffix(
                destination_path.suffix + ".json"
            )
            metadata_path.write_text(
                json.dumps(
                    {
                        "product_id": product_id,
                        "predicted_label": predicted_label,
                        "confidence": pending.get("confidence"),
                        "source_image_path": str(source_path),
                        "telegram_message_id": message_id,
                        "feedback": "incorrect",
                        "needs_manual_label": True,
                        "saved_at_utc": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return str(destination_path)

        except OSError as error:
            print(f"Unable to save incorrect feedback image: {error}")
            return None

    def _finalise_incorrect_feedback(
        self,
        callback_query: dict[str, object],
        pending_key: str,
    ) -> None:
        pending = self.pending_feedback.get(pending_key)

        if not pending:
            self._answer_callback(
                callback_query_id=str(callback_query.get("id", "")),
                text=(
                    "Feedback was already recorded "
                    "or the product record is missing."
                ),
                show_alert=True,
            )
            return

        user = callback_query.get("from") or {}
        message = callback_query.get("message") or {}
        copied_image_path = self._copy_incorrect_image(pending)

        self._append_feedback_log(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "product_id": pending.get("product_id"),
                "predicted_label": pending.get("predicted_label"),
                "actual_label": None,
                "ml_correct": False,
                "confidence": pending.get("confidence"),
                "original_image_path": pending.get("image_path"),
                "feedback_image_path": copied_image_path,
                "needs_manual_label": True,
                "telegram_chat_id": pending.get("telegram_chat_id"),
                "telegram_message_id": pending.get("telegram_message_id"),
                "reviewer_id": user.get("id"),
                "reviewer_username": user.get("username"),
                "reviewer_first_name": user.get("first_name"),
            }
        )

        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        message_id = int(message.get("message_id", 0))
        current_caption = str(message.get("caption", ""))
        final_caption = (
            f"{current_caption}\n\n"
            "👎 ML prediction marked incorrect.\n"
            "Saved for manual relabelling before retraining."
        )

        try:
            self._edit_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=final_caption,
                reply_markup={"inline_keyboard": []},
            )
        except Exception as error:
            print(
                "Incorrect feedback was saved, but Telegram message "
                f"update failed: {error}"
            )

        self.pending_feedback.pop(pending_key, None)
        self._save_pending_feedback()
        self._answer_callback(
            callback_query_id=str(callback_query.get("id", "")),
            text="Saved for manual relabelling.",
        )

    @staticmethod
    def _chat_matches(
        chat: dict[str, object],
        configured_chat_id: str,
    ) -> bool:
        configured_chat_id = str(
            configured_chat_id
        ).strip()

        actual_chat_id = str(
            chat.get("id", "")
        ).strip()

        # Public channels may be configured as @channelname.
        if configured_chat_id.startswith("@"):
            configured_username = (
                configured_chat_id[1:].lower()
            )
            actual_username = str(
                chat.get("username", "")
            ).lower()

            return (
                bool(actual_username)
                and configured_username
                == actual_username
            )

        return (
            bool(configured_chat_id)
            and configured_chat_id
            == actual_chat_id
        )

    def _reviewer_is_allowed(
        self,
        user: dict[str, object],
    ) -> bool:
        if not self.allowed_feedback_user_ids:
            return True

        try:
            user_id = int(user.get("id", 0))
        except (TypeError, ValueError):
            return False

        return (
            user_id
            in self.allowed_feedback_user_ids
        )

    def _answer_callback(
        self,
        callback_query_id: str,
        text: str,
        show_alert: bool = False,
    ) -> None:
        try:
            self._post_form(
                method="answerCallbackQuery",
                fields={
                    "callback_query_id": (
                        callback_query_id
                    ),
                    "text": text,
                    "show_alert": show_alert,
                },
            )
        except Exception as error:
            print(
                "Telegram callback answer failed: "
                f"{error}"
            )

    def _edit_caption(
        self,
        chat_id: str,
        message_id: int,
        caption: str,
        reply_markup: dict[str, object],
    ) -> None:
        self._post_form(
            method="editMessageCaption",
            fields={
                "chat_id": chat_id,
                "message_id": message_id,
                "caption": caption,
                "reply_markup": reply_markup,
            },
        )

    def _finalise_feedback(
        self,
        callback_query: dict[str, object],
        pending_key: str,
        actual_label: str,
    ) -> None:
        pending = self.pending_feedback.get(
            pending_key
        )

        if not pending:
            self._answer_callback(
                callback_query_id=str(
                    callback_query.get("id", "")
                ),
                text=(
                    "Feedback was already recorded "
                    "or the product record is missing."
                ),
                show_alert=True,
            )
            return

        if actual_label not in FEEDBACK_LABELS:
            self._answer_callback(
                callback_query_id=str(
                    callback_query.get("id", "")
                ),
                text="Unknown product class.",
                show_alert=True,
            )
            return

        predicted_label = str(
            pending.get("predicted_label", "")
        )

        ml_correct = (
            predicted_label == actual_label
        )

        user = callback_query.get("from") or {}
        message = callback_query.get("message") or {}

        copied_image_path = (
            self._copy_confirmed_image(
                pending=pending,
                actual_label=actual_label,
            )
        )

        feedback_record = {
            "timestamp_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "product_id": pending.get(
                "product_id"
            ),
            "predicted_label": predicted_label,
            "actual_label": actual_label,
            "ml_correct": ml_correct,
            "confidence": pending.get(
                "confidence"
            ),
            "original_image_path": pending.get(
                "image_path"
            ),
            "feedback_image_path": (
                copied_image_path
            ),
            "telegram_chat_id": pending.get(
                "telegram_chat_id"
            ),
            "telegram_message_id": pending.get(
                "telegram_message_id"
            ),
            "reviewer_id": user.get("id"),
            "reviewer_username": user.get(
                "username"
            ),
            "reviewer_first_name": user.get(
                "first_name"
            ),
        }

        self._append_feedback_log(
            feedback_record
        )

        # Keep a copy for main.py. The Telegram callback is handled
        # inside this notifier, but EdgeHub publishing belongs to the
        # main controller.
        self.completed_feedback_events.append(
            dict(feedback_record)
        )

        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        message_id = int(
            message.get("message_id", 0)
        )
        current_caption = str(
            message.get("caption", "")
        )

        feedback_icon = (
            "✅"
            if ml_correct
            else "❌"
        )

        feedback_status = (
            "ML prediction confirmed correct."
            if ml_correct
            else "ML prediction corrected by human feedback."
        )

        actual_display = (
            LABEL_DISPLAY_NAMES.get(
                actual_label,
                actual_label,
            )
        )

        dataset_folder = DATASET_FOLDER_BY_LABEL.get(
            actual_label,
            actual_label,
        )

        final_caption = (
            f"{current_caption}\n\n"
            f"{feedback_icon} {feedback_status}\n"
            f"Actual class: {actual_display}\n"
            f"Added to training folder: "
            f"storage/datasets/{dataset_folder}"
        )

        try:
            # Empty inline_keyboard removes the buttons so the
            # same product is not labelled multiple times.
            self._edit_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=final_caption,
                reply_markup={
                    "inline_keyboard": []
                },
            )
        except Exception as error:
            print(
                "Feedback was saved, but Telegram "
                f"message update failed: {error}"
            )

        self.pending_feedback.pop(
            pending_key,
            None,
        )
        self._save_pending_feedback()

        callback_text = (
            "Correct prediction saved."
            if ml_correct
            else f"Corrected to {actual_display}."
        )

        self._answer_callback(
            callback_query_id=str(
                callback_query.get("id", "")
            ),
            text=callback_text,
        )

    def _handle_callback_query(
        self,
        callback_query: dict[str, object],
    ) -> None:
        callback_query_id = str(
            callback_query.get("id", "")
        )

        user = callback_query.get("from") or {}
        message = (
            callback_query.get("message")
            or {}
        )
        chat = message.get("chat") or {}

        if not self._chat_matches(
            chat=chat,
            configured_chat_id=(
                self.settings.telegram_chat_id
            ),
        ):
            self._answer_callback(
                callback_query_id,
                "Feedback from this chat is not accepted.",
                show_alert=True,
            )
            return

        if not self._reviewer_is_allowed(user):
            self._answer_callback(
                callback_query_id,
                "You are not authorised to label products.",
                show_alert=True,
            )
            return

        chat_id = str(chat.get("id", ""))
        message_id = int(
            message.get("message_id", 0)
        )
        pending_key = self._message_key(
            chat_id,
            message_id,
        )

        pending = self.pending_feedback.get(
            pending_key
        )

        if not pending:
            self._answer_callback(
                callback_query_id,
                (
                    "Feedback was already recorded "
                    "or the product record is missing."
                ),
                show_alert=True,
            )
            return

        callback_data = str(
            callback_query.get("data", "")
        )

        parts = callback_data.split(":", 2)

        if len(parts) != 3:
            self._answer_callback(
                callback_query_id,
                "Invalid feedback button.",
                show_alert=True,
            )
            return

        action, product_id_text, value = parts

        try:
            callback_product_id = int(
                product_id_text
            )
            pending_product_id = int(
                pending.get("product_id", -1)
            )
        except (TypeError, ValueError):
            self._answer_callback(
                callback_query_id,
                "Invalid product ID.",
                show_alert=True,
            )
            return

        if (
            callback_product_id
            != pending_product_id
        ):
            self._answer_callback(
                callback_query_id,
                "Product record does not match.",
                show_alert=True,
            )
            return

        if action == "feedback":
            if value == "true":
                predicted_label = str(
                    pending.get(
                        "predicted_label",
                        "",
                    )
                )

                self._finalise_feedback(
                    callback_query=callback_query,
                    pending_key=pending_key,
                    actual_label=predicted_label,
                )
                return

            if value == "false":
                self._finalise_incorrect_feedback(
                    callback_query=callback_query,
                    pending_key=pending_key,
                )
                return

        if action == "actual":
            self._finalise_feedback(
                callback_query=callback_query,
                pending_key=pending_key,
                actual_label=value,
            )
            return

        self._answer_callback(
            callback_query_id,
            "Unknown feedback action.",
            show_alert=True,
        )

    def get_feedback_messages(
        self,
    ) -> list[dict[str, object]]:
       
        if not self.settings.telegram_enabled:
            return []

        if not self.settings.telegram_bot_token:
            return []

        params: dict[str, object] = {
            "timeout": 0,
            "allowed_updates": json.dumps(
                [
                    "message",
                    "callback_query",
                ]
            ),
        }

        if self.last_update_id is not None:
            params["offset"] = (
                self.last_update_id + 1
            )

        url = (
            self._api_url("getUpdates")
            + "?"
            + urllib.parse.urlencode(params)
        )

        try:
            with urllib.request.urlopen(
                url,
                timeout=2,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )

        except Exception:
            return []

        messages: list[dict[str, object]] = []

        for update in payload.get("result", []):
            update_id = int(
                update.get("update_id", 0)
            )

            self.last_update_id = max(
                self.last_update_id or 0,
                update_id,
            )

            callback_query = update.get(
                "callback_query"
            )

            if isinstance(
                callback_query,
                dict,
            ):
                try:
                    self._handle_callback_query(
                        callback_query
                    )
                except Exception as error:
                    print(
                        "Telegram feedback handling "
                        f"failed: {error}"
                    )

                continue

            message = update.get("message") or {}
            text = str(
                message.get("text", "")
            ).strip()
            chat = message.get("chat") or {}
            chat_id = str(
                chat.get("id", "")
            )

            if not text:
                continue

            if not self._chat_matches(
                chat=chat,
                configured_chat_id=(
                    self._chat_id()
                ),
            ):
                continue

            messages.append(
                {
                    "text": text,
                    "chat_id": chat_id,
                }
            )

        return messages

    def pop_feedback_events(
        self,
    ) -> list[dict[str, object]]:
      
        events = list(self.completed_feedback_events)
        self.completed_feedback_events.clear()
        return events

    def alarm(self, message: str) -> None:
        self.send(
            f"🚨 Conveyor alarm: {message}"
        )