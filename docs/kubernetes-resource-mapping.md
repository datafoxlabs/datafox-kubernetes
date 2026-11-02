---
type: specification-draft
status: proposed
created: 2026-11-02
as_of: 2026-11-02
---

# Datafox Kubernetes Resource Mapping — 输入映射与冲突处理（草案）

> **状态：Proposal，未批准、未实施。** 本文件只定义在 Kubernetes 接入中从 Pod Metadata / Env 到 OTel Resource 的**映射候选、来源优先级与失败处理边界**。属性 Key、类型与 OTel Stability 统一由 [Attribute Registry](attribute-registry.md) 引用，不在此再次定义。跨语言最终 SDK Resource 必须以实际版本与 E2E 为准。

## 1. 范围和不变量

Kubernetes Label 的命名由企业、Helm、GitOps 和云厂商自行管理。Datafox 的共同语义层是最终 OTel Resource，不是强制重命名 Pod Label。复用 Operator 的标准 Annotation / Well-Known Label 路径是一种**推荐实现**，并非所有语言、所有生产版本的统一合并算法。

- 应用明确提供的标准 `service.*` 不应被 Collector 静默改写；上游 Operator 自动注入与环境变量之间的冲突必须在渲染后、Pod CREATE 前检查。
- 凭未经认证的 Pod UID/IP 或 Gateway 连接 IP 不能提升 Tenant 权限或推断进程级服务实例。
- 普通 OTel 接入缺失某项 Release Tracking 字段时继续接收遥测；受管理发布按[接入策略](unified-tagging-convention.md#3-datafox-接入合同)执行预检。
- Webhook 是否被调用、Pod 是否发生 Mutation、业务进程是否正常启动和真实 OTLP 是否到达，是不同的验收结果。

## 2. Kubernetes 标签适配：推荐默认映射，不强制企业改名

Kubernetes Label 的命名由业务团队、Helm Chart、GitOps 模板或云厂商各自管理。Datafox **只要求最终输出符合 OTel Resource 语义**，不要求用户的现有 Label 命名符合某个厂商/项目模板。下表是**上游 Operator 支持的推荐默认路径**，不是 Datafox 唯一接受的 Kubernetes 标签来源。

### 2.1 推荐映射（可直接复用上游 Operator）

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

### 2.2 企业自定义 Label / 云厂商标签的适配路径

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

### 2.3 推荐的 Pod Template

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

## 3. 优先级、冲突与缺失的统一处理

### 3.1 注入来源优先级

由 Operator 负责将 Pod 元数据转换为标准 SDK 配置，采用以下决策顺序：

1. 用户已有的 **可安全读取的显式** 配置；其中 `OTEL_SERVICE_NAME` 在 SDK 对 `service.name` 的解析中优先于 `OTEL_RESOURCE_ATTRIBUTES` 里的同名属性。
2. `resource.opentelemetry.io/*` Annotation。
3. 开启 Label 提取后的标准 `app.kubernetes.io/*`。
4. Operator 其他自动推导，**仅作为上游兼容行为**，不能代替 Datafox 的生产版本准入规则。
5. Instrumentation CR 默认 Resource 属性。

上述顺序仅是**按具体属性理解的期望来源**，不能跨环境变量当成统一的覆盖算法。已检查 Operator 在 `env[]` 缺少 `OTEL_SERVICE_NAME` 时会**另行注入该变量**，即使 `OTEL_RESOURCE_ATTRIBUTES` 已设置 `service.name`；若 Pod Label 的 `app.kubernetes.io/instance=order-prod` 而显式 `OTEL_RESOURCE_ATTRIBUTES=service.name=order-service`，SDK 最终名称可能被注入的 `OTEL_SERVICE_NAME=order-prod` 覆盖。受管理注入须同时解析两种变量与 Annotation/Label：最小修正为显式设置一致的 `OTEL_SERVICE_NAME`，或在 Pod Template 加入一致的 `resource.opentelemetry.io/service.name`；无法确定最终一致性则在 CI 拒绝。SDK 最终 Resource 仍可能合并用户代码创建的 Resource 和其他 Detector，因此每种语言必须以真实 OTLP 验证，而不能只查环境变量。[Operator 固定源码](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/instrumentation/sdk.go#L495-L566)、[OTel SDK Resource 规范](https://opentelemetry.io/docs/specs/otel/resource/sdk/)。[Operator Resource Attributes（固定研究源码）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)、[OTel Resource SDK](https://opentelemetry.io/docs/specs/otel/resource/sdk/)。

### 3.2 Datafox 负责的冲突策略

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

### 3.3 安全说明：注入本身也可能造成业务故障

上游已检查源码对 `OTEL_RESOURCE_ATTRIBUTES` 的 `valueFrom` 输入可能追加普通 `value`，引起 Kubernetes Pod CREATE 校验拒绝；`envFrom` 存在同名键时也可能被显式环境变量遮蔽。Java `JAVA_TOOL_OPTIONS.valueFrom` 存在类似不兼容性。此类检查属于**准入前配置验证**，而不是本规范中定义新的 Kubernetes Admission Webhook。详细机制、负面测试和恢复步骤见 [实施与验证手册](implementation-and-verification.md)。

## 4. 证据与验证

本映射需要依据锁定的 Operator/SDK 版本验证 Env 优先级、`envFrom` / `valueFrom`、服务名冲突、Annotation 优先级、Label 版本限制和多容器行为，不能仅以公开 `main` 源码代替产品兼容性结论。具体执行步骤在[实施手册](implementation-and-verification.md)，Tag-03–Tag-07、Tag-11–Tag-15 的输入与断言在[语义合同测试](tagging-contract-tests.md)。

上游权威参考：[Kubernetes Resource Attributes 推荐映射](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/non-normative/k8s-attributes.md)、[OpenTelemetry Operator Resource Attributes](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)、[Resource SDK](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/resource/sdk.md)。本文件描述推荐方案，不代表该方案已部署。
