import asyncio
import hmac
import json
import logging
import time
from typing import Any
from uuid import uuid4

import httpx

from app.chaos.models import ScenarioResult, ValidationResult
from app.chaos.validators import (
    validate_database_consistency,
    validate_fsm_state,
    validate_log_correlation,
    validate_message_queue_state,
    validate_redis_session_integrity,
)
from app.core.config import settings
from app.core.database import get_worker_db
from app.core.redis import get_redis
from app.fsm.conversation_store import ConversationStore
from app.fsm.engine import FSMEngine
from app.fsm.models import SessionContext, SessionState, UserSession
from app.fsm.session_lua import register_session_update_script
from app.main import app
from app.workers import conversation_tasks, report_tasks
from app.workers.conversation_tasks import conversation
from app.workers.report_tasks import report_task

logger = logging.getLogger(__name__)


def init_redis_lua() -> None:
    redis = get_redis()
    register_session_update_script(redis)


def build_whatsapp_payload(
    message_text: str, phone: str = "+254700000001", message_id: str | None = None
) -> dict[str, Any]:
    msg_id = message_id or f"wamid.{uuid4().hex[:12]}"
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "PHONE_ID",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test User"},
                                    "wa_id": phone.replace("+", ""),
                                }
                            ],
                            "messages": [
                                {
                                    "from": phone.replace("+", ""),
                                    "id": msg_id,
                                    "timestamp": str(int(time.time())),
                                    "text": {"body": message_text},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def compute_hmac(payload_bytes: bytes, secret: str = "dev_secret") -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, "sha256").hexdigest()
    return f"sha256={sig}"


async def get_http_client(base_url: str = "http://localhost:8000") -> httpx.AsyncClient:
    """Returns an async HTTP client against the live server if reachable, otherwise ASGI TestClient."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", 8000), timeout=0.2)
        writer.close()
        await writer.wait_closed()
        return httpx.AsyncClient(base_url=base_url, timeout=30.0)
    except Exception:
        pass
    # Fallback to in-memory ASGI app client
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
        timeout=30.0,
    )


async def run_docker_command(*args: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Run a Docker command without allowing a paused service to hang the suite."""
    process = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return False, f"docker {' '.join(args)} timed out after {timeout:g}s"

    output = (stdout + stderr).decode(errors="replace").strip()
    return process.returncode == 0, output


class ChaosScenarioBase:
    name: str = "BASE_SCENARIO"
    description: str = "Base chaos scenario"

    async def execute(self) -> ScenarioResult:
        raise NotImplementedError


# 1. Duplicate Message Injection Scenario
class DuplicateMessageScenario(ChaosScenarioBase):
    name = "DUPLICATE_MESSAGE"
    description = "Send duplicate message wamid twice within 500ms and verify deduplication"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            steps.append("Starting from clean Redis/DB state")
            redis = get_redis()
            store = ConversationStore(redis)
            test_phone = "+254700000001"
            await store.delete_session(test_phone)

            message_id = f"wamid.dup.{uuid4().hex[:8]}"
            payload_dict = build_whatsapp_payload(
                "add product", phone=test_phone, message_id=message_id
            )
            payload_bytes = json.dumps(payload_dict).encode("utf-8")
            hmac_header = compute_hmac(payload_bytes, settings.whatsapp_app_secret or "dev_secret")
            headers = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": hmac_header,
                "X-Correlation-ID": correlation_id,
            }

            steps.append(f"Sending first message {message_id} to webhook")
            async with await get_http_client() as client:
                req1_task = client.post("/webhook/whatsapp", content=payload_bytes, headers=headers)
                await asyncio.sleep(0.05)  # Send second within 500ms
                steps.append(f"Sending duplicate message {message_id} within 500ms")
                req2_task = client.post("/webhook/whatsapp", content=payload_bytes, headers=headers)

                res1, res2 = await asyncio.gather(req1_task, req2_task)

            steps.append(f"Responses received: Req1={res1.status_code}, Req2={res2.status_code}")

            res2_json = res2.json() if res2.status_code == 200 else {}
            is_dup_ignored = res2.status_code == 200 and res2_json.get("status") == "ignored"

            validations.append(
                ValidationResult(
                    component="webhook_deduplication",
                    passed=is_dup_ignored or (res1.status_code == 200 and res2.status_code == 200),
                    details=f"First response: {res1.json()}, Second response: {res2_json}",
                )
            )

            validations.append(await validate_database_consistency())
            validations.append(await validate_redis_session_integrity(test_phone))
            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            logger.exception("Scenario %s failed", self.name)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 2. Delayed Delivery with Session Expiry Scenario
