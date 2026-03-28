# FUNCTION_DESIGN.md - 能力模块设计

> **版本**: 0.1.0
> **更新日期**: 2026-03-02
> **状态**: 草稿
> **前置文档**: `DESIGN.md`（能力域边界）、`TECH_DESIGN.md`（API/RID/错误规范）、`PRODUCT_DESIGN.md`（模块结构）、`ONTOLOGY.md`（ActionType 定义）、`DATA_DESIGN.md`（DataService Protocol / 写回管道）

---

## 1. 模块定位

能力模块是 Function 能力域的完整实现，覆盖后端服务和前端交互。

**职责**：
- 加载 Ontology Action：根据 ActionType 定义加载执行引擎，解析参数，执行操作
- 管理 Global Function：注册、版本管理和执行无状态函数
- 编排工作流（Workflow）：将多个原子能力组合为可执行的工作流
- 向 Copilot 提供统一的可调用能力清单（原子能力 + 工作流），作为 Copilot 的唯一能力入口
- 通过 Data 管理的写回管道（FDB EditLog）将数据变更持久化
- 根据 safety_level 决定执行策略（直接执行 / 需要确认 / 需要审批）
- 记录执行日志和副作用审计

**不负责**：
- ActionType 的定义和版本管理（Ontology 的职责）
- 数据的底层读取和解析（Data 的职责）
- 写回管道的基础设施（FDB、Flink 同步、读取时合并——Data 的职责）

---

## 2. 后端服务设计

### 2.1 服务层架构

```
function/
├── router.py               # FastAPI 路由定义
├── service.py               # 业务逻辑（FunctionServiceImpl）
├── interface.py             # Protocol 接口（供 Copilot 调用）
├── actions/
│   ├── loader.py            # ActionType 加载器（从 Ontology 获取定义，构建可执行 Action）
│   ├── param_resolver.py    # 参数解析（显式值 + 实例引用）
│   └── engines/
│       ├── base.py          # 执行引擎抽象接口
│       ├── native_crud.py   # NativeCRUD 引擎
│       ├── python_venv.py   # PythonVenv 引擎
│       ├── sql_runner.py    # SQLRunner 引擎
│       └── webhook.py       # Webhook 引擎
├── globals/
│   ├── registry.py          # Global Function 注册表
│   ├── builtins.py          # 内置 Global Function（查询实例、获取类型定义等）
│   └── executor.py          # Global Function 执行器
├── workflows/
│   ├── repository.py        # 工作流 Repository（PostgreSQL）
│   ├── engine.py            # 工作流执行引擎（顺序 / 并行 / 条件分支）
│   └── models.py            # 工作流定义模型（节点、边、条件）
├── safety/
│   └── enforcer.py          # 安全策略执行（safety_level 检查、确认/审批拦截）
├── audit/
│   └── logger.py            # 执行审计日志
└── schemas/
    ├── requests.py          # 请求 DTO
    └── responses.py         # 响应 DTO
```

**关键约束**：
- 执行引擎通过抽象接口隔离，新增引擎只需实现 `Engine` 接口并注册
- Function 通过 OntologyService Protocol 获取 ActionType 定义，通过 DataService Protocol 获取实例数据
- 数据写入通过 Data 提供的写回接口（FDB EditLog）完成，Function 不直接操作底层数据源
- 所有执行记录持久化到 PostgreSQL，支持执行历史查询和审计

**FunctionService Protocol 接口**（供 Copilot 调用）：

```python
# function/interface.py
class FunctionService(Protocol):
    def list_capabilities(self) -> list[CapabilityDescriptor]: ...

    def execute_action(
        self,
        action_type_rid: str,
        params: dict[str, Any],
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> ExecutionResult: ...

    def execute_function(
        self,
        function_rid: str,
        params: dict[str, Any],
        branch: str | None = None,
    ) -> ExecutionResult: ...

    def execute_workflow(
        self,
        workflow_rid: str,
        params: dict[str, Any],
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> ExecutionResult: ...
```

- `list_capabilities`：返回统一的能力清单（Action + Global Function + Workflow），供 Copilot 发现可调用的能力。每个 `CapabilityDescriptor` 包含名称、描述、参数 schema、outputs 摘要（从 implementation 中提取）、安全级别、副作用
- `execute_action`：执行 Ontology Action（参数解析 → 安全检查 → 引擎执行 → 写回）
- `execute_function`：执行 Global Function（无状态，无写回）。`branch` 透传给内置函数（如 `query_instances` 调用 `DataService.query_instances(branch=...)`），保证读取与写入的分支上下文一致
- `execute_workflow`：执行工作流（按编排逻辑依次/并行执行多个原子能力）
- `skip_confirmation`：跳过 FunctionService 内部的确认阶段（`pending_confirmation`），由调用方自行完成确认。Copilot 通过 LangGraph 的 `interrupt()` 在图执行层完成用户确认后，设置 `skip_confirmation=True` 调用 FunctionService，避免双重确认。非 Copilot 调用方（如前端 UI）不传此参数，走 FunctionService 自身的确认流程

### 2.2 API 设计

遵循 `TECH_DESIGN.md` 第 3 节的 API 规范。URL 前缀 `/function/v1/`。

#### 2.2.1 Action 执行 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/function/v1/actions/{action_type_rid}/execute` | 执行 Action |
| POST | `/function/v1/actions/{action_type_rid}/validate` | 校验参数（不执行） |
| POST | `/function/v1/actions/query` | 查询可用 Action 列表 |
| GET | `/function/v1/actions/{action_type_rid}` | 查询 Action 详情（参数 schema、安全级别、执行历史摘要） |

**执行请求**：

```json
POST /function/v1/actions/{action_type_rid}/execute

{
  "params": {
    "robot": { "primary_key": { "robot_id": "R2-D2" } },
    "new_status": "maintenance"
  },
  "branch": "main",
  "skip_confirmation": false
}
```

| 字段 | 说明 |
|------|------|
| `branch` | 数据分支（可选，默认 `"main"`），透传给 DataService.write_editlog |
| `skip_confirmation` | 跳过确认阶段（可选，默认 `false`），Copilot 调用时设为 `true` |

参数值有两种形式：
- **实例引用**（derived_from 参数）：`{ "primary_key": { ... } }`，Function 根据 ActionParameter 的 `derived_from_*_type_rid` 调用 DataService.get_instance 解析完整实例数据
- **显式值**（explicit_type 参数）：直接传值（如 `"maintenance"`）

**执行响应**：

```json
{
  "data": {
    "execution_id": "exec_xxx",
    "status": "success",
    "result": {
      "updated_fields": { "status": "maintenance" },
      "affected_primary_keys": [{ "robot_id": "R2-D2" }]
    },
    "started_at": "2026-03-02T10:00:00Z",
    "completed_at": "2026-03-02T10:00:01Z"
  }
}
```

