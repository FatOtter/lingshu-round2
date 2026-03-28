# ONTOLOGY_DESIGN.md - 本体模块设计

> **版本**: 0.1.0
> **更新日期**: 2026-02-24
> **状态**: 草稿
> **前置文档**: `DESIGN.md`（能力域边界）、`TECH_DESIGN.md`（API/RID/错误规范）、`PRODUCT_DESIGN.md`（模块结构）、`ONTOLOGY.md`（本体理论）

---

## 1. 模块定位

本体模块是 Ontology 能力域的完整实现，覆盖后端服务和前端交互。

**职责**：
- 6 种实体类型的 CRUD（SharedPropertyType、PropertyType、InterfaceType、ObjectType、LinkType、ActionType）
- 版本生命周期管理（Draft → Staging → Snapshot → Active）
- AssetMapping 配置
- 依赖检测、级联更新、循环依赖校验
- 图数据的存储与查询

**不负责**：
- 数据实例的关联和查询（Data 能力域）
- Action 的运行时执行（Function 能力域）

---

## 2. 后端服务设计

### 2.1 服务层架构

```
ontology/
├── router.py              # FastAPI 路由定义
├── service.py             # 业务逻辑（OntologyServiceImpl）
├── interface.py           # Protocol 接口（供其他能力域调用）
├── repository/
│   ├── graph_repo.py      # 图数据库 Repository（Neo4j）
│   └── snapshot_repo.py   # 版本快照 Repository（PostgreSQL）
├── schemas/
│   ├── requests.py        # 请求 DTO
│   └── responses.py       # 响应 DTO
└── validators/
    ├── dependency.py       # 依赖检测（删除前检查引用）
    ├── cascade.py          # 级联更新逻辑
    └── cycle_detection.py  # 循环依赖检测（DFS）
```

**关键约束**：
- 图查询使用标准 Cypher，集中在 Repository 层管理，便于后续 GalaxyBase 迁移时整体替换
- 模块对外只暴露 `OntologyService` Protocol 接口
- 所有查询自动附加 `tenant_id` 过滤

**OntologyService Protocol 接口**（供 Data、Function、Copilot 调用）：

```python
# ontology/interface.py
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

    def query_asset_mapping_references(
        self,
        connection_rid: str,
    ) -> list[AssetMappingReference]: ...
```

- 所有 `get_*` / `list_*` 方法仅返回 Active 版本的实体定义
- `check_implements`：校验指定 ObjectType/LinkType 是否实现了指定 InterfaceType（供 Function 参数解析使用）
- `query_asset_mapping_references`：查询引用指定 Connection 的 AssetMapping 列表（供 Data 删除连接前的引用检测使用）

### 2.2 API 设计

遵循 `TECH_DESIGN.md` 第 3 节的 API 规范。URL 前缀 `/ontology/v1/`。

#### 2.2.1 实体 CRUD API

5 种实体类型有完整 CRUD：

| 实体 | 基础路径 |
|------|----------|
| ObjectType | `/ontology/v1/object-types` |
| LinkType | `/ontology/v1/link-types` |
| InterfaceType | `/ontology/v1/interface-types` |
| ActionType | `/ontology/v1/action-types` |
| SharedPropertyType | `/ontology/v1/shared-property-types` |

每种实体提供以下端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{type}/query` | 列表查询（仅返回 Active 版本，筛选、排序、分页） |
| GET | `/{type}/{rid}` | 查询单个（返回当前生效版本） |
| GET | `/{type}/{rid}/draft` | 查询 Draft 版本（优先 Draft → Staging → Active） |
| POST | `/{type}` | 创建 |
| PUT | `/{type}/{rid}` | 更新（写入 Draft） |
| DELETE | `/{type}/{rid}` | 标记删除（写入 Draft 删除标记，依赖检查） |
| GET | `/{type}/{rid}/related` | 查询关联实体 |
| POST | `/{type}/{rid}/lock` | 获取编辑锁 |
| POST | `/{type}/{rid}/submit-to-staging` | 将 Draft 提交到 Staging |
| DELETE | `/{type}/{rid}/staging` | 丢弃单个实体的 Staging |
| PUT | `/{type}/{rid}/lock` | 续期编辑锁（心跳） |
| DELETE | `/{type}/{rid}/lock` | 释放编辑锁 |
| DELETE | `/{type}/{rid}/draft` | 丢弃 Draft |

PropertyType 和 AssetMapping 的增删改通过父实体（ObjectType / LinkType）的 CRUD 完成，但提供只读查询端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ontology/v1/property-types/query` | 跨实体的 PropertyType 扁平查询 |
| GET | `/ontology/v1/property-types/{rid}` | 查询单个 PropertyType |
| POST | `/ontology/v1/asset-mappings/query` | 跨实体的 AssetMapping 状态查询 |
| GET | `/ontology/v1/asset-mappings/{rid}` | 查询单个 AssetMapping |

**响应中的版本状态标识**：

查询编辑版本（`GET /{type}/{rid}/draft`）的响应中包含 `version_status` 字段：

```json
{
  "data": { ... },
  "version_status": "draft",
  "is_active": true,
  "metadata": { ... }
}
```

`version_status` 取值：`draft`（用户有未提交的草稿）、`staging`（已提交到 Staging 但未发布）、`active`（无未发布修改，返回当前生效版本）。`is_active` 表示该版本的实体存活状态：`false` 表示这是一个删除标记（实体将在发布后停用）。前端据此决定显示对应的状态提示。

