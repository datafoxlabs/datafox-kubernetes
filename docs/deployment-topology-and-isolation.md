# Datafox 多租户、多地域与可选单元部署模型

> **状态：Architecture Proposal · 2026-10-31。** 本文件是 [统一标签规范](unified-tagging-convention.md) 的部署拓扑补充，与 [Kubernetes 系统架构](architecture.md) 共用服务身份和发布事件契约。
>
> **实施边界：** P0 确定可信租户、OTel 服务身份和标准 Region/Cluster 属性；P1 为存在单元化业务的服务提供**可选** `datafox.unit.id` 和发布事件 `target.unit_id`；P2 **暂缓**逻辑 Region、自建 Cell 注册中心、跨 Cluster/Region 拓扑目录和跨地域数据编排。
>
> 本文为数据模型与集成约束，不代表 Backend 隔离、Unit 查询、OTel SDK/Collector 配置或发布 API 已实现。**不注册或自动接受正式 RepoFoundry ADR。**

## 1. 为什么需要 Region 与 Cell 两个维度

同一逻辑服务 `commerce/order-service` 可以在 AWS Tokyo 的多个 Cell 和 GCP Tokyo 的另一个 Cell 中运行。三个实例可使用相同的 `service.version=2.4.1`，但灰度、故障影响范围与回滚节奏可能不同。

必须分别回答：谁有权查询（Tenant）、是什么服务（Service）、运行在哪里（Region/Cluster/Pod）、属于哪个流量或故障隔离单元（Cell）、是哪一次部署（Deployment）。

**这几类身份不得互相替代**：Tenant 不能从 `service.namespace` 推断，Region 不能写成 `deployment.environment.name`，Cell 不能写成 `k8s.cluster.name`。

### 1.1 层次与所有权

~~~mermaid
flowchart TB
    Auth["认证的 Datafox OTLP / Release API 入口"] --> Tenant["Trusted Platform Tenant"]
    Tenant --> Service["Logical Service<br/>service.namespace + service.name"]
    Service --> Env["Environment<br/>deployment.environment.name"]
    Env --> Location["Physical Location（可用时）<br/>cloud.region / k8s.cluster.uid"]
    Env --> Unit["Optional Cell<br/>datafox.unit.id"]
    Location --> Instance["Pod / Process"]
    Unit -. "通过工作负载部署事实关联" .-> Instance
~~~

图中的 Location 和 Cell 是两个**独立的维度**。一个 Cell 可以覆盖多个 Cluster，一个 Cluster 可以有多个 Cell；P1 不构建这些关系的通用目录，只在已有可信部署目标下关联实际 Workload。

## 2. P0 — 可信租户、服务身份和标准 Region

### 2.1 Datafox Platform Tenant 是权限边界

Datafox 的平台 Tenant ID 由**认证与服务端授权**确定，参与写入分区、查询过滤、发布事件关联和配额/保留策略。它属于 Backend 的可信上下文，**不要求作为 OTel Resource Attribute 发送**。

- 客户端写入 `tenant_id`、`datafox.tenant.id`、任意 Pod Label 或 Collector 用户自定义字段，都**不能**覆盖已认证的 Tenant。
- 未认证或未授权的输入应按入口契约拒绝，不得自动写入默认 Tenant。
- 多租户共享 Collector 的认证、出口路由及权限隔离需要独立验证；不能依靠 `service.namespace` 或开放的 OTLP Receiver 实施隔离。
- **被观测 SaaS 应用的客户租户**与 Datafox 平台 Tenant 不同。每个请求的 customer/account ID 属于可选的请求级业务上下文，不放到共享进程的全局 SDK Resource；隐私与高基数处理另行设计。

本节描述**必须满足的权限不变量**，不是当前 Backend 已通过安全测试的结论。

### 2.2 逻辑服务与部署环境

逻辑服务键为 `(trusted_tenant_id, service.namespace, service.name)`；`service.namespace` 可按 OTel 规范省略并以空命名空间参与身份处理。同一服务在不同 Environment、Region、Cell、Cluster、Pod 运行时，逻辑服务身份保持不变。