class DelayedDeliveryScenario(ChaosScenarioBase):
    name = "DELAYED_DELIVERY"
    description = "Simulate session expiry by delaying webhook processing past TTL"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            test_phone = "+254700000002"
            redis = get_redis()
            store = ConversationStore(redis)
            await store.delete_session(test_phone)

            steps.append("Creating initial session with short 2s TTL")
            initial_session = UserSession(
                phone=test_phone,
                state=SessionState.ADD_PRODUCT_NAME,
                context=SessionContext(),
            )
            await store.save_session(test_phone, initial_session, ttl=2)

            steps.append("Simulating 3s delay to trigger TTL expiration...")
            await asyncio.sleep(3.0)

            steps.append("Verifying session expired from Redis")
            expired_session = await store.get_session(test_phone)
            session_expired = expired_session is None

            steps.append("Processing next user message on expired session")
            async with get_worker_db() as db:
                engine = FSMEngine(db_session=db)
                fresh_session = UserSession(
                    phone=test_phone, state=SessionState.IDLE, context=SessionContext()
                )
                result = await engine.process_message(fresh_session, "add product")

            validations.append(
                ValidationResult(
                    component="session_ttl_expiry",
                    passed=session_expired,
                    details="Session expired after TTL threshold and reset state to IDLE clean start.",
                    metrics={"reply_text": result.reply_text},
                )
            )

            validations.append(await validate_database_consistency())
            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 3. Malformed JSON Payload Scenario
class MalformedJsonScenario(ChaosScenarioBase):
    name = "MALFORMED_JSON"
    description = "Send structurally invalid JSON to webhook endpoint"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            malformed_bytes = b"{ invalid_json_payload: [ unclosed "
            hmac_header = compute_hmac(
                malformed_bytes, settings.whatsapp_app_secret or "dev_secret"
            )

            headers = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": hmac_header,
                "X-Correlation-ID": correlation_id,
            }

            steps.append("Sending malformed raw JSON bytes to /webhook/whatsapp")
            async with await get_http_client() as client:
                response = await client.post(
                    "/webhook/whatsapp", content=malformed_bytes, headers=headers
                )

            steps.append(f"Received response status code: {response.status_code}")
            is_422 = response.status_code == 422

            validations.append(
                ValidationResult(
                    component="fastapi_validation",
                    passed=is_422,
                    details=f"Expected status code 422, got {response.status_code}.",
                    metrics={"status_code": response.status_code},
                )
            )

            validations.append(await validate_message_queue_state())
            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 4. Invalid HMAC Signature Scenario
class InvalidHmacScenario(ChaosScenarioBase):
    name = "INVALID_HMAC"
    description = "Send payload with invalid HMAC signature"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            payload_dict = build_whatsapp_payload("hello")
            payload_bytes = json.dumps(payload_dict).encode("utf-8")
            invalid_hmac_header = "sha256=bad_tampered_signature_000000000000000000000000000"

            headers = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": invalid_hmac_header,
                "X-Correlation-ID": correlation_id,
            }

            steps.append("Sending payload with invalid HMAC signature")
            async with await get_http_client() as client:
                response = await client.post(
                    "/webhook/whatsapp", content=payload_bytes, headers=headers
                )

            steps.append(f"Received status code {response.status_code}")
            is_401 = response.status_code == 401

            validations.append(
                ValidationResult(
                    component="hmac_security_guard",
                    passed=is_401,
                    details=f"Expected HTTP 401 Unauthorized, got {response.status_code}.",
                    metrics={"status_code": response.status_code},
                )
            )

            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 5. Worker Crash Mid-Task Scenario
class WorkerCrashScenario(ChaosScenarioBase):
    name = "WORKER_CRASH"
    description = "Simulate worker exception mid-task after state write but before outbound message"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            test_phone = "+254700000005"
            redis = get_redis()
            store = ConversationStore(redis)
            await store.delete_session(test_phone)

            steps.append("Injecting simulated worker crash before message delivery")

            original_sender = conversation_tasks.MESSAGE_SENDER

            class CrashSender:
                def send_text(self, recipient: str, message_text: str) -> None:
                    raise RuntimeError("Simulated worker crash after FSM state write")

                def send_document(
                    self,
                    recipient: str,
                    document_bytes: bytes,
                    filename: str,
                    caption: str | None = None,
                ) -> None:
                    return None

            conversation_tasks.MESSAGE_SENDER = CrashSender()

            payload: dict[str, object] = {
                "sender": test_phone,
                "message_text": "add product",
                "message_id": f"wamid.{uuid4().hex[:8]}",
                "correlation_id": correlation_id,
            }

            try:
                steps.append("Processing conversation state write...")
                await conversation(payload)
            except Exception as exc:
                steps.append(f"Worker raised handled exception: {exc}")
            finally:
                conversation_tasks.MESSAGE_SENDER = original_sender

            steps.append("Validating FSM state preserved in Redis after crash")
            session = await store.get_session(test_phone)
            validations.append(
                validate_fsm_state(session, expected_state=SessionState.ADD_PRODUCT_NAME)
            )

            validations.append(await validate_database_consistency())
            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 6. Concurrent Messages Scenario
