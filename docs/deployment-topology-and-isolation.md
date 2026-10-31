# Datafox 多租户、多地域、多单元部署模型

> **状态：架构提案，待评审 · 2026-10-31。** 本文是 [统一标签规范](unified-tagging-convention.md) 的拓扑与权限扩展，并与 [Kubernetes 系统架构](architecture.md) 共用服务身份和发布事件契约。**本文不表示这些属性、后端隔离或发布流程已经实现**。
>
> **关键结论：** 租户由 Datafox 已鉴权的接入确定；物理位置采用已有 OTel `cloud.*` / `k8s.*`；单元（Cell）为 Datafox 业务部署拓扑，只有明确需要时使用拟议的 `datafox.unit.id`。跨云/IDC 的**逻辑地域**在确有业务需要时才引入拟议 `datafox.region.id`。这些属性不能冒充 OTel 标准字段，更不能拿未经鉴权的 Resource 值执行安全授权。

## 1. 为什么需要独立的部署拓扑

一个企业在 AWS 东京和 GCP 东京同时运行 `commerce/order-service`。AWS 东京内部有 `cell-a`、`cell-b`，GCP 东京另有 `cell-c`；公司也可能把一批客户或流量路由到某个单元。相同版本 `2.4.1` 可以逐个单元灰度升级。

Datafox 必须同时回答四个不同问题：

- **谁有权读取这些数据？** Datafox 平台 Tenant / Organization。
- **属于哪个业务服务？** `service.namespace` + `service.name`，跨 Region/Cell 仍然不变。
- **运行在哪里？** 云 Region、Availability Zone、Kubernetes Cluster/Pod，以及可选的企业逻辑 Region。
- **在哪个部署单元？** 某个业务 Cell，可能由多个 Kubernetes 集群或多个 Namespace 组成。

若把 Tenant 塞入 `service.namespace`、把 Cell 塞入 `k8s.cluster.name`、把 Region 塞入 `deployment.environment.name`，就会破坏 OTel 原有语义，并使跨单元发布与故障隔离失去独立的查询维度。

## 2. 三种不同身份：权限、服务和部署拓扑

~~~mermaid
flowchart TB
    Ingest["Datafox Ingestion<br/>已认证客户端 / 凭证"] --> T["Platform Tenant<br/>安全与数据隔离边界"]
    T --> S["Logical Service<br/>service.namespace + service.name"]
    S --> E["Deployment Environment<br/>production / staging"]
    E --> R["Logical Region（可选）<br/>datafox.region.id"]
    R --> U["Deployment Unit（可选）<br/>datafox.unit.id"]
    U --> C["Physical Infrastructure<br/>cloud.* / k8s.* / container.*"]
    E --> C
    C --> P["Pod / Process<br/>service.instance.id"]
~~~

此图表达数据浏览与关联层级，**不**声称每个部署都必须有逻辑 Region/Unit，也不代表 Kubernetes 的所有资源都严格树形归属。一个 Cell 可以覆盖多个 Cluster，一个 Cluster 也可能托管多个 Cell；后端应使用显式关系而不是推导固定一对一映射。

### 2.1 Datafox 平台租户（安全边界）

**Platform Tenant ID** 是 Datafox Backend 的已认证租户上下文（例如 API Key/OIDC 身份对应的内部租户 ID）。它决定数据写入分区、查询授权、配额与保留策略：

- 通过认证和服务端授权解析，不由 `OTEL_RESOURCE_ATTRIBUTES`、Pod Label、`service.namespace` 或 Collector 自定义 Header 指定。
- 入站 OTLP Resource 中伪造 `tenant_id` / `datafox.tenant.id` **不得改变**租户归属或权限；Datafox 不要求 Agent 发送此类属性。
- Storage/Index 的主键、检索过滤、跨 Tenant 查询与 Release Event 关联必须以可信租户上下文隔离。未认证/无效认证按入口策略拒绝，不能降级写入默认 Tenant。
- Collector 可以在平台受控链路附带认证信息，但认证 Header 与业务 Resource 必须分离；共享 Collector 的每租户路由、凭据和出口权限必须单独审查。

