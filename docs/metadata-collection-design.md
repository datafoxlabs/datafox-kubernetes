# Datafox Metadata Collection Design — 元数据采集与补全设计

> **状态：Architecture Proposal，未实施、未完成 E2E。** 本文是 [DD-001](design-docs/dd-001_kubernetes-metadata-release-integration/DESIGN.md) 系统架构下的专题设计，不单独注册 Design Package。属性 Key、Type、Stability 与 Datafox 语义约束以[统一标签规范](unified-tagging-convention.md)为准；本文只说明**如何获得属性**，不重新定义属性。

## 1. 目标与职责边界

Datafox 的默认策略是 **Operator 优先提供应用和 Pod/Workload 基础元数据，Collector 按需补全缺失的可信基础设施信息**。不 Fork Operator、Collector 或 SDK，不在 Java Agent 中增加 Kubernetes API Detector，不要求每个服务提供全部基础设施属性。

| 组件 | 负责的事实 | 不负责的事情 |
| --- | --- | --- |
| 应用 SDK / Agent | 最终应用 Resource、Instrumentation 请求属性、进程级实例身份 | 不需要为 Datafox 自研 Kubernetes API 访问 |
| OpenTelemetry Operator | 在 Pod CREATE 时注入 Agent/SDK 配置，提供可推导的 Pod、Container、Workload 元数据 | 不自动发现全部云元数据、Pod IP、运行时 Image Digest 或 Release Event |
| Collector | 可信 Pod 关联、Kubernetes API/容器元数据补全、必要的集群与云属性 | 不覆盖明确的应用服务身份，不以 Pod UID/IP 认证 Tenant |
| CI/CD / 部署配置 | 环境、制品版本、可选 Cell 与独立的发布事件 | 不从 Pod 镜像标签反推已经成功的 Deployment |
| Datafox Backend | 已认证 Tenant、数据驻留与 Release/Service 关联 | 不信任客户端自报的 Tenant、Pod UID/IP 作为授权证据 |

“Operator 可注入”不等于“自动发现”。下文区分：

- **自动生成**：Operator 从 Pod/Namespace/OwnerReferences 等已知对象生成。
- **条件生成**：必须启用 Operator 选项或满足特定 Workload/容器条件。
- **显式透传**：应用、CI/CD 或部署平台已经知道值，Operator 只负责注入。
- **Collector 补全**：根据可信 Pod 关联、Kubernetes API 或已启用的处理器增加属性；不是所有 Collector 都自动具备这些能力。

## 2. Operator 默认能够提供的属性

以下依据已研究的 [Operator 固定源码](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go)。这是源码能力对照，**不是**已锁定的 Datafox 生产兼容矩阵。

| Attribute | 采集机制 | 前提或限制 |
| --- | --- | --- |
| `service.name` | 自动推导或显式配置 | Pod Annotation、Label、Workload；可能额外注入 `OTEL_SERVICE_NAME` |
| `service.namespace` | 自动推导或显式配置 | Annotation、Kubernetes Namespace；应优先保留用户明确业务命名空间 |
| `service.version` | 自动推导或显式配置 | Annotation、可选 Label、镜像版本回退；不保证与 CI/CD Release Event 一致 |
| `service.instance.id` | 自动生成或显式配置 | 默认 Namespace/Pod/Container 级，无法保证同容器多个独立 SDK 进程唯一 |
| `k8s.namespace.name` | 自动生成 | Namespace |
| `k8s.pod.name` | 自动生成 | Downward API `metadata.name` |
| `k8s.pod.uid` | 条件生成 | `resource.addK8sUIDAttributes`，Downward API `metadata.uid` |
| `k8s.node.name` | 自动生成 | Downward API `spec.nodeName` |
| `k8s.container.name` | 自动生成 | 被注入的目标容器 |
| `k8s.deployment.name`、`k8s.replicaset.name` | 条件生成 | 对应 Pod OwnerReferences 与必要 API 查询 |
| `k8s.statefulset.name`、`k8s.daemonset.name` | 条件生成 | 仅实际对应 Workload |
| `k8s.job.name`、`k8s.cronjob.name` | 条件生成 | 仅实际对应 Job/CronJob |

`deployment.environment.name`、`cloud.region`、`datafox.unit.id` 等可由已知的部署配置或 Resource Annotation **显式传入**，但 Operator 不因此具有环境、云地域或 Cell 的自动发现能力。

**服务名冲突：** 固定 Operator 版本在容器缺少 `OTEL_SERVICE_NAME` 时可能根据 Pod Label/Annotation 另行注入该变量，即使 `OTEL_RESOURCE_ATTRIBUTES` 已显式包含 `service.name`。SDK 的 `OTEL_SERVICE_NAME` 优先级更高。受管理发布须在 CI 检查两种变量与目标业务服务名的一致性，并以真实 OTLP 验证最终值。

