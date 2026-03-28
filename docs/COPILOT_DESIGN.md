# COPILOT_DESIGN.md - 智能体模块设计

> **版本**: 0.1.0
> **更新日期**: 2026-03-03
> **状态**: 草稿
> **前置文档**: `DESIGN.md`（能力域边界）、`TECH_DESIGN.md`（API/RID/错误规范）、`PRODUCT_DESIGN.md`（模块结构）、`FUNCTION_DESIGN.md`（FunctionService Protocol / 能力清单）

---

## 1. 模块定位

智能体模块是 Copilot 能力域的完整实现，覆盖后端服务和前端交互。

**职责**：
- 理解用户自然语言意图，自主决策调用哪些 Function 完成任务
- 通过 A2UI 协议流式生成结构化 UI 组件，在对话中嵌入可交互的数据展示
- 管理对话上下文和会话状态
- 高风险操作的人工确认（Human-in-the-loop）
- 管理智能体基础设施：基座模型配置、Skill 注册与管理、MCP 服务连接、Sub-Agent 配置

**不负责**：
- 不直接与 Data 或 Ontology 交互——运行时一切通过 FunctionService 完成
- 不管理原子能力的注册和加载——Function 能力域负责统一提供
- Copilot 是**代理者**，代替用户与系统交互

**两种交互入口**：

| 入口 | 位置 | 上下文范围 | 说明 |
|------|------|-----------|------|
| Copilot Shell | 全局右侧面板 | 当前模块上下文 | 辅助当前模块操作，可拒绝无关请求 |
| 智能体模块对话 | Main Stage 内容区域 | 全系统 | 通用对话，可调用所有能力 |

两个入口共享同一套后端 Agent 执行引擎和 A2UI 协议，区别在于系统提示词和可用工具范围。

---

## 2. 后端服务设计

### 2.1 服务层架构

```
copilot/
├── router.py               # FastAPI 路由定义
├── service.py               # 业务逻辑（CopilotServiceImpl）
├── interface.py             # Protocol 接口（当前无消费方）
├── agent/
│   ├── graph.py             # LangGraph Agent 定义（节点、边、状态）
│   ├── state.py             # Agent 状态定义（对话历史、工具调用记录）
│   ├── tools.py             # Tool 绑定（FunctionService 能力 → LLM Tool）
│   ├── prompts.py           # 系统提示词（Shell 模式 / 通用模式）
│   └── context.py           # 上下文管理（页面上下文、会话上下文）
├── a2ui/
│   ├── protocol.py          # A2UI 协议定义（事件类型、组件 schema）
│   ├── components.py        # A2UI 组件类型定义
│   └── renderer.py          # A2UI 渲染器（Agent 输出 → SSE 事件流）
├── sessions/
│   ├── manager.py           # 会话管理（创建、恢复、归档）
│   └── repository.py        # 会话持久化（PostgreSQL）
├── infra/
│   ├── models.py            # 基座模型管理
│   ├── skills.py            # Skill 管理
│   ├── mcp.py               # MCP 服务连接管理
│   └── subagents.py         # Sub-Agent 管理
└── schemas/
    ├── requests.py          # 请求 DTO
    └── responses.py         # 响应 DTO
```

**关键约束**：
- Copilot 通过 FunctionService Protocol 调用所有能力，不依赖其他能力域
- Agent 执行使用 LangGraph 构建有状态的多步推理图
- Agent 检查点通过 `AsyncPostgresSaver` 持久化，支持会话恢复和 interrupt/resume
- 会话元数据和基础设施配置持久化到 PostgreSQL

### 2.2 API 设计

遵循 `TECH_DESIGN.md` 第 3 节的 API 规范。URL 前缀 `/copilot/v1/`。

#### 2.2.1 对话 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/copilot/v1/sessions` | 创建新会话 |
| POST | `/copilot/v1/sessions/{session_id}/messages` | 发送消息（返回 SSE 事件流） |
| POST | `/copilot/v1/sessions/{session_id}/resume` | 恢复中断的 Agent 执行（确认/取消高风险操作） |
| PUT | `/copilot/v1/sessions/{session_id}/context` | 更新会话上下文（页面切换，不触发 Agent） |
| GET | `/copilot/v1/sessions/{session_id}` | 获取会话详情（含历史消息，从 checkpoint 提取） |
| POST | `/copilot/v1/sessions/query` | 查询会话列表 |
| DELETE | `/copilot/v1/sessions/{session_id}` | 删除会话 |

**创建会话**：

```json
POST /copilot/v1/sessions

{
  "mode": "shell",
  "context": {
    "module": "ontology",
    "page": "/ontology/object-types/ri.obj.{uuid}",
    "entity_rid": "ri.obj.{uuid}",
    "branch": "main"
  }
}
```

| 字段 | 说明 |
|------|------|
| `mode` | `"shell"`（Copilot Shell）或 `"agent"`（智能体模块对话） |
| `context` | 页面上下文（shell 模式必填）：当前模块、页面路径、正在查看的实体 RID、当前数据分支 |

**创建会话响应**：

```json
{
  "data": {
    "session_id": "ri.session.{uuid}",
    "mode": "shell",
    "created_at": "2026-03-03T10:00:00Z"
  }
}
```

**发送消息**：

```json
POST /copilot/v1/sessions/{session_id}/messages

{
  "content": "帮我查一下所有电量低于20%的机器人"
}
```

响应为 **SSE 事件流**（`Content-Type: text/event-stream`），详见 §2.4 A2UI 协议。

**获取会话详情**：

历史消息存储在 LangGraph 的 checkpoint 中（AsyncPostgresSaver），不在 sessions 表。API 层通过 `graph.get_state(config)` 从 checkpoint 提取 `messages` 列表，与 sessions 表的元数据组合返回：

```python
state = graph.get_state({"configurable": {"thread_id": session_id}})
messages = state.values["messages"]   # 完整对话历史
summary = state.values.get("summary") # 长对话摘要（如有）
```

