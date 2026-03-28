# SETTING_DESIGN.md - 设置模块设计

> **版本**: 0.2.0
> **更新日期**: 2026-03-05
> **状态**: 草稿
> **前置文档**: `DESIGN.md`（能力域边界）、`TECH_DESIGN.md`（API/RID/错误规范）、`PRODUCT_DESIGN.md`（模块结构）

---

## 1. 模块定位

设置模块是系统管理的横切关注点实现，覆盖后端服务和前端交互。

**职责**：
- 认证（AuthN）：用户登录、登出、Token 刷新、密码管理
- 用户管理：用户 CRUD、状态管理（启用/停用）
- 审计日志聚合查询：跨模块审计日志的统一查询入口
- 租户管理：租户 CRUD、成员关系管理、租户切换

**不负责**：
- 数据源连接管理（Data 模块的职责）
- 各模块的业务授权逻辑（各模块内部判断）
- 审计日志写入（各模块通过 `write_audit_log` 工具自行写入，Setting 只提供查询）
- 行级数据权限（延后实现）

---

## 2. 后端服务设计

### 2.1 服务层架构

```
setting/
├── router.py                # FastAPI 路由定义
├── service.py               # 业务逻辑（SettingServiceImpl）
├── interface.py             # Protocol 接口（供其他能力域调用）
├── auth/
│   ├── provider.py          # Identity Provider 抽象 + 内置实现（authlib JWT 签发/校验）
│   ├── middleware.py         # Auth Middleware（Cookie 提取 → JWT 校验 → ContextVar）
│   └── password.py          # 密码哈希与校验（passlib + bcrypt）
├── authz/
│   ├── enforcer.py          # Casbin Enforcer 封装（check_permission 实现）
│   ├── model.conf           # Casbin 权限模型定义（P0: ACL, P1: RBAC, P2: RBAC+资源级）
│   └── adapter.py           # Casbin PostgreSQL Adapter（Policy 持久化）
├── repository/
│   ├── user_repo.py         # 用户 Repository（PostgreSQL）
│   ├── tenant_repo.py       # 租户 Repository（PostgreSQL）
│   ├── membership_repo.py   # 用户-租户成员关系 Repository
│   ├── refresh_token_repo.py # Refresh Token Repository
│   └── audit_log_repo.py    # 审计日志 Repository（只读查询）
├── schemas/
│   ├── requests.py          # 请求 DTO
│   └── responses.py         # 响应 DTO
└── seed.py                  # 首次启动数据初始化
```

**核心依赖库**：

| 库 | 用途 | 说明 |
|----|------|------|
| `authlib` | JWT 签发/校验、OIDC 协议 | OIDC-compatible，P3 接 SSO 时只需切换 Identity Provider |
| `passlib[bcrypt]` | 密码哈希 | FastAPI 生态标准，支持多种哈希算法，内置 bcrypt |
| `casbin` | RBAC / ABAC 权限判断 | 权限模型与代码解耦，策略变更不需改代码 |
| `casbin-sqlalchemy-adapter` | Casbin Policy 持久化 | Policy 存 PostgreSQL，多实例一致 |

**关键约束**：
- Auth Middleware 在所有 API 路由前执行（登录和健康检查除外）
- 所有查询自动附加 `tenant_id` 过滤
- 密码不以明文存储，不在任何响应中返回

**SettingService Protocol 接口**（供其他能力域调用）：

```python
# setting/interface.py
class SettingService(Protocol):
    def get_current_user(self) -> UserInfo:
        """从当前请求上下文获取用户信息"""
        ...

    def check_permission(
        self,
        user_id: str,
        resource_type: str,        # "object_type" / "connection" / "workflow" 等
        action: str,               # "create" / "read" / "update" / "delete" / "execute"
        resource_rid: str | None = None,
    ) -> bool:
        """
        检查用户是否有权执行指定操作。底层委托 Casbin Enforcer。
        P0：Casbin model 配置为 allow-all（永远返回 True）。
        P1：切换为 RBAC model，按角色判断。
        P2：切换为 RBAC + 资源级 model，支持 resource_rid 粒度。
        """
        ...

    def write_audit_log(
        self,
        event_type: str,           # "create" / "update" / "delete" / "execute" / "publish" 等
        resource_type: str,        # "object_type" / "connection" / "action" 等
        resource_rid: str | None = None,
        details: dict | None = None,
    ) -> None:
        """
        写入审计日志。自动从 ContextVar 获取 tenant_id、user_id、request_id。
        各能力域在关键操作后调用此方法。
        """
        ...
```

