# TECH_DESIGN.md - LingShu 整体技术设计

> **版本**: 0.3.0
> **更新日期**: 2026-02-22
> **状态**: 草稿
> **前置文档**: `DESIGN.md`（整体设计）、`ONTOLOGY.md`（本体定义）

---

## 1. 技术选型

### 1.1 按能力域划分

| 能力域 | 语言 | 框架 | 说明 |
|--------|------|------|------|
| Ontology | Python | FastAPI | 类型定义 CRUD、版本管理、依赖检测 |
| Data | Python | FastAPI | 数据源关联、实例查询、脱敏 |
| Function | Python | FastAPI | 原子能力执行、Global Function 管理、工作流编排 |
| Copilot | Python | LangGraph | AI Agent、A2UI 流式生成 |
| Setting | Python | FastAPI | 认证、用户管理、租户管理、审计日志 |
| 前端 | TypeScript | Next.js 15 + Shadcn/UI | Ontology Studio、Data Explorer、Copilot 面板 |

**说明**：初期全部使用 Python 实现后端服务，降低技术栈复杂度，加快迭代速度。后续根据性能需求将 Ontology、Data、Function 服务迁移至 Go。

### 1.2 存储选型

| 存储 | 用途 | 说明 |
|------|------|------|
| 图数据库 | Ontology 图模型（类型定义 + 关系） | 初期 Neo4j，目标迁移至 GalaxyBase（见 11.2） |
| PostgreSQL | 版本快照、审计日志、Copilot 会话、用户/租户 | 长期方案 |
| Redis | Active 版本缓存、分布式锁、JWT Blacklist | 长期方案 |
| FoundationDB | EditLog 编辑缓冲、行级锁 | P2 阶段引入，详见 DATA_DESIGN.md §2.3.2 |

### 1.3 通信协议

| 场景 | 协议 | 说明 |
|------|------|------|
| 前端 → 后端（CRUD） | REST (HTTP/JSON) | Ontology / Data / Function 的标准操作 |
| 前端 → 后端（Copilot） | HTTP POST | 发送自然语言消息、对话交互 |
| 后端 → 前端（Copilot） | SSE (Server-Sent Events) | A2UI 流式 UI 推送 |
| 后端服务间 | 进程内函数调用 | 初期单体部署，通过接口抽象保证可拆分 |

---

## 2. 服务划分

### 2.1 初期：单体部署

初期所有能力域部署在同一个 Python 进程中，通过模块化隔离：

```
lingshu/
├── ontology/       # Ontology 能力域
├── data/           # Data 能力域
├── function/       # Function 能力域
├── copilot/        # Copilot 能力域
├── setting/        # Setting 模块（Auth、用户、租户、审计）
├── infra/          # 基础设施（DB 连接、请求上下文、错误处理）
└── main.py         # FastAPI 应用入口
```

**模块间通信**：通过 Python 接口（Protocol / ABC）调用，不直接引用具体实现类。

**关键约束**：
- 模块间禁止共享数据库 Model 或 ORM 对象——通过 DTO 传递数据
- 每个模块有独立的路由前缀（`/ontology/`、`/data/`、`/function/`、`/copilot/`、`/setting/`）
- 每个模块有独立的数据库访问层——不跨模块直接查库

### 2.2 目标：可拆分服务

当性能或团队规模需要时，将模块拆分为独立服务：
- 模块间通信从函数调用切换为 gRPC
- 基础设施抽取为独立的 SDK 包
- 各服务独立部署、独立扩缩

---

## 3. API 规范

### 3.1 URL 命名

```
/{capability}/{version}/{resource}

示例：
/ontology/v1/object-types
/ontology/v1/object-types/{rid}
/data/v1/objects/{object_type_rid}/instances
/function/v1/actions/{action_type_rid}/execute
/function/v1/workflows
/copilot/v1/sessions
/copilot/v1/models
```

