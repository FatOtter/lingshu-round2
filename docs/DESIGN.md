# DESIGN.md - LingShu 整体设计文档

> **版本**: 0.3.0
> **更新日期**: 2026-02-22
> **状态**: 草稿

---

## 1. 系统定位

LingShu 是一个以 Ontology 为核心的数据操作系统。用户通过 Ontology 建模描述业务世界，通过 Data 关联和探索数据实例，通过 Function 对数据执行操作，通过 Copilot 用自然语言完成上述一切。

**核心理念**：Ontology 是唯一的真理源头。所有能力域——Data、Function、Copilot——都从 Ontology 的定义中派生自己的行为。

---

## 2. 能力域划分

LingShu 由四个能力域组成，每个能力域是一个对用户有意义的完整单元。

### 2.1 Ontology — 定义业务世界

**职责**：管理业务领域的类型定义和数据集成映射。

**边界**：
- 管理 6 种实体类型（SharedPropertyType、PropertyType、InterfaceType、ObjectType、LinkType、ActionType）和 7 种关系边
- 管理版本生命周期（Draft → Staging → Snapshot → Active）
- 配置数据集成映射（AssetMapping：读路径和写路径）

**不负责**：
- 不负责数据实例的关联和查询（Data 的职责）
- 不负责 Action 和 Function 的运行时执行（Function 的职责）

**输入**：用户通过 Ontology Studio UI 或 Copilot 进行类型定义操作。

**输出**：
- 一套经过版本管理的、可查询的类型定义图谱（存储于图数据库）
- 版本快照历史（存储于关系型数据库）
- AssetMapping 配置 → 供 Data 能力域定位数据源
- ActionType 定义 → 供 Function 能力域加载执行引擎

**核心规则**：
- Proto 是源头真理（`proto/ontology.proto`, `proto/validation.proto`, `proto/common.proto`, `proto/interaction.proto`）
- 完整设计见 `ONTOLOGY.md`

### 2.2 Data — 关联和探索数据

**职责**：管理数据源连接，基于 Ontology 定义将底层数据源与类型模型关联，提供数据实例的查询访问能力，管理写回管道基础设施以保证读写一致性。

**边界**：
- 管理数据源连接（Connection CRUD、连接测试、状态监控）
- 根据 AssetMapping 读路径连接底层数据源，建立 Ontology 类型定义与物理数据的映射
- 将底层数据源的原始数据按照 ObjectType/LinkType schema 解析为类型化的数据实例
- 提供数据实例的查询、搜索、筛选、排序能力
- 提供实例间的关系遍历（Object→Link、Link→Object）
- 根据 ComplianceConfig 在数据返回前执行脱敏，所有消费方（前端、Function、Copilot）获取的都是已脱敏数据
- 作为统一的数据读取层，为 Function（实例上下文解析）和 Copilot（数据查询）提供服务
- 管理写回管道基础设施（FDB EditLog、Flink 同步、读取时合并），保证 Read-after-Write 一致性

**不负责**：
- 不负责类型定义的管理（Ontology 的职责）
- 不负责 AssetMapping 的定义（AssetMapping 是 Ontology 中 ObjectType/LinkType 的一部分）
- 不发起数据写入——写入由 Function 执行 Action 触发，通过 Data 管理的写回管道完成
- 不负责前端渲染——Data 返回结构化数据，前端根据 WidgetConfig 自行决定展示形式

**输入**：
- Ontology 定义（类型 schema、AssetMapping 读路径、ComplianceConfig）
- 底层数据源（通过 AssetMapping 的 read_connection_id + read_asset_path 定位）

**输出**：
- 结构化的数据实例（符合 Ontology schema 的对象和关系数据）
- 数据实例上下文 → 供 Function 解析实例引用参数
- 查询结果 → 供 Copilot 返回给用户

### 2.3 Function — 执行操作

**职责**：管理和执行系统中所有可调用的能力，作为 Copilot 的唯一能力入口。

**两类原子能力**：

| 类别 | 来源 | 特征 | 示例 |
|------|------|------|------|
| Ontology Action | Ontology 中定义的 ActionType | 有状态，绑定对象上下文，参数可引用数据实例 | 更新机器人状态、创建任务记录 |
| Global Function | Function 能力域内注册和管理 | 无状态，通用能力 | 查询数据实例、获取类型定义、搜索新闻、代码解释器、发送通知 |

Ontology Action 和 Global Function 统称为**原子能力**，可单独执行，也可编排为**工作流（Workflow）**。

