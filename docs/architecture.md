---
type: synthesis-note
status: proposed
created: 2026-10-30
updated: 2026-10-30
as_of: 2026-10-30
review_after: 2027-01-30
---

# Datafox Kubernetes Metadata & Release Integration：架构与设计决策

> [!abstract] 范围与状态
> 这是一份独立于聊天记录的 **架构设计稿**。它解释多语言 APM 如何统一获得 Kubernetes 元数据和应用发布版本，以及如何避免自动注入破坏业务工作负载。它不是已部署的产品文档。
>
> **四项已定决策**：标准 Pod Label + Annotation；复用 OpenTelemetry Operator；Collector 只补充基础设施属性；CI/CD 主动上报发布事件。
>
> 配套执行步骤与验收矩阵： [实施与验证手册](implementation-and-verification.md)。

## 一分钟结论

对 Java、Python、Node.js、.NET、Go 分别实现 Kubernetes 版本探测，会带来不同的版本来源、配置覆盖与升级行为。Datafox 统一在 Kubernetes 入口确定应用身份：**Operator 负责在 Pod 创建时将标准版本来源转换为 SDK 环境配置**；SDK 在初始化时把 `service.name` 与 `service.version` 放入 Resource；Collector 通过 Kubernetes API 将 Pod / Workload / Node 信息补全到遥测 Resource；CI/CD 向 Datafox Backend 上报真实的发布事件。

以上环节具有不同的故障边界。Operator 的 Pod Webhook 故障可配置为 fail-open，但**成功完成 Mutation 并不保证应用能成功启动**：Init Container、镜像拉取、Agent 与应用兼容性仍会影响业务。上线必须采用显式启用、金丝雀与回滚机制。

## 1. 从一个发布事故理解需求

假设 `commerce/order-service` 原来运行 `2.4.0`，CI/CD 发布 `2.4.1`，滚动升级期间两个版本同时服务流量。值班工程师需要回答：

1. 哪些 Trace 来自 `2.4.1`，错误和延迟是否上升？
2. 出问题的请求来自哪个 Cluster、Deployment、Pod？
3. 新版本对应什么 Git Commit、镜像 Digest，什么时候开始/完成部署？
4. Java、Go、Python 服务能否以相同条件查询？
5. 如果 Operator 或注入的 Agent 故障，是否会阻止业务 Pod 创建或启动？

仅把 `service.version` 交给语言 Agent 自行推导，会使不同语言对镜像 Tag、构建产物的理解不一致；仅靠 Collector 补全也不能稳定确定**业务应用**的版本，尤其在同一 Pod 内运行多个容器时。CI/CD 的部署事件又是独立事实，不能从首个 Span 的时间推定。

## 2. 参与者、归属与通信

| 对象 | 类型 | 创建者 / 所在位置 | 负责 | 不负责 |
| --- | --- | --- | --- | --- |
| Deployment / Pod Template | K8s 声明式资源 | CI/CD 或 GitOps | 声明容器、Pod Labels、Annotations | 采集 Trace |
| Pod Admission Webhook | Kubernetes API Server 的准入扩展 | OTel Operator 安装 | 在 Pod 创建时变更环境变量、Init Container、Volume、启动参数 | 在业务进程内读取 JVM 或 Go 代码 |
| Instrumentation CR | OTel Operator 自定义资源 | 平台团队 | 持有注入镜像、Exporter、SDK 参数 | 承载业务版本历史 |
| Language Agent / SDK | 应用进程组件 | Operator 注入或应用自行集成 | 创建 Span 和 SDK Resource；通过 OTLP 发数据 | 查询 Kubernetes API 还原 Deployment |
| Resource | OTel 遥测身份与环境属性集合 | SDK 初始化时；Collector 也可补全 | 将 `service.version` 等属性关联到遥测 | 表达一次部署的完整生命周期 |
| OTel Collector | 集群独立服务或 DaemonSet | 平台部署 | 接收、处理、转发 OTLP；通过 `k8sattributes` 关联 Pod | 修改业务版本；跟踪 CI/CD 部署状态 |
| CI/CD / GitOps | 发布控制系统 | 交付平台 | 构建、下发版本 Label、上报发布事件 | 解释单条 Trace 属于哪个 Pod |
| Datafox Backend | 独立后端 | Datafox 平台 | 存储/索引遥测与发布事件，按版本比较 | 在业务 Pod 上执行 Admission Mutation |