**规则**：
- 能力域前缀：`ontology` / `data` / `function` / `copilot` / `setting`
- 版本号：各能力域独立版本化（`v1`、`v2`...）
- 资源名称使用 **kebab-case**（如 `object-types`）
- 资源 ID 使用 RID（如 `ri.obj.xxx`）

### 3.2 HTTP 方法

| 操作 | 方法 | 示例 |
|------|------|------|
| 创建 | POST | `POST /ontology/v1/object-types` |
| 查询单个 | GET | `GET /ontology/v1/object-types/{rid}` |
| 查询列表 | POST | `POST /ontology/v1/object-types/query` |
| 更新 | PUT | `PUT /ontology/v1/object-types/{rid}` |
| 删除 | DELETE | `DELETE /ontology/v1/object-types/{rid}` |
| 执行操作 | POST | `POST /function/v1/actions/{rid}/execute` |

### 3.3 请求/响应格式

**成功响应**：

```json
{
  "data": { ... },
  "metadata": {
    "request_id": "req_xxx",
    "timestamp": "2026-02-22T10:00:00Z"
  }
}
```

**列表查询请求**：

```json
POST /data/v1/objects/{rid}/instances/query

{
  "filters": [
    { "field": "status", "operator": "eq", "value": "active" },
    { "field": "battery_level", "operator": "gte", "value": 20 }
  ],
  "sort": [
    { "field": "created_at", "order": "desc" }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20
  }
}
```

**列表查询响应**：

```json
{
  "data": [ ... ],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "has_next": true
  },
  "metadata": {
    "request_id": "req_xxx",
    "timestamp": "2026-02-22T10:00:00Z"
  }
}
```

### 3.4 筛选操作符

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `{"field": "status", "operator": "eq", "value": "active"}` |
| `neq` | 不等于 | `{"field": "status", "operator": "neq", "value": "deleted"}` |
| `gt` / `gte` | 大于 / 大于等于 | `{"field": "battery", "operator": "gte", "value": 20}` |
| `lt` / `lte` | 小于 / 小于等于 | `{"field": "battery", "operator": "lt", "value": 80}` |
| `contains` | 包含（字符串） | `{"field": "name", "operator": "contains", "value": "robot"}` |
| `in` | 在列表中 | `{"field": "status", "operator": "in", "value": ["active", "experimental"]}` |

---

## 4. 请求上下文

每个 API 请求携带以下上下文信息：

| 上下文 | 来源 | 说明 |
|--------|------|------|
| `tenant_id` | JWT Cookie（production） / `X-Tenant-ID` Header（dev） | 租户标识 |
| `user_id` | JWT Cookie（production） / `X-User-ID` Header（dev） | 用户标识 |
| `request_id` | `X-Request-ID` Header | 请求追踪 ID（UUID，客户端生成或网关生成） |
| `trace_id` | `X-Trace-ID` Header | 分布式追踪 ID（可选，可观测性系统注入） |

**上下文来源**：

- **Production 模式**（`LINGSHU_AUTH_MODE=production`）：Auth Middleware 从 HttpOnly Cookie 中提取 JWT，解析 `sub`（user_id）和 `tenant_id` 写入 ContextVar。`X-Tenant-ID` / `X-User-ID` Header 被忽略
- **Dev 模式**（`LINGSHU_AUTH_MODE=dev`）：Auth Middleware 从 `X-Tenant-ID` / `X-User-ID` Header 读取，写入 ContextVar。无需登录，便于开发调试。详见 `SETTING_DESIGN.md` §2.2

**传递方式**：
- 前端 → 后端：JWT Cookie（production）或 HTTP Header（dev）
- 模块间调用：通过 Python ContextVar 传递（单体阶段）；通过 gRPC metadata 传递（拆分后）
- 数据库查询：所有查询自动附加 `tenant_id` 过滤条件

---

## 5. 错误处理规范

### 5.1 错误响应格式