`get_current_user` 从 ContextVar 读取 Auth Middleware 写入的用户信息，不涉及数据库查询。

`write_audit_log` 是异步写入（fire-and-forget），不阻塞业务流程。`tenant_id`、`user_id`、`request_id` 从请求上下文自动注入，调用方无需传递。

### 2.2 认证设计

#### 2.2.1 设计原则：OIDC-Compatible

认证层按 **OIDC（OpenID Connect）协议** 设计接口，不自写 JWT 处理逻辑，使用 `authlib` 库。核心目标：P3 接入外部 SSO 时**只需切换 Identity Provider 配置，不改业务代码**。

```
┌─────────────────────────────────────────────────────┐
│                  Auth Middleware                      │
│  （从 Cookie 提取 JWT → 校验 → ContextVar）           │
└──────────────────────┬──────────────────────────────┘
                       │ 委托校验
                       ▼
         ┌─────────────────────────┐
         │   Identity Provider     │  ← 抽象接口
         │   (Protocol)            │
         ├─────────────────────────┤
         │ · issue_token()         │
         │ · validate_token()      │
         │ · refresh_token()       │
         │ · revoke_token()        │
         │ · get_jwks()            │
         └──────┬──────────────────┘
                │
    ┌───────────┼───────────────┐
    ▼                           ▼
┌──────────┐            ┌──────────────┐
│ Built-in │            │   External   │
│ Provider │            │   OIDC       │  ← P3 阶段
│ (authlib)│            │ (Keycloak /  │
│          │            │  Ory Kratos) │
└──────────┘            └──────────────┘
```

**P0-P2：Built-in Provider**（内置实现）：
- 使用 `authlib` 签发和校验 JWT（OIDC-compatible claims）
- 用户凭证存储在本地 PostgreSQL（users 表）
- 密码哈希使用 `passlib`（bcrypt，cost 12）

**P3：External OIDC Provider**（外部身份源）：
- 部署 Keycloak / Ory Kratos 等外部 IdP
- 配置 `LINGSHU_AUTH_OIDC_ISSUER_URL` 指向外部 IdP
- Auth Middleware 切换为校验外部 JWT（仅改配置，不改代码）
- 用户首次通过 SSO 登录时，自动在本地 users 表创建对应记录（JIT Provisioning）

#### 2.2.2 Token 方案

采用 JWT + HttpOnly Cookie：

| Token | 存储位置 | TTL | 用途 |
|-------|---------|-----|------|
| Access Token | HttpOnly Cookie (`lingshu_access`) | 15 分钟 | 请求认证 |
| Refresh Token | HttpOnly Cookie (`lingshu_refresh`) | 7 天 | 刷新 Access Token |

**选择 Cookie 而非 Header 的理由**：
- HttpOnly Cookie 防 XSS（JavaScript 无法读取）
- 浏览器自动携带，SSE 流式连接无需额外处理（Copilot A2UI 依赖 SSE）
- CSRF 通过 SameSite=Lax + 自定义 Header（`X-Requested-With`）双重防护

#### 2.2.3 JWT Payload（OIDC 标准 Claims）

```json
{
  "iss": "https://lingshu.example.com",
  "sub": "ri.user.{uuid}",
  "aud": "lingshu",
  "tid": "ri.tenant.{uuid}",
  "role": "admin",
  "jti": "{uuid}",
  "iat": 1709500000,
  "exp": 1709500900
}
```

| Claim | 说明 | OIDC 标准 |
|-------|------|----------|
| `iss` | 签发者（内置 Provider 为本服务 URL，外部 SSO 为 IdP URL） | 标准 |
| `sub` | 用户 RID | 标准 |
| `aud` | 受众（固定 `"lingshu"`） | 标准 |
| `tid` | 当前租户 RID | 自定义 |
| `role` | 用户在该租户中的角色 | 自定义 |
| `jti` | Token 唯一标识（用于黑名单） | 标准 |

