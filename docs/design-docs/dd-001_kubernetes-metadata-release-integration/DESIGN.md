---
schema_version: "1.1"
metadata_schema: "1"
artifact_type: design-doc
id: DD-001
doc_type: design
layout: package
title: "Datafox Kubernetes Metadata and Release Integration"
status: draft
working_revision: "1"
published_revision: "0"
research_refs: []
research_not_required_reason: "Existing version-pinned OpenTelemetry Operator and Collector source review, merged architecture proposal, and explicit product scope decisions provide the current design inputs."
adr_refs: []
design_dependencies: []
decision_not_required_reason: ""
approved_by: ""
approved_at: ""
approval_ref: ""
superseded_by: ""
terminal_reason: ""
revision_reason: ""
author: "Datafox engineering (proposal)"
owner: "Unassigned"
created: 2026-11-02
updated: 2026-11-02
---

# Datafox Kubernetes Metadata and Release Integration

This document is the entrypoint for `DD-001`. The logical Design and all
managed package members share one review and approval boundary.

## Design Summary

本 Design 将 Datafox Kubernetes Metadata & Release Integration 的现有架构提案纳入一个可修订、可评审的治理边界。应用 SDK/Agent 负责生成应用身份；OpenTelemetry Operator 在 Pod 创建时按 Opt-in 注入；Collector 只补充可信 Kubernetes 基础设施属性；CI/CD 独立向 Backend 报告 Release/Deployment 事实。预期结果是跨语言的服务、环境和发布版本可关联，而不修改应用运行时的 OpenTelemetry 契约。

主要取舍是复用上游 Operator/Collector 和标准语义，避免自研 Admission Webhook、Kubernetes Detector 或发布 Watcher。该架构目前只适用于**提案与实施规划**：Operator/Collector 版本、Admission 失败策略、业务启动安全、各语言 SDK Resource 合并和 Backend 事件契约均须在实现时锁定并实测。[完整系统架构](../../architecture.md)保留详细时序和源码证据。

## Goals and Non-goals

目标是明确四项设计决策 D1–D4：推荐标准 Pod Label/Annotation 作为版本来源，复用上游 Operator 进行显式 Opt-in，Collector 只补充基础设施属性，CI/CD 主动上报发布事件。统一最终 OTel Resource 语义而非强制客户重命名 Kubernetes Label；隔离 Tenant、Region、Cell 的数据和权限边界；定义上线前预检与 Canary/回滚验收。

非目标包括 Fork Operator/Collector、独立 Datafox Admission Webhook、在 Java Agent 内实现 Kubernetes API 探测、默认强制 Cell、生产环境自动发布，以及在本 Design 中实现 Backend Release API。

## Research and Decision Inputs

**已观察的上游行为：** 锁定的 Operator 源码 `cddb78156d2556c80d3b8fb7c7bbfa7c064f9617` 在缺少 `OTEL_SERVICE_NAME` 时可能依据 Pod 标签注入该变量；SDK 中它优先于 `OTEL_RESOURCE_ATTRIBUTES.service.name`。Operator 默认的实例 ID 可以区分容器，但不能保证同一容器内多个独立 SDK 进程唯一。Collector `k8sattributes` 的 Pod UID/IP 和 Connection 关联需要按接入信任边界配置，不能把客户端自报 Resource 当成身份认证。

**产品设计输入：** D1–D4 来自已合并的 [系统架构提案](../../architecture.md)，不是正式接受的 RepoFoundry ADR；目前没有可引用的已批准 ADR。字段语义以[统一标签规范](../../unified-tagging-convention.md)为准；可信 Tenant、标准 `cloud.region` 与可选 `datafox.unit.id` 以[拓扑提案](../../deployment-topology-and-isolation.md)为准。

**尚未验证：** 实际 Operator/Collector 发行版本、所有语言的 Resource 结果、Admission 与启动失败对业务的影响、发布事件幂等/乱序/回滚的 Backend 实现。当前研究不另立 Research 工件，原因是已有固定上游源码与合并的提案可支撑本次 Design 草案；进入批准或实施前必须更新证据并执行[验收计划](../../implementation-and-verification.md)。

## System Context and Invariants

