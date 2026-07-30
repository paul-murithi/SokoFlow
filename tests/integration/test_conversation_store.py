import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.core.config import settings
from app.fsm.conversation_store import ConversationStore
from app.fsm.models import SessionContext, SessionState, UserSession
from app.fsm.session_lua import register_session_update_script
from app.utils.errors import CorruptedSessionError, SessionStateMismatchError


@pytest_asyncio.fixture
async def redis_client():
    client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    register_session_update_script(client)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def store(redis_client: Redis):
    store = ConversationStore(redis=redis_client)
    yield store
    # Clean up test session keys after test
    keys = await redis_client.keys("session:test_*")
    if keys:
        await redis_client.delete(*keys)


@pytest.mark.asyncio
async def test_get_session_not_found(store: ConversationStore):
    session = await store.get_session("test_non_existent_session")
    assert session is None


@pytest.mark.asyncio
async def test_save_and_get_session(store: ConversationStore):
    session_id = "test_save_get"
    new_session = UserSession(
        phone="+254712345678",
        state=SessionState.IDLE,
        context=SessionContext(product_name="Maize Flour"),
    )

    await store.save_session(session_id=session_id, new_session=new_session)

    retrieved = await store.get_session(session_id)
    assert retrieved is not None
    assert retrieved.phone == new_session.phone
    assert retrieved.state == SessionState.IDLE
    assert retrieved.context.product_name == "Maize Flour"


@pytest.mark.asyncio
async def test_save_session_state_transition(store: ConversationStore):
    session_id = "test_state_transition"
    initial_session = UserSession(
        phone="+254712345678",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    await store.save_session(session_id=session_id, new_session=initial_session)

    updated_session = UserSession(
        phone="+254712345678",
        state=SessionState.SALE,
        context=SessionContext(product_name="Sugar"),
    )

    await store.save_session(
        session_id=session_id,
        new_session=updated_session,
        old_session=initial_session,
    )

    retrieved = await store.get_session(session_id)
    assert retrieved is not None
    assert retrieved.state == SessionState.SALE
    assert retrieved.context.product_name == "Sugar"


@pytest.mark.asyncio
async def test_save_session_state_mismatch_error(store: ConversationStore):
    session_id = "test_state_mismatch"
    initial_session = UserSession(
        phone="+254712345678",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    await store.save_session(session_id=session_id, new_session=initial_session)

    # Attempt save with wrong expected old_session state
    mismatched_old_session = UserSession(
        phone="+254712345678",
        state=SessionState.SALE,
        context=SessionContext(),
    )
    next_session = UserSession(
        phone="+254712345678",
        state=SessionState.CONFIRM,
        context=SessionContext(),
    )

    with pytest.raises(SessionStateMismatchError):
        await store.save_session(
            session_id=session_id,
            new_session=next_session,
            old_session=mismatched_old_session,
        )


@pytest.mark.asyncio
async def test_save_session_corrupted_data_error(
    store: ConversationStore, redis_client: Redis
):
    session_id = "test_corrupted_data"
    # Invalid non-JSON string into Redis session key
    await redis_client.set(f"session:{session_id}", "invalid_json_data")

    next_session = UserSession(
        phone="+254712345678",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    with pytest.raises(CorruptedSessionError):
        await store.save_session(
            session_id=session_id,
            new_session=next_session,
        )


@pytest.mark.asyncio
async def test_get_session_corrupted_data(
    store: ConversationStore, redis_client: Redis
):
    session_id = "test_get_corrupted"
    await redis_client.set(f"session:{session_id}", "{invalid_json}")

    retrieved = await store.get_session(session_id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_session(store: ConversationStore):
    session_id = "test_delete"
    session_data = UserSession(
        phone="+254712345678",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    await store.save_session(session_id=session_id, new_session=session_data)
    assert await store.get_session(session_id) is not None

    deleted = await store.delete_session(session_id)
    assert deleted is True

    assert await store.get_session(session_id) is None

    # Deleting non-existent session returns False
    deleted_again = await store.delete_session(session_id)
    assert deleted_again is False


@pytest.mark.asyncio
async def test_session_ttl(store: ConversationStore, redis_client: Redis):
    session_id = "test_ttl"
    session_data = UserSession(
        phone="+254712345678",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    ttl_seconds = 300
    await store.save_session(
        session_id=session_id, new_session=session_data, ttl=ttl_seconds
    )

    remaining_ttl = await redis_client.ttl(f"session:{session_id}")
    assert 0 < remaining_ttl <= ttl_seconds
