---
type: synthesis-note
status: proposed
created: 2026-10-31
updated: 2026-11-02
as_of: 2026-11-02
review_after: 2027-01-31
---

# Datafox Unified Tagging Convention — 统一遥测标签规范

> **状态：Proposal v0.2，待架构评审。** 这是一份跨语言、跨信号、跨部署环境的**语义契约**，尚未成为已批准的 RepoFoundry ADR，也没有被任何生产 CI、SDK、Operator、Collector 或 Backend 强制执行。
>
> **规范权威：** OpenTelemetry Semantic Conventions 和 SDK Resource 配置规范。Datadog Unified Service Tagging 仅用于比较产品体验；Datadog 的 `env/service/version` 不作为 Datafox OTLP 属性名。
>
> **阅读顺序：** 先读本规范确定字段和数据所有权，再读 [系统架构](architecture.md) 理解注入/补全/关联，最后读 [实施与验证](implementation-and-verification.md) 的实际配置与测试。
>
> **影响范围：** Datafox Java Agent、其他语言 OTel SDK/Agent、Kubernetes Operator、Collector、APM Backend、Logs/Metrics 接入、CI/CD Release Tracking。
>
> **拓扑与安全补充：** [Deployment Topology & Isolation Model](deployment-topology-and-isolation.md) 按 P0（可信 Tenant 与标准 OTel Region/Cluster）→ P1（可选 `datafox.unit.id`）→ P2（按需研究逻辑 Region 和复杂拓扑）分阶段定义。Tenant 不由 Resource 决定，普通服务不要求 Cell。

## 1. 核心主张：用 OTel Resource 统一服务身份，用平台契约统一查询行为

Datadog 的统一服务标签使用 `env`、`service`、`version` 连接 APM、指标、日志与发布视图。Datafox 保留这一产品目标，但**不创建一组平行的 `datafox.env` / `datafox.service` / `datafox.version`**。所有受支持的 OTel 遥测使用标准 Resource Attribute，保留用户的标准键名和类型，不在 Collector 中把它们改成 Datafox 私有键。

Datadog 的 `service`、`env`、`version` 在 Datafox 中分别对应标准 OTel `service.name`、`deployment.environment.name`、`service.version`；需要逻辑服务分组时使用 `service.namespace`。这些字段的具体类型和使用条件统一在第 3 节定义，此处不再维护第二份属性表。

Datafox 的**逻辑服务身份** 是 `(tenant, service.namespace, service.name)`。`tenant` 由**已鉴权的接入与租户上下文** 决定，**不是** 允许调用者在 OTLP Resource 中自行声称的 `tenant` 属性。`deployment.environment.name` 和 `service.version` 分别是服务的部署维度与软件版本维度，不能作为“创建了一个新逻辑服务”的依据。

OpenTelemetry Service SemConv 要求同一水平扩展服务的 `service.name` 一致；`service.namespace` 可为空但此时同名空间下必须避免服务名冲突。Datafox **推荐** 对需要跨 Namespace/环境关联的服务显式提供稳定的 `service.namespace`。对不需要逻辑命名空间的服务允许省略，并遵循 OTel 的原始含义；不能为了统一格式而虚构一个命名空间。

**与 Datadog 的产品体验对齐，不代表与 Datadog 标签字面兼容。** Datafox 不自动把 `DD_ENV`、`DD_SERVICE` 或 `DD_VERSION` 解释成 OTel Resource。任何未来的 Datadog 迁移映射必须是独立、可测试的兼容性功能。