`deployment.environment.name` 是部署环境属性；没有启用环境比较的普通 OTel 服务可以省略它。**P1 启用 Cell 发布关联时必须明确 Environment**，避免同一 Unit 名称在 staging 与 production 中发生歧义。

### 2.3 复用标准云地域和 Kubernetes 属性

| 维度 | 标准属性 | 来源与约束 |
| --- | --- | --- |
| 云厂商 / 云账号 | `cloud.provider`、`cloud.account.id`（当前 OTel Development） | 保留厂商与账号原始语义；不是租户授权信息 |
| 云地域 / 可用区 | `cloud.region`、`cloud.availability_zone`（当前 OTel Development） | 保留云厂商原生值；不同云的 Region 编码不必相同 |
| Kubernetes 集群 | `k8s.cluster.uid`、`k8s.cluster.name`（Stable） | UID 辅助准确定位，Name 主要用于展示 |
| Workload / Pod | `k8s.deployment.name` 等、`k8s.pod.uid` | 按实际 Kubernetes 对象提取；不是单元标识 |

无云 Region 的自建机房服务可以保留该属性缺失状态，不强制注册 `datafox.region.id`。地域归并、IDC 目录与数据驻留是不同的产品需求，**P0/P1 不实现跨云逻辑地域归一化**。

数据驻留必须由受信任的入口/存储路由策略执行；不能根据用户可伪造的 `cloud.region` 决定权限或落盘地域。

## 3. P1 — Cell 是可选的一等部署维度

### 3.1 定义和最小属性

**Cell / Unit** 是企业定义、用于隔离业务流量或故障影响范围的稳定逻辑单元。它**可以**作为独立发布、灰度、扩容或回滚目标，但不要求具备全部这些能力。Cell 既不是 Availability Zone，也不是 Kubernetes Namespace、Deployment 或 Cluster 的别名。

Datafox v1 提议仅增加一个自定义 OTel Resource Attribute：

| 属性 | 类型 | 必需性 | 示例 | 意义 |
| --- | --- | --- | --- | --- |
| `datafox.unit.id` | string | **可选**；单元化业务启用 | `cell-a` | 稳定的业务流量或故障隔离单元 |

`datafox.unit.id` **不是 OTel 标准属性**。不要在 P1 同时增加 `datafox.unit.name`、`datafox.cell.id`、`datafox.unit.region` 等平行字段；Friendly Name 可以作为产品展示层配置，但不需要引入一个强制的注册中心。

**推荐的 P1 身份规则**：`datafox.unit.id` 在同一 **(可信 Tenant, Environment)** 内唯一标识一个 Cell。相同的字面名称如果表示两个不同 Cell，必须由部署系统提供不同 ID，而不是靠 Region/Cluster 字符串做隐式消歧。一个 Cell 可跨多个 Cluster；它是否跨云 Region 属于客户既有部署事实，P1 不据此创建复杂映射目录。

未使用 Cell 的普通应用**不设置该属性**，也不伪造 `default`、`unknown` 或单元目录项。缺失 Unit 不妨碍 Trace、Metrics、Logs 的标准 OTel 接入。

### 3.2 Cell ID 来源：优先使用已有部署配置

| 应用已有来源 | P1 适配方式 | 不应做的事情 |
| --- | --- | --- |
| OTel SDK 已显式提供 `datafox.unit.id` | 保留 Resource | 让 Collector 重写该属性 |
| Helm / Kustomize / GitOps / CI/CD 已有 Unit 变量 | 转成受支持的 `OTEL_RESOURCE_ATTRIBUTES` 或 `resource.opentelemetry.io/datafox.unit.id` | 要求业务修改所有 Kubernetes Label |
| 企业已有 Cell Label | 在部署模板阶段读取并映射到 Resource，保留原 Label | 让 Operator 自动识别任意企业键 |
| 仅能在可信 Cluster/Workload 上判断 Cell | 按需使用明确的单元级部署配置；后续可评估 Collector 可信拓扑补全 | P1 默认引入 Cluster→Cell 注册/映射服务 |
| 无 Unit 的业务 | 不设置 `datafox.unit.id` | 根据 Namespace、Cluster 或 Pod 名猜测 Cell |