**需要确认时的响应**（safety_level ≥ SAFETY_NON_IDEMPOTENT）：

```json
{
  "data": {
    "execution_id": "exec_xxx",
    "status": "pending_confirmation",
    "confirmation": {
      "message": "此操作将启动机器人任务，无法撤销",
      "safety_level": "SAFETY_NON_IDEMPOTENT",
      "affected_outputs": [
        { "name": "robot_update", "target": "机器人 R2-D2", "operation": "update", "writeback": true }
      ],
      "side_effects": [
        { "category": "DATA_MUTATION", "description": "更新机器人状态" },
        { "category": "EXTERNAL_API_CALL", "description": "调用机器人控制 API" }
      ],
      "confirm_url": "/function/v1/executions/exec_xxx/confirm",
      "cancel_url": "/function/v1/executions/exec_xxx/cancel"
    }
  }
}
```

#### 2.2.2 Global Function API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/function/v1/functions` | 注册 Global Function |
| POST | `/function/v1/functions/query` | 查询 Global Function 列表 |
| GET | `/function/v1/functions/{rid}` | 查询 Global Function 详情 |
| PUT | `/function/v1/functions/{rid}` | 更新 Global Function |
| DELETE | `/function/v1/functions/{rid}` | 删除 Global Function |
| POST | `/function/v1/functions/{rid}/execute` | 执行 Global Function |

**注册请求**：

```json
POST /function/v1/functions

{
  "api_name": "query_robot_status",
  "display_name": "查询机器人状态",
  "description": "根据机器人 ID 查询当前状态",
  "parameters": [
    {
      "api_name": "robot_type_rid",
      "display_name": "机器人类型",
      "data_type": "DT_STRING",
      "required": true
    },
    {
      "api_name": "primary_key",
      "display_name": "主键",
      "data_type": "DT_STRING",
      "required": true
    }
  ],
  "implementation": {
    "type": "builtin",
    "handler": "query_instance"
  }
}
```

**Global Function 实现类型**：

| type | 说明 | 示例 |
|------|------|------|
| `builtin` | 系统内置函数，调用 DataService / OntologyService | 查询实例、获取类型定义、关系遍历 |
| `python` | 用户自定义 Python 函数 | 数据转换、计算、格式化 |
| `webhook` | 调用外部 HTTP API | 搜索新闻、发送通知、第三方集成 |

#### 2.2.3 Workflow API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/function/v1/workflows` | 创建工作流 |
| POST | `/function/v1/workflows/query` | 查询工作流列表 |
| GET | `/function/v1/workflows/{rid}` | 查询工作流详情 |
| PUT | `/function/v1/workflows/{rid}` | 更新工作流 |
| DELETE | `/function/v1/workflows/{rid}` | 删除工作流 |
| POST | `/function/v1/workflows/{rid}/execute` | 执行工作流 |

**工作流定义**：

```json
{
  "api_name": "batch_robot_maintenance",
  "display_name": "批量机器人维护",
  "description": "批量将电量低于阈值的机器人设为维护状态",
  "parameters": [
    { "api_name": "battery_threshold", "data_type": "DT_INTEGER", "required": true }
  ],
  "nodes": [
    {
      "id": "step_1",
      "type": "function",
      "capability_rid": "ri.func.{uuid}",
      "params_mapping": {
        "robot_type_rid": "ri.obj.{uuid}"
      }
    },
    {
      "id": "step_2",
      "type": "action",
      "capability_rid": "ri.action.{uuid}",
      "params_mapping": {
        "robot": "$step_1.output.instances",
        "new_status": "maintenance"
      },
      "condition": "$step_1.output.battery_level < $input.battery_threshold"
    }
  ],
  "edges": [
    { "from": "step_1", "to": "step_2" }
  ]
}
```

#### 2.2.4 执行管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/function/v1/executions/{execution_id}` | 查询执行详情 |
| POST | `/function/v1/executions/query` | 查询执行历史（按 Action/Function/Workflow、时间范围、状态筛选） |
| POST | `/function/v1/executions/{execution_id}/confirm` | 确认待确认的执行 |
| POST | `/function/v1/executions/{execution_id}/cancel` | 取消待确认的执行 |

**执行记录响应**：

```json
{
  "data": {
    "execution_id": "exec_xxx",
    "capability_type": "action",
    "capability_rid": "ri.action.{uuid}",
    "capability_name": "更新机器人状态",
    "status": "success",
    "params": { "robot": { "robot_id": "R2-D2" }, "new_status": "maintenance" },
    "result": { "updated_fields": { "status": "maintenance" } },
    "safety_level": "SAFETY_IDEMPOTENT_WRITE",
    "side_effects": [{ "category": "DATA_MUTATION", "description": "更新机器人状态" }],
    "user_id": "user_123",
    "started_at": "2026-03-02T10:00:00Z",
    "completed_at": "2026-03-02T10:00:01Z"
  }
}
```

#### 2.2.5 能力清单 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/function/v1/capabilities/query` | 查询统一能力清单（Action + Global Function + Workflow） |

**响应**：

```json
{
  "data": [
    {
      "type": "action",
      "rid": "ri.action.{uuid}",
      "api_name": "update_robot_status",
      "display_name": "更新机器人状态",
      "description": "将机器人设为指定状态",
      "parameters": [
        { "api_name": "robot", "display_name": "机器人", "source": "derived_from_object_type", "type_rid": "ri.obj.{uuid}", "required": true },
        { "api_name": "new_status", "display_name": "新状态", "source": "explicit", "data_type": "DT_STRING", "required": true }
      ],
      "outputs": [
        { "name": "robot_update", "target_param": "robot", "operation": "update", "writeback": true }
      ],
      "safety_level": "SAFETY_IDEMPOTENT_WRITE",
      "side_effects": [{ "category": "DATA_MUTATION" }]
    },
    {
      "type": "function",
      "rid": "ri.func.{uuid}",
      "api_name": "query_robot_status",
      "display_name": "查询机器人状态",
      "parameters": [ ... ],
      "outputs": [],
      "safety_level": "SAFETY_READ_ONLY",
      "side_effects": []
    },
    {
      "type": "workflow",
      "rid": "ri.workflow.{uuid}",
      "api_name": "batch_robot_maintenance",
      "display_name": "批量机器人维护",
      "parameters": [ ... ],
      "outputs": [
        { "name": "robot_update", "target_param": "robots", "operation": "update", "writeback": true }
      ],
      "safety_level": "SAFETY_NON_IDEMPOTENT",
      "side_effects": [{ "category": "DATA_MUTATION" }]
    }
  ]
}
```