系统存在两类控制路径和一条遥测数据路径：CI/CD 设置 Pod Template 和发布事实；Kubernetes API 调用 Operator Admission；应用通过 SDK/Agent 发送 OTLP，经可信 Collector 补全后进入 Backend。CI/CD 事件走独立 Backend API，不由 Span 时间推断发布。

不变量：应用服务身份以可信 Tenant + `service.namespace` + `service.name` 关联；Pod UID/IP 不等于进程实例身份，也不能授予 Tenant 权限；Collector 不覆盖用户的 `service.*`；Release 与 Deployment 分离，回滚产生新的 Deployment ID；未经验证的注入不能声明为业务安全。

## Proposed Architecture

**Operator 与应用边界。** Operator 仅负责 Pod 创建阶段的自动注入。应用 SDK/Agent 仍拥有最终 Resource。发布前 CI 应联合检查 `OTEL_SERVICE_NAME`、`OTEL_RESOURCE_ATTRIBUTES`、Resource Annotation、Pod Label 及 `envFrom/valueFrom`，不通过时停止受管理发布，而不是在生产 Admission 时猜测修复。

**Collector 与身份边界。** Collector 只在可信的同集群入口进行 Pod 关联与 Kubernetes 属性补全；跨租户或代理 Gateway 不得依赖未经认证的 UID/IP 或代理连接 IP。不能凭 Pod 关联结果推断授权。 `k8s.pod.ip` 的实际提取须显式配置并按版本验证。

**发布与拓扑边界。** CI/CD 记录版本来源和部署事件，Backend 维护 Deployment 状态机。Tenant 由可信接入决定；Region 使用标准 OTel `cloud.region`；Cell 仅在真实部署隔离需求下使用候选 `datafox.unit.id`。实现示例和边界测试在[实施手册](../../implementation-and-verification.md)，本 Design 不维护第二套配置或属性表。

## Control and Data Flows

**Pod 创建与遥测。** CI 渲染 Pod Template 并检查环境变量来源；Kubernetes API 在 Pod CREATE 时调用 Operator Webhook；符合 Opt-in 的容器被注入 SDK/Agent 配置；应用启动后导出 OTLP Resource。可信 Collector 根据 Pod UID 等条件关联基础设施信息并转发。Webhook fail-open 可能导致 Pod 正常启动但无 Agent；注入成功也可能导致业务启动失败，必须分别监控并进行 Canary。

**Release/Deployment。** CI 构建制品形成 Release，向 Backend 发送一次 Deployment 的 started 事件；部署成功或失败后上报终态。重复事件按 `event_id` 幂等，冲突终态拒绝；回滚旧制品仍生成新 Deployment ID，不能改写原部署历史。具体状态转移表在[实施与验证手册](../../implementation-and-verification.md)。

**多地域与单元。** 同一逻辑服务可部署到不同 `cloud.region` 或可选 Cell。每次独立 Rollout 使用独立 Deployment ID，跨地域/Cell 关联必须保留可信 Tenant 边界。

## Alternatives, Open Questions, and Revisit Triggers

**已排除的首期方案：** 自研 Datafox Admission Webhook 会增加 Pod CREATE 故障面；在每种语言 Agent 中加入 Kubernetes Detector 会重复上游能力并增加维护成本；Collector 重写 `service.name` 会破坏应用身份契约；通过 Kubernetes Watcher 推断 Release 会丢失 CI/CD 构建与部署事实。

**待解决：** 锁定并验证 Operator/Collector/Agent 版本、各语言的最终 Resource 优先级、Webhook 超时与失败策略、可信 Pod Association 的入口隔离、Release API 的 Schema 与鉴权、跨版本/操作系统兼容矩阵。当前责任人未正式指定，不能推断审批权。出现上游注入行为变化、跨租户关联风险或真实 Cell 需求时，应重新评审相应边界。

**状态边界：** 本 Package 是 `draft`，不是批准、发布或生产就绪证据。

## Package Document Map

<!-- DESIGNCTL:MAP:START -->
| Stable reference | Role | Path | Title |
|---|---|---|---|
| `DD-001` | `entrypoint` | `DESIGN.md` | Datafox Kubernetes Metadata and Release Integration |
| `DD-001/DOC-001` | `reading-map` | `README.md` | Datafox Kubernetes Metadata and Release Integration — Reading map |
<!-- DESIGNCTL:MAP:END -->

## Revision Notes

- 2026-11-02 — Created working revision 1.
