# Datafox Kubernetes Metadata & Release Integration — 系统架构

> **状态：Architecture Proposal · 2026-10-30**  
> **读者：** Datafox 平台、Java Agent、Kubernetes 和 APM Backend 的设计与实现人员。  
> **范围：** Kubernetes 中跨语言的应用身份注入、基础设施元数据补全和部署事件关联。  
> **决策状态：** D1–D4 已在产品架构评审中确认；尚未注册为 RepoFoundry 正式 ADR，也未完成运行时验收。
>
> **标签语义与数据模型优先**：[Datafox Unified Tagging Convention](unified-tagging-convention.md) 是本方案待评审的跨语言字段契约。本文使用其中的字段来说明系统结构；在该规范被评审前，本架构仍不能作为已经批准的字段兼容性承诺。
>
> 本文描述目标系统的结构、依赖、接口和失败边界。**具体 YAML、构建命令、上线步骤、回滚操作与 44 项测试用例**由 [实施与验证手册](implementation-and-verification.md) 维护，避免两个文件重复保存操作细节。

## 1. 设计目标：让跨语言遥测具备统一的服务、运行位置和发布身份

设想 `order-service` 从 `2.4.0` 滚动升级到 `2.4.1`：两个版本可能在同一个 Kubernetes Deployment 的不同 Pod 上同时运行。Java、Python、Node.js、.NET 和 Go 服务都可能产生 Trace。Datafox 必须分别回答：

- **它是什么应用？** 服务名、服务命名空间、应用版本。
- **它运行在哪里？** Cluster、Namespace、Workload、Pod、必要时 Container。
- **它属于哪次交付？** Git Commit、镜像 Digest、部署目标、开始与结束事件。

这三组事实来自不同的系统，生命周期也不同。服务版本属于**应用制品身份**，Pod 属于**运行实例**，Deployment Event 属于**交付历史**。把三者合并成一个标签，会在滚动升级、回滚、跨环境发布或同版本重复部署时产生错误归因。

**设计主张：应用身份在 SDK Resource 中确定；Kubernetes 拓扑由 Collector 补充；CI/CD 负责发布事实。** Datafox 只在平台配置与 Backend 建立这些事实之间的契约，不为每种语言重新实现 Kubernetes 探测。

### 1.1 目标与验收语义

| 目标 | 对外可观察的结果 |
| --- | --- |
| 多语言一致 | 同一应用版本在不同语言中最终导出一致的标准 `service.*` Resource 属性 |
| 版本保真 | 用户显式版本被保留；Collector 不写入或覆盖应用身份 |
| Pod 可追踪 | 遥测可通过可信 Pod 身份关联到正确的 Kubernetes Workload |
| 发布可追溯 | 同一软件版本的多次部署、蓝绿和回滚具有独立的 Deployment 身份 |
| 业务优先 | 未启用注入的工作负载不被增加业务容器变更；注入失败可检测、可停止扩量、可回滚 |
| 上游可升级 | Operator、Collector 和语言 SDK 通过官方配置与 OTLP 契约集成，不 Fork 其运行时 |

本架构**不承诺** Agent 对业务“零开销”或“永不影响启动”。Admission、Agent 启动及业务性能必须分别验证，才能决定是否允许生产扩量。

### 1.2 范围和非目标

**本仓库**计划交付 Operator/Collector 安装配置、Datafox Java 自动注入镜像封装、多语言样例、版本来源预检、Helm 与端到端测试。仓库不运行一个额外的 Datafox Kubernetes Controller。

**外部职责**：`datafox-java-agent` 负责 Java Instrumentation Distribution；其他语言优先复用官方 OpenTelemetry Instrumentation / SDK；Datafox Backend 实现 Release Tracking API、持久化和版本分析。

v1 不引入自研 Admission Webhook、Operator/Collector Fork、Java 内置 Kubernetes Client、Collector 服务版本覆盖、Kubernetes Deployment Watcher、默认特权 Go eBPF 注入，也不自动部署到生产集群。非 Kubernetes 接入继续通过标准 OTel SDK/Resource 配置实现。

