# ADR 001 — Use Redis for FSM Session Storage

**Date:** 2026-05-25
**Status:** Accepted

---

## Context

SokoFlow processes WhatsApp messages over a stateless HTTP transport. Each message
arrives as an independent POST request with no built-in session mechanism. The system
must reconstruct conversational context on every request.

A persistent session store is required to hold the current FSM state, partial flow context
(e.g. product name collected but quantity not yet provided), and message deduplication keys.

## Decision

Use Redis as the FSM session store and deduplication key store.

Sessions are stored as JSON documents under keys `session:{phone_number}` with a TTL
of 1800 seconds (30 minutes of inactivity).

Deduplication keys are stored under `processed_messages` as a Redis Set with per-key TTL
of 60 seconds.

## Consequences

**Positive:**
- Sub-millisecond read/write for session state (critical for <100ms webhook response target)
- Built-in TTL support — session expiry is automatic, no cleanup job required
- Redis is already required as the Celery broker, so no additional infrastructure cost
- `fakeredis` enables in-memory Redis in unit tests with zero infrastructure

**Negative:**
- Redis is an in-memory store; session data is lost on Redis restart without persistence config
- Mitigation: `redis.conf` with `appendonly yes` ensures data survives restarts

## Alternatives Considered

- **PostgreSQL sessions table:** Durable but too slow for sub-10ms session reads.
- **In-process memory (dict):** Not viable — multiple Celery workers cannot share process memory.

---

*Write an ADR for every significant architectural decision made during the build.*
*Template: Context → Decision → Consequences → Alternatives.*