Collector 仍以补充**基础设施属性**为主要职责。P1 **不要求** Collector 实现自定义 Cell 检测器；确有可信的 Workload→Cell 映射时可单独评审静态配置扩展，但不得修改 `service.*` 或凭 Unit 值授权。

对于启用 Operator 自动注入的工作负载，`OTEL_RESOURCE_ATTRIBUTES.valueFrom`、`envFrom` 等已知兼容性风险仍按 [实施手册](implementation-and-verification.md) 的发布前检查处理；不能因为新增 Unit 反而强制 Agent 或 SDK 添加运行时 Kubernetes API Client。

## 4. Release Tracking：同一 Release 在不同 Cell 可分别部署

~~~mermaid
flowchart LR
    R["Release<br/>order-service 2.4.1"] --> D1["Deployment A<br/>cell-a"]
    R --> D2["Deployment B<br/>cell-b"]
    D1 --> P1["实际 Workload / Pods"]
    D2 --> P2["实际 Workload / Pods"]
~~~

Release 代表软件制品，Deployment 代表**一次发布尝试**。同一 Release 在不同 Cell 上独立灰度时使用不同 `deployment_id`，每条部署事件记录真实环境、Cluster、Namespace/Workload 和状态。

Datafox Release Event API **提议**增加可选的 `target.unit_id`。该值来自已经确认的部署目标，应与工作负载实际 `datafox.unit.id` 对齐；没有启用 Cell 的发布不需要填该字段。事件的 Tenant Scope 始终来自发布 API 的可信认证上下文。

| 情况 | 正确的发布表示 |
| --- | --- |
| 单环境、无 Cell | 原有 `deployment_id` + Target；`target.unit_id` 不存在 |
| 同一 Release 顺序发布 cell-a、cell-b | 两个 Deployment ID，同一个 Release ID |
| cell-b 回滚到旧版本 | 新的 Deployment ID、目标 cell-b、引用原 Deployment，原事件历史保持不变 |
| Release Event Unit 与 Resource Unit 不一致 | 记录拓扑冲突，保留原始遥测，不覆盖任一来源 |
| 同一个 Release 被发布到两个云 Region | 仍是不同 Deployment；Region 采用实际标准云/Cluster 属性，不需要 `datafox.region.id` |

发布事件 API 和状态机仍由 Backend 负责；本仓库只定义字段契约及联调测试。

## 5. 查询、安全与基数边界

Datafox UI 的基本查询维度为：

**已授权 Tenant → Service → Environment → 可选 Cloud Region → 可选 Unit → Cluster/Workload → Pod/Instance**。

Region 和 Unit 不参与创建新的逻辑 Service；同一个 Trace 可跨多个 Unit，不能把完整 Trace 绑定到第一条 Span 所在 Cell。基础设施指标、Node Metrics 不应凭同 Cluster 的某个应用 Unit 被重新标记。

`datafox.unit.id` 应是**低基数的部署维度**，不能为每次请求、每个 Pod 或每位客户随机生成。Metric 聚合应按明确的维度预算进行，不自动将所有 Resource 属性扩展成数据点标签。

**授权与数据驻留**由认证、租户上下文和区域入口/存储策略实施。OTLP Resource 中的 `datafox.unit.id` 或 `cloud.region` 是关联事实，不能成为授予访问权限或跨地域复制数据的依据。

## 6. 交付顺序与非目标

