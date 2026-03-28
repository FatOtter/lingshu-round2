# IMPLEMENTATION_PLAN.md - LingShu 分阶段实施计划

> **版本**: 1.0.0
> **创建日期**: 2026-03-11
> **状态**: 待确认
> **基于**: `TECHNICAL_DESIGN.md`、各模块设计文档

---

## 总览

### 阶段划分原则

1. **依赖驱动**：每个阶段的前置依赖在前序阶段完成
2. **闭环交付**：每个阶段交付可运行、可验证的最小闭环
3. **前后端并行**：后端 API 和前端 UI 在同一阶段内并行开发
4. **TDD 强制**：每个原子任务包含测试编写，覆盖率 ≥ 80%

### 能力域依赖链

```
Phase 0: 项目脚手架 + 基础设施
    ↓
Phase 1: Setting P0（认证 + 用户 + 审计）
    ↓
Phase 2: Ontology P0（核心 CRUD + 图存储 + 版本基础）
    ↓
Phase 3: Data P0（数据源连接 + 只读查询管道）
    ↓
Phase 4: Function P0（Action 执行 + Global Function + 能力清单）
    ↓
Phase 5: Copilot P0（Agent + A2UI + 对话 + 会话管理）
    ↓
Phase 6: 前端基础（布局框架 + 路由 + 认证 + 通用组件）
    ↓
Phase 7: 前端各模块 P0 页面
    ↓
Phase 8+: P1/P2/P3 功能迭代
```

### 标记说明

- `[BE]` 后端任务
- `[FE]` 前端任务
- `[INFRA]` 基础设施任务
- `[TEST]` 测试任务
- `[DOC]` 文档任务

---

## Phase 0: 项目脚手架与基础设施

> **目标**: 项目可启动、可开发、CI 可运行
> **前置依赖**: 无
> **交付物**: 空项目骨架 + Docker 本地环境 + CI 流水线

### 0.1 后端项目初始化

- [x] `[BE]` 创建 `backend/` 目录，初始化 `pyproject.toml`（uv 项目，Python 3.12+）
- [x] `[BE]` 配置依赖：fastapi, uvicorn, pydantic, sqlalchemy[asyncio], asyncpg, neo4j, redis, authlib, passlib[bcrypt], casbin, httpx, pytest, pytest-asyncio, pytest-cov, ruff, mypy
- [x] `[BE]` 创建 `backend/src/lingshu/__init__.py` 和基础包结构
- [x] `[BE]` 创建 `backend/src/lingshu/main.py`（FastAPI app 入口，含健康检查 `/health`）
- [x] `[BE]` 创建 `backend/src/lingshu/config.py`（Pydantic Settings，从环境变量读取配置）
- [x] `[BE]` 配置 Ruff（`ruff.toml`）和 mypy（`mypy.ini`）
- [x] `[BE]` 创建 `backend/tests/conftest.py`（共享 fixtures 框架）
- [x] `[TEST]` 编写健康检查端点的单元测试

### 0.2 基础设施层

- [x] `[BE]` 创建 `backend/src/lingshu/infra/database.py`（PostgreSQL 异步连接池，SQLAlchemy async engine + session factory）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/graph_db.py`（Neo4j 异步驱动连接管理）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/redis.py`（Redis 连接管理）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/context.py`（ContextVar：user_id, tenant_id, role, request_id）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/errors.py`（统一异常类 + FastAPI 异常处理器 + 错误码枚举）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/rid.py`（RID 生成 `ri.{type}.{uuid}` + 校验）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/logging.py`（结构化日志配置）
- [x] `[BE]` 创建 `backend/src/lingshu/infra/models.py`（通用 DTO：Filter, SortSpec, Pagination, PagedResponse）
- [x] `[TEST]` 编写 RID 生成/校验、ContextVar、错误处理的单元测试

### 0.3 数据库迁移

- [x] `[BE]` 初始化 Alembic（`backend/alembic/`）
- [x] `[BE]` 配置 `alembic/env.py`（异步引擎，读取 config.py 的数据库 URL）
- [x] `[BE]` 创建初始迁移脚本（空数据库基线）

### 0.4 Docker 本地开发环境

- [x] `[INFRA]` 创建 `docker/docker-compose.yml`（PostgreSQL 16 + Neo4j Community + Redis 7）
- [x] `[INFRA]` 创建 `docker/docker-compose.test.yml`（测试环境，隔离端口）
- [x] `[INFRA]` 创建 `.env.example`（所有环境变量模板）
- [x] `[INFRA]` 创建 `Makefile`（常用命令：`make dev`, `make test`, `make lint`, `make migrate`）

### 0.5 前端项目初始化

- [x] `[FE]` 创建 `frontend/` 目录，`pnpm create next-app`（Next.js 15, App Router, TypeScript）
- [x] `[FE]` 配置 Tailwind CSS 4.x + `tailwind.config.ts`
- [x] `[FE]` 初始化 Shadcn/UI（`components.json`）
- [x] `[FE]` 配置 `tsconfig.json`（路径别名 `@/`）
- [x] `[FE]` 安装核心依赖：@tanstack/react-query, zustand, zod, react-flow, @monaco-editor/react
- [x] `[FE]` 配置 Vitest + Testing Library + Playwright
- [x] `[FE]` 创建 `frontend/src/lib/api/client.ts`（基础 HTTP 客户端，fetch wrapper，自动错误处理）
- [x] `[TEST]` 编写 API 客户端的单元测试

### 0.6 CI/CD

- [x] `[INFRA]` 创建 `.github/workflows/ci.yml`（后端：ruff + mypy + pytest；前端：tsc + vitest）
- [x] `[INFRA]` 创建 `.gitignore`（Python + Node.js + IDE + .env）

---

## Phase 1: Setting 模块 P0

> **目标**: 认证闭环 — 用户可登录/登出，JWT 鉴权，审计日志可写入和查询
> **前置依赖**: Phase 0
> **交付物**: Auth Middleware + 用户 CRUD + 审计日志 + Seed 初始化
> **参考文档**: `SETTING_DESIGN.md` §2

