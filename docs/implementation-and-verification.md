---
type: synthesis-note
status: proposed
created: 2026-10-30
updated: 2026-10-30
as_of: 2026-10-30
review_after: 2027-01-30
---

# Datafox Kubernetes Integration：实施、安全上线与验证手册

> [!abstract] 使用方式
> 这份手册面向平台工程师、Java Agent 工程师、SRE 和 Datafox Backend 工程师。先阅读 [架构设计](architecture.md)，再按本文推进 P0–P4。
>
> **注意**：下列镜像名称、Endpoint、命名空间和 API 域名是**示例占位值**，未经实际部署验证；不要复制到生产环境直接执行。文中命令是人工实施/验证步骤，本次文档提交没有执行这些命令。

## 1. 目标、前提与验收门槛

目标：新创建的 Java / Python / Node.js / .NET 业务 Pod，或已集成 OTel SDK 的 Go Pod，在不修改业务版本解析代码的前提下，向 Datafox 输出：

~~~text
service.name                  = order-service
service.version               = 2.4.1
deployment.environment.name   = production
k8s.namespace.name            = commerce
k8s.deployment.name           = order-service
k8s.pod.uid                   = <the actual pod UID>
k8s.node.name                 = <the actual node>
~~~

同时 CI/CD 能将同一个 `2.4.1` 版本的 Git Commit、Image Digest 和发布事件报给 Datafox Backend。滚动升级时旧版和新版 Trace 独立可查。

**开始前必须具备**：一个可丢弃的测试 Kubernetes 集群（Kind 或测试环境）、对该集群的管理员安装权限、可以访问的 Collector/测试 OTLP Receiver、Datafox Java Agent 最终 JAR、各语言测试应用、一个可用的镜像仓库，以及能够查看 Pod/Admission Events 的权限。

必须锁定下列版本，不使用 `latest`：

| 依赖 | 版本来源 | 当前状态 |
| --- | --- | --- |
| OTel Operator + CRD | 经 Helm/Operator 官方发布的版本与 Chart Digest | 待选定并测试 |
| OTel Collector Contrib/K8s 发行版 | 包含 `k8sattributes` 的固定版本 | 待选定并测试 |
| Datafox Java Agent | 项目构建产物与 JAR SHA-256 | v2.32.0 为上游研究基线，实际制品待验证 |
| Python / Node.js / .NET Auto Instrumentation | 与选定 Operator 兼容的固定镜像 Digest | 待选定并测试 |
| Go OTel SDK | 应用实际依赖版本 | 按测试应用分别记录 |
| Kubernetes / JDK / OS | 与生产目标一致的矩阵 | 待确定 |

**原则**：本仓库维护版本矩阵与部署配置，不将未经测试的 Operator `main` 源码直接视为生产兼容版本。

## 2. 实施分层与顺序

~~~mermaid
flowchart TD
  P0["P0 锁版本与准备基线"] --> P1["P1 部署 Collector 和 RBAC"]
  P1 --> P2["P2 安装 Operator + Instrumentation CR"]
  P2 --> P3["P3 显式启用 Java Canary"]
  P3 --> P4["P4 多语言 Resource E2E"]
  P4 --> P5["P5 CI/CD Release Events"]
  P5 --> P6["P6 生产渐进上线 + 故障演练"]
  P3 -->|"失败"| Rollback["撤销注入 + 回滚工作负载"]
  P4 -->|"失败"| Rollback
  P6 -->|"失败"| Rollback
~~~

### P0：安装前风险盘点

在测试集群读取现有对象，确认 Operator 是否已由其他团队管理，禁止重复安装：

~~~bash
kubectl get mutatingwebhookconfigurations
kubectl get validatingwebhookconfigurations
kubectl get crd instrumentations.opentelemetry.io
kubectl get deployments --all-namespaces
kubectl get namespaces --show-labels
~~~