三种能力类型使用统一的 `CapabilityDescriptor` 结构，包含 `outputs` 字段（运行时从各引擎 implementation 中解析提取，仅包含 `name`、`target_param`、`operation`、`writeback`）。Copilot 从此接口发现所有可调用能力，根据 `type` 字段决定调用 `execute_action`、`execute_function` 或 `execute_workflow`。Copilot 在 `interrupt()` 时使用 `outputs` 向用户展示操作影响（哪些实例将被修改、什么操作）。

#### 2.2.6 概览 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/function/v1/overview` | 能力模块全局概览 |

**响应**：

```json
{
  "data": {
    "capabilities": {
      "actions": 12,
      "functions": 8,
      "workflows": 3
    },
    "recent_executions": {
      "total_24h": 156,
      "by_status": { "success": 140, "failed": 10, "pending_confirmation": 6 }
    }
  }
}
```

### 2.3 Action 执行流程

#### 2.3.1 完整执行管道

```
用户发起执行请求（params + branch）
  ↓
① 加载 ActionType 定义
  · OntologyService.get_action_type(rid) → ActionTypeDefinition
  · 获取 parameters、execution（type + implementation）、safety_level、side_effects
  · 从 implementation 中解析 outputs 声明
  ↓
② 参数解析
  · 遍历 ActionParameter：
    · derived_from_*_type_rid → DataService.get_instance(type_rid, primary_key) 获取实例数据
    · explicit_type → 直接使用用户传入的值，校验类型匹配
  ↓
③ 安全检查（safety_level + outputs + side_effects + skip_confirmation 共同决定）
  · skip_confirmation = true → 跳过确认阶段，直接执行（调用方已完成用户确认，如 Copilot interrupt）
  · SAFETY_READ_ONLY / SAFETY_IDEMPOTENT_WRITE → 直接执行
  · SAFETY_NON_IDEMPOTENT → 返回确认请求（含 outputs 写回摘要 + side_effects），等用户确认
  · SAFETY_CRITICAL → 返回确认请求（含影响分析 + outputs 写回摘要 + side_effects），等用户确认
  · 确认请求中展示：哪些实例将被修改（outputs 的 target_param）、什么操作、哪些副作用
  ↓
④ 引擎执行
  · 根据 execution.type 选择引擎（NativeCRUD / PythonVenv / SQLRunner / Webhook）
  · 引擎接收解析后的参数，执行操作逻辑
  · 返回 EngineResult（computed_values：引擎计算的中间值，供 field_mappings 引用）
  ↓
⑤ 写回（按 outputs 声明逐一处理）
  · 遍历 writeback = true 的 output：
    · 按 field_mappings 解析字段值（来自参数表达式或 $computed.*）
    · 从 target_param 的已解析参数获取 type_rid 和 primary_key
    · 检查 AssetMapping.writeback_enabled → false 则报错
    · 调用 DataService.write_editlog(type_rid, primary_key, operation, field_values, branch)
  ↓
⑥ 审计日志
  · 记录执行详情（参数、结果、耗时、safety_level、side_effects）到 PostgreSQL
  ↓
返回 ExecutionResult
```

#### 2.3.2 参数解析

ActionParameter 有四种 `definition_source`，解析方式不同：

| definition_source | 用户传入 | 解析方式 |
|---|---|---|
| `derived_from_object_type_rid` | `{ "primary_key": { ... } }` | 调用 DataService.get_instance(object_type_rid, primary_key) 获取完整实例 |
| `derived_from_link_type_rid` | `{ "primary_key": { ... } }` | 调用 DataService.get_instance(link_type_rid, primary_key) 获取完整实例 |
| `derived_from_interface_type_rid` | `{ "type_rid": "ri.obj.*", "primary_key": { ... } }` | 需额外指定具体类型 RID，调用 DataService.get_instance 获取实例，校验该类型实现了指定 InterfaceType |
| `explicit_type` | 原始值（如 `"maintenance"`） | 按 ActionParameter 的 DataType 校验类型，直接使用 |

**接口引用参数**（`derived_from_interface_type_rid`）的特殊处理：用户需同时指定具体类型 RID 和主键，因为 InterfaceType 可被多个 ObjectType/LinkType 实现，必须明确引用哪个类型的实例。Function 校验该类型确实 IMPLEMENTS 了指定的 InterfaceType。

#### 2.3.3 输出声明（outputs）

`outputs` 嵌入在各引擎的 `implementation` 配置中（而非 proto 层独立字段），定义 Action 产出的返回值实体。每个 output 独立声明目标、操作和写回配置：

| 字段 | 说明 |
|------|------|
| `name` | 输出实体标识符 |
| `target_param` | 目标实例参数名（`update` / `delete` 时必填，必须引用 `derived_from_*` 参数） |
| `target_type_rid` | 目标类型 RID（`create` 时必填，指定要创建的实例类型） |
| `operation` | `"create"` / `"update"` / `"delete"`（省略则为纯数据返回） |
| `field_mappings` | 字段值映射：目标实例的哪些字段写入什么值（值来自参数表达式或引擎计算结果） |
| `writeback` | 是否将变更写入 FDB EditLog（仅 `operation` 存在时可配置） |

`field_mappings` 是 output 级别的配置，定义"目标实例的哪些字段被写入什么值"。值来源使用参数表达式（`param_name` 或 `param_name.field`，与 §2.3.5 统一）或引擎计算结果（见各引擎说明）。

**outputs、safety_level、side_effects 的一致性**（ActionType 保存时校验）：

| 校验规则 | 说明 |
|---|---|
| `safety_level = SAFETY_READ_ONLY` 时，不允许存在 `writeback = true` 的 output | 只读操作不产生数据变更 |
| 存在 `writeback = true` 的 output 时，`safety_level` 不得为 `SAFETY_READ_ONLY` | 有写回必须声明写权限 |
| 存在 `writeback = true` 的 output 时，`side_effects` 应包含 `DATA_MUTATION` | 写回即数据变更副作用 |
| `target_param` 必须引用 `derived_from_*` 类型的参数 | 操作目标必须是实例引用 |
| 不同 output 的 `target_param` 不得相同 | 每个 output 操作独立的目标实例 |
| `writeback = true` 的 output，其目标类型的 AssetMapping 必须存在 | 写回需要数据映射支持 |
| `field_mappings` 中引用的参数名必须在 `parameters` 中存在 | 值来源可追溯 |

##### outputs 的存储与提取

`outputs` 不在 proto 层定义独立字段，而是嵌入在各引擎 `implementation` 字符串的 JSON 结构中：