Operator 可以独立运行在集群中，Collector 可能部署为单层 Gateway 或 DaemonSet + Gateway；SDK/Agent 位于业务容器运行时内。Deployment 是对象而不是进程，Resource 是遥测数据模型而不是独立服务。

### 2.1 职责拓扑

~~~mermaid
flowchart TB
  subgraph Delivery["CI/CD / GitOps"]
    Release["构建制品与版本"]
    Manifest["Deployment / Pod Template"]
    Event["Deployment Events"]
    Release --> Manifest
    Release --> Event
  end
  subgraph Cluster["Kubernetes Cluster"]
    API["API Server Admission"]
    Operator["OTel Operator Webhook"]
    Pods["业务 Pods"]
    Collector["OTel Collector + k8sattributes"]
    KubeAPI["Kubernetes API"]
    Manifest --> API
    API <--> Operator
    API --> Pods
    KubeAPI --> Collector
    Pods -->|"OTLP"| Collector
  end
  subgraph Backend["Datafox Backend"]
    Ingest["OTLP Ingestion"]
    Releases["Release Tracking"]
    Analytics["Version / Deployment Analytics"]
    Ingest --> Analytics
    Releases --> Analytics
  end
  Collector --> Ingest
  Event --> Releases
~~~

这个图描述职责和数据通道；实际 Operator Webhook 是在 API Server Admission 调用期间参与 Pod 创建，并非每次应用请求时参与。

### 2.2 一次部署和一次业务请求

~~~mermaid
sequenceDiagram
  participant CI as CI/CD
  participant API as Kubernetes API Server
  participant OP as OTel Operator
  participant JVM as App + SDK/Agent
  participant COL as Collector
  participant DF as Datafox Backend
  CI->>API: 提交 Deployment（版本 Label）
  API->>OP: Pod CREATE AdmissionReview
  OP-->>API: Patch（SDK 环境 / Agent Init Container）
  API-->>JVM: 创建 Pod；Init、拉镜像、启动业务进程
  JVM->>COL: OTLP（service.version + Pod 身份）
  COL->>API: 查询 / Watch Pod 元数据（独立权限）
  COL->>DF: OTLP（补全基础设施 Resource）
  CI->>DF: deployment.started / succeeded / failed
  DF-->>DF: 按服务版本、环境与工作负载关联
~~~

**重要：** “AdmissionReview 允许创建”与“容器正常启动”是不同阶段。后者需要进行探针、资源消耗、Agent 行为的独立验证。

## 3. 四项架构决策

本节使用 **D1–D4** 标识本次评审确认的产品架构决策。这些编号只用于本设计文档，**不是** RepoFoundry 工具注册的正式 ADR ID，也不表示已经在 `docs/DECISIONS.md` 中完成 ADR 审批。后续如需正式 ADR，须由授权人员通过对应工作流创建并建立映射。

### D1：标准 Pod Label + Annotation 定义服务版本

平台要求每个生产业务 Pod Template 声明：

- `app.kubernetes.io/name`：缺省服务名称；
- `app.kubernetes.io/version`：缺省应用版本；
- 可选 `resource.opentelemetry.io/service.version`：覆盖版本；
- 可选 `resource.opentelemetry.io/service.name`：覆盖服务名称。

默认优先级按 Operator 的**逐属性**解析规则：

| 顺序 | 来源 | 示例 |
| --- | --- | --- |
| 1 | 用户已显式设置 `OTEL_RESOURCE_ATTRIBUTES` / `OTEL_SERVICE_NAME` | `service.version=2.4.9` |
| 2 | Pod Annotation | `resource.opentelemetry.io/service.version=2.4.2` |
| 3 | Pod Label，需开启 `useLabelsForResourceAttributes` | `app.kubernetes.io/version=2.4.1` |
| 4 | Operator 其他推导（包括合规镜像 Tag） | `2.4.1` |
| 5 | Instrumentation CR 默认 Resource | 固定模板值 |

