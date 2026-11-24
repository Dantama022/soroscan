# Architecture Decision Records — moved

The architecture decisions previously recorded in this file have been
**consolidated** into the canonical ADR directory at
[`docs/adrs/`](../adrs/README.md). See the [ADR index](../adrs/README.md) for the
complete, authoritative list.

This file previously contained six inline decisions ("ADR 001"–"ADR 006"). They
now live as numbered ADRs in `docs/adrs/`, mapped as follows:

| Former section in this file | Canonical ADR |
| --- | --- |
| ADR 001: Soroban RPC vs Horizon-only ingestion | [ADR 0001](../adrs/0001-event-ingestion-architecture.md) |
| ADR 002: PostgreSQL for event storage | [ADR 0003](../adrs/0003-database-schema-rationale.md) |
| ADR 003: Strawberry GraphQL | [ADR 0007](../adrs/0007-strawberry-graphql.md) |
| ADR 004: Exponential backoff for webhook retries | [ADR 0004](../adrs/0004-webhook-delivery-system.md) |
| ADR 005: Redis as shared cache and channel layer | [ADR 0008](../adrs/0008-redis-cache-and-channels.md) |
| ADR 006: Django + Next.js application stack | [ADR 0006](../adrs/0006-django-backend.md) |

This file is retained only as a redirect. Do not edit decisions here — open a PR
against [`docs/adrs/`](../adrs/README.md) instead. See issue #1685 for the full
consolidation rationale.
