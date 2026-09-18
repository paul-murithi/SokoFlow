import argparse
import hmac
import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx

from app.core.config import settings
from app.fsm.models import WhatsAppWebhook

RECEIVER_HOST = os.getenv("RECEIVER_HOST", "0.0.0.0")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000/webhook/whatsapp")
STATIC_PHONE_NUMBER = os.getenv(
    "DEFAULT_SIMULATOR_PHONE", settings.whatsapp_phone_number_id or "254712345678"
)
STATIC_DIR = Path(__file__).parent / "static"

# In-memory store for messages per phone number: { phone: [ {id, sender, type, text, ...}, ... ] }
messages_store: dict[str, list[dict[str, object]]] = {}
store_lock = threading.Lock()
is_server_mode = False


def construct_payload(phone_number: str, message: str, message_id: str) -> WhatsAppWebhook:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": phone_number,
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": message},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    return WhatsAppWebhook.model_validate(payload)


def extract_bot_text(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("message_text", "reply_text", "message", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for key in ("data", "result", "response", "payload"):
            nested = payload.get(key)
            if nested is not None:
                extracted = extract_bot_text(nested)
                if extracted:
                    return extracted

    if isinstance(payload, list):
        for item in payload:
            extracted = extract_bot_text(item)
            if extracted:
                return extracted

    return ""


def store_message(phone: str, message_data: dict[str, object]) -> None:
    with store_lock:
        if phone not in messages_store:
            messages_store[phone] = []
        messages_store[phone].append(message_data)


def clear_messages(phone: str) -> None:
    with store_lock:
        messages_store[phone] = []


def get_messages(phone: str) -> list[dict[str, object]]:
    with store_lock:
        return list(messages_store.get(phone, []))


class BotReplyReceiver(BaseHTTPRequestHandler):
    """HTTP receiver that serves Web UI, accepts simulated inbound requests,
    and receives bot replies from the worker callback.
    """

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json_response(self, data: object, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # API Endpoints
        if path == "/api/messages":
            phone = query_params.get("phone", [STATIC_PHONE_NUMBER])[0]
            self._send_json_response({"status": "ok", "messages": get_messages(phone)})
            return

        if path == "/api/status":
            api_connected = False
            try:
                # Check backend API root or health
                health_url = WEBHOOK_URL.rsplit("/webhook", 1)[0] + "/health"
                r = httpx.get(health_url, timeout=2.0)
                api_connected = r.status_code == 200
            except Exception:
                api_connected = False

            self._send_json_response(
                {
                    "status": "ok",
                    "webhook_url": WEBHOOK_URL,
                    "api_connected": api_connected,
                    "phone": STATIC_PHONE_NUMBER,
                }
            )
            return

        # Static file serving
        if path == "/":
            file_path = STATIC_DIR / "index.html"
            content_type = "text/html; charset=utf-8"
        elif path == "/style.css":
            file_path = STATIC_DIR / "style.css"
            content_type = "text/css; charset=utf-8"
        elif path == "/app.js":
            file_path = STATIC_DIR / "app.js"
            content_type = "application/javascript; charset=utf-8"
        else:
            self._send_json_response({"detail": "Not found"}, 404)
            return

        if file_path.exists() and file_path.is_file():
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json_response({"detail": "File not found"}, 404)

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b""

        # Web UI Inbound Send API
        if path == "/api/send":
            try:
                payload_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                phone = str(payload_data.get("phone") or STATIC_PHONE_NUMBER).strip()
                message_text = str(payload_data.get("message") or "").strip()

                if not message_text:
                    self._send_json_response({"detail": "Message text required"}, 400)
                    return

                msg_id = f"wamid.{uuid4()}"

                # Store user message in local Simulator log
                store_message(
                    phone,
                    {
                        "id": msg_id,
                        "sender": "user",
                        "type": "text",
                        "text": message_text,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                # Send simulated WhatsApp webhook to backend API
                webhook_payload = construct_payload(
                    phone_number=phone,
                    message=message_text,
                    message_id=msg_id,
                )
                success = send_payload(webhook_payload)

                if success:
                    self._send_json_response({"status": "ok", "message_id": msg_id})
                else:
                    self._send_json_response({"detail": "Failed to post to backend webhook"}, 502)

            except Exception as exc:
                self._send_json_response({"detail": str(exc)}, 500)
            return

        # Clear Chat API
        if path == "/api/clear":
            try:
                payload_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                phone = str(payload_data.get("phone") or STATIC_PHONE_NUMBER).strip()
                clear_messages(phone)
                self._send_json_response({"status": "ok"})
            except Exception as exc:
                self._send_json_response({"detail": str(exc)}, 500)
            return

        # Outbound Bot Reply Callback - from MockMessageSender
        bot_text = ""
        recipient = STATIC_PHONE_NUMBER
        filename = None
        caption = None
        document_length = None

        if raw_body:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                if isinstance(payload, dict):
                    recipient = str(payload.get("recipient") or recipient)
                    filename = payload.get("filename")
                    caption = payload.get("caption")
                    document_length = payload.get("document_length")

                bot_text = extract_bot_text(payload)
                if not bot_text and not filename:
                    bot_text = json.dumps(payload, ensure_ascii=True)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                bot_text = raw_body.decode("utf-8", errors="replace").strip()

        msg_data: dict[str, object] = {
            "id": f"bot-{uuid4()}",
            "sender": "bot",
            "type": "document" if filename else "text",
            "text": bot_text or caption or (f"Document: {filename}" if filename else ""),
            "filename": filename,
            "caption": caption,
            "document_length": document_length,
            "timestamp": datetime.now().isoformat(),
        }

        store_message(recipient, msg_data)

        # CLI mode - print to console
        if not is_server_mode:
            print(f"\nBot: {bot_text}\n", end="", flush=True)

        self._send_json_response({"status": "ok"})


def start_receiver_server(host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), BotReplyReceiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def send_payload(
    payload: WhatsAppWebhook,
    app_secret: str | None = None,
    invalid_signature: bool = False,
    custom_message_id: str | None = None,
) -> bool:
    if app_secret is None:
        app_secret = settings.whatsapp_app_secret or "test-app-secret-for-hmac"

    if custom_message_id and payload.entry:
        payload.entry[0].changes[0].value.messages[0].id = custom_message_id

    raw_body = json.dumps(payload.model_dump(by_alias=True)).encode("utf-8")

    if invalid_signature:
        sig_header = "sha256=invalid_hmac_signature_hex"
    else:
        sig_hex = hmac.new(app_secret.encode("utf-8"), raw_body, "sha256").hexdigest()
        sig_header = f"sha256={sig_hex}"

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig_header,
    }

    try:
        response = httpx.post(WEBHOOK_URL, content=raw_body, headers=headers)
        response.raise_for_status()
        print(f"[Simulator] Webhook accepted message (HTTP {response.status_code})")
        return True
    except httpx.HTTPStatusError as exc:
        print(f"Error response {exc.response.status_code} while requesting {exc}.")
        return False
    except httpx.HTTPError as exc:
        print(f"Could not connect to webhook ({WEBHOOK_URL}): {exc}")
        return False


def main() -> None:
    global is_server_mode

    parser = argparse.ArgumentParser(description="SokoFlow WhatsApp Chat Simulator")
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run in standalone Web UI server mode without CLI prompt",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for simulator HTTP server (default: 3000 for --server, 8080 for CLI)",
    )
    args = parser.parse_args()

    is_server_mode = args.server

    # Determine default port based on MESSAGE_SENDER_URL or SIMULATOR_PORT or default 8080
    env_sender_url = os.getenv("MESSAGE_SENDER_URL", "")
    sender_port = None
    if env_sender_url:
        try:
            parsed = urlparse(env_sender_url)
            if parsed.port:
                sender_port = parsed.port
        except Exception:
            pass

    default_port = sender_port or int(os.getenv("PORT", os.getenv("SIMULATOR_PORT", "8080")))
    port = args.port or default_port

    print("==== SokoFlow Chat Simulator ===")
    print(f"Simulator Web UI available at: http://{RECEIVER_HOST}:{port}/")
    print(f"Webhook URL target: {WEBHOOK_URL}")

    if is_server_mode:
        server = ThreadingHTTPServer((RECEIVER_HOST, port), BotReplyReceiver)
        print(f"Server mode active. Listening on http://{RECEIVER_HOST}:{port}/ ...")
        try:
            server.serve_forever()
        except (KeyboardInterrupt, SystemExit):
            print("\nShutting down simulator server.")
        finally:
            server.shutdown()
            server.server_close()
    else:
        print(f"CLI mode active. Bot receiver listening on http://{RECEIVER_HOST}:{port}")
        print("Type 'exit' or 'quit' to stop.\n")

        server = start_receiver_server(RECEIVER_HOST, port)

        try:
            while True:
                try:
                    message_text = input("You ❯ ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if message_text.lower() in {"exit", "quit"}:
                    break

                if not message_text:
                    continue

                msg_id = f"wamid.{uuid4()}"
                store_message(
                    STATIC_PHONE_NUMBER,
                    {
                        "id": msg_id,
                        "sender": "user",
                        "type": "text",
                        "text": message_text,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                payload = construct_payload(
                    phone_number=STATIC_PHONE_NUMBER,
                    message=message_text,
                    message_id=msg_id,
                )
                send_payload(payload)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