```json
{
  "error": {
    "code": "ONTOLOGY_DEPENDENCY_CONFLICT",
    "message": "Cannot delete SharedPropertyType: referenced by 3 PropertyTypes",
    "details": {
      "shared_property_type_rid": "ri.shprop.xxx",
      "referencing_rids": ["ri.prop.aaa", "ri.prop.bbb", "ri.prop.ccc"]
    }
  },
  "metadata": {
    "request_id": "req_xxx",
    "timestamp": "2026-02-22T10:00:00Z"
  }
}
```

### 5.2 错误码体系

错误码格式：`{CAPABILITY}_{CATEGORY}_{SPECIFIC}`

| 能力域 | 前缀 | 示例 |
|--------|------|------|
| Ontology | `ONTOLOGY_` | `ONTOLOGY_DEPENDENCY_CONFLICT`、`ONTOLOGY_VERSION_CONFLICT`、`ONTOLOGY_VALIDATION_FAILED` |
| Data | `DATA_` | `DATA_SOURCE_UNREACHABLE`、`DATA_QUERY_TIMEOUT`、`DATA_SCHEMA_MISMATCH` |
| Function | `FUNCTION_` | `FUNCTION_EXECUTION_FAILED`、`FUNCTION_TIMEOUT`、`FUNCTION_NOT_FOUND` |
| Copilot | `COPILOT_` | `COPILOT_SESSION_NOT_FOUND`、`COPILOT_SESSION_EXPIRED`、`COPILOT_TOOL_FAILED` |
| Setting | `SETTING_` | `SETTING_AUTH_INVALID_CREDENTIALS`、`SETTING_USER_NOT_FOUND`、`SETTING_PERMISSION_DENIED` |
| 通用 | `COMMON_` | `COMMON_UNAUTHORIZED`、`COMMON_FORBIDDEN`、`COMMON_NOT_FOUND`、`COMMON_INVALID_INPUT` |

### 5.3 HTTP 状态码映射

| 状态码 | 场景 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误（INVALID_INPUT） |
| 401 | 未认证（UNAUTHORIZED） |
| 403 | 无权限（FORBIDDEN） |
| 404 | 资源不存在（NOT_FOUND） |
| 409 | 冲突（VERSION_CONFLICT、DEPENDENCY_CONFLICT） |
| 422 | 业务校验失败（VALIDATION_FAILED） |
| 500 | 服务器内部错误 |
| 504 | 超时（QUERY_TIMEOUT、EXECUTION_TIMEOUT） |

---

## 6. RID 规范

### 6.1 格式定义

系统中所有资源使用统一的 RID（Resource Identifier）格式：

```
ri.{resource_type}.{uuid}
```

- `ri` — 固定前缀
- `resource_type` — 资源类型标识（小写，见下表）
- `uuid` — UUID v4（全局唯一）

### 6.2 资源类型注册表

| 资源类型 | RID 前缀 | 所属能力域 | 说明 |
|----------|----------|-----------|------|
| `shprop` | `ri.shprop.{uuid}` | Ontology | SharedPropertyType |
| `prop` | `ri.prop.{uuid}` | Ontology | PropertyType |
| `iface` | `ri.iface.{uuid}` | Ontology | InterfaceType |
| `obj` | `ri.obj.{uuid}` | Ontology | ObjectType |
| `link` | `ri.link.{uuid}` | Ontology | LinkType |
| `action` | `ri.action.{uuid}` | Ontology | ActionType |
| `snap` | `ri.snap.{uuid}` | Ontology | Snapshot |
| `conn` | `ri.conn.{uuid}` | Data | 数据源连接 |
| `func` | `ri.func.{uuid}` | Function | Global Function |
| `workflow` | `ri.workflow.{uuid}` | Function | 工作流 |
| `session` | `ri.session.{uuid}` | Copilot | 会话 |
| `model` | `ri.model.{uuid}` | Copilot | 基座模型配置 |
| `skill` | `ri.skill.{uuid}` | Copilot | Skill |
| `mcp` | `ri.mcp.{uuid}` | Copilot | MCP 服务连接 |
| `subagent` | `ri.subagent.{uuid}` | Copilot | 子智能体 |
| `user` | `ri.user.{uuid}` | Setting | 用户 |
| `tenant` | `ri.tenant.{uuid}` | Setting | 租户 |