**业务租户（应用的客户）≠ Datafox 平台租户。** 例如被观测 SaaS 的每个请求可能携带 customer/account ID，这是动态的**请求级业务上下文**。不能把它当作 SDK 的全局 Resource，也不能与平台 Tenant ID 混淆；若确有诊断需求，应由应用按权限、隐私和高基数策略决定是否放入 Span/Log Attribute，不能为其发明“跨请求全局服务身份”。

### 2.2 逻辑服务（跨地域稳定）

逻辑服务标识采用 `(trusted_tenant_id, service.namespace, service.name)`。其中 `service.namespace` 可按 OTel 规范省略；缺失时以空命名空间处理，**不从 Region/Cell 反向合成**。`service.version` 作为制品版本独立存在，Region、Cell、Environment 变化不会使同一服务变成新的逻辑 Service。

### 2.3 部署拓扑（运行位置与故障域）

| 维度 | 建议字段 | 权威/数据来源 | 必需性与边界 |
| --- | --- | --- | --- |
| Environment | `deployment.environment.name`（OTel Stable） | 业务/部署配置 | 环境比较时推荐；不是云 Region |
| 云厂商 | `cloud.provider`（OTel Development） | SDK Resource Detector / 可信平台配置 | 云环境可选；保留厂商标识 |
| 云账号 | `cloud.account.id`（OTel Development） | 云资源元数据/平台 | 多账号需要；避免只以 Region 名全局唯一定位 |
| 物理云 Region | `cloud.region`（OTel Development） | 云原生 Resource Detector / 平台 | 例如 AWS `ap-northeast-1`、GCP `asia-northeast1`；**原样保留各云编码** |
| Availability Zone | `cloud.availability_zone`（OTel Development） | 云资源元数据 | 例如 `ap-northeast-1a`；不能当 Cell |
| Kubernetes Cluster | `k8s.cluster.uid`（OTel Stable）、`k8s.cluster.name`（OTel Stable） | 集群元数据 / Collector | UID 优先，Name 用于展示，不与 Region 或 Cell 混同 |
| 逻辑地域 | `datafox.region.id`（**拟议 Datafox 自定义属性**） | 受控部署拓扑配置 | **仅在跨云、IDC、业务逻辑地域需要时启用**，例如 `jp-east` |
| 单元 / Cell | `datafox.unit.id`（**拟议 Datafox 自定义属性**） | 受控部署拓扑/工作负载配置 | 仅在多单元业务启用；例如 `cell-a` |
| Pod 和业务实例 | `k8s.pod.uid`、`service.instance.id`（OTel Stable） | Operator/Collector/SDK | 具体运行实例，不能代替 Unit |

