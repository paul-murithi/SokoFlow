local key = KEYS[1]
local expected_old_state = ARGV[1]
local new_json_payload = ARGV[2]
local ttl = tonumber(ARGV[3])

-- Existing session string
local current_raw = redis.call("GET", key)

if current_raw then
	-- safely parse JSON
	local success, current_session = pcall(cjson.decode, current_raw)

	-- reject write if string is invalid JSON or parsing fails
	if not success then
		return -1 -- Corrupted data
	end

	-- Reject if state is missing / does not match FSM expected state
	if not current_session.state or current_session.state ~= expected_old_state then
		return 0 -- Optimistic locking failure or stale data
	end
end

-- safely commit the new update
redis.call("SET", key, new_json_payload, "EX", ttl)
return 1 -- Success