| 引擎 | proto 字段 | 内容格式 | outputs 位置 |
|------|-----------|---------|-------------|
| NativeCRUD | `native_crud_json` | JSON | `outputs` 即全部配置，无需额外引擎参数 |
| PythonVenv | `python_script` | JSON | `{"script": "...", "outputs": [...]}` |
| SQLRunner | `sql_template` | JSON | `{"template": "...", "outputs": [...]}` |
| Webhook | `webhook_config_json` | JSON | 在已有 JSON 中增加 `"outputs"` 键 |

> proto 字段名是 oneof 分支标识符，实际内容格式由应用层定义。`python_script` 和 `sql_template` 的内容是包含代码/模板和 outputs 的 JSON 对象。

**运行时提取**：各引擎适配器负责从 implementation 中解析 outputs。`list_capabilities` API 返回的 `outputs` 摘要，由 FunctionService 在加载 ActionType 时从 implementation 中提取并缓存。

##### outputs 与执行管道的关系

```
                     ActionType 定义
                    ┌──────────────────────────────────┐
                    │  parameters（输入）                │
                    │  implementation（引擎配置 + outputs）│
                    │  safety_level + side_effects       │
                    │  execution.type（引擎类型）         │
                    └──────────────────────────────────┘
                              ↓
            ┌─────────────────┼──────────────────┐
            ↓                 ↓                  ↓
     ② 参数解析         ③ 安全检查           ④ 引擎执行
    （获取实例数据）  （safety_level      （执行计算逻辑，
                      决定是否需要         不决定写什么）
                      用户确认）
            └─────────────────┼──────────────────┘
                              ↓
                    ⑤ 写回（按 implementation 中的 outputs 声明）
                    · 遍历 writeback=true 的 output
                    · 从 target_param 获取目标实例
                    · 按 field_mappings 计算字段值
                    · 调用 DataService.write_editlog
```

关键分工：
- **implementation 中的 outputs 声明**决定写什么（目标、操作、字段映射、是否写回）
- **safety_level** 决定何时写（直接执行 or 确认后执行）
- **引擎**负责计算逻辑（校验、复杂计算），不决定写回行为
- **AssetMapping.writeback_enabled** 是数据层的能力约束（数据源是否支持写入），不满足则报错

#### 2.3.4 执行引擎

每种引擎实现统一的抽象接口：

```python
class Engine(Protocol):
    def execute(
        self,
        config: ActionExecutionConfig,
        resolved_params: dict[str, Any],
    ) -> EngineResult: ...
```

`EngineResult` 包含：
- `data`：引擎计算产出的数据（查询结果、外部 API 响应等）
- `computed_values`：引擎计算产出的中间值（供 `field_mappings` 引用，见各引擎说明）

引擎只负责执行计算逻辑，不负责写回。写回由框架根据 outputs 声明完成。

#### 2.3.5 参数表达式

outputs 的 `field_mappings` 和各引擎配置中统一使用相同的参数引用语法：

| 表达式 | 含义 | 示例 |
|---|---|---|
| `param_name` | 取参数值。explicit 参数取原始值；derived_from 参数取完整实例 | `new_status` → `"maintenance"` |
| `param_name.field` | 取 derived_from 参数的指定属性 | `robot.status` → `"active"` |

各引擎将此表达式嵌入各自的格式中：

| 引擎 | 嵌入语法 | 示例 |
|---|---|---|
| NativeCRUD | 无需嵌入（field_mappings 在 output 声明中，直接使用参数表达式） | `"source": "new_status"` |
| PythonVenv | Python dict 访问 | `params["new_status"]`、`params["robot"]["owner"]` |
| SQLRunner | `:` 前缀 | `:new_status`、`:robot.owner` |
| Webhook | `{{params.}}` 模板 | `{{params.new_status}}`、`{{params.robot.owner}}` |

**校验时机**：ActionType 保存时（Ontology 侧），校验引用的参数名在 parameters 中存在、`.field` 引用仅用于 derived_from 参数。

---

**ENGINE_NATIVE_CRUD**

纯声明式引擎，无需编写代码。`native_crud_json` 即 outputs 声明本身。

Action 的全部行为由 outputs 的 `field_mappings` 决定。NativeCRUD 引擎解析 field_mappings 中的参数表达式和内置变量（`$NOW`、`$USER`），计算最终字段值。

示例 `native_crud_json` 内容：

```json
{
  "outputs": [
    {
      "name": "robot_update",
      "target_param": "robot",
      "operation": "update",
      "field_mappings": [
        { "target_field": "status", "source": "new_status" },
        { "target_field": "last_operator", "source": "robot.owner" },
        { "target_field": "updated_at", "value": "$NOW" }
      ],
      "writeback": true
    }
  ]
}
```

`field_mappings` 每项：

| 字段 | 说明 |
|------|------|
| `target_field` | 目标实例的 PropertyType api_name |
| `source` | 值来源：参数表达式（`param_name` 或 `param_name.field`） |
| `value` | 值来源：静态值或内置变量（`$NOW` = 当前时间戳，`$USER` = 当前用户 ID） |

`source` 和 `value` 二选一。

`operation = "delete"` 时 `field_mappings` 为空，仅标记删除。

`operation = "create"` 时 `target_type_rid` 指定目标类型，`field_mappings` 定义初始值，primary_key 字段必须在 `field_mappings` 中提供。

---

**ENGINE_PYTHON_VENV**

用户编写的 Python 脚本。`python_script` 是 JSON 对象，包含脚本内容和 outputs 声明。脚本必须定义 `execute` 函数。

脚本的职责是**执行业务逻辑**（校验、复杂计算），不决定写回行为。写回由同一 JSON 中的 `outputs` 声明的 `field_mappings` 控制。

脚本产出的计算结果通过 `computed_values` 返回，供 `field_mappings` 引用（语法：`$computed.key`）。如果 `field_mappings` 的值全部来自参数表达式（不需要引擎计算），脚本只做校验，返回空 dict 即可。

```python
def execute(params: dict, context: dict) -> dict:
    """
    params: 解析后的参数
      - derived_from 参数：完整实例数据（properties dict）
      - explicit 参数：原始值
    context: 执行上下文
      - tenant_id: 租户 ID
      - user_id: 用户 ID
      - action_type_rid: ActionType RID
    返回值：computed_values dict（供 field_mappings 通过 $computed.key 引用）
    """
    robot = params["robot"]
    new_status = params["new_status"]

    # 业务校验
    if robot["battery_level"] < 20 and new_status == "active":
        raise ValueError("电量过低，无法激活")

    # 复杂计算（直接引用参数即可的字段无需在此计算）
    return {
        "maintenance_deadline": compute_deadline(robot["last_maintenance"])
    }
```

示例 `python_script` 内容（JSON）：

