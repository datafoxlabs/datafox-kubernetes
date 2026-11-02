# Datafox Kubernetes — 文档总览

> **文档状态（2026-11-02）：** 产品架构与字段约定仍为 **Proposal**，并非全部经过正式治理批准或运行时验证。仓库已初始化 RepoFoundry Harness；其验证结果不等于 Kubernetes/SDK/Backend 的功能验证。

这里是项目的**唯一详细文档导航**，不在本页重复定义产品属性、架构决策或 API。项目简介见 [README](../README.md)，一页架构速览见 [ARCHITECTURE.md](../ARCHITECTURE.md)。

## 1. 按需要阅读

| 你需要回答的问题 | 首选文档 | 本文档的权威范围 |
| --- | --- | --- |
| 服务身份、环境、版本和跨信号关联需要满足哪些 Datafox 条件？ | [统一语义合同](unified-tagging-convention.md) | Datafox 接入策略、身份边界、普通 OTLP 与受管理 Release Tracking 的差异 |
| 标准属性名称、类型、成熟度、作用域、来源是什么？ | [属性登记表](attribute-registry.md) | OTel Attribute 唯一登记表；一行一个 Key；标准属性与自定义提案分开 |
| Kubernetes Label/Annotation 怎样映射，来源冲突时怎么处理？ | [Kubernetes 资源映射](kubernetes-resource-mapping.md) | Operator/SDK 输入、版本优先级、CI 预检与失败行为 |
| Tag、Inst、Domain 用例在哪里定义？ | [语义合同测试](tagging-contract-tests.md) | Tag-01–15、Inst-01–08、Domain-01–09 的唯一用例位置，全部待执行 |
| 为什么复用 Operator？SDK、Collector、CI/CD、Backend 如何协作？发生故障时谁负责？ | [系统架构](architecture.md) | 控制面/数据面、D1–D4 产品设计决策、接口与生命周期、故障域与架构取舍 |
| Tenant、Cloud Region、Cluster、Cell 的关系是什么？哪些可以作为授权或部署目标？ | [部署拓扑与隔离模型](deployment-topology-and-isolation.md) | 可信租户、数据驻留边界、标准地域、可选 `datafox.unit.id`、Topo 合同 |
| 具体怎么安装、预检、金丝雀上线、回滚或验收？ | [实施与验证手册](implementation-and-verification.md) | Operator/Collector 配置示例、发布事件状态机、CI 预检、T01–T44 计划验收与证据要求 |

**阅读顺序：** 先看[统一语义合同](unified-tagging-convention.md)中的产品约束，按需查[属性登记表](attribute-registry.md)、[Kubernetes 映射](kubernetes-resource-mapping.md)与[语义测试](tagging-contract-tests.md)，再看[系统架构](architecture.md)与[拓扑设计](deployment-topology-and-isolation.md)，最后依据[实施手册](implementation-and-verification.md)执行验证。

## 2. 避免重复定义：Source of Truth

规范入口及其属性、映射、测试文档与架构/拓扑/实施文档共享以下职责边界：

| 内容 | 唯一维护位置 | 其他文档应如何引用 |
| --- | --- | --- |
| OTel 字段名、类型、稳定性和上游来源 | [属性登记表](attribute-registry.md) | 不在其它表重写同一属性的基础定义 |
| Datafox 接入条件、跨信号语义 | [统一语义合同](unified-tagging-convention.md) | 不把 P0/P1 或 Datafox Required 混同 OTel Requirement Level |
| Kubernetes 输入映射与冲突处理 | [Kubernetes 资源映射](kubernetes-resource-mapping.md) | 只引用属性 Key 和既有字段定义 |
| Tag/Inst/Domain 合同测试 | [语义合同测试](tagging-contract-tests.md) | 不复制成 T01–T44 的另一个事实来源 |
| Operator/SDK/Collector/CI/CD/Backend 的架构职责 | [系统架构](architecture.md) | 引用组件与数据流，不把实现示例当成架构 |
| Tenant/Region/Cell 身份作用域和阶段划分 | [拓扑与隔离模型](deployment-topology-and-isolation.md) | 使用相同定义，避免另建 Region/Cell 目录或强制字段 |
| Manifest、发布前校验、Canary/回滚操作、事件状态转移明细 | [实施与验证手册](implementation-and-verification.md) | 架构文档只维护不变量与接口边界 |
| RepoFoundry ADR/Design/ExecPlan 的批准与生命周期状态 | 下方对应**受治理索引与工件** | D1–D4 不冒用 ADR ID，也不能从文档讨论推断批准 |

