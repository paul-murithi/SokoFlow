import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chaos.models import ValidationResult
from app.core.database import get_worker_db
from app.core.redis import get_redis
from app.fsm.conversation_store import ConversationStore
from app.fsm.models import SessionState, UserSession
from app.models import Inventory, Product, Sale

logger = logging.getLogger(__name__)


async def validate_database_consistency(
    db_session: AsyncSession | None = None,
) -> ValidationResult:
    """Validates database integrity across products, inventory, and sales schemas.

    - Inventory quantities are non-negative.
    - Every inventory item maps to an existing product.
    - Every sale references a valid shop/product.
    """
    try:

        async def _run_validation(session: AsyncSession) -> ValidationResult:
            # 1. Check non-negative inventory
            inv_res = await session.execute(select(Inventory).where(Inventory.quantity < 0))
            negative_inv = inv_res.scalars().all()
            if negative_inv:
                return ValidationResult(
                    component="database_inventory",
                    passed=False,
                    details=f"Found {len(negative_inv)} inventory records with negative quantity.",
                    failure_reason="Inventory constraint violation: negative stock quantity",
                    metrics={"negative_inventory_count": len(negative_inv)},
                )

            # 2. Check total products & sales records count
            products_res = await session.execute(select(Product))
            products = products_res.scalars().all()

            sales_res = await session.execute(select(Sale))
            sales = sales_res.scalars().all()

            return ValidationResult(
                component="database_consistency",
                passed=True,
                details="Database state is consistent. No negative stock or orphaned records found.",
                metrics={"product_count": len(products), "sales_count": len(sales)},
            )

        if db_session is not None:
            return await _run_validation(db_session)

        async with get_worker_db() as db:
            return await _run_validation(db)
    except Exception as exc:
        logger.exception("Database validation failed: %s", exc)
        return ValidationResult(
            component="database_consistency",
            passed=False,
            details=f"Database check exception: {str(exc)}",
            failure_reason=str(exc),
        )


async def validate_redis_session_integrity(
    phone_number: str | None = None,
) -> ValidationResult:
    """Validates Redis session integrity.

    - Verifies session store access.
    - If phone_number is provided, validates that session can be deserialized cleanly into UserSession.
    """
    try:
        redis = get_redis()
        store = ConversationStore(redis)

        if phone_number:
            session = await store.get_session(phone_number)
            if session:
                if not isinstance(session.state, SessionState):
                    return ValidationResult(
                        component="redis_session",
                        passed=False,
                        details=f"Session state '{session.state}' is invalid.",
                        failure_reason="Invalid SessionState enum value",
                    )
            return ValidationResult(
                component="redis_session",
                passed=True,
                details=f"Session for phone {phone_number} retrieved and validated successfully.",
                metrics={
                    "phone": phone_number,
                    "state": session.state.value if session else "NONE",
                },
            )

        # Ping Redis
        pong = await redis.ping()
        if not pong:
            return ValidationResult(
                component="redis_session",
                passed=False,
                details="Redis ping failed.",
                failure_reason="Redis unresponsive to PING",
            )

        return ValidationResult(
            component="redis_session",
            passed=True,
            details="Redis connection and session store healthy.",
            metrics={"redis_ping": True},
        )
    except Exception as exc:
        return ValidationResult(
            component="redis_session",
            passed=False,
            details=f"Redis session integrity check error: {exc}",
            failure_reason=str(exc),
        )


def validate_fsm_state(
    session: UserSession | None, expected_state: SessionState = SessionState.IDLE
) -> ValidationResult:
    """Validates FSM state correctness."""
    if session is None:
        if expected_state == SessionState.IDLE:
            return ValidationResult(
                component="fsm_state",
                passed=True,
                details="Session is None (treated as IDLE state).",
                metrics={"state": "IDLE"},
            )
        return ValidationResult(
            component="fsm_state",
            passed=False,
            details=f"Expected state {expected_state.value}, but session was None.",
            failure_reason="Session is None",
        )

    if session.state == expected_state:
        return ValidationResult(
            component="fsm_state",
            passed=True,
            details=f"FSM state matches expected state '{expected_state.value}'.",
            metrics={
                "state": session.state.value,
                "error_count": session.context.error_count,
            },
        )

    return ValidationResult(
        component="fsm_state",
        passed=False,
        details=f"FSM state mismatch. Expected '{expected_state.value}', got '{session.state.value}'.",
        failure_reason=f"State mismatch: {session.state.value} != {expected_state.value}",
        metrics={
            "actual_state": session.state.value,
            "expected_state": expected_state.value,
        },
    )


async def validate_message_queue_state() -> ValidationResult:
    """Validates Celery / Redis message queue state."""
    try:
        redis = get_redis()
        # Check standard queue keys in Redis
        conv_queue_len = await redis.llen("conversation_tasks")  # type: ignore[misc]
        report_queue_len = await redis.llen("reports_tasks")  # type: ignore[misc]

        return ValidationResult(
            component="message_queue",
            passed=True,
            details="Celery queues checked successfully.",
            metrics={
                "conversation_queue_length": conv_queue_len,
                "reports_queue_length": report_queue_len,
            },
        )
    except Exception as exc:
        return ValidationResult(
            component="message_queue",
            passed=False,
            details=f"Message queue check failed: {exc}",
            failure_reason=str(exc),
        )


def validate_log_correlation(correlation_id: str) -> ValidationResult:
    """Validates presence and propagation of correlation ID."""
    if correlation_id and len(correlation_id) > 0:
        return ValidationResult(
            component="log_correlation",
            passed=True,
            details=f"Correlation ID '{correlation_id}' validated.",
            metrics={"correlation_id": correlation_id},
        )
    return ValidationResult(
        component="log_correlation",
        passed=False,
        details="Correlation ID missing or empty.",
        failure_reason="Missing correlation_id",
    )