#### 2.2.2 概览拓扑 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ontology/v1/topology` | 获取 Ontology 语义拓扑数据（供概览页可视化） |

**说明**：返回的是 Ontology 语义层面的类型拓扑关系，不是图数据库的原始存储结构。只包含 ObjectType、LinkType、InterfaceType 等一级实体和它们之间的语义关系（如 CONNECTS、IMPLEMENTS），不包含 PropertyType 等细节节点。

**响应**：

```json
{
  "data": {
    "types": [
      {
        "rid": "ri.obj.{uuid1}",
        "kind": "ObjectType",
        "display_name": "机器人",
        "lifecycle_status": "ACTIVE"
      }
    ],
    "relations": [
      {
        "rid": "ri.link.{uuid2}",
        "kind": "CONNECTS",
        "source_rid": "ri.obj.{uuid1}",
        "target_rid": "ri.obj.{uuid3}",
        "display_name": "充电关系"
      }
    ]
  }
}
```

#### 2.2.3 全局搜索 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ontology/v1/search?q={keyword}&types={types}&limit={n}` | 跨实体类型搜索 |

`types` 可选，逗号分隔实体类型（如 `object,link`），不传则搜索所有类型。搜索范围包括 `api_name`、`display_name`、`description`。

#### 2.2.4 版本管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ontology/v1/staging/summary` | Staging 摘要（各实体类型的待提交数量） |
| POST | `/ontology/v1/staging/commit` | 发布 Staging → 创建 Snapshot → 更新 Active |
| POST | `/ontology/v1/staging/discard` | 丢弃所有 Staging 修改（逐个执行单个丢弃逻辑） |
| GET | `/ontology/v1/drafts/summary` | Draft 摘要（各用户的未提交 Draft 数量和列表） |
| POST | `/ontology/v1/snapshots/query` | 查询 Snapshot 列表 |
| GET | `/ontology/v1/snapshots/{snapshot_id}` | 查询 Snapshot 详情 |
| GET | `/ontology/v1/snapshots/{snapshot_id}/diff` | 与当前 Active 版本的 Diff |
| POST | `/ontology/v1/snapshots/{snapshot_id}/rollback` | 回滚到指定 Snapshot |

**Staging 摘要响应**：

```json
{
  "data": {
    "total": 5,
    "by_type": {
      "object_types": { "created": 1, "updated": 2, "deleted": 0 },
      "link_types": { "created": 0, "updated": 1, "deleted": 0 },
      "shared_property_types": { "created": 1, "updated": 0, "deleted": 0 }
    }
  }
}
```

其中统计逻辑：`created` = Staging 且该实体无 Active 节点；`updated` = Staging 且有 Active 且 `is_active = true`；`deleted` = Staging 且 `is_active = false`。

**Draft 摘要响应**：

```json
{
  "data": {
    "total": 3,
    "by_user": [
      {
        "user_id": "user_123",
        "count": 2,
        "entities": [
          { "rid": "ri.obj.{uuid1}", "entity_type": "ObjectType", "display_name": "机器人" },
          { "rid": "ri.link.{uuid2}", "entity_type": "LinkType", "display_name": "充电关系" }
        ]
      },
      {
        "user_id": "user_456",
        "count": 1,
        "entities": [
          { "rid": "ri.iface.{uuid3}", "entity_type": "InterfaceType", "display_name": "可充电" }
        ]
      }
    ]
  }
}
```

**Diff 响应**：

```json
{
  "data": {
    "changes": [
      {
        "entity_rid": "ri.obj.{uuid}",
        "entity_type": "ObjectType",
        "display_name": "机器人",
        "operation": "update",
        "field_changes": [
          {
            "field": "description",
            "old_value": "旧描述",
            "new_value": "新描述"
          }
        ]
      }
    ]
  }
}
```

#### 2.2.5 关联实体查询

`GET /{type}/{rid}/related` 的响应结构因实体类型而异：

| 实体类型 | 返回的关联内容 |
|----------|-------------|
| ObjectType | 关联的 LinkType（作为 source/target）、实现的 InterfaceType、操作它的 ActionType |
| LinkType | source/target ObjectType 或 InterfaceType、实现的 InterfaceType、操作它的 ActionType |
| InterfaceType | 实现它的 ObjectType/LinkType、继承它的子 InterfaceType、引用的 SharedPropertyType |
| ActionType | 操作的 ObjectType/LinkType/InterfaceType |
| SharedPropertyType | 继承它的 PropertyType（及其所属实体）、引用它的 InterfaceType |

### 2.3 存储设计

#### 2.3.1 图数据库（Neo4j）

存储 Ontology 的实体节点和关系边，承担以下职责：
- 实体的全部版本状态（Draft / Staging / Active）
- 7 种关系边（BELONGS_TO、BASED_ON、IMPLEMENTS、EXTENDS、CONNECTS、REQUIRES、OPERATES_ON）
- 版本状态标记（`is_draft`、`is_staging`、`is_active`、`draft_owner`、`snapshot_id`、`parent_snapshot_id`、`tenant_id`，详见 `ONTOLOGY.md` 第 10.2 节）

**三个标记的语义**：