**扩展规则**：新增资源类型时，在此表注册前缀，确保全局不冲突。

> **注意**：Function 模块的执行记录（executions）使用 `exec_{uuid}` 格式而非 RID 格式。执行记录是追加写入的时序数据，不需要跨系统引用，因此不纳入 RID 体系。详见 FUNCTION_DESIGN.md §2.7。

### 6.3 生成与校验

- **生成时机**：服务端在资源创建时生成，客户端不可指定
- **唯一性保证**：UUID v4 + 资源类型前缀，全局唯一
- **校验规则**：正则 `^ri\.[a-z]+\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
- **不可变性**：RID 一旦生成不可修改，资源删除后 RID 不复用

---

## 7. 配置管理

### 7.1 配置分层

| 层级 | 来源 | 说明 | 示例 |
|------|------|------|------|
| 默认值 | 代码内置 | 合理的默认配置 | 分页大小 20、Redis TTL 5 分钟 |
| 环境变量 | `.env` / 部署平台 | 环境相关配置，覆盖默认值 | 数据库连接串、端口号 |
| 运行时配置 | 数据库 / Redis | 可动态调整的业务配置 | 功能开关、限流阈值 |

**优先级**：运行时配置 > 环境变量 > 默认值

### 7.2 环境变量规范

命名格式：`LINGSHU_{CAPABILITY}_{NAME}`

```bash
# 基础设施
LINGSHU_SERVER_PORT=8000
LINGSHU_SERVER_ENV=development          # development / staging / production

# 存储连接
LINGSHU_GRAPH_DB_URI=bolt://localhost:7687
LINGSHU_POSTGRES_URI=postgresql://localhost:5432/lingshu
LINGSHU_REDIS_URI=redis://localhost:6379/0

# Copilot
LINGSHU_COPILOT_LLM_API_KEY=sk-xxx
LINGSHU_COPILOT_LLM_MODEL=gpt-4
```

### 7.3 敏感信息管理

- 敏感配置（API Key、数据库密码）**不得**提交到代码仓库
- 本地开发使用 `.env` 文件（已加入 `.gitignore`）
- 生产环境通过部署平台的 Secrets 管理注入

---

## 8. 日志规范

### 8.1 日志格式

所有能力域使用统一的结构化 JSON 日志格式：

```json
{
  "timestamp": "2026-02-22T10:00:00.123Z",
  "level": "INFO",
  "logger": "ontology.service",
  "message": "ObjectType created",
  "request_id": "req_xxx",
  "tenant_id": "tenant_001",
  "user_id": "user_123",
  "trace_id": "trace_xxx",
  "data": {
    "object_type_rid": "ri.obj.xxx",
    "api_name": "robot"
  }
}
```

### 8.2 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| ERROR | 需要立即关注的错误 | 数据库连接失败、Saga 补偿失败 |
| WARN | 异常但可自动恢复 | 查询超时后重试成功、缓存未命中 |
| INFO | 关键业务事件 | 资源创建/更新/删除、版本发布、Function 执行 |
| DEBUG | 调试信息（生产环境关闭） | 请求参数、SQL 语句、图查询 |

### 8.3 必记录事件

每个能力域必须记录以下事件（INFO 级别）：

| 能力域 | 必记录事件 |
|--------|-----------|
| Ontology | 类型创建/更新/删除、版本提交/发布/回滚 |
| Data | 数据源连接/断开、查询执行（含耗时） |
| Function | 原子能力和工作流执行开始/结束/失败（含耗时和参数摘要） |
| Copilot | 会话创建/结束、Tool 调用（含调用链）、智能体配置变更 |
| Setting | 用户登录/登出、用户创建/更新/停用、租户创建/切换、密码重置 |

### 8.4 关联追踪

- 所有日志必须包含 `request_id` 和 `tenant_id`，从请求上下文（第 4 节）自动注入
- 跨模块调用时 `request_id` 保持不变，确保一次用户请求的全链路可追踪
- `trace_id` 可选，用于对接外部可观测性系统

---

## 9. 能力域间通信

### 9.1 接口定义

每个能力域对外暴露一个 Python 接口（Protocol），其他模块通过该接口调用：

```python
# ontology/interface.py（详见 ONTOLOGY_DESIGN.md §2.1）
class OntologyService(Protocol):
    def get_object_type(self, rid: str) -> ObjectTypeDefinition: ...
    def get_link_type(self, rid: str) -> LinkTypeDefinition: ...
    def get_action_type(self, rid: str) -> ActionTypeDefinition: ...
    def get_interface_type(self, rid: str) -> InterfaceTypeDefinition: ...
    def get_shared_property_type(self, rid: str) -> SharedPropertyTypeDefinition: ...

    def list_object_types(self, filters: list[Filter] | None = None) -> list[ObjectTypeDefinition]: ...
    def list_link_types(self, filters: list[Filter] | None = None) -> list[LinkTypeDefinition]: ...
    def list_action_types(self, filters: list[Filter] | None = None) -> list[ActionTypeDefinition]: ...

    def check_implements(self, type_rid: str, interface_type_rid: str) -> bool: ...

    def query_asset_mapping_references(self, connection_rid: str) -> list[AssetMappingReference]: ...

