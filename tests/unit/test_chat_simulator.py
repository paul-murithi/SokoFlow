import httpx

from tools.chat_simulator import (
    clear_messages,
    construct_payload,
    extract_bot_text,
    get_messages,
    start_receiver_server,
    store_message,
)


def test_construct_payload():
    payload = construct_payload("254712345678", "add product", "wamid.123")
    assert payload.entry[0].changes[0].value.messages[0].from_ == "254712345678"
    assert payload.entry[0].changes[0].value.messages[0].id == "wamid.123"
    assert payload.entry[0].changes[0].value.messages[0].text.body == "add product"


def test_extract_bot_text():
    assert extract_bot_text({"reply_text": "Hello"}) == "Hello"
    assert extract_bot_text({"data": {"message": "Nested"}}) == "Nested"
    assert extract_bot_text([{"text": "List item"}]) == "List item"
    assert extract_bot_text({}) == ""


def test_messages_store_operations():
    phone = "254799887766"
    clear_messages(phone)
    assert get_messages(phone) == []

    msg = {"id": "1", "sender": "user", "text": "Hi"}
    store_message(phone, msg)
    assert len(get_messages(phone)) == 1
    assert get_messages(phone)[0]["text"] == "Hi"

    clear_messages(phone)
    assert get_messages(phone) == []


def test_server_get_endpoints():
    server = start_receiver_server("127.0.0.1", 0)
    host, port = server.server_address
    try:
        url = f"http://{host}:{port}/"
        res = httpx.get(url, timeout=3.0)
        assert res.status_code == 200
        assert "SokoFlow" in res.text

        api_url = f"http://{host}:{port}/api/messages?phone=254799887766"
        res_api = httpx.get(api_url, timeout=3.0)
        assert res_api.status_code == 200
        assert "messages" in res_api.json()
    finally:
        server.shutdown()
        server.server_close()