**测试索引不等于测试通过：** 实施验收编号为 **T01–T44**；跨仓库语义合同分别以 **Tag-01–15**、**Topo-01–12**、**Inst-01–08**、**Domain-01–09** 维护。各索引仍是拟执行的合同，不表示测试已运行，也不应被复制为第二套相互冲突的权威测试表。

## 3. 受治理的系统 Design

- [DD-001 — Kubernetes Metadata and Release Integration（Draft）](design-docs/dd-001_kubernetes-metadata-release-integration/DESIGN.md)：以现有系统架构提案为输入的正式 Design Package，当前为工作修订版，**尚未 Review Ready 或 Approved**。原有四份产品文档仍是对应细节的权威来源，Design 负责汇总系统边界与跨文档不变量。
- [Design 生命周期索引](DESIGN-DOCS.md)：由 `designctl` 生成和更新，不能以手动改写索引代替注册、审批或快照。

## 4. RepoFoundry AI 工程治理

以下是 Harness 提供的工程工作流、索引与控制文件。多数仍是**初始化骨架**，不是已完成的研究、批准的 ADR、上线报告或生产 SLO。

| 用途 | 入口 |
| --- | --- |
| Agent 工作约定与路由 | [AGENTS.md](../AGENTS.md) · [RepoFoundry 项目 Skill](../.repo-foundry/skills/repo-foundry-ai/SKILL.md) |
| 决策历史与正式 ADR | [DECISIONS.md](DECISIONS.md) · [DECISION-VIEWS.md](DECISION-VIEWS.md) |
| 设计包与实施计划 | [DESIGN-DOCS.md](DESIGN-DOCS.md) · [Design Docs 索引](design-docs/index.md) · [PLANS.md](PLANS.md) |
| 研究、缺陷与技术债 | [RESEARCH.md](RESEARCH.md) · [BUGFIXES.md](BUGFIXES.md) · [技术债清单](exec-plans/tech-debt-tracker.md) |
| 工程质量与安全 | [QUALITY_SCORE.md](QUALITY_SCORE.md) · [RELIABILITY.md](RELIABILITY.md) · [SECURITY.md](SECURITY.md) |
| Engineering Specifications | [受管规范索引](agent-guides/managed/index.md) · `docs/.engineering/specs.json` · `docs/.engineering/specs.lock.json` |
| Agent 的 Portable 使用说明 | [Agent Engineering Guide](agent-guides/README.md) |

**受管文件约束：** `docs/.engineering/`、`docs/.epctl/`、`docs/.designctl/`、`docs/agent-guides/managed/` 和 `.repo-foundry/` 中的版本、锁与状态遵守各自工具的生命周期规则。不要为了“目录整洁”手动重命名、搬移、重排或改写受管内容；需要升级、登记或修复时使用相应 RepoFoundry 流程及预览/校验。

## 5. 文档变更规则

1. **先确认职责**：属性 Key/类型/稳定性改登记表；接入语义改统一合同；Kubernetes 输入改映射合同；Tag/Inst/Domain 断言改测试合同；架构边界改系统架构；Tenant/Region/Cell 改拓扑模型；实施步骤和运行结果改实施手册。导航页只更新指向。
2. **维持链接稳定**：既有四份设计文档路径保持不变，新规范文件采用独立路径；跨文档引用指向唯一事实来源。补齐相对链接和外部引用迁移方案后才讨论重命名或移动。
3. **保留真实状态**：明确区分 Proposal、已确认设计方向、已实现、已实际测试与未验证；运行命令、测试结果、生产安全或版本兼容结论必须有本次验证证据。
4. **遵守权威来源**：运行时以锁定版本的 OTel API/Operator/Collector 为准；RepoFoundry 治理状态不能靠手写 `ADR-001` 或文档标题代替。
5. **变更检查**：校验 Markdown 结构、相对链接、Mermaid/代码围栏以及所有受影响的合同用例编号；涉及真实配置再执行相应 Helm、Kubernetes、SDK/Collector、Backend 验证。

**未完成的工程前提**：Operator/Collector 与语言组件的生产版本矩阵、可运行的安装配置、正式 CI/CD Release API、责任人及审批记录、业务 SLO 和运行时/E2E 证据仍需后续实施。任何工件不能因被导航页链接就视为已经正式批准。