```json
{
  "script": "def execute(params, context):\n    robot = params['robot']\n    new_status = params['new_status']\n    if robot['battery_level'] < 20 and new_status == 'active':\n        raise ValueError('电量过低，无法激活')\n    return {'maintenance_deadline': compute_deadline(robot['last_maintenance'])}",
  "outputs": [
    {
      "name": "robot_update",
      "target_param": "robot",
      "operation": "update",
      "field_mappings": [
        { "target_field": "status", "source": "new_status" },
        { "target_field": "maintenance_deadline", "source": "$computed.maintenance_deadline" }
      ],
      "writeback": true
    }
  ]
}
```

`field_mappings` 值来源可以是参数表达式（`new_status`）或引擎计算结果（`$computed.maintenance_deadline`）。框架在引擎执行后、写回前，统一解析 field_mappings 构建字段值。

运行环境约束：
- 在隔离进程中执行（subprocess），不与主进程共享内存
- 超时控制：默认 30 秒，可在 ActionType 中配置
- 可用标准库 + 白名单第三方库（如 `json`、`datetime`、`math`）
- 不可直接访问数据库或网络——需要数据时通过参数传入（实例引用在执行前已解析）

---

**ENGINE_SQL_RUNNER**

SQL 模板，参数通过命名占位符注入。`sql_template` 是 JSON 对象，包含 SQL 模板和 outputs 声明。引擎执行 SQL 查询，查询结果作为 `computed_values` 返回，供 `field_mappings` 引用（`$computed.column_name`）。纯数据返回场景下查询结果直接作为 output 的 data。

示例 `sql_template` 内容（JSON）：

```json
{
  "template": "SELECT robot_id, status, battery_level\nFROM {{robot.read_asset_path}}\nWHERE status = :status_filter\nAND battery_level < :threshold\nAND owner = :robot.owner",
  "outputs": []
}
```

SQL 模板（`template` 字段）占位符语法：

| 占位符语法 | 说明 |
|---|---|
| `:param_name` | 参数化绑定（防注入），引用 explicit 参数，直接取值 |
| `:param_name.field` | 引用 derived_from 参数的指定属性 |
| `{{param_name.read_asset_path}}` | derived_from 参数关联类型的 AssetMapping 的 read_asset_path |

引擎执行逻辑：
1. 从 `sql_template` JSON 中提取 `template` 和 `outputs`
2. 解析 `{{param_name.read_asset_path}}`：从 derived_from 参数关联类型的 AssetMapping 获取 `read_connection_id` 和 `read_asset_path`
3. 渲染模板：替换 `{{...}}` 变量
4. 通过 Connector 执行参数化查询（`:param` 绑定，防止 SQL 注入）
5. 查询结果作为 `computed_values` 返回

---

**ENGINE_WEBHOOK**

调用外部 HTTP API。`webhook_config_json` 格式：

```json
{
  "url": "https://api.robot-control.com/v1/commands",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer {{secret:robot_api_key}}"
  },
  "body_template": {
    "robot_id": "{{params.robot.robot_id}}",
    "command": "{{params.command}}",
    "operator": "{{context.user_id}}"
  },
  "timeout_ms": 5000,
  "retry": {
    "max_attempts": 3,
    "backoff_ms": 1000
  },
  "response_mapping": {
    "result_status": "$.status",
    "message": "$.data.message"
  },
  "outputs": [
    {
      "name": "robot_command_result",
      "target_param": "robot",
      "operation": "update",
      "field_mappings": [
        { "target_field": "last_command_status", "source": "$computed.result_status" }
      ],
      "writeback": true
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `url` | 请求 URL |
| `method` | HTTP 方法（`GET` / `POST` / `PUT` / `DELETE`） |
| `headers` | 请求头，`{{secret:key_name}}` 引用加密存储的凭证 |
| `body_template` | 请求体模板，`{{params.xxx}}` 引用 Action 参数，`{{context.xxx}}` 引用执行上下文 |
| `timeout_ms` | 超时时间（毫秒） |
| `retry` | 重试策略（`max_attempts` + `backoff_ms`） |
| `response_mapping` | 响应字段提取（JSONPath 语法），提取的字段作为 `computed_values` 供 `field_mappings` 引用（`$computed.key`） |
| `outputs` | 输出声明（与其他引擎相同的 outputs 结构） |

引擎执行逻辑：
1. 渲染模板：替换 `{{params.*}}`、`{{context.*}}`、`{{secret:*}}`
2. 发起 HTTP 请求（超时 + 重试）
3. 按 `response_mapping` 解析响应，提取字段作为 `computed_values` 返回

#### 2.3.6 批量执行

ActionType 的 `is_batch = true` 时支持批量执行。

```json
POST /function/v1/actions/{action_type_rid}/execute

{
  "params": {
    "robots": [
      { "primary_key": { "robot_id": "R2-D2" } },
      { "primary_key": { "robot_id": "R2-D3" } }
    ],
    "new_status": "maintenance"
  },
  "batch_mode": true
}
```

**批量执行策略**：
- 逐条执行，每条独立成功/失败
- 返回批量结果（成功数 / 失败数 / 各条详情）
- 单条失败不影响其他条目（非事务）
- 每条执行的 writeback output 各自生成独立的 FDB EditLog 条目

#### 2.3.7 异步执行

ActionType 的 `is_sync = false` 时使用异步执行。

- 请求立即返回 `execution_id`，状态为 `running`
- 引擎在后台执行
- 客户端通过 `GET /function/v1/executions/{execution_id}` 轮询状态
- 完成后状态更新为 `success` 或 `failed`

### 2.4 数据写回

Function 不直接操作底层数据源。写入通过 Data 管理的写回管道完成。

#### 2.4.1 写回调用路径

```
引擎执行完成（computed_values）+ implementation 中的 outputs 声明（field_mappings）
  ↓
遍历 outputs 声明中 writeback = true 的 output：
  ↓
解析 field_mappings → 构建字段值：
  · source = 参数表达式 → 从已解析参数取值
  · source = $computed.key → 从引擎 computed_values 取值
  · value = 静态值 / $NOW / $USER → 直接取值
  ↓
获取写回目标：
  · update / delete → 从 target_param 的已解析参数获取 type_rid 和 primary_key
  · create → 从 target_type_rid 获取类型，从字段值提取 primary_key
  ↓
检查 AssetMapping：
  · writeback_enabled = false → 报错 FUNCTION_WRITEBACK_DISABLED
  · writeback_enabled = true → 继续
  ↓
调用 DataService 的写回接口：
  · write_editlog(type_rid, primary_key, operation, field_values, branch)
  ↓
Data 在 FDB 事务中完成：
  · 获取行级锁
  · 写入 EditLog
  · 释放锁
  ↓
