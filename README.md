# Datafox Kubernetes Integration

OpenTelemetry-based Kubernetes metadata and release integration for Datafox, designed for **Java, Python, Node.js, .NET, Go and SDK-instrumented services**.

> **Status: architecture and implementation design only.** No Operator, Collector, Java image or Backend release API has been deployed or verified by this repository yet.

## Tagging standard — review this first

**[Datafox Unified Tagging Convention — OTel-first (中文)](docs/unified-tagging-convention.md)** defines service identity, environment, application version, Kubernetes metadata, cross-signal semantics, and release tagging. It is a **proposed contract**, not an approved ADR or implemented policy. Review it before treating the architecture/implementation examples as normative.

## Tenancy, region, and cell topology

**[Deployment Topology & Isolation Model (中文)](docs/deployment-topology-and-isolation.md)** defines authenticated Datafox tenant isolation, standard OTel cloud/cluster location fields, optional multi-cloud logical regions and business cells, and per-unit deployment tracking. Custom `datafox.region.id` / `datafox.unit.id` attributes are **proposals, not required OTel fields**.

## Architecture decisions

| Decision | Contract |
| --- | --- |
| Version source | Standard Kubernetes app labels are **recommended defaults, not mandatory**. Existing enterprise/cloud labels may be mapped by deployment templates to OTel Resource annotations; explicit SDK/OTEL configuration remains supported and subject to injection compatibility checks |
| Injection | Reuse OpenTelemetry Operator; opt-in per workload; no Datafox admission webhook |
| Collector | Enrich Kubernetes infrastructure attributes; never rewrite `service.name` / `service.version` |
| Release events | CI/CD actively reports deployment lifecycle to Datafox Backend |

## Documentation

- **[Architecture and design decisions (中文)](docs/architecture.md)** — The problem, system roles, data flows, language integration, release identity, failure domains and upstream source evidence.
- **[Implementation, rollout safety and verification (中文)](docs/implementation-and-verification.md)** — Operator Instrumentation, Collector configuration, Java image requirements, multi-language usage, CI/CD API, canary/rollback and 44 planned acceptance tests.

### Recommended reading path

1. Read the architecture to understand **why** service identity belongs to the SDK and Kubernetes topology belongs to Collector.
2. Follow the implementation guide in a **disposable Kubernetes test cluster**, not in production.
3. Lock actual Operator / Collector releases, verify the Pod mutation fail-open policy and test Java Agent startup.
4. Complete the E2E matrix before expanding from canary to other production workloads.

## Scope

This repository will own Kubernetes manifests/Helm conventions, integration examples, packaging of a Datafox Java Agent injection image, validation tests and operational documentation. The Java runtime remains in `datafox-java-agent`. Datafox Backend owns the release event API and analytics.

No custom Operator fork, Java Kubernetes detector, mandatory namespace-wide injection, privileged Go eBPF auto-instrumentation or automatic production rollout is part of v1.

**Pre-deployment safeguards:** The planned CI gate rejects incompatible `OTEL_RESOURCE_ATTRIBUTES.valueFrom`, Java `JAVA_TOOL_OPTIONS.valueFrom`, unresolved or colliding `envFrom` keys in opted-in containers. The Pod Webhook can still match Pods without an injection annotation; admission match scope and fail-open observability coverage require separate validation. Neither safeguard has been implemented or tested yet.

## Upstream

- [OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator)
- [OpenTelemetry Collector Contrib / k8sattributes](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/k8sattributesprocessor)
- [OpenTelemetry Java Instrumentation](https://github.com/open-telemetry/opentelemetry-java-instrumentation)

See the documentation for **fixed upstream source snapshots** and unverified integration assumptions.