记录已有 OpenTelemetry / Istio / Kyverno / Vault 等涉及 Pod Mutation 的组件，重点审查环境变量、Init Container、Volume 和启动参数可能产生的冲突。先保存**未启用注入**的测试应用 Deployment 模板、Pod Spec、启动时间、Ready 比例、内存/CPU、错误率与延迟基线。

**不对 `commerce` Namespace 配置通配注入 Annotation**。每个待测试 Deployment 以自己的 Pod Template 注解显式加入。

## 3. Operator 与 SDK Resource 注入

### 3.1 平台级 Instrumentation CR

以下示例以 OTLP/HTTP `4318` 作为演示协议；生产环境应根据 TLS/认证和镜像能力统一配置。不要把示例域名、镜像和 HTTP 明文配置复制进生产。

~~~yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: datafox
  namespace: commerce
spec:
  defaults:
    useLabelsForResourceAttributes: true
  resource:
    addK8sUIDAttributes: true
  exporter:
    endpoint: http://otel-collector.observability.svc.cluster.local:4318
  env:
    - name: OTEL_EXPORTER_OTLP_PROTOCOL
      value: http/protobuf
    - name: OTEL_TRACES_EXPORTER
      value: otlp
  propagators:
    - tracecontext
    - baggage
  java:
    image: registry.example.com/datafox/java-instrumentation:REPLACE_WITH_VALIDATED_TAG
~~~

这份配置使用上游 v1alpha1 定义的 `spec.defaults.useLabelsForResourceAttributes`、`spec.resource.addK8sUIDAttributes` 和 `spec.env`。用户 Container 显式环境变量高于语言级、公共配置环境变量；Operator 的 Resource 属性还有自己的优先级规则。最终结论必须通过 Pod 环境与 OTLP 输出同时验证。

它只为 Java 指定 Datafox 自定义镜像。Python/Node.js/.NET 使用 Operator 对应版本的上游默认镜像或明确固定镜像。**选择 Instrumentation 版本后，应检查它是否仍支持这些 v1alpha1 字段**。

查证：

~~~bash
kubectl -n commerce get instrumentation datafox -o yaml
kubectl explain instrumentation.spec --recursive
~~~

对于正式配置，至少还应设置安全传输、限制网络出口，禁止把认证 Token 放在公开的 Helm Values 或 Annotation 中。

### 3.2 Java 自定义 Operator 注入镜像

参考 Operator 对应版本的 `autoinstrumentation/java/Dockerfile`，自定义 Datafox 镜像必须提供：

- 根路径 `/javaagent.jar`，内容为**最终发行版 Agent JAR**；
- 该文件对注入 Init Container 用户可读；
- 镜像内包含 `cp` 命令；
- 镜像 CPU 架构匹配目标 Node（如 amd64、arm64）；
- 与 `Instrumentation.spec.java.image` 锁定同一 Digest。

示意 Dockerfile（`datafox-javaagent.jar` 应在构建上下文中且经 SHA 校验）：

~~~dockerfile
FROM busybox:1.36
COPY datafox-javaagent.jar /javaagent.jar
RUN chmod a+r /javaagent.jar
~~~

上例只用于展示必须满足的路径/命令契约；真实发布须固定基础镜像 Digest、扫描漏洞并构建多架构镜像。不能假设 Datafox 的普通 `java -javaagent` JAR 已经满足所有 Operator 镜像约束。要用最终镜像触发一次 Pod Injection，再验证 Init Container 和 JVM 加载。

**未通过这些测试前，不将 Datafox Java 镜像投入生产。**

### 3.3 Java 显式 opt-in Deployment

~~~yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: commerce
spec:
  replicas: 1
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
        app.kubernetes.io/name: order-service
        app.kubernetes.io/version: "2.4.1"
      annotations:
        instrumentation.opentelemetry.io/inject-java: "datafox"
        instrumentation.opentelemetry.io/container-names: "app"
    spec:
      containers:
        - name: app
          image: registry.example.com/order-service:2.4.1
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
~~~

