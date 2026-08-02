import argparse

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


def main() -> None:
    print("==== SokoFlow Chat Simulator ===")

    args = parse_args()

    print(f"Sender: {args.sender}")
    print(f"Message: {args.text}")


if __name__ == "__main__":
    main()