# data/interface.py（详见 DATA_DESIGN.md §2.1）
class DataService(Protocol):
    def query_instances(
        self, type_rid: str, filters: list[Filter],
        sort: list[SortSpec], pagination: Pagination,
        branch: str | None = None,
    ) -> QueryResult: ...
    def get_instance(
        self, type_rid: str, primary_key: dict[str, Any],
        branch: str | None = None,
    ) -> Instance | None: ...
    def invalidate_schema_cache(self, tenant_id: str) -> None: ...
    def on_schema_published(
        self, tenant_id: str, entity_changes: dict[str, str],
    ) -> None: ...
    def write_editlog(
        self, type_rid: str, primary_key: dict[str, Any],
        operation: str, field_values: dict[str, Any],
        user_id: str, action_type_rid: str,
        branch: str | None = None,
    ) -> WriteResult: ...

# function/interface.py（详见 FUNCTION_DESIGN.md §2.1）
class FunctionService(Protocol):
    def list_capabilities(self) -> list[CapabilityDescriptor]: ...
    def execute_action(
        self, action_type_rid: str, params: dict[str, Any],
        branch: str | None = None, skip_confirmation: bool = False,
    ) -> ExecutionResult: ...
    def execute_function(
        self, function_rid: str, params: dict[str, Any],
        branch: str | None = None,
    ) -> ExecutionResult: ...
    def execute_workflow(
        self, workflow_rid: str, params: dict[str, Any],
        branch: str | None = None, skip_confirmation: bool = False,
    ) -> ExecutionResult: ...

# setting/interface.py（详见 SETTING_DESIGN.md §2.1）
class SettingService(Protocol):
    def get_current_user(self) -> UserInfo: ...
    def check_permission(
        self, user_id: str, resource_type: str, action: str,
        resource_rid: str | None = None,
    ) -> bool: ...
    def write_audit_log(
        self, event_type: str, resource_type: str,
        resource_rid: str | None = None, details: dict | None = None,
    ) -> None: ...