生产应用可有不同探针、端口和启动时间；这里的 Probe 是演示值。务必将 `instrumentation.opentelemetry.io/inject-java` 放在 **Pod Template metadata.annotations** 中，而不是仅放在 Deployment 顶层 metadata。

版本覆盖例子：

~~~yaml
metadata:
  annotations:
    resource.opentelemetry.io/service.version: "2.4.1-hotfix.1"
~~~

此 Annotation 同样必须位于 Pod Template；如果容器已显式设置 `OTEL_RESOURCE_ATTRIBUTES=service.version=...`，应验证用户版本优先保留。Operator 会尝试从镜像 Tag 兜底，但 Datafox 生产发布规则要求 CI 在部署前确认 Label/Annotation/显式版本的存在和合法性，**不能将镜像 Tag 兜底误称为生产发布契约**。

### 3.4 多语言接入

| 语言 | Pod Template 注入 Annotation | 前提 |
| --- | --- | --- |
| Java | `instrumentation.opentelemetry.io/inject-java: "datafox"` | 自定义 Agent 镜像通过 Smoke Test |
| Python | `instrumentation.opentelemetry.io/inject-python: "datafox"` | 上游 Python Auto Instrumentation 镜像兼容 |
| Node.js | `instrumentation.opentelemetry.io/inject-nodejs: "datafox"` | 上游 Node.js Auto Instrumentation 镜像兼容 |
| .NET | `instrumentation.opentelemetry.io/inject-dotnet: "datafox"` | 上游 .NET Auto Instrumentation 镜像兼容 |
| Go（已有 SDK） | `instrumentation.opentelemetry.io/inject-sdk: "datafox"` | SDK 实际读取 `OTEL_*` 环境变量 |

在不同 Namespace 使用 CR 时，按 Operator 版本文档配置跨 Namespace 引用，例如 `other-namespace/datafox`；不应假设任意策略/权限都允许跨 Namespace 引用。

Go SDK 的手动 Resource 构建示意：

~~~go
res, err := resource.New(
    context.Background(),
    resource.WithFromEnv(),
    resource.WithTelemetrySDK(),
)
// 将 res 传入 SDK TracerProvider / MeterProvider 初始化
~~~

上游 Go SDK 的 `resource.WithFromEnv()` 会消费 `OTEL_RESOURCE_ATTRIBUTES`、`OTEL_SERVICE_NAME`。如果应用自己覆盖 Resource 或没有接入 OTel SDK，`inject-sdk` 本身不会创建 Span。

**不在第一版自动开启 Go eBPF 自动注入**：当前 Go 自动注入实现需要可执行路径，并可要求特权配置；和 SDK-only 是不同风险等级。

### 3.5 Pod Mutation 的结果检查

~~~bash
kubectl -n commerce get pod -l app=order-service
kubectl -n commerce describe pod -l app=order-service
kubectl -n commerce get pod -l app=order-service -o yaml
kubectl -n commerce rollout status deployment/order-service
~~~

验收时检查：
- 未加注解的对照 Pod **不出现**额外 Init Container 或 Agent 环境变量；
- 加注解 Pod 只改变指定 `app` 容器，未误注入 Sidecar；
- Java Pod 的 Init Container、Volume、`JAVA_TOOL_OPTIONS` 等符合所选 Operator 版本；
- 实际 OTLP Resource 包含正确的 `service.version`，不能只看 Environment；
- 各语言的业务探针、请求行为与未注入版本一致。

## 4. Collector：仅补基础设施属性

### 4.1 单层 Collector 配置示例

下列是**测试环境用的完整组件片段**，包含 Receiver / Processor / Exporter / Pipeline。需在包含 `k8sattributes` 的 Collector 发行版中运行；真实部署还需完整 Kubernetes Deployment、RBAC、凭证及资源配置。