### 1.1 数据库表

- [x] `[BE]` Alembic 迁移：创建 `users` 表
- [x] `[BE]` Alembic 迁移：创建 `tenants` 表
- [x] `[BE]` Alembic 迁移：创建 `user_tenant_memberships` 表
- [x] `[BE]` Alembic 迁移：创建 `refresh_tokens` 表
- [x] `[BE]` Alembic 迁移：创建 `audit_logs` 表（含 4 组索引）

### 1.2 Repository 层

- [x] `[BE]` 创建 `setting/repository/user_repo.py`（CRUD + email 唯一性检查 + tenant_id 过滤）
- [x] `[BE]` 创建 `setting/repository/tenant_repo.py`（CRUD + tenant_id 过滤）
- [x] `[BE]` 创建 `setting/repository/membership_repo.py`（成员关系 CRUD + 角色查询）
- [x] `[BE]` 创建 `setting/repository/refresh_token_repo.py`（创建 + 撤销 + 过期清理）
- [x] `[BE]` 创建 `setting/repository/audit_log_repo.py`（只读查询 + 多条件筛选 + 分页）
- [x] `[TEST]` 编写所有 Repository 的集成测试（testcontainers PostgreSQL）

### 1.3 认证核心

- [x] `[BE]` 创建 `setting/auth/password.py`（bcrypt cost=12，hash + verify）
- [x] `[BE]` 创建 `setting/auth/provider.py`（IdentityProvider Protocol + BuiltinProvider：JWT 签发/校验/刷新/撤销，authlib）
- [x] `[BE]` 创建 `setting/auth/middleware.py`（Auth Middleware：Cookie 提取 → JWT 校验 → ContextVar 写入 → 路径白名单 → 开发降级模式）
- [x] `[TEST]` 编写密码哈希的单元测试
- [x] `[TEST]` 编写 JWT 签发/校验/过期的单元测试
- [x] `[TEST]` 编写 Auth Middleware 的单元测试（正常、过期、黑名单、白名单、开发模式）

### 1.4 权限框架

- [x] `[BE]` 创建 `setting/authz/model.conf`（P0: allow-all matcher）
- [x] `[BE]` 创建 `setting/authz/enforcer.py`（Casbin Enforcer 封装，`check_permission` 实现）
- [x] `[BE]` 创建 `setting/authz/adapter.py`（Casbin PostgreSQL Adapter 配置）
- [x] `[TEST]` 编写 Casbin allow-all 模式的单元测试

### 1.5 Service 层

- [x] `[BE]` 创建 `setting/interface.py`（SettingService Protocol：get_current_user, check_permission, write_audit_log）
- [x] `[BE]` 创建 `setting/schemas/requests.py`（LoginRequest, CreateUserRequest, QueryAuditLogRequest 等）
- [x] `[BE]` 创建 `setting/schemas/responses.py`（UserResponse, TenantResponse, AuditLogResponse 等）
- [x] `[BE]` 创建 `setting/service.py`（SettingServiceImpl：实现 Protocol 接口 + 业务逻辑）
- [x] `[TEST]` 编写 SettingService 业务逻辑的单元测试

### 1.6 Router 层

- [x] `[BE]` 创建 `setting/router.py`：Auth API（login, logout, refresh, me, change-password）
- [x] `[BE]` 扩展 `setting/router.py`：User API（CRUD + query + reset-password）
- [x] `[BE]` 扩展 `setting/router.py`：Audit API（query + get detail）
- [x] `[BE]` 扩展 `setting/router.py`：Overview API
- [x] `[TEST]` 编写所有 API 端点的集成测试

### 1.7 Seed 初始化

- [x] `[BE]` 创建 `setting/seed.py`（首次启动检查 → 创建默认租户 + admin 用户）
- [x] `[BE]` 在 `main.py` 的 lifespan 中注册 seed 逻辑
- [x] `[TEST]` 编写 seed 逻辑的集成测试

### 1.8 模块注册

- [x] `[BE]` 在 `main.py` 中注册 Auth Middleware
- [x] `[BE]` 在 `main.py` 中注册 Setting Router（前缀 `/setting/v1/`）
- [x] `[BE]` 在 `main.py` 中组装依赖注入（SettingServiceImpl 实例化）

---

## Phase 2: Ontology 模块 P0

> **目标**: 核心 CRUD 闭环 — 5 种实体类型的增删改查 + 图存储 + Staging 摘要
> **前置依赖**: Phase 1（Auth Middleware）
> **交付物**: 实体 CRUD + Neo4j 图存储 + 编辑锁 + 版本基础
> **参考文档**: `ONTOLOGY_DESIGN.md` §2, `ONTOLOGY.md`

### 2.1 数据库表 + Neo4j 初始化

- [x] `[BE]` Alembic 迁移：创建 `snapshots` 表
- [x] `[BE]` Alembic 迁移：创建 `active_pointers` 表
- [x] `[BE]` 创建 `scripts/neo4j_init.py`（Neo4j 约束：RID 唯一性 + tenant_id 索引，每种节点类型）

### 2.2 Repository 层

- [x] `[BE]` 创建 `ontology/repository/graph_repo.py`：节点 CRUD（创建/读取/更新/删除 Neo4j 节点）
- [x] `[BE]` 扩展 `graph_repo.py`：版本状态查询（Active/Draft/Staging 节点过滤）
- [x] `[BE]` 扩展 `graph_repo.py`：关系边管理（BELONGS_TO, BASED_ON, IMPLEMENTS, EXTENDS, CONNECTS, REQUIRES, OPERATES_ON）
- [x] `[BE]` 扩展 `graph_repo.py`：拓扑查询（Topology API 数据）
- [x] `[BE]` 扩展 `graph_repo.py`：搜索查询（跨实体类型搜索 api_name/display_name/description）
- [x] `[BE]` 创建 `ontology/repository/snapshot_repo.py`（快照 CRUD + active_pointers 管理）
- [x] `[TEST]` 编写 graph_repo 的单元测试（Mock Neo4j driver）
- [x] `[TEST]` 编写 snapshot_repo 的集成测试

