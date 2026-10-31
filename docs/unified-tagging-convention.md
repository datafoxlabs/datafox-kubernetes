---
type: synthesis-note
status: proposed
created: 2026-10-31
updated: 2026-10-31
as_of: 2026-10-31
review_after: 2027-01-31
---

# Datafox Unified Tagging Convention — 统一遥测标签规范

> **状态：Proposal v0.1，待架构评审。** 这是一份跨语言、跨信号、跨部署环境的**语义契约**，尚未成为已批准的 RepoFoundry ADR，也没有被任何生产 CI、SDK、Operator、Collector 或 Backend 强制执行。
>
> **规范权威：** OpenTelemetry Semantic Conventions 和 SDK Resource 配置规范。Datadog Unified Service Tagging 仅用于比较产品体验；Datadog 的 `env/service/version` 不作为 Datafox OTLP 属性名。
>
> **阅读顺序：** 先读本规范确定字段和数据所有权，再读 [系统架构](architecture.md) 理解注入/补全/关联，最后读 [实施与验证](implementation-and-verification.md) 的实际配置与测试。
>
> **影响范围：** Datafox Java Agent、其他语言 OTel SDK/Agent、Kubernetes Operator、Collector、APM Backend、Logs/Metrics 接入、CI/CD Release Tracking。

## 1. 核心主张：用 OTel Resource 统一服务身份，用平台契约统一查询行为

Datadog 的统一服务标签使用 `env`、`service`、`version` 连接 APM、指标、日志与发布视图。Datafox 保留这一产品目标，但**不创建一组平行的 `datafox.env` / `datafox.service` / `datafox.version`**。所有受支持的 OTel 遥测使用标准 Resource Attribute，保留用户的标准键名和类型，不在 Collector 中把它们改成 Datafox 私有键。

| Datadog 概念 | Datafox 使用的 OTel 字段 | 稳定性（研究快照） | 意义 |
| --- | --- | --- | --- |
| `service` | `service.name` | Stable | 逻辑业务服务 |
| 无直接同名核心标签 | `service.namespace` | Stable | 逻辑业务域，区分不同系统中的同名服务 |
| `env` | `deployment.environment.name` | Stable | 部署环境，作为服务查询过滤维度 |
| `version` | `service.version` | Stable | 软件制品版本，作为发布前后比较维度 |

Datafox 的**逻辑服务身份**是 `(tenant, service.namespace, service.name)`。`tenant` 由**已鉴权的接入与租户上下文**决定，**不是**允许调用者在 OTLP Resource 中自行声称的 `tenant` 属性。`deployment.environment.name` 和 `service.version` 分别是服务的部署维度与软件版本维度，不能作为“创建了一个新逻辑服务”的依据。

OpenTelemetry Service SemConv 要求同一水平扩展服务的 `service.name` 一致；`service.namespace` 可为空但此时同名空间下必须避免服务名冲突。Datafox **推荐**对需要跨 Namespace/环境关联的服务显式提供稳定的 `service.namespace`。对不需要逻辑命名空间的服务允许省略，并遵循 OTel 的原始含义；不能为了统一格式而虚构一个命名空间。

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

## 3. 标准属性清单与字段级数据所有权

下表使用 `P0` 表示 Datafox 首期需要定义的字段，`P1` 表示按具体需求启用的字段。必需性是 **Datafox 交付策略**，不应被理解为 OTel 对所有运行环境的普遍要求。

### 3.1 P0：应用与环境身份

| OTel Attribute | Datafox 受管理生产服务 | 类型 | 权威来源 | 写入阶段与规则 |
| --- | --- | --- | --- | --- |
| `service.name` | **必需** | string | 应用显式配置；否则 Operator 解析 | SDK Resource；缺省 `unknown_service` 不满足 Datafox 生产契约 |
| `service.namespace` | **推荐**；跨环境稳定服务身份时建议显式设置 | string | 业务域 / 平台配置；否则保留上游默认 | SDK Resource；**不能**无条件将 Kubernetes Namespace 当成长期逻辑身份 |
| `deployment.environment.name` | **推荐**；部署环境比较/发布关联场景需要 | string | 部署平台 / 用户配置 | SDK Resource；环境值由企业定义，`development`、`test`、`staging`、`production` 仅为示例 |
| `service.version` | **参与发布追踪时必需** | string | 构建/发布系统；用户显式配置可覆盖 | SDK Resource；必须稳定、可追溯、与发布事件一致 |
| `service.instance.id` | **推荐** | string | SDK/Instrumentation | 运行实例身份；不得由无法区分容器的 Collector 盲目推导 |

**作用域**：Datafox 兼容普通 OTel 入口和受管理的 Release Tracking 两种模式。普通 OTel 遥测只要求能够可靠识别服务，允许 `service.namespace`、环境和版本缺失并保留“未知”状态；需要按环境分析或将 Trace 关联到发布事件时，对应维度必须在该功能入口满足契约。是否要求在 CI 中拒绝缺失值由**显式启用的受管理发布策略**决定，不得对所有 Kubernetes 应用无差别施加强制要求。非 Kubernetes 服务也使用同一套 Resource 字段，不要求具备 `k8s.*`。

