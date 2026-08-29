# SoroScan Architecture Decision Records

Architecture Decision Records (ADRs) document significant technical decisions made for SoroScan.

Each ADR explains the context of a decision, the selected approach, its rationale, alternatives that were considered, and the consequences of adopting it.

ADRs help contributors understand not only how the system is implemented, but why important architecture choices were made.

## ADR Index

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](./adr_001_django_backend.md) | Use Django for the SoroScan backend | Accepted |
| [ADR-002](./adr_002_strawberry_graphql.md) | Use Strawberry GraphQL for the SoroScan GraphQL API | Accepted |

## Creating a New ADR

Use [`adr_template.md`](./adr_template.md) when proposing a new architecture decision.

1. Copy `adr_template.md`.
2. Assign the next available ADR number.
3. Give the file a descriptive lowercase name.
4. Document the context, decision, rationale, alternatives, and consequences.
5. Set the initial status to `Proposed`.
6. Add the new ADR to the table in this file.
7. Submit the ADR for review through the normal pull request process.

An ADR should focus on a significant architectural decision rather than routine implementation details.

## ADR Statuses

Use one of the following statuses:

- **Proposed** — the decision is under discussion and has not yet been accepted.
- **Accepted** — the decision has been approved and should guide implementation.
- **Deprecated** — the decision is no longer recommended but remains relevant for historical context.
- **Superseded** — a newer ADR replaces this decision. Link to the replacement ADR from the superseded record.

Accepted ADRs should not normally be rewritten to describe a different decision. If an architecture choice changes substantially, create a new ADR and mark the previous ADR as superseded.