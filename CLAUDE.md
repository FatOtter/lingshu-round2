# CLAUDE.md - LingShu AI 开发指南

## 项目概述

LingShu 是一个以本体（Ontology）为核心的数据操作系统，包含 4 个能力域 + 1 个横切模块：

| 能力域 | 职责 | 后端路径 | API 前缀 |
|--------|------|---------|---------|
| **Ontology** | 类型定义、版本管理、图存储 | `backend/src/lingshu/ontology/` | `/ontology/v1/` |
| **Data** | 数据源连接、实例查询、脱敏 | `backend/src/lingshu/data/` | `/data/v1/` |
| **Function** | Action 执行、Global Function、工作流 | `backend/src/lingshu/function/` | `/function/v1/` |
| **Copilot** | LangGraph Agent、A2UI 流式、会话管理 | `backend/src/lingshu/copilot/` | `/copilot/v1/` |
| **Setting** | 认证、用户/租户管理、审计日志、RBAC | `backend/src/lingshu/setting/` | `/setting/v1/` |

**前端**：`frontend/src/`，Next.js 15 App Router，5 个模块（本体/数据/能力/智能体/设置）

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.12+ / FastAPI / Pydantic 2 | 所有能力域统一语言 |
| ORM | SQLAlchemy 2 (async) + Alembic | PostgreSQL 访问 + 迁移 |
| 图数据库 | Neo4j (neo4j-driver async) | Ontology 实体 + 关系 + 版本状态 |
| 缓存/锁 | Redis 7 | JWT 黑名单、编辑锁、提交锁 |
| Agent | LangGraph + LangChain | Copilot Agent 引擎（仅 Copilot 使用） |
| 认证 | authlib (JWT) + passlib (bcrypt) + casbin (RBAC) | OIDC-compatible |
| 前端 | Next.js 15 / TypeScript / Shadcn/UI / Tailwind CSS 4 | App Router |
| 状态 | TanStack Query (服务端) + Zustand (客户端) | 数据获取 + UI 状态 |
| 包管理 | uv (后端) / pnpm (前端) | |
| 测试 | pytest + pytest-asyncio (后端) / Vitest + Playwright (前端) | 覆盖率 ≥ 80% |
| 代码质量 | Ruff + mypy (后端) | strict 模式 |

---

## 文档地图

**开发前必读**：根据你要做的工作，先读对应的文档。

| 文档 | 职责 | 何时必读 |
|------|------|----------|
| `docs/TECHNICAL_DESIGN.md` | 实施版技术架构：选型、数据模型、目录结构 | 新建文件、选择技术方案时 |
| `docs/IMPLEMENTATION_PLAN.md` | 分阶段任务拆解（257 个原子任务） | 确认当前任务属于哪个阶段 |
| `docs/DESIGN.md` | 能力域定位、边界、依赖、数据流 | 跨域调用、新增域职责 |
| `docs/TECH_DESIGN.md` | API 规范、RID、错误码、存储架构、通信协议 | API 设计、RID 生成、错误处理 |
| `docs/PRODUCT_DESIGN.md` | 页面布局、模块结构、Sitemap、交互原则 | 前端页面结构、路由 |
| `docs/ONTOLOGY_DESIGN.md` | Ontology CRUD、版本发布、图存储、编辑锁 | 本体模块开发 |
| `docs/DATA_DESIGN.md` | 数据源、查询管道、脱敏、写回 | 数据模块开发 |
| `docs/FUNCTION_DESIGN.md` | Action 执行管道、引擎、Global Function、工作流 | 能力模块开发 |
| `docs/COPILOT_DESIGN.md` | Agent 图、A2UI 协议、Tool 绑定、会话 | 智能体模块开发 |
| `docs/SETTING_DESIGN.md` | 认证、JWT、用户/租户、Casbin RBAC | 设置模块开发 |
| `docs/ONTOLOGY.md` | 本体系统完整指南（6 实体 + 7 关系 + 版本生命周期） | 数据模型、版本管理 |
| `proto/*.proto` | **源头真理**：所有实体字段定义 | 实体字段、数据类型、枚举 |