| is_draft | is_staging | is_active | 含义 |
|----------|-----------|-----------|------|
| true | false | true | Draft：新建或修改 |
| true | false | false | Draft：删除 |
| false | true | true | Staging：新建或修改 |
| false | true | false | Staging：删除 |
| false | false | true | 当前生效版本 |
| false | false | false | 历史版本（已归档） |

`is_draft` 和 `is_staging` 互斥，不会同时为 true。两者都为 false 表示正式节点（已发布）。`is_active` 表示该实体在此节点语境下是否存活：在 Draft/Staging 上代表发布后的目标状态（意图），在正式节点上代表当前事实
- 依赖检测和级联更新的图遍历

**Proto → 图节点映射规则**：
- 基本类型字段（string、int、bool、enum）：直接映射为节点属性
- 枚举字段：存储为字符串
- 重复消息字段（repeated message）：序列化为 JSON 字符串
- oneof 字段：展平为可空属性
- Map 字段（如 property_types）：不存为节点属性，通过 BELONGS_TO 边表达
- 引用 RID 字段（如 `source_object_type_rid`）：不存为属性，通过关系边表达

**软删除**：实体不物理删除。发布删除类 Staging（`is_active = false`）时，对应 Active 节点设置 `is_active = false`，实体从查询结果中消失但节点保留用于回滚。

#### 2.3.2 Redis

**对象级编辑锁**：

- Key 格式：`lock:{tenant_id}:{entity_rid}`
- Value：`{ user_id, locked_at }`
- 创建方式：SETNX（原子性获取）
- TTL：1800 秒（30 分钟），防止用户断线后死锁
- 续期：前端每 60 秒发送心跳（`PUT /{type}/{rid}/lock`），刷新 TTL。用户在页面停留或操作期间锁不会过期
- 用途：防止多用户同时编辑同一实体

**租户级提交锁**：

- Key 格式：`commit_lock:{tenant_id}`
- TTL：60 秒（短 TTL）
- 续期：服务端在发布/回滚操作过程中每 15 秒自动续期 TTL。操作持续多久锁就持续多久
- 释放：操作完成（成功或失败）后主动释放。服务崩溃时无续期，锁在 60 秒后自动过期
- 用途：提交/回滚操作的互斥

#### 2.3.3 PostgreSQL

存储版本快照：

**snapshots 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| snapshot_id | VARCHAR | 主键，`ri.snap.{uuid}` |
| parent_snapshot_id | VARCHAR | 父快照 ID |
| tenant_id | VARCHAR | 租户 ID |
| commit_message | TEXT | 提交消息 |
| author | VARCHAR | 提交者 |
| entity_changes | JSONB | 变更详情 `{ "ri.obj.{uuid1}": "create", "ri.link.{uuid2}": "update" }` |
| created_at | TIMESTAMP | 创建时间 |

**active_pointers 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| tenant_id | VARCHAR | 主键 |
| snapshot_id | VARCHAR | 当前 Active 的 Snapshot ID |
| updated_at | TIMESTAMP | 更新时间 |

### 2.4 版本管理流程

基于 `ONTOLOGY.md` 第 10 章的四阶段模型（Draft → Staging → Snapshot → Active），具体实现流程如下。

#### 2.4.1 获取编辑锁

```
用户点击"编辑" → POST /{type}/{rid}/lock
  1. 尝试获取对象级锁：SETNX lock:{tenant_id}:{rid}，TTL 30 分钟
  2. 获取失败 → 返回 409，附带锁持有者信息（user_id、locked_at）
     前端提示"该实体正在被 xxx 编辑"
  3. 获取成功 → 检查是否存在其他用户的孤儿 Draft（draft_owner ≠ 当前用户）
     → 存在则自动丢弃（锁已过期说明原用户已离开，Draft 视为放弃）
  4. 返回 200，前端进入编辑模式，启动心跳定时器
```

**心跳续期**：前端每 60 秒调用 `PUT /{type}/{rid}/lock` 刷新锁 TTL。用户在页面停留或操作期间锁持续有效；用户关闭页面或断线后心跳停止，锁在 30 分钟后自动过期释放。

用户关闭编辑器或手动退出编辑时主动释放锁（`DELETE /{type}/{rid}/lock`）。

#### 2.4.2 创建新实体

```
用户新建 → POST /{type}
  1. 生成 RID（ri.{type}.{uuid}）
  2. 获取编辑锁（SETNX lock:{tenant_id}:{rid}）
  3. 创建 Draft 节点：
     - 写入用户提交的基本信息（api_name、display_name 等）
     - 设置 is_draft = true, is_active = true, draft_owner = user_id
     - 设置 parent_snapshot_id = NULL（无 Active 版本）
  4. 返回完整的 Draft 实体（含 RID）
```

前端收到响应后在新 Tab 中打开编辑器进入编辑模式。后续的编辑保存走 `PUT /{type}/{rid}`（2.4.3），提交走 `POST /{type}/{rid}/submit-to-staging`（2.4.4）。

#### 2.4.3 编辑保存（写入 Draft）

Draft 是用户级草稿，存储在 Neo4j 中，仅草稿所有者可见。

