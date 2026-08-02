import argparse
from uuid import uuid4

import httpx
from httpx import Client, Response

from app.fsm.models import WhatsAppWebhook


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WhatsApp Chat Simulator")

    parser.add_argument(
        "--from", dest="sender", required=True, help="Phone number of the sender."
    )

    parser.add_argument("--text", required=True, help="Message body")

    parser.add_argument("--type", choices=["text", "image", "audio"], default="text")

    return parser.parse_args()


def send_payload(payload: WhatsAppWebhook, client: Client, url: str) -> Response:
    try:
        return client.post(url, json=payload.model_dump(by_alias=True))
    except httpx.ConnectError:
        print("Could not connect to webhook")
        raise


def prepare_data() -> tuple[argparse.Namespace, str, str, Client]:
    args = parse_args()
    message_id = f"wamid.{uuid4()}"
    server_url = "http://localhost:8000/webhook/whatsapp"
    client = httpx.Client()

    return args, message_id, server_url, client


def main() -> None:
    print("==== SokoFlow Chat Simulator ===")

    args, message_id, server_url, client = prepare_data()

    # Construct payload
    payload = construct_payload(
        phone_number=args.sender, message=args.text, message_id=message_id
    )

    # Send payload
    response = send_payload(payload=payload, client=client, url=server_url)
    print(f"response: {response}")


if __name__ == "__main__":
    main()