~~~yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 512

  k8sattributes:
    auth_type: serviceAccount
    passthrough: false
    extract:
      metadata:
        - k8s.namespace.name
        - k8s.pod.name
        - k8s.pod.uid
        - k8s.pod.start_time
        - k8s.deployment.name
        - k8s.replicaset.name
        - k8s.statefulset.name
        - k8s.daemonset.name
        - k8s.node.name
    pod_association:
      - sources:
          - from: resource_attribute
            name: k8s.pod.uid
      - sources:
          - from: resource_attribute
            name: k8s.pod.ip
      - sources:
          - from: connection

  resource/cluster:
    attributes:
      - key: k8s.cluster.name
        value: test-cluster
        action: insert

  batch: {}

exporters:
  otlp/datafox:
    endpoint: datafox-otlp.observability.svc.cluster.local:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource/cluster, batch]
      exporters: [otlp/datafox]
~~~

`tls.insecure: true` 仅适用于受控测试集群。生产必须设置 TLS、认证、队列/重试策略、流量限制与安全出口。Metrics、Logs Pipeline 应按需要分别接入同类 `k8sattributes` 配置；不能只验证 Traces 就声称三个信号均完成。

`k8sattributes` 通过 Pod UID、IP、Connection 的顺序关联。使用 Connection 的处理器必须置于 Batch/Tail Sampling 之前，因为后者会使原始连接上下文不可用。

**禁止在 Datafox 配置中加入**：

~~~yaml
# 反例，Datafox v1 不允许以下来源覆盖应用身份
# extract:
#   metadata:
#     - service.name
#     - service.version
#   otel_annotations: true
~~~

对于需要多容器镜像元数据的场景，先让应用提供 `container.id` 或 `k8s.container.name`，再按官方配置显式打开容器级属性提取；不要将一个 Pod 的任意容器镜像错误附着到所有 Resource。

### 4.2 最小权限与部署形态

平台应参照 Collector Helm Chart 的 `kubernetesAttributes` Preset 生成必要 RBAC，再检查实际权限及 Pod/Workload 读取范围。不要直接授予 `cluster-admin`。

单层 Gateway 能基于 Pod UID 正确关联时可先用 Gateway；如果流量经代理、NAT 或多个 Collector，推荐在靠近应用的数据入口完成 Pod 关联，再转发已带有 Pod UID/基础设施属性的 OTLP。

当 Kubernetes API 不可访问或 Pod 元数据缓存缺失时，保留原始 OTLP Resource；**不反向修改服务版本**，也不根据碰巧相同的 IP 猜测已经删除的 Pod 身份。Collector 仍需独立验证自身排队和出口背压风险。

## 5. CI/CD：版本校验与主动事件上报

### 5.1 发布前校验契约

CI 对**最终渲染的 Pod Template** 做校验，不只检查 Helm Values 源文件。对 Deployment、StatefulSet、DaemonSet、Job、CronJob 分别定位 Template。

建议校验：

- 生产应用至少存在合法的 `service.version` 来源（显式环境、标准 Label 或 Resource Annotation）；
- 版本不能为空、不能是 `latest`、`dev` 这种不可追溯占位值；
- `service.name` 明确且不会因为 `app.kubernetes.io/instance` 等 Label 被意外替换；
- Image Digest 与构建产物元数据已经保留；
- 明确是否打开自动注入，且有对应受验证的 Operator/Instrumentation 版本；
- Helm/Manifest 不重复设置不同语言注入 Annotation；
- Java 镜像与镜像拉取 Secret 在目标 Namespace 可用。

不要新增阻断业务 Pod 创建的自定义 Validating Webhook。缺版本的部署在 CI 阶段失败，已有业务 Pod 不受影响。

### 5.2 Release 与 Deployment 事件

建议后端接口（**设计契约，尚未实现**）：

~~~http
POST /api/v1/deployment-events
Authorization: Bearer <release-scoped-token>
Content-Type: application/json
~~~