```
用户保存 → PUT /{type}/{rid}
  1. 校验调用者持有该实体的编辑锁
  2. 判断当前实体状态，创建或更新 Draft 节点：
     a. 实体处于 Active 状态（无 Draft 也无 Staging）
        → 从 Active 节点克隆出 Draft 节点
        - 复制所有属性
        - 设置 is_draft = true, is_active = true, is_staging = false
        - 设置 draft_owner = user_id
        - 设置 parent_snapshot_id = Active 节点的 snapshot_id（用于冲突检测）
        - 设置 snapshot_id = NULL
     b. 实体已有 Staging 节点（之前提交过但未发布）
        → 从 Staging 节点克隆出 Draft 节点
        - 复制 Staging 的所有属性（包括 is_active）
        - 设置 is_draft = true, is_staging = false
        - 设置 draft_owner = user_id
        - 设置 parent_snapshot_id = Active 节点的 snapshot_id
        - Staging 节点保持不变（is_staging = true）
        - 基于 Staging 的内容继续编辑
     c. 实体已有 Draft 节点
        → 直接更新 Draft 节点
     d. 新创建实体
        → 直接创建 Draft 节点（无需克隆）
        - 设置 is_draft = true, is_active = true, draft_owner = user_id
  3. 将用户修改写入 Draft 节点
```

**Draft 特性**：
- 仅 draft_owner 可见，其他用户看不到
- 多个用户可同时编辑不同实体（各自有独立 Draft），通过对象级锁保证同一实体只有一个 Draft
- Draft 可多次保存覆盖
- 已提交到 Staging 的实体可以再次编辑（从 Staging 克隆 Draft，Staging 节点保持不变）

#### 2.4.4 提交到 Staging（Draft → Staging）

用户完成编辑后将 Draft 提交到 Staging，使修改对租户内所有用户可见。

```
用户提交 → POST /{type}/{rid}/submit-to-staging
  1. 校验调用者是 Draft 的 owner
  2. 冲突检测：
     - parent_snapshot_id = NULL（新创建实体）→ 跳过冲突检测
     - parent_snapshot_id ≠ NULL → 比较与当前 Active 的 snapshot_id，不一致则返回 409（ONTOLOGY_VERSION_CONFLICT）
  3. 判断是否存在对应的 Staging 节点：
     a. 存在 Staging 节点（二次编辑场景）
        → 用 Draft 节点的内容和 is_active 更新 Staging 节点
        → 删除 Draft 节点
     b. 不存在 Staging 节点
        → 将 Draft 原地标记为 Staging：is_draft = false, is_staging = true, draft_owner = NULL（is_active 保持不变）
  4. 释放编辑锁
```

#### 2.4.5 丢弃 Staging

**单个丢弃**（`DELETE /{type}/{rid}/staging`）：

```
用户丢弃 → DELETE /{type}/{rid}/staging
  1. 检查实体是否有 Staging 节点 → 无则返回 404
  2. 检查实体是否有 Draft → 有则返回 409（ONTOLOGY_LOCK_CONFLICT，需先丢弃 Draft）
  3. 判断 Staging 节点的来源：
     a. 实体有 Active 版本（无论 Staging 是修改还是删除）
        → 删除 Staging 节点，Active 保持不变
     b. 新创建实体（无 Active）
        → 将 Staging 转为 Draft：is_staging = false, is_draft = true, draft_owner = current_user
        → 返回提示"实体已退回为您的 Draft"
```

**批量丢弃**（`POST /ontology/v1/staging/discard`）：

对每个 Staging 实体逐个执行与单个丢弃相同的逻辑。有 Active 的实体回退到 Active，新创建实体转为原提交者的 Draft。

**设计说明**：
- 对于已有 Active 的实体，丢弃 Staging = 撤销未发布的修改，Active 版本自然生效
- 对于新创建实体（仅有 Staging，无 Active），直接删除会导致实体彻底消失。因此转为 Draft，保留修改内容
- 批量和单个丢弃的语义一致，不因操作方式不同而改变行为

#### 2.4.6 标记删除（→ Draft）

删除实体不立即生效，和编辑一样先写入 Draft，再提交到 Staging，最终通过发布执行删除。删除 Draft 与编辑 Draft 的区别仅在于 `is_active = false`。

仅已发布的实体（有 Active 版本）可以走删除流程。新创建实体（仅有 Draft 或 Staging，无 Active）不需要删除——通过丢弃 Draft（2.4.7）或丢弃 Staging（2.4.5）即可撤销。

```
用户删除 → DELETE /{type}/{rid}
  1. 前置校验：实体无 Active 节点 → 返回 400，提示通过丢弃 Draft/Staging 处理
  2. 依赖检测（详见 2.5.1），有依赖则阻止并返回引用列表
  3. 检查是否有该实体的编辑锁或 Draft → 有则返回 409（ONTOLOGY_LOCK_CONFLICT，实体正在被编辑）
  4. 获取编辑锁
  5. 创建 Draft 删除节点：
     a. 实体仅有 Active（无 Staging）→ 创建 Draft 节点，设置 is_draft = true, is_active = false, draft_owner = user_id, parent_snapshot_id = Active 的 snapshot_id
     b. 实体有 Active 和 Staging → 创建 Draft 节点，设置 is_draft = true, is_active = false, draft_owner = user_id, parent_snapshot_id = Active 的 snapshot_id（Staging 节点保持不变）
  6. 返回成功（Draft 处于待提交状态，用户需通过 submit-to-staging 提交）
```