Auth Middleware 校验时检查 `iss` 和 `aud`，确保 Token 来源合法。切换到外部 SSO 后，`iss` 变为外部 IdP 的 URL，Middleware 自动适配。

#### 2.2.4 Auth Middleware

```
请求进入
  ↓
路径白名单检查：/setting/v1/auth/login、/health → 跳过认证
  ↓
从 Cookie 提取 Access Token
  ↓
Cookie 不存在？→ 检查 X-User-ID + X-Tenant-ID Header（开发降级）
  ↓
委托 Identity Provider 校验：签名（JWKS）+ iss + aud + 过期时间 + jti 不在黑名单
  ↓
校验通过 → 解析 payload → 写入 ContextVar（user_id, tenant_id, role, request_id）
  ↓
后续所有模块从 ContextVar 读取用户信息
```

**开发降级模式**：环境变量 `LINGSHU_AUTH_MODE=dev` 时，接受 `X-User-ID` + `X-Tenant-ID` Header 作为认证凭据，跳过 JWT 校验。仅限 development 环境使用。

#### 2.2.5 登出与 Token 撤销

登出时将当前 Access Token 的 `jti` 写入 Redis 黑名单，TTL 等于该 Token 的剩余有效期。同时撤销关联的 Refresh Token（数据库标记 `revoked_at`）。

```
Redis Key: {tenant_id}:jwt_blacklist:{jti}
Redis Value: "1"
Redis TTL: Access Token 剩余有效秒数
```

### 2.3 API 设计

遵循 `TECH_DESIGN.md` 第 3 节的 API 规范。URL 前缀 `/setting/v1/`。

#### 2.3.1 Auth API

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/setting/v1/auth/login` | 登录（email + password） | 无需 |
| POST | `/setting/v1/auth/logout` | 登出（撤销 Token） | 需要 |
| POST | `/setting/v1/auth/refresh` | 刷新 Access Token | 仅需 Refresh Token |
| GET | `/setting/v1/auth/me` | 获取当前用户信息 | 需要 |
| POST | `/setting/v1/auth/change-password` | 修改密码 | 需要 |

**登录请求/响应**：

```json
POST /setting/v1/auth/login

{
  "email": "admin@example.com",
  "password": "********"
}

// 响应（200）— Token 通过 Set-Cookie 返回，Body 返回用户信息
{
  "data": {
    "user": {
      "rid": "ri.user.{uuid}",
      "email": "admin@example.com",
      "display_name": "Admin",
      "role": "admin",
      "tenant": {
        "rid": "ri.tenant.{uuid}",
        "display_name": "默认租户"
      }
    }
  }
}
```

**登录失败**（401）：统一返回 `SETTING_AUTH_INVALID_CREDENTIALS`，不区分"用户不存在"和"密码错误"（防止用户枚举）。

#### 2.3.2 User API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/setting/v1/users` | 创建用户 |
| POST | `/setting/v1/users/query` | 查询用户列表（筛选、排序、分页） |
| GET | `/setting/v1/users/{rid}` | 查询单个用户详情 |
| PUT | `/setting/v1/users/{rid}` | 更新用户信息 |
| DELETE | `/setting/v1/users/{rid}` | 停用用户（软删除，status → disabled） |
| POST | `/setting/v1/users/{rid}/reset-password` | 重置用户密码（管理员操作） |

**创建用户请求**：

```json
POST /setting/v1/users

{
  "email": "user@example.com",
  "display_name": "张三",
  "password": "initial_password",
  "role": "member"
}
```

创建用户时自动将其加入当前租户（从 ContextVar 获取 `tenant_id`）。

#### 2.3.3 Tenant API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/setting/v1/tenants` | 创建租户 |
| POST | `/setting/v1/tenants/query` | 查询租户列表 |
| GET | `/setting/v1/tenants/{rid}` | 查询租户详情 |
| PUT | `/setting/v1/tenants/{rid}` | 更新租户信息 |
| DELETE | `/setting/v1/tenants/{rid}` | 停用租户（软删除） |
| POST | `/setting/v1/tenants/switch` | 切换当前租户 |
| POST | `/setting/v1/tenants/{rid}/members/query` | 查询租户成员列表 |
| POST | `/setting/v1/tenants/{rid}/members` | 添加成员 |
| PUT | `/setting/v1/tenants/{rid}/members/{user_rid}` | 修改成员角色 |
| DELETE | `/setting/v1/tenants/{rid}/members/{user_rid}` | 移除成员 |