```

### 9.2 模块组装

应用启动时通过工厂函数组装模块依赖：

```python
# main.py
def create_app() -> FastAPI:
    # 基础设施
    graph_db = create_graph_db_client()
    postgres = create_postgres_client()
    redis = create_redis_client()

    # 按依赖顺序组装（Setting 最先，提供 Auth Middleware、权限检查和审计写入）
    setting_service = SettingServiceImpl(postgres, redis)
    ontology_service = OntologyServiceImpl(graph_db, postgres, setting_service)
    data_service = DataServiceImpl(ontology_service, postgres, setting_service)
    function_service = FunctionServiceImpl(ontology_service, data_service, setting_service)
    copilot_service = CopilotServiceImpl(function_service, setting_service)

    # 注册路由
    app = FastAPI()
    app.middleware("http")(setting_service.auth_middleware)  # Auth Middleware
    app.include_router(setting_router(setting_service))
    app.include_router(ontology_router(ontology_service))
    app.include_router(data_router(data_service))
    app.include_router(function_router(function_service))
    app.include_router(copilot_router(copilot_service))
    return app
```

模块间只依赖 Protocol 接口，不 import 其他模块的实现类。

### 9.3 拆分后的通信

拆分为独立服务时，为每个 Protocol 实现一个 gRPC Client 适配器：

```python
# function/adapters/ontology_grpc.py
class OntologyGrpcClient(OntologyService):
    def get_object_type(self, rid: str) -> ObjectTypeDefinition:
        # gRPC 调用
        ...