---

## 强制规则

### 源头真理

1. **Proto 是源头真理**。任何偏离 `proto/*.proto` 和 `docs/ONTOLOGY.md` 的实现都是错误的
2. 新增或修改实体字段：**先改 proto → 再改 ONTOLOGY.md → 最后改代码**
3. 涉及 Ontology 实体（ObjectType/LinkType/InterfaceType/ActionType/SharedPropertyType/PropertyType）时，必须先读 `docs/ONTOLOGY.md` + 对应 proto

### 架构约束

4. **模块隔离**：模块间通过 Protocol 接口通信，禁止共享 ORM Model，通过 DTO 传递数据
5. **依赖方向**：Setting(横切) → Ontology(基础) → Data(数据) → Function(执行) → Copilot(代理)。禁止反向依赖
6. **租户隔离**：所有数据库查询自动附加 `tenant_id` 过滤（从 ContextVar 读取）
7. **Copilot 只调 FunctionService**：Copilot 不直接调用 DataService 或 OntologyService，运行时一切通过 FunctionService Protocol

### 编码规范

8. **不可变优先**：创建新对象而非修改已有对象
9. **文件大小**：单文件 200-400 行典型，800 行上限
10. **函数大小**：单函数 < 50 行
11. **错误处理**：所有错误显式处理，使用统一错误码（`{MODULE}_{CATEGORY}_{SPECIFIC}`）
12. **密码/凭证**：永不硬编码、永不日志记录、永不响应返回

---

## 项目结构

```
lingshu/
├── CLAUDE.md                      # 本文件
├── docs/                          # 设计文档
├── proto/                         # Protobuf 定义（源头真理）
├── backend/
│   ├── pyproject.toml             # uv 项目配置
│   ├── alembic/                   # 数据库迁移
│   ├── tests/                     # 测试（unit/ + integration/）
│   └── src/lingshu/
│       ├── main.py                # FastAPI 入口 + 模块组装
│       ├── config.py              # Pydantic Settings
│       ├── infra/                 # 基础设施（DB连接、ContextVar、错误、RID、日志）
│       ├── setting/               # Setting 模块
│       ├── ontology/              # Ontology 模块
│       ├── data/                  # Data 模块
│       ├── function/              # Function 模块
│       └── copilot/               # Copilot 模块
├── frontend/
│   ├── package.json               # pnpm
│   └── src/
│       ├── app/                   # Next.js App Router
│       │   ├── login/             # 登录页
│       │   └── (authenticated)/   # 认证路由组
│       │       ├── ontology/
│       │       ├── data/
│       │       ├── function/
│       │       ├── agent/
│       │       └── setting/
│       ├── components/            # UI 组件
│       ├── lib/api/               # API 客户端
│       ├── hooks/                 # 自定义 Hooks
│       ├── stores/                # Zustand 状态
│       └── types/                 # TypeScript 类型
└── docker/
    ├── docker-compose.yml         # 本地开发（PostgreSQL + Neo4j + Redis）
    └── docker-compose.test.yml    # 测试环境
```

---

## 开发命令

```bash
# 启动本地基础设施
make dev                    # docker compose up -d

# 后端
cd backend
uv sync                     # 安装依赖
uv run alembic upgrade head # 运行迁移
uv run uvicorn lingshu.main:app --reload  # 启动开发服务器
uv run pytest               # 运行测试
uv run pytest --cov=lingshu --cov-report=term-missing  # 测试+覆盖率
uv run ruff check .         # Lint
uv run ruff format .        # Format
uv run mypy .               # 类型检查

# 前端
cd frontend
pnpm install                # 安装依赖
pnpm dev                    # 启动开发服务器
pnpm test                   # 运行 Vitest 测试
pnpm test:e2e               # 运行 Playwright E2E 测试
pnpm lint                   # ESLint
pnpm build                  # 生产构建
```

---

## 开发流程（TDD 强制）

每个功能的开发流程：

1. **确认阶段**：查看 `docs/IMPLEMENTATION_PLAN.md`，找到当前任务所属 Phase 和 checkbox
2. **读文档**：根据任务内容，读取对应的设计文档（见文档地图）
3. **写测试**（RED）：先写测试，运行确认失败
4. **写实现**（GREEN）：写最小实现，运行测试确认通过
5. **重构**（IMPROVE）：优化代码，确保测试仍通过
6. **验证覆盖率**：`pytest --cov`，确保 ≥ 80%

---

## 模块间通信模式

```python
# 每个模块定义 Protocol 接口（interface.py）
class OntologyService(Protocol):
    def get_object_type(self, rid: str) -> ObjectTypeDefinition: ...

# 其他模块通过 Protocol 调用，不引用具体实现
class DataServiceImpl:
    def __init__(self, ontology_service: OntologyService): ...

# main.py 中组装依赖
ontology_svc = OntologyServiceImpl(graph_repo, snapshot_repo)
data_svc = DataServiceImpl(ontology_service=ontology_svc)
```

---

## RID 规范

格式：`ri.{resource_type}.{uuid}`

| 前缀 | 资源 | 前缀 | 资源 |
|------|------|------|------|
| `ri.obj.*` | ObjectType | `ri.conn.*` | 数据源连接 |
| `ri.link.*` | LinkType | `ri.func.*` | Global Function |
| `ri.iface.*` | InterfaceType | `ri.workflow.*` | 工作流 |
| `ri.action.*` | ActionType | `ri.session.*` | Copilot 会话 |
| `ri.shprop.*` | SharedPropertyType | `ri.model.*` | 基座模型 |
| `ri.prop.*` | PropertyType | `ri.skill.*` | Skill |
| `ri.snap.*` | Snapshot | `ri.mcp.*` | MCP 服务 |
| `ri.user.*` | 用户 | `ri.subagent.*` | Sub-Agent |
| `ri.tenant.*` | 租户 | `exec_*` | 执行记录（非 RID） |

---

## API 响应格式

```json
// 成功
{ "data": { ... }, "metadata": { "request_id": "req_xxx" } }

// 列表
{ "data": [...], "pagination": { "total": 100, "page": 1, "page_size": 20, "has_next": true }, "metadata": {...} }

// 错误
{ "error": { "code": "ONTOLOGY_DEPENDENCY_CONFLICT", "message": "...", "details": {...} }, "metadata": {...} }
```

---

## 版本管理四阶段（Ontology 核心）

```
Draft（用户级草稿，仅 owner 可见）
  → submit-to-staging →
Staging（租户级预发布，所有人可见）
  → commit →
Snapshot（不可变快照，PostgreSQL 存储）
  → 自动更新 →
Active（当前生效版本，Neo4j is_active=true）
```

Neo4j 节点三标记：`is_draft` / `is_staging` / `is_active`（互斥关系见 `ONTOLOGY_DESIGN.md` §2.3.1）

---

## 环境变量

```bash
# 数据库
LINGSHU_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/lingshu
LINGSHU_NEO4J_URI=bolt://localhost:7687
LINGSHU_NEO4J_USER=neo4j
LINGSHU_NEO4J_PASSWORD=password
LINGSHU_REDIS_URL=redis://localhost:6379/0

# 认证
LINGSHU_AUTH_MODE=dev          # dev（Header 降级）/ production（JWT Cookie）
LINGSHU_JWT_SECRET=change-me-in-production
LINGSHU_JWT_ALGORITHM=HS256
LINGSHU_ACCESS_TOKEN_TTL=900   # 15 分钟
LINGSHU_REFRESH_TOKEN_TTL=604800  # 7 天

# Seed
LINGSHU_SEED_ADMIN_EMAIL=admin@example.com
LINGSHU_SEED_ADMIN_PASSWORD=change_me_123
LINGSHU_SEED_TENANT_NAME=Default
```