**边界**：
- 加载 Ontology Action：根据 ActionType 定义加载执行引擎（NativeCRUD / PythonVenv / SQLRunner / Webhook）
- 管理 Global Function：注册、版本管理和执行无状态函数（包括封装 Data 和 Ontology 查询能力的函数）
- 向 Copilot 提供统一的可调用能力清单，包括原子能力和工作流（Copilot 的唯一能力入口）
- 解析参数：获取用户输入或从 Data 获取实例引用
- 执行具体逻辑（CRUD 操作、Python 脚本、SQL 语句、Webhook 调用、自定义函数）
- 通过 AssetMapping 写路径将数据变更回写到数据源（Ontology Action）
- 根据 safety_level 决定执行策略（直接执行 / 需要确认 / 需要审批）
- 根据 side_effects 声明记录副作用和审计日志
- 管理执行状态（批量/同步/异步、成功/失败/超时）
- 工作流管理：将多个原子能力编排为工作流（Workflow），定义执行顺序、条件分支和错误处理

**不负责**：
- 不负责 ActionType 的定义和版本管理（Ontology 的职责）
- 不负责数据的底层读取和解析（Data 的职责）

**输入**：
- ActionType 定义（来自 Ontology，参数、引擎、安全级别）
- Global Function 注册信息（Function 内部管理）
- 用户提供的参数值（原始值或实例引用）
- 数据实例上下文（从 Data 能力域获取）

**输出**：
- 执行结果（成功/失败/部分成功）
- 数据变更（通过 AssetMapping 写路径回写到数据源）
- 查询结果（Global Function 返回的 Data/Ontology 查询结果）
- 副作用记录（审计日志）
- 执行状态 → 供 Copilot 感知和展示

### 2.4 Copilot — 用自然语言交互

**职责**：通过 AI Agent 将自然语言转化为系统操作，代理用户完成所有任务；管理智能体基础设施。运行时通过 Function 能力域执行所有操作。

**边界**：
- 理解用户自然语言意图，自主决策调用哪些 Function
- 通过 A2UI 协议流式生成结构化 UI 组件（Table、MetricCard、Form、ConfirmationCard 等）
- 管理对话上下文和会话状态
- 高风险操作的人工确认（Human-in-the-loop）
- 管理智能体基础设施：基座模型配置、Skill 注册与管理、MCP 服务连接、Sub-Agent 配置

**不负责**：
- 不直接与 Data 或 Ontology 交互——运行时一切通过 Function 能力域完成
- 不管理原子能力的注册和加载——Function 能力域负责统一提供
- Copilot 是**代理者**，代替用户与系统交互，自主决定调用哪些 Function 来完成用户意图

**输入**：
- 用户自然语言
- 对话历史和会话上下文
- 当前页面上下文（用户正在查看什么对象/数据）
- 可调用能力清单（Function 能力域提供的原子能力 + 工作流）
- 智能体配置（基座模型、Skill、MCP 连接、Sub-Agent）

**输出**：
- A2UI 流式 UI 组件 → 展示给用户
- Function 调用请求 → 转发给 Function 能力域

---

## 3. 能力域依赖关系

### 3.1 依赖图

```
┌──────────┐
│ Ontology │
│  (定义)   │
└─────┬────┘
      │
 ┌────┴────┐
 │         │
 ▼         ▼
┌────┐  ┌──────────┐
│Data│─→│ Function │
│(关联)│  │  (执行)   │
└────┘  └─────┬────┘
              │
         ┌────▼────┐
         │ Copilot │
         │  (代理)  │
         └─────────┘
```

Ontology 向 Data 和 Function 提供定义，Data 向 Function 提供数据访问能力，Function 是 Copilot 的唯一入口。

### 3.2 依赖说明

| 消费方 | 提供方 | 依赖内容 |
|--------|--------|---------|
| Data | Ontology | ObjectType/LinkType schema、AssetMapping（读路径）、ComplianceConfig |
| Function | Ontology | ActionType 定义（参数、引擎、安全级别）、AssetMapping（写路径）、类型定义数据（供 Global Function 查询） |
| Function | Data | 数据实例上下文（解析实例引用参数）、数据实例（供 Global Function 查询） |
| Copilot | Function | 统一的可调用能力清单（原子能力 + 工作流） |

### 3.3 数据流

以下列举系统中所有能力域间的数据流。

#### 用户 → 能力域