**实例唯一性**：`service.instance.id` 应满足 OTel 的实例唯一性约束，可能是 SDK 生成的 UUID 或稳定实例标识。不要把它与 `service.name` 组合生成新的业务服务，也不要在默认指标聚合中以其作为低基数维度。

### 3.2 P0/P1：运行位置、制品与发行版

| OTel Attribute | 优先级 | 由谁提供 | 用途与边界 |
| --- | --- | --- | --- |
| `k8s.cluster.name` | P0（K8s） | Collector/集群显式配置 | 可读集群名，不能单凭名称假设跨租户全球唯一 |
| `k8s.cluster.uid` | P1 | 有权限的基础设施采集 | 更稳定的集群身份；OTel 约定可用 `kube-system` Namespace UID 表示 |
| `k8s.namespace.name` | P0（K8s） | Collector | 实际 Pod Namespace，**不等于** `service.namespace` |
| `k8s.deployment.name` 等 Workload 属性 | P0（适用时） | Collector | 实际 Deployment/StatefulSet/Job；不存在的类型应省略 |
| `k8s.pod.uid` | P0（K8s Pod 关联） | Operator Downward API / Collector | 关联 Pod，优先于经过代理后可能失真的连接 IP |
| `k8s.pod.name`、`k8s.node.name` | P1 | Collector | 排障和工作负载定位 |
| `k8s.container.name`、`container.id` | P1 | SDK / Collector（可确定时） | 多容器区分；不能盲目从 Pod 选取任意 Container |
| `container.image.name`、`container.image.tags` | P1 | Collector/容器运行时 | 标准镜像字段；Tag 不是应用发布身份 |
| `container.image.repo_digests` | P1 | Collector/容器运行时 | 镜像制品定位；并非每个接入场景都会提供 |
| `vcs.ref.head.revision` | P1 | CI/CD / 构建系统 | VCS 提交版本；研究快照中为 Release Candidate，需按版本锁定和兼容 |
| `telemetry.distro.name`、`telemetry.distro.version` | P1 | Agent Distribution | 标识 **Datafox Agent 发行版版本**，绝不冒充 `service.version` |

**兼容性提示**：OTel 当前稳定字段为数组类型 `container.image.tags`；原项目实现手册中使用的 `container.image.tag` 必须在锁定 Collector 版本后明确兼容映射，不得假设两者是当前相同类型的字段。[OTel Container Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/container/)、[OTel Telemetry Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/telemetry/)、[OTel Kubernetes Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/k8s/)。

### 3.3 暂不纳入 v1 必需 Resource 的字段

OTel Registry 当前列出了 `deployment.id`、`deployment.name` 和 `deployment.status`，但这些字段在研究快照中是 **Development**。Datafox v1 保留发布 API 中独立的 `release_id`、`deployment_id` 和事件状态，不强制各语言 SDK 在 Resource 中携带这几个尚未稳定的部署字段。未来上游稳定且有明确关联需求时，再评估单向映射与版本迁移。[OTel Deployment Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/deployment/)。

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
| 完全不能修改业务 Manifest 或 SDK | 仅观察现有 OTLP 输出 | 可提供有限的自动推导与缺失提示；**不承诺**仅凭自定义 Label 就能自动注入正确应用身份 |

在 OpenTelemetry Operator 的已检查实现中，`useLabelsForResourceAttributes` **不是任意 Label → Resource 的通用映射引擎**。它识别的标准键范围有限。自定义 Label 若要成为 `service.version` 等应用身份，优先在**Helm/CI/CD/GitOps 模板渲染阶段**转成受支持的 Resource Annotation，避免自建 Admission Webhook。[Operator 支持的映射](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)。

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

1. 用户已有的 **可安全读取的显式** `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES`。
2. `resource.opentelemetry.io/*` Annotation。
3. 开启 Label 提取后的标准 `app.kubernetes.io/*`。
4. Operator 其他自动推导，**仅作为上游兼容行为**，不能代替 Datafox 的生产版本准入规则。
5. Instrumentation CR 默认 Resource 属性。