---

## 核心术语速查

| 术语 | 含义 |
|------|------|
| 能力域 | Ontology / Data / Function / Copilot（后端 4 大模块） |
| 原子能力 | Ontology Action + Global Function 的统称 |
| RID | 资源标识符 `ri.{type}.{uuid}` |
| A2UI | Agent-to-UI 流式协议（SSE 推送结构化 UI 组件） |
| ContextVar | Python 请求上下文（user_id, tenant_id, role, request_id） |
| Protocol | Python 模块间接口（typing.Protocol），单体阶段进程内调用 |
| AssetMapping | ObjectType/LinkType 与物理数据源的映射配置 |
| Virtual Expression | 虚拟计算字段（基于物理字段的表达式） |
| ComplianceConfig | 数据脱敏配置（敏感度 + 脱敏策略） |

---

## 踩坑记录

### CORS + AuthMiddleware 中间件顺序（2026-03-12）

**问题**：前端跨域请求被 CORS 拦截，即使已配置 `CORSMiddleware`。

**根因三层**：
1. **中间件顺序**：FastAPI 中间件执行顺序是 LIFO。`CORSMiddleware` 必须最后 `add_middleware`（成为最外层），否则内层中间件（如 AuthMiddleware）的错误响应不会带 CORS 头
2. **OPTIONS 放行**：`AuthMiddleware` 必须无条件放行 OPTIONS 请求，否则 CORS 预检被 401 拦截
3. **500 错误也需 CORS 头**：即使端点崩溃返回 500，CORS 头也必须存在，否则浏览器报 CORS 错误而非真正的 500 错误（误导排查方向）

**修复**：
```python
# main.py — 中间件添加顺序（LIFO，后加的先执行）
app.add_middleware(AuthMiddleware, ...)   # 先加 → 内层
app.add_middleware(CORSMiddleware, ...)   # 后加 → 外层（包裹一切）
```
```python
# AuthMiddleware.dispatch() — 无条件放行 OPTIONS
if request.method == "OPTIONS":
    return await call_next(request)
```

**规则**：
- `CORSMiddleware` 必须是最外层中间件（最后一个 `add_middleware`）
- 任何认证中间件必须跳过 `OPTIONS` 方法
- 公开端点（如 `/setting/v1/auth/sso/config`）需加入 `WHITELIST_PATHS`
- 所有 DateTime 列使用 `DateTime(timezone=True)` 避免 offset-naive/aware 混用

### DateTime 时区一致性（2026-03-12）

**问题**：login 端点返回 500，错误被 CORS 遮盖（浏览器只报 CORS 错误不报 500）。

**根因**：SQLAlchemy 模型用 `DateTime`（无时区），但代码用 `datetime.now(UTC)`（有时区），PostgreSQL 拒绝插入。

**修复**：所有模型统一 `DateTime(timezone=True)`，数据库列用 `TIMESTAMP WITH TIME ZONE`。

**规则**：永远使用 `DateTime(timezone=True)` + `datetime.now(UTC)`，不要混用。

### 前后端 API 响应格式不匹配（2026-03-12）

**问题**：前端列表页面（用户、租户、会话、模型等）数据为空，表格显示 "No items found"。

**根因**：前后端对分页查询的请求/响应格式约定不一致。

| | 后端实际格式 | 前端错误用法 |
|---|---|---|
| **请求参数** | `{ pagination: { page: 1, page_size: 20 } }` | `{ offset: 0, limit: 20 }` |
| **响应格式** | `{ data: T[], pagination: { total, page, page_size, has_next } }` (`PagedResponse<T>`) | `{ data: { items: T[], total: N } }` (`ApiResponse<{ items, total }>`) |
| **数据访问** | `data?.data` (数组) + `data?.pagination?.total` | `data?.data?.items` (undefined) + `data?.data?.total` (undefined) |