**恢复执行**（确认/取消高风险操作）：

```json
POST /copilot/v1/sessions/{session_id}/resume

{
  "approved": true
}
```

Agent 因高风险操作暂停时（`interrupt()`），前端通过此接口恢复执行。内部通过 `graph.invoke(Command(resume=approved), config)` 恢复图执行。响应同样为 SSE 事件流。

#### 2.2.2 基座模型 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/copilot/v1/models` | 注册基座模型 |
| POST | `/copilot/v1/models/query` | 查询模型列表 |
| GET | `/copilot/v1/models/{rid}` | 获取模型详情 |
| PUT | `/copilot/v1/models/{rid}` | 更新模型配置 |
| DELETE | `/copilot/v1/models/{rid}` | 删除模型 |

**注册请求**：

```json
POST /copilot/v1/models

{
  "api_name": "gpt4o",
  "display_name": "GPT-4o",
  "provider": "openai",
  "connection": {
    "api_base": "https://api.openai.com/v1",
    "api_key_ref": "secret:openai_key",
    "model_id": "gpt-4o"
  },
  "parameters": {
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "is_default": true
}
```

| 字段 | 说明 |
|------|------|
| `provider` | 模型供应商标识（`openai` / `anthropic` / `azure_openai` / `custom`） |
| `connection` | 连接配置，`api_key_ref` 引用加密存储的凭证 |
| `parameters` | 模型推理参数 |
| `is_default` | 是否为默认模型（全局唯一） |

#### 2.2.3 Skill API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/copilot/v1/skills` | 注册 Skill |
| POST | `/copilot/v1/skills/query` | 查询 Skill 列表 |
| GET | `/copilot/v1/skills/{rid}` | 获取 Skill 详情 |
| PUT | `/copilot/v1/skills/{rid}` | 更新 Skill |
| DELETE | `/copilot/v1/skills/{rid}` | 删除 Skill |

**Skill 定义**：

```json
{
  "api_name": "data_analysis",
  "display_name": "数据分析助手",
  "description": "分析数据实例的统计特征和趋势",
  "system_prompt": "你是一个数据分析助手，擅长...",
  "tool_bindings": [
    { "type": "capability", "rid": "ri.func.{uuid_1}" },
    { "type": "mcp", "rid": "ri.mcp.{uuid_2}" }
  ],
  "enabled": true
}
```

Skill 是一组预配置的系统提示词 + 工具绑定。Agent 运行时可激活一个或多个 Skill，将其提示词和工具注入 Agent 上下文。

`tool_bindings` 中 `type` 支持 `capability`（FunctionService 的能力 RID）和 `mcp`（MCP 服务 RID，加载该服务发现的所有 Tools）。

#### 2.2.4 MCP API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/copilot/v1/mcp` | 注册 MCP 服务连接 |
| POST | `/copilot/v1/mcp/query` | 查询 MCP 服务列表 |
| GET | `/copilot/v1/mcp/{rid}` | 获取 MCP 服务详情 |
| PUT | `/copilot/v1/mcp/{rid}` | 更新 MCP 服务 |
| DELETE | `/copilot/v1/mcp/{rid}` | 删除 MCP 服务 |
| POST | `/copilot/v1/mcp/{rid}/test` | 测试 MCP 服务连接 |

**MCP 服务定义**：

```json
{
  "api_name": "github_tools",
  "display_name": "GitHub 工具集",
  "description": "通过 MCP 连接 GitHub，提供代码搜索、PR 管理等能力",
  "transport": {
    "type": "sse",
    "url": "https://mcp.example.com/github/sse"
  },
  "auth": {
    "type": "bearer",
    "token_ref": "secret:github_mcp_token"
  },
  "enabled": true
}
```

| 字段 | 说明 |
|------|------|
| `transport.type` | MCP 传输类型（`sse` / `stdio`） |
| `transport.url` | SSE 类型的 MCP 服务端点 |
| `auth` | 认证配置，`token_ref` 引用加密存储的凭证 |

MCP 服务连接成功后，其提供的 Tools 自动纳入 Agent 的可用工具列表。Agent 调用 MCP Tool 时，Copilot 通过 MCP 协议转发请求。

#### 2.2.5 Sub-Agent API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/copilot/v1/sub-agents` | 创建 Sub-Agent |
| POST | `/copilot/v1/sub-agents/query` | 查询 Sub-Agent 列表 |
| GET | `/copilot/v1/sub-agents/{rid}` | 获取 Sub-Agent 详情 |
| PUT | `/copilot/v1/sub-agents/{rid}` | 更新 Sub-Agent |
| DELETE | `/copilot/v1/sub-agents/{rid}` | 删除 Sub-Agent |

**Sub-Agent 定义**：

```json
{
  "api_name": "report_writer",
  "display_name": "报告生成器",
  "description": "根据数据分析结果生成结构化报告",
  "model_rid": "ri.model.{uuid}",
  "system_prompt": "你是一个专业的报告撰写助手...",
  "tool_bindings": [
    { "type": "capability", "rid": "ri.func.{uuid_1}" },
    { "type": "mcp", "rid": "ri.mcp.{uuid_2}" }
  ],
  "safety_policy": {
    "max_tool_calls": 20,
    "allowed_safety_levels": ["SAFETY_READ_ONLY", "SAFETY_IDEMPOTENT_WRITE"],
    "require_parent_approval_above": "SAFETY_IDEMPOTENT_WRITE"
  },
  "enabled": true
}
```

| 字段 | 说明 |
|------|------|
| `model_rid` | 该 Sub-Agent 使用的基座模型（可与主 Agent 不同） |
| `system_prompt` | Sub-Agent 专属的系统提示词 |
| `tool_bindings` | 可用工具（`capability` 引用 FunctionService 能力，`mcp` 引用 MCP 服务的工具） |
| `safety_policy` | 安全策略：最大工具调用次数、允许的安全级别、超出级别时需主 Agent（用户）审批 |