**租户切换请求/响应**：

```json
POST /setting/v1/tenants/switch

{
  "tenant_rid": "ri.tenant.{uuid}"
}

// 响应（200）— 签发新 JWT（tid 更新），通过 Set-Cookie 返回
{
  "data": {
    "tenant": {
      "rid": "ri.tenant.{uuid}",
      "display_name": "新租户"
    },
    "role": "member"
  }
}
```

切换租户前校验用户是否为该租户的成员。切换后签发新的 Access Token 和 Refresh Token（`tid` 和 `role` 更新）。

#### 2.3.4 Audit API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/setting/v1/audit-logs/query` | 查询审计日志（只读，跨模块统一查询） |
| GET | `/setting/v1/audit-logs/{log_id}` | 查询单条审计日志详情 |

**查询请求**：

```json
POST /setting/v1/audit-logs/query

{
  "filters": [
    { "field": "module", "operator": "eq", "value": "ontology" },
    { "field": "event_type", "operator": "in", "value": ["create", "update", "delete"] },
    { "field": "created_at", "operator": "gte", "value": "2026-03-01T00:00:00Z" }
  ],
  "sort": [
    { "field": "created_at", "order": "desc" }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50
  }
}
```

**查询响应**：

```json
{
  "data": [
    {
      "log_id": "audit_001",
      "module": "ontology",
      "event_type": "create",
      "resource_type": "object_type",
      "resource_rid": "ri.obj.{uuid}",
      "user_id": "ri.user.{uuid}",
      "user_display_name": "Admin",
      "action": "Created ObjectType 'Robot'",
      "details": { "api_name": "robot", "display_name": "机器人" },
      "request_id": "req_xxx",
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "pagination": { "total": 200, "page": 1, "page_size": 50, "has_next": true }
}
```

**可筛选字段**：`module`（ontology / data / function / copilot / setting）、`event_type`、`resource_type`、`user_id`、`created_at`（时间范围）。

#### 2.3.5 Overview API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/setting/v1/overview` | 设置模块全局概览 |

**响应**：

```json
{
  "data": {
    "users": {
      "total": 12,
      "by_status": { "active": 10, "disabled": 2 }
    },
    "tenants": {
      "total": 3
    },
    "recent_audit": [
      {
        "log_id": "audit_001",
        "module": "ontology",
        "event_type": "publish",
        "action": "Published Ontology v2.1",
        "user_display_name": "Admin",
        "created_at": "2026-03-01T10:00:00Z"
      }
    ]
  }
}
```

### 2.4 存储设计

#### 2.4.1 PostgreSQL

**users 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.user.{uuid}` |
| email | VARCHAR | 唯一，登录凭据 |
| display_name | VARCHAR | 显示名称 |
| password_hash | VARCHAR | bcrypt 哈希（cost 12） |
| status | VARCHAR | `active` / `disabled` |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

索引：`UNIQUE(email)`

**user_tenant_memberships 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| user_rid | VARCHAR | 外键 → users.rid |
| tenant_rid | VARCHAR | 外键 → tenants.rid |
| role | VARCHAR | `admin` / `member` / `viewer` |
| is_default | BOOLEAN | 用户登录时默认进入的租户 |
| created_at | TIMESTAMP | 加入时间 |

主键：`(user_rid, tenant_rid)`

**tenants 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.tenant.{uuid}` |
| display_name | VARCHAR | 租户名称 |
| status | VARCHAR | `active` / `disabled` |
| config | JSONB | 租户级配置（预留，如功能开关、限额） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**refresh_tokens 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| token_hash | VARCHAR | 主键，Refresh Token 的 SHA-256 哈希 |
| user_rid | VARCHAR | 外键 → users.rid |
| tenant_rid | VARCHAR | 外键 → tenants.rid |
| expires_at | TIMESTAMP | 过期时间 |
| revoked_at | TIMESTAMP | 撤销时间（NULL 表示有效） |
| created_at | TIMESTAMP | 创建时间 |