```

业务代码无需修改。

---

## 10. 存储架构

### 10.1 各存储的职责

```
┌───────────────────────────────────────────────┐
│               应用层（能力域）                   │
├────────────┬──────────┬───────────────────────┤
│  图数据库   │PostgreSQL│        Redis          │
│            │          │                       │
│ ·Ontology  │ ·Snapshot │ ·分布式锁             │
│  图模型     │  版本历史 │ ·JWT Blacklist        │
│ ·类型定义   │ ·审计日志 │ ·Active 缓存         │
│ ·Draft/    │ ·Saga 日志│                       │
│  Staging   │ ·Copilot │                       │
│ ·关系边     │  会话状态 │                       │
└────────────┴──────────┴───────────────────────┘
```

### 10.2 数据分布

| 数据 | 存储 | 说明 |
|------|------|------|
| Ontology 类型定义（节点和边） | 图数据库 | 图遍历、依赖检测、级联更新 |
| 版本快照元数据 + 变更详情 | PostgreSQL (JSONB) | 不可变历史记录 |
| Draft 版本数据 | 图数据库 | 与类型定义同库，通过 is_draft 标记区分，用户级隔离 |
| Staging 预发布数据 | 图数据库 | 与类型定义同库，通过 is_staging 标记区分，租户级可见 |
| Active 版本缓存 | Redis | 热数据缓存，TTL 5 分钟 |
| 分布式锁（对象级 / 租户级） | Redis | SET NX EX + Lua 脚本 |
| Copilot 会话状态 | PostgreSQL | 会话元数据 + LangGraph Agent 检查点（AsyncPostgresSaver） |
| Saga 事务日志 | PostgreSQL | 补偿操作记录，崩溃恢复 |
| 用户/租户/审计日志 | PostgreSQL | Setting 模块的存储，详见 SETTING_DESIGN.md §2.4 |
| EditLog 编辑缓冲 | FoundationDB | P2 引入，数据写回的 ACID 缓冲区，详见 DATA_DESIGN.md §2.3.2 |
| 行级锁 | FoundationDB | P2 引入，FDB 事务内锁，详见 DATA_DESIGN.md §2.3.2 |
| 数据实例持久化 | Iceberg | P1 引入，数据湖存储（via Nessie Catalog），详见 DATA_DESIGN.md §2.4.3 |
| 热数据查询加速 | Doris | P3 引入，OLAP 服务层缓存，详见 DATA_DESIGN.md §2.7 |

### 10.3 事务模型

跨存储的操作采用 **Saga 模式**：

- 每个步骤有正向操作和补偿操作
- Saga 日志持久化到 PostgreSQL
- 失败时按反序执行补偿操作
- 支持崩溃恢复（重启后从 Saga 日志恢复未完成的事务）

---

## 11. 演进策略

### 11.1 后端语言：Python → Go

| 维度 | 当前方案（Python） | 目标方案（Go） | 迁移条件 |
|------|-------------------|---------------|---------|
| 适用范围 | Ontology + Data + Function | Ontology + Data + Function | 性能瓶颈出现或团队扩大 |
| Copilot | Python（LangGraph） | Python（不迁移） | — |
| 迁移方式 | — | 逐模块替换，Python Protocol → gRPC 接口 | — |

**设计约束**：
- 模块间通过 Protocol 接口通信，不依赖 Python 语言特性
- 数据传输使用 JSON/Protobuf，不依赖 Python 对象序列化
- 数据库访问层独立封装，不泄露 ORM 细节

### 11.2 图数据库：Neo4j → GalaxyBase

| 维度 | 当前方案（Neo4j） | 目标方案（GalaxyBase） | 迁移条件 |
|------|-----------------|---------------------|---------|
| 用途 | Ontology 图模型存储 | 同左 | 数据量增长或性能需求 |
| 查询语言 | Cypher | nGQL / Cypher 兼容 | — |
| 迁移方式 | — | 实现 GraphDB 接口层，底层切换 | — |

**设计约束**：
- 图数据库操作通过抽象接口（Repository Pattern）封装
- 业务代码不直接写 Cypher 查询——通过 Repository 方法调用
- 查询语句集中管理，迁移时只需替换 Repository 实现

### 11.3 服务形态：单体 → 微服务

| 维度 | 当前方案（单体） | 目标方案（微服务） | 迁移条件 |
|------|---------------|-----------------|---------|
| 部署 | 单进程 | 每个能力域独立部署 | 团队规模 >5 人或性能瓶颈 |
| 通信 | 进程内函数调用 | gRPC | — |
| 迁移方式 | — | Protocol 接口不变，替换实现为 gRPC Client | — |

**设计约束**：
- 模块间通过 Protocol 接口调用（第 9 节）
- 禁止跨模块共享数据库连接或 Model
- 请求上下文通过 ContextVar 传递，可平滑切换为 gRPC metadata

### 11.4 数据层演进

| 维度 | 当前方案 | 目标方案 | 迁移条件 |
|------|---------|---------|---------|
| 数据实例存储 | PostgreSQL | Iceberg（数据湖） | 数据量超过单机 PostgreSQL 容量 |
| 实时查询 | PostgreSQL | Doris（OLAP） | 查询延迟不满足需求 |
| 对象存储 | 本地文件系统 | MinIO（S3 兼容） | 附件/文件管理需求 |

**设计约束**：
- Data 能力域通过 AssetMapping 抽象数据源连接，不硬编码存储类型
- 新增数据源类型只需实现对应的 Connector，不改变 Data 的查询接口

---

## 12. 多租户隔离策略

所有存储层的数据都 scoped to tenant，查询自动附加租户过滤条件。Auth Middleware 从 JWT 解析 `tenant_id` 写入 ContextVar，各模块 Repository 层统一读取。

### 12.1 各存储层隔离方式

| 存储 | 隔离方式 | 说明 |
|------|---------|------|
| Neo4j | 所有节点和边包含 `tenant_id` 属性 | Cypher 查询自动附加 `WHERE n.tenant_id = $tenant_id` |
| PostgreSQL | 所有业务表包含 `tenant_id` 字段 | P0：应用层 WHERE 过滤；P2+：PostgreSQL RLS（Row-Level Security） |
| Redis | Key 前缀 `{tenant_id}:` | 如 `{ri.tenant.xxx}:schema:ri.obj.yyy`、`{ri.tenant.xxx}:jwt_blacklist:jti` |
| FoundationDB | Key 前缀 `{tenant_id}:` | 如 `{tenant_id}:edit:{type_rid}:{pk_hash}:{timestamp}` |

### 12.2 PostgreSQL RLS 演进

**P0-P1：应用层过滤**

Repository 层的所有查询方法从 ContextVar 读取 `tenant_id`，手动附加 WHERE 条件：

```python
# 伪代码
tenant_id = get_current_tenant_id()  # 从 ContextVar 读取
query = select(users).where(users.c.tenant_id == tenant_id)
```

**P2+：PostgreSQL RLS**

启用 RLS 后，即使应用层遗漏 WHERE 条件，数据库层面也能保证隔离：

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
  USING (tenant_id = current_setting('app.tenant_id'));
```