| 发起方 | 目标 | 数据流 | 说明 |
|--------|------|--------|------|
| 用户 | Ontology | 类型定义 CRUD 请求 | 创建/修改/删除 ObjectType、LinkType 等 |
| 用户 | Ontology | 版本管理操作 | 提交 Draft、发布 Staging、回滚 Snapshot |
| 用户 | Ontology | AssetMapping 配置 | 配置数据源的读写路径 |
| 用户 | Data | 数据探索请求 | 浏览、搜索、筛选数据实例 |
| 用户 | Data | 关系图谱探索 | 沿 LinkType 关系浏览关联实例 |
| 用户 | Function | 能力执行请求 | 选择原子能力或工作流、填写参数、触发执行 |
| 用户 | Copilot | 自然语言输入 | 对话、提问、下达任务指令 |
| 用户 | Copilot | 智能体配置操作 | 基座模型、Skill、MCP、Sub-Agent 的管理 |

#### 能力域 → 能力域

| 提供方 | 消费方 | 数据流 | 说明 |
|--------|--------|--------|------|
| Ontology | Data | 类型 schema | Data 根据 ObjectType/LinkType 定义解析数据实例 |
| Ontology | Data | AssetMapping（读路径） | Data 根据读路径定位底层数据源 |
| Ontology | Data | ComplianceConfig | Data 根据合规配置执行数据脱敏 |
| Ontology | Function | ActionType 定义 | Function 根据定义加载执行引擎和参数约束 |
| Ontology | Function | AssetMapping（写路径） | Function 根据写路径将数据变更回写到数据源 |
| Ontology | Function | 类型定义数据 | Function 通过 Global Function 封装 Ontology 查询，供 Copilot 调用 |
| Data | Function | 数据实例上下文 | Function 解析 derived_from 参数时，从 Data 获取实例数据 |
| Data | Function | 数据实例 | Function 通过 Global Function 封装 Data 查询，供 Copilot 调用 |
| Function | Copilot | 可调用能力清单 | Function 向 Copilot 提供统一的能力入口（原子能力 + 工作流） |
| Function | Copilot | 调用结果 | Copilot 获取 Function 调用结果（执行结果或查询结果），呈现给用户 |

#### 能力域 → 外部

| 提供方 | 目标 | 数据流 | 说明 |
|--------|------|--------|------|
| Data | 底层数据源 | 读取请求 | 通过 AssetMapping 读路径从数据源获取数据 |
| Function | 底层数据源 | 写入请求 | 通过 AssetMapping 写路径将变更回写到数据源 |
| Function | 外部系统 | Webhook / API 调用 | Webhook 类型的 Action 或 Global Function 调用外部服务 |
| Copilot | 用户 | A2UI 流式 UI | 通过 SSE 推送结构化 UI 组件给前端渲染 |
| Copilot | LLM 提供商 | 模型推理请求 | 调用基座模型进行自然语言理解和生成 |
| Copilot | MCP 服务 | MCP 协议调用 | 通过 MCP 连接调用外部工具和数据源 |

---

## 4. 横切关注点

以下关注点贯穿所有能力域，当前阶段**设计预留、延后实现**。

### 4.1 租户隔离

**设计原则**：所有资源都 scoped to tenant，API 请求上下文携带 tenant_id。

**预留方式**：
- 图数据库中所有节点和关系包含 `tenant_id` 属性（Ontology 已定义）
- API 请求上下文传递 `tenant_id`
- 数据查询默认附加租户过滤条件
- Agent 会话绑定 tenant 上下文

**延后实现**：
- 租户管理 CRUD
- 租户间数据物理隔离（独立图数据库实例）
- 租户级配额和计费

### 4.2 认证与授权

**设计原则**：资源和操作分离定义，先实现"谁是谁"，再实现"谁能做什么"。

**完整设计**：详见 `SETTING_DESIGN.md`（设置模块设计）。

**实现路径**：
- P0：JWT + HttpOnly Cookie 认证，Auth Middleware，用户 CRUD，`check_permission` 永远返回 True
- P1：三角色 RBAC（admin / member / viewer），租户管理和切换
- P2：自定义角色 + 资源级权限
- P3：SSO/LDAP 集成

### 4.3 可观测性

**设计原则**：每个能力域的关键操作可追溯。

**预留方式**：
- Ontology 的 Snapshot 机制天然提供变更审计
- Function 的 side_effects 声明提供副作用追踪
- Copilot 的对话日志提供交互审计

**延后实现**：
- 结构化日志
- 分布式追踪
- Agent 推理链可视化
- 系统级监控仪表盘

### 4.4 错误处理

**设计原则**：错误分层，每层只处理自己能处理的错误。

**预留方式**：
- Ontology 层：校验错误（PropertyValidationConfig / EntityValidationConfig）、依赖冲突、版本冲突
- Data 层：数据源连接失败、查询超时、数据格式不匹配
- Function 层：执行失败、超时、重试（区分幂等与非幂等）
- Copilot 层：意图识别失败、Tool 调用失败、人工干预升级

---
