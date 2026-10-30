# Datafox Kubernetes Integration

OpenTelemetry-based Kubernetes metadata and release integration for Datafox, designed for **Java, Python, Node.js, .NET, Go and SDK-instrumented services**.

> **Status: architecture and implementation design only.** No Operator, Collector, Java image or Backend release API has been deployed or verified by this repository yet.

## Architecture decisions

| Decision | Contract |
| --- | --- |
| Version source | Standard `app.kubernetes.io/version` Pod Label; `resource.opentelemetry.io/service.version` Annotation for override; explicit `OTEL_RESOURCE_ATTRIBUTES` wins |
| Injection | Reuse OpenTelemetry Operator; opt-in per workload; no Datafox admission webhook |
| Collector | Enrich Kubernetes infrastructure attributes; never rewrite `service.name` / `service.version` |
| Release events | CI/CD actively reports deployment lifecycle to Datafox Backend |

## Documentation

- **[Architecture and design decisions (中文)](docs/architecture.md)** — The problem, system roles, data flows, language integration, release identity, failure domains and upstream source evidence.
- **[Implementation, rollout safety and verification (中文)](docs/implementation-and-verification.md)** — Operator Instrumentation, Collector configuration, Java image requirements, multi-language usage, CI/CD API, canary/rollback and 28 acceptance tests.

### Recommended reading path

1. Read the architecture to understand **why** service identity belongs to the SDK and Kubernetes topology belongs to Collector.
2. Follow the implementation guide in a **disposable Kubernetes test cluster**, not in production.
3. Lock actual Operator / Collector releases, verify the Pod mutation fail-open policy and test Java Agent startup.
4. Complete the E2E matrix before expanding from canary to other production workloads.

## Scope

This repository will own Kubernetes manifests/Helm conventions, integration examples, packaging of a Datafox Java Agent injection image, validation tests and operational documentation. The Java runtime remains in `datafox-java-agent`. Datafox Backend owns the release event API and analytics.

No custom Operator fork, Java Kubernetes detector, mandatory namespace-wide injection, privileged Go eBPF auto-instrumentation or automatic production rollout is part of v1.

## Upstream

- [OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator)
- [OpenTelemetry Collector Contrib / k8sattributes](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/k8sattributesprocessor)
- [OpenTelemetry Java Instrumentation](https://github.com/open-telemetry/opentelemetry-java-instrumentation)

See the documentation for **fixed upstream source snapshots** and unverified integration assumptions.