**后续流程**：
- 用户提交到 Staging（`POST /{type}/{rid}/submit-to-staging`）→ Draft 的 `is_active = false` 同步到 Staging 节点
- 管理员发布时：`is_active = false` 的 Staging 节点执行软删除（对应 Active 节点设置 `is_active = false`），而非创建新的 Active 节点
- 提交到 Staging 时，如果存在旧 Staging 修改，删除 Draft 的 `is_active = false` 覆盖之前的修改

**撤销删除**：
- Draft 阶段：用户丢弃 Draft（`DELETE /{type}/{rid}/draft`）
- Staging 阶段：丢弃单个 Staging（`DELETE /{type}/{rid}/staging`），或丢弃全部 Staging（`POST /ontology/v1/staging/discard`）

#### 2.4.7 丢弃 Draft

用户可主动丢弃自己的 Draft，回退到之前的状态。

```
用户丢弃 → DELETE /{type}/{rid}/draft
  1. 校验调用者是 Draft 的 owner
  2. 删除 Draft 节点：
     a. Draft 克隆自 Active → 删除 Draft 节点（Active 不受影响）
     b. Draft 克隆自 Staging → 删除 Draft 节点（Staging 不受影响）
     c. Draft 是新创建实体（无 Active 也无 Staging）→ 删除 Draft 节点
  3. 释放编辑锁（如果持有）
```

由于 Staging 节点始终独立保留（2.4.3 分支 b 采用克隆而非原地转换），丢弃 Draft 只需删除 Draft 节点即可，不会影响已有的 Staging 或 Active 版本。

#### 2.4.8 发布（Staging → Snapshot → Active）

管理员将所有 Staging 修改统一发布为新版本。

```
管理员发布 → POST /ontology/v1/staging/commit
  1. 获取租户级 Redis 锁（SETNX，TTL 60 秒，启动后台线程每 15 秒续期）
  2. 检查是否有未提交的 Draft → 有则返回 Draft 摘要，提示管理员通知用户先提交或丢弃
  3. 查询所有 Staging 节点（is_staging = true）
  4. 校验：
     - 引用完整性（被引用的实体存在，is_active = false 的 Staging 实体不被其他非删除实体引用）
     - 循环依赖检测（InterfaceType EXTENDS）
     - InterfaceType 契约满足性
     - api_name 唯一性
     - 数据类型兼容性
  5. 生成 snapshot_id（ri.snap.{uuid}）
  6. PostgreSQL 事务：
     - 写入 snapshots 表
     - 更新 active_pointers 表
  7. Neo4j 切换：
     - 对于 is_active = false 的 Staging 节点（删除）：对应 Active 节点设置 is_active = false，删除 Staging 节点
     - 对于 is_active = true 的 Staging 节点（新建/修改）：旧 Active 节点设置 is_active = false，Staging 节点设置 is_staging = false, snapshot_id = {new_id}（is_active 已经是 true）
  8. 通知 Data 能力域：
     - DataService.invalidate_schema_cache(tenant_id)：清除 Schema 缓存
     - DataService.on_schema_published(tenant_id, entity_changes)：触发 Schema 变更后的联动处理
       （如 Doris 自动建表/加列/删列、Flink Job 重新计算 VE 物化列等，详见 DATA_DESIGN.md §2.7 / §2.9.2）
  9. 释放锁
  10. 返回 snapshot_id
```

**失败处理**：
- PostgreSQL 写入失败：释放锁，返回错误，Staging 保持不变
- Neo4j 切换失败：PostgreSQL 已提交，启动异步重试（最多 10 次，间隔 30 秒）。超过重试次数进入降级模式（查询可用，编辑/提交/回滚禁用）

#### 2.4.9 回滚

```
管理员回滚 → POST /ontology/v1/snapshots/{snapshot_id}/rollback
  1. 获取租户级锁
  2. 前置检查：
     - 查询是否存在未提交的 Draft 或 Staging 节点
     - 存在则返回 409（ONTOLOGY_UNCOMMITTED_CHANGES），附带 Draft/Staging 摘要
     - 要求管理员先处理未提交的修改（丢弃或发布）后再回滚
  3. Neo4j：切换 is_active 标记（当前版本 → false，目标版本 → true）
  4. PostgreSQL：更新 active_pointers
  5. 释放锁
```

回滚不创建新 Snapshot，只切换 Active 标记。回滚前要求所有 Draft 和 Staging 已清空，避免回滚后版本状态混乱。

### 2.5 业务规则

#### 2.5.1 依赖检测（删除前）

标记删除实体前检查入度引用（详见 2.4.6），有依赖则阻止并返回引用列表：

| 实体类型 | 删除前检查 |
|----------|----------|
| SharedPropertyType | 被 PropertyType 继承（BASED_ON）、被 InterfaceType 引用（REQUIRES） |
| InterfaceType | 被 ObjectType/LinkType 实现（IMPLEMENTS）、被子 InterfaceType 继承（EXTENDS） |
| ObjectType | 被 LinkType 端点引用（CONNECTS）、被 ActionType 操作（OPERATES_ON） |
| LinkType | 被 ActionType 操作（OPERATES_ON） |
| ActionType | 无前置依赖，可直接删除 |

#### 2.5.2 级联更新

详细规则见 `ONTOLOGY.md` 第 9 章。以下为所有会触发级联的场景：

**SharedPropertyType 修改 → 三层级联**：