每次数据库连接设置会话变量 `SET app.tenant_id = :tenant_id`，PostgreSQL 自动过滤。

### 12.3 跨租户操作

系统不支持跨租户数据访问。以下场景例外（需 super admin 权限，P3+）：
- 全局审计日志查询（运维场景）
- 租户数据迁移

---

## 13. 数据库迁移与初始化

### 13.1 工具选型

| 存储 | 迁移工具 | 说明 |
|------|---------|------|
| PostgreSQL | Alembic | Python 生态标准迁移工具，支持版本管理和回滚 |
| Neo4j | 手动 Cypher 脚本 | 约束和索引通过 Cypher 脚本管理，启动时幂等执行 |

### 13.2 初始化流程

```
docker-compose up -d（启动 PostgreSQL、Neo4j、Redis）
  ↓
alembic upgrade head（执行 PostgreSQL 迁移，创建所有表和索引）
  ↓
Neo4j 约束与索引脚本（幂等执行，CREATE CONSTRAINT IF NOT EXISTS）
  ↓
Seed 数据初始化（检查 users 表是否为空 → 创建默认租户 + admin 用户）
  ↓
应用启动
```

Alembic 迁移和 Neo4j 脚本在应用启动前执行，可集成到启动脚本或 Docker entrypoint 中。

### 13.3 环境配置

`.env.example` 模板：

```bash
# 基础设施
LINGSHU_SERVER_PORT=8000
LINGSHU_SERVER_ENV=development

# 存储连接
LINGSHU_GRAPH_DB_URI=bolt://localhost:7687
LINGSHU_GRAPH_DB_USER=neo4j
LINGSHU_GRAPH_DB_PASSWORD=password
LINGSHU_POSTGRES_URI=postgresql://lingshu:password@localhost:5432/lingshu
LINGSHU_REDIS_URI=redis://localhost:6379/0

# 认证（详见 SETTING_DESIGN.md §2.2）
LINGSHU_AUTH_MODE=dev                           # dev / production
LINGSHU_AUTH_PROVIDER=builtin                   # builtin（内置）/ oidc（外部 SSO，P3）
LINGSHU_JWT_SECRET=change-me-in-production      # JWT 签名密钥（builtin Provider 使用）
LINGSHU_JWT_ACCESS_TTL=900                      # Access Token TTL（秒），默认 900
LINGSHU_JWT_REFRESH_TTL=604800                  # Refresh Token TTL（秒），默认 604800
# LINGSHU_AUTH_OIDC_ISSUER_URL=                 # 外部 OIDC Provider URL（P3，auth_provider=oidc 时必填）
# LINGSHU_AUTH_OIDC_CLIENT_ID=                  # OIDC Client ID（P3）
# LINGSHU_AUTH_OIDC_CLIENT_SECRET=              # OIDC Client Secret（P3）

# 初始化
LINGSHU_SEED_ADMIN_EMAIL=admin@example.com
LINGSHU_SEED_ADMIN_PASSWORD=change_me_123
LINGSHU_SEED_TENANT_NAME=Default

# Copilot
LINGSHU_COPILOT_LLM_API_KEY=sk-xxx
LINGSHU_COPILOT_LLM_MODEL=gpt-4
```

---