### 2.3 校验器

- [x] `[BE]` 创建 `ontology/validators/dependency.py`（删除前依赖检测：入度引用查询）
- [x] `[BE]` 创建 `ontology/validators/cascade.py`（SharedPropertyType → PropertyType 级联更新逻辑）
- [x] `[BE]` 创建 `ontology/validators/cycle_detection.py`（InterfaceType EXTENDS 循环检测 DFS）
- [x] `[TEST]` 编写每个校验器的单元测试

### 2.4 Service 层

- [x] `[BE]` 创建 `ontology/interface.py`（OntologyService Protocol）
- [x] `[BE]` 创建 `ontology/schemas/requests.py`（各实体类型的创建/更新/查询请求 DTO）
- [x] `[BE]` 创建 `ontology/schemas/responses.py`（各实体类型的响应 DTO + version_status）
- [x] `[BE]` 创建 `ontology/service.py`：ObjectType CRUD（create → Draft, update → Draft, delete → Draft 标记）
- [x] `[BE]` 扩展 `ontology/service.py`：LinkType CRUD
- [x] `[BE]` 扩展 `ontology/service.py`：SharedPropertyType CRUD
- [x] `[BE]` 扩展 `ontology/service.py`：InterfaceType CRUD（含契约校验）
- [x] `[BE]` 扩展 `ontology/service.py`：ActionType CRUD
- [x] `[BE]` 扩展 `ontology/service.py`：编辑锁管理（Redis SETNX + TTL 续期 + 释放）
- [x] `[BE]` 扩展 `ontology/service.py`：Draft → Staging 提交（冲突检测 + parent_snapshot_id 校验）
- [x] `[BE]` 扩展 `ontology/service.py`：Staging 摘要查询
- [x] `[BE]` 扩展 `ontology/service.py`：Draft 摘要查询 + 丢弃 Draft
- [x] `[BE]` 扩展 `ontology/service.py`：丢弃 Staging（单个 + 批量）
- [x] `[BE]` 扩展 `ontology/service.py`：发布流程（Staging → Snapshot → Active 切换 + 提交锁 + DataService 通知）
- [x] `[BE]` 扩展 `ontology/service.py`：回滚流程
- [x] `[BE]` 扩展 `ontology/service.py`：拓扑数据查询
- [x] `[BE]` 扩展 `ontology/service.py`：全局搜索
- [x] `[BE]` 扩展 `ontology/service.py`：关联实体查询（`/{type}/{rid}/related`）
- [x] `[TEST]` 编写 OntologyService 各操作的单元测试（Mock graph_repo）
- [x] `[TEST]` 编写版本管理流程的集成测试（Draft → Staging → Publish → Rollback）

### 2.5 Router 层

- [x] `[BE]` 创建 `ontology/router.py`：5 种实体类型的 CRUD 端点（query, get, get/draft, create, update, delete）
- [x] `[BE]` 扩展 `ontology/router.py`：编辑锁端点（lock, unlock, heartbeat）
- [x] `[BE]` 扩展 `ontology/router.py`：版本管理端点（submit-to-staging, staging/summary, staging/commit, staging/discard, drafts/summary）
- [x] `[BE]` 扩展 `ontology/router.py`：快照端点（snapshots/query, snapshots/{id}, snapshots/{id}/diff, snapshots/{id}/rollback）
- [x] `[BE]` 扩展 `ontology/router.py`：拓扑 + 搜索 + PropertyType 查询 + AssetMapping 查询 + 关联实体查询
- [x] `[TEST]` 编写所有 API 端点的集成测试

### 2.6 模块注册

- [x] `[BE]` 在 `main.py` 中注册 Ontology Router（前缀 `/ontology/v1/`）
- [x] `[BE]` 在 `main.py` 中组装 OntologyServiceImpl 依赖注入

---

## Phase 3: Data 模块 P0

> **目标**: 只读查询闭环 — 数据源连接管理 + Schema 驱动查询 + 脱敏
> **前置依赖**: Phase 2（OntologyService Protocol 可用）
> **交付物**: Connection CRUD + PostgreSQL Connector + 实例查询管道 + 脱敏
> **参考文档**: `DATA_DESIGN.md` §2

### 3.1 数据库表

- [x] `[BE]` Alembic 迁移：创建 `connections` 表

### 3.2 Repository 层

- [x] `[BE]` 创建 `data/repository/connection_repo.py`（CRUD + tenant_id 过滤）
- [x] `[TEST]` 编写 connection_repo 的集成测试

### 3.3 Connector 抽象层

- [x] `[BE]` 创建 `data/connectors/base.py`（Connector Protocol：execute_query, get_row, test_connection）
- [x] `[BE]` 创建 `data/connectors/postgresql.py`（PostgreSQL Connector：SQL 生成 + 参数化查询 + 连接池）
- [x] `[TEST]` 编写 PostgreSQL Connector 的集成测试

### 3.4 读取管道

- [x] `[BE]` 创建 `data/pipeline/schema_loader.py`（从 OntologyService 获取类型定义 → PropertyType 列表 + AssetMapping + ComplianceConfig → 进程内缓存 TTL 5min）
- [x] `[BE]` 创建 `data/pipeline/query_engine.py`（api_name → 物理列映射 → Filter/Sort/Pagination 翻译 → Connector 调用）
- [x] `[BE]` 创建 `data/pipeline/virtual_eval.py`（Virtual Expression 应用层计算：解析表达式 → 逐行计算虚拟字段）
- [x] `[BE]` 创建 `data/pipeline/masking.py`（脱敏管道：按 ComplianceConfig 处理 → sortable/filterable 字段排除）
- [x] `[TEST]` 编写 schema_loader 的单元测试（Mock OntologyService）
- [x] `[TEST]` 编写 query_engine 的单元测试
- [x] `[TEST]` 编写 virtual_eval 的单元测试
- [x] `[TEST]` 编写 masking 的单元测试

### 3.5 Service 层