```
SharedPropertyType 修改
  → 查询继承它的 PropertyType（BASED_ON 边）
    → 过滤：字段值与 SharedPropertyType 相同的 PropertyType（未覆盖的才级联）
      → 更新 PropertyType
        → 更新所属的 ObjectType / LinkType
```

**InterfaceType 修改 → 契约重新校验**：

```
InterfaceType 契约变更（required_shared_property_type_rids / link_requirements / object_constraint）
  → 查询实现它的 ObjectType / LinkType（IMPLEMENTS 边）
    → 重新校验契约满足性（是否仍满足新的契约要求）
    → 不满足则标记为校验失败，提交时阻止
  → 查询继承它的子 InterfaceType（EXTENDS 边）
    → 递归传播契约变更
```

InterfaceType 级联不自动修改实现者的内容，而是触发校验。如果实现者不再满足新契约，提交（commit）时校验会失败，需要用户手动修复。

#### 2.5.3 发布后不可变字段

已发布（有 Active 版本）的实体，以下字段不可修改：

| 字段 | 原因 |
|------|------|
| api_name | 外部系统可能已依赖此标识 |
| data_type（PropertyType/SharedPropertyType） | 数据实例已按此类型存储 |
| category（InterfaceType） | 已有实现者依赖此分类 |
| source_type / target_type（LinkType） | 已有数据实例依赖此端点 |

#### 2.5.4 错误码

遵循 `TECH_DESIGN.md` 第 5 节的错误码体系，前缀 `ONTOLOGY_`：

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `ONTOLOGY_DEPENDENCY_CONFLICT` | 409 | 删除实体时存在引用依赖 |
| `ONTOLOGY_CIRCULAR_DEPENDENCY` | 422 | InterfaceType 存在循环继承 |
| `ONTOLOGY_DUPLICATE_API_NAME` | 409 | api_name 在同类实体中重复 |
| `ONTOLOGY_VERSION_CONFLICT` | 409 | 提交时 Active 版本已被其他人更新 |
| `ONTOLOGY_VALIDATION_FAILED` | 422 | 实体校验失败 |
| `ONTOLOGY_IMMUTABLE_FIELD` | 422 | 修改已发布实体的不可变字段 |
| `ONTOLOGY_LOCK_CONFLICT` | 409 | 实体正在被其他用户编辑 |
| `ONTOLOGY_LOCK_REQUIRED` | 403 | 更新操作需要先获取编辑锁 |
| `ONTOLOGY_STAGING_EMPTY` | 400 | 无 Staging 内容时提交 |
| `ONTOLOGY_UNCOMMITTED_CHANGES` | 409 | 回滚时存在未提交的 Draft 或 Staging |
| `ONTOLOGY_DRAFT_NOT_FOUND` | 404 | 丢弃 Draft 时实体无 Draft |
| `ONTOLOGY_STAGING_NOT_FOUND` | 404 | 从 Staging 退回时实体无 Staging |
| `ONTOLOGY_DEGRADED_MODE` | 503 | 系统处于降级模式 |

---

## 3. 前端交互设计

### 3.1 页面结构

本体模块在 Main Stage 内采用 PRODUCT_DESIGN.md 定义的**侧边面板 + 内容区域**结构。内容区域使用多 Tab 编辑器模式。

```
┌──────────────┬──────────────────────────────────────────┐
│  侧边面板     │  Tab Bar                                 │
│              │  [对象类型] [机器人 ●] [充电关系]           │
│ ▸ 概览       ├──────────────────────────────────────────┤
│ ▾ 对象类型    │                                          │
│   · 机器人    │             Tab 内容区域                  │
│   · 充电桩    │                                          │
│ ▸ 关系类型    │         （列表页 / 编辑器 / 图）           │
│ ▾ 接口类型    │                                          │
│   · 可充电    │                                          │
│ ▸ 动作类型    │                                          │
│ ▸ 共享属性    │                                          │
│ ▸ 属性类型    │                                          │
│ ▸ 数据映射    │                                          │
│ ▸ 版本管理    │                                          │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
  （示例：编辑"机器人" ObjectType 时，关联的实体按类型展开在对应分区下）
```

**侧边面板说明**：

侧边面板始终展示 9 个固定分区入口。点击分区名称在内容区域打开对应的列表页或管理页。

当编辑器 Tab（即实体的查看/编辑详情页）处于激活状态时，关联实体以抽屉形式展开在对应的实体类型分区下方。例如编辑一个 ObjectType 时，与它关联的 LinkType 显示在"关系类型"分区下，实现的 InterfaceType 显示在"接口类型"分区下。无关联内容的分区保持折叠。列表页、概览图、版本管理等非实体详情页激活时，各分区下不展示关联实体。

### 3.2 多 Tab 编辑器

内容区域采用多 Tab 容器，类似 IDE 的标签页模式。

**Tab 类型**：
- 列表页 Tab：点击侧边面板导航分区时打开，展示对应实体类型的列表（或概览图、版本管理等管理页）
- 编辑器 Tab：点击列表中的具体实体时打开，展示实体的编辑器

**Tab 管理规则**：
- 最多同时打开 10 个 Tab
- 相同内容不重复开 Tab（已打开则激活）
- 当前 Tab 无未保存修改时，点击新实体复用当前 Tab
- 超过上限时按 LRU 策略关闭最久未使用的 Tab（有未保存修改的 Tab 受保护，不被自动关闭）