**影响范围**：Setting / Copilot / Data / Function 模块的所有 query 方法和列表页面（共 4 个 API 客户端 + 18 个页面组件）。Ontology 模块未受影响（已正确使用 `PagedResponse`）。

**修复**：
1. API 客户端类型：`ApiResponse<{ items: T[], total }>` → `PagedResponse<T>`
2. 请求参数：`{ offset, limit }` → `{ pagination: { page, page_size } }`
3. 页面数据访问：`data?.data?.items` → `data?.data`，`data?.data?.total` → `data?.pagination?.total`

**规则**：
- 所有分页查询必须使用 `PagedResponse<T>` 类型（`client.ts` 中定义）
- 请求参数使用 `{ pagination: { page, page_size } }` 格式（匹配后端 `QueryRequest` 模型）
- 新增列表页面前先确认后端 router 实际返回的响应模型（查看 `backend/src/lingshu/infra/models.py`）
- 特例：`/function/v1/capabilities/query` 返回 `ApiResponse<CapabilityDescriptor[]>`（无分页），直接用 `data?.data` 取数组

### 前端 API 路径与后端 Router 不一致（2026-03-12）

**问题**：审计日志页面请求 404。

**根因**：前端 API 客户端路径 `/setting/v1/audit/query`，但后端 router 注册的是 `/setting/v1/audit-logs/query`。

**规则**：新增 API 调用时，先 grep 后端 router 确认实际注册路径：`grep -r "@router" backend/src/lingshu/{module}/router.py`

---

## Docker 部署

### 端口映射（避免与其他项目冲突）

| 服务 | 宿主端口 | 容器端口 |
|------|---------|---------|
| frontend | 3100 | 3000 |
| backend | 8100 | 8000 |
| postgres | 5440 | 5432 |
| neo4j (HTTP/Bolt) | 7480 / 7690 | 7474 / 7687 |
| redis | 6390 | 6379 |

### 部署命令

```bash
# 根目录
docker compose up -d          # 启动所有服务
docker compose build frontend # 重建前端镜像
docker compose build backend  # 重建后端镜像
docker compose logs -f backend  # 查看后端日志

# E2E 测试（需先启动 Docker）
cd frontend
npx playwright test e2e/docker-e2e.spec.ts
```

### CORS 配置

`LINGSHU_CORS_ORIGINS` 环境变量（逗号分隔），默认：`http://localhost:3000,http://localhost:3100`

### 中间件懒加载

`AuthMiddleware` 在 `create_app()` 时构造，但 `auth_provider` 在 `lifespan` 中初始化。中间件通过 `request.app.state.auth_provider` 懒解析 provider，不能在构造函数中注入（此时 Redis 等依赖尚未就绪）。

---

## 工作流强制规则（2026-03-13 沉淀）

以下规则从实际踩坑中总结，**必须严格遵守**，违反任何一条都会导致虚假的"全部通过"：

### 规则 1：禁止跳过失败，必须立即修复

**问题**：发现测试失败后只汇报不修，或者绕过失败宣布"全部通过"。

**规则**：
- 发现任何失败 → **立刻修复** → 重新验证 → 确认通过。不存在"已知失败可以忽略"的情况
- 禁止对失败进行分类汇报后就结束。分类是修复的第一步，不是最后一步
- 如果修不了，必须明确告诉用户"这个我修不了，原因是 X，建议 Y"

### 规则 2：代码变更后必须重建 Docker 并验证

**问题**：修改了后端/前端代码，但 Docker 容器还在跑旧代码，E2E 测试跑的是旧版本。

**规则**：
- 任何 `backend/src/` 或 `frontend/src/` 代码变更后，必须 `docker compose build` + `docker compose up -d` 再跑 E2E
- Docker build 失败 ≠ "旧容器也能用"。Build 失败必须修复，不能绕过
- Build 失败常见原因：lockfile 不同步（`uv lock`）、Alembic 多 head、网络超时（重试）