- [x] `[BE]` 创建 `data/interface.py`（DataService Protocol：query_instances, get_instance, invalidate_schema_cache, on_schema_published）
- [x] `[BE]` 创建 `data/schemas/requests.py`（连接请求 + 实例查询请求 DTO）
- [x] `[BE]` 创建 `data/schemas/responses.py`（连接响应 + 实例查询响应 + schema 元数据 DTO）
- [x] `[BE]` 创建 `data/service.py`（DataServiceImpl：连接管理 + 实例查询管道编排）
- [x] `[TEST]` 编写 DataService 的单元测试

### 3.6 Router 层

- [x] `[BE]` 创建 `data/router.py`：Connection API（CRUD + test）
- [x] `[BE]` 扩展 `data/router.py`：实例查询 API（objects/{rid}/instances/query, objects/{rid}/instances/get, links/...）
- [x] `[BE]` 扩展 `data/router.py`：关系查询 API（objects/{rid}/instances/links, links/{rid}/instances/objects）
- [x] `[BE]` 扩展 `data/router.py`：Overview API
- [x] `[TEST]` 编写所有 API 端点的集成测试

### 3.7 模块注册

- [x] `[BE]` 在 `main.py` 中注册 Data Router（前缀 `/data/v1/`）
- [x] `[BE]` 在 `main.py` 中组装 DataServiceImpl 依赖注入

---

## Phase 4: Function 模块 P0

> **目标**: 执行闭环 — Action 加载 + 参数解析 + NativeCRUD 引擎 + 能力清单
> **前置依赖**: Phase 2（OntologyService）+ Phase 3（DataService）
> **交付物**: Action 执行 + 内置 Global Function + 能力清单 + 执行历史
> **参考文档**: `FUNCTION_DESIGN.md` §2

### 4.1 数据库表

- [x] `[BE]` Alembic 迁移：创建 `global_functions` 表
- [x] `[BE]` Alembic 迁移：创建 `workflows` 表
- [x] `[BE]` Alembic 迁移：创建 `executions` 表

### 4.2 Action 执行核心

- [x] `[BE]` 创建 `function/actions/loader.py`（从 OntologyService 获取 ActionType → 解析 execution config + outputs）
- [x] `[BE]` 创建 `function/actions/param_resolver.py`（参数解析：derived_from → DataService.get_instance，explicit → 类型校验，interface → 类型校验 + implements 检查）
- [x] `[BE]` 创建 `function/actions/engines/base.py`（Engine Protocol：execute → EngineResult）
- [x] `[BE]` 创建 `function/actions/engines/native_crud.py`（NativeCRUD 引擎：解析 field_mappings + 参数表达式 + $NOW/$USER）
- [x] `[TEST]` 编写 loader 的单元测试（Mock OntologyService）
- [x] `[TEST]` 编写 param_resolver 的单元测试（Mock DataService）
- [x] `[TEST]` 编写 NativeCRUD 引擎的单元测试

### 4.3 安全与审计

- [x] `[BE]` 创建 `function/safety/enforcer.py`（safety_level → 执行策略：直接执行 / pending_confirmation）
- [x] `[BE]` 创建 `function/audit/logger.py`（执行记录持久化 + SettingService.write_audit_log 调用）
- [x] `[TEST]` 编写安全策略的单元测试

### 4.4 Global Function

- [x] `[BE]` 创建 `function/globals/registry.py`（Global Function 注册表：CRUD + 版本管理）
- [x] `[BE]` 创建 `function/globals/builtins.py`（内置函数：query_instances, get_instance, list_object_types, list_link_types, get_object_type, get_link_type, get_related_links, get_related_objects）
- [x] `[BE]` 创建 `function/globals/executor.py`（Global Function 执行器：根据 implementation.type 分发）
- [x] `[TEST]` 编写内置函数的单元测试

### 4.5 Service 层

- [x] `[BE]` 创建 `function/interface.py`（FunctionService Protocol：list_capabilities, execute_action, execute_function, execute_workflow）
- [x] `[BE]` 创建 `function/schemas/requests.py`（执行请求 + 查询请求 DTO）
- [x] `[BE]` 创建 `function/schemas/responses.py`（执行响应 + 能力清单 DTO）
- [x] `[BE]` 创建 `function/service.py`（FunctionServiceImpl：能力清单聚合 + Action 执行管道编排 + Global Function 执行 + 确认/取消流程）
- [x] `[TEST]` 编写 FunctionService 的单元测试

### 4.6 Router 层

- [x] `[BE]` 创建 `function/router.py`：Action 执行 API（execute, validate, query, get detail）
- [x] `[BE]` 扩展 `function/router.py`：Global Function API（CRUD + execute）
- [x] `[BE]` 扩展 `function/router.py`：执行管理 API（get execution, query executions, confirm, cancel）
- [x] `[BE]` 扩展 `function/router.py`：能力清单 API + Overview API
- [x] `[TEST]` 编写所有 API 端点的集成测试

### 4.7 模块注册

- [x] `[BE]` 在 `main.py` 中注册 Function Router（前缀 `/function/v1/`）
- [x] `[BE]` 在 `main.py` 中组装 FunctionServiceImpl 依赖注入

---

## Phase 5: Copilot 模块 P0

> **目标**: 对话闭环 — 用户发消息 → Agent 调用能力 → 流式返回结果
> **前置依赖**: Phase 4（FunctionService）
> **交付物**: LangGraph Agent + A2UI 协议 + SSE 流式 + 会话管理 + 基座模型管理
> **参考文档**: `COPILOT_DESIGN.md` §2

### 5.1 数据库表

- [x] `[BE]` Alembic 迁移：创建 `sessions` 表
- [x] `[BE]` Alembic 迁移：创建 `models` 表
- [x] `[BE]` Alembic 迁移：创建 `skills` 表
- [x] `[BE]` Alembic 迁移：创建 `mcp_connections` 表
- [x] `[BE]` Alembic 迁移：创建 `sub_agents` 表
- [x] `[BE]` 初始化 AsyncPostgresSaver（LangGraph checkpoint 表）

