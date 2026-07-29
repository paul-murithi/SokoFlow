from pathlib import Path

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

LUA_SAVE_SESSION_SCRIPT = "update_session_state.lua"
_LUA_UPDATE_SESSION: AsyncScript | None = None


def register_session_update_script(redis_client: Redis) -> None:
    global _LUA_UPDATE_SESSION

    script_path = Path(__file__).with_name("lua") / LUA_SAVE_SESSION_SCRIPT
    lua_content = script_path.read_text()
    _LUA_UPDATE_SESSION = redis_client.register_script(lua_content)


def get_update_script() -> AsyncScript:
    if _LUA_UPDATE_SESSION is None:
        raise RuntimeError("Script not registered")
    return _LUA_UPDATE_SESSION