用户配置的 Sub-Agent 与系统内置 Sub-Agent 共享同一编排机制——通过 `create_agent()` 创建并包装为 Tool，由主 Agent 的 `supervisor` 按需调用（见 §2.3.3）。Sub-Agent 在自己的工具范围内自主执行，结果返回给主 Agent。

### 2.3 Agent 执行引擎

基于 LangGraph 构建。以下设计遵循 LangGraph 的实际 API 和架构模式。

#### 2.3.1 架构概览

```
用户消息
  ↓
┌────────────────────────────────────────────────────┐
│  主 Agent（自定义 StateGraph）                       │
│                                                     │
│  ┌──────────┐     ┌──────────────┐                  │
│  │  router   │────→│  supervisor  │                  │
│  │（意图分类）│     │ （任务编排）   │                  │
│  └──────────┘     └──────┬───────┘                  │
│       │                  │                          │
│       │ 简单问答          │ 需要工具调用               │
│       ↓                  ↓                          │
│  ┌─────────┐     ┌──────────────┐                   │
│  │ respond  │     │    tools     │←──┐              │
│  │（直接回复）│     │ （ToolNode） │   │ ReAct 循环   │
│  └─────────┘     └──────┬───────┘   │              │
│                         ↓           │              │
│                  ┌──────────────┐   │              │
│                  │  supervisor  │───┘              │
│                  │ （结果判断）   │                   │
│                  └──────┬───────┘                   │
│                         │ 任务完成                   │
│                         ↓                          │
│                  ┌──────────────┐                   │
│                  │   respond    │                   │
│                  │ （A2UI 生成） │                   │
│                  └──────────────┘                   │
└────────────────────────────────────────────────────┘
  ↓
stream（messages + custom 模式）
```

**核心结构**：

主 Agent 是一个自定义 `StateGraph`，包含四个节点：

| 节点 | 职责 |
|------|------|
| `router` | 解析用户意图。简单问答 → `respond`；需要工具调用 → `supervisor` |
| `supervisor` | ReAct 循环的 LLM 节点。决定调用哪些工具、检查结果、决定是否追加调用。任务完成 → `respond` |
| `tools` | `ToolNode`，执行 `supervisor` 发出的 tool_calls，结果返回 `supervisor` |
| `respond` | 将最终结果转化为 A2UI 组件，通过 `get_stream_writer()` 推送 |

`supervisor` ↔ `tools` 构成标准 ReAct 循环（Model → Tools → Model），由 `tools_condition` 控制：有 tool_calls 则走 `tools`，否则走 `respond`。

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

builder = StateGraph(CopilotState)
builder.add_node("router", router_node)
builder.add_node("supervisor", supervisor_node)
builder.add_node("tools", ToolNode(all_tools, handle_tool_errors=True))
builder.add_node("respond", respond_node)

builder.add_edge(START, "router")
builder.add_conditional_edges("router", route_intent)           # → supervisor 或 respond
builder.add_conditional_edges("supervisor", tools_condition,
    {"tools": "tools", END: "respond"})                         # ReAct 循环
builder.add_edge("tools", "supervisor")
```

#### 2.3.2 Agent 状态

```python
from typing import Annotated
from langgraph.graph import MessagesState
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class CopilotState(MessagesState):
    """扩展 MessagesState，messages 字段已内置 add_messages reducer。"""
    context: SessionContext            # 会话上下文（模式、页面、激活 Skill）
    summary: str                       # 长对话摘要（历史压缩用）
```

| 字段 | Reducer | 说明 |
|------|---------|------|
| `messages` | `add_messages`（内置） | 完整对话历史，按 message ID 去重和追加 |
| `context` | 覆盖（默认） | 会话上下文，页面切换时整体替换 |
| `summary` | 覆盖（默认） | 长对话摘要，触发压缩时更新 |

**`SessionContext`**：

| 字段 | 说明 |
|------|------|
| `mode` | `"shell"` / `"agent"` |
| `module` | 当前模块（仅 shell 模式） |
| `page` | 当前页面路径（仅 shell 模式） |
| `entity_rid` | 当前正在查看的实体 RID（仅 shell 模式） |
| `active_skills` | 当前激活的 Skill RID 列表 |
| `model_rid` | 当前使用的基座模型 RID |
| `branch` | 当前数据分支（默认 `"main"`），Action 执行时透传给 FunctionService |

#### 2.3.3 多智能体架构

Copilot 采用 **Subagent 模式**的多智能体架构。领域 Sub-Agent 通过 `create_agent()` 创建，包装为 Tool 供主 Agent 的 `supervisor` 调用。

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

# 创建领域 Sub-Agent
data_agent = create_agent(
    model=model,
    tools=[query_instances, get_instance, search_instances],
    name="data_agent",
    system_prompt="你是数据查询专家，负责查询和分析数据实例...",
)

# 包装为 Tool，供主 Agent 调用
@tool("data_analysis")
def call_data_agent(query: str) -> str:
    """分析数据实例的统计特征和趋势。"""
    result = data_agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content
```

**设计要点**：

- 主 Agent 的 `supervisor` 节点决定是否调用 Sub-Agent Tool，和调用普通 Tool 无区别
- 每个 Sub-Agent 拥有独立的模型、提示词和工具集，上下文隔离
- Sub-Agent 来源：
  - **系统内置**：Copilot 预定义的领域 Agent，无需用户配置
  - **用户配置**：通过 §2.2.5 Sub-Agent API 注册，运行时动态加载为 Tool

#### 2.3.4 Tool 绑定

`supervisor` 节点的可用工具来自三个来源：

**1. FunctionService 能力**（核心）

调用 `FunctionService.list_capabilities()` 获取能力清单，为每个 `CapabilityDescriptor` 生成 `@tool` 函数：

