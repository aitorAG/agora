# Project Working Priorities

These priorities apply to every change in this repository unless explicitly overridden by the user.

## Core Objectives

1. High efficiency and execution speed.
2. Solid, modular software that is production-ready and easy to iterate on.

## Engineering Rules Derived From Objectives

- Prefer low-latency paths and avoid unnecessary work (calls, I/O, allocations, model invocations).
- Optimize for end-to-end response time, not only local micro-optimizations.
- Keep architecture modular: clear boundaries, small components, explicit interfaces.
- Favor changes that improve maintainability and safe iteration (tests, backward-compatible defaults, feature flags when useful).
- Avoid quick fixes that increase coupling or technical debt without a clear tradeoff.
- For performance-sensitive flows, include basic measurement hooks/logs or tests to prevent regressions.

## Definition of Done (Default)

- Change keeps or improves runtime performance.
- Change keeps or improves modularity and production robustness.
- Relevant tests pass; new tests are added when behavior/performance paths change.