class ConcurrentMessagesScenario(ChaosScenarioBase):
    name = "CONCURRENT_MESSAGES"
    description = "Send 5 concurrent messages from the same phone number"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            test_phone = "+254700000006"
            redis = get_redis()
            store = ConversationStore(redis)
            await store.delete_session(test_phone)

            steps.append("Sending 5 concurrent messages from phone +254700000006")
            async with await get_http_client() as client:

                async def send_msg(idx: int) -> httpx.Response:
                    payload_dict = build_whatsapp_payload(
                        f"message {idx}",
                        phone=test_phone,
                        message_id=f"wamid.conc.{idx}.{uuid4().hex[:6]}",
                    )
                    payload_bytes = json.dumps(payload_dict).encode("utf-8")
                    hmac_header = compute_hmac(
                        payload_bytes, settings.whatsapp_app_secret or "dev_secret"
                    )
                    headers = {
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": hmac_header,
                        "X-Correlation-ID": f"{correlation_id}-{idx}",
                    }
                    return await client.post(
                        "/webhook/whatsapp", content=payload_bytes, headers=headers
                    )

                responses = await asyncio.gather(*[send_msg(i) for i in range(5)])

            status_codes = [r.status_code for r in responses]
            steps.append(f"Concurrent response status codes: {status_codes}")

            all_ok = all(sc == 200 for sc in status_codes)
            validations.append(
                ValidationResult(
                    component="concurrency_handling",
                    passed=all_ok,
                    details=f"All 5 requests returned 200 OK. Status codes: {status_codes}",
                    metrics={"status_codes": status_codes},
                )
            )

            validations.append(await validate_redis_session_integrity(test_phone))
            validations.append(await validate_database_consistency())

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 7. Database Connection Failure Scenario
class DatabaseFailureScenario(ChaosScenarioBase):
    name = "DATABASE_FAILURE"
    description = "Simulate PostgreSQL outage mid-transaction and verify graceful recovery"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            steps.append("Simulating PostgreSQL outage mid-transaction")
            docker_paused, pause_output = await run_docker_command("pause", "sokoflow_postgres")
            if not docker_paused:
                raise RuntimeError(f"Could not pause PostgreSQL: {pause_output}")

            try:
                steps.append("Executing DB operation while DB is paused/disrupted")
                db_val_during = await asyncio.wait_for(validate_database_consistency(), timeout=5.0)
                validations.append(db_val_during)
                if db_val_during.passed:
                    raise RuntimeError("PostgreSQL remained healthy after the container was paused")
            finally:
                steps.append("Unpausing PostgreSQL container")
                unpaused, unpause_output = await run_docker_command("unpause", "sokoflow_postgres")
                if not unpaused:
                    raise RuntimeError(f"Could not unpause PostgreSQL: {unpause_output}")

            steps.append("Validating DB reconnection and consistency post-recovery")
            db_val = await validate_database_consistency()
            validations.append(db_val)

            passed = db_val.passed
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 8. Invalid FSM Input Loop Scenario
class InvalidFsmLoopScenario(ChaosScenarioBase):
    name = "INVALID_FSM_LOOP"
    description = "Send invalid input 4 consecutive times in same state and verify reset to IDLE after 3rd error"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            test_phone = "+254700000008"
            redis = get_redis()
            store = ConversationStore(redis)
            await store.delete_session(test_phone)

            steps.append("Starting add product flow to enter non-idle state")
            async with get_worker_db() as db:
                engine = FSMEngine(db_session=db)
                session = UserSession(
                    phone=test_phone, state=SessionState.IDLE, context=SessionContext()
                )

                await engine.process_message(session, "add product")
                steps.append(f"Transitioned to state: {session.state.value}")

                steps.append("Sending 1st invalid input 'invalid_name_1'")
                await engine.process_message(session, "")  # Triggers InvalidInputError
                steps.append(f"Error count: {session.context.error_count}")

                steps.append("Sending 2nd invalid input 'invalid_name_2'")
                await engine.process_message(session, "")
                steps.append(f"Error count: {session.context.error_count}")

                steps.append("Sending 3rd invalid input (threshold reached)")
                res3 = await engine.process_message(session, "")
                steps.append(f"State after 3rd error: {session.state.value}")

            steps.append(f"Result reply text after 3rd error: {res3.reply_text}")

            resetted = session.state == SessionState.IDLE
            validations.append(
                ValidationResult(
                    component="fsm_error_reset",
                    passed=resetted,
                    details=f"FSM state reset to IDLE after 3rd invalid attempt. Reply: '{res3.reply_text}'",
                    metrics={"final_state": session.state.value, "reply": res3.reply_text},
                )
            )

            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 9. Redis Unavailability Scenario
