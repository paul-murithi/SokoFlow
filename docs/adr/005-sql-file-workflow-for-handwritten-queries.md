# ADR 005: SQL File Workflow for Handwritten Queries

**Date:** 2026-07-13
**Status:** Accepted

---

## Context

SokoFlow already uses SQLAlchemy as the ORM layer for mapped classes, relationships, sessions, transactions, and Alembic migrations.

As the codebase has grown, some repository queries became clearer as handwritten SQL than as chained SQLAlchemy expressions. I needed a way to improve readability and maintainability for those queries without changing the overall architecture or introducing a new query system.

The challenge was to make SQL easier to manage while keeping the existing ORM-based design intact.

---

## Decision

We will keep **SQLAlchemy** for:

- ORM models
- mapped classes
- relationships
- session management
- transactions
- dependency injection
- Alembic migrations
- Pydantic integration

We will use **SQL files** only for handwritten repository queries where plain SQL is clearer.

Each query lives in its own file under `app/sql/`, and repositories load those files through the cached `load_sql(...)` helper before executing them with SQLAlchemy `text(...)` and named parameters.

---

## Rationale

This approach gives me the readability benefits of handwritten SQL without disrupting the parts of the system that SQLAlchemy already handles well.

It preserves the current architecture, keeps services free of SQL details, and avoids introducing extra abstractions such as a query builder, parser, DSL, or SQL management library.

The filesystem becomes the source of organization for handwritten queries, which makes the intent obvious to contributors and keeps each query easy to find.

---

## Consequences

### Positive

- SQL stays easy to read for reporting and join-heavy queries
- SQLAlchemy remains the ORM and migration system
- Repositories remain the execution boundary for database reads
- Query files are cached after first load, so they are cheap to reuse
- The codebase remains familiar to contributors already used to SQLAlchemy

### Negative

- Query files must be kept in sync with repository call sites
- Contributors need to know when to prefer ORM queries versus SQL files
- There is a small amount of extra structure to maintain under `app/sql/`

---

## Alternatives Considered

### Keep all queries in SQLAlchemy expressions

This would avoid new files, but some queries are clearer as plain SQL and become harder to read when composed through ORM syntax.

### Introduce a query builder or SQL management library

Rejected because it would add unnecessary abstraction and move the project away from the current boring, explicit style.

### Replace SQLAlchemy entirely

Rejected because SQLAlchemy is already working well for the ORM and migration responsibilities, and replacing it would be a rewrite rather than an incremental evolution.
