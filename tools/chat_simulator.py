import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import httpx

from app.fsm.models import WhatsAppWebhook

RECEIVER_HOST = "localhost"
RECEIVER_PORT = 8080
WEBHOOK_URL = "http://localhost:8000/webhook/whatsapp"
STATIC_PHONE_NUMBER = "254712345678"


def construct_payload(
    phone_number: str, message: str, message_id: str
) -> WhatsAppWebhook:
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


class BotReplyReceiver(BaseHTTPRequestHandler):
    """HTTP receiver that prints bot replies from the local worker callback."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b""

        bot_text = ""
        if raw_body:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                bot_text = extract_bot_text(payload)
                if not bot_text:
                    bot_text = json.dumps(payload, ensure_ascii=True)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                bot_text = raw_body.decode("utf-8", errors="replace").strip()

        print(f"\nBot: {bot_text}\n", end="", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


def start_receiver_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((RECEIVER_HOST, RECEIVER_PORT), BotReplyReceiver)

    # Thread 1:  Daemon thread running the HTTP server in the background
    threading.Thread(target=server.serve_forever, daemon=True).start()

    return server


def send_payload(payload: WhatsAppWebhook) -> None:
    try:
        response = httpx.post(WEBHOOK_URL, json=payload.model_dump(by_alias=True))
        response.raise_for_status()
        print(f"Webhook: {response.json()}")
    except httpx.HTTPStatusError as exc:
        print(f"Error response {exc.response.status_code} while requesting {exc}.")
    except httpx.HTTPError as exc:
        print(f"Could not connect to webhook: {exc}")


def main() -> None:
    print("==== SokoFlow Chat Simulator ===")
    print(f"Receiver listening on http://{RECEIVER_HOST}:{RECEIVER_PORT}")
    print("Type 'exit' or 'quit' to stop.\n")

    server = start_receiver_server()

    try:
        # Thread 2: Interactive main loop
        while True:
            try:
                message_text = input("You ❯ ").strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break

            if message_text.lower() in {"exit", "quit"}:
                break

            if not message_text:
                continue

            payload = construct_payload(
                phone_number=STATIC_PHONE_NUMBER,
                message=message_text,
                message_id=f"wamid.{uuid4()}",
            )
            send_payload(payload)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