**约束**：Datafox 生产发布的 CI 校验要求显式稳定版本，不能仅靠镜像 Tag 兜底。没有提供版本时，**发布流水线拒绝**；我们不为此增加阻止 Pod 创建的 Webhook。这条拒绝规则是 Datafox 的发布政策，不是 OTel Operator 默认行为。

#### 环境变量来源的准入边界

Operator 的“已有环境变量优先”规则仅能在其能识别并安全修改的输入形式上成立。对于 opt-in 的目标容器，Datafox **发布前检查**必须区分：

| 输入形式 | 设计约束 | 不满足时的结果 |
| --- | --- | --- |
| `env: [{name: OTEL_RESOURCE_ATTRIBUTES, value: "..."}]` | 允许；验证格式和最终 Resource 冲突优先级 | CI 拒绝非法属性 |
| `env[].name=OTEL_RESOURCE_ATTRIBUTES` 且使用 `valueFrom` | 暂不支持自动注入；先转换为受控字面量配置，或关闭该容器注入 | CI 拒绝 opt-in 发布 |
| `envFrom` 中的 ConfigMap/Secret 含 Operator 将注入的同名环境变量 | 暂不支持；需明确迁移来源，避免显式 `env` 遮蔽 | CI 拒绝 opt-in 发布 |
| `envFrom` 的引用数据或键集合在发布前不可核验 | 不猜测安全；要求提供可核验键清单，或关闭注入 | CI 拒绝 opt-in 发布 |
| Java `JAVA_TOOL_OPTIONS` 通过 `valueFrom` 提供 | 当前 Operator 不支持安全追加 Java Agent 启动参数 | CI 拒绝 Java opt-in 发布 |

`envFrom` **本身并非全部禁止**：只要完整解析最终名称（含前缀）并证明不与目标语言的 Operator 注入变量冲突，就可保留。检查适用于真正被注入的容器，不影响未启用自动注入的 Pod。配置值如包含机密，不应为了通过校验而写入公开 Manifest；应调整配置所有权或退出自动注入模式。

