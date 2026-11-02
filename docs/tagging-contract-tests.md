---
type: verification-contract-draft
status: proposed
created: 2026-11-02
as_of: 2026-11-02
---

# Datafox Tagging Contract Tests — 跨语言与属性语义验收（草案）

> **状态：Proposal，全部待执行。** 此处是 Tag-01–Tag-15、Inst-01–Inst-08、Domain-01–Domain-09 的**唯一用例定义位置**。从原 [Unified Tagging Convention](unified-tagging-convention.md) 原样迁移合同编号、输入和断言；不是已通过的测试报告，也不新增通用映射工具或 Agent Detector。

测试应使用 [Attribute Registry](attribute-registry.md) 的唯一字段定义、[Datafox 接入合同](unified-tagging-convention.md#3-datafox-接入合同)的功能启用条件和 [Kubernetes Mapping](kubernetes-resource-mapping.md) 的冲突处理规则。T01–T44 的实施步骤与实际执行证据仍由[实施与验证手册](implementation-and-verification.md)管理；Topo-01–Topo-12 仍由[拓扑与隔离模型](deployment-topology-and-isolation.md)管理，本页不复制它们的断言。

## 1. 最小验收合同与下一步

统一标签规范 **尚未实现**。第一批工程测试必须证明：

| Case | 输入 | 需要检查的结果 |
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

### 1.1 多租户、多地域、多单元合同测试

**Topo-01–Topo-12** 分阶段作为拓扑合同：P0 检验租户隔离、标准云 Region、数据驻留；仅在启用 Cell 的 P1 运行单元关联、跨 Cell 发布与查询用例。复杂跨云逻辑地域目录不纳入 P0/P1。具体输入、预期结果和权限边界统一维护在 [拓扑与隔离设计](deployment-topology-and-isolation.md)，不复制为第二套独立权威测试表。

### 1.2 不同标签来源的兼容性案例

| Case | 输入来源 | 需要检查的结果 |
| --- | --- | --- |
| Tag-11 | 自定义 `company.example.com/release` Label，经 Helm 模板映射到 Resource Annotation | 保留企业标签原值，最终 OTel `service.version` 等于目标制品版本 |
| Tag-12 | 只提供显式 `OTEL_RESOURCE_ATTRIBUTES`，无任何推荐 Kubernetes Label | 正常进入 Datafox，SDK Resource 不被 Collector 改写 |
| Tag-13 | 自定义基础设施 Label 仅通过 Collector 白名单提取 | 自定义属性可查询，但不覆盖业务 `service.*` |
| Tag-14 | 无版本且未启用 Release Tracking 的普通 OTel 服务 | 遥测可接收，不被强制推断出发布版本 |
| Tag-15 | 多容器 Pod 与企业自定义 Pod 级版本 Label | 不把一份 Pod Label 作为多个业务容器的不同应用版本 |

这些仍是**拟定测试契约**；实施前需要根据实际 Helm/CI/CD 接入方式落地，不代表已有通用映射工具或已经完成 E2E。

**前置的评审问题**：确定 Datafox 在受管理发布与普通 OTel 接入中的最小字段要求、多租户鉴权和数据驻留的真实部署方案、P1 可选 Cell 的实际来源与应用范围，以及哪些企业标签映射确有业务需要。Service Namespace 的长期语义、版本字符串格式、CI 事件来源和历史数据兼容性仍需逐项确认。完成规范评审后，再锁定 Operator/Collector 版本和开发注入配置。

### 1.3 实例与 IP 合同测试

| Case | 场景 | 预期 |
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

### 1.4 域名、DNS 与 Endpoint 合同测试

| Case | 场景 | 预期 |
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

## 2. 执行证据要求

每个通过的用例必须记录被测语言/Agent、Operator、Collector、SDK 的真实版本和镜像 Digest、输入 Pod/CI 配置、实际 OTLP Resource、Backend Release Event（若启用）、结果与复现命令。尚未运行不得标记为已通过，特别是 Pod CREATE、跨 Tenant、代理 IP 和 `OTEL_SERVICE_NAME` 冲突用例。

本次只是文档归属重构，未运行 Kubernetes 或 Backend E2E。
