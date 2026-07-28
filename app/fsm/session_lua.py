from pathlib import Path

from redis.asyncio import Redis

LUA_SAVE_SESSION_SCRIPT = "update_session_state.lua"
LUA_UPDATE_SESSION = None


def register_session_update_script(redis_client: Redis) -> None:
    global LUA_UPDATE_SESSION

    script_path = Path(__file__).with_name("lua") / LUA_SAVE_SESSION_SCRIPT
    lua_content = script_path.read_text()
    LUA_UPDATE_SESSION = redis_client.register_script(lua_content)