索引：`(user_rid, tenant_rid)`，用于登出时批量撤销

**audit_logs 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| log_id | BIGSERIAL | 主键，自增 |
| tenant_id | VARCHAR | 租户隔离 |
| module | VARCHAR | 来源模块（`ontology` / `data` / `function` / `copilot` / `setting`） |
| event_type | VARCHAR | 事件类型（`create` / `update` / `delete` / `execute` / `publish` / `login` / `logout`） |
| resource_type | VARCHAR | 资源类型（`object_type` / `connection` / `action` / `workflow` / `session` 等） |
| resource_rid | VARCHAR | 资源 RID（可为 NULL，如登录事件） |
| user_id | VARCHAR | 操作者用户 RID |
| action | VARCHAR | 操作描述（人类可读） |
| details | JSONB | 操作详情（变更前后的 diff、参数等） |
| request_id | VARCHAR | 请求追踪 ID |
| created_at | TIMESTAMP | 事件时间（DEFAULT NOW()） |

索引：
- `(tenant_id, created_at DESC)` — 默认按时间倒序查询
- `(tenant_id, module, created_at DESC)` — 按模块筛选
- `(tenant_id, user_id, created_at DESC)` — 按用户筛选
- `(tenant_id, resource_type, resource_rid)` — 按资源查询历史

**设计选择**：审计日志使用 `BIGSERIAL` 自增 ID 而非 RID，因为审计日志是追加写入（append-only）的时序数据，不需要跨系统引用，自增 ID 查询更高效。

#### 2.4.2 Redis

| Key 模式 | 用途 | TTL |
|---------|------|-----|
| `{tenant_id}:jwt_blacklist:{jti}` | Access Token 黑名单 | Token 剩余有效期 |

Redis 仅用于 JWT 黑名单。Refresh Token 的撤销通过 PostgreSQL 的 `revoked_at` 字段管理，无需 Redis。

### 2.5 权限模型（Casbin）

权限判断委托 **Casbin** 框架，权限模型（model）和策略（policy）与业务代码完全解耦。不同阶段只需切换 model 配置文件 + 调整 policy 数据，`check_permission` 的调用方式不变。

#### 2.5.1 Casbin 架构

```
check_permission(user_id, resource_type, action, resource_rid?)
  ↓
Casbin Enforcer.enforce(sub, obj, act)
  ↓
Model（model.conf）定义匹配规则
  ↓
Policy（PostgreSQL adapter）存储具体策略
  ↓
返回 allow / deny
```

**Model 与 Policy 分离的优势**：
- 权限模型升级（P0→P1→P2）只需替换 `model.conf`，不改代码
- Policy 存 PostgreSQL，多实例部署一致，支持运行时动态变更
- Casbin 经过广泛生产验证，避免自写权限逻辑的安全风险

#### 2.5.2 P0：Allow-All

```ini
# model_p0.conf — 所有已认证用户拥有全部权限
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = true
```

P0 阶段不写入任何 policy 数据，matcher 直接返回 `true`。效果等同于"不鉴权"。

#### 2.5.3 P1：三角色 RBAC

```ini
# model_p1.conf — 基于角色的访问控制
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

三个内置角色：

| 角色 | 说明 | 权限范围 |
|------|------|---------|
| `admin` | 管理员 | 所有操作 |
| `member` | 成员 | 读写操作，不可管理用户/租户 |
| `viewer` | 观察者 | 只读操作 |

**Seed Policy**（系统启动时写入 PostgreSQL）：

```csv
# p, role, resource_type, action
p, admin, *, *
p, member, object_type, create
p, member, object_type, read
p, member, object_type, update
p, member, object_type, delete
p, member, connection, create
p, member, connection, read
p, member, connection, update
p, member, connection, delete
p, member, action, execute
p, member, workflow, *
p, member, user, read
p, member, tenant, read
p, member, audit_log, read
p, viewer, object_type, read
p, viewer, connection, read
p, viewer, workflow, read
p, viewer, user, read
p, viewer, tenant, read
p, viewer, audit_log, read