**Tab 标题**：
- 列表页 Tab：分区名称（如"对象类型"）
- 编辑器 Tab：实体的 display_name
- 未保存修改：标题旁显示圆点指示

**URL 策略**：URL 只反映当前激活的 Tab。全部 Tab 状态（打开列表、各 Tab 的查看/编辑模式）存储在 LocalStorage，刷新后恢复 Tab 列表但内容重新加载。

### 3.3 查看模式与编辑模式

每个编辑器 Tab 有两种模式：

**查看模式**（默认）：
- 从列表页点击实体、从侧边面板关联抽屉点击关联实体、或外部链接跳转时进入
- 加载数据来源：`GET /{type}/{rid}`（当前生效版本）
- 所有表单控件禁用
- 显示"编辑"按钮
- 不追踪修改状态

**编辑模式**：
- 点击"编辑"按钮 → 请求编辑锁（`POST /{type}/{rid}/lock`）→ 获取成功后进入编辑模式；获取失败提示锁持有者信息
- 加载数据来源：`GET /{type}/{rid}/draft`（优先返回 Draft → Staging → Active 版本）
- 所有表单控件启用（不可变字段除外）
- 追踪修改状态（Deep Diff 比较当前值与初始加载值）
- 有修改时 Tab 标题显示圆点、保存按钮可用
- 保存操作：`PUT /{type}/{rid}`，写入 Draft（Neo4j）
- 提交操作：`POST /{type}/{rid}/submit-to-staging`，将 Draft 提交到 Staging

**退出编辑模式**：
- 保存/提交后点击"退出编辑"或关闭 Tab → 释放编辑锁（`DELETE /{type}/{rid}/lock`）→ 切换回查看模式

**关闭 Tab 行为**：
- 查看模式或无修改：直接关闭
- 编辑模式有未保存修改：弹出三选一对话框（保存 / 不保存 / 取消）。保存和不保存都会释放编辑锁
- 已保存的 Draft 在释放锁后仍保留在 Neo4j 中，用户下次编辑时可继续

### 3.4 侧边面板关联展示

当实体详情页（查看模式或编辑模式的编辑器 Tab）处于激活状态时，关联实体以抽屉形式展开在侧边面板对应的实体类型分区下方，用于快速导航。列表页、概览图等非实体详情页激活时不展示关联实体。

**数据来源**：`GET /{type}/{rid}/related`

**关联实体的分区归属**：

| 当前编辑实体 | 展开的分区 → 关联内容 |
|------------|---------------------|
| ObjectType | 关系类型 → 关联的 LinkType；接口类型 → 实现的 InterfaceType；动作类型 → 操作它的 ActionType；共享属性 → 引用的 SharedPropertyType |
| LinkType | 对象类型 → source/target ObjectType；接口类型 → source/target InterfaceType、实现的 InterfaceType；动作类型 → 操作它的 ActionType |
| InterfaceType | 对象类型 → 实现它的 ObjectType；关系类型 → 实现它的 LinkType；接口类型 → 继承它的子 InterfaceType；共享属性 → 引用的 SharedPropertyType |
| ActionType | 对象类型 → 操作的 ObjectType；关系类型 → 操作的 LinkType；接口类型 → 操作的 InterfaceType |
| SharedPropertyType | 对象类型 → 继承它的 PropertyType 所属 ObjectType；关系类型 → 继承它的 PropertyType 所属 LinkType；接口类型 → 引用它的 InterfaceType |

**行为**：
- 有关联内容的分区自动展开抽屉，无关联内容的分区保持折叠
- 点击关联实体在内容区域打开对应的编辑器 Tab
- 关联数据在保存后刷新（编辑过程中不实时更新）

### 3.5 各实体编辑器

所有编辑器采用单页垂直滚动布局，按 Section 分区。

#### 3.5.1 ObjectType 编辑器

| Section | 内容 |
|---------|------|
| 基本信息 | api_name、display_name、description、lifecycle_status |
| 属性 | PropertyType 列表（表格：名称、数据类型、来源[本地/共享/接口]、是否必填、主键标记）。支持新建属性、从 SharedPropertyType 添加 |
| 接口 | 已实现的 InterfaceType 列表，支持添加/移除。添加时校验契约满足性 |
| 数据映射 | AssetMapping 配置（读路径、写路径） |
| 校验规则 | EntityValidationConfig（跨属性校验表达式） |

#### 3.5.2 LinkType 编辑器

| Section | 内容 |
|---------|------|
| 基本信息 | api_name、display_name、description、lifecycle_status |
| 连接定义 | source_type（ObjectType 或 InterfaceType 选择）、target_type、Cardinality |
| 属性 | 同 ObjectType 的属性 Section |
| 接口 | 同 ObjectType 的接口 Section |
| 数据映射 | AssetMapping 配置 |
| 校验规则 | EntityValidationConfig |

#### 3.5.3 InterfaceType 编辑器

| Section | 内容 |
|---------|------|
| 基本信息 | api_name、display_name、description、lifecycle_status、category（OBJECT_INTERFACE / LINK_INTERFACE） |
| 契约 | required_shared_property_type_rids（选择 SharedPropertyType）。OBJECT_INTERFACE 时显示 link_requirements；LINK_INTERFACE 时显示 object_constraint |
| 继承 | extends_interface_type_rids（选择父 InterfaceType） |
| 实现者 | 只读列表，展示实现此 InterfaceType 的 ObjectType/LinkType |