### 5.2 Agent 核心

- [x] `[BE]` 创建 `copilot/agent/state.py`（CopilotState：MessagesState 扩展 + SessionContext + summary）
- [x] `[BE]` 创建 `copilot/agent/context.py`（SessionContext 定义 + 上下文更新逻辑）
- [x] `[BE]` 创建 `copilot/agent/prompts.py`（系统提示词模板：Shell 模式 + Agent 模式 + 上下文注入）
- [x] `[BE]` 创建 `copilot/agent/tools.py`（FunctionService 能力 → LangGraph Tool 转换：make_capability_tool + interrupt 逻辑）
- [x] `[BE]` 创建 `copilot/agent/graph.py`（StateGraph 构建：router → supervisor ↔ tools → respond + AsyncPostgresSaver checkpointer）
- [x] `[TEST]` 编写 Tool 绑定的单元测试（Mock FunctionService）
- [x] `[TEST]` 编写 Agent Graph 的集成测试

### 5.3 A2UI 协议

- [x] `[BE]` 创建 `copilot/a2ui/protocol.py`（SSE 事件类型定义：text_delta, component, tool_start, tool_end, thinking, interrupt, error, done）
- [x] `[BE]` 创建 `copilot/a2ui/components.py`（A2UI 组件 schema：Table, MetricCard, ConfirmationCard）
- [x] `[BE]` 创建 `copilot/a2ui/renderer.py`（Agent stream → SSE 事件流转换：messages mode → text_delta, custom mode → component/tool events）
- [x] `[TEST]` 编写 A2UI 组件 schema 校验的单元测试
- [x] `[TEST]` 编写 SSE renderer 的单元测试

### 5.4 会话管理

- [x] `[BE]` 创建 `copilot/sessions/repository.py`（sessions 表 CRUD + tenant_id 过滤）
- [x] `[BE]` 创建 `copilot/sessions/manager.py`（会话创建 → thread_id 映射 + 会话恢复 → checkpoint 加载 + 历史消息提取）
- [x] `[TEST]` 编写会话管理的单元测试

### 5.5 基础设施管理

- [x] `[BE]` 创建 `copilot/infra/models.py`（基座模型 CRUD + 默认模型管理 + 连接测试）
- [x] `[TEST]` 编写模型管理的单元测试

### 5.6 Service + Router 层

- [x] `[BE]` 创建 `copilot/service.py`（CopilotServiceImpl：消息处理 → graph.astream + SSE 输出 + resume 处理 + 上下文更新）
- [x] `[BE]` 创建 `copilot/router.py`：对话 API（create session, send message/SSE, resume, update context, get session, query sessions, delete session）
- [x] `[BE]` 扩展 `copilot/router.py`：基座模型 API（CRUD）
- [x] `[TEST]` 编写对话 API 的集成测试（SSE 流验证）

### 5.7 模块注册

- [x] `[BE]` 在 `main.py` 中注册 Copilot Router（前缀 `/copilot/v1/`）
- [x] `[BE]` 在 `main.py` 中组装 CopilotServiceImpl 依赖注入

---

## Phase 6: 前端基础框架

> **目标**: 前端可运行 — 布局框架 + 路由 + 认证 + 通用组件就绪
> **前置依赖**: Phase 1（Setting API 可用）
> **交付物**: 三栏布局 + 登录页 + 认证拦截 + Shadcn/UI 基础组件
> **说明**: Phase 6 可与 Phase 2-5 并行开发

### 6.1 认证

- [x] `[FE]` 创建 `src/lib/api/setting.ts`（Setting API 客户端：login, logout, refresh, me）
- [x] `[FE]` 创建 `src/hooks/use-auth.ts`（认证 Hook：登录状态管理 + Token 自动刷新 + 未认证重定向）
- [x] `[FE]` 创建 `src/app/login/page.tsx`（登录页：邮箱+密码表单 + 错误提示 + 重定向）
- [x] `[TEST]` 编写认证 Hook 的单元测试

### 6.2 布局框架

- [x] `[FE]` 创建 `src/app/layout.tsx`（根布局：TanStack QueryProvider + 全局样式）
- [x] `[FE]` 创建 `src/app/(authenticated)/layout.tsx`（认证路由组：三栏布局 Dock + Main Stage + Shell）
- [x] `[FE]` 创建 `src/components/layout/dock.tsx`（Dock 导航栏：5 个模块图标 + 当前模块高亮）
- [x] `[FE]` 创建 `src/components/layout/header.tsx`（Global Header：Logo + 租户切换 + 用户头像下拉菜单）
- [x] `[FE]` 创建 `src/components/layout/sidebar.tsx`（通用侧边面板：接受导航项配置）
- [x] `[FE]` 创建 `src/components/layout/shell.tsx`（Copilot Shell 面板：展开/收起 + 宽度调整）
- [x] `[TEST]` 编写布局组件的单元测试

### 6.3 客户端状态

- [x] `[FE]` 创建 `src/stores/shell-store.ts`（Zustand：Shell 开关 + 宽度状态）
- [x] `[FE]` 创建 `src/stores/tab-store.ts`（Zustand：Tab 管理 + LRU 策略 + 未保存标记 + LocalStorage 持久化）
- [x] `[FE]` 创建 `src/hooks/use-tab-manager.ts`（Tab 管理 Hook：打开/关闭/激活/复用逻辑）

### 6.4 通用组件

- [x] `[FE]` 安装 Shadcn/UI 基础组件：Button, Input, Select, Dialog, Sheet, Table, Form, Card, Badge, Tabs, Tooltip, DropdownMenu, Command, Separator, ScrollArea
- [x] `[FE]` 创建 `src/components/ui/data-table.tsx`（通用数据表格：排序 + 筛选 + 分页 + 动态列）
- [x] `[FE]` 创建 `src/components/ui/query-filter.tsx`（通用筛选组件：与 Filter DTO 对齐）
- [x] `[FE]` 创建 `src/components/ui/confirm-dialog.tsx`（确认对话框）
- [x] `[FE]` 创建 `src/components/ui/loading.tsx`（加载状态组件）
- [x] `[FE]` 创建 `src/components/ui/error-boundary.tsx`（错误边界组件）