来源：[Datadog Unified Service Tagging](https://docs.datadoghq.com/getting_started/tagging/unified_service_tagging/)、[OTel Service Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/resource/service/)、[OTel Deployment Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/)。

## 2. 术语和属性归属

“标签”在不同产品中可能指 Kubernetes Label、Metric Label、Span Attribute、Log Attribute 或 OTel Resource Attribute。Datafox 使用下列严格区分：

| 对象 | 数据位置 | 代表什么 | 本规范的做法 |
| --- | --- | --- | --- |
| **Kubernetes Label** | `metadata.labels` | 工作负载/Pod 的可查询部署元信息，受 Kubernetes 标签格式限制 | **输入**，不是最终遥测数据模型 |
| **Kubernetes Annotation** | `metadata.annotations` | 自定义元数据；Operator 的 `resource.opentelemetry.io/*` 可成为 Resource 来源 | **输入**，支持比 Label 更广的版本字符串 |
| **OTel Resource Attribute** | OTLP Resource / SDK Resource | 产生遥测的服务、运行实例和环境 | Datafox **唯一规范的服务标签语义层** |
| **Span / Log Record Attribute** | 单条信号内部 | 某个操作、事件或日志记录的上下文 | 保留 OTel 语义，不逐 Span 重复填充全局身份 |
| **Metric 数据点属性** | Metric 数据点 | 某个指标的数据维度 | 不默认追加高基数 Pod/实例属性；依指标与查询场景评估 |
| **Release / Deployment Event** | Datafox 发布 API | 某次制品构建/部署的生命周期事实 | 独立的产品事件模型，不强制写进所有遥测 Resource |

**作用域原则**：同一个业务应用的 SDK Traces / Metrics / Logs 在受支持且已启用的信号中，应能观察到相同的**服务身份 Resource**。这不意味着 Kubernetes Node/Container 的基础设施指标也必须带某个业务的 `service.version`，或没有开启的 SDK Logs 自动凭空出现。

## 3. 标准属性与 Datafox 使用约束

本节只列 Datafox **当前确实需要约定的常用 OTel 字段**，不是 OpenTelemetry 全量 Attribute Registry。Key、类型和稳定性以 [OpenTelemetry Semantic Conventions](https://github.com/open-telemetry/semantic-conventions/tree/main/docs/registry/attributes) 为准；以下属性稳定性核对日期为 2026-11-02，生产兼容性仍须以锁定版本为准。

**属性表固定六列：`Attribute`、`Type`、`OTel Stability`、`Scope`、`属性来源`、`Datafox 规则`。** 一行只定义一个属性，不合并不同类型的 Key；`Scope` 是本方案当前使用位置，不是对所有上游信号的全局排他规则。P0/P1 是产品交付阶段，**不是** OTel `Required/Recommended/Opt-In`，也不表示普通 OTLP 接入必须提供全部字段。后续未列出的标准属性继续遵守上游语义，Datafox 不因此禁止接收。

**来源说明：** 本表的“属性来源”只说明属性对应的事实由哪个系统产生，不承诺特定组件或版本能够自动采集。Operator、Collector、SDK Detector 的自动生成、条件注入、透传与补全行为由独立的[元数据采集设计](metadata-collection-design.md)定义。属性语义不随采集机制变化。

### 3.1 P0：应用与环境身份

| Attribute | Type | OTel Stability | Scope | 属性来源 | Datafox 规则 |
| --- | --- | --- | --- | --- | --- |
| `service.name` | string | Stable | Resource | 应用 SDK；Operator 可自动推导 | 逻辑服务名；普通 OTLP 允许上游缺省，受管理发布必须是明确业务身份 |
| `service.namespace` | string | Stable | Resource | 应用 SDK；Operator 可自动推导 | 可缺失；跨环境稳定关联时推荐显式提供，不等于 K8s Namespace |
| `deployment.environment.name` | string | Stable | Resource | 部署配置经 SDK / Operator 传递 | 环境查询和发布关联启用时需要；环境值由业务定义 |
| `service.version` | string | Stable | Resource | CI/CD 版本配置；Operator 可自动推导 | 普通接入可缺失；受管理 Release Tracking 要求与 Release Event 的版本一致 |
| `service.instance.id` | string | Stable | Resource | SDK；Operator 可生成容器级默认值 | 同一服务的并存实例应唯一；不能由 Collector 根据 Pod IP 盲目生成 |

**接入条件分层：** 普通 OTel 遥测允许命名空间、环境、版本缺失，按照 SDK 实际值接收；仅在显式启用受管理 Release Tracking 时，才对业务服务名、目标环境及发布版本实施相应 CI 预检。Datafox 的必需性不替代上游 Service/Service Instance Entity 的 Requirement Level。缺少必要信息时停止**相应受管理发布或关联**，不得无差别拒收正常 OTLP。

**实例唯一性：** Operator 默认可按 Namespace/Pod/Container 构造 ID，通常可区分不同容器，但不能保证同一容器的多个独立 SDK 进程唯一。多进程场景需进程各自提供实例 ID，并以真实 OTLP 验证。`service.instance.id` 不参与逻辑服务名拼接，也不默认成为所有指标的聚合维度。[官方服务实例规范](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/resource/service.md)。

### 3.2 P0/P1：运行位置、制品与发行版

| Attribute | Type | OTel Stability | Scope | 属性来源 | Datafox 规则 |
| --- | --- | --- | --- | --- | --- |
| `k8s.cluster.name` | string | Stable | Resource | 可信集群配置 / Collector | Kubernetes 定位 P0；不能仅凭名称推断跨租户唯一身份 |
| `k8s.cluster.uid` | string | Stable | Resource | Kubernetes API / Collector | P1 可选；可用 `kube-system` Namespace UID 表示 |
| `k8s.namespace.name` | string | Stable | Resource | Operator 可注入 | Pod 实际命名空间，不等于 `service.namespace` |
| `k8s.deployment.name` | string | Stable | Resource | Operator 可按 Workload 注入 | P0 适用时；只反映真实存在的 Workload |
| `k8s.pod.uid` | string | Stable | Resource | Operator 可条件注入 | Kubernetes Pod 关联键；未经验证的自报值不授予可信身份 |
| `k8s.pod.ip` | string | Stable | Resource | Kubernetes Pod 运行位置 | 可选补充单值 IP；会复用，不是实例主键 |
| `k8s.pod.name` | string | Stable | Resource | Operator 可注入 | P1 排障定位，不替代 Pod UID |
| `k8s.node.name` | string | Stable | Resource | Operator 可注入 | P1 Node 定位，不把 Pod IP 当 Node IP |
| `k8s.container.name` | string | Stable | Resource | Operator 可注入 | P1 区分多容器；不能随意选取任一容器 |
| `container.id` | string | Stable | Resource | 容器运行时元数据 | P1 容器身份，不等于独立 SDK 进程 |
| `container.image.name` | string | Stable | Resource | 容器运行时 / Kubernetes 元数据 | P1 镜像名称，不是逻辑服务名 |
| `container.image.tags` | string[] | Stable | Resource | 容器镜像元数据 | P1 镜像 Tag 数组；不能直接当应用发布版本 |
| `container.image.repo_digests` | string[] | Stable | Resource | 容器镜像元数据 | P1 制品定位，不等于 Deployment ID |
| `cloud.region` | string | Development | Resource（适用时） | 云平台元数据 / 部署配置 | P0 适用时保留云厂商原生值，不自造跨云 Region |
| `cloud.provider` | string | Development | Resource（适用时） | 云平台元数据 / 部署配置 | 按上游云厂商约定，不决定 Datafox Tenant |
| `host.ip` | string[] | Development | Resource（主机场景） | Host Resource Detector | P1 可选主机 IP 数组，不能视为单值 Pod IP |
| `telemetry.distro.name` | string | Stable | Resource | Agent Distribution / SDK | P1 标识 Agent 发行版，不代表被观测服务 |
| `telemetry.distro.version` | string | Stable | Resource | Agent Distribution / SDK | P1 标识 Agent 发行版本，不能覆盖 `service.version` |
| `vcs.ref.head.revision` | string | Release Candidate | Resource（适用时） | CI/CD / 构建系统 | P1 可选 VCS 修订；不替代独立 Release Event |

表中只列本方案的主要关联字段。`k8s.statefulset.name`、`k8s.job.name`、`k8s.node.uid`、`cloud.account.id`、`cloud.availability_zone`、`host.name`、`cloud.resource_id` 等其它标准字段按上游语义使用，不因未列入此表而被禁用或强制要求。不存在的 Workload 类型必须省略。

**来源与兼容性：** Collector 只在可信来源和确定 Pod/Container 的情况下补充基础设施信息，不覆盖应用 `service.*`。`container.image.tags` 是 `string[]`；旧版 Collector 的 `container.image.tag` 不能无测试就视为等价字段。实际属性是否由某个 Operator/Collector 版本产生，必须在锁定版本后验证。[Kubernetes](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) · [Container](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/container.md) · [Cloud](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/cloud.md) · [Telemetry](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/telemetry.md)。

### 3.3 多租户、多地域、多单元的字段分层

这三类事实属于不同模型，不能使用单一的 Kubernetes Label 或 `service.namespace` 表示：

| 部署维度 | 权威数据 | 是否参与服务身份 | Datafox 约束 |
| --- | --- | --- | --- |
| 平台 Tenant | Backend 已认证的 `tenant_id`（内部） | 是，可信命名空间 | 不信任 OTLP / Pod Label 自报，决定权限与数据驻留 |
| 逻辑服务 | `service.namespace` + `service.name` | 是 | 跨 Environment / Region / Cell 保持逻辑身份 |
| Environment | `deployment.environment.name` | 否 | 业务发布环境，不当云 Region |
| 云 Region / AZ | `cloud.region` / `cloud.availability_zone` | 否 | 保留云厂商原生地域，不强制归一化 |
| Kubernetes Cluster | `k8s.cluster.uid` / `k8s.cluster.name` | 否 | 独立运行位置，不等于 Tenant、Region、Cell |
| 业务 Cell / Unit | `datafox.unit.id`（P1 可选提案） | 否 | 稳定的业务流量/故障隔离单元，不要求普通应用提供 |
| 逻辑地域 | `datafox.region.id`（P2 候选，暂缓） | 否 | 未成为正式属性合同，先复用标准 `cloud.region` |

Datafox Platform Tenant 与**被观测应用的业务客户租户** 是不同概念。后者可能随请求变化，不应在共享进程的全局 SDK Resource 中设置。Region/Cell 可以用于查询和发布定位，但输入的 Resource 值无权改变 Backend 的写入租户、读取权限或数据驻留路由。

**逻辑服务身份**：`(trusted_tenant_id, service.namespace, service.name)`。P1 **Unit 身份作用域** 为 `(trusted_tenant_id, deployment.environment.name, datafox.unit.id)`，单元化业务在该作用域内应保证 ID 唯一；不同的 Cell 若同名，应由部署系统明确提供不同 ID，不能强依赖 Region/Cluster 目录消歧。普通单地域、无 Cell 服务不要求提供任何 `datafox.*` 属性。

准确的数据来源、Cell↔Cluster 多对多关系、发布事件扩展、跨区域 Trace 和权限合同见 [拓扑与隔离设计](deployment-topology-and-isolation.md)。

### 3.4 暂不纳入 v1 必需 Resource 的字段

OTel Registry 当前列出了 `deployment.id`、`deployment.name` 和 `deployment.status`，但这些字段在研究快照中是 **Development**。Datafox v1 保留发布 API 中独立的 `release_id`、`deployment_id` 和事件状态，不强制各语言 SDK 在 Resource 中携带这几个尚未稳定的部署字段。未来上游稳定且有明确关联需求时，再评估单向映射与版本迁移。[OTel Deployment Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/)。

### 3.5 P0：实例身份、网络地址与 IP 的语义边界

**实例 ID 是身份，IP 是可变化的网络位置。** Pod IP 可能随着 Pod 重建而改变或复用；多个容器/进程可能共用 Pod IP，代理、NAT 和 Host Network 也会使所见 IP 与实际应用不一致。Datafox 不增加 `datafox.instance.ip`、`instance.ip` 等重复的私有字段，也不以 `(service.name, IP)` 唯一标识实例。

**字段定义只维护一次：** `service.instance.id` 见 3.1；`k8s.pod.uid`、`k8s.pod.ip`、`host.ip` 等位置属性见 3.2。以下只说明身份、网络与采集的行为约束，不再次复制字段类型和稳定性。

**唯一性不变量**：OTel 要求 `(service.namespace, service.name, service.instance.id)` 能唯一地区分并存服务实例。SDK 可以使用 UUID；Collector 只有在明确知道实际实例时才能填充，不应仅根据 Pod UID 或 IP 机械生成进程级 ID。Operator 的 Pod/Container 默认 ID 不是进程级唯一性保证：一个 Pod 中的不同容器通常可区分，而同一容器内的多个独立进程需要各自设置唯一值，并通过真实遥测校验。[OTel Service](https://opentelemetry.io/docs/specs/semconv/registry/attributes/service/)、[OTel K8s](https://opentelemetry.io/docs/specs/semconv/registry/attributes/k8s/)、[OTel Host](https://opentelemetry.io/docs/specs/semconv/registry/attributes/host/)、[OTel Container](https://opentelemetry.io/docs/specs/semconv/registry/attributes/container/)。

**网络连接属性与 Resource 不同**。`network.local.address` / `network.peer.address`、`server.address` / `server.port`、`client.address` 依赖**一次具体连接或请求**，属于相应 Span/网络事件上下文；它们不表示固定的服务实例 IP。`server.address` 可能是域名或网关地址，`client.address` 可能涉及个人隐私。`net.host.ip` 和 `net.peer.ip` 已 Deprecated，新埋点不再以其作为通用 Resource 字段。[Network Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/network/)、[Server Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/server/)、[Client Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/client/)。

#### P0 采集与关联规则

- **Kubernetes**：优先复用 Operator 和 Collector `k8sattributes`，通过经过可信入口验证的 `k8s.pod.uid` 关联 Pod，再按需补 `k8s.pod.ip` 与实际 Node/Workload 信息。任意客户端可以伪造 OTLP Resource 的 Pod UID/IP，这两个字段**不是认证凭据**；共享/跨集群 Gateway 不得根据未认证的 UID 或代理连接 IP 做可信归属。只有 IP 时还必须考虑可信 Cluster、观测时间及 Pod 生命周期，不得因同 IP 合并历史 Pod。
- **VM/物理机**：保留应用已有 `service.instance.id`；主机网络排障可选用 `host.ip` 数组。应用进程或容器中看到的 Hostname、网卡地址不必等于 Node 的身份。
- **双栈**：`k8s.pod.ip` 对应 `status.podIP`（单值）；不要把 `status.podIPs` 中的多个值连接为一个字符串，或假称它包含全部接口。
- **HostNetwork/NAT/Service Mesh**：Collector 接收连接源 IP 可能来自 Gateway/Sidecar/Node；不能直接写入 `k8s.pod.ip`。
- **缺失、历史与权限**：缺少 IP 时仍正常接入，不合成 `default`/`unknown` IP；IP 到实例的历史关系需保留观测时间，且不同 Tenant 不能因相同内网 IP 串数据。避免用高基数 IP/Pod UID 作为所有 Metric 的默认聚合维度。
- **运行时开销**：不因这份规范增加 Datafox Java Agent 私有网络探测器、DNS 反查、周期性扫描网卡或应用高频路径的 Kubernetes API 调用。基础设施信息优先在已有 Operator/Collector 与部署平台收集。

### 3.6 P0：服务访问域名、Kubernetes DNS 与请求地址

**域名属于访问入口或请求上下文，不天然属于一个服务实例。** 业务可以同时通过公网域名、内部 Kubernetes Service DNS、Ingress/Gateway 域名和服务发现名称访问；一个域名也可能由 Gateway 路由到多个逻辑服务。因此 `server.address`、`url.full`、`k8s.service.name` **不能取代** `service.name`、`service.namespace`、`service.instance.id` 或 `k8s.pod.uid`。P0 复用上游已有 HTTP/RPC 埋点，不增加 `datafox.service.domain`、`datafox.instance.domain` 等私有 Resource 字段。

| Attribute | Type | OTel Stability | Scope | 属性来源 | Datafox 规则 |
| --- | --- | --- | --- | --- | --- |
| `server.address` | string | Stable | Span / 调用上下文 | 上游 Instrumentation | 已知域名优先，否则可为 IP；不强制反向 DNS |
| `server.port` | int | Stable | Span / 调用上下文 | 上游 Instrumentation | 目标端口，不是服务实例身份 |
| `client.address` | string | Stable | Span / 调用上下文 | 上游 Instrumentation | 可能受代理影响，遵守隐私与信任链 |
| `network.local.address` | string | Stable | Span / 连接上下文 | 上游 Instrumentation | 本地连接地址，不当 Host Resource IP |
| `network.peer.address` | string | Stable | Span / 连接上下文 | 上游 Instrumentation | 对端连接地址，不等于 `k8s.pod.ip` |
| `url.full` | string | Stable | Span / 请求上下文 | 上游 Instrumentation | 完整 URL；敏感路径、参数和凭据须按 SemConv 清理 |
| `url.domain` | string | Development | Span / URL 上下文 | 上游 Instrumentation | 可选派生域名，不默认写入服务 Resource |
| `dns.question.name` | string | Development | DNS Span / Metric 上下文 | 上游 DNS Instrumentation | 可选诊断，不以 DNS 名作为服务唯一身份 |
| `k8s.service.name` | string | Development | Resource（适用时） | Kubernetes Service 元数据 | Kubernetes Service 对象名，不等于 `service.name` |
| `k8s.service.uid` | string | Development | Resource（适用时） | Kubernetes Service 元数据 | Service 对象 UID，不是 Pod / 进程 ID |
| `http.request.header.host` | string[] | Stable（Header 模板） | Span / 请求上下文 | 上游 HTTP Instrumentation（Opt-In） | 仅在明确需要时采集，不使用可伪造 Host 决定权限 |

`host.name` 若作为 Host Resource 使用，遵守上游 Host Registry，不能把 HTTP Host、Service DNS 或公网域名等同于主机名。`http.request.header.host` 按上游 `http.request.header.<key>` 模板类型定义。非上述字段依然遵守官方 SemConv，不自动进入 Datafox P0 必填集合。

HTTP 客户端调用 `https://order-service.commerce.svc.cluster.local:8443/api/orders` 时，可在相应 Span 上观察到 `server.address=order-service.commerce.svc.cluster.local` 和 `server.port=8443`；`service.name=order-service` 仍属于**应用自己的 Resource**。在服务端，`server.address` 可能按可信代理传递的 `Forwarded` / `X-Forwarded-Host`、HTTP/2 `:authority` 或 `Host` 得到，属于请求视角；未受信任客户端可操纵 Host 类 Header，Datafox 不应把它作为未经校验的权威资产目录、路由目标或权限依据。[OTel HTTP SemConv](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)、[Server Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/server/)。

#### Kubernetes Service DNS 与公网域名

Kubernetes Service DNS 通常可采用 `<service>.<namespace>.svc.<cluster-domain>` 形式，实际 Cluster Domain **不保证** 为 `cluster.local`。一个普通 Service DNS 可解析到 ClusterIP；Headless Service DNS 可解析到多个 Pod IP。Ingress、Gateway、企业内网 DNS 和公有域名与 Pod 的关系可能随路由配置变化。**不要仅从 Pod Name 或 Service 名拼接一个 FQDN 并写入所有业务进程的 Resource。** [Kubernetes DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)。

如果 Datafox 后续需要 **“服务访问域名 / Endpoint 清单”** 产品能力，应在 Backend 作为独立的、带来源和观察时间的 **Service Endpoint / Route 关联**，依据受信任的 Ingress/Gateway/Service 配置和实际路由关系建立。一个逻辑服务可以对应多个域名，一个域名可对应多个路由和后端；P0 **不建设**实时 DNS 探测器、域名注册中心或强制的单域名 Resource 属性。

#### 安全、基数与采集成本

- `url.full` 可能包含账号、Token、查询参数、用户输入或完整业务 ID。根据 OTel URL SemConv 清理敏感内容；默认查询与指标分组优先使用稳定、低基数的 `http.route`，不要以任意 URL/Host/DNS 查询值作为默认 Metric 标签。
- DNS 查询名称可能包括内部服务信息或用户控制的任意域名。DNS 自动埋点属于**按需诊断**，不能为了补齐服务域名强制对每次连接发起 DNS 查询。
- 多租户的公网域名可能相同，私有 DNS 名也可能在不同 Cluster 重复；域名、Host Header、URL 均不能决定 Datafox Tenant、数据驻留或实例身份。
- 为了得到 `server.address` 不进行反向 DNS、网络扫描或高频缓存查询；优先复用上游 HTTP/RPC Instrumentation 已知的目标地址。代理后的真实目标只有明确可获知时才使用，不能依靠猜测。
- 旧版 `http.host` / `http.server_name` 已弃用。新接入优先采用相应的 `server.address`，仅在有保留原始 Header 的明确需求时使用 `http.request.header.host`。[HTTP Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/http/)、[OTel URL Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/url/)、[DNS SemConv](https://opentelemetry.io/docs/specs/semconv/dns/dns-metrics/)。

## 4. Kubernetes 标签适配：推荐默认映射，不强制企业改名

Kubernetes Label 的命名由业务团队、Helm Chart、GitOps 模板或云厂商各自管理。Datafox **只要求最终输出符合 OTel Resource 语义**，不要求用户的现有 Label 命名符合某个厂商/项目模板。下表是**上游 Operator 支持的推荐默认路径**，不是 Datafox 唯一接受的 Kubernetes 标签来源。

### 4.1 推荐映射（可直接复用上游 Operator）

| Kubernetes 输入（Pod Template） | OTel 目标 | Datafox 规则 |
| --- | --- | --- |
| `app.kubernetes.io/name` | `service.name` | **推荐业务名输入**；Operator 也会优先检查 `app.kubernetes.io/instance` |
| `app.kubernetes.io/instance` | `service.name`（Operator 可能优先采用） | **仅表示应用安装实例**；如果它与业务服务名不同，必须提供显式 `service.name` |
| `app.kubernetes.io/version` | `service.version` | 推荐版本来源之一；使用时遵循 Kubernetes Label 格式 |
| `resource.opentelemetry.io/service.name` | `service.name` | Helm Release 和业务服务名不一致时明确指定 |
| `resource.opentelemetry.io/service.namespace` | `service.namespace` | 需要跨 Namespace 统一逻辑服务身份时显式提供 |
| `resource.opentelemetry.io/service.version` | `service.version` | 允许发布系统显式覆盖版本 Label |
| `resource.opentelemetry.io/deployment.environment.name` | `deployment.environment.name` | 推荐环境来源；既有企业环境 Label 也可以在部署模板阶段适配，不要求重命名 |
| Kubernetes API Pod/Owner 结构 | `k8s.*` | Collector 按基础设施对象补全，不作为业务身份映射 |

官方 Kubernetes 推荐 Label 包含 `name`、`instance`、`version`、`part-of`、`component`、`managed-by`；本规范不默认将 `part-of` 映射成 `service.namespace`，因为“整个应用”和“业务命名空间”并不一定是同一个概念。Operator 在 `useLabelsForResourceAttributes: true` 时使用支持的 Label，并遵循其已知的 `instance → name` 顺序。[Kubernetes Recommended Labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/)、[OTel Kubernetes Resource 计算规则](https://opentelemetry.io/docs/specs/semconv/non-normative/k8s-attributes/)。

**Label 值边界**：采用 Label 路径时，Kubernetes Label 值最多 63 字符，且不接受 `+` 等字符。因此 `service.version=2.4.1+build.17` 这样的合法应用版本**不能直接写成 Kubernetes Label 值**；应使用 `resource.opentelemetry.io/service.version` Annotation 或显式 SDK Resource。版本字符串不自动截断、去掉 `+` 或转换成另一种版本。OTel `service.version` 本身不强制 SemVer。[Kubernetes Label Syntax](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/)。

### 4.2 企业自定义 Label / 云厂商标签的适配路径

企业可能使用 `company.example.com/service`、`company.example.com/release`、`platform.example.com/environment`，或由云平台/Helm Chart 维护已有标签。以上键名只是**教学示例**，不代表任何云厂商的真实默认值。Datafox 不接管这些名称，也不要求替换它们。

推荐按已有控制权选择最薄的适配方式：

| 企业现状 | 适配位置 | Datafox 处理 |
| --- | --- | --- |
| 应用已通过 OTel SDK/Agent 显式设置 Resource | 应用初始化 / 现有 OTel 配置 | **直接接受**；不强制附加 Kubernetes Label |
| 使用上游 `app.kubernetes.io/*` | Operator 原生映射 | 打开 Label 解析选项并验证最终 Resource |
| 使用自定义公司/云厂商 Label，能够修改 Helm/Kustomize/GitOps 模板 | **部署模板适配层** | 保留原 Label，同时从企业来源取值生成 `resource.opentelemetry.io/*` Annotation 或标准 SDK 配置 |
| 通过 CI/CD 已有构建元数据、无需从 Pod Label 读取 | 发布流水线/应用配置 | 直接生成 OTel Resource 的配置，避免制造重复标签 |
| 仅想保留企业自定义基础设施标签供筛选 | Collector `k8sattributes.extract.labels` 白名单 | 映射到独立的基础设施/组织属性；不改写 `service.*` |
| 完全不能修改业务 Manifest 或 SDK | 仅观察现有 OTLP 输出 | 可提供有限的自动推导与缺失提示；**不承诺** 仅凭自定义 Label 就能自动注入正确应用身份 |

在 OpenTelemetry Operator 的已检查实现中，`useLabelsForResourceAttributes` **不是任意 Label → Resource 的通用映射引擎**。它识别的标准键范围有限。自定义 Label 若要成为 `service.version` 等应用身份，优先在**Helm/CI/CD/GitOps 模板渲染阶段** 转成受支持的 Resource Annotation，避免自建 Admission Webhook。[Operator 支持的映射](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)。

Collector 官方提供 [`k8sattributes.extract.labels` 的定向提取](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md)，但 Datafox 依然遵守 D3：**Collector 只补充基础设施与经允许的组织元数据，不承担应用服务名称/版本的覆盖职责。**

**首期工程范围**：优先复用用户已有 OTel 配置和部署模板，不急于设计一套新的通用标签转换 DSL。若后续确实有跨多家企业、批量维护映射的业务需求，再评估在 Helm/CI/CD 层提供**可配置、可测试的 Mapping Profile**；它应是部署时转换，不是运行中的自定义 Webhook。

### 4.3 推荐的 Pod Template

下面只是属性来源示例，不是完整 Deployment 或已验证的 Operator 安装配置。

~~~yaml
template:
  metadata:
    labels:
      app.kubernetes.io/name: order-service
      app.kubernetes.io/instance: order-service-prod
      app.kubernetes.io/version: "2.4.1"
    annotations:
      # 避免将 Helm Release instance 误作为 service.name。
      resource.opentelemetry.io/service.name: "order-service"
      resource.opentelemetry.io/service.namespace: "commerce"
      resource.opentelemetry.io/deployment.environment.name: "production"
      instrumentation.opentelemetry.io/inject-java: "datafox"
~~~

如需要 `2.4.1+build.17`，通过 `resource.opentelemetry.io/service.version` 表示完整版本，且 CI/CD 发布事件必须采用**相同的最终版本值**。

上游 Operator 使用 Pod Metadata；只在 Deployment 顶层 `metadata.labels` 填字段，无法保证自动注入读取到相同内容。可以同时给 Workload Metadata 与 Pod Template 添加相同标准 Label 方便管理，但**Pod Template 是本方案的注入入口**。

多业务容器共用一个 Pod 时，Pod Label/Annotation 无法表示每个业务容器的不同身份。推荐拆成不同 Pod；确需共存时由容器显式 Resource 配置决定自己的 `service.*`，并在 CI 中验证冲突，不能对所有容器广播 Pod 级业务版本。

## 5. 优先级、冲突与缺失的统一处理

### 5.1 注入来源优先级

由 Operator 负责将 Pod 元数据转换为标准 SDK 配置，采用以下决策顺序：

1. 用户已有的 **可安全读取的显式** 配置；其中 `OTEL_SERVICE_NAME` 在 SDK 对 `service.name` 的解析中优先于 `OTEL_RESOURCE_ATTRIBUTES` 里的同名属性。
2. `resource.opentelemetry.io/*` Annotation。
3. 开启 Label 提取后的标准 `app.kubernetes.io/*`。
4. Operator 其他自动推导，**仅作为上游兼容行为**，不能代替 Datafox 的生产版本准入规则。
5. Instrumentation CR 默认 Resource 属性。

上述顺序仅是**按具体属性理解的期望来源**，不能跨环境变量当成统一的覆盖算法。已检查 Operator 在 `env[]` 缺少 `OTEL_SERVICE_NAME` 时会**另行注入该变量**，即使 `OTEL_RESOURCE_ATTRIBUTES` 已设置 `service.name`；若 Pod Label 的 `app.kubernetes.io/instance=order-prod` 而显式 `OTEL_RESOURCE_ATTRIBUTES=service.name=order-service`，SDK 最终名称可能被注入的 `OTEL_SERVICE_NAME=order-prod` 覆盖。受管理注入须同时解析两种变量与 Annotation/Label：最小修正为显式设置一致的 `OTEL_SERVICE_NAME`，或在 Pod Template 加入一致的 `resource.opentelemetry.io/service.name`；无法确定最终一致性则在 CI 拒绝。SDK 最终 Resource 仍可能合并用户代码创建的 Resource 和其他 Detector，因此每种语言必须以真实 OTLP 验证，而不能只查环境变量。[Operator 固定源码](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go#L495-L566)、[OTel SDK Resource 规范](https://opentelemetry.io/docs/specs/otel/resource/sdk/)。[Operator Resource Attributes（固定研究源码）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)、[OTel Resource SDK](https://opentelemetry.io/docs/specs/otel/resource/sdk/)。

### 5.2 Datafox 负责的冲突策略

只有启用了受管理自动注入或 Release Tracking 的工作负载，才需要额外执行对应的发布前字段校验；普通 SDK 遥测接收不应因为未使用推荐 Kubernetes Label 而被拒绝。

| 情况 | 处理 |
| --- | --- |
| 显式版本与 Annotation/Label 不同 | 按锁定 SDK/Operator 的版本优先级验证并保留最终显式值；CI 显示生效来源，不静默重写 |
| Annotation 版本不同于 Label | 允许显式覆盖，但 Release Event 的版本必须与**最终生效值** 一致 |
| `service.name` 被 `app.kubernetes.io/instance` 或注入的 `OTEL_SERVICE_NAME` 误影响 | 受管理注入须验证 `OTEL_SERVICE_NAME` 与 `OTEL_RESOURCE_ATTRIBUTES.service.name`、Annotation、Release Event 的**最终值** 一致；普通接入可保留实际值并提示冲突 |
| 跨环境的 `service.namespace` 随 Kubernetes Namespace 变化 | 不自动合并；需要跨环境统一逻辑服务时推荐显式稳定身份 |
| `OTEL_RESOURCE_ATTRIBUTES.valueFrom` / `envFrom` 同名冲突 | 在**注入目标容器的 CI 发布前检查** 中拒绝不兼容输入 |
| 业务版本缺失 | 普通遥测允许缺失；启用受管理 Release Tracking 且要求版本关联时阻止发布扩量；接收端不伪造 `service.version` |
| SDK Resource 与 CI Release Event 不一致 | 保存原始遥测，发布关联标记不一致，不覆盖原始 Resource |
| Collector 无法识别 Pod | 保留已有遥测与 Service Resource；省略无法证实的基础设施属性 |
| 新旧字段或不同 SemConv 版本冲突 | 保留原始输入并记录版本；只有经明确批准的迁移规则才可规范化 |

不能用 Collector 对 `service.name`、`service.namespace`、`service.version` 的“补全”掩盖错误。业务服务身份必须可溯源到 SDK/Operator 的配置来源。

### 5.3 安全说明：注入本身也可能造成业务故障

上游已检查源码对 `OTEL_RESOURCE_ATTRIBUTES` 的 `valueFrom` 输入可能追加普通 `value`，引起 Kubernetes Pod CREATE 校验拒绝；`envFrom` 存在同名键时也可能被显式环境变量遮蔽。Java `JAVA_TOOL_OPTIONS.valueFrom` 存在类似不兼容性。此类检查属于**准入前配置验证**，而不是本规范中定义新的 Kubernetes Admission Webhook。详细机制、负面测试和恢复步骤见 [实施与验证手册](implementation-and-verification.md)。

## 6. 统一查询与跨信号关联

### 6.1 Datafox 的默认筛选和分组

| 查询层级 | 默认维度 | 用途 |
| --- | --- | --- |
| Service Inventory | 已鉴权 Tenant + `service.namespace` + `service.name` | 服务列表与服务归属 |
| Environment View | Service + `deployment.environment.name` | 同一服务跨环境对比 |
| Version View | Service + Environment + `service.version` | 版本错误率、延迟趋势、发布影响 |
| Workload / Pod Drill-down | Version View + `k8s.cluster.name` / `k8s.namespace.name` / `k8s.pod.uid` | 定位实际运行 Pod |
| Release Tracking | Service + Version + Environment + Deployment Event 目标与时间证据 | 关联发布动作；证据不足时保留候选 |

注意 `service.version` 是软件版本，**不是** Deployment ID；同版本多次部署不应合并 Deployment 记录。OTel 尚未稳定的 `deployment.id` 不作为 v1 的跨语言强制字段。

### 6.2 多租户、地域与单元的查询层级

Datafox 的查询层首先通过可信认证确定 Tenant，再按 Service、Environment、已有 `cloud.region`，以及可选 Unit 过滤，最终下钻到 Cluster、Workload 和 Pod。**Region 和 Unit 不改变 Service 身份，也无需强制构成一棵树**。P1 不引入逻辑 Region 注册中心。

- 同一 `service.version` 可以部署在多个 `cloud.region` 和多个可选 `datafox.unit.id`；每次独立 Rollout 都必须保留自己的 `deployment_id`。
- 同一 Trace 可以跨 Region 或 Unit，不能把全部 Span 强行归为单个 Cell。
- `cloud.region` 表示云厂商原生地域；跨云逻辑 `datafox.region.id` 仅作为 P2 待评审扩展，**当前不要求注入、不索引、不作为发布关联前置条件**。
- Datafox Backend 的 Tenant 过滤与数据驻留由鉴权与路由实现，**不得依赖** 可伪造的 OTLP Resource 属性。

完整的发布关联和安全边界见 [拓扑与隔离设计](deployment-topology-and-isolation.md)。

### 6.3 Traces、Metrics、Logs 的一致性不是盲目复制

- **Traces**：优先使用 Resource 的服务与环境身份，不为每个 Span 重复写 `service.name`/`version`。
- **Metrics**：保持 SDK Resource 与必要的数据点属性；查询引擎和存储需要明确维度预算。`k8s.pod.uid` / `service.instance.id` 高基数，禁止无差别作为每条派生指标的默认分组标签。
- **Logs**：OTLP Logs 使用自己的 Resource；其他日志源只有在能可信关联容器/工作负载时才能映射相应服务身份。不能凭一个 Node IP 将全部日志标成同一个应用版本。
- **基础设施指标**：Node / Pod / Container 资源指标可关联 `k8s.*`，但不需要给每个 Node Metric 赋予某个业务容器的 `service.version`。在 UI 中通过有证据的实体/工作负载关系关联，不改写信号本身的身份。

## 7. 治理、扩展与版本演进

### 7.1 语义来源和版本

语义优先级：**OTel Specification / Semantic Conventions → 锁定版本的 SDK、Operator、Collector 实现 → Datafox 平台准入与查询契约**。

本规范是 Datafox 对标准字段的使用配置，不取代 OpenTelemetry 原始属性定义。所有语义变化应记录受影响的 OTel SemConv 版本、项目组件版本、迁移策略及测试。稳定字段优先；Development / Release Candidate 属性只能按明确的兼容门槛选用，不能作为无条件的强制身份。

### 7.2 自定义属性的准入

优先寻找现有 `service.*`、`deployment.*`、`k8s.*`、`container.*`、`cloud.*`、`host.*`、`vcs.*`、`telemetry.*` 等 OTel 标准字段。确属 Datafox 独有、无法用现有语义表达的能力，才提出 `datafox.*` 自定义属性，并同时定义语义、类型、作用域、来源、保留期、隐私风险、索引基数和迁移办法。

**不支持** 将 Token、Secret、密码、客户个人信息、任意 HTTP 请求 ID、完整 Kubernetes Annotation/Label 集合批量注入通用 Resource。不自动将未经白名单核准的任意 Pod Label 全量转成 Metric 维度。

自定义属性不能冒充 OTel 规范字段，也不能被用来修改 `service.name` 的意义。

### 7.3 版本升级与历史兼容

- 新数据首先遵循当前锁定的 OTel 规范键名；历史使用的 `deployment.environment` 已弃用，v1 不作为新输入建议。
- 若旧版 Collector 产生 `container.image.tag`，而新 SemConv 稳定字段是 `container.image.tags`（`string[]`），必须经独立兼容设计和实际类型测试转换；不在本文默认宣称同名或等价。
- 任何历史数据兼容/索引映射必须保持源值可追踪，不能静默修复用户非法输入。
- 需要定期核验 Operator 对 `app.kubernetes.io/instance` / `name`、Env 优先级、SDK-only 和 Kubernetes Webhook 的实际支持，不用当前上游 `main` 的代码替代生产发行版证据。

## 8. 最小验收合同与下一步

统一标签规范 **尚未实现**。第一批工程测试必须证明：

| Case | 输入 / 场景 | 预期结果 |
| --- | --- | --- |
| Tag-01 | Java/Python/Node.js/.NET/Go 同一业务身份与版本 | 最终 OTLP Resource 的四个核心属性完全一致 |
| Tag-02 | 跨 Namespace/Cluster 发布同一 Service | `service.namespace/name` 稳定，`k8s.*` 区分实际部署位置 |
| Tag-03 | Helm `app.kubernetes.io/instance` ≠ 业务 `name`，同时只在 `OTEL_RESOURCE_ATTRIBUTES` 设置 `service.name` | 识别 Operator 注入 `OTEL_SERVICE_NAME` 的覆盖风险；受管理发布在 CI 拒绝或显式统一，E2E 验证最终服务名 |
| Tag-04 | `2.4.1+build.17` | 使用 Annotation 传递完整值；非法 Label 不进入 Pod |
| Tag-05 | 显式版本、Annotation、Label 三者冲突；独立检查 `OTEL_SERVICE_NAME` 与 Resource 中的 `service.name` 冲突 | 按各属性真实 SDK 优先级确认最终值，CI 与发布事件一致 |
| Tag-06 | `valueFrom` / 冲突 `envFrom` | 在自动注入发布前失败，不触发生产 Pod CREATE |
| Tag-07 | Collector 缺少 Pod 关联信息 | 不伪造或覆盖服务与 Pod 身份 |
| Tag-08 | 同版本重复部署/回滚 | 一个 Service Version，多条独立 Deployment 记录 |
| Tag-09 | Agent 发行版本升级 | `telemetry.distro.version` 变化不影响 `service.version` |
| Tag-10 | Trace / Metric / Log / Node Metric | 应用信号身份一致；Node Metric 不被错误贴上单个服务版本 |

实施手册中既有 T01–T44 仍是 **实施验收清单**；本节 Tag-01–Tag-15 是跨仓库合同测试的语义索引，不应被记录为额外已经通过的测试。

### 8.1 多租户、多地域、多单元合同测试

**Topo-01–Topo-12** 分阶段作为拓扑合同：P0 检验租户隔离、标准云 Region、数据驻留；仅在启用 Cell 的 P1 运行单元关联、跨 Cell 发布与查询用例。复杂跨云逻辑地域目录不纳入 P0/P1。具体输入、预期结果和权限边界统一维护在 [拓扑与隔离设计](deployment-topology-and-isolation.md)，不复制为第二套独立权威测试表。

### 8.2 不同标签来源的兼容性案例

| Case | 输入 / 场景 | 预期结果 |
| --- | --- | --- |
| Tag-11 | 自定义 `company.example.com/release` Label，经 Helm 模板映射到 Resource Annotation | 保留企业标签原值，最终 OTel `service.version` 等于目标制品版本 |
| Tag-12 | 只提供显式 `OTEL_RESOURCE_ATTRIBUTES`，无任何推荐 Kubernetes Label | 正常进入 Datafox，SDK Resource 不被 Collector 改写 |
| Tag-13 | 自定义基础设施 Label 仅通过 Collector 白名单提取 | 自定义属性可查询，但不覆盖业务 `service.*` |
| Tag-14 | 无版本且未启用 Release Tracking 的普通 OTel 服务 | 遥测可接收，不被强制推断出发布版本 |
| Tag-15 | 多容器 Pod 与企业自定义 Pod 级版本 Label | 不把一份 Pod Label 作为多个业务容器的不同应用版本 |

这些仍是**拟定测试契约**；实施前需要根据实际 Helm/CI/CD 接入方式落地，不代表已有通用映射工具或已经完成 E2E。

**前置的评审问题**：确定 Datafox 在受管理发布与普通 OTel 接入中的最小字段要求、多租户鉴权和数据驻留的真实部署方案、P1 可选 Cell 的实际来源与应用范围，以及哪些企业标签映射确有业务需要。Service Namespace 的长期语义、版本字符串格式、CI 事件来源和历史数据兼容性仍需逐项确认。完成规范评审后，再锁定 Operator/Collector 版本和开发注入配置。

### 8.3 实例与 IP 合同测试

| Case | 输入 / 场景 | 预期结果 |
| --- | --- | --- |
| Inst-01 | 两个业务 Worker 位于同一 Pod：先在不同容器，再在同一容器内作为独立进程 | Operator 默认容器级 ID 不保证同容器进程唯一；第二种必须由 SDK/进程显式提供不同 `service.instance.id`，E2E 检查输出 |
| Inst-02 | Pod 重建后 IP 被复用 | 不因同 IP 合并两个 Pod UID 或错误关联历史遥测 |
| Inst-03 | HostNetwork、Sidecar 或 Gateway 转发 | 不把连接源 IP 直接写成 `k8s.pod.ip` |
| Inst-04 | K8s Pod IP 缺失但 Pod UID 存在 | 保留实例身份与 Trace，不生成虚假 IP |
| Inst-05 | 双栈 Pod 的 `status.podIPs` 有多个地址 | `k8s.pod.ip` 遵守单值来源，不能把数组序列化成字符串 |
| Inst-06 | VM 多张网卡、IPv4 + IPv6 | `host.ip` 为合法 `string[]`，不误作 `k8s.pod.ip` |
| Inst-07 | 带 `client.address` 的请求、NAT/代理连接 | 网络地址留在请求/连接上下文，遵守隐私与脱敏策略 |
| Inst-08 | 两个 Tenant 使用相同 RFC1918 私网 IP | 不因 IP 复用导致跨租户实例/遥测关联 |

以上为 **P0 字段与联调测试提案**，尚未执行，不增加 SDK 运行时 Detector。

### 8.4 域名、DNS 与 Endpoint 合同测试

| Case | 输入 / 场景 | 预期结果 |
| --- | --- | --- |
| Domain-01 | HTTP Client 调用 `order-service.commerce.svc.cluster.local` | Span 的 `server.address` 为已知目标域名；Resource 的 `service.name` 不变 |
| Domain-02 | 公网域名经 Ingress / Gateway 到两个业务服务 | 不将域名直接当作唯一 Service ID，关联须有实际路由证据 |
| Domain-03 | Headless Service 域名解析到多个 Pod | 不把一个 Service FQDN 错当成一个实例或一个 Pod IP |
| Domain-04 | 仅得到目标 IP，没有 DNS 名 | `server.address` 可以是 IP，不强制反向 DNS 查询 |
| Domain-05 | `url.full` 包含用户凭据或敏感查询参数 | 敏感内容按标准清理，不泄露到查询/日志 |
| Domain-06 | DNS 查询有 `dns.question.name` | 只归属 DNS 查询上下文，不自动变成应用 Resource 域名 |
| Domain-07 | 客户端伪造 HTTP Host / `X-Forwarded-Host` | 不据此覆盖业务 Service 身份或 Datafox 授权/资产所有权 |
| Domain-08 | 不同 Tenant 或 Cluster 使用相同内部 DNS 名 | 不发生跨租户/跨集群误关联 |
| Domain-09 | Kubernetes Cluster Domain 不是 `cluster.local` | 不硬编码构造 Service FQDN，保留真实访问名 |

这些测试属于**拟定 P0 语义合同**。不代表已实现 DNS 探测、Ingress/Service 路由目录、HTTP Header 信任链验证或自动域名关联。

## 参考资料与可信度

- [Datadog Unified Service Tagging](https://docs.datadoghq.com/getting_started/tagging/unified_service_tagging/) — 产品概念比较，不是 OTel 协议权威。
- [OpenTelemetry Service Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/resource/service/) — 服务身份与版本。
- [OpenTelemetry Deployment Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/) — 环境稳定字段，以及当前 Development 部署字段。
- [OpenTelemetry Kubernetes Attributes](https://opentelemetry.io/docs/specs/semconv/non-normative/k8s-attributes/) — Kubernetes 到 Resource 的标签映射。
- [OpenTelemetry SDK Resource Specification](https://opentelemetry.io/docs/specs/otel/resource/sdk/) — 环境变量与 SDK Resource 合并。
- [OpenTelemetry Container Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/container/) — 镜像属性当前类型。
- [OpenTelemetry Kubernetes Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/k8s/) — Pod、Cluster、Workload 等属性。
- [OpenTelemetry Telemetry Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/telemetry/) — SDK 与发行版版本。
- [Kubernetes Recommended Labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/) 与 [Label Syntax](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/)。
- [OpenTelemetry Operator Resource Attributes（源码快照 cddb781）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)。

> **证据状态**：上述字段与规范状态按 2026-10-31 的公开官方材料整理。Operator 内部行为与 Env 冲突引用固定源码快照；实际生产版本仍待锁定。**没有执行** Kubernetes Operator/Collector、多语言 SDK、CI/CD 或 Backend 合同测试，也没有批准正式 ADR。