这一顺序属于 **Operator 注入配置规则**。SDK 最终 Resource 还可能合并用户代码创建的 Resource 和其他 Detector；因此每种语言必须用真实 OTLP 输出验证“最终值”，不只检测容器的环境变量。[Operator Resource Attributes（固定研究源码）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)、[OTel Resource SDK](https://opentelemetry.io/docs/specs/otel/resource/sdk/)。

### 5.2 Datafox 负责的冲突策略

只有启用了受管理自动注入或 Release Tracking 的工作负载，才需要额外执行对应的发布前字段校验；普通 SDK 遥测接收不应因为未使用推荐 Kubernetes Label 而被拒绝。

| 情况 | 处理 |
| --- | --- |
| 显式版本与 Annotation/Label 不同 | 按上游优先级保留显式值；CI 显示生效来源，不静默重写 |
| Annotation 版本不同于 Label | 允许显式覆盖，但 Release Event 的版本必须与**最终生效值**一致 |
| `service.name` 被 `app.kubernetes.io/instance` 误影响 | 若参与受管理发布追踪，要求显式确认业务服务名；普通接入可保留原值并显示可能的命名冲突 |
| 跨环境的 `service.namespace` 随 Kubernetes Namespace 变化 | 不自动合并；需要跨环境统一逻辑服务时推荐显式稳定身份 |
| `OTEL_RESOURCE_ATTRIBUTES.valueFrom` / `envFrom` 同名冲突 | 在**注入目标容器的 CI 发布前检查**中拒绝不兼容输入 |
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

### 6.2 Traces、Metrics、Logs 的一致性不是盲目复制

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

**不支持**将 Token、Secret、密码、客户个人信息、任意 HTTP 请求 ID、完整 Kubernetes Annotation/Label 集合批量注入通用 Resource。不自动将未经白名单核准的任意 Pod Label 全量转成 Metric 维度。

自定义属性不能冒充 OTel 规范字段，也不能被用来修改 `service.name` 的意义。

### 7.3 版本升级与历史兼容

- 新数据首先遵循当前锁定的 OTel 规范键名；历史使用的 `deployment.environment` 已弃用，v1 不作为新输入建议。
- 若旧版 Collector 产生 `container.image.tag`，而新 SemConv 稳定字段是 `container.image.tags`（`string[]`），必须经独立兼容设计和实际类型测试转换；不在本文默认宣称同名或等价。
- 任何历史数据兼容/索引映射必须保持源值可追踪，不能静默修复用户非法输入。
- 需要定期核验 Operator 对 `app.kubernetes.io/instance` / `name`、Env 优先级、SDK-only 和 Kubernetes Webhook 的实际支持，不用当前上游 `main` 的代码替代生产发行版证据。

## 8. 最小验收合同与下一步

统一标签规范 **尚未实现**。第一批工程测试必须证明：

| Case | 输入 | 需要检查的结果 |
| --- | --- | --- |
| Tag-01 | Java/Python/Node.js/.NET/Go 同一业务身份与版本 | 最终 OTLP Resource 的四个核心属性完全一致 |
| Tag-02 | 跨 Namespace/Cluster 发布同一 Service | `service.namespace/name` 稳定，`k8s.*` 区分实际部署位置 |
| Tag-03 | Helm `app.kubernetes.io/instance` ≠ 业务 `name` | 受管理发布要求明确业务服务名；普通接入保留用户配置并提示歧义 |
| Tag-04 | `2.4.1+build.17` | 使用 Annotation 传递完整值；非法 Label 不进入 Pod |
| Tag-05 | 显式版本、Annotation、Label 三者冲突 | 用户显式值优先，发布事件一致 |
| Tag-06 | `valueFrom` / 冲突 `envFrom` | 在自动注入发布前失败，不触发生产 Pod CREATE |
| Tag-07 | Collector 缺少 Pod 关联信息 | 不伪造或覆盖服务与 Pod 身份 |
| Tag-08 | 同版本重复部署/回滚 | 一个 Service Version，多条独立 Deployment 记录 |
| Tag-09 | Agent 发行版本升级 | `telemetry.distro.version` 变化不影响 `service.version` |
| Tag-10 | Trace / Metric / Log / Node Metric | 应用信号身份一致；Node Metric 不被错误贴上单个服务版本 |

实施手册中既有 T01–T44 仍是 **实施验收清单**；本节 Tag-01–Tag-10 是跨仓库合同测试的语义索引，不应被记录为额外已经通过的测试。

### 8.1 不同标签来源的兼容性案例

| Case | 输入来源 | 需要检查的结果 |
| --- | --- | --- |
| Tag-11 | 自定义 `company.example.com/release` Label，经 Helm 模板映射到 Resource Annotation | 保留企业标签原值，最终 OTel `service.version` 等于目标制品版本 |
| Tag-12 | 只提供显式 `OTEL_RESOURCE_ATTRIBUTES`，无任何推荐 Kubernetes Label | 正常进入 Datafox，SDK Resource 不被 Collector 改写 |
| Tag-13 | 自定义基础设施 Label 仅通过 Collector 白名单提取 | 自定义属性可查询，但不覆盖业务 `service.*` |
| Tag-14 | 无版本且未启用 Release Tracking 的普通 OTel 服务 | 遥测可接收，不被强制推断出发布版本 |
| Tag-15 | 多容器 Pod 与企业自定义 Pod 级版本 Label | 不把一份 Pod Label 作为多个业务容器的不同应用版本 |

这些仍是**拟定测试契约**；实施前需要根据实际 Helm/CI/CD 接入方式落地，不代表已有通用映射工具或已经完成 E2E。

**前置的评审问题**：确定 Datafox 在受管理发布与普通 OTel 接入中的最小字段要求，以及哪些企业标签映射确有业务需要。Service Namespace 的长期语义、版本字符串格式、CI 事件来源和历史数据兼容性仍需逐项确认。完成规范评审后，再锁定 Operator/Collector 版本和开发注入配置。

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
