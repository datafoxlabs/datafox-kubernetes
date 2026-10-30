# Datafox Kubernetes Integration

Datafox 的 Kubernetes 集成项目，面向 Java、Python、Node.js、.NET、Go 等 OpenTelemetry 应用。

本项目采用 **OpenTelemetry Operator** 注入应用侧 Resource 与自动埋点配置，使用 **OpenTelemetry Collector** 补充基础设施元数据，发布事件由 CI/CD 主动上报 Datafox Backend。

## 工程原则

- 运行时复用 OpenTelemetry 官方组件，不 Fork Operator 或 Collector。
- 版本优先使用标准 Pod Label `app.kubernetes.io/version`，允许 `resource.opentelemetry.io/service.version` Annotation 和用户显式配置覆盖。
- Collector 只补充 Kubernetes 基础设施属性，不改写 `service.name` 或 `service.version`。
- 仅对显式选择的工作负载启用 Pod Mutation，并通过 Canary、回滚和失败注入验证业务安全。
- 当前仓库处于设计阶段，不表示已完成部署、兼容性验证或正式发布。

完整架构、部署步骤和验收规范将通过仓库文档评审逐步维护。