### 6.5 TypeScript 类型

- [x] `[FE]` 创建 `src/types/setting.ts`（User, Tenant, AuditLog 类型）
- [x] `[FE]` 创建 `src/types/ontology.ts`（ObjectType, LinkType, InterfaceType, ActionType, SharedPropertyType 类型）
- [x] `[FE]` 创建 `src/types/data.ts`（Connection, Instance, QueryResult 类型）
- [x] `[FE]` 创建 `src/types/function.ts`（Capability, Execution, Workflow 类型）
- [x] `[FE]` 创建 `src/types/copilot.ts`（Session, A2UIEvent, Model 类型）
- [x] `[FE]` 创建 `src/types/a2ui.ts`（A2UI 组件类型：Table, MetricCard, ConfirmationCard, Chart, EntityCard, Form）

### 6.6 API 客户端

- [x] `[FE]` 创建 `src/lib/api/ontology.ts`（Ontology API 客户端）
- [x] `[FE]` 创建 `src/lib/api/data.ts`（Data API 客户端）
- [x] `[FE]` 创建 `src/lib/api/function.ts`（Function API 客户端）
- [x] `[FE]` 创建 `src/lib/api/copilot.ts`（Copilot API 客户端）
- [x] `[FE]` 创建 `src/lib/sse.ts`（SSE 客户端：连接管理 + 自动重连 + 事件解析）

---

## Phase 7: 前端各模块 P0 页面

> **目标**: 各模块核心页面可用
> **前置依赖**: Phase 6（前端框架）+ Phase 2-5（后端 API）
> **交付物**: 5 个模块的核心页面

### 7.1 Setting 模块前端

- [x] `[FE]` 创建 `src/app/(authenticated)/setting/layout.tsx`（侧边面板：概览/用户/审计/租户）
- [x] `[FE]` 创建 `setting/overview/page.tsx`（概览页：统计卡片 + 最近审计）
- [x] `[FE]` 创建 `setting/users/page.tsx`（用户列表：表格 + 新建按钮 + 状态切换）
- [x] `[FE]` 创建 `setting/users/[rid]/page.tsx`（用户详情/编辑页）
- [x] `[FE]` 创建 `setting/audit/page.tsx`（审计日志：筛选 + 表格 + 跨模块跳转）
- [x] `[FE]` 创建 Header 用户头像下拉菜单对接（me + 修改密码 + 登出）
- [x] `[TEST]` 编写 Setting 模块页面的 E2E 测试（登录→用户管理流程）

### 7.2 Ontology 模块前端

- [x] `[FE]` 创建 `src/app/(authenticated)/ontology/layout.tsx`（侧边面板：9 分区 + 关联实体抽屉）
- [x] `[FE]` 创建 `src/components/ontology/tab-container.tsx`（多 Tab 编辑器容器 + Tab 管理逻辑）
- [x] `[FE]` 创建 `ontology/overview/page.tsx`（概览拓扑图：React Flow + Topology API）
- [x] `[FE]` 创建 `ontology/object-types/page.tsx`（ObjectType 列表页）
- [x] `[FE]` 创建 `ontology/object-types/[rid]/page.tsx`（ObjectType 编辑器：基本信息 + 属性 + 接口 + 数据映射 + 校验规则）
- [x] `[FE]` 创建 `ontology/link-types/page.tsx` + `[rid]/page.tsx`（LinkType 列表 + 编辑器）
- [x] `[FE]` 创建 `ontology/interface-types/page.tsx` + `[rid]/page.tsx`（InterfaceType 列表 + 编辑器）
- [x] `[FE]` 创建 `ontology/action-types/page.tsx` + `[rid]/page.tsx`（ActionType 列表 + 编辑器，含 Monaco Editor）
- [x] `[FE]` 创建 `ontology/shared-property-types/page.tsx` + `[rid]/page.tsx`（SharedPropertyType 列表 + 编辑器）
- [x] `[FE]` 创建 `ontology/properties/page.tsx`（PropertyType 只读索引页）
- [x] `[FE]` 创建 `ontology/asset-mappings/page.tsx`（AssetMapping 只读索引页）
- [x] `[FE]` 创建 `ontology/versions/page.tsx`（版本管理页：Staging 摘要 + 发布对话框 + Snapshot 历史 + Diff 对比 + 回滚）
- [x] `[FE]` 实现查看/编辑模式切换逻辑（编辑锁获取 → Draft 加载 → 保存 → 提交 → 释放锁）
- [x] `[TEST]` 编写 Ontology 模块的 E2E 测试（创建 ObjectType → 编辑 → 提交 → 发布流程）

### 7.3 Data 模块前端

- [x] `[FE]` 创建 `src/app/(authenticated)/data/layout.tsx`（侧边面板：概览/数据源/数据浏览/数据版本）
- [x] `[FE]` 创建 `data/overview/page.tsx`（概览页：数据源状态 + 类型统计）
- [x] `[FE]` 创建 `data/sources/page.tsx`（数据源列表 + 新建表单 + 连接测试）
- [x] `[FE]` 创建 `data/sources/[rid]/page.tsx`（数据源详情/编辑）
- [x] `[FE]` 创建 `data/browse/page.tsx`（类型选择页：ObjectType/LinkType 卡片列表）
- [x] `[FE]` 创建 `data/browse/[typeKind]/[typeRid]/page.tsx`（实例列表：动态列 + WidgetConfig 渲染 + 筛选 + 排序 + 分页 + 脱敏字段禁用提示）
- [x] `[FE]` 创建实例详情组件（属性面板 + 关系面板 + 操作链接）
- [x] `[TEST]` 编写 Data 模块的 E2E 测试（创建数据源 → 浏览实例流程）

### 7.4 Function 模块前端