返回写入确认（所有 writeback output 逐一处理）
```

**多 output 写回的事务语义**：

多个 `writeback = true` 的 output 逐一调用 `write_editlog`。如果某个 output 写回失败（如 `FUNCTION_WRITEBACK_LOCK_CONFLICT`），已完成的 output 不回滚。整体执行状态标记为 `partial_success`，返回每个 output 的独立写回结果（成功/失败及原因），由用户决定后续处理。

选择 best-effort 而非事务回滚的理由：
- 每个 output 操作的是**不同实例**（target_param 唯一性校验保证），相互独立
- EditLog 是追加式写入，已写入的条目代表有效的业务操作，不应因无关实例的写回失败而撤销
- 需要 all-or-nothing 语义的场景应编排为工作流（Workflow），在工作流层面处理补偿

**DataService Protocol 扩展**（写回方法）：

```python
class DataService(Protocol):
    # ... 已有的 query_instances, get_instance, invalidate_schema_cache ...

    def write_editlog(
        self,
        type_rid: str,
        primary_key: dict[str, Any],
        operation: str,             # "create" / "update" / "delete"
        field_values: dict[str, Any],
        user_id: str,
        action_type_rid: str,
        branch: str | None = None,
    ) -> WriteResult: ...
```

Function 不直接操作 FDB，而是通过 DataService Protocol 的 `write_editlog` 方法写入。FDB 事务（锁 + EditLog）的实现细节封装在 Data 内部。

#### 2.4.2 写回映射

output 声明的 `operation` 决定 EditLog 的写入内容：

| output operation | EditLog operation | field_values 内容 |
|---|---|---|
| `"create"` | `"create"` | 全量字段（含主键） |
| `"update"` | `"update"` | 仅变更字段 |
| `"delete"` | `"delete"` | 空（标记删除） |

此映射与引擎类型无关——由 implementation 中 outputs 声明的 operation 和 field_mappings 统一决定。

### 2.5 Global Function

#### 2.5.1 内置 Global Function

系统预注册的内置函数，封装 DataService 和 OntologyService 的查询能力：

| api_name | 说明 | 调用的 Protocol 方法 |
|---|---|---|
| `query_instances` | 查询数据实例 | DataService.query_instances |
| `get_instance` | 获取单个数据实例 | DataService.get_instance |
| `list_object_types` | 列出所有 ObjectType | OntologyService.list_object_types |
| `list_link_types` | 列出所有 LinkType | OntologyService.list_link_types |
| `get_object_type` | 获取 ObjectType 详情 | OntologyService.get_object_type |
| `get_link_type` | 获取 LinkType 详情 | OntologyService.get_link_type |
| `get_related_links` | 查询 Object 实例的关联 Link | Data API 端点: `POST /data/v1/objects/{rid}/instances/links` |
| `get_related_objects` | 查询 Link 实例的关联 source/target Object | Data API 端点: `POST /data/v1/links/{rid}/instances/objects` |

内置函数的 `safety_level` 均为 `SAFETY_READ_ONLY`，无副作用声明。

`get_related_links` / `get_related_objects` 通过 Data 模块的 API 端点实现关系遍历（方案 A），不通过 DataService Protocol 接口。原因：关系遍历是"Ontology 元数据查询 + 多次 Data 原始操作"的组合逻辑（详见 DATA_DESIGN.md §2.1），属于 API 层的组合端点，不属于跨模块 Protocol 接口。单体阶段通过进程内直接调用 Data Router 的处理函数实现，无需经过 HTTP 网络请求。

Copilot 通过这些内置函数查询数据和类型定义，无需直接调用 DataService 或 OntologyService。

#### 2.5.2 用户自定义 Function

用户可注册自定义 Global Function：

**Python 类型**：
- 用户上传 Python 脚本
- 在隔离环境中执行（与 ENGINE_PYTHON_VENV 共用隔离机制）
- 可调用内置函数获取数据

**Webhook 类型**：
- 配置外部 HTTP API 端点
- 请求模板支持参数注入
- 响应解析为结构化结果

#### 2.5.3 版本管理

Global Function 支持版本管理：

- 每次更新生成新版本（version 自增）
- 可回退到历史版本
- 当前生效版本标记为 `active`
- 工作流引用 Global Function 时绑定到 `active` 版本

### 2.6 工作流

#### 2.6.1 工作流模型

工作流由**节点**（Node）和**边**（Edge）组成的有向无环图（DAG）。

**节点类型**：

| 类型 | 说明 |
|------|------|
| `action` | 执行 Ontology Action |
| `function` | 执行 Global Function |
| `condition` | 条件判断，决定后续走哪条边 |

**边**：
- `from` → `to`：执行顺序
- 条件边：附带条件表达式，根据上游节点输出判断是否执行

**参数映射**（`params_mapping`）：
- 节点参数可引用工作流输入（`$input.xxx`）
- 节点参数可引用上游节点输出（`$step_1.output.xxx`）
- 静态值直接设置

#### 2.6.2 执行引擎

```
接收工作流执行请求（params）
  ↓
加载工作流定义（nodes + edges）
  ↓
拓扑排序 → 确定执行顺序
  ↓
按顺序执行节点：
  · 解析参数映射（$input / $step_N.output / 静态值）
  · condition 节点：评估条件，决定后续分支
  · action / function 节点：调用对应的执行方法
    · action 节点的 safety_level ≥ SAFETY_NON_IDEMPOTENT → 工作流暂停，返回确认请求
    · 用户确认 → 恢复执行当前节点，继续后续节点
    · 用户取消 → 工作流标记为 cancelled
  · 记录节点执行结果
  ↓
任意节点失败 → 工作流标记为 failed，停止执行后续节点
  ↓
所有节点完成 → 工作流标记为 success
  ↓
返回 WorkflowExecutionResult（各节点结果 + 整体状态）
```

**工作流暂停与恢复**：
- 工作流暂停时，执行状态（已完成节点及其结果、当前待确认节点）持久化到 executions 表的 `result` 字段
- 工作流执行状态标记为 `pending_confirmation`，确认/取消 URL 指向工作流的 execution_id
- 用户确认后从持久化状态恢复执行，继续后续节点

**错误处理**：
- 默认策略：节点失败时停止工作流
- 可配置 `on_error: "continue"`：节点失败时跳过，继续后续节点
- 工作流级别的超时控制

#### 2.6.3 安全级别与副作用自动计算

工作流的 `safety_level` 和 `side_effects` 由其包含的节点自动推导，不允许手动设置：

```
工作流保存时：
  1. 遍历所有 action / function 节点
  2. 获取每个节点对应能力的 safety_level
  3. 工作流 safety_level = max(所有节点的 safety_level)
     优先级：SAFETY_CRITICAL > SAFETY_NON_IDEMPOTENT > SAFETY_IDEMPOTENT_WRITE > SAFETY_READ_ONLY
  4. 工作流 side_effects = 所有节点 side_effects 的去重合集
  5. 持久化到 workflows 表的 safety_level 和 side_effects 字段