## 2. 系统模型：两条控制路径，一条遥测数据路径

### 2.1 参与者与部署单元

| 参与者 | 所在位置 / 对象类型 | 负责 | 明确不负责 |
| --- | --- | --- | --- |
| CI/CD / GitOps | 集群外发布控制系统 | 制品、Pod Template、版本校验、发布事件 | 采集业务 Span |
| OpenTelemetry Operator | 集群内 Controller 和 Admission Webhook | 在 Pod 创建时注入 Agent 文件与 SDK 配置 | 在应用请求中持续参与执行 |
| `Instrumentation` CR | Kubernetes 配置对象 | 定义语言 Agent 镜像、通用 SDK/Exporter 选项 | 保存发布历史或运行时指标 |
| 业务 Pod 内的 SDK / Agent | Java、Python、Node.js、.NET、Go 等应用进程 | SDK Resource、Span/Metric/Log 和 OTLP 导出 | 反查 Kubernetes Deployment 生命周期 |
| OTel Collector | 集群内 Gateway 或 Agent/Gateway 组合 | 接收 OTLP、关联 Pod、补充基础设施属性、转发 | 改写 `service.name` / `service.version`，或确认一次发布成功 |
| Datafox Backend | Datafox 独立服务 | 处理 OTLP、保存发布事件、提供查询与关联 | 对业务 Pod 执行 Mutation |
| Kubernetes API Server | Kubernetes 控制面 | 调用 Webhook、创建 Pod、提供工作负载元数据 | 决定业务服务版本含义 |

这里的 **Resource** 是 OpenTelemetry 中与一组遥测关联的属性集合，不是一个 Kubernetes Pod，也不是独立部署的组件。**Release** 是已构建的软件制品身份；**Deployment** 是某个 Release 面向某个环境的一次部署尝试；**Pod** 是当时实际运行该制品的实例。

### 2.2 系统上下文和数据所有权

~~~mermaid
flowchart TB
    subgraph Delivery["发布控制面"]
        CI["CI/CD / GitOps"]
        Template["Pod Template<br/>版本 Label / Annotation"]
        CI --> Template
    end

    subgraph Kubernetes["Kubernetes 控制面"]
        API["Kubernetes API Server"]
        Operator["OpenTelemetry Operator<br/>Pod Mutating Webhook"]
        K8sMeta["Kubernetes API<br/>Pod / Owner Metadata"]
        Template -->|"创建 / 更新工作负载"| API
        API <-->|"Pod CREATE Admission"| Operator
    end

    subgraph Runtime["业务运行与遥测数据面"]
        SDK["业务 Pod 内<br/>Language SDK / Agent"]
        Collector["OpenTelemetry Collector<br/>k8sattributes"]
        API -->|"已准入的 PodSpec"| Kubelet["Kubelet / Pod Startup"]
        Kubelet -->|"拉取镜像、Init、启动"| SDK
        SDK -->|"OTLP + SDK Resource"| Collector
        K8sMeta -->|"Watch / Cache"| Collector
    end

    subgraph Backend["Datafox Backend"]
        Ingest["OTLP Ingestion"]
        Release["Release Tracking"]
        Query["版本查询 / 部署关联"]
        Ingest --> Query
        Release --> Query
    end

    Collector -->|"Enriched OTLP"| Ingest
    CI -->|"Deployment Events"| Release
~~~

图中 **Pod Admission** 发生在新 Pod 创建时，**遥测导出**发生在业务进程运行时，**发布事件上报**发生在 CI/CD 交付过程中。三者互不替代。

系统有两条控制路径：

1. **配置控制路径**：CI/CD → Kubernetes API Server → Operator Webhook → 新 Pod 的 SDK/Agent 配置。Operator 仅参与创建阶段；运行时不依赖它逐次注入属性。
2. **交付事实路径**：CI/CD → Datafox Release Tracking。它保存部署尝试及其状态，不经过 Collector。