```python
from langchain_core.tools import tool
from langgraph.types import interrupt

def make_capability_tool(cap: CapabilityDescriptor, function_service: FunctionService, get_branch: Callable[[], str | None]):
    @tool(cap.api_name, description=cap.description)
    def capability_tool(**params) -> str:
        # 高风险操作：interrupt() 必须在 execute() 之前，确保无非幂等副作用被重复执行
        if cap.safety_level >= "SAFETY_NON_IDEMPOTENT":
            approved = interrupt({
                "action": cap.api_name,
                "description": cap.description,
                "params": params,
                "safety_level": cap.safety_level,
                "outputs": cap.outputs,
                "side_effects": cap.side_effects,
            })
            if not approved:
                return "操作已取消"

        # 从会话上下文获取当前分支，透传给 FunctionService
        branch = get_branch()
        skip = cap.safety_level >= "SAFETY_NON_IDEMPOTENT"

        # 根据能力类型分发到对应的 Protocol 方法
        if cap.type == "action":
            result = function_service.execute_action(cap.rid, params, branch=branch, skip_confirmation=skip)
        elif cap.type == "function":
            result = function_service.execute_function(cap.rid, params, branch=branch)
        elif cap.type == "workflow":
            result = function_service.execute_workflow(cap.rid, params, branch=branch, skip_confirmation=skip)
        return result

    return capability_tool
```

`skip_confirmation`：Copilot 通过 `interrupt()` 在图执行层完成确认，调用 FunctionService 时跳过其内部的 `pending_confirmation` 阶段，避免双重确认。非 Copilot 调用方（如 Function 模块前端）仍走 FunctionService 自身的确认流程。

`branch`：从 `SessionContext.branch` 获取当前数据分支，透传给 FunctionService。写入场景：FunctionService 透传给 `DataService.write_editlog(branch=...)`，写入 FDB EditLog 时携带分支标记，Flink 根据 branch 字段路由到对应的 Nessie 分支。读取场景：FunctionService 透传给内置 Global Function（如 `query_instances`），最终传递给 `DataService.query_instances(branch=...)`，保证读写一致。

**分支来源**：

| 场景 | branch 来源 | 说明 |
|------|------------|------|
| 数据模块 Shell | 同步数据模块的分支选择器 | 用户看什么分支的数据，Shell 就查询/操作什么分支 |
| 其他模块 Shell（本体/能力/设置） | 固定 `main` | 这些模块没有分支概念，Shell 始终操作 main |
| 智能体模块对话 | 对话页自带分支选择器 | 独立于其他模块，用户自行选择操作的分支 |

**2. MCP Tools**

MCP 协议定义了 Tool 的名称、描述和参数 schema，直接映射为 LangGraph Tool。Agent 调用时经 Copilot 代理转发 MCP 请求。

**3. Sub-Agent Tools**

领域 Sub-Agent 包装为 Tool（见 §2.3.3），与普通 Tool 统一注册到 `supervisor` 的工具列表。

**Shell 模式 vs Agent 模式的工具范围**：

| 维度 | Shell 模式 | Agent 模式 |
|------|-----------|-----------|
| FunctionService 能力 | 仅与当前模块相关的能力子集 | 全部能力 |
| MCP Tools | 全部已启用 | 全部已启用 |
| Sub-Agent Tools | 全部已启用 | 全部已启用 |
| 系统提示词 | 包含当前页面上下文，聚焦模块内辅助 | 通用系统提示词 |

Shell 模式下的"相关能力子集"根据 `context.module` 筛选：
- `ontology` → 类型定义相关的查询能力
- `data` → 数据查询、实例浏览相关能力
- `function` → 全部能力
- `setting` → 系统配置相关的查询能力

**工具加载策略**：

全量加载所有工具不可行——工具数量多时 LLM 选择准确率下降且上下文溢出。`supervisor` 每次推理时实际绑定的工具集通过以下规则裁剪：

| 层级 | 裁剪规则 | 说明 |
|------|---------|------|
| 模式过滤 | Shell 模式按 `context.module` 过滤 FunctionService 能力 | 排除不相关模块的能力 |
| Skill 聚焦 | 激活 Skill 时，仅加载该 Skill 的 `tool_bindings` 声明的工具 | Skill 是最直接的工具范围控制手段 |
| 全量兜底 | Agent 模式 + 无激活 Skill 时加载全部能力 | 通用对话场景 |

**优化预留**：
- 工具索引：维护全部工具的 name + description 索引（轻量）。`router` 节点根据用户意图从索引中筛选相关工具子集，仅将子集绑定给 `supervisor`
- 动态加载：首轮推理绑定核心工具子集；`supervisor` 判断需要额外工具时，通过内置的 `load_tools` 工具按需加载

#### 2.3.5 Human-in-the-loop

使用 LangGraph 的 `interrupt()` 机制暂停图执行，等待用户确认后通过 `Command(resume=...)` 恢复。

**前置条件**：编译图时必须配置 checkpointer，调用时必须传入 `thread_id`。

**流程**：

```
supervisor 调用 capability_tool
  ↓
capability_tool 检查 cap.safety_level ≥ SAFETY_NON_IDEMPOTENT
  ↓
capability_tool 调用 interrupt({action, params, outputs, side_effects})
  · LangGraph 将当前状态写入 checkpoint，暂停图执行
  · interrupt 的 payload 随 stream 返回给调用方
  ↓
Copilot 层将 interrupt payload 转化为 ConfirmationCard 推送前端（A2UI interrupt 事件）
  ↓
用户确认 → 前端调用 POST /sessions/{id}/resume {"approved": true}
  · Copilot 层调用 graph.invoke(Command(resume=True), config)
  · interrupt() 返回 True → capability_tool 调用 FunctionService.execute(skip_confirmation=True)
  · supervisor 获取执行结果，继续 ReAct 循环
  ↓
用户取消 → 前端调用 POST /sessions/{id}/resume {"approved": false}
  · Copilot 层调用 graph.invoke(Command(resume=False), config)
  · interrupt() 返回 False → capability_tool 返回 "操作已取消"
  · supervisor 收到取消信息，生成取消提示
```