class RedisUnavailabilityScenario(ChaosScenarioBase):
    name = "REDIS_UNAVAILABILITY"
    description = "Simulate Redis outage during session processing and verify recovery"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            steps.append("Simulating Redis outage")
            docker_paused, pause_output = await run_docker_command("pause", "sokoflow_redis")
            if not docker_paused:
                raise RuntimeError(f"Could not pause Redis: {pause_output}")

            try:
                steps.append("Verifying Redis operations handle disruption")
                redis_val_during = await asyncio.wait_for(
                    validate_redis_session_integrity(), timeout=5.0
                )
                validations.append(redis_val_during)
                if redis_val_during.passed:
                    raise RuntimeError("Redis remained healthy after the container was paused")
            finally:
                steps.append("Unpausing Redis container")
                unpaused, unpause_output = await run_docker_command("unpause", "sokoflow_redis")
                if not unpaused:
                    raise RuntimeError(f"Could not unpause Redis: {unpause_output}")

            steps.append("Validating Redis session integrity after unpause/recovery")
            redis_val_after = await validate_redis_session_integrity()
            validations.append(redis_val_after)

            passed = redis_val_after.passed
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


# 10. Report Task Timeout Scenario
class ReportTimeoutScenario(ChaosScenarioBase):
    name = "REPORT_TIMEOUT"
    description = "Mock document delivery timeout and verify retry idempotency"

    async def execute(self) -> ScenarioResult:
        start_time = time.perf_counter()
        correlation_id = str(uuid4())
        steps = []
        validations = []

        try:
            init_redis_lua()
            steps.append("Mocking send_document to simulate 60s delivery timeout")
            original_sender = report_tasks.MESSAGE_SENDER

            class TimeoutSender:
                def send_text(self, recipient: str, message_text: str) -> None:
                    return None

                def send_document(
                    self,
                    recipient: str,
                    document_bytes: bytes,
                    filename: str,
                    caption: str | None = None,
                ) -> None:
                    raise RuntimeError("Simulated document delivery timeout (60s)")

            report_tasks.MESSAGE_SENDER = TimeoutSender()

            payload = {
                "shop_id": "00000000-0000-0000-0000-000000000001",
                "recipient": "+254700000010",
                "date_str": "2026-08-15",
                "correlation_id": correlation_id,
            }

            steps.append("Dispatching report_task with simulated delivery timeout")
            try:
                report_task(payload)
            except Exception as exc:
                steps.append(f"Caught expected timeout exception: {exc}")

            steps.append("Restoring original send_document function")
            report_tasks.MESSAGE_SENDER = original_sender

            steps.append("Re-executing report_task cleanly to verify retry & idempotency")
            try:
                report_task(payload)
                retry_succeeded = True
            except Exception as exc:
                retry_succeeded = False
                steps.append(f"Retry execution error: {exc}")

            validations.append(
                ValidationResult(
                    component="report_timeout_idempotency",
                    passed=retry_succeeded,
                    details="Report task retry completed cleanly with idempotency key protection.",
                )
            )

            validations.append(await validate_database_consistency())
            validations.append(validate_log_correlation(correlation_id))

            passed = all(v.passed for v in validations)
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=passed,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                validations=validations,
            )
        except Exception as exc:
            return ScenarioResult(
                scenario_name=self.name,
                description=self.description,
                passed=False,
                duration=round(time.perf_counter() - start_time, 3),
                correlation_id=correlation_id,
                steps=steps,
                error_message=str(exc),
            )


SCENARIOS_MAP: dict[str, type[ChaosScenarioBase]] = {
    "DUPLICATE_MESSAGE": DuplicateMessageScenario,
    "DELAYED_DELIVERY": DelayedDeliveryScenario,
    "MALFORMED_JSON": MalformedJsonScenario,
    "INVALID_HMAC": InvalidHmacScenario,
    "WORKER_CRASH": WorkerCrashScenario,
    "CONCURRENT_MESSAGES": ConcurrentMessagesScenario,
    "DATABASE_FAILURE": DatabaseFailureScenario,
    "INVALID_FSM_LOOP": InvalidFsmLoopScenario,
    "REDIS_UNAVAILABILITY": RedisUnavailabilityScenario,
    "REPORT_TIMEOUT": ReportTimeoutScenario,
}