**数据路径**为应用 SDK/Agent → OTLP → Collector → Datafox Ingestion。Collector 独立从 Kubernetes API 获取 Pod/Owner 信息；它根据传入遥测的 Pod 身份进行补全，而不通过修改应用 Pod 写回元数据。

### 2.3 本仓库与外部系统的依赖方向

~~~mermaid
flowchart LR
    Integration["datafox-kubernetes<br/>Helm / CR / Tests"] -->|"配置与镜像适配"| Upstream["OTel Operator / Collector"]
    Integration -->|"Java 注入镜像封装"| Java["datafox-java-agent<br/>最终 Agent JAR"]
    Integration -->|"事件格式与联调测试"| Backend["datafox-backend<br/>Release API"]
    Upstream -->|"标准 OTLP"| Backend
~~~

这是**工程与运行时的依赖关系示意**，不表示三个代码仓库之间必须形成编译依赖。Datafox Kubernetes Integration 持有部署与集成配置；Java Agent 和 Backend 都维持各自的发布及兼容性边界。

## 3. 契约一：在 Pod 创建时确定应用身份

本节聚焦 **Operator/SDK 的运行时职责**；属性名称、数据类型、Kubernetes Label/Annotation 映射、服务身份定义和跨信号规则的唯一维护位置为 [统一标签规范](unified-tagging-convention.md)。

### 3.1 版本来源与优先级

本设计保留 **D1：推荐使用标准 Pod Label + OTel Resource Annotation** 的架构决策。标准字段是默认接入路径，**不是强制的 Kubernetes 标签命名政策**。企业自定义 Label 可由已有 Helm、Kustomize 或 CI/CD 模板转换为标准 Resource Annotation；已显式提供 OTel SDK Resource 的应用不需要为 Datafox 添加重复 Label。[字段规范与适配路径](unified-tagging-convention.md)。

| 层级 | 来源 | 作用 |
| --- | --- | --- |
| 1 | 用户显式 `OTEL_RESOURCE_ATTRIBUTES` / `OTEL_SERVICE_NAME` | 保留已明确设置的应用身份 |
| 2 | Pod Annotation `resource.opentelemetry.io/service.version` | 发布场景中的显式版本覆盖 |
| 3 | Pod Label `app.kubernetes.io/version` | 默认应用版本 |
| 4 | Operator 其他推导（例如镜像 Tag） | 上游兜底行为；**不作为 Datafox 生产版本契约** |

启用 `Instrumentation.spec.defaults.useLabelsForResourceAttributes` 才会采用相关标准 Label。上游 Operator 的 Resource 选择是**逐属性**处理；表格属于 Operator 注入阶段的规则，不能直接推断所有语言 SDK 内其他 Resource Detector 的合并顺序。[上游依据：Resource Attributes](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)。

**启用受管理 Release Tracking 的发布**必须由 CI/CD 在最终配置中验证稳定版本来源，可能来自标准 Label、自定义 Label 的部署时映射、OTel Annotation 或应用显式配置；缺失时按发布策略拒绝扩量。普通 OTel 遥测允许版本缺失并保留未知状态。Datafox 不另加阻断 Pod 创建的自定义 Webhook；Collector 不从 Image Tag 生成 `service.version`。

### 3.2 稳定服务身份不能依赖 Helm Release 名

Datafox Backend 的逻辑服务键定义为 **`(tenant, service.namespace, service.name)`**。`deployment.environment.name`、`k8s.namespace.name` 和 Cluster 属于部署维度，不参与同一业务服务的默认命名。

例如，一个 `order-service` 在 `commerce-staging` 和 `commerce-prod` 两个 Kubernetes Namespace 运行。如果希望跨环境查询同一业务服务，必须使两个应用的 `service.namespace=commerce`、`service.name=order-service` 保持一致。

特别需要验证：Operator 支持从 `app.kubernetes.io/instance` / `app.kubernetes.io/name` 推导 `service.name`；前者可能是 Helm Release 名。两者不同且没有显式服务名时，**受管理发布追踪**必须要求明确业务身份；普通遥测接入保留上游的实际值并报告命名歧义，而不是强制更改企业 Helm Label。`service.namespace` 的上游缺省推导可以来自 Kubernetes Namespace，因此跨环境的逻辑命名空间应显式提供。[上游依据：Operator Resource Attributes](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)。