**关键约束**：
- `interrupt()` 不能被 `try/except Exception` 捕获（内部使用特殊异常机制）
- `interrupt()` 之前的副作用必须幂等，因为恢复时节点从头重新执行
- payload 必须 JSON 可序列化

#### 2.3.6 流式输出

使用 LangGraph 原生 `stream()` / `astream()`，而非 LangChain 的 `astream_events()`。

```python
# 多模式并行流式输出
async for mode, chunk in graph.astream(
    {"messages": [{"role": "user", "content": user_input}]},
    config={"configurable": {"thread_id": session_id}},
    stream_mode=["messages", "custom"],
):
    if mode == "messages":
        msg_chunk, metadata = chunk
        # LLM token → SSE text_delta 事件
        yield sse_event("text_delta", {"content": msg_chunk.content})

    elif mode == "custom":
        # 自定义事件 → SSE component / tool_start / tool_end 事件
        yield sse_event(chunk["type"], chunk["data"])
```

| LangGraph stream_mode | 用途 | 映射到 A2UI |
|----------------------|------|-------------|
| `messages` | LLM token 流式输出 | `text_delta` 事件 |
| `custom` | 自定义进度和结构化数据 | `component`、`tool_start`、`tool_end`、`thinking` 事件 |

**自定义事件发送**（在节点或 Tool 内通过 `get_stream_writer()` 发送）：

```python
from langgraph.config import get_stream_writer

def respond_node(state: CopilotState):
    writer = get_stream_writer()
    # 推送 A2UI 组件
    writer({"type": "component", "data": {"type": "table", "title": "查询结果", ...}})
    return {"messages": [AIMessage(content="查询完成")]}
```

#### 2.3.7 持久化

```python
from langgraph.checkpoint.postgres import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(POSTGRES_URI)
await checkpointer.setup()  # 初始化表结构

graph = builder.compile(checkpointer=checkpointer)
```

| 维度 | 说明 |
|------|------|
| Checkpointer | `AsyncPostgresSaver`，与系统共用 PostgreSQL 实例 |
| Thread ID | 等同于 session_id（`ri.session.{uuid}`） |
| 检查点粒度 | 每个节点执行后自动保存 |
| 恢复机制 | 通过 `thread_id` 恢复完整对话状态，支持 interrupt/resume、崩溃恢复 |
| 长对话压缩 | 消息数超过阈值时触发摘要节点，用 `RemoveMessage` 清理旧消息、更新 `summary` 字段 |

**长对话摘要**：

```python
from langchain_core.messages import RemoveMessage

def maybe_summarize(state: CopilotState):
    if len(state["messages"]) <= 20:
        return state
    # 用 LLM 摘要旧消息
    summary_prompt = f"已有摘要：{state.get('summary', '')}\n请根据以上新消息扩展摘要。"
    response = model.invoke(state["messages"] + [HumanMessage(content=summary_prompt)])
    # 保留最近 6 条消息，删除其余
    delete = [RemoveMessage(id=m.id) for m in state["messages"][:-6]]
    return {"summary": response.content, "messages": delete}
```

#### 2.3.8 上下文管理

**页面上下文注入**（Shell 模式）：

前端发送消息时附带当前页面上下文。`supervisor` 的系统提示词中注入该上下文：

```
你正在辅助用户操作「本体」模块。
当前页面：ObjectType 编辑器
正在编辑的实体：ri.obj.{uuid}（机器人类型）
当前数据分支：main
```

**页面上下文更新**：用户切换页面或切换数据分支时，前端通过 `update_state` 更新会话上下文，不触发 Agent 推理：

```python
# 前端发送上下文更新 → Copilot 层直接更新图状态
graph.update_state(
    config={"configurable": {"thread_id": session_id}},
    values={"context": new_context},
    as_node="router",
)
```

#### 2.3.9 演进：LangGraph Server

初期 Copilot 与其他能力域一同部署在单 Python 进程中，直接调用编译后的 graph 对象。

当需要独立扩缩或多实例部署时，可迁移至 LangGraph Server（Agent Server）：
- 自带 HTTP API（threads、runs、streaming）、PostgreSQL 持久化、Redis 任务队列
- 支持 MCP 端点和 A2A（Agent-to-Agent）协议
- graph 代码不变，部署方式从进程内调用切换为 HTTP Client SDK 调用

### 2.4 A2UI 协议

A2UI（Agent-to-UI）是 Copilot 向前端推送结构化 UI 组件的流式协议。

#### 2.4.1 传输层

基于 SSE（Server-Sent Events）。每个 SSE 事件的 `data` 字段为一个 JSON 对象。

```
id: 1
event: a2ui
data: {"type": "text_delta", "content": "正在查询"}

id: 2
event: a2ui
data: {"type": "text_delta", "content": "机器人数据..."}

id: 3
event: a2ui
data: {"type": "component", "component": {"type": "table", ...}}

id: 4
event: a2ui
data: {"type": "tool_start", "tool_name": "function_query_instances", "params": {...}}

id: 5
event: a2ui
data: {"type": "tool_end", "tool_name": "function_query_instances", "status": "success"}

id: 6
event: a2ui
data: {"type": "done"}
```

**断连恢复**：每个 SSE 事件携带递增的 `id`。前端断连后重连时，通过 `Last-Event-ID` 请求头告知服务端上次收到的事件 ID。服务端不重放历史事件——如果 Agent 仍在执行，从当前位置继续推送；如果 Agent 已完成（`done` 已发出），返回 `done` 事件，前端通过 `GET /sessions/{id}` 获取完整的最终结果。

#### 2.4.2 事件类型