以上云属性的标准稳定性以本次审查的 OTel Semantic Conventions 快照为准，实施时必须固定目标 SemConv 版本。[Cloud 属性](https://opentelemetry.io/docs/specs/semconv/registry/attributes/cloud/)、[Kubernetes 属性](https://opentelemetry.io/docs/specs/semconv/registry/attributes/k8s/)、[Service 属性](https://opentelemetry.io/docs/specs/semconv/registry/attributes/service/)。

**默认兼容性**：普通单地域、非单元化服务不要求提供 `datafox.region.id` 或 `datafox.unit.id`。这两个可选属性只有在明确启用逻辑地域或 Cell 的部署/查询功能后才参与合同验证。

**无云 Region 时不要编造 `cloud.region`。** 自建机房可选择提供 `datafox.region.id`；云环境也可以同时具有 `cloud.region` 和 `datafox.region.id`，两者分别表示**云厂商物理位置**和**企业自定义的逻辑地域**，不得自动假定相等。不要使用根 `geo.*` 属性来偷偷表示云资源位置或请求客户位置。

## 3. 单元（Cell）的严格语义与身份

**Deployment Unit / Cell** 指企业定义的、可以独立部署或承接流量、通常具备故障影响范围的业务拓扑单元。它可能是一个独立集群、同一集群里的若干工作负载，也可能横跨多个集群；这一关系由部署/调度平台决定。

**`datafox.unit.id` 不是 OTel 已标准化的字段。** 这是 Datafox v1 **候选扩展**，只有在确认当前产品存在 Cell 查询、发布和故障域定位需求后才进入正式协议。v1 不增加 `datafox.unit.name`、`datafox.unit.zone` 等额外字段；需要展示友好名称时可以由 Datafox 配置/后端目录关联。

建议将 Unit 的**作用域唯一键**定义为：

`(trusted_tenant_id, deployment.environment.name, logical_region_or_platform_location, datafox.unit.id)`。

其中 `logical_region_or_platform_location` 是 Datafox 后端维护的经审核位置标识；它不能通过字符串比较不同厂商的 `cloud.region` 生成。在未配置逻辑地域的单云项目中，位置可以由受信任的云账号/Region 或集群目录关联。**同一个 `unit.id` 可以在不同租户、地域或环境中重复使用**，查询时不得脱离作用域进行全局合并。

### 3.1 元数据来源与映射

由于用户已有的 Kubernetes Label 可能完全不同，不要求引入统一的 `datafox/unit` Label。推荐使用当前受控的发布配置或集群接入配置：

| 现有来源 | 建议适配 | 需要的验证 |
| --- | --- | --- |
| Helm/Kustomize/GitOps 中定义了 Unit | 部署模板将确定值注入标准 `OTEL_RESOURCE_ATTRIBUTES` 或 `resource.opentelemetry.io/datafox.unit.id` Annotation | 值与真实部署目标一致；Operator/SDK 兼容性检查 |
| 工作负载已有自定义 Cell Label | 在部署模板使用相同值生成 Resource 配置，保留原 Label | 无来源冲突，不能自动把所有同 Pod 容器都视为同一 Cell |
| 一个 Cluster 仅有一个 Cell，且映射由平台管理 | 在 **Collector 接入层**只添加明确授权的基础设施位置属性，或由 Backend 可信映射关联 | 不能据此覆盖 `service.*`；不能以客户端数据授权 |
| 同一 Cluster 中多个 Cell | 由每个工作负载的受控配置或精确、白名单式拓扑映射提供 | 不允许根据 Cluster 名自动猜 Unit |
| 非 Kubernetes 平台 | SDK/部署配置或 Backend 目录明确提供 | 使用相同逻辑 ID；不制造 `k8s.*` |

**何时属于“Collector 只补基础设施”的例外？** Cell 在本模型中属于**部署拓扑元数据**，不是服务身份。因此在显式的可信 Cluster/Workload→Cell 映射存在时，可以由 Collector 补全 `datafox.unit.id`；但这是一项需单独评审的配置，必须优先保留可信现有值、不猜测归属、不改写 `service.*`。无论来源如何，这些 Resource 值**均不负责 Datafox 租户权限校验**。

## 4. 发布时序：同一版本跨 Region/Cell 不等于一次部署

~~~mermaid
flowchart LR
    Release["Release<br/>order-service 2.4.1"] --> TokyoA["Deployment A<br/>AWS Tokyo / cell-a"]
    Release --> TokyoB["Deployment B<br/>AWS Tokyo / cell-b"]
    Release --> GcpC["Deployment C<br/>GCP Tokyo / cell-c"]
    TokyoA --> PoA["多个 Pod 实例"]
    TokyoB --> PoB["多个 Pod 实例"]
    GcpC --> PoC["多个 Pod 实例"]
~~~

每个 Deployment Event 在现有服务名、版本、环境、Cluster、Namespace/Workload 之外，**按已知情况**附带：

- `target.cloud.provider`、`target.cloud.region`、`target.cloud.availability_zone`：源自云平台事实，按 OTel 语义理解但作为 Datafox API 的 JSON 字段，不能宣称是 OTel Wire Contract。
- `target.region_id`（可选）：逻辑地域，须关联平台目录。
- `target.unit_id`（可选）：部署单元，须关联相应环境和位置。
- `target.cluster` / Cluster UID、`target.namespace`、`target.workload_name`：物理目标。

**API 字段命名是提案，不是已经实现的 JSON Schema。** Backend 不使用 `unit_id` 取代 Kubernetes Cluster ID，也不能把“目标单元”与客户端随意上报的 Unit 资源属性视为同一可信身份。每个单元的一次 Rollout 都有独立的 `deployment_id`；同一个 Release 跨单元多次部署需要多个 Deployment Event。

发布关联时，后端应利用可信发布目标、资源的 Service Version、实际 Pod/Cluster 身份与时间范围匹配。若 Unit 与 Cluster/Workload 映射冲突，保留遥测并标记“拓扑不一致”，不修改原始 `datafox.unit.id` 或伪造单元归属。

## 5. 查询、索引、基数与隔离

### 5.1 查询视图应能逐级收敛

推荐的用户视图：

**Tenant（隐式鉴权） → Service → Environment → Logical/Cloud Region → Unit → Cluster/Workload → Pod/Instance → Span/Metric/Log。**

Region 和 Unit 作为**可选维度**，不能导致没有 Cell 的普通服务无法查询。平台应允许按跨 Region/Unit 汇总，同时保留准确的细分维度。对于真正跨地域的 Trace，同一 Trace ID 可能涉及不同 Region/Unit；界面不应把 Trace 固定归到其第一条 Span 的 Region。

### 5.2 多租户安全不通过 Resource 实现

| 输入或行为 | 正确处理 |
| --- | --- |
| 另一租户发送与本租户相同的 `service.name` / `unit.id` | 后端隔离数据，两个逻辑实体独立 |
| 客户端伪造 `datafox.region.id` / `datafox.unit.id` | 只视为待校验的拓扑声明；不改变写入租户、权限或数据驻留策略 |
| 生产需要特定地域的数据驻留 | 由接入控制面 / 认证租户路由与后端区域部署策略执行，**不依赖**可伪造的 `cloud.region` |
| 同一 Tenant 有多个授权数据 Region | 查询层按授权跨区域组合结果，不默认把 Trace 和发布数据复制到其他地域 |
| 共享 Collector 承接多个 Tenant | 需要认证、出口隔离和可审计分区；不能仅依赖一个开放 OTLP Receiver 上的 Pod Label |
| 业务请求里的 customer_id / tenant_id | 动态请求属性，单独评估脱敏、ACL、采样及高基数成本；不默认成为 SDK Resource |

### 5.3 基数和一致性约束

`datafox.region.id`、`datafox.unit.id` 应为**低基数部署维度**；不接受每个请求或 Pod 随机生成一个 Unit。Metric 维度预算由指标管线决定；不无差别将所有 Resource 属性展开为每个 Metric 的数据点标签。Cluster UID、Pod UID 和实例 ID 仍是高基数基础设施身份，主要用于定位和查询 Drill-down。

禁止自动用 `k8s.namespace.name` 推导 Platform Tenant 或 `datafox.unit.id`；Namespace/Cluster 可以跨业务部署域复用。对 Unit/Region 映射缺失保留 unknown/not-associated 状态，不默认写 `default` 或从 Pod 名字符串猜测。

## 6. 边界示例

| 维度 | AWS Tokyo / cell-a | AWS Tokyo / cell-b | GCP Tokyo / cell-c |
| --- | --- | --- | --- |
| 平台 Tenant（认证） | t-acme | t-acme | t-acme |
| `service.namespace` | commerce | commerce | commerce |
| `service.name` | order-service | order-service | order-service |
| `deployment.environment.name` | production | production | production |
| `service.version` | 2.4.1 | 2.4.1 | 2.4.1 |
| `cloud.provider` | aws | aws | gcp |
| `cloud.region` | ap-northeast-1 | ap-northeast-1 | asia-northeast1 |
| `datafox.region.id`（可选） | jp-east | jp-east | jp-east |
| `datafox.unit.id` | cell-a | cell-b | cell-c |
| Kubernetes Cluster / Pod | 独立真实 UID | 独立真实 UID | 独立真实 UID |
| Release Deployment ID | dep-001 | dep-002 | dep-003 |

此例中 **Service 只有一个**，**部署实例有三个**。如果三个实例各自有不同的 `service.version`，仍不会创建新逻辑 Service，但版本分析要分开统计。三个单元可能承接不同客户流量；用户请求的业务 customer_id 不是表中 Platform Tenant ID。

## 7. 最小合同测试和演进

| 测试 | 输入与条件 | 预期 |
| --- | --- | --- |
| Topo-01 | 两个平台 Tenant 上报同名 Service、Region、Unit | 租户隔离，查询/Release Event 不交叉 |
| Topo-02 | 未认证请求伪造 `tenant_id` / `datafox.tenant.id` | 不获得对应 Tenant 的写入或读取权限 |
| Topo-03 | 同一 Service 跨云厂商 Region | `cloud.region` 保留厂商编码，逻辑 `datafox.region.id` 可以相同 |
| Topo-04 | 同 Region 多个 Cell | `datafox.unit.id` 可区分各 Cell，服务身份不变 |
| Topo-05 | 同一 Cell 覆盖多个 Cluster | 后端使用显式映射，不把 Cell 强制等同 Cluster |
| Topo-06 | 同一 Cluster 托管多个 Cell | 不能用 Cluster 名把全部业务归为一个 Cell |
| Topo-07 | 缺失 Unit 的普通服务 | 正常接收并查询，不伪造 Cell |
| Topo-08 | Client Resource 与受控拓扑映射冲突 | 原始遥测保留，关联结果标记冲突，不跨租户串数据 |
| Topo-09 | 同一 Release 跨三个 Cell 滚动发布 | 生成三个独立 Deployment ID，支持逐 Cell 回滚 |
| Topo-10 | 跨 Region 的分布式 Trace | 各 Span/Resource 位置可识别，跨区域查询遵守授权 |
| Topo-11 | 将业务客户 ID 放入全局 SDK Resource | 受管理接入预检按策略拒绝；保留按请求受控属性的可能性 |
| Topo-12 | 数据驻留要求与客户端伪造 `cloud.region` 冲突 | 数据路由按已鉴权配置而非可伪造 Resource 执行 |

上述测试均为**待实现的跨仓库合同测试**，不代表现有 Backend 支持相关隔离能力或安全机制。设计获批后应由 Backend、Collector 和 CI/CD 共同实现并形成可复现测试证据。

### 实施分层

- **第一阶段**：仅确认现有 OTel `cloud.*` / `k8s.*` 来源、多租户鉴权契约和 Unit 的实际产品需求；不为未来能力批量增加 Agent 配置。
- **第二阶段（确有多单元业务）**：引入明确命名空间的 `datafox.unit.id`，通过部署配置或可信拓扑映射传递；Backend 增加单元过滤和发布目标关联。
- **第三阶段（确有跨云逻辑地域需求）**：启用 `datafox.region.id` 与逻辑地域目录；保持云原生 `cloud.region` 原值；独立验证跨地域查询、权限和数据驻留。

## 参考资料与证据状态

- [OTel Cloud Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/cloud/) — 云厂商、账号、Region 和 AZ 的原生属性（当前 Development）。
- [OTel Kubernetes Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/k8s/) — Cluster UID、Pod UID、Workload 属性（部分 Stable）。
- [OTel Service Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/resource/service/) — 逻辑服务身份独立于环境与部署位置。
- [OTel Deployment Environment](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/) — 环境不是 Region，`deployment.id` 仍为 Development。
- [OTel Attributes Registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/) — 自定义属性须避免与标准字段语义冲突。

**已确认**：上述 OTel Registry 当前字段与其稳定性、现有 Datafox 项目 D1–D4 决策。**待评审**：`datafox.unit.id`、`datafox.region.id` 名称与类型、Backend 内部租户与区域目录、Release Event 拓扑字段、支持跨 Region 查询的业务需求。**尚未执行**：权限隔离测试、Region/Cell 采集、SDK/Collector 联调、Backend Event 合同测试或生产集群部署。
