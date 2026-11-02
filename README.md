# Datafox Kubernetes Integration

Datafox 的 Kubernetes 可观测性集成项目。以 **OpenTelemetry 标准** 为跨语言遥测契约，计划复用上游 Operator 进行工作负载级自动注入、使用 Collector 补充 Kubernetes 基础设施属性，并由 CI/CD 向 Datafox Backend 上报发布事件。

> **项目状态：架构与实施方案（Proposal）。** 目前仓库已包含 RepoFoundry 工程 Harness，但尚未实现、安装或验证 Operator/Collector 集成、Java Agent 注入镜像、多语言 E2E 或 Backend Release API。本文和示例配置不是生产就绪承诺。

## 从哪里开始

| 目的 | 权威文档 |
| --- | --- |
| 定义应用身份、环境、版本与 Datafox 接入条件 | [统一语义合同](docs/unified-tagging-convention.md) |
| 查阅属性 Key、类型、稳定性、作用域及来源 | [属性登记表](docs/attribute-registry.md) |
| Kubernetes Label/Annotation 如何转成 Resource、冲突时怎么办 | [Kubernetes 资源映射](docs/kubernetes-resource-mapping.md) |
| Tag/Inst/Domain 语义合同测试 | [语义验收测试](docs/tagging-contract-tests.md) |
| 理解控制面、数据面、Operator/Collector 分工与 Release Tracking | [系统架构设计](docs/architecture.md) |
| 定义可信 Tenant、云 Region、可选 Cell 的作用域和隔离边界 | [部署拓扑与隔离模型](docs/deployment-topology-and-isolation.md) |
| 查看示例配置、发布前预检、Canary/回滚及待执行测试 | [实施与验证手册](docs/implementation-and-verification.md) |

**完整导航、文档职责和维护规则：** [docs/index.md](docs/index.md)。架构速览见 [ARCHITECTURE.md](ARCHITECTURE.md)；工程 Agent 从 [AGENTS.md](AGENTS.md) 开始。

## 核心约束

- **应用身份**：各语言 SDK/Agent 生成 OTel Resource；Kubernetes Label 只是推荐输入之一，客户现有 Label 不强制改名。最终 `service.name`、`service.version` 等必须按实际 Operator/SDK 行为验证。
- **自动注入**：复用 OpenTelemetry Operator，以业务工作负载 Opt-in；不增加 Datafox 自定义 Admission Webhook。注入失败可能造成业务启动失败或遥测缺失，必须先 Canary。
- **基础设施补全**：Collector 补充 `k8s.*` 等已验证属性，不重写 `service.*`。自报 Pod UID/IP 不代表可信身份，不能用作 Tenant 授权。
- **发布事实**：CI/CD 上报 Release/Deployment Event；一次制品构建、一次部署尝试与一个运行中的 Pod 具有不同身份和生命周期。
- **拓扑与权限**：Tenant 来自可信认证；Region 使用 OTel `cloud.region`；仅存在实际单元化业务需求时启用可选 `datafox.unit.id`。

以上为**设计契约**，不是已实施功能。D1–D4 是产品层已讨论的设计决策编号，**不是**已注册或批准的 RepoFoundry ADR。

## 工程边界与验证

本仓库计划维护 Kubernetes 配置、Helm/部署约定、Java 注入镜像封装和集成测试；Java Agent 的运行时实现在独立的 `datafox-java-agent` 项目，发布 API 与分析能力由 Datafox Backend 负责。

RepoFoundry Harness/Spec 校验与 **Kubernetes 运行时验证** 是不同的门禁。目前 T01–T44 及 Tag/Topo/Inst/Domain 合同仍为待执行用例。任何正式部署前必须锁定 Operator/Collector 和各语言组件版本，并取得真实 Pod CREATE、OTLP Resource、业务性能和回滚验证证据。

参考上游：[OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator) · [Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib) · [Java Instrumentation](https://github.com/open-telemetry/opentelemetry-java-instrumentation)。
