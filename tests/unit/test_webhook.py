import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings


def compute_signature(body: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), body, "sha256").hexdigest()
    return f"sha256={sig}"


def make_valid_payload_dict():
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "254712345678",
                                    "id": "wamid.sim_abc123",
                                    "type": "text",
                                    "text": {"body": "add product milk"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_401(client):
    payload = make_valid_payload_dict()
    response = await client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing HMAC signature"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401(client):
    payload = make_valid_payload_dict()
    headers = {"X-Hub-Signature-256": "sha256=invalid_signature"}
    response = await client.post("/webhook/whatsapp", json=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing HMAC signature"


@pytest.mark.asyncio
async def test_webhook_modified_body_returns_401(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    payload = make_valid_payload_dict()
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(body_bytes, secret)

    # Modify body
    payload["object"] = "tampered"
    headers = {"X-Hub-Signature-256": sig}
    response = await client.post("/webhook/whatsapp", json=payload, headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_malformed_json_returns_422(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    raw_body = b"not-a-json-string"
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }
    response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "Malformed webhook payload"


@pytest.mark.asyncio
async def test_webhook_structurally_invalid_payload_returns_422(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    raw_body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode("utf-8")
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }
    response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_webhook_valid_message_dispatches_task(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    payload = make_valid_payload_dict()
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
        "X-Correlation-ID": "test-corr-id-123",
    }

    with (
        patch("app.api.routes.webhook.get_redis") as mock_get_redis,
        patch("app.api.routes.webhook.conversation_task.apply_async") as mock_apply_async,
    ):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True  # NX returns True -> not duplicate
        mock_get_redis.return_value = mock_redis

        response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)

        assert response.status_code == 200
        assert response.json() == {"status": "success", "message": "accepted"}

        mock_redis.set.assert_called_once_with(
            "dedup:wamid.sim_abc123", "1", nx=True, ex=settings.dedup_ttl_seconds
        )
        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args[1]
        task_args = call_kwargs["args"][0]
        assert task_args["message_id"] == "wamid.sim_abc123"
        assert task_args["sender"] == "254712345678"
        assert task_args["message_text"] == "add product milk"
        assert task_args["correlation_id"] == "test-corr-id-123"


@pytest.mark.asyncio
async def test_webhook_duplicate_message_is_ignored(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    payload = make_valid_payload_dict()
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }

    with (
        patch("app.api.routes.webhook.get_redis") as mock_get_redis,
        patch("app.api.routes.webhook.conversation_task.apply_async") as mock_apply_async,
    ):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = False  # NX returns False -> duplicate
        mock_get_redis.return_value = mock_redis

        response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)

        assert response.status_code == 200
        assert response.json() == {"status": "ignored", "message": "Duplicate message ignored"}
        mock_apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_redis_error_returns_500(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    payload = make_valid_payload_dict()
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }

    with patch("app.api.routes.webhook.get_redis") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = Exception("Redis connection failed")
        mock_get_redis.return_value = mock_redis

        response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)
        assert response.status_code == 500
        assert response.json()["detail"] == "Infrastructure error during deduplication"


@pytest.mark.asyncio
async def test_webhook_celery_error_returns_500(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    payload = make_valid_payload_dict()
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }

    with (
        patch("app.api.routes.webhook.get_redis") as mock_get_redis,
        patch(
            "app.api.routes.webhook.conversation_task.apply_async",
            side_effect=Exception("Broker down"),
        ),
    ):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_get_redis.return_value = mock_redis

        response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)
        assert response.status_code == 500
        assert response.json()["detail"] == "Infrastructure error during task dispatch"


@pytest.mark.asyncio
async def test_webhook_does_not_access_db_or_fsm(client):
    secret = settings.whatsapp_app_secret or "your-test-app-secret-for-hmac"
    payload = make_valid_payload_dict()
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(raw_body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }

    with (
        patch("app.api.routes.webhook.get_redis") as mock_get_redis,
        patch("app.api.routes.webhook.conversation_task.apply_async"),
        patch("app.fsm.engine.FSMEngine") as mock_fsm,
    ):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_get_redis.return_value = mock_redis

        response = await client.post("/webhook/whatsapp", content=raw_body, headers=headers)
        assert response.status_code == 200
        mock_fsm.assert_not_called()