| 事件类型 | 说明 |
|---------|------|
| `text_delta` | 文本增量（流式文字输出） |
| `component` | 结构化 UI 组件（见 §2.4.3） |
| `tool_start` | Tool 调用开始（工具名称 + 参数） |
| `tool_end` | Tool 调用结束（状态 + 结果摘要） |
| `thinking` | Agent 推理过程（可选展示） |
| `interrupt` | Agent 暂停，等待用户确认（含 ConfirmationCard 数据） |
| `error` | 错误信息 |
| `done` | 消息处理完成 |

#### 2.4.3 A2UI 组件

Agent 在回复中嵌入结构化 UI 组件，前端根据组件类型选择渲染方式。

**Table — 数据表格**

```json
{
  "type": "table",
  "title": "电量低于20%的机器人",
  "object_type_rid": "ri.obj.{uuid}",
  "columns": [
    { "key": "robot_id", "label": "ID" },
    { "key": "name", "label": "名称" },
    { "key": "battery_level", "label": "电量" },
    { "key": "status", "label": "状态" }
  ],
  "rows": [
    { "robot_id": "R2-D2", "name": "巡检机器人A", "battery_level": 15, "status": "active" },
    { "robot_id": "R2-D3", "name": "搬运机器人B", "battery_level": 8, "status": "active" }
  ],
  "actions": [
    { "label": "设为维护", "action_rid": "ri.action.{uuid}", "param_mapping": { "robot": "$row" } }
  ]
}
```

**与 WidgetConfig 的关系**：`object_type_rid` 关联到 ObjectType 定义。前端拿到该 RID 后，从 ObjectType 的 PropertyType 列表中获取每列对应属性的 `WidgetConfig`，用于单元格渲染（如 `WidgetStatus` 渲染为带颜色的状态标签、`WidgetDate` 按配置格式化日期）。A2UI Table 组件不重复定义渲染规则，复用 Ontology 中已有的 WidgetConfig。

Table 组件的 `actions` 定义行级操作按钮。点击后前端用 `param_mapping` 构建 Action 执行请求，通过 Copilot 发起执行。

**MetricCard — 指标卡片**

```json
{
  "type": "metric_card",
  "metrics": [
    { "label": "机器人总数", "value": 42 },
    { "label": "在线", "value": 35, "color": "green" },
    { "label": "低电量", "value": 5, "color": "red" },
    { "label": "维护中", "value": 2, "color": "orange" }
  ]
}
```

**Form — 参数表单**

```json
{
  "type": "form",
  "title": "更新机器人状态",
  "action_rid": "ri.action.{uuid}",
  "fields": [
    { "key": "robot", "label": "机器人", "type": "instance_selector", "type_rid": "ri.obj.{uuid}", "value": { "primary_key": { "robot_id": "R2-D2" } } },
    { "key": "new_status", "label": "新状态", "type": "select", "options": ["active", "maintenance", "offline"] }
  ]
}
```

Agent 生成预填参数的表单。用户修改后提交，前端通过 Copilot 发起 Action 执行。`fields` 中的 `type` 可直接指定（如 `select`、`instance_selector`），也可省略——前端根据关联 PropertyType 的 `WidgetConfig` 自动推导输入组件。

**ConfirmationCard — 确认卡片**

```json
{
  "type": "confirmation_card",
  "action": "update_robot_status",
  "description": "更新机器人状态",
  "safety_level": "SAFETY_NON_IDEMPOTENT",
  "message": "此操作将更新 2 台机器人的状态",
  "affected_outputs": [
    { "name": "robot_update", "target": "R2-D2", "operation": "update" },
    { "name": "robot_update", "target": "R2-D3", "operation": "update" }
  ],
  "side_effects": [
    { "category": "DATA_MUTATION", "description": "更新机器人状态" }
  ]
}
```

ConfirmationCard 是纯展示组件，数据来自 `interrupt()` 的 payload（见 §2.3.4 Tool 绑定中的 interrupt 调用）。前端已知 session_id（从对话上下文获取），确认/取消通过 `POST /sessions/{id}/resume` 完成，卡片本身不需要携带 execution_id。前端渲染确认/取消按钮。

**Chart — 图表**

```json
{
  "type": "chart",
  "chart_type": "bar",
  "title": "机器人电量分布",
  "x_axis": { "label": "电量区间", "values": ["0-20%", "20-50%", "50-80%", "80-100%"] },
  "y_axis": { "label": "数量" },
  "series": [
    { "name": "数量", "values": [5, 12, 15, 10] }
  ]
}
```

**EntityCard — 实体卡片**

```json
{
  "type": "entity_card",
  "entity_type": "ObjectType",
  "rid": "ri.obj.{uuid}",
  "display_name": "机器人",
  "properties": [
    { "label": "API Name", "value": "robot" },
    { "label": "属性数量", "value": 12 },
    { "label": "状态", "value": "ACTIVE" }
  ],
  "link": "/ontology/object-types/ri.obj.{uuid}"
}
```

点击 EntityCard 跳转到对应编辑器或详情页。

#### 2.4.4 组件列表

| 组件 | 用途 | 典型场景 |
|------|------|---------|
| `table` | 数据表格 | 查询结果展示、实例列表 |
| `metric_card` | 指标卡片 | 统计概览、KPI 展示 |
| `form` | 参数表单 | Action 执行前的参数填写 |
| `confirmation_card` | 确认卡片 | 高风险操作确认 |
| `chart` | 图表 | 数据可视化（柱状图、折线图、饼图） |
| `entity_card` | 实体卡片 | Ontology 实体摘要展示 |
| `code` | 代码块 | SQL、Python 代码展示 |
| `list` | 列表 | 简单的有序/无序列表 |

### 2.5 会话管理

#### 2.5.1 会话生命周期

