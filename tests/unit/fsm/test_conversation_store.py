from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from app.fsm.models import SessionState
from app.utils.errors import CorruptedSessionError, SessionStateMismatchError


@pytest.mark.asyncio
async def test_is_duplicate_when_key_exists(store, redis_mock):
    redis_mock.set.return_value = False

    assert await store.is_duplicate("abc123") is True


@pytest.mark.asyncio
async def test_is_duplicate_when_key_created(store, redis_mock):
    redis_mock.set.return_value = True

    assert await store.is_duplicate("abc123") is False


@pytest.mark.asyncio
async def test_get_session_returns_none_when_missing(store, redis_mock):  # pyright: ignore[]
    redis_mock.get.return_value = None

    result = await store.get_session("abc123")

    assert result is None
    redis_mock.get.assert_awaited_once_with("session:abc123")


@pytest.mark.asyncio
async def test_get_session_decodes_session(store, redis_mock, session):  # pyright: ignore[]
    redis_mock.get.return_value = session.model_dump_json()

    result = await store.get_session("abc123")

    assert result == session
    redis_mock.get.assert_awaited_once_with("session:abc123")


@pytest.mark.asyncio
async def test_get_session_returns_none_on_corrupted_data(store, redis_mock):  # pyright: ignore[]
    redis_mock.get.return_value = "not valid json"

    result = await store.get_session("abc123")

    assert result is None
    redis_mock.get.assert_awaited_once_with("session:abc123")


@pytest.mark.asyncio
async def test_get_session_propagates_redis_errors(store, redis_mock):  # pyright: ignore[]
    redis_mock.get.side_effect = RedisError("error")

    with pytest.raises(RedisError, match="error"):
        await store.get_session("abc123")

    redis_mock.get.assert_awaited_once_with("session:abc123")


@pytest.mark.asyncio
async def test_save_session_success_uses_idle_state_when_old_session_missing(
    store,
    redis_mock,
    session,  # pyright: ignore[]
):
    script = AsyncMock(return_value=1)

    with (
        patch("app.fsm.conversation_store.get_update_script", return_value=script),
        patch("app.fsm.conversation_store.encode_session", return_value="encoded-session"),
    ):
        await store.save_session("abc123", session, ttl=120)

    script.assert_awaited_once_with(
        keys=["session:abc123"],
        args=[SessionState.IDLE, "encoded-session", 120],
    )


@pytest.mark.asyncio
async def test_save_session_success_uses_old_state_when_present(
    store,
    redis_mock,
    session,
    idle_session,  # pyright: ignore[]
):
    script = AsyncMock(return_value=1)

    with (
        patch("app.fsm.conversation_store.get_update_script", return_value=script),
        patch("app.fsm.conversation_store.encode_session", return_value="encoded-session"),
    ):
        await store.save_session("abc123", session, old_session=idle_session, ttl=45)

    script.assert_awaited_once_with(
        keys=["session:abc123"],
        args=[SessionState.IDLE, "encoded-session", 45],
    )


@pytest.mark.asyncio
async def test_save_session_raises_state_mismatch_error(store, session):  # pyright: ignore[]
    script = AsyncMock(return_value=0)

    with (
        patch("app.fsm.conversation_store.get_update_script", return_value=script),
        patch("app.fsm.conversation_store.encode_session", return_value="encoded-session"),
    ):
        with pytest.raises(SessionStateMismatchError, match="Session abc123 changed before save"):
            await store.save_session("abc123", session)


@pytest.mark.asyncio
async def test_save_session_raises_corrupted_session_error(store, session):  # pyright: ignore[]
    script = AsyncMock(return_value=-1)

    with (
        patch("app.fsm.conversation_store.get_update_script", return_value=script),
        patch("app.fsm.conversation_store.encode_session", return_value="encoded-session"),
    ):
        with pytest.raises(CorruptedSessionError, match="Session abc123 was corrupted"):
            await store.save_session("abc123", session)


@pytest.mark.asyncio
async def test_save_session_raises_runtime_error_for_unmapped_lua_response(store, session):  # pyright: ignore[]
    script = AsyncMock(return_value=999)

    with (
        patch("app.fsm.conversation_store.get_update_script", return_value=script),
        patch("app.fsm.conversation_store.encode_session", return_value="encoded-session"),
    ):
        with pytest.raises(RuntimeError, match="Invalid or unmapped Lua response 999"):
            await store.save_session("abc123", session)


@pytest.mark.asyncio
async def test_save_session_propagates_redis_errors(store, session):  # pyright: ignore[]
    script = AsyncMock(side_effect=RedisError("boom"))

    with (
        patch("app.fsm.conversation_store.get_update_script", return_value=script),
        patch("app.fsm.conversation_store.encode_session", return_value="encoded-session"),
    ):
        with pytest.raises(RedisError, match="boom"):
            await store.save_session("abc123", session)


@pytest.mark.asyncio
async def test_delete_session_deletes_redis_key(store, redis_mock):  # pyright: ignore[]
    await store.delete_session("abc123")

    redis_mock.delete.assert_awaited_once_with("session:abc123")


@pytest.mark.asyncio
async def test_delete_session_propagates_redis_errors(store, redis_mock):  # pyright: ignore[]
    redis_mock.delete.side_effect = RedisError("boom")

    with pytest.raises(RedisError, match="boom"):
        await store.delete_session("abc123")

    redis_mock.delete.assert_awaited_once_with("session:abc123")