~~~json
{
  "event_id": "dep-20261030-001:succeeded",
  "deployment_id": "dep-20261030-001",
  "event_type": "deployment.succeeded",
  "occurred_at": "2026-10-30T05:00:00Z",
  "service": {
    "name": "order-service",
    "namespace": "commerce",
    "version": "2.4.1"
  },
  "artifact": {
    "git_commit": "a4f29c7...",
    "image_digest": "sha256:<full-digest>"
  },
  "target": {
    "environment": "production",
    "cluster": "prod-sg",
    "namespace": "commerce",
    "workload_kind": "Deployment",
    "workload_name": "order-service"
  }
}
~~~

允许的事件类型：`deployment.started`、`deployment.succeeded`、`deployment.failed`、`deployment.rolled_back`。在 CI/CD 中以**同一个 `deployment_id`**关联开始与结束事件；事件重试使用相同 `event_id`，避免重复。

Backend 需要：
- 事件主键在租户范围内唯一，重复请求返回已有结果；
- 状态机允许乱序事件且不会把旧状态覆盖新状态；
- 不同 Deployment 即使同版本也必须独立保存；
- 单独的发布 API 认证、租户隔离和审计；
- `deployment.succeeded` 以发布系统观察到的 Rollout 完成条件为依据；
- 发布事件缺失时不影响 Trace 接收，但部署时间与成功状态标记为未知。

发布事件不携带敏感环境变量、Token 或完整 Pod Spec。

## 6. 如何确认“没有影响业务”

**必须分别检查 Admission 和 Runtime。**

### 6.1 Admission 风险

已检查的 Operator 固定源码快照中，`/mutate-v1-pod` Pod Webhook 标注 `failurePolicy=ignore`，Namespace 查询/Mutator 失败的响应也设置了 `Allowed=true`。这是源码证据，**不代替真实安装版本检查**：

~~~bash
kubectl get mutatingwebhookconfigurations -o yaml
kubectl get validatingwebhookconfigurations -o yaml
~~~

只确认与 Pod CREATE Mutation 相关的 Webhook 的 `failurePolicy`、`namespaceSelector`、`objectSelector`、`timeoutSeconds`、Webhook Service 可达性；不要把其他 CRD 验证 Webhook 的 `Fail` 误认成 Pod Admission 失败行为。

演练：暂时让测试环境 Webhook 不可用（仅有授权时操作），创建**未注入**及**显式启用注入**的测试 Pod，验证失败策略、Event、最终 Pod Spec。禁止在生产直接破坏 Webhook 以测试。

### 6.2 Runtime 风险与 Canary

在业务真实压测场景对照有/无 Agent 的同版本应用。至少观测：

| 指标 | 意义 |
| --- | --- |
| Pod Scheduled → Ready 时间 | 检测 Init Container / Agent 启动开销 |
| Init Container Pull / Exit / Retry | 检测镜像、复制、权限问题 |
| 应用 Startup Logs / Exit Code | 检测 JDK 或框架兼容性 |
| Restart / OOMKilled / CPU / RSS | 检测资源开销 |
| 应用 HTTP 错误率、P95/P99 延迟 | 检测业务行为变化 |
| OTLP 导出成功率、丢弃量、队列容量 | 检测遥测管道失败 |
| Collector Pod 关联成功/失败 | 检测元数据可靠性 |

比较要在相同负载、资源限制、版本下完成。接受阈值须由业务 SLO 和压测目标确定，不能凭文档中的任意百分比宣布“对业务零影响”。

### 6.3 回滚流程

若 Canary 出现 Init Container 失败、Agent 启动错误或业务性能回归：

1. 暂停下一批流量与 Deployment Rollout；
2. 从 Deployment **Pod Template** 移除对应 `inject-*` Annotation，或显式设置 `false`；保持原有用户应用配置；
3. 通过正常 Rollout 重新创建 Pod。**已存在的被 Mutation Pod 不会因删除 Annotation 而自动还原**；
4. 验证新 Pod 中没有新增 Init Container、共享 Volume、Agent 启动选项；
5. 若旧 Pod 启动异常，回退到先前已验证的镜像/Deployment ReplicaSet；
6. 验证业务 Ready、错误率、延迟和资源恢复；记录失败事件和关联日志；
7. 对 Operator Webhook/Collector 的修复与应用回滚分别处理。