该兼容性限制来自已检查 Operator [`sdk.go`](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go#L502-L566) 对 `OTEL_RESOURCE_ATTRIBUTES` 的追加，以及 [`javaagent.go`](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/javaagent.go) 对 `JAVA_TOOL_OPTIONS` 的校验。Kubernetes [EnvVar 规则](https://kubernetes.io/docs/reference/kubernetes-api/core/pod-v1/) 要求 `valueFrom` 不与非空 `value` 并存，显式 `env` 又优先于 `envFrom`。需要在锁定的 Operator 发行版上重新执行 Pod CREATE 负面测试。

版本语义：`service.version` 是**应用软件版本**，不是 Operator 版本、Java Agent 版本，也不是 Kubernetes Rollout ID。同一服务版本可以多次部署。镜像 Tag 可能是 `latest`，镜像 Digest 才能唯一指认容器制品；这些字段不得强行互相替代。

[来源：Operator Resource Attributes（固定源码快照）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)。

### D2：复用 OTel Operator，不自研 Webhook

Platform 维护一个已安装、锁定版本的 Operator；Datafox 管理自己的 `Instrumentation` 及 Opt-in Pod Annotations。支持：

- Java：Datafox Java Agent Operator 注入镜像；
- Python / Node.js / .NET：上游自动埋点镜像；
- Go：优先已集成 SDK + `inject-sdk`，不默认使用高权限的 Go eBPF 自动埋点；
- 其他 SDK：显式读取 OTel 环境配置。

**区分两种注入**：语言 Auto Instrumentation 会修改启动环境/添加 Agent；`inject-sdk` 只设置 SDK 环境变量，不会安装 SDK。已有 SDK 的语言必须验证资源构造实际读取 `OTEL_RESOURCE_ATTRIBUTES`；Go 手动创建 Resource 时可显式使用 `resource.WithFromEnv()`。

Operator 的 Java 自定义镜像要求根路径 `/javaagent.jar` 可读，镜像中提供 `cp`；注入过程通过 Init Container 复制至共享 Volume。不能将可执行 Agent JAR 直接当成容器镜像。不要引入独立 extension JAR 发行版架构。

[来源：Custom Images](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/custom-images.md)、[Java Dockerfile](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/autoinstrumentation/java/Dockerfile)、[SDK-only](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/languages/sdk-only.md)。

### D3：Collector 只补充基础设施属性

`k8sattributes` 通过 Kubernetes API 获取 Pod、Namespace、Deployment、ReplicaSet、Node 等信息，以 Pod UID（优先）、Pod IP、连接 IP 匹配遥测。可由 Operator 在应用侧预先注入 `k8s.pod.uid`，提升代理转发场景的匹配可靠性。

允许 Collector 补全 `k8s.*` 与必要的 `container.*` 属性；**禁止 Collector 配置提取/改写 `service.name`、`service.namespace`、`service.version`**。即使上游 Processor 允许映射这些字段，Datafox 的最终配置也不允许。

Collector 不使用 `otel_annotations: true` 自动把全部 Pod Resource Annotations 引入遥测，不批量采集 Labels/Annotations，避免覆盖应用身份、泄露配置和形成高基数数据。

[来源：k8sattributes Processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md)。

### D4：CI/CD 主动上报部署事件

Datafox Release Tracking 将 **Release**（制品/软件版本）与 **Deployment**（在某个环境的一次部署）分离；一个 Release 可以对应多次 Deployment。事件至少包含：

`deployment_id`、`event_id`、`event_type`、`service.name`、`service.version`、`environment`、`cluster`、`namespace`、`workload`、`git_commit`、`image_digest`、`occurred_at`。

发布 API 是 Datafox 产品契约，**不是 OTel 标准协议**。完成事件只能由部署控制系统依据 Rollout 成功事实报告，不能由收到第一个 Span 代替。

事件必须区分**不可变的 Deployment 历史事实**和**新部署引发的回滚动作**：同一 Deployment 的 `started → succeeded|failed` 状态一旦终结不可改写；迟到的 `started` 只能补记事件，不能回退状态；同一事件 ID 不同载荷、同一部署出现冲突终态，应返回确定的冲突错误。回滚是一次**新的 Deployment**（引用旧 Release 和被回滚的 Deployment），原部署已成功的历史记录不得重写为失败。详细的幂等键、状态转移与拒绝测试见 [实施手册第 5.2 节](implementation-and-verification.md)。

## 4. 版本与基础设施数据的分工

| Resource / 记录字段 | 权威来源 | 所在阶段 | 注意 |
| --- | --- | --- | --- |
| `service.name` | 应用显式配置或 Operator | SDK 初始化 | Pod Label 的 `instance` 也可能参与服务名推导；发布时校验 |
| `service.version` | 显式配置 / Annotation / Label | SDK 初始化 | Collector 不覆盖 |
| `deployment.environment.name` | 应用/平台配置 | SDK 初始化 | 不与 `k8s.namespace.name` 混淆 |
| `k8s.pod.uid` | Operator Downward API 或 Collector | SDK / Collector | 首选 Pod 关联依据 |
| `k8s.pod.name`, `k8s.namespace.name` | Collector | 接收/处理 OTLP | 应用预先提供时保持一致 |
| `k8s.deployment.name`, `k8s.node.name` | Collector | 接收/处理 OTLP | 需要相应 K8s API 权限 |
| `container.image.tag` | Collector | Pod 关联后 | 多容器需 `container.id` / `k8s.container.name` |
| Git Commit / Image Digest | CI/CD | 发布记录 | 不要求所有 Trace 重复携带 |
| Deployment ID / started / succeeded | CI/CD | 发布记录 | 关联到环境和工作负载 |

#### 跨环境的稳定服务身份

Datafox 的服务逻辑身份采用 **`(tenant, service.namespace, service.name)`**；`deployment.environment.name`、`k8s.namespace.name`、Cluster 和 Deployment ID 是独立维度。避免将 Helm Release 名称、Pod 名称或环境 Namespace 隐式当作业务服务标识：

- `app.kubernetes.io/instance` 和 `app.kubernetes.io/name` 同时存在且值不同：Datafox CI 必须要求显式 `OTEL_SERVICE_NAME` 或 `resource.opentelemetry.io/service.name` 指定业务名；不得假设一定选择 `name` Label。
- `service.namespace` 省略时，Operator 可以从 Kubernetes Namespace 推导；如果 staging/prod 使用不同 Namespace 但希望同属一个 Datafox 业务服务，生产 Pod Template **必须显式配置稳定的** `resource.opentelemetry.io/service.namespace` 或等效标准 Resource。
- 每次 CI/CD 发布事件中的 `service.name`、`service.namespace` 与最终 SDK Resource 必须一致；`target.namespace` 仍保留物理 Kubernetes Namespace，不能混用两者。
- CI 对跨 Namespace、跨 Cluster、两个 Helm Release 名称和多容器版本差异进行契约验证；无法确定服务身份时，阻止该 opt-in 发布，而不是在 Backend 猜测服务合并规则。

该约束是 Datafox 的**期望服务身份契约**，不是 Operator 默认保证的跨环境行为。上游 [Resource Attributes](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md) 和 [`sdk.go`](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go#L611-L660) 给出了默认推导方式。

**多容器 Pod 是版本模型的边界**：Pod Label 只有一份，无法表达两个业务容器的独立版本。推荐业务应用拆成独立 Pod；确实需要共存时，明确目标容器并在容器级显式配置版本，不能向所有容器广播同一个 Pod 级 `service.version`。

## 5. 从 `order-service` 2.4.0 → 2.4.1 的全链路推演

1. CI 构建 `2.4.1`，产生 Git SHA 和不可变的 Image Digest；验证 Deployment Pod Template 包含 `app.kubernetes.io/version: "2.4.1"`。
2. CI 发送 `deployment.started`，部署到 `production / prod-sg / commerce`。
3. API Server 创建新 Pod 时调用 Operator 的 Pod Mutating Webhook。Operator 按显式 opt-in Annotation 定位对应 `Instrumentation`，添加环境变量和语言 Agent 文件挂载（SDK-only 不添加 Agent）。
4. 新容器初始化 SDK，得到 `service.name=order-service` 与 `service.version=2.4.1`；旧 Pod 仍带 `2.4.0`。两个版本并存是滚动升级的正常状态。
5. Collector 按 Pod UID 识别新 Pod，补上 `k8s.deployment.name`、`k8s.node.name` 等，不改写版本。
6. CI 确认 Rollout 成功才发送 `deployment.succeeded`；失败则报告 `deployment.failed`，同时执行原有回滚策略。
7. Backend 按 `service.version` 对比 Trace；关联到具体 Deployment 时继续检查 Environment、Cluster、Workload、时间窗口和可用的制品/Pod 身份。版本相同不代表部署相同。

## 6. 为什么简单方案不足

| 方案 | 问题 | 最终判断 |
| --- | --- | --- |
| 每种语言 Agent 自行检测版本 | 语义不一致，Java / Go / Node 的实现和升级不同 | 不采用 |
| Collector 从 Image Tag 覆盖 `service.version` | `latest` 不可追溯；多容器歧义；用户版本可能被覆盖 | 不采用 |
| Datafox 自建 Pod Admission Webhook | 重复 Operator 机制，增加 Webhook 故障和冲突面 | 不采用 |
| Collector 监听 Deployment 推断“部署成功” | Pod 状态不完整反映 GitOps 审批与发布状态；难关联 CI 制品 | 不采用 |
| Operator + Collector + CI/CD 组合 | 每层职责清楚，但需协调版本/安全和发布接口 | 采用 |

## 7. 业务安全：Pod 创建与应用运行是两种风险

### 7.1 Admission 阶段

在所检查的 Operator 源码快照中，Pod Mutation Webhook 的 `failurePolicy` 是 `Ignore`；`webhookhandler.go` 还针对 Namespace 查询或 Mutator 错误设置了 `Allowed = true`。这意味着 Webhook 无法响应/部分处理异常时，**设计意图是允许 Pod 继续创建**。

**匹配范围与修改范围不同**：检查的上游 Pod CREATE Webhook Manifest 未限定 `namespaceSelector`/`objectSelector`，因此未 opt-in 的 Pod 仍可能经过 Webhook 请求，承担 Admission 延迟与超时；未 opt-in 只表示不应为业务容器增加 Agent 变更。生产安装前必须审查最终 Webhook 匹配规则、`timeoutSeconds`、失败策略和其他 Admission Webhook，并在测试集群对无注入 Pod 测量创建开销。可用范围限制方式必须以锁定的 Helm Chart/Kubernetes 版本为准，不直接手动改写共享 Operator 的受管理 Webhook。

**Fail-open 也会使已 opt-in Pod 在 Webhook 失效时不带 Agent 启动**。这保护业务 Pod 创建，但破坏可观测性覆盖率。发布流水线应核对实际 Pod Spec 的预期 Init Container / 环境变量，以及 OTLP Resource；缺失时报告“未注入”，不把 Ready 当成注入成功。恢复动作采用受控新 Pod Rollout，不强制中断已有健康容器。

但这不是跨所有 Helm/Operator 版本的无限承诺。真实集群必须检查 `MutatingWebhookConfiguration`、Namespace Selector、CABundle、超时及其他 Admission Webhook。`Instrumentation` CR 自身的验证 Webhook 可能配置为 `Fail`，不要把它与 Pod CREATE Webhook 混为一谈。

[来源：Pod Webhook 源码](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/webhook/podmutation/webhookhandler.go)、[Webhook Manifest](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/config/webhook/manifests.yaml)。

### 7.2 Mutation 成功后的启动阶段

成功 Mutation 会改变业务 Pod 的 Init Container、环境变量、Volume 或启动参数。风险包括：

- Agent 镜像不可拉取、文件复制失败 → Pod Init 无法完成；
- 不兼容的 Java Agent 或 `JAVA_TOOL_OPTIONS` → JVM 启动失败；
- 自动埋点框架冲突 → 业务行为变化或异常；
- SDK/Agent 内存与 CPU 消耗 → 启动变慢、OOM、延迟恶化；
- OTLP Exporter 错误配置 → 遥测丢失或额外开销；
- 多个 Mutating Webhook 的顺序或重复注入 → 环境/挂载冲突。

**安全原则**：默认不对整个 Namespace 启用语言 Agent；业务 Pod 显式 opt-in；先测试命名空间，再小流量 Canary；确认指标、探针和异常后才逐步扩展。需要说明的是，**Pod opt-in 不自动缩小 Webhook 的 API Server 匹配范围**，这两项要分别检查和测量。

停用注入只能影响**新建 Pod**。已经创建并被 Mutation 的 Pod 不会自动恢复，应通过回滚 Deployment Pod Template 和受控重新创建进行撤销。对没有提供版本的生产 Manifest 在 CI 中拒绝，不在集群 Admission 上实施全局阻断。

## 8. 发布域模型与关联精度

~~~mermaid
erDiagram
  SERVICE ||--o{ RELEASE : produces
  RELEASE ||--o{ DEPLOYMENT : deployed_as
  DEPLOYMENT ||--o{ DEPLOYMENT_EVENT : emits
  SERVICE {
    string tenant_scope
    string service_name
    string service_namespace
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
    string workload
    string status
  }
  DEPLOYMENT_EVENT {
    string event_id
    string event_type
    datetime occurred_at
  }
~~~

Release（应用制品）与 Deployment（部署实例）是**一对多**。租户范围必须参与唯一性约束。蓝绿和滚动发布时，同一服务可以同时有多个版本；同版本多次部署也必须分开存储。

**关联等级**：

- L1：服务 + 版本，可靠支持版本级 Trace 查询；
- L2：L1 + 环境 + 集群，缩小部署候选；
- L3：L2 + Workload + 时间窗口 + Pod UID / Image Digest，按证据关联部署；
- L4：L3 + CI/CD 状态，支持发布窗口、回滚和故障归因。

v1 产品可先交付 L1/L2，不因缺少 L3 身份就强行“猜测唯一部署”。

## 9. 交付物与非目标

**本仓库负责**：Operator/Collector 版本锁定和配置、Java Operator 注入镜像约定、Helm/安装流程、多语言示例、CI 校验规范、Kubernetes E2E 测试及安全运行手册。

**datafox-java-agent 负责**：OpenTelemetry Java Agent Distribution 和 Java Runtime；继续遵循项目锁定的 v2.32.0、Splunk 工程基础设施基线。不引入额外 Kubernetes Detector，不 Fork Agent，也不增加独立 Extension JAR。

**datafox-backend 负责**：发布事件 API、Release/Deployment 存储、OTLP Ingestion 和版本分析。这部分设计由本仓库记录契约，但不在此仓库实现服务端。

**明确非目标**：自建 Admission Controller、强制劫持所有 Namespace、修改业务应用容器镜像、按 Span 重写版本、实时动态更新已经初始化的 SDK Resource、初版 Go 特权 eBPF 注入、自动远程生产部署或发布。

## 10. 证据登记与开放问题

| Claim | 证据等级 | 证据 / 固定版本 | 适用条件或待确认 |
| --- | --- | --- | --- |
| C1 Operator 支持 Label/Annotation 和逐属性优先级 | A | Operator commit `cddb781` 的 resource-attributes.md、sdk.go | 实际交付版本重新锁定并验证 |
| C2 SDK-only 只注入 SDK 环境变量 | A | 同 commit 的 languages/sdk-only.md | 应用 SDK 必须实际读取环境 |
| C3 自定义 Java Init Image 需要 `/javaagent.jar` 和 `cp` | A | 同 commit 的 Java Dockerfile | 路径和用户权限需镜像测试 |
| C4 Pod Webhook 源码为 `failurePolicy=ignore` / Allowed=true | A | 同 commit 的 webhookhandler.go / manifests.yaml | 不保证 Mutation 成功后的业务启动 |
| C5 k8sattributes 支持 Pod 关联与基础设施提取 | A | collector-contrib commit `d63fa33` 的 README | RBAC、Pod UID、转发拓扑和容器身份 |
| C6 Collector 不覆盖服务版本 | C（架构约束） | Datafox D3 | 通过最终 Collector 配置和 E2E 验证 |
| C7 CI/CD 发布事件构成唯一发布事实 | C（产品契约） | Datafox D4 | Backend API、幂等和状态机尚待实现 |

证据分级：**A** = 已阅读固定源码/仓库一手材料；**B** = 官方设计或文档；**C** = 明确的 Datafox 设计判断；**H** = 教学示例；**U** = 待核验。上表不代表任何运行测试已通过。

开放问题：固定 Operator/Collector 发行版及镜像 Digest；Java 发行版镜像和 JDK 兼容矩阵；现有集群是否有其他 Mutation Webhook；目标 SDK 是否消费环境变量；两层 Collector 的 Pod 身份保真；Release Tracking API 的实际认证和数据表约束。

## 11. 学习检查

读完这份设计，应该能够回答：

1. `service.version` 为什么必须在应用 Resource 中确定，而不能由 Collector 随意覆盖？
2. Operator Webhook `failurePolicy: Ignore` 能避免哪类问题，不能避免哪类问题？
3. Go 已集成 SDK 时，为什么可以只使用 `inject-sdk`？
4. 同一版本发布两次，Datafox 如何避免把两次部署合并？
5. 接入 Gateway Collector 后，为什么 Pod UID 比来源连接 IP 更重要？

## 12. 参考来源

- [OpenTelemetry Operator：Resource Attributes](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)
- [OpenTelemetry Operator：SDK-only](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/languages/sdk-only.md)
- [OpenTelemetry Operator：Custom Images](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/custom-images.md)
- [OpenTelemetry Operator：Pod Webhook](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/webhook/podmutation/webhookhandler.go)
- [Collector Contrib：k8sattributes](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md)
- [OpenTelemetry Java Instrumentation v2.32.0](https://github.com/open-telemetry/opentelemetry-java-instrumentation/tree/v2.32.0)
- [Splunk OTel Java Agent v2.32.0](https://github.com/signalfx/splunk-otel-java/tree/v2.32.0)
- [OpenTelemetry Kubernetes Collector Components](https://opentelemetry.io/docs/platforms/kubernetes/collector/components/)

> [!warning] 验证状态
> 已核对部分上游固定源码与接口文档；**未执行** Helm 部署、Operator/Collector 集成、Datafox Java Agent 镜像 Smoke Test、多语言 E2E 或实际生产 Pod 风险测试。实施时以锁定发行版和真实测试结果为准。