### 3.3 多语言适配契约

| 应用类型 | 注入形态 | SDK Resource 的实际创建者 |
| --- | --- | --- |
| Java | Datafox Java Agent 注入镜像 + Operator `inject-java` | Datafox Java Agent 所复用的上游 OTel SDK |
| Python | 上游 Auto Instrumentation + Operator `inject-python` | Python OTel SDK |
| Node.js | 上游 Auto Instrumentation + Operator `inject-nodejs` | Node.js OTel SDK |
| .NET | 上游 Auto Instrumentation + Operator `inject-dotnet` | .NET OTel SDK |
| Go（已集成 SDK） | Operator `inject-sdk` | 业务初始化的 Go OTel SDK |
| 其他已集成 SDK | SDK-only 或显式配置 | 业务 SDK |

**自动埋点注入**与 **SDK-only 配置注入**是两种独立能力。`inject-sdk` 不会安装 SDK，也不会凭空生成 Span。Go 手动初始化 Resource 时需要显式读取环境配置，例如使用上游 `resource.WithFromEnv()`；不默认启用需要额外权限的 Go eBPF 自动埋点。[上游依据：SDK-only](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/languages/sdk-only.md)。

Datafox Java Agent 仅负责自己的 Java Instrumentation Distribution。Operator 使用的自定义 Java 注入镜像需要提供可读的 `/javaagent.jar` 和文件复制命令；具体 Dockerfile、构建来源及镜像 Digest 由实施手册和发布流水线定义。[上游依据：Java 注入镜像](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/autoinstrumentation/java/Dockerfile)。

## 4. 契约二：Collector 只丰富基础设施元数据

本设计的 **D3** 将服务身份与 Kubernetes 拓扑信息分开维护。

| 数据 | Source of truth | 进入遥测的位置 | 不变量 |
| --- | --- | --- | --- |
| `service.name`、`service.namespace`、`service.version` | 应用显式配置、Operator 的受控注入 | 应用 SDK Resource | Collector 不覆盖 |
| `deployment.environment.name` | 应用/平台环境声明 | 应用 SDK Resource | 不用 Kubernetes Namespace 代替 |
| `k8s.pod.uid` | Kubernetes Pod UID | Operator 可通过 Downward API 提供，Collector 可确认/补充 | 关联正确 Pod，禁止凭不可靠 IP 强行归因 |
| `k8s.pod.name`、`k8s.namespace.name`、`k8s.deployment.name`、`k8s.node.name` | Kubernetes API / 对象 Owner | Collector `k8sattributes` 补充 | 不改变已有服务身份 |
| `container.*` 与镜像属性 | Kubernetes Container 状态 | Collector 可选补充 | 多容器场景需要容器身份 |
| Git SHA、Image Digest、部署状态 | CI/CD 发布系统 | Release Tracking 记录 | 不强制复制到每个 Span |

Operator 上游也可能提前注入部分 `k8s.*` 属性；因此这里的“Collector 是基础设施补全层”表示**责任与覆盖边界**，不意味着 SDK Resource 绝不能包含 Pod UID 等基础设施属性。

`k8sattributes` 通过 Kubernetes API 建立 Pod 元数据缓存，并按照配置的匹配规则关联接收到的 Resource。推荐匹配顺序为 **Pod UID → Pod IP → 连接 IP**。经过代理或多级 Collector 转发后，连接 IP 可能不再代表业务 Pod；最接近应用的入口应在可能的情况下使用 Pod UID 完成关联。仅凭 Pod UID 不能区分同 Pod 的两个业务容器，镜像/容器属性还需 `k8s.container.name` 或 `container.id`。[上游依据：k8sattributes](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md)。

### 4.1 单层与多层 Collector