#### 3.5.4 ActionType 编辑器

| Section | 内容 |
|---------|------|
| 基本信息 | api_name、display_name、description、lifecycle_status |
| 参数 | ActionParameter 列表。每个参数配置 definition_source（explicit_type / derived_from 选择） |
| 执行配置 | engine 类型选择，对应配置区（NATIVE_CRUD: CRUD 配置表单，PYTHON_VENV: 代码编辑器，SQL_RUNNER: SQL 编辑器，WEBHOOK: URL 和参数配置）。is_batch、is_sync 开关 |
| 安全与副作用 | safety_level 选择、side_effects 多选 |

#### 3.5.5 SharedPropertyType 编辑器

| Section | 内容 |
|---------|------|
| 基本信息 | api_name、display_name、description、lifecycle_status |
| 定义 | data_type 选择 |
| UI 配置 | WidgetConfig |
| 校验规则 | PropertyValidationConfig |
| 合规 | ComplianceConfig（Sensitivity + MaskingStrategy） |
| 使用分析 | 只读，展示继承此 SharedPropertyType 的 PropertyType 及其所属实体 |

#### 3.5.6 PropertyType（只读索引页）

不是编辑器，而是跨所有实体的 PropertyType 扁平查询列表。

**列**：名称、数据类型、来源类型（SharedPropertyType / 独立定义）、所属实体（ObjectType / LinkType）。

**操作**：点击跳转到所属实体的编辑器。

#### 3.5.7 AssetMapping（只读索引页）

跨所有 ObjectType / LinkType 的 AssetMapping 配置状态列表。

**列**：实体名称、实体类型、读路径状态、写路径状态。

**操作**：点击跳转到对应实体的编辑器。

### 3.6 概览页（图可视化）

侧边面板点击"概览"进入，展示 Ontology 全局拓扑图。

**数据来源**：`GET /ontology/v1/topology`

**交互**：
- 支持缩放、平移、拖拽节点
- 节点按实体类型用不同颜色区分
- 点击节点：在 Tab 中打开该实体的编辑器
- 点击边（LinkType）：在 Tab 中打开该 LinkType 的编辑器

### 3.7 版本管理页

侧边面板点击"版本管理"进入。

**页面内容**：
- Staging 状态区：显示 Staging 摘要（各类型的待发布数量）。提供"发布"和"丢弃"按钮
- 发布对话框：填写 commit_message，展示变更 Diff 预览
- Snapshot 历史列表：按时间倒序展示提交记录（snapshot_id、提交者、时间、消息）
- Snapshot 详情：点击记录查看变更详情，提供"回滚到此版本"按钮
- Diff 对比：当前 Active 与目标 Snapshot 的逐字段差异对比

### 3.8 列表页

各实体类型的列表页遵循 `PRODUCT_DESIGN.md` 第 6.1 节的通用交互原则。

**通用功能**：
- 搜索（按 api_name、display_name）
- 筛选（按 lifecycle_status）
- 排序（按名称、更新时间）
- 分页
- 新建按钮（左上角）
- 批量操作（勾选后批量删除等）

**新建流程**：
- 点击新建 → 弹出对话框填写基本信息（api_name、display_name）
- 确认后在新 Tab 中打开编辑器进入编辑模式

### 3.9 跨模块跳转

遵循 `PRODUCT_DESIGN.md` 第 6.6 节"引用即链接"原则。本体模块内及跨模块的跳转场景：

**模块内跳转**（同一个 Tab 容器内切换）：
- ObjectType 编辑器 → 点击属性来源的 SharedPropertyType → 打开 SharedPropertyType 编辑器
- ObjectType 编辑器 → 点击实现的 InterfaceType → 打开 InterfaceType 编辑器
- LinkType 编辑器 → 点击 source/target ObjectType → 打开 ObjectType 编辑器
- InterfaceType 编辑器 → 点击实现者 → 打开对应编辑器
- 侧边面板关联抽屉 → 点击任何关联实体 → 打开对应编辑器
- PropertyType 索引 → 点击所属实体 → 打开对应编辑器
- AssetMapping 索引 → 点击所属实体 → 打开对应编辑器
- 版本管理 Diff → 点击变更的实体 → 打开对应编辑器

**跨模块跳转**（导航到其他模块）：
- ObjectType/LinkType 编辑器 → AssetMapping 中的 connection_id → 跳转到数据模块的数据源配置
- ActionType 编辑器 → "在能力模块中执行" → 跳转到能力模块的 Action 执行页

---

## 4. 实现优先级

| 阶段 | 范围 | 说明 |
|------|------|------|
| P0 | 核心 CRUD + 图查询 + Staging 摘要 | ObjectType/LinkType/SharedPropertyType 的增删改查，图可视化，多 Tab 编辑器 |
| P1 | InterfaceType + ActionType + 关联查询 | 接口契约校验、Action 参数定义、侧边面板联动 |
| P2 | 版本管理 | Staging 提交、Snapshot 历史、Diff 对比、回滚 |
| P3 | 搜索 + PropertyType 索引 + AssetMapping 索引 | 全局搜索、只读索引页 |
| P4 | 级联更新 + 降级模式 | SharedPropertyType 级联、Neo4j 故障降级 |

---
