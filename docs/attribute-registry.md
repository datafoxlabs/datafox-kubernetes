---
type: specification-draft
status: proposed
created: 2026-11-02
as_of: 2026-11-02
---

# Datafox Attribute Registry — OTel 属性登记表（草案）

> **状态：Proposal，尚未批准。** 本文件是 Datafox 在当前 Kubernetes 集成方案中引用的属性的**唯一字段登记位置**。上游的 Key、Type、Stability 和原始语义始终以 [OpenTelemetry Semantic Conventions](https://github.com/open-telemetry/semantic-conventions) 为准；本登记表不重新定义上游属性。类型/稳定性依据 2026-11-02 检查的官方 `main` 文档快照，**不是生产组件的版本锁定或兼容性证明**。

## 1. 读表规则

- **Key**：一行一个完整属性名，不用复合行隐藏类型差异；引用上游 Attribute Registry。
- **Scope**：描述当前 Datafox 方案在哪里使用属性。Resource、Span 和其他数据点属性不相互替代；同名属性在其他合规场景出现不自动非法。
- **Type / Stability**：从 OTel Registry 引用，不由 Datafox 修改；部分 Resource 语义的上游 Requirement Level 取决于所属实体或信号，不能由属性键单独推断。
- **阶段**：P0、P1 表示 Datafox 当前设计与验收规划，**不等于 OTel Required**，也不等于所有语言和信号都必须包含。何时必需由[接入场景合同](unified-tagging-convention.md#3-datafox-接入合同)决定。
- **来源**：推荐的数据所有者或生产者，并非 SDK/Operator/Collector 在所有版本中的自动配置保证；具体注入顺序见[Kubernetes 映射合同](kubernetes-resource-mapping.md)。

Datafox 不以任何 `datafox.*` 私有属性替代上游 `service.*`、`k8s.*` 或 `cloud.*`。同一个 Key 的默认值、合规条件和不同来源冲突只在相应合同中定义，不在多张字段表重复定义。

## 2. 应用服务与发布

| Attribute | Scope | OTel Type | OTel Stability | Datafox 阶段 | 数据来源与使用边界 |
| --- | --- | --- | --- | --- | --- |
| [`service.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/service.md) | Resource | `string` | Stable | P0 | 应用/SDK；受管理注入需核对 Operator；逻辑服务名；缺省 `unknown_service:*` 对普通 OTLP 可接入，但不满足受管理发布所需的明确业务身份 |
| [`service.namespace`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/service.md) | Resource | `string` | Stable | P0 可选 | 应用/SDK；逻辑服务的命名空间；不等于 `k8s.namespace.name`，空值按上游未指定语义处理 |
| [`service.version`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/service.md) | Resource | `string` | Stable | P0 有条件 | 构建/发布配置 → 应用 SDK；应用制品版本，受管理 Release Tracking 必须与发布事件一致；不等于 Image Tag 或 Deployment ID |
| [`service.instance.id`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/service.md) | Resource | `string` | Stable | P0 推荐 | SDK/Instrumentation；同一服务并存实例须唯一；Collector 不得仅凭 Pod UID/IP 猜测进程级 ID |
| [`deployment.environment.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/deployment.md) | Resource | `string` | Stable | P0 有条件 | 应用/部署配置；环境比较或受管理发布关联需要；环境值由企业定义 |
| [`telemetry.distro.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/telemetry.md) | Resource | `string` | Stable | P1 | Agent Distribution；标识产生遥测的发行版，不是应用服务名 |
| [`telemetry.distro.version`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/telemetry.md) | Resource | `string` | Stable | P1 | Agent Distribution；标识 Agent 发行版版本，不是 `service.version` |
| [`vcs.ref.head.revision`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/vcs.md) | Resource（适用时） | `string` | Release Candidate | P1 | CI/CD 或构建系统；VCS 修订；不替代 Release 事件或应用版本 |

## 3. Kubernetes 运行位置

| Attribute | Scope | OTel Type | OTel Stability | Datafox 阶段 | 数据来源与使用边界 |
| --- | --- | --- | --- | --- | --- |
| [`k8s.cluster.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0（K8s） | 集群配置/Collector；可读集群名；不单独承担跨租户唯一身份 |
| [`k8s.cluster.uid`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P1 | 可信 Kubernetes API/Collector；`kube-system` Namespace UID 代表的集群伪 ID；无权限时不伪造 |
| [`k8s.namespace.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0（K8s） | Kubernetes API/Collector；运行 Pod 的 Kubernetes Namespace，与逻辑 Service Namespace 不同 |
| [`k8s.deployment.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes API/Collector；实际 Deployment 名；仅所属 Workload 类型适用时提供 |
| [`k8s.statefulset.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes API/Collector；实际 StatefulSet 名 |
| [`k8s.daemonset.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes API/Collector；实际 DaemonSet 名 |
| [`k8s.replicaset.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes API/Collector；实际 ReplicaSet 名 |
| [`k8s.cronjob.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes API/Collector；实际 CronJob 名 |
| [`k8s.job.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes API/Collector；实际 Job 名 |
| [`k8s.pod.uid`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0（K8s） | Operator/可信 Collector；Pod 关联键；自报 UID 不能作为接入身份或 Tenant 授权依据 |
| [`k8s.pod.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P1 | Kubernetes API/Collector；可读定位，不替代 Pod UID |
| [`k8s.pod.ip`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P0 适用时 | Kubernetes `status.podIP`/可信 Collector；当前 Pod IP 单值；可能复用且不是进程/Pod 不可变身份 |
| [`k8s.node.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P1 | Kubernetes API/Collector；Node 定位 |
| [`k8s.node.uid`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P1 | Kubernetes API/Collector；Node UID；不把 Pod IP 当 Node IP |
| [`k8s.container.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource | `string` | Stable | P1 | PodSpec/SDK/Collector；Container 区分；不能在多容器 Pod 中盲选 |
| [`k8s.service.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/k8s.md) | Resource（适用时） | `string` | Development | P1 可选 | Kubernetes API/Collector；Kubernetes Service 名；不能替代应用 `service.name` |

## 4. 容器、主机与云环境

| Attribute | Scope | OTel Type | OTel Stability | Datafox 阶段 | 数据来源与使用边界 |
| --- | --- | --- | --- | --- | --- |
| [`container.id`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/container.md) | Resource | `string` | Stable | P1 | 容器运行时/可信采集；运行时容器标识 |
| [`container.image.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/container.md) | Resource | `string` | Stable | P1 | 容器运行时/可信采集；镜像名称，不能直接当 Release 版本 |
| [`container.image.tags`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/container.md) | Resource | `string[]` | Stable | P1 | 容器运行时/可信采集；镜像标签数组；不等于历史 `container.image.tag` 单字符串 |
| [`container.image.repo_digests`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/container.md) | Resource | `string[]` | Stable | P1 | 容器运行时/可信采集；镜像仓库 Digest 数组；制品定位不等于 Deployment ID |
| [`cloud.provider`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/cloud.md) | Resource（上下文相关） | `string` | Development | P0 适用时 | 云平台/可信采集；原生云厂商名称，按上游枚举 |
| [`cloud.account.id`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/cloud.md) | Resource（上下文相关） | `string` | Development | P0 适用时 | 云平台/可信采集；云账号；不是 Datafox Tenant ID |
| [`cloud.region`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/cloud.md) | Resource（上下文相关） | `string` | Development | P0 适用时 | 云平台/可信采集；保留云厂商原生 Region；不自行创建跨云逻辑地域 ID |
| [`cloud.availability_zone`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/cloud.md) | Resource（上下文相关） | `string` | Development | P1 | 云平台/可信采集；云可用区；不是 Cell |
| [`cloud.resource_id`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/cloud.md) | Resource | `string` | Development | P1 | 云平台/可信采集；云资源标识；不代替 `service.instance.id` |
| [`host.id`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/host.md) | Resource | `string` | Development | P1（主机场景） | Host Resource Detector；主机 ID；不等于应用实例 ID |
| [`host.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/host.md) | Resource | `string` | Development | P1（主机场景） | Host Resource Detector；主机名，不等于 HTTP Host/服务域名 |
| [`host.ip`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/host.md) | Resource | `string[]` | Development | P1（主机场景） | Host Resource Detector；非回环主机 IP 数组，不当单值 Pod IP |

## 5. 网络请求与域名（非服务 Resource）

| Attribute | Scope | OTel Type | OTel Stability | Datafox 阶段 | 数据来源与使用边界 |
| --- | --- | --- | --- | --- | --- |
| [`server.address`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/server.md) | Span/连接上下文 | `string` | Stable | P0 按 Instrumentation | 上游 HTTP/RPC Instrumentation；已知服务器域名；缺失时允许 IP，不做强制反向 DNS |
| [`server.port`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/server.md) | Span/连接上下文 | `int` | Stable | P0 按 Instrumentation | 上游 HTTP/RPC Instrumentation；服务器端口 |
| [`client.address`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/client.md) | Span/连接上下文 | `string` | Stable | P0 按 Instrumentation | 上游 Instrumentation；请求客户端地址；遵守代理信任链和隐私策略 |
| [`network.local.address`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/network.md) | Span/网络连接上下文 | `string` | Stable | P0 按 Instrumentation | 上游 Instrumentation；连接本地地址，不是主机或服务实例身份 |
| [`network.peer.address`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/network.md) | Span/网络连接上下文 | `string` | Stable | P0 按 Instrumentation | 上游 Instrumentation；连接对端地址，不是 `k8s.pod.ip` 的替代 |
| [`url.full`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/url.md) | Span/请求上下文 | `string` | Stable | P0 按 Instrumentation | 上游 Instrumentation；实际 URL；敏感信息按对应 SemConv 清理 |
| [`dns.question.name`](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/dns.md) | Span/DNS 查询上下文 | `string` | Development | P1 | 上游 DNS Instrumentation；DNS 查询名，不自动提升为服务 Resource |

## 6. Datafox 自定义属性与非 Resource 身份

| Key 或身份 | 类型与存储位置 | 状态 | 规则 |
| --- | --- | --- | --- |
| `datafox.unit.id` | `string`，Resource（单元化工作负载） | P1 **可选 Datafox 提案**，不属于 OTel SemConv | 稳定的 Cell / 业务流量或故障隔离单元；启用时在 `(trusted_tenant_id, deployment.environment.name, datafox.unit.id)` 作用域唯一，不要求普通应用提供；权威定义在[拓扑与隔离模型](deployment-topology-and-isolation.md) |
| `tenant_id`（平台内部） | Backend 可信身份上下文，**不是 Resource** | P0 | 由接入认证、授权与数据路由确定；不信任 OTLP/Pod Label 自报值，不将 `service.namespace` 当 Tenant |
| `datafox.region.id` | 尚未定义正式 Resource 契约 | P2 候选，当前暂缓 | 使用标准 `cloud.region`；有实际跨云逻辑地域需求后重新评审 |
| `release_id` / `deployment_id` / `event_id` | Datafox Release Event API | P0/P1 事件模型（提案） | 独立于 Resource；同一版本多次发布使用不同 Deployment ID |

## 7. 明确的禁用与兼容边界

- `deployment.environment` 已废弃，新数据使用 `deployment.environment.name`。
- `container.image.tag` 不等于稳定的 `container.image.tags`（`string[]`）；旧 Collector 的输出须单独验证迁移和类型转换。
- `net.host.ip`、`net.peer.ip` 已废弃；连接语义使用上游现行 `network.*` 或 `server.*` / `client.*` 语义，不拿它们拼装 Resource 实例 IP。
- `deployment.id` 等上游 Development 属性不是 Datafox v1 的跨语言强制 Resource；发布身份以独立 API 事件为准。
- 不创建 `datafox.instance.ip`、`datafox.env`、`datafox.service`、`datafox.version` 作为平行标准字段。
- 不全量采集任意 Kubernetes Label、Annotation、HTTP Header、客户个人信息或 Secret 进入通用 Resource；按白名单、最小权限和基数预算控制。

## 8. 与其他文档的关系

本文件只保管**属性 Key、类型、成熟度、位置和引用**，不定义 Operator Env 合并算法、发布状态机或 Backend 查询权限。应用与发布需要什么属性见[统一语义合同](unified-tagging-convention.md)，Kubernetes Label/Annotation 的输入与冲突规则见[映射合同](kubernetes-resource-mapping.md)，实例/IP/Domain 与跨语言回归用例见[语义合同测试](tagging-contract-tests.md)，Tenant/Region/Cell 的身份范围见[拓扑设计](deployment-topology-and-isolation.md)。

### 上游权威资料

- [OTel Service Resource Semantic Conventions](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/resource/service.md)
- [OTel Semantic Convention Attribute Registry](https://github.com/open-telemetry/semantic-conventions/tree/main/docs/registry/attributes)
- [OTel Resource SDK Specification](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/resource/sdk.md)
- [OTel Attribute Requirement Levels](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/general/attribute-requirement-level.md)

**未验证：** 本文件未证明目标 Operator、Collector、各语言 SDK 的实际 Resource 合成结果；正式接入前须锁定版本并执行测试。