```
创建会话（POST /sessions）
  ↓
活跃对话（用户发消息 ↔ Agent 回复）
  ↓
恢复会话（用户重新打开历史会话）→ 通过 thread_id 从 PostgreSQL checkpoint 恢复完整状态
  ↓
用户删除 → 清理 PostgreSQL 数据（sessions 表 + checkpoint 数据）
```

#### 2.5.2 存储分层

| 数据 | 存储 | 说明 |
|------|------|------|
| Agent 检查点 | PostgreSQL（`AsyncPostgresSaver`） | LangGraph 每步自动保存，支持 interrupt/resume、崩溃恢复、会话恢复 |
| 会话元数据 | PostgreSQL（sessions 表） | session_id、mode、created_at、last_active_at、title |

**LangGraph Checkpointer**：使用 `AsyncPostgresSaver` 作为 checkpointer，与系统共用 PostgreSQL 实例。Agent 每个节点执行后自动保存检查点（thread_id = session_id）。会话恢复时通过 thread_id 加载完整状态，无需额外的归档/迁移策略。

### 2.6 存储设计

#### 2.6.1 PostgreSQL

**sessions 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | VARCHAR | 主键，`ri.session.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| user_id | VARCHAR | 会话所有者 |
| mode | VARCHAR | `shell` / `agent` |
| title | VARCHAR | 会话标题（首条消息自动生成或用户自定义） |
| context | JSONB | 会话上下文（module、page、entity_rid） |
| model_rid | VARCHAR | 使用的基座模型 RID |
| status | VARCHAR | `active` / `deleted` |
| created_at | TIMESTAMP | 创建时间 |
| last_active_at | TIMESTAMP | 最后活跃时间 |

**models 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.model.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| api_name | VARCHAR | API 名称 |
| display_name | VARCHAR | 显示名称 |
| provider | VARCHAR | 模型供应商 |
| connection | JSONB | 连接配置（api_base、model_id，api_key_ref 引用） |
| parameters | JSONB | 推理参数 |
| is_default | BOOLEAN | 是否为默认模型 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**skills 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.skill.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| api_name | VARCHAR | API 名称 |
| display_name | VARCHAR | 显示名称 |
| description | TEXT | 描述 |
| system_prompt | TEXT | 系统提示词 |
| tool_bindings | JSONB | 工具绑定列表 |
| enabled | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**mcp_connections 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.mcp.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| api_name | VARCHAR | API 名称 |
| display_name | VARCHAR | 显示名称 |
| description | TEXT | 描述 |
| transport | JSONB | 传输配置（type、url） |
| auth | JSONB | 认证配置 |
| discovered_tools | JSONB | 连接后发现的 Tools 列表 |
| status | VARCHAR | `connected` / `disconnected` / `error` |
| enabled | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**sub_agents 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.subagent.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| api_name | VARCHAR | API 名称 |
| display_name | VARCHAR | 显示名称 |
| description | TEXT | 描述 |
| model_rid | VARCHAR | 使用的基座模型 RID |
| system_prompt | TEXT | 系统提示词 |
| tool_bindings | JSONB | 工具绑定列表 |
| safety_policy | JSONB | 安全策略 |
| enabled | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 2.7 业务规则

#### 2.7.1 工具调用限制

单次消息处理中，Agent 的工具调用次数有上限（默认 30 次），防止无限循环。达到上限后 Agent 停止工具调用，将已有结果返回用户并提示已达到限制。

#### 2.7.2 模型切换

- 默认模型（`is_default = true`）全局唯一，新会话默认使用该模型
- 用户可在会话内切换模型（更新 SessionContext.model_rid），后续 Agent 调用使用新模型
- 切换模型不影响已有对话历史，仅影响后续推理

#### 2.7.3 错误码

遵循 `TECH_DESIGN.md` 第 5 节的错误码体系，前缀 `COPILOT_`：

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `COPILOT_SESSION_NOT_FOUND` | 404 | 会话不存在 |
| `COPILOT_SESSION_EXPIRED` | 410 | 会话已过期（超过 TTL） |
| `COPILOT_INTENT_UNCLEAR` | 422 | Agent 无法理解用户意图 |
| `COPILOT_TOOL_FAILED` | 500 | Tool 调用失败 |
| `COPILOT_TOOL_LIMIT_EXCEEDED` | 429 | 单次消息工具调用次数超限 |
| `COPILOT_MODEL_UNAVAILABLE` | 503 | 基座模型不可用 |
| `COPILOT_MCP_CONNECTION_FAILED` | 502 | MCP 服务连接失败 |
| `COPILOT_SUBAGENT_FAILED` | 500 | Sub-Agent 执行失败 |

---

## 3. 前端交互设计

### 3.1 Copilot Shell

全局右侧面板，不属于任何模块。

```
┌────────────────────────────┐
│  Copilot Shell (400px)      │
│                             │
│  ┌────────────────────────┐ │
│  │  消息流                 │ │
│  │                         │ │
│  │  [用户] 帮我查一下...    │ │
│  │                         │ │
│  │  [Agent] 正在查询...     │ │
│  │  ┌────────────────────┐ │ │
│  │  │  Table 组件         │ │ │
│  │  │  (A2UI 渲染)        │ │ │
│  │  └────────────────────┘ │ │
│  │                         │ │
│  │  [Agent] 找到 5 台...   │ │
│  │                         │ │
│  └────────────────────────┘ │
│                             │
│  ┌────────────────────────┐ │
│  │  输入框      [发送]     │ │
│  └────────────────────────┘ │
└────────────────────────────┘
```

**行为**：
- Header 区域的 Copilot 开关控制展开/收起
- 默认收起，宽度 400px，可拖拽至屏幕宽度 80%
- 切换到智能体模块时自动收起且禁用开关
- 新打开 Shell 时创建新会话（`mode: "shell"`），关闭后会话保留在 PostgreSQL
- 再次打开恢复上次 Shell 会话，直到用户主动开始新会话
- 页面切换或分支切换时调用 `PUT /sessions/{id}/context` 更新上下文（不触发 Agent）
- 数据模块的分支选择器切换时，自动同步 `context.branch` 到 Copilot Shell 会话

**消息流渲染**：
- 文本消息：Markdown 渲染
- A2UI 组件：按组件类型选择渲染组件（Table → 数据表格、MetricCard → 指标卡片等）
- Tool 调用：折叠展示（工具名称 + 状态图标），可展开查看参数和结果
- ConfirmationCard：确认/取消按钮

### 3.2 智能体模块

智能体模块的 Main Stage 内容区域本身就是完整的对话界面。

#### 3.2.1 对话页

路由：`/agent/chat`（默认）、`/agent/chat/:session_id`（指定会话）

```
┌──────────────┬──────────────────────────────────────────┐
│  侧边面板     │  内容区域（对话界面）                       │
│              │                                          │
│  对话        │  ┌──────────────────────────┬──────────┐ │
│  会话        │  │  消息流                   │ main  ▾  │ │
│  基座模型    │  │                           └──────────┘ │
│  Skill      │  │  文本 + A2UI 组件                     │  │
│  MCP        │  │                                      │  │
│  Sub-Agent  │  └────────────────────────────────────┘  │
│  监控        │                                          │
│              │  ┌────────────────────────────────────┐  │
│              │  │  输入框                   [发送]     │  │
│              │  └────────────────────────────────────┘  │
└──────────────┴──────────────────────────────────────────┘
```

**分支选择器**（内容区域右上角）：下拉框列出所有 Nessie 分支。切换后调用 `PUT /sessions/{id}/context` 更新 `context.branch`，后续 Agent 的所有读取和写入操作使用新分支上下文。初期（无 Nessie）不显示。

与 Shell 的区别：
- 创建会话时 `mode: "agent"`，无页面上下文限制
- 可调用全部 FunctionService 能力
- 更宽的内容区域，A2UI 组件有更大的展示空间
- 自带分支选择器（Shell 模式的分支由当前模块的分支选择器同步）

#### 3.2.2 会话管理页

路由：`/agent/sessions`

| 列 | 内容 |
|----|------|
| 标题 | 会话标题（自动生成或自定义） |
| 模式 | Shell / Agent |
| 最后活跃 | 时间戳 |
| 消息数 | 消息条数 |

**操作**：
- 点击 → 打开该会话继续对话
- 删除 → 确认后删除会话

#### 3.2.3 基座模型管理页

路由：`/agent/models`、`/agent/models/:id`

- 模型列表：名称、供应商、是否默认
- 模型配置表单：API 连接信息（api_base、model_id）、凭证引用、推理参数
- 连接测试：发送测试请求验证 API 可用性
- 设为默认模型

#### 3.2.4 Skill 管理页

路由：`/agent/skills`、`/agent/skills/:id`

- Skill 列表：名称、描述、启用状态
- Skill 配置表单：系统提示词编辑器、工具绑定选择（从能力清单中选择）
- 启用/禁用

#### 3.2.5 MCP 管理页

路由：`/agent/mcp`、`/agent/mcp/:id`

- MCP 服务列表：名称、连接状态（已连接/断开/错误）、发现的工具数量
- MCP 配置表单：传输类型选择、URL 输入、认证配置
- 连接测试：测试 MCP 服务连通性
- 工具列表：连接成功后展示发现的 Tools（名称、描述、参数 schema）

#### 3.2.6 Sub-Agent 管理页

路由：`/agent/sub-agents`、`/agent/sub-agents/:id`

- Sub-Agent 列表：名称、描述、使用的模型、启用状态
- Sub-Agent 配置表单：
  - 基座模型选择（下拉，引用已注册的模型）
  - 系统提示词编辑器
  - 工具绑定选择（从能力清单 + MCP Tools 中选择）
  - 安全策略配置（最大调用次数、允许的安全级别、审批阈值）

#### 3.2.7 监控页

路由：`/agent/monitor`

- 最近的 Agent 执行记录列表
- 点击记录 → 展开推理链可视化：
  - Agent 每步决策（router → supervisor → tools → respond）
  - Tool 调用列表（工具名称、参数、结果、耗时）
  - Sub-Agent 调用链（委派的子任务及其 Tool 调用）
  - 总耗时、Token 使用量

### 3.3 跨模块跳转

**A2UI 组件跳转**：
- EntityCard 的 `link` 字段 → 跳转到本体模块或数据模块的对应页面
- Table 行点击实例 → 跳转到数据模块实例详情页

**从其他模块跳入**：
- 任何模块通过 Copilot Shell 发起操作 → Shell 内完成或跳转到智能体模块继续
- Shell 中复杂任务 → 提示用户切换到智能体模块获得完整能力

---

## 4. 实现优先级

| 阶段 | 范围 | 前置依赖 | 说明 |
|------|------|---------|------|
| P0 | LangGraph Agent + FunctionService Tool 绑定 + SSE 流式对话 + A2UI 基础组件（text、table、metric_card）+ 前端对话界面 | FunctionService P0（能力清单 + 执行） | 核心对话闭环：用户发消息 → Agent 调用能力 → 流式返回结果 |
| P0 | 会话管理（创建、恢复、归档）+ 基座模型管理 | — | 多会话支持和模型配置 |
| P1 | Copilot Shell + 页面上下文注入 + Shell/Agent 模式区分 | P0 完成 | 全局 AI 辅助面板 |
| P1 | Human-in-the-loop（ConfirmationCard + 确认流程）| FunctionService 安全策略 | 高风险操作确认 |
| P1 | A2UI 完整组件（form、confirmation_card、chart、entity_card、code、list） | P0 完成 | 丰富的结构化展示 |
| P2 | Skill 管理 + MCP 连接 | P0 完成 | 扩展 Agent 能力 |
| P3 | Sub-Agent + 监控页 + 推理链可视化 | P2 完成 | 高级 Agent 能力 |

---