## 3. Collector 建议补全的属性

Collector 的 `k8sattributes` 只在正确配置了 `extract.metadata`、`pod_association`、RBAC 和可信入口后，才能可靠补全相应属性。**“推荐由 Collector 补全”不等于“必须通过 Collector 获取”。**

| Attribute | 推荐采集机制 | 前提或限制 |
| --- | --- | --- |
| `k8s.pod.ip` | `k8sattributes` | Pod 关联成功且显式启用元数据提取；也可通过 `status.podIP` Downward API 注入 |
| `k8s.cluster.name` | Collector 可信配置 | 不从 Pod IP 猜测集群 |
| `k8s.cluster.uid` | `k8sattributes` / Kubernetes API | 读取 `kube-system` Namespace UID，需要相应 RBAC |
| `k8s.node.uid` | `k8sattributes` / Kubernetes API | 需要 Node 查询权限 |
| `k8s.service.name`、`k8s.service.uid` | Kubernetes Service 元数据关联 | 需验证具体 Collector 版本是否支持、如何关联以及 Service 多对多关系 |
| `container.id` | Collector / 运行时 | 需要可信容器信息 |
| `container.image.name` | `k8sattributes` / 容器元数据 | 多容器 Pod 需明确 `k8s.container.name` 或 `container.id` |
| `container.image.tags` | 容器镜像元数据 | 旧版本可能输出 `container.image.tag`；必须核对字段与类型 |
| `container.image.repo_digests` | 容器元数据 | 依赖 CRI/Kubernetes 是否提供 Digest，不能保证总有值 |
| `cloud.provider`、`cloud.region`、`cloud.account.id` | Cloud Detector / 可信配置 | `k8sattributes` 不自动等同云元数据 Detector |
| `host.id`、`host.name`、`host.ip` | Host Detector / 基础设施采集 | 主机 Resource 与应用 Pod Resource 不能无条件混用 |

对于已经由 Operator 正确提供的 `k8s.namespace.name`、`k8s.pod.name`、`k8s.deployment.name` 等，Collector 可以核验或补充缺失值，但**不需要为了这些字段强制重复提取**。缺失元数据时保留原始 OTLP，不推导未经证实的身份。

源码依据：[Collector k8sattributes README（研究基线）](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md)。

## 4. Pod Association 与可信边界

推荐在靠近业务 Pod 的**可信同集群 Collector** 中按 Pod UID、Pod IP 的顺序尝试关联；连接 IP 仅在可证明是业务 Pod 直连、没有代理且作用域受限时启用回退。跨集群或共享 Gateway 不得将未经认证的 Resource Pod UID/IP 或上游 Collector 连接 IP 当作权威 Pod 身份。

- Pod UID 可能由客户端自行声明，**不是认证凭据**。
- Pod IP 会复用，也可能属于代理、Sidecar 或 HostNetwork；不能据此合并历史 Pod。
- 容器镜像元数据需要明确具体 Container，否则多容器 Pod 可能补错镜像。
- Collector 不覆盖用户的 `service.name`、`service.version` 或 `service.instance.id`。
- Tenant 授权、跨 Region/Cell 的数据驻留与部署关系由 Backend 的可信接入上下文决定。

完整的 Collector 配置示例、`extract.metadata`、RBAC 和 Pod Association 负面场景由[实施与验证手册](implementation-and-verification.md)维护，不在本文复制第二套 YAML。

## 5. Datafox 首期落地与验收

**P0 推荐：** SDK/Operator 负责 `service.*`、`k8s.namespace.name`、`k8s.pod.name`、`k8s.node.name` 和实际 Workload 属性；按需启用 `k8s.pod.uid`；Collector 补全 `k8s.pod.ip`、可信 Cluster 信息及必要的 Container Image。CI/CD 提供 Release 版本、Environment 和可选 Cell，Backend 提供可信 Tenant。

**不强制：** Node UID、全部容器 Digest、Host IP、云账号以及没有业务需求的 Cell。不能仅为“标签完整”引入更多 Informer、RBAC、Detector 或全量 Kubernetes Label 采集。

**验证合同（全部待执行）：** 对比无 Collector / 启用 Collector 时的实际 OTLP Resource；检查多容器、Pod UID 开关、显式 Resource 冲突、Cloud/Host Detector 缺失、Kubernetes API 不可达、代理与跨 Tenant 伪造 UID/IP。以[现有 T01–T44](implementation-and-verification.md)和[Tag/Inst/Domain 合同](unified-tagging-convention.md)为准，不重复分配测试 ID。

本文是对上游能力的设计分析，尚未证明 Datafox 在生产版本上具有全部列出的采集能力。正式落地前锁定 Operator、Collector、SDK 与云/Host Detector 版本，执行 E2E 并记录真实输出。