```

**节点变更时重新计算**：工作流定义更新（增删节点、更换引用能力）时自动重新计算。引用的 ActionType 或 Global Function 的 safety_level 变更时，相关工作流在下次保存或发布时重新计算。

### 2.7 安全策略

#### 2.7.1 执行策略映射

| safety_level | 前端行为 | Copilot 行为 |
|---|---|---|
| `SAFETY_READ_ONLY` | 直接执行 | 直接执行 |
| `SAFETY_IDEMPOTENT_WRITE` | 直接执行 | 直接执行 |
| `SAFETY_NON_IDEMPOTENT` | 弹出确认弹窗（FunctionService pending_confirmation） | interrupt() 确认 → skip_confirmation=true 调用 FunctionService |
| `SAFETY_CRITICAL` | 弹出确认弹窗 + 影响分析（FunctionService pending_confirmation） | interrupt() 确认 + 影响分析 → skip_confirmation=true 调用 FunctionService |

#### 2.7.2 确认流程

```
执行请求 → safety_level ≥ SAFETY_NON_IDEMPOTENT

路径 A：skip_confirmation = false（前端 UI 直接调用）
  ↓
  创建执行记录（status = pending_confirmation）
  ↓
  返回确认请求：
    · outputs 写回摘要（哪些实例将被修改、什么操作）
    · side_effects 列表
    · confirm/cancel URL
  ↓
  用户确认 → POST /function/v1/executions/{id}/confirm
    · 重新解析 derived_from 参数（获取最新实例数据，避免确认等待期间数据过期）
    · 若实例已不存在或数据变化导致校验失败 → 返回错误，执行标记 failed
    · 继续执行（引擎 + 写回）
  用户取消 → POST /function/v1/executions/{id}/cancel → 标记 cancelled，不执行
  ↓
  超时未确认（默认 10 分钟）→ 自动标记 expired

路径 B：skip_confirmation = true（Copilot 调用，已通过 interrupt() 完成确认）
  ↓
  跳过 pending_confirmation 阶段，直接执行（引擎 + 写回）
  ↓
  创建执行记录（status = success/failed），confirmed_by 标记为 "copilot_interrupt"