- [x] `[FE]` 创建 `src/app/(authenticated)/function/layout.tsx`（侧边面板：概览/原子能力/工作流）
- [x] `[FE]` 创建 `function/overview/page.tsx`（概览页：能力统计 + 最近执行）
- [x] `[FE]` 创建 `function/capabilities/page.tsx`（统一能力列表：Action + Global Function）
- [x] `[FE]` 创建 `function/capabilities/actions/[rid]/page.tsx`（Action 执行页：动态参数表单 + 安全级别提示 + 确认流程 + 执行历史）
- [x] `[FE]` 创建 `function/capabilities/globals/page.tsx`（Global Function 管理页：CRUD + 测试执行）
- [x] `[TEST]` 编写 Function 模块的 E2E 测试（执行 Action 流程）

### 7.5 Copilot 模块前端

- [x] `[FE]` 实现 Copilot Shell 面板对话功能（SSE 连接 + 消息流渲染 + 输入框）
- [x] `[FE]` 创建 `src/components/a2ui/renderer.tsx`（A2UI 组件分发器：根据 type 选择渲染组件）
- [x] `[FE]` 创建 `src/components/a2ui/table.tsx`（A2UI Table 组件）
- [x] `[FE]` 创建 `src/components/a2ui/metric-card.tsx`（A2UI MetricCard 组件）
- [x] `[FE]` 创建 `src/components/a2ui/confirmation-card.tsx`（A2UI ConfirmationCard 组件 + 确认/取消按钮）
- [x] `[FE]` 创建 `src/hooks/use-copilot.ts`（Copilot Hook：SSE 管理 + 消息状态 + A2UI 事件处理）
- [x] `[FE]` 创建 `src/app/(authenticated)/agent/layout.tsx`（侧边面板：对话/会话/基座模型/Skill/MCP/Sub-Agent/监控）
- [x] `[FE]` 创建 `agent/chat/page.tsx`（对话页：消息流 + A2UI 渲染 + 输入框）
- [x] `[FE]` 创建 `agent/chat/[sessionId]/page.tsx`（指定会话对话）
- [x] `[FE]` 创建 `agent/sessions/page.tsx`（会话管理列表）
- [x] `[FE]` 创建 `agent/models/page.tsx` + `[rid]/page.tsx`（基座模型管理）
- [x] `[TEST]` 编写 Copilot 模块的 E2E 测试（创建会话 → 发送消息 → 接收流式响应）

---

## Phase 8: P1 功能迭代

> **前置依赖**: Phase 7 全部完成
> **目标**: 权限管理 + 高级实体类型 + 扩展引擎 + Copilot Shell

### 8.1 Setting P1 — 权限与租户

- [x] `[BE]` 升级 Casbin model 为 RBAC（model_p1.conf + Seed Policy）
- [x] `[BE]` 实现租户 CRUD API
- [x] `[BE]` 实现租户切换 API（JWT 重签发）
- [x] `[BE]` 实现成员管理 API（添加/移除成员 + 修改角色）
- [x] `[FE]` 创建 `setting/tenants/page.tsx` + `[rid]/page.tsx`（租户管理页 + 成员管理）
- [x] `[FE]` 实现 Header 租户切换功能
- [x] `[TEST]` 编写 RBAC 权限的集成测试

### 8.2 Function P1 — 扩展引擎

- [x] `[BE]` 创建 `function/actions/engines/python_venv.py`（PythonVenv 引擎：subprocess 隔离 + 超时 + 白名单库）
- [x] `[BE]` 创建 `function/actions/engines/sql_runner.py`（SQLRunner 引擎：模板渲染 + 参数化查询 + Connector 执行）
- [x] `[BE]` 创建 `function/actions/engines/webhook.py`（Webhook 引擎：模板渲染 + httpx 请求 + 重试 + response_mapping）
- [x] `[BE]` 实现用户自定义 Global Function（Python + Webhook 类型）
- [x] `[TEST]` 编写每个引擎的单元测试和集成测试

### 8.3 Copilot P1 — Shell + 确认流程

- [x] `[BE]` 实现 Shell 模式的工具范围过滤（按 context.module 裁剪能力子集）
- [x] `[BE]` 实现 Human-in-the-loop 完整流程（interrupt → ConfirmationCard → resume）
- [x] `[FE]` 实现 Copilot Shell 页面上下文同步（PUT /sessions/{id}/context）
- [x] `[FE]` 创建 `src/components/a2ui/form.tsx`（A2UI Form 组件）
- [x] `[FE]` 创建 `src/components/a2ui/chart.tsx`（A2UI Chart 组件）
- [x] `[FE]` 创建 `src/components/a2ui/entity-card.tsx`（A2UI EntityCard 组件）
- [x] `[TEST]` 编写 Shell 模式的集成测试
- [x] `[TEST]` 编写确认流程的 E2E 测试

---

## Phase 9: P2 功能迭代

> **前置依赖**: Phase 8
> **目标**: 写回管道 + Skill/MCP 扩展 + 细粒度权限

### 9.1 Data P1 — Iceberg + Nessie

- [x] `[INFRA]` Docker Compose 添加 MinIO + Nessie
- [x] `[BE]` 创建 `data/connectors/iceberg.py`（Iceberg Connector：PyIceberg + Nessie Catalog）
- [x] `[BE]` 创建 `data/branch/nessie_client.py`（Nessie REST API 客户端）
- [x] `[BE]` 实现分支管理 API（list, create, delete, merge, diff）
- [x] `[FE]` 实现分支选择器（侧边面板底部 + 分支管理页）
- [x] `[FE]` 创建 `data/versions/page.tsx`（分支管理页）

### 9.2 Data P2 — 写回管道

- [x] `[INFRA]` Docker Compose 添加 FoundationDB
- [x] `[BE]` 创建 `data/writeback/fdb_client.py`（FDB 连接 + EditLog 读写 + 行级锁）
- [x] `[BE]` 创建 `data/writeback/lock.py`（FDB 行级锁管理）
- [x] `[BE]` 实现 DataService.write_editlog 方法
- [x] `[BE]` 实现读取时合并逻辑（`data/pipeline/merge.py`）
- [x] `[TEST]` 编写写回管道的集成测试

