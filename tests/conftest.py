import pytest
import fakeredis


@pytest.fixture
def fake_redis():
    """In-memory Redis for unit tests. No running Redis required."""
    return fakeredis.FakeRedis(decode_responses=True)


# TODO: async DB session fixture
# @pytest.fixture
# async def db_session():
#     ...

# TODO: FastAPI TestClient fixture
# @pytest.fixture
# def client():
#     from fastapi.testclient import TestClient
#     from app.main import app
#     return TestClient(app)