平台不得因遥测缺失就自动杀死正常业务 Pod；如果 Datafox Agent 的可用性影响了业务启动，优先停用该工作负载的自动注入。

## 7. 逐项验收矩阵

表中“待验证”是初始状态；仅当 CI 或现场日志证明执行成功时才更新。不要把配置存在视为功能通过。

| ID | 层级 | 场景 | 通过条件 | 状态 |
| --- | --- | --- | --- | --- |
| T01 | 静态 | Helm lint / template、YAML schema、镜像 Digest | 解析成功、版本锁定 | 待验证 |
| T02 | Admission | 没有注解的 Pod | 无 Datafox 注入副作用 | 待验证 |
| T03 | Admission | Java 显式 opt-in | 仅目标容器被修改 | 待验证 |
| T04 | Admission | Webhook 故障，`Ignore` | Pod 允许创建且留下可诊断事件 | 待验证 |
| T05 | Admission | Pod Label 与 Annotation 冲突 | Annotation 版本生效 | 待验证 |
| T06 | Admission | 显式 `OTEL_RESOURCE_ATTRIBUTES` | 显式版本保留 | 待验证 |
| T07 | Admission | 版本来源缺失 | **CI 拒绝**，不新增集群 Webhook | 待验证 |
| T08 | Java | 自定义 Image 文件 / 权限 / Init | JAR 可复制，JVM 加载成功 | 待验证 |
| T09 | Java | Spring Boot `build-info.properties` 冲突 | 最终版本符合显式策略 | 待验证 |
| T10 | Python | Auto Instrumentation | Trace Resource 含正确版本 | 待验证 |
| T11 | Node.js | Auto Instrumentation | Trace Resource 含正确版本 | 待验证 |
| T12 | .NET | Auto Instrumentation | Trace Resource 含正确版本 | 待验证 |
| T13 | Go | SDK-only + `WithFromEnv` | SDK Resource 含正确版本 | 待验证 |
| T14 | Collector | Pod UID / IP / Connection | 依优先级匹配到正确 Pod | 待验证 |
| T15 | Collector | 多容器 Pod | 不把其他容器 Image 关联到业务服务 | 待验证 |
| T16 | Collector | 二级 Collector / Proxy | Pod UID 保留，最终身份不丢 | 待验证 |
| T17 | Collector | K8s API 不可用 / Pod 消失 | 原始遥测可用，不错误关联 | 待验证 |
| T18 | Collector | 属性覆盖检查 | `service.name` 和 `service.version` 未被改写 | 待验证 |
| T19 | Signals | Traces、Metrics、Logs | 各已启用信号的资源符合契约 | 待验证 |
| T20 | CI/CD | started → succeeded | Backend 保存一次 Deployment 和事件 | 待验证 |
| T21 | CI/CD | 重复事件 / 乱序事件 | 幂等且状态正确 | 待验证 |
| T22 | CI/CD | 同版本重复部署 / 回滚 | 不合并不同 Deployment | 待验证 |
| T23 | Backend | 新旧版本滚动并存 | 能分别查询两个 `service.version` | 待验证 |
| T24 | 安全 | Agent 镜像不可拉取 | Canary 检出并能按文档回滚 | 待验证 |
| T25 | 安全 | Java Agent/JDK 兼容性 | 目标 JDK 矩阵与业务 Smoke Test 通过 | 待验证 |
| T26 | 安全 | 性能 / 压测 | 与基线对比满足明确 SLO | 待验证 |
| T27 | 安全 | Webhook / Collector 升级 | 回归测试通过，业务 Pod 未被意外 Mutation | 待验证 |
| T28 | 安全 | RBAC / 元数据选择 | 最小权限，不批量采集敏感 Labels/Annotations | 待验证 |

### 7.1 E2E 最小断言

每个语言测试服务主动生成一个 Trace，由**测试 OTLP Receiver**读取实际 Resource，比较：