# g, user_role_assignment (从 user_tenant_memberships 表同步)
# g, ri.user.{uuid}, admin
```

用户与角色的绑定（`g` 规则）从 `user_tenant_memberships` 表同步到 Casbin。用户登录或租户切换时，Casbin adapter 加载该用户在当前租户中的角色。

**权限矩阵**（等价表述）：

| resource_type | action | admin | member | viewer |
|---------------|--------|-------|--------|--------|
| object_type | create / update / delete | Y | Y | N |
| object_type | read | Y | Y | Y |
| connection | create / update / delete | Y | Y | N |
| connection | read | Y | Y | Y |
| action | execute | Y | Y | N |
| workflow | create / update / delete / execute | Y | Y | N |
| workflow | read | Y | Y | Y |
| user | create / update / delete | Y | N | N |
| user | read | Y | Y | Y |
| tenant | create / update / delete | Y | N | N |
| tenant | read | Y | Y | Y |
| audit_log | read | Y | Y | Y |

#### 2.5.4 P2：自定义角色 + 资源级权限

```ini
# model_p2.conf — RBAC + 资源级权限
[request_definition]
r = sub, obj, act, res

[policy_definition]
p = sub, obj, act, res

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act && (p.res == "*" || p.res == r.res)
```

P2 扩展：
- 自定义角色：在 policy 中定义新角色和权限集合，无需改代码
- 资源级权限：`res` 字段匹配 `resource_rid`，支持"用户 A 只能编辑 ObjectType X"
- 权限继承：通过 Casbin 的 `g` 规则实现角色层级（如 `g, editor, viewer`）

### 2.6 业务规则

#### 2.6.1 密码策略

- 长度 ≥ 8 字符
- 至少包含字母和数字
- 哈希：`passlib` 的 `CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)`
- 密码不在响应中返回，不在日志中记录
- P3 接入外部 SSO 后，密码由外部 IdP 管理，本地 `password_hash` 字段置空

#### 2.6.2 首次启动 Seed

系统首次启动时执行初始化：

```
启动检查：users 表是否为空
  ↓ 为空
1. 创建默认租户：
   - rid: 自动生成
   - display_name: 从 LINGSHU_SEED_TENANT_NAME 读取（默认 "Default"）
  ↓
2. 创建管理员用户：
   - email: 从 LINGSHU_SEED_ADMIN_EMAIL 读取（必填）
   - password: 从 LINGSHU_SEED_ADMIN_PASSWORD 读取（必填）
   - role: admin
   - 自动加入默认租户
  ↓
3. 记录审计日志：SEED_INITIALIZED
```

**环境变量**：

```bash
LINGSHU_SEED_ADMIN_EMAIL=admin@example.com    # 必填
LINGSHU_SEED_ADMIN_PASSWORD=change_me_123     # 必填，首次登录后应修改
LINGSHU_SEED_TENANT_NAME=Default              # 可选，默认 "Default"
```

缺少必填环境变量时，启动失败并输出明确的错误信息。

#### 2.6.3 租户隔离执行

```
Auth Middleware 解析 JWT
  → 写入 ContextVar: tenant_id = JWT.tid
  → 后续所有数据库查询自动附加 WHERE tenant_id = :tenant_id