| 阶段 | 交付范围 | 明确暂缓 |
| --- | --- | --- |
| **P0 — 必须** | Tenant 可信鉴权边界；标准 OTel 服务身份、环境、版本；标准云/集群属性和缺失处理 | 自定义 Region；Cell 必填；跨地域管理系统 |
| **P1 — 有单元需求时** | 可选 `datafox.unit.id`；部署配置注入；可选 Release Event `target.unit_id`；Unit 查询过滤与分组 | Cell 注册中心、通用映射 DSL、Agent 内 Cell Detector |
| **P2 — 需求驱动** | 必须有跨云逻辑地域/复杂映射的实际业务证据，才单独设计 `datafox.region.id`、Cell/Cluster 目录及跨区域编排 | 默认预装、提前定义全套运行时扩展 |

P1 的 Cell 是**一等查询与部署维度**，但不是一个独立于客户平台、必须由 Datafox 接管生命周期的 Kubernetes 资源。产品可先读取稳定 Unit ID 做查询、按单元比较错误率/延迟和关联发布，不需要管理 Cell 创建/删除。

P2 的 `datafox.region.id` **尚不构成正式属性契约**；如果后来确实存在 IDC/跨云 Region 归并需求，应重新评审名称、语义、范围、迁移和安全策略。

## 7. 需要实际执行的合同测试

| 测试 | 场景 | 预期 |
| --- | --- | --- |
| Topo-01 | 两个平台 Tenant 上报同名 Service、Unit | 隔离数据、查询与发布事件 |
| Topo-02 | 客户端伪造 `tenant_id` / `datafox.tenant.id` | 不得改变 Backend 授权或落盘归属 |
| Topo-03 | 同 Service 跨云 Region | 保留原生 `cloud.region`，无需 `datafox.region.id` |
| Topo-04 | 同环境两个不同 Cell | `datafox.unit.id` 可区分，Service 身份相同 |
| Topo-05 | 一个 Cell 覆盖两个 Cluster | Unit ID 相同仍可按 Cluster 下钻，无注册中心 |
| Topo-06 | 同 Cluster 承载两个 Cell | 分别按工作负载配置 Unit，不按 Cluster 猜测 |
| Topo-07 | 普通服务没有 Cell | 接收、查询正常，不产生伪造 Unit |
| Topo-08 | SDK Unit 与 Release Event 目标冲突 | 保存原始数据并报告关联歧义 |
| Topo-09 | 同 Release 在两个 Cell 发布、单 Cell 回滚 | 不同 Deployment ID，保留完整历史 |
| Topo-10 | 跨 Region / Cell 的分布式 Trace | 各 Span 的 Resource 身份保留，不按首 Span 统一归属 |
| Topo-11 | 业务 customer_id 被误用为全局 Resource | 受管理接入预检按策略处理，防止高基数与隐私问题 |
| Topo-12 | 客户端伪造 `cloud.region` 企图改变驻留区域 | 后端路由以可信策略为准，不受 Resource 影响 |

Topo-01–Topo-03 和 Topo-12 是 **P0 安全与语义合同**；Topo-04–Topo-10 是 **P1 可选 Cell 功能启用时的合同**；复杂跨云逻辑地域的拓扑目录不进入 P0/P1 测试门禁。全部测试**尚未执行**，需要后续 CI/Backend/Collector 证据。

## 8. 源码依据与未验证事项

- [OTel Service Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/resource/service/) — Service 与 Instance 身份。
- [OTel Cloud Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/cloud/) — 云厂商原生 Region/AZ。
- [OTel Kubernetes Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/k8s/) — Cluster、Workload、Pod 元数据。
- [OTel Deployment Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/) — Environment 与部署字段的演进。
- [OTel Operator Resource Attributes（固定快照）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md) — 注入时的 Resource 来源与优先级。

**已形成架构决策方向**：P0 只复用标准身份与可信租户，P1 允许单个可选 Unit 属性，P2 需求驱动。**仍待评审/实现**：Unit ID 的实际业务来源、Backend 的查询与 Release API 字段、跨地域授权与数据驻留。**未执行**任何 Kubernetes/SDK/Collector/Backend E2E 或权限测试。