~~~text
assert resource["service.name"] == "order-service"
assert resource["service.version"] == "2.4.1"
assert resource["k8s.namespace.name"] == "commerce"
assert resource["k8s.pod.uid"] == kubectl_get_pod_uid()
assert resource["k8s.deployment.name"] == "order-service"
assert collector_output["service.version"] == sdk_output["service.version"]
~~~

这段是测试断言伪代码，非可直接执行脚本。针对指标和日志也需要类似 Resource 检查；没有启用某个 SDK 信号的语言不宣称该信号已通过。

### 7.2 版本冲突数据集

| 显式 | Annotation | Label | 结果 |
| --- | --- | --- | --- |
| `3.0.0` | `2.0.0` | `1.0.0` | `3.0.0` |
| 无 | `2.0.0` | `1.0.0` | `2.0.0` |
| 无 | 无 | `1.0.0` | `1.0.0` |
| 无 | 无 | 无 | CI 拒绝正式发布 |

同时记录最终 Pod 注入的 `OTEL_RESOURCE_ATTRIBUTES` 和 SDK 实际发送的 Resource，以发现不同语言 SDK 自身版本检测与平台版本覆盖的差异。

## 8. 交付边界与里程碑

| 里程碑 | 工作内容 | 门禁 |
| --- | --- | --- |
| M0 | 锁定 Operator、Collector、语言镜像/JDK/K8s 矩阵，建立基线 | 版本表与兼容性计划经评审 |
| M1 | Datafox Java 注入镜像 + Instrumentation 配置 | T01–T09 |
| M2 | Collector 基础设施补全 + Pod 关联 | T14–T18、T28 |
| M3 | Python / Node.js / .NET / Go E2E | T10–T13、T19 |
| M4 | Release Tracking API / CI 事件联调 | T20–T23 |
| M5 | 安全故障演练、压力测试、升级验证 | T24–T27 |

本仓库可以先维护文档、Helm 配置和 E2E；Release Tracking 的 Backend API 由 Datafox Backend 仓库实现。在没有 Backend 联调前，M4 不得标记为完成。

## 9. 证据与执行记录

研究快照：

- [Operator Resource Attributes（commit cddb781）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/resource-attributes.md)
- [Operator Instrumentation CR 类型（同 commit）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/apis/v1alpha1/instrumentation_types.go)
- [Operator Java Dockerfile（同 commit）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/autoinstrumentation/java/Dockerfile)
- [Operator SDK-only（同 commit）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/docs/auto-instrumentation/languages/sdk-only.md)
- [Operator Pod Webhook（同 commit）](https://github.com/open-telemetry/opentelemetry-operator/blob/cddb78156d2556c80d3b8fb7c7bbfa7c064f9617/internal/webhook/podmutation/webhookhandler.go)
- [Collector k8sattributes（commit d63fa33）](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/d63fa334e03aa36d0ac2cd29af05cc8f60d164fc/processor/k8sattributesprocessor/README.md)
- [OTel Go SDK Resource 例子](https://github.com/open-telemetry/opentelemetry-go/blob/73c24babfd982206e57ebce54b388e686fe90177/sdk/resource/example_test.go)

**已完成**：基于固定上游源码/文档核对的设计与实施方案整理。

**尚未执行**：Kubernetes/Helm 命令、Agent Image 构建、Collector 校验、CI/CD 发布事件联调、Mermaid 实际渲染与全部 E2E 测试。后续 PR 应附上真实 CI Job、Pod Event、Resource 断言与性能对比证据。

## 10. 操作完成后的回顾问题

1. 业务 Pod 没有启用注入时，创建和启动过程是否完全保持原样？
2. 在 Webhook 不可达和 Agent Init Image 不可拉取时，分别发生什么？
3. 哪个真实 OTLP Resource 证明各语言有相同 `service.version`？
4. Collector 为什么必须保留应用侧的服务身份？
5. 一次 Release 重复部署两次，Release Tracking 如何区分 Deployment？