```

确认请求中的 outputs 写回摘要从 implementation 中解析的 outputs 声明生成：列出所有 `writeback = true` 的 output，展示目标实例（`target_param` 的已解析数据）和操作类型，让用户清楚知道这次执行会修改什么。

### 2.8 Action Revert（设计预留）

**当前不实现**，预留设计方向。

EditLog 是追加式日志，天然支持撤销：写入一条反向 EditLog 条目即可。执行记录（executions 表）中已持久化完整的写回信息（params、result、affected outputs），包含足够的数据用于构建反向操作。

**未来实现方向**：
- 仅支持最近一次执行的撤销（与 Palantir 一致）
- 仅执行用户本人可撤销
- Side effects（外部 API 调用、通知）不可撤销
- 撤销操作本身记录为新的执行记录（`capability_type: "revert"`）

### 2.9 存储设计

#### 2.9.1 PostgreSQL

**global_functions 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.func.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| api_name | VARCHAR | API 名称 |
| display_name | VARCHAR | 显示名称 |
| description | TEXT | 描述 |
| parameters | JSONB | 参数定义列表 |
| implementation | JSONB | 实现配置（type + handler/script/webhook_config） |
| version | INTEGER | 当前版本号 |
| is_active | BOOLEAN | 是否为当前生效版本 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**workflows 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.workflow.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| api_name | VARCHAR | API 名称 |
| display_name | VARCHAR | 显示名称 |
| description | TEXT | 描述 |
| parameters | JSONB | 工作流输入参数定义 |
| definition | JSONB | 工作流定义（nodes + edges） |
| safety_level | VARCHAR | 自动计算：所有节点 safety_level 的最大值（见 §2.6.3） |
| side_effects | JSONB | 自动计算：所有节点 side_effects 的去重合集（见 §2.6.3） |
| version | INTEGER | 当前版本号 |
| is_active | BOOLEAN | 是否为当前生效版本 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**executions 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| execution_id | VARCHAR | 主键，`exec_{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| capability_type | VARCHAR | `action` / `function` / `workflow` |
| capability_rid | VARCHAR | 被执行的能力 RID |
| status | VARCHAR | `running` / `pending_confirmation` / `success` / `partial_success` / `failed` / `cancelled` / `expired` |
| params | JSONB | 执行参数 |
| result | JSONB | 执行结果 |
| safety_level | VARCHAR | 安全级别 |
| side_effects | JSONB | 副作用声明 |
| user_id | VARCHAR | 执行用户 |
| branch | VARCHAR | 数据分支 |
| started_at | TIMESTAMP | 开始时间 |
| completed_at | TIMESTAMP | 完成时间 |
| confirmed_at | TIMESTAMP | 确认时间（仅 pending_confirmation） |
| confirmed_by | VARCHAR | 确认来源：`user`（前端确认）/ `copilot_interrupt`（Copilot interrupt 确认） |

### 2.10 业务规则

#### 2.10.1 Action 可用性

Action 的可用性取决于 ActionType 的版本状态和 `lifecycle_status`：

- **仅 Active 版本的 ActionType 可执行**：Draft 和 Staging 版本不可执行，不出现在能力清单中（版本状态由 Ontology 版本管理系统控制，详见 ONTOLOGY_DESIGN.md §2.4）
- **`lifecycle_status` 过滤**：Active 版本中，仅 `ACTIVE` 和 `EXPERIMENTAL` 状态的 ActionType 可执行；`DEPRECATED` 和 `EXAMPLE` 状态的不出现在能力清单中

#### 2.10.2 工作流引用检测

删除 Global Function 前检查是否被工作流引用：

```
DELETE /function/v1/functions/{rid}
  1. 查询 workflows 表中 definition 包含该 function_rid 的工作流
  2. 存在引用 → 返回 409（FUNCTION_IN_USE），附带引用列表
  3. 无引用 → 执行删除
```

#### 2.10.3 错误码

遵循 `TECH_DESIGN.md` 第 5 节的错误码体系，前缀 `FUNCTION_`：

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `FUNCTION_NOT_FOUND` | 404 | Action/Function/Workflow RID 不存在 |
| `FUNCTION_EXECUTION_FAILED` | 500 | 引擎执行失败 |
| `FUNCTION_TIMEOUT` | 504 | 执行超时 |
| `FUNCTION_PARAM_INVALID` | 400 | 参数类型不匹配或缺少必填参数 |
| `FUNCTION_PARAM_INSTANCE_NOT_FOUND` | 404 | 实例引用参数指向的实例不存在 |
| `FUNCTION_INTERFACE_NOT_IMPLEMENTED` | 422 | 接口引用参数的实例类型未实现指定 InterfaceType |
| `FUNCTION_WRITEBACK_DISABLED` | 422 | 目标类型的 AssetMapping 未启用写回 |
| `FUNCTION_WRITEBACK_LOCK_CONFLICT` | 409 | 写回时 FDB 行级锁冲突 |
| `FUNCTION_CONFIRMATION_EXPIRED` | 410 | 待确认的执行已过期 |
| `FUNCTION_WORKFLOW_CYCLE` | 422 | 工作流定义包含循环依赖 |
| `FUNCTION_IN_USE` | 409 | 删除 Function 时被工作流引用 |

---

## 3. 前端交互设计

### 3.1 页面结构

能力模块在 Main Stage 内采用 PRODUCT_DESIGN.md 定义的**侧边面板 + 内容区域**结构。

```
┌──────────────┬──────────────────────────────────────────┐
│  侧边面板     │  内容区域                                 │
│              │                                          │
│  概览        │                                          │
│  原子能力    │     （能力列表 / 执行页 / 管理页）          │
│  工作流      │                                          │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
```

**侧边面板说明**：
- 3 个固定导航项：概览、原子能力、工作流
- 侧边面板不展示具体能力列表——点击导航项后在内容区域展示

### 3.2 原子能力

#### 3.2.1 能力列表

点击侧边面板"原子能力"，在内容区域展示统一的能力列表。

```
从 Function 获取能力清单
  → Action：从 Ontology 获取所有 Active 的 ActionType
  → Global Function：从 Function 获取所有注册的函数
  → 合并为统一列表，按类型分组
```

| 列 | 内容 |
|----|------|
| 名称 | display_name |
| 类型 | Action / Global Function（标签区分） |
| 安全级别 | safety_level（颜色编码：绿/黄/橙/红） |
| 描述 | description |
| 最近执行 | 时间戳 |

**操作**：
- 点击 Action → 进入 Action 执行页
- 点击 Global Function → 进入 Function 详情/执行页
- 新建 Global Function：列表页入口

#### 3.2.2 Action 执行页

**参数表单**（根据 ActionType.parameters 动态生成）：

| 参数类型 | 表单控件 |
|---|---|
| `derived_from_object_type_rid` | 实例选择器（下拉搜索该 ObjectType 的实例） |
| `derived_from_link_type_rid` | 实例选择器（下拉搜索该 LinkType 的实例） |
| `derived_from_interface_type_rid` | 先选类型（实现了该接口的 ObjectType/LinkType），再选实例 |
| `explicit_type: DT_STRING` | 文本输入 |
| `explicit_type: DT_INTEGER / DT_DOUBLE` | 数字输入 |
| `explicit_type: DT_BOOLEAN` | 开关 |
| `explicit_type: DT_DATE / DT_TIMESTAMP` | 日期选择器 |

**执行按钮**：
- `SAFETY_READ_ONLY / SAFETY_IDEMPOTENT_WRITE`：直接执行
- `SAFETY_NON_IDEMPOTENT / SAFETY_CRITICAL`：确认弹窗后执行

**执行历史**：
- 该 ActionType 的历史执行记录（时间、执行用户、状态、参数摘要）
- 点击记录 → 查看执行详情

**跳转**：
- "查看 ActionType 定义" → 跳转到本体模块 ActionType 编辑器

#### 3.2.3 Global Function 管理页

- 查看/编辑 Function 配置
- 参数定义管理
- 实现配置（builtin / python / webhook）
- 测试执行：填写参数 → 执行 → 查看结果
- 版本历史和回退

### 3.3 工作流

#### 3.3.1 工作流列表

点击侧边面板"工作流"，在内容区域展示工作流列表。

| 列 | 内容 |
|----|------|
| 名称 | display_name |
| 节点数 | 工作流包含的节点数 |
| 描述 | description |
| 最近执行 | 时间戳 |

**操作**：
- 点击 → 进入工作流编辑页
- 新建工作流：列表页入口

#### 3.3.2 工作流编辑页

**画布区域**：
- DAG 可视化编辑器
- 拖拽添加节点（从原子能力列表中选择）
- 连线定义执行顺序
- 点击节点配置参数映射和条件

**参数面板**（右侧）：
- 工作流输入参数定义
- 选中节点时展示该节点的参数映射配置

**操作**：
- 保存 / 发布
- 测试执行

#### 3.3.3 工作流执行页

- 参数输入表单（根据工作流 parameters 动态生成）
- 执行按钮
- 执行进度：DAG 图中标记每个节点的执行状态（待执行 / 执行中 / 成功 / 失败）
- 执行历史

### 3.4 概览页

侧边面板点击"概览"进入。

**内容**：
- 能力统计卡片：Action 数量、Global Function 数量、Workflow 数量
- 最近执行记录：最近 24 小时的执行统计（成功/失败/待确认）
- 最近执行列表：按时间排序的执行记录

### 3.5 跨模块跳转

**跳转到本体模块**：
- Action 执行页的"查看定义" → 本体模块 ActionType 编辑器

**跳转到数据模块**：
- 实例选择器中的实例 → 数据模块实例详情页

**从数据模块跳入**：
- 实例详情页的"执行操作" → 能力模块 Action 执行页（预填实例引用参数）

---

## 4. 实现优先级

| 阶段 | 范围 | 前置依赖 | 说明 |
|------|------|---------|------|
| P0 | Action 加载 + 参数解析 + NativeCRUD 引擎 + 安全检查 + 执行历史 + 前端 Action 执行页 | Ontology P1（ActionType 定义） | 核心执行闭环：可加载 ActionType、解析参数、执行 NativeCRUD、记录执行日志 |
| P0 | 内置 Global Function（查询实例、获取类型定义）+ 能力清单 API | DataService P0、OntologyService P0 | Copilot 可调用的基础查询能力 |
| P1 | PythonVenv / SQLRunner / Webhook 引擎 + 用户自定义 Function | — | 扩展执行引擎和用户自定义能力 |
| P2 | Action 写回（FDB EditLog）+ 批量执行 + 异步执行 | Data P2（FDB 写回管道） | 写入闭环：Action 执行后数据变更持久化 |
| P3 | 工作流编排 + 工作流执行引擎 + 前端 DAG 编辑器 | P0-P2 完成 | 组合能力编排 |

---