```

各能力域的 Repository 层统一从 ContextVar 读取 `tenant_id`，确保租户隔离无遗漏。具体各存储层的隔离策略见 `TECH_DESIGN.md` 第 12 节。

#### 2.6.4 错误码

遵循 `TECH_DESIGN.md` 第 5 节的错误码体系，前缀 `SETTING_`：

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `SETTING_AUTH_INVALID_CREDENTIALS` | 401 | 邮箱或密码错误 |
| `SETTING_AUTH_TOKEN_EXPIRED` | 401 | Access Token 已过期 |
| `SETTING_AUTH_TOKEN_REVOKED` | 401 | Token 已被撤销（在黑名单中） |
| `SETTING_AUTH_REFRESH_EXPIRED` | 401 | Refresh Token 已过期或已撤销 |
| `SETTING_USER_NOT_FOUND` | 404 | 用户 RID 不存在 |
| `SETTING_USER_EMAIL_DUPLICATE` | 409 | 邮箱已被注册 |
| `SETTING_USER_DISABLED` | 403 | 用户已停用 |
| `SETTING_TENANT_NOT_FOUND` | 404 | 租户 RID 不存在 |
| `SETTING_TENANT_NOT_MEMBER` | 403 | 用户不是该租户的成员 |
| `SETTING_PASSWORD_TOO_WEAK` | 422 | 密码不满足强度要求 |
| `SETTING_PERMISSION_DENIED` | 403 | RBAC 权限不足（P1+） |

---

## 3. 前端交互设计

### 3.1 页面结构

设置模块在 Main Stage 内采用 PRODUCT_DESIGN.md 定义的**侧边面板 + 内容区域**结构。

```
┌──────────────┬──────────────────────────────────────────┐
│  侧边面板     │  内容区域                                 │
│              │                                          │
│  概览        │                                          │
│  用户管理    │     （用户列表 / 审计日志 / 租户详情）      │
│  审计日志    │                                          │
│  租户管理    │                                          │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
```

**侧边面板说明**：
- 4 个固定导航项：概览、用户管理、审计日志、租户管理
- 点击导航项在内容区域展示对应页面

### 3.2 登录页

路由：`/login`（认证布局外，不显示 Dock 和 Global Header）。

**页面内容**：
- 居中卡片布局：Logo + 系统名称 + 登录表单
- 表单字段：邮箱、密码
- 登录按钮 + 错误提示区域
- 登录成功后跳转到首页（`/`）或登录前的目标页面

**未认证重定向**：访问任何需要认证的页面时，如果未登录，自动重定向到 `/login?redirect={原路径}`。

### 3.3 用户管理

**列表页**（`/setting/users`）：

| 列 | 内容 |
|----|------|
| 名称 | display_name |
| 邮箱 | email |
| 角色 | 当前租户中的角色 |
| 状态 | active / disabled（状态标签） |
| 创建时间 | created_at |

**操作**：
- 新建：右上角按钮 → 弹出创建表单（邮箱、名称、初始密码、角色）
- 编辑：点击行 → 进入用户详情/编辑页
- 停用/启用：操作按钮切换用户状态
- 重置密码：管理员操作，生成临时密码或发送重置链接

**用户详情页**（`/setting/users/:rid`）：
- 基本信息：邮箱、名称、状态
- 所属租户列表：该用户加入的所有租户及角色
- 操作历史：该用户的最近审计日志

### 3.4 审计日志

**列表页**（`/setting/audit`）：

| 列 | 内容 |
|----|------|
| 时间 | created_at |
| 模块 | module（标签样式，不同模块不同颜色） |
| 事件类型 | event_type |
| 操作描述 | action |
| 操作者 | user_display_name |
| 资源 | resource_type + resource_rid（可点击跳转） |

**筛选控件**（表格上方）：
- 模块：下拉多选（ontology / data / function / copilot / setting）
- 操作者：下拉选择用户
- 时间范围：日期区间选择器
- 事件类型：下拉多选

**资源跨模块跳转**：`resource_rid` 可点击，根据 RID 前缀跳转到对应模块的详情页：
- `ri.obj.*` → `/ontology/object-types/:rid`
- `ri.link.*` → `/ontology/link-types/:rid`
- `ri.conn.*` → `/data/sources/:rid`
- `ri.action.*` → `/ontology/action-types/:rid`
- `ri.func.*` → `/function/capabilities/globals/:rid`
- `ri.workflow.*` → `/function/workflows/:rid`
- `ri.session.*` → `/agent/chat/:session_id`
- `ri.user.*` → `/setting/users/:rid`

### 3.5 租户管理

**列表页**（`/setting/tenants`）：

| 列 | 内容 |
|----|------|
| 名称 | display_name |
| 状态 | active / disabled |
| 成员数 | 该租户的成员数量 |
| 创建时间 | created_at |

**租户详情页**（`/setting/tenants/:rid`）：
- 基本信息：名称、状态、配置
- 成员列表：用户名、邮箱、角色、加入时间。支持添加/移除成员、修改角色

### 3.6 概览页

**内容**（`/setting/overview`）：
- 统计卡片：用户总数（活跃/停用）、租户总数
- 最近审计活动：最近 10 条审计日志摘要（时间、模块、事件、操作者）

### 3.7 Global Header 集成

**用户头像下拉菜单**（PRODUCT_DESIGN.md §3.2 定义）对接 Setting 模块 API：

| 菜单项 | 行为 | API |
|--------|------|-----|
| 用户信息 | 显示当前用户名和邮箱 | `GET /setting/v1/auth/me` |
| 切换租户 | 展开租户列表，点击切换 | `POST /setting/v1/tenants/switch` |
| 修改密码 | 弹出修改密码对话框 | `POST /setting/v1/auth/change-password` |
| 退出登录 | 登出并跳转到登录页 | `POST /setting/v1/auth/logout` |

### 3.8 跨模块跳转

遵循 `PRODUCT_DESIGN.md` 第 6.6 节"引用即链接"原则。

**从设置模块跳出**：
- 审计日志的 resource_rid → 对应模块的详情页（见 3.4 跳转规则）

**从其他模块跳入**：
- 任何模块中的用户名/用户 ID → `/setting/users/:rid`

---

## 4. 实现优先级

| 阶段 | 范围 | 前置依赖 | 说明 |
|------|------|---------|------|
| P0 | Built-in Provider（authlib JWT）+ Auth Middleware + 用户 CRUD + Casbin allow-all + Seed 初始化 + 审计日志表 + `write_audit_log` 工具 + 审计日志查询 API | 无 | 认证闭环 + 审计基础：用户可登录/登出，Casbin 就位但不拦截，各模块可写入和查询审计日志 |
| P1 | Casbin RBAC model（admin/member/viewer）+ 租户 CRUD + 租户切换 + 成员管理 | P0 | 权限和多租户：切换 Casbin model 为 RBAC，三角色权限控制生效 |
| P2 | Casbin RBAC + 资源级 model + 自定义角色 + 审计日志保留策略（自动归档/清理） | P1 | 精细化权限：切换 Casbin model 支持 resource_rid 粒度控制 |
| P3 | 外部 OIDC Provider（Keycloak/Ory Kratos）+ SSO/LDAP + JIT Provisioning + 租户配额与计费 | P2 | 企业级扩展：配置 `LINGSHU_AUTH_OIDC_ISSUER_URL` 切换到外部 IdP，业务代码不变 |

---

## 5. SSO 集成演进路径

本节说明从内置认证到外部 SSO 的演进路径，以及为什么当前架构不需要大改就能接入。

### 5.1 架构保证

| 设计要素 | 如何保证 SSO 可接入 |
|---------|-------------------|
| Identity Provider 抽象 | `provider.py` 定义 Protocol 接口，内置实现和外部 OIDC 实现可互换 |
| OIDC-compatible JWT Claims | `iss`/`sub`/`aud`/`jti` 遵循 OIDC 标准，外部 IdP 签发的 JWT 格式兼容 |
| authlib 库 | 内置 OIDC client 支持，P3 直接使用其 OIDC discovery + token 校验能力 |
| Casbin 权限与认证解耦 | 权限判断只依赖 JWT 中的 `sub`（用户）和 `role`，不依赖认证方式 |
| 用户表保留 | 外部 SSO 用户通过 JIT Provisioning 同步到本地 users 表，审计日志等业务逻辑不变 |

### 5.2 P3 接入步骤

```
1. 部署外部 IdP（如 Keycloak），配置 Realm、Client、角色映射
2. 设置环境变量：
   LINGSHU_AUTH_PROVIDER=oidc
   LINGSHU_AUTH_OIDC_ISSUER_URL=https://keycloak.example.com/realms/lingshu
   LINGSHU_AUTH_OIDC_CLIENT_ID=lingshu
   LINGSHU_AUTH_OIDC_CLIENT_SECRET=xxx
3. Auth Middleware 自动切换：
   · 从 OIDC Discovery 获取 JWKS（公钥）
   · 用 JWKS 校验外部签发的 JWT（替代本地签名校验）
   · 从 JWT claims 提取 sub/tid/role，写入 ContextVar（流程不变）
4. 登录页重定向到外部 IdP 的授权页面（OAuth2 Authorization Code Flow）
5. 首次登录的 SSO 用户自动创建本地 users 记录（JIT Provisioning）
6. 本地 /setting/v1/auth/login 端点保留为 fallback（管理员本地登录）
```

**不需要改的部分**：Auth Middleware 下游的所有业务代码（ContextVar 读取、Casbin 权限判断、审计日志、租户隔离）。

---