### 9.3 Function P2 — 写回 + 批量 + 异步

- [x] `[BE]` 实现 Action 写回流程（outputs → field_mappings → DataService.write_editlog）
- [x] `[BE]` 实现批量执行（is_batch = true）
- [x] `[BE]` 实现异步执行（is_sync = false）
- [x] `[TEST]` 编写写回 + 批量 + 异步的集成测试

### 9.4 Copilot P2 — Skill + MCP

- [x] `[BE]` 创建 `copilot/infra/skills.py`（Skill CRUD + tool_bindings 解析）
- [x] `[BE]` 创建 `copilot/infra/mcp.py`（MCP 连接管理 + Tool 发现 + MCP 协议转发）
- [x] `[BE]` 实现 Skill API + MCP API
- [x] `[BE]` 实现 Agent 工具加载策略（模式过滤 + Skill 聚焦 + 全量兜底）
- [x] `[FE]` 创建 `agent/skills/page.tsx` + `[rid]/page.tsx`（Skill 管理页）
- [x] `[FE]` 创建 `agent/mcp/page.tsx` + `[rid]/page.tsx`（MCP 管理页）
- [x] `[TEST]` 编写 Skill + MCP 的集成测试

### 9.5 Setting P2 — 细粒度权限

- [x] `[BE]` 升级 Casbin model 为 RBAC + 资源级（model_p2.conf）
- [x] `[BE]` 实现自定义角色管理 API
- [x] `[BE]` 审计日志保留策略（自动归档/清理）
- [x] `[TEST]` 编写资源级权限的集成测试

---

## Phase 10: P3 功能迭代

> **前置依赖**: Phase 9
> **目标**: 工作流 + Sub-Agent + OLAP + SSO

### 10.1 Function P3 — 工作流

- [x] `[BE]` 创建 `function/workflows/models.py`（工作流定义模型：节点 + 边 + 条件）
- [x] `[BE]` 创建 `function/workflows/engine.py`（工作流执行引擎：拓扑排序 + 顺序/并行执行 + 条件分支 + 暂停/恢复）
- [x] `[BE]` 创建 `function/workflows/repository.py`（工作流 CRUD + safety_level 自动计算）
- [x] `[BE]` 实现 Workflow API（CRUD + execute）
- [x] `[FE]` 创建 `function/workflows/page.tsx`（工作流列表）
- [x] `[FE]` 创建 `function/workflows/[rid]/page.tsx`（工作流编辑页：React Flow DAG 编辑器 + 参数映射 + 执行进度）
- [x] `[TEST]` 编写工作流引擎的单元测试和集成测试

### 10.2 Copilot P3 — Sub-Agent + 监控

- [x] `[BE]` 创建 `copilot/infra/subagents.py`（Sub-Agent CRUD + 动态加载为 Tool）
- [x] `[BE]` 实现 Sub-Agent API
- [x] `[BE]` 实现多智能体编排（主 Agent → Sub-Agent Tool 调用）
- [x] `[FE]` 创建 `agent/sub-agents/page.tsx` + `[rid]/page.tsx`（Sub-Agent 管理页）
- [x] `[FE]` 创建 `agent/monitor/page.tsx`（监控页：推理链可视化 + Token 使用量）
- [x] `[TEST]` 编写多智能体的集成测试

### 10.3 Data P3 — OLAP 热数据

- [x] `[INFRA]` Docker Compose 添加 Flink + Doris
- [x] `[BE]` 创建 `data/connectors/doris.py`（Doris Connector：MySQL 协议）
- [x] `[BE]` 实现 Flink CDC Job（FDB EditLog → Iceberg + Doris）
- [x] `[BE]` 实现 Doris 自动建表与 Schema 同步
- [x] `[BE]` 实现 Virtual Expression 物化列（Doris）
- [x] `[TEST]` 编写 OLAP 管道的集成测试

### 10.4 Setting P3 — SSO

- [x] `[BE]` 实现 External OIDC Provider（Keycloak/Ory Kratos 配置切换）
- [x] `[BE]` 实现 JIT Provisioning（SSO 首次登录 → 本地 users 自动创建）
- [x] `[FE]` 实现 SSO 登录跳转（OAuth2 Authorization Code Flow）
- [x] `[TEST]` 编写 SSO 集成测试

---

## 任务统计

| 阶段 | 任务数 | 核心产出 |
|------|--------|---------|
| Phase 0 | 26 | 项目脚手架 + Docker + CI |
| Phase 1 | 27 | 认证闭环 + 用户管理 + 审计日志 |
| Phase 2 | 28 | Ontology CRUD + 图存储 + 版本管理 |
| Phase 3 | 18 | 数据源连接 + 只读查询管道 |
| Phase 4 | 20 | Action 执行 + Global Function + 能力清单 |
| Phase 5 | 21 | LangGraph Agent + A2UI + 对话 |
| Phase 6 | 29 | 前端布局 + 认证 + 通用组件 |
| Phase 7 | 33 | 前端各模块核心页面 |
| Phase 8 | 18 | P1: 权限 + 扩展引擎 + Shell |
| Phase 9 | 20 | P2: 写回管道 + Skill/MCP |
| Phase 10 | 17 | P3: 工作流 + Sub-Agent + OLAP + SSO |
| **总计** | **257** | |

---

## 里程碑

| 里程碑 | 阶段 | 验收标准 |
|--------|------|---------|
| **M1: 后端 MVP** | Phase 0-5 完成 | 所有后端 API 可调用，Postman/curl 验证通过 |
| **M2: 全栈 MVP** | Phase 6-7 完成 | 用户可登录 → 创建 ObjectType → 浏览数据 → 执行 Action → 与 Copilot 对话 |
| **M3: 生产就绪 v1** | Phase 8 完成 | RBAC 权限 + 多引擎 + Copilot Shell，可交付内部测试 |
| **M4: 完整平台** | Phase 9-10 完成 | 数据写回 + 工作流 + MCP/Sub-Agent + SSO，可交付生产 |

---
