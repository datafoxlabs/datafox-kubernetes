---
type: synthesis-note
status: proposed
created: 2026-10-31
updated: 2026-11-02
as_of: 2026-11-02
review_after: 2027-01-31
---

# Datafox Unified Tagging Convention — 统一遥测语义合同（草案）

> **状态：Proposal v0.2，待架构评审。** 本文定义 Datafox 跨语言遥测的服务身份、数据归属、接入条件和查询语义。它不重新定义 OTel Attribute Key、Type、Stability，也不宣称 Operator/Collector/Backend 已实现这些策略；D1–D4 仍是产品设计决策编号，不是已批准的 RepoFoundry ADR。

**规范来源：** [OpenTelemetry Specification](https://github.com/open-telemetry/opentelemetry-specification/tree/main/specification) 定义 SDK/Resource/信号行为；[OpenTelemetry Semantic Conventions](https://github.com/open-telemetry/semantic-conventions) 定义字段名、类型与语义。Datafox 在这些标准之上规定**产品接入和发布关联的条件**，不能覆盖或另造上游字段含义。Datadog Unified Service Tagging 是产品体验对照，不作为 OTLP 协议字段来源。

**单一事实来源：** [Attribute Registry](attribute-registry.md) 是所有被引用字段的唯一清单；[Kubernetes Resource Mapping](kubernetes-resource-mapping.md) 说明 Label/Annotation/SDK 输入与冲突；[Tagging Contract Tests](tagging-contract-tests.md) 持有 Tag/Inst/Domain 测试合同；[Deployment Topology & Isolation](deployment-topology-and-isolation.md) 持有可信 Tenant、Region、Cell 的详细定义；[Implementation & Verification](implementation-and-verification.md) 持有部署、风险预检和 E2E 记录。

## 1. 范围、术语与规范约束

Datafox 的“统一标签”指跨 Traces、Metrics、Logs 使用标准 OTel Resource 识别**被观测业务服务**，并通过可信部署与发布事实构建关联。它不表示每个 Span 或 Metric 数据点都复制全部 Resource，也不表示 Kubernetes Label、应用 Resource、请求属性和 Release Event 在同一存储模型中。

| 数据层 | 承载事实 | 约束 |
| --- | --- | --- |
| OTel Resource | 应用逻辑服务、环境、运行实例、可确定的基础设施位置 | 跨应用信号保持相同身份语义；不因连接、请求或发布操作改变逻辑服务 ID |
| Span / Log Record / Metric 数据点属性 | 具体请求、网络连接、日志与指标维度 | 采用相应官方 SemConv；不得把请求地址当作全局服务实例身份 |
| Kubernetes Label / Annotation | 业务/部署平台提供的元数据与配置输入 | 可由已有 Operator/Helm/CI 转成 Resource，**不要求企业改名**；Pod Label 也不是权限凭据 |
| Datafox Release / Deployment Event | 构建制品、一次部署尝试、状态与时间证据 | 通过 CI/CD 独立上报，不从当前 Pod Image Tag 或 Trace 时间反向伪造 |
| Datafox Backend 可信上下文 | 已认证的平台 Tenant、授权、数据驻留路由 | **不是可由 OTLP Resource 或任意 Pod Label 决定的属性** |

规范性用语：本文中的“必须/不得”是 **Datafox 当前提案对启用相应产品能力的要求**，不是 OpenTelemetry 对所有 SDK 的新要求；“推荐”允许按场景不启用；“可选”不得成为普通接入的隐含门槛。`P0/P1/P2` 表示设计和交付顺序，**不等于** OTel `Required/Recommended/Opt-In` 或 `Stable/Development`。上游 Requirement Level 由所采用的 Entity/Signal SemConv 决定，详见[官方说明](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/general/attribute-requirement-level.md)。

## 2. 身份与部署语义

### 2.1 逻辑服务、实例和部署是不同身份

Datafox Backend 的逻辑服务键是 **`(trusted_tenant_id, service.namespace, service.name)`**。其中 Tenant 来自 Backend 已鉴权的接入上下文，而非自报 Resource；`service.namespace` 遵守 OTel 可缺失的语义，未指定时是有效的空命名空间。对需要跨 Kubernetes Namespace 或环境稳定关联的业务，推荐显式配置稳定的逻辑命名空间，**不得**自动用 `k8s.namespace.name` 替代。

`deployment.environment.name` 表示部署环境，`service.version` 表示软件制品版本。它们是查询和发布比较维度，**不是**同一服务在不同环境/版本下自动创建的新逻辑服务。一次 Release 可以在多个环境或 Cell 发布；每次发布尝试有独立的 `deployment_id`。回滚恢复旧制品时仍建立新的 Deployment，不能改写历史部署终态。

`service.instance.id` 是并存服务实例的标识；Pod UID、Container ID 和 IP 不自动等于独立 SDK/进程实例。上游 Operator 的容器级默认标识不能保证同一容器内多个独立 SDK 进程唯一，必须由真实进程配置并核对最终 OTLP。Collector 若无法唯一确定真正的应用实例，不得仅凭 Pod UID 或连接 IP 推导它。所有字段的类型与稳定性在[Attribute Registry](attribute-registry.md)中唯一维护。

### 2.2 运行位置、网络地址与租户权限

Kubernetes 运行位置优先保留可验证的 Cluster、Namespace、Workload、Pod、Container 事实。Pod UID 可用于经过信任边界验证后的 Pod 关联；Pod IP 可能复用、变化或因 HostNetwork、Sidecar、Gateway 而被错误观察，不是身份认证或服务实例主键。双栈时 `k8s.pod.ip` 仍遵守单值来源，不能把地址数组序列化为字符串。`host.ip` 是主机的 IP 数组，两者不能互相转换。

`server.address`、`server.port`、`client.address`、`network.local.address`、`network.peer.address`、`url.full`、`dns.question.name` 属于其各自的请求或网络语义，**不构成服务的 Resource 域名或实例 IP**。HTTP Host/Forwarded Header 可能被伪造；不进行强制反向 DNS，不用 Kubernetes Service FQDN 或同名域名直接合并跨 Tenant 服务。URL 敏感信息遵守上游清理规范。详见[实例与域名验收用例](tagging-contract-tests.md)。

Kubernetes Service DNS 常见形式为 `<service>.<namespace>.svc.<cluster-domain>`，但 Cluster Domain 不保证为 `cluster.local`。普通 Service、Headless Service、Ingress 与 Gateway 的路由关系不同；同一服务可能暴露多个访问域名，同一域名也可能对应不同业务。不得从 Pod Name 或 Service 名猜测 FQDN 并写入全局 Resource。若未来需要服务访问域名资产目录，应由 Backend 基于可信路由配置、来源和观察时间单独构建 Service Endpoint / Route 关系；P0 不建设域名注册中心或实时 DNS 探测器。

`url.full` 可能含账号、Token 与敏感查询参数，`dns.question.name` 可包含内部服务信息；默认指标按稳定的 `http.route` 等低基数维度组织，避免使用任意 URL/Host/DNS 值分组。仅在明确需求下按白名单采集 `http.request.header.<key>`（例如 `host`），不把客户端可控制的 Header 或网络地址作为服务身份、数据驻留、Tenant 权限或权威路由证据。Java Agent 不增加私有网络探测器、反向 DNS、周期网卡扫描或应用热路径的 Kubernetes API 调用。

### 2.3 Tenant、Cloud Region 与可选 Cell

已认证的平台 Tenant 是读写权限和数据驻留的边界。被观测 SaaS 应用的**业务客户租户**可能随请求变化，不应被自动写成共享进程的全局 Resource；来自 OTLP、Pod Label 或 `cloud.region` 的值不能提升平台权限。

`cloud.region` 与 `cloud.availability_zone` 表示云厂商原生物理位置；Kubernetes Cluster 是另一部署维度；**Cell / Unit 是可选的一等业务部署维度**，仅在企业确有稳定的流量或故障隔离单元时启用拟议的 `datafox.unit.id`。普通服务不需要 `datafox.*` 属性，不强制建设 Cell 注册中心或跨云逻辑 Region。Cell 的身份作用域、Cluster 多对多关系及发布目标约束以[拓扑规范](deployment-topology-and-isolation.md)为准。

## 3. Datafox 接入合同

下表定义 **Datafox 功能门槛**，不是 OTel SemConv Attribute Requirement Level。表中的“必须”仅在所述条件成立时适用。

| 能力或事实 | 普通 OTLP 接入 | 受管理 Release Tracking | 受管理 Operator 自动注入 |
| --- | --- | --- | --- |
| 明确业务 `service.name` | 接收符合 SDK 缺省语义的值；`unknown_service*` 保留未识别状态 | 必须明确业务身份；缺失或不明确时发布前停止受管理关联 | 必须检查最终 `OTEL_SERVICE_NAME` 与 Resource 来源是否冲突，不静默选择错误业务名 |
| `service.namespace` | 可缺失；不自动等于 K8s Namespace | 跨环境关联需要稳定命名空间时显式设置；否则保留缺失语义 | 不覆盖用户明确配置 |
| `service.version` | 可以缺失；不伪造 Release | 启用版本级发布关联时必须有可追溯值并与 Release Event 一致 | 仅在同时启用发布关联时作为必要条件；其他注入不强制版本 |
| `deployment.environment.name` | 可以缺失 | 按环境发布与查询关联时必须明确 | 注入本身不强制所有 Pod 提供环境 |
| `service.instance.id` | 遵守上游服务实例语义 | 不得把同一版本的不同实例当不同逻辑服务 | 多容器/多进程时实际核对唯一性，默认 Operator 值不保证同容器多 SDK 进程唯一 |
| `k8s.*` 与 `cloud.*` | 非 K8s/非云场景不适用 | 需要 Pod、Cluster、Region 定位时使用经验证的关联证据 | 无法关联 Pod 时保留原始遥测，不生成伪造位置 |
| `datafox.unit.id` | 默认缺失 | **仅 Cell 功能明确启用时**使用与 Event 相同的 Unit | 无 Cell 工作负载不添加或合成 `default` / `unknown` |

受管理发布的失败属于 **CI/CD 配置预检**，不是对所有普通 OTLP 数据的接收拒绝。CI 应检查最终渲染 Pod Template、`OTEL_SERVICE_NAME`、`OTEL_RESOURCE_ATTRIBUTES`、Pod Annotation、Label、`envFrom` 与 `valueFrom`。来源无法确定或明确冲突时停止相应受管理发布；不自行在集群增加新的业务阻断 Webhook。与 Kubernetes Label/Annotation 和 Env 的详细顺序及故障示例见[Kubernetes Mapping](kubernetes-resource-mapping.md)。

## 4. 跨信号关联与查询约束

Datafox 的查询首先在可信 Tenant 下定位 `service.namespace + service.name`，随后按环境、版本、Cloud Region、可选 Cell 下钻至 Cluster/Workload/Pod。**Environment、Version、Region、Cell 不改变逻辑服务身份**；跨 Region/Cell 的单条 Trace 不应被强制贴到一个 Cell。

在应用 SDK Traces、Metrics、Logs 都已启用且能够提供一致 Resource 的情况下，它们应以相同服务身份关联。Metrics 仍保留各数据点的语义，**不得**把 `service.instance.id` 或 Pod UID 无差别加入每一项聚合指标的默认分组；基础设施 Node/Pod/Container Metrics 不需要冒用某个应用 `service.version`。其他日志源必须有可信 Container/Workload 关联才能补全应用身份，不能仅凭 Node IP 推断。

Release Tracking 从真实 CI/CD Event 获取部署动作与终态，用受管理版本、环境、部署目标及时间证据建立关联；信息不足则保留候选关系，不覆盖 SDK 的服务身份或历史发布事实。查询视图和 API 详细模型由[系统架构](architecture.md)与[实施手册](implementation-and-verification.md)维护。

## 5. 兼容与演进原则

1. OTel Specification 和 Semantic Conventions 定义属性原始语义；SDK、Operator、Collector **锁定版本**决定真实实现与优先级；Datafox 的 CI 和 Backend 只实施已声明的产品条件。
2. 不自动读取 `DD_ENV`、`DD_SERVICE`、`DD_VERSION` 并覆盖 OTel Resource。将来支持 Datadog 迁移，应作为单独兼容特性明确配置、测试与记录来源。
3. `deployment.environment` 已弃用，`container.image.tag` 与当前 `container.image.tags` 的类型不同。历史数据转换需独立审批与兼容测试，不能静默重写。
4. 新的 `datafox.*` 属性须证明无法由现有 OTel 字段表达，并定义 Key、类型、使用作用域、权威来源、敏感性、索引基数、兼容与迁移策略；优先维护在[Registry](attribute-registry.md)的自定义区域。现阶段只提议可选的 `datafox.unit.id`。
5. 不在全局 Resource 中批量写入任意 Kubernetes Label、Annotation、Token、Secret、客户个人信息或请求级 IP/域名；扩展应由真实产品需求驱动。
6. 稳定性为上游属性的规范成熟度，不等于 Datafox 已实施或通过跨版本验证。记录所依据的 SemConv 与项目组件版本，升级时重新验证对应字段类型与输出。

## 6. 阅读路线与验收状态

- 需要核对 Attribute Key、类型、Scope、上游稳定性或标准与自定义边界：读[Attribute Registry](attribute-registry.md)。
- 需要配置 Kubernetes Pod Label、Resource Annotation、Operator、Env 和冲突处理：读[Kubernetes Resource Mapping](kubernetes-resource-mapping.md)。
- 需要确认 Tenant、Region、Cell、逻辑服务与部署目标关系：读[Deployment Topology](deployment-topology-and-isolation.md)。
- 需要 Tag-01–15、Inst-01–08、Domain-01–09 的完整输入/断言：读[Tagging Contract Tests](tagging-contract-tests.md)；Topo-01–12 保留在拓扑规范中；T01–T44 仍在[实施手册](implementation-and-verification.md)。
- 需要 Operator/Collector/Backend 实际安装、发布前兼容性检查与 Rollout/回滚：读[Implementation & Verification](implementation-and-verification.md)。

**验证状态：** 这是对现有提案的组织结构重构。未执行 Kubernetes、Operator、Collector、任一语言 SDK 或 Backend E2E；现有测试编号仅表示未来的验收合同。DD-001 保持原有 `draft` / 未发布状态；合并 Markdown 或通过 CI 不构成 Design Approval。

## 参考资料

- [OpenTelemetry Resource Specification](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/resource/README.md)
- [OpenTelemetry Resource SDK Specification](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/resource/sdk.md)
- [OpenTelemetry Semantic Conventions — Resource](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/resource/README.md)
- [OpenTelemetry Kubernetes Attributes Mapping](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/non-normative/k8s-attributes.md)
- [Datadog Unified Service Tagging](https://docs.datadoghq.com/getting_started/tagging/unified_service_tagging/) — 仅用于产品体验对比。
