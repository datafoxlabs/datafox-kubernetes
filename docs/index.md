# Datafox Kubernetes — Documentation Map

Status: architecture documented; implementation pending  
Last reviewed: 2026-10-30

## Project knowledge

- [README](../README.md) — repository purpose and approved integration boundaries.
- [Architecture Map](../ARCHITECTURE.md) — responsibilities, invariants, repository locations and implementation status.
- [Kubernetes Metadata & Release Integration Design](architecture.md) — source-backed, multi-language architecture and four decisions.
- [Implementation, Rollout Safety and Verification](implementation-and-verification.md) — reference configuration, installation gates, canary/rollback and 28 acceptance scenarios.

## RepoFoundry Engineering Lifecycle

- [Agent guidance](../AGENTS.md) and [portable agent entry](agent-guides/README.md).
- [Research](RESEARCH.md), [Decisions](DECISIONS.md), [Design Docs](design-docs/index.md).
- [Execution Plans](PLANS.md), [Bugfixes](BUGFIXES.md), [Technical Debt](exec-plans/tech-debt-tracker.md).

## Engineering Controls

- [Quality Score](QUALITY_SCORE.md) — current assessment unknown until tests are run.
- [Reliability](RELIABILITY.md) — operational requirements and evidence gaps.
- [Security](SECURITY.md) — trust boundaries and controls to verify.
- Managed Engineering Specs: [index](agent-guides/managed/index.md), manifest `docs/.engineering/specs.json` and lock `docs/.engineering/specs.lock.json`.

## Maintaining this documentation

The detailed architecture and implementation guide remain the source for the Kubernetes integration design. Update the map when implementation paths exist. Record durable decisions through the RepoFoundry decision workflow only with explicit owner approval. Never turn examples or planned test cases into claims of validated production behavior.

Project-specific build commands, accountable owners, and production deployment policies remain **BOOTSTRAP_TODO** until established and verified.