- **单层 Collector Gateway**：应用携带可靠的 Pod UID 后，Gateway 可以完成 Pod 关联和补全；在 Pod 身份不足时必须显式暴露元数据缺失。
- **Agent Collector → Gateway**：靠近应用的第一层完成 Pod 关联，转发已补全的 OTLP；后续 Gateway 保留这些 Resource 属性，不把上游连接 IP 误当业务 IP。

这属于可选部署形态，v1 不强制引入第二层 Collector。是否采用 DaemonSet / Gateway 由实际网络与吞吐条件验证决定。Collector 的 Batch、Retry、Queue 和存储能力属于遥测可靠性设计，不应把“基础设施补全失败时保留原始遥测”理解成“Exporter 不会丢数据”。

## 5. 契约三：Release Tracking 保存独立的部署事实

本设计的 **D4** 要求 CI/CD 主动上报 Deployment Event。Backend 不从 Kubernetes Pod 创建时间或第一条 Span 推断真实发布开始与完成时间。

~~~mermaid
erDiagram
    SERVICE ||--o{ RELEASE : builds
    RELEASE ||--o{ DEPLOYMENT : deploys
    DEPLOYMENT ||--o{ DEPLOYMENT_EVENT : records

    SERVICE {
        string tenant
        string service_namespace
        string service_name
    }
    RELEASE {
        string release_id
        string service_version
        string git_commit
        string image_digest
    }
    DEPLOYMENT {
        string deployment_id
        string environment
        string cluster
        string k8s_namespace
        string workload
        string status
    }
    DEPLOYMENT_EVENT {
        string event_id
        string type
        datetime occurred_at
    }
~~~

这个 ER 图表达**逻辑关系**，不预设 Backend 的数据库表结构。一个 Release 可以部署多次；相同 `service.version` 不保证 Git SHA 或 Image Digest 完全相同，因此不能单凭版本字符串合并 Release 或 Deployment。

### 5.1 发布 API 的边界

Backend 提供独立于 OTLP 的 Datafox Release API，最小交互是 `deployment.started`、`deployment.succeeded`、`deployment.failed`，回滚通过**新的 Deployment ID** 恢复旧 Release，并用引用关系关联原 Deployment。

Backend 需要在租户范围内验证 `event_id` 幂等、`deployment_id` 稳定身份、乱序事件和冲突终态。事件上报认证与 OTLP Ingestion 认证隔离；敏感配置不得作为发布事件载荷。具体状态转移表、`409`/`422` 语义和示例 JSON 在 [实施手册第 5.2 节](implementation-and-verification.md) 中定义。这是**拟实现的 Datafox API 契约**，不是 OpenTelemetry 标准。

### 5.2 版本级查询与部署级归因必须分开

按 `(tenant, service.namespace, service.name, service.version, environment)` 查询 Trace，能够做版本级聚合；但在蓝绿发布、滚动升级、同版本多次部署和跨 Cluster 复用版本时，不能仅按版本字符串唯一反查 Deployment。

部署级关联需要更强的运行时证据：Cluster、Workload、Pod UID、Image Digest、事件时间窗口等。缺少这些证据时，Backend 必须保留多个候选或返回“无法唯一关联”，不能默默选择时间上最近的一次发布。

v1 的最小能力为**版本级查询 + 带环境/集群维度的候选部署关联**；严格的 Pod→Deployment 唯一归因属于后续可验证扩展。

### 5.3 多租户、多地域、多单元是独立的部署拓扑

Datafox 服务身份与物理部署、故障隔离和租户权限必须拆开：

- **租户隔离**由 Backend 的认证租户上下文确定，不允许 SDK/Collector 传入的任意 Resource Attribute 改变存储分区或读取授权。
- **部署位置**使用 OTel `cloud.region`、`cloud.availability_zone`（当前 Development）与 `k8s.cluster.uid`（Stable）等标准属性；不能把 `deployment.environment.name` 当作 Region。
- **业务单元（Cell）**是可选的一等部署维度。仅在存在稳定的流量/故障隔离单元时启用 `datafox.unit.id`（Datafox 自定义属性提案），按 `(tenant, environment, unit.id)` 保持唯一；不要求所有语言 Agent 开发 Cell Detector。
- **Release/Deployment 关系**：同一服务的相同版本在不同 Region/Cell 独立发布，是同一逻辑服务对应多个 Deployment。启用 Cell 时，Release API 可选增加 `target.unit_id`；无 Cell 发布无需此字段。不同发布尝试分配独立 Deployment ID。

**实施顺序**：P0 复用 OTel 标准 Region/Cluster 属性并建立 Tenant 鉴权约束；P1 仅提供可选 `datafox.unit.id` 和发布 `target.unit_id`；P2 有真实跨云归一化需求时才重新评审 `datafox.region.id` 和复杂拓扑目录。一个 Cell 可以跨多个 Cluster，一个 Cluster 可以包含多个 Cell；P1 不建设 Cell 注册中心。完整身份边界见 [多租户、多地域、多单元部署模型](deployment-topology-and-isolation.md)。

## 6. 一次滚动发布如何贯穿三条路径

下图使用 `order-service:2.4.0 → 2.4.1` 作为教学案例；它说明期望的因果次序，不保证所有上游实现都按图中单一时序串行执行。

~~~mermaid
sequenceDiagram
    participant CI as CI/CD
    participant API as Kubernetes API Server
    participant OP as OTel Operator
    participant Node as Kubelet
    participant App as order-service SDK
    participant COL as OTel Collector
    participant DF as Datafox Backend

    CI->>CI: 校验最终 Pod Template 的版本与注入兼容性
    CI->>DF: deployment.started
    CI->>API: 提交包含版本 Label 的 Deployment
    API->>OP: 新 Pod CREATE AdmissionReview
    alt opt-in 且 Webhook 正常
        OP-->>API: 返回环境变量和 Agent Init Container Patch
    else 未 opt-in 或 Webhook fail-open
        OP-->>API: 无注入变更或跳过失败 Webhook
    end
    API-->>Node: PodSpec 已准入、调度到 Node
    Node->>App: 拉镜像、执行 Init Container、启动业务进程
    App->>App: SDK 初始化 Resource
    COL->>API: 独立 Watch / Cache Pod 元数据
    App->>COL: OTLP（service.version=2.4.1）
    COL->>DF: OTLP（补充 k8s.*）
    CI->>CI: 依据 Rollout 实际结果检查成功或失败
    CI->>DF: deployment.succeeded 或 deployment.failed
~~~

这条流程有四个需要单独验证的观察点：

1. **发布前**：CI 检查版本来源、稳定服务名、目标容器和环境变量兼容性，不把非法输入交给生产 Admission。
2. **Pod 创建后**：最终 Pod Spec 确认是否实际注入 Agent/SDK 配置；Pod Ready 不等于注入成功。
3. **遥测到达后**：SDK Resource 和 Collector 输出的服务版本一致，Pod UID 关联正确，旧版与新版 Trace 同时存在且可区分。
4. **部署结束后**：CI/CD 按实际发布系统状态上报结果；未收到事件时，遥测仍可查询，但部署历史显示不完整。

## 7. 可靠性与安全边界：业务不中断优先

**D2：复用 Operator** 不意味着对 Kubernetes 创建流程零风险。必须区分三种故障位置：

| 失败阶段 | 影响范围和具体行为 | 架构处理原则 |
| --- | --- | --- |
| Admission Webhook 不可达 | 在所核对的 Operator 快照中，Pod Webhook 使用 `failurePolicy: Ignore`；Pod 可绕过注入继续创建 | 保留业务创建；检测 Agent/Resource 注入缺失，停止继续扩大启用范围 |
| Webhook 返回非法 Patch / Mutation 成功后启动失败 | Pod CREATE 仍可能被 Kubernetes 校验拒绝；Agent Image、Init Container 或 JVM 选项可能导致 Pod 不 Ready | 生产发布前兼容性校验 + Kind 负面测试 + Canary；失败后停止扩量并回滚 Pod Template |
| Collector / OTLP Exporter 失败 | 可能缺失基础设施属性、丢失遥测或产生排队压力；业务进程不应依赖遥测成功才能继续处理请求 | 以 OTel SDK/Exporter 合理的非阻塞配置与明确资源预算为基础，独立监测数据质量和业务 SLO |

### 7.1 Webhook 的匹配范围与 Mutation 范围不同

在固定源码快照中，Pod CREATE MutatingWebhook 的规则并未按 Datafox opt-in Annotation 缩小 API Server 调用范围。**无注入 Annotation 不等于该 Pod 不经过 Webhook**；它只表示 Operator 不应给该容器应用语言 Instrumentation。

生产安装前检查实际 `MutatingWebhookConfiguration` 的 Selector、Timeout、Failure Policy 和多个 Webhook 的交互，并测量未启用注入 Pod 的创建延迟。`failurePolicy: Ignore` 也不能让 API Server 接受 Webhook 已返回的非法 Pod Patch。[上游依据：Webhook Handler](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/webhook/podmutation/webhookhandler.go)、[Manifest](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/config/webhook/manifests.yaml)。

### 7.2 发布前配置兼容性是入口约束

上游 Operator 对已有 `OTEL_RESOURCE_ATTRIBUTES` 环境变量可能在原 `value` 后追加属性。如果它原本来自 `valueFrom`，则可能形成 Kubernetes 不允许的非空 `value` + `valueFrom` 组合，**直接阻断 Pod CREATE**。`envFrom` 内的同名键也可能被显式 `env` 注入遮蔽。对于 Java，`JAVA_TOOL_OPTIONS.valueFrom` 可能触发 Operator Mutation 错误，使 Pod 无 Agent 启动。[上游依据：SDK 注入](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go#L502-L566)、[Java 注入](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/javaagent.go)。

因此 Datafox 预检只针对**启用注入的目标容器**：检查最终渲染 Pod Template 的 `env` / `envFrom` / `valueFrom`、ConfigMap/Secret 的实际键集合和来源一致性；无法证明兼容时拒绝**本次自动注入发布**，不拒绝未启用注入的业务。具体支持矩阵和错误测试位于实施手册第 3.1.1 节。

### 7.3 生命周期边界与回滚

Pod Mutation 在创建时生效，不会在 Operator 恢复后自动修改已经运行的 Pod。移除注入 Annotation 也不会撤销既有 Pod 的 Agent。回滚必须通过新 Pod 的受控重建完成，并确认原业务镜像、探针、启动参数和流量健康。

Datafox 不因缺少遥测自动删除业务 Pod，不在 v1 引入“埋点失败则阻断 Pod”的 Admission 策略；同时必须通过告警和发布门禁防止 fail-open 导致的**静默覆盖率缺失**。生产上线必须具备可测的 Canary/回滚规则，不能用单一的 Pod Ready 作为成功证据。

## 8. 决策依据与架构取舍

四项产品决策在此文档内记为 D1–D4；其名称不是 RepoFoundry 正式 ADR 编号。

| 决策 | 采用方案 | 不采用的替代方案 | 取舍 |
| --- | --- | --- | --- |
| D1 版本来源 | 推荐标准 Pod Label / Annotation，允许企业自定义来源部署时映射；显式 SDK Resource 优先 | 每种语言独立检测 Manifest / Image | 统一最终 OTel 属性，不强制 Kubernetes Label 命名 |
| D2 自动注入 | 复用上游 OTel Operator，按目标工作负载 opt-in | Datafox 自研 Admission Webhook | 避免重复工程，但需要接受/验证上游版本兼容性和 Webhook 故障范围 |
| D3 基础设施元数据 | Collector `k8sattributes` 补全 | Agent 内调用 Kubernetes API；Collector 改写服务版本 | 降低语言与权限耦合；要求 Pod 身份可靠，缺元数据时不可强行归因 |
| D4 发布事件 | CI/CD 主动上报 Datafox Release API | Collector/Deployment Watcher 从 Pod 推断发布 | 发布事实可审计；需要 CI/CD 集成与事件状态机 |

**组件权威顺序**：标准 OTel SDK 与 Semantic Conventions → 上游 Operator/Collector 的公开配置与扩展契约 → Datafox 配置和 Release API。实现与上游行为不一致时，先补充兼容性验证，不通过 Fork 解决可配置的问题。

## 9. 演进边界、验收条件与代码导航

### 9.1 首期交付切分

| 阶段 | 产生的新能力 | 架构验收点 |
| --- | --- | --- |
| M0 | 锁定 Operator/Collector 发行版、CRD、语言镜像与应用 JDK/Kubernetes 矩阵 | 输入来源优先级、匹配范围和危险环境变量组合可验证 |
| M1 | Datafox Java Agent 注入镜像及 Operator 配置 | Java Pod 安全创建，版本进入真实 OTLP Resource |
| M2 | Collector 基础设施补全和 Pod 关联 | Pod UID 与 Workload 属性正确，应用身份保持不变 |
| M3 | Python / Node.js / .NET 自动埋点和 Go SDK-only 集成 | 多语言最终 Resource 契约一致 |
| M4 | CI/CD Release API 联调 | 同版本多次部署、滚动升级与回滚关系可核验 |
| M5 | 故障注入、升级兼容性与性能门禁 | 未启用注入的业务无容器 Mutation，异常注入可检测和回滚 |

具体执行顺序、Manifest、Dockerfile、Collector Processor、RBAC、测试环境、44 个测试 ID、事件状态转移表均见 [实施与验证手册](implementation-and-verification.md)。

### 9.2 工程文件位置

| 位置 | 职责与状态 |
| --- | --- |
| `docs/architecture.md` | 本文件：系统形态、数据所有权、接口与设计取舍 |
| `docs/implementation-and-verification.md` | 实施文档：配置、测试、发布步骤与回滚 |
| `README.md` | 仓库入口、四项决策与文档导航 |
| 规划中的 `charts/`、`configs/`、`images/`、`tests/` | Kubernetes 集成交付物；**当前 PR 尚未实现** |
| 外部 `datafox-java-agent` | Java 发行版构建与运行时测试 |
| 外部 Datafox Backend | OTLP 接收、Release Tracking 和查询 |

**当前版本仅包含设计、统一标签与拓扑契约、实施手册。** 这里列出的规划路径不是已存在的模块；不要用此架构图推断仓库已经完成安装或运行。

### 9.3 固定上游证据与待验证假设

| 关键事实 | 可核对依据 | 状态 |
| --- | --- | --- |
| Operator 的 Label / Annotation 与显式环境优先级 | [Operator Resource Attributes @ cddb781](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md) | 固定源码/官方文档确认 |
| SDK-only 注入不安装 SDK；Java 注入镜像结构 | [SDK-only](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/languages/sdk-only.md)、[Java Dockerfile](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/autoinstrumentation/java/Dockerfile) | 固定源码/文档确认 |
| Pod Mutation Webhook fail-open 和 SDK 追加环境变量 | [Pod Webhook](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/webhook/podmutation/webhookhandler.go)、[SDK Config](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go) | 固定源码确认，集群行为未测试 |
| Pod 关联、基础设施提取、多容器限制 | [Collector k8sattributes @ d63fa33](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md) | 固定源码/文档确认 |
| 多语言最终 Resource 一致、发布事件状态机、生产安全 | Datafox 本设计与实施手册 | **待实现与 E2E 验证** |

**尚未完成**：锁定实际 Operator/Collector 发行版和镜像 Digest、Kubernetes/Helm 渲染、Pod Admission/Java Agent Smoke Test、五语言 Resource E2E、发布 API 联调、性能及故障注入。未来版本升级必须重新核验这些固定源码依据及相应测试。

---

**架构不变量**：`service.*` 保持应用身份；`k8s.*` 记录运行位置；Release Events 记录交付历史。三者通过标准 OTLP Resource 和明确的 Datafox 发布契约关联，任何补全层都不得在证据不足时将其中一种身份替代为另一种。