### 规则 3：禁止提前宣布胜利

**问题**：单元测试通过就宣布"全部通过"，实际上 E2E、Docker、集成测试还没跑。

**规则**：
- "全部通过"意味着以下 **全部** 验证完毕：
  1. `cd backend && uv run pytest tests/ -q` — 后端全量
  2. `cd frontend && pnpm test -- --run` — 前端 Vitest
  3. `docker compose build && docker compose up -d` — 容器重建成功
  4. `npx playwright test e2e/` — E2E 全量（包括 journeys）
- 任何一层没跑或者跑了有失败，都不能说"全部通过"
- 每层测试必须在**最新代码**上运行，不能用缓存结果

### 规则 4：Alembic 迁移变更后必须检查 head

**问题**：新增迁移文件时序号冲突（两个 `005_`），导致 Docker 容器启动时 `alembic upgrade head` 报 "Multiple head revisions"。

**规则**：
- 新增 migration 前先 `uv run alembic heads` 确认当前只有一个 head
- 新增后再次 `uv run alembic heads` 确认仍然只有一个 head
- 如果出现多 head，用 `alembic merge` 或手动调整 `down_revision` 修复

### 规则 5：E2E 测试必须对齐实际 UI

**问题**：E2E 测试引用了不存在的路由（`/ontology/object-types/new`）、不存在的按钮文本、或者与实际 UI 不匹配的选择器。

**规则**：
- 写 E2E 测试前先读目标页面的 `page.tsx`，确认路由、元素、文本都存在
- 用 `page.getByRole()` 优于 `page.getByText()`（避免 sidebar 文本冲突）
- 用 API 创建测试数据比依赖 UI 表单更稳定
- `toBeVisible` 必须带 `timeout: 10000+`，页面有异步加载

---

## E2E 测试覆盖

**测试总量**：174 个 Playwright E2E 测试 + 10 个 BrowserUse 测试

### docker-e2e.spec.ts — 33 个基础验证

| 类别 | 测试项 |
|------|--------|
| 登录流程 | 登录页渲染、真实登录跳转 |
| Ontology 模块 | overview / object-types / link-types / interface-types / action-types / shared-property-types / versions |
| Data 模块 | overview / sources / browse |
| Function 模块 | overview / capabilities |
| Agent 模块 | overview / chat / models / skills / mcp / sessions / sub-agents / monitor |
| Setting 模块 | overview / users / tenants / audit |
| 数据渲染验证 | users 表显示 admin 用户、tenants 表显示 Default 租户、overview 用户计数 > 0 |
| API 健康 | /health 端点、认证 API 调用 |
| 导航 | Dock 模块间导航 |
| 控制台错误 | 无关键 JS 错误 |

### journeys/ — 22 个用户旅程（J01-J22），共 78 个测试

| Journey | 场景 | 测试数 |
|---------|------|--------|
| J01-J03 | Ontology CRUD / 版本生命周期 / 删除 | 11 |
| J04-J07 | 数据源 / Action 执行 / Copilot / Shell | 10 |
| J08-J15 | 用户管理 / 拓扑 / 资产映射 / 工作流 / 回滚 / RBAC / 搜索 / 导航 | 32 |
| J16-J22 | 图表渲染 / 空状态 / MCP / 多模型 / Sub-Agent / 能力总览 / 完整建模 | 25 |

### BrowserUse — 10 个有头浏览器场景（BU-01 to BU-10）

| 场景 | 验证内容 |
|------|---------|
| BU-01~02 | 登录流程 / ObjectType 创建 |
| BU-03~05 | 版本管理 / 数据源 / 数据浏览 |
| BU-06~07 | Copilot 对话 / Shell 面板 |
| BU-08~10 | 用户管理 / 跨模块导航 / 拓扑可视化 |
