# ADR 001: Use Redis for FSM Session Storage

**Date:** 2026-05-25
**Status:** Accepted

---

## Context

SokoFlow receives WhatsApp messages through a stateless HTTP webhook. Every message arrives as an independent request, so there’s no built-in concept of a session or conversation history.

To make the FSM work, we need a way to persist conversational state between messages — things like the current step in the flow, partially collected data (e.g. product name before quantity is provided), and deduplication of repeated webhook deliveries.

This requires a fast, shared, and temporary state store.

---

## Decision

We will use **Redis** as the session store for FSM state and as the deduplication store.

Each session is stored under:

`session:{phone_number}`

* Format: JSON document representing current FSM state
* TTL: 1800 seconds (30 minutes of inactivity)

Message deduplication is handled using a Redis Set:

* Key: `processed_messages`
* TTL per entry: 60 seconds

---

## Rationale

Redis fits the problem well because the FSM needs extremely fast read/write access on every incoming message. The webhook response path is latency-sensitive, so avoiding slower persistent storage here is important.

It also already exists in the stack as the Celery broker, so there’s no additional infrastructure overhead.

TTL support is a big win here — sessions expire naturally without needing cleanup jobs or background maintenance logic.

---

## Consequences

### Positive

* Very fast session reads/writes, supporting low-latency webhook responses
* Automatic session expiry via TTL (no cleanup jobs required)
* No extra infrastructure since Redis is already part of the system
* Easy to mock in tests using `fakeredis`

### Negative

* Session state is not durable by default (in-memory nature of Redis)
* Risk of data loss on Redis restart if persistence is not configured

**Mitigation:**
Enable Redis persistence (`appendonly yes`) to reduce risk of session loss on restarts.

---

## Alternatives Considered

### PostgreSQL session table

More durable, but too slow for the latency requirements of real-time WhatsApp message handling.

### In-process memory (dict-based storage)

Not viable because the system runs across multiple workers. State would not be shared reliably between processes.

---
