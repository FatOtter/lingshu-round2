# DATA_DESIGN.md - 数据模块设计

> **版本**: 0.3.0
> **更新日期**: 2026-03-02
> **状态**: 草稿
> **前置文档**: `DESIGN.md`（能力域边界）、`TECH_DESIGN.md`（API/RID/错误规范）、`PRODUCT_DESIGN.md`（模块结构）、`ONTOLOGY.md`（本体定义）、`ONTOLOGY_DESIGN.md`（本体模块设计）

---

## 1. 模块定位

数据模块是 Data 能力域的完整实现，覆盖后端服务和前端交互。

**职责**：
- 数据源连接的配置与管理（Connection CRUD、连接测试、状态监控）
- 基于 Ontology 定义（ObjectType/LinkType schema + AssetMapping）将底层数据源的原始数据解析为类型化的数据实例
- 数据实例的只读查询（搜索、筛选、排序、分页、关系遍历）
- 根据 ComplianceConfig 执行脱敏，所有消费方获取的都是已脱敏数据
- 统一数据读取层，为 Function（实例上下文解析）和 Copilot（数据查询）提供服务
- 数据版本管理（Nessie 分支：创建、切换、合并）

**不负责**：
- 类型定义的管理（Ontology 的职责）
- AssetMapping 的定义（Ontology 中 ObjectType/LinkType 的一部分）
- 数据写入的发起——写入由 Function 执行 Action 触发，通过写回管道（Funnel Protocol）完成
- 前端渲染——Data 返回结构化数据，前端根据 WidgetConfig 决定展示形式

---

## 2. 后端服务设计

### 2.1 服务层架构

```
data/
├── router.py              # FastAPI 路由定义
├── service.py             # 业务逻辑（DataServiceImpl）
├── interface.py           # Protocol 接口（供其他能力域调用）
├── connectors/
│   ├── base.py            # Connector 抽象接口
│   ├── postgresql.py      # PostgreSQL Connector
│   ├── doris.py           # Doris Connector（P3）
│   └── iceberg.py         # Iceberg Connector（via Nessie Catalog）
├── repository/
│   └── connection_repo.py # 数据源连接 Repository（PostgreSQL）
├── pipeline/
│   ├── schema_loader.py   # Ontology Schema 加载与缓存
│   ├── query_engine.py    # Schema 驱动的查询生成与执行
│   ├── merge.py           # 读取时合并（基准数据 + FDB EditLog）
│   ├── masking.py         # 脱敏管道
│   └── virtual_eval.py    # Virtual Expression 计算
├── writeback/
│   ├── fdb_client.py      # FoundationDB 连接与 EditLog 读写
│   └── lock.py            # FDB 行级锁管理
├── schemas/
│   ├── requests.py        # 请求 DTO
│   └── responses.py       # 响应 DTO
└── branch/
    └── nessie_client.py   # Nessie REST API 客户端
```

**关键约束**：
- Connector 接口抽象底层存储差异，新增数据源类型只需实现新 Connector
- 数据源连接信息中的凭证加密存储，查询响应中不返回明文凭证
- 所有查询自动附加 `tenant_id` 过滤
- Data 通过 OntologyService Protocol 接口获取类型定义，不直接访问 Neo4j

**DataService Protocol 接口**（供 Function、Copilot 调用）：

```python
# data/interface.py
class DataService(Protocol):
    def query_instances(
        self,
        type_rid: str,              # object_type_rid 或 link_type_rid
        filters: list[Filter],
        sort: list[SortSpec],
        pagination: Pagination,
        branch: str | None = None,
    ) -> QueryResult: ...

    def get_instance(
        self,
        type_rid: str,              # object_type_rid 或 link_type_rid
        primary_key: dict[str, Any],
        branch: str | None = None,
    ) -> Instance | None: ...

    def invalidate_schema_cache(self, tenant_id: str) -> None: ...

    def on_schema_published(
        self,
        tenant_id: str,
        entity_changes: dict[str, str],  # { "ri.obj.{uuid}": "create" / "update" / "delete" }
    ) -> None: ...

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

Object 和 Link 的查询管道完全一致（Schema 加载 → 查询引擎 → VE → 脱敏），通过 RID 前缀（`ri.obj.` / `ri.link.`）区分类型，无需单独的方法。

**关系遍历不在 Protocol 中**：Object→Link（给定 Object 查关联 Link）和 Link→Object（给定 Link 查关联 Object）都是"Ontology 元数据查询 + 多次 Data 原始操作"的组合，属于 API 层或 Global Function 层的逻辑，不属于跨模块 Protocol 接口。

读取方法返回的数据实例已经过脱敏处理。调用方（Function、Copilot）获取的是脱敏后的数据。

`write_editlog` 是 Function 写回数据的唯一入口。Function 不直接操作 FDB，而是通过此方法将变更写入 EditLog。FDB 事务（行级锁 + EditLog 写入）的实现细节封装在 Data 内部。

### 2.2 API 设计

遵循 `TECH_DESIGN.md` 第 3 节的 API 规范。URL 前缀 `/data/v1/`。

#### 2.2.1 数据源连接 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/data/v1/connections` | 创建数据源连接 |
| POST | `/data/v1/connections/query` | 查询连接列表（筛选、排序、分页） |
| GET | `/data/v1/connections/{rid}` | 查询单个连接详情 |
| PUT | `/data/v1/connections/{rid}` | 更新连接配置 |
| DELETE | `/data/v1/connections/{rid}` | 删除连接（需检查 AssetMapping 引用） |
| POST | `/data/v1/connections/{rid}/test` | 测试连接（校验连通性、返回延迟和版本信息） |

**连接测试响应**：

```json
{
  "data": {
    "status": "success",
    "latency_ms": 23,
    "server_version": "PostgreSQL 16.2",
    "error": null
  }
}
```

#### 2.2.2 实例查询 API

实例没有统一的 `instance_id` 概念。每个实例由其 ObjectType/LinkType 定义的 `primary_key_property_type_rids` 唯一标识，主键可能是单列（如 `robot_id`）或复合列（如 `source_id` + `target_id`）。因此实例查询统一使用 POST + 主键条件，而非 URL path 参数。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/data/v1/objects/{object_type_rid}/instances/query` | 查询 ObjectType 的数据实例列表 |
| POST | `/data/v1/objects/{object_type_rid}/instances/get` | 按主键查询单个 Object 实例详情 |
| POST | `/data/v1/objects/{object_type_rid}/instances/links` | 查询实例的关联 Link（请求体中传主键） |
| POST | `/data/v1/links/{link_type_rid}/instances/query` | 查询 LinkType 的数据实例列表 |
| POST | `/data/v1/links/{link_type_rid}/instances/get` | 按主键查询单个 Link 实例详情 |
| POST | `/data/v1/links/{link_type_rid}/instances/objects` | 查询 Link 实例关联的 source/target Object（请求体中传主键） |

**查询请求**（遵循 TECH_DESIGN.md 3.3 节通用格式）：

```json
POST /data/v1/objects/{object_type_rid}/instances/query

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
  },
  "branch": "main"
}
```

`filters` 中的 `field` 使用 PropertyType 的 `api_name`，查询引擎将其映射到物理列。`branch` 可选，默认 `main`，指定 Nessie 分支上下文（仅 Iceberg 数据源有效）。

**单实例查询请求**：

```json
POST /data/v1/objects/{object_type_rid}/instances/get

{
  "primary_key": {
    "robot_id": "R2-D2"
  },
  "branch": "main"
}
```

复合主键示例：`"primary_key": { "source_id": "R2-D2", "target_id": "CS-001" }`。

**实例查询响应**：

```json
{
  "data": [
    {
      "primary_key": { "robot_id": "R2-D2" },
      "type_rid": "ri.obj.{uuid}",
      "properties": {
        "robot_id": "R2-D2",
        "name": "R2-D2",
        "status": "active",
        "battery_level": 85,
        "battery_pct": "85%"
      }
    }
  ],
  "schema": {
    "columns": [
      { "api_name": "robot_id", "display_name": "机器人ID", "data_type": "DT_STRING", "is_primary_key": true },
      { "api_name": "name", "display_name": "名称", "data_type": "DT_STRING" },
      { "api_name": "status", "display_name": "状态", "data_type": "DT_STRING" },
      { "api_name": "battery_level", "display_name": "电量", "data_type": "DT_INTEGER" },
      { "api_name": "battery_pct", "display_name": "电量百分比", "data_type": "DT_STRING", "is_virtual": true }
    ],
    "sortable_fields": ["robot_id", "name", "battery_level"],
    "filterable_fields": ["robot_id", "name", "status", "battery_level"]
  },
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "has_next": true
  },
  "metadata": {
    "request_id": "req_xxx",
    "branch": "main"
  }
}
```

`schema` 提供列元数据，前端据此动态生成表头。`is_virtual` 标记虚拟计算字段。`is_primary_key` 标记主键列。`sortable_fields` 和 `filterable_fields` 排除了被脱敏的字段（见 2.5.4），前端据此控制排序和筛选控件的可用性。

**实例详情响应**（`/instances/get`）：

```json
{
  "data": {
    "primary_key": { "robot_id": "R2-D2" },
    "type_rid": "ri.obj.{uuid}",
    "properties": {
      "robot_id": "R2-D2",
      "name": "R2-D2",
      "status": "active",
      "battery_level": 85
    }
  }
}
```

Object 和 Link 的 `/instances/get` 响应结构完全一致，`type_rid` 为 `ri.obj.*` 或 `ri.link.*`。

**Object→Link 关系查询响应**（`/objects/{rid}/instances/links`）：

```json
{
  "data": {
    "outgoing": [
      {
        "link_type_rid": "ri.link.{uuid}",
        "link_display_name": "充电关系",
        "link_primary_key": { "robot_id": "R2-D2", "station_id": "CS-001" },
        "link_properties": {
          "connected_since": "2026-01-15",
          "priority": 1
        },
        "target_type_rid": "ri.obj.{uuid2}",
        "target_primary_key": { "station_id": "CS-001" },
        "target_display": "充电站 #1"
      }
    ],
    "incoming": []
  }
}
```

**Link→Object 关系查询响应**（`/links/{rid}/instances/objects`）：

```json
{
  "data": {
    "source": {
      "type_rid": "ri.obj.{uuid}",
      "primary_key": { "robot_id": "R2-D2" },
      "display": "R2-D2"
    },
    "target": {
      "type_rid": "ri.obj.{uuid2}",
      "primary_key": { "station_id": "CS-001" },
      "display": "充电站 #1"
    }
  }
}
```

关系查询是 API 层的组合逻辑（Ontology 元数据 + 多次 DataService 原始调用），不属于 DataService Protocol 接口。前端详情页并行调用 `/instances/get` + 关系端点获取完整数据。

#### 2.2.3 分支管理 API（Nessie）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/v1/branches` | 列出所有分支 |
| POST | `/data/v1/branches` | 创建分支（从指定分支或 main 分叉） |
| GET | `/data/v1/branches/{name}` | 查询分支详情（最新 commit、创建时间） |
| DELETE | `/data/v1/branches/{name}` | 删除分支（main 不可删除） |
| POST | `/data/v1/branches/{name}/merge` | 将指定分支合并到目标分支 |
| GET | `/data/v1/branches/{name}/diff/{target}` | 对比两个分支的数据差异 |

**创建分支请求**：

```json
POST /data/v1/branches

{
  "name": "simulation_v1",
  "source_branch": "main"
}
```

**合并请求**：

```json
POST /data/v1/branches/simulation_v1/merge

{
  "target_branch": "main"
}
```

分支操作通过 Nessie REST API 实现，Data 模块封装为内部客户端。分支仅对 Iceberg 数据源生效，PostgreSQL 数据源不支持分支。

#### 2.2.4 概览 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/v1/overview` | 数据模块全局概览 |

**响应**：

```json
{
  "data": {
    "connections": {
      "total": 3,
      "by_status": { "connected": 2, "error": 1 }
    },
    "mapped_types": {
      "object_types": 5,
      "link_types": 3
    },
    "branches": {
      "total": 2,
      "names": ["main", "simulation_v1"]
    }
  }
}
```

### 2.3 存储设计

#### 2.3.1 PostgreSQL（连接配置）

**connections 表**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | VARCHAR | 主键，`ri.conn.{uuid}` |
| tenant_id | VARCHAR | 租户隔离 |
| display_name | VARCHAR | 显示名称 |
| type | VARCHAR | 连接类型（`postgresql` / `iceberg`） |
| config | JSONB | 连接配置（host、port、database 等，不含凭证） |
| credentials | VARCHAR | 凭证引用（加密存储或指向 Secrets 管理） |
| status | VARCHAR | 最近一次探测状态（`connected` / `disconnected` / `error`） |
| status_message | TEXT | 状态详情（错误信息等） |
| last_tested_at | TIMESTAMP | 最近测试时间 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**连接配置（config JSONB）示例**：

不同连接类型的字段结构完全不同，使用 JSONB 而非结构化列。应用层按 `type` 字段选择对应的校验 schema，确保字段完整性和类型正确。

```json
// PostgreSQL — 必填：host, port, database; 可选：schema (默认 "public")
{
  "host": "db.example.com",
  "port": 5432,
  "database": "production",
  "schema": "public"
}

// Iceberg (via Nessie) — 必填：nessie_uri, warehouse
{
  "nessie_uri": "http://nessie:19120/api/v2",
  "warehouse": "s3://datalake/warehouse"
}
```

新增连接类型时，实现对应的 Connector + 配置校验 schema 即可。

#### 2.3.2 FoundationDB（EditLog + 行级锁）

FoundationDB 在写回管道（2.6 节）中承担编辑缓冲区和事务锁的角色。

**EditLog 存储结构**：

```
Key:   edit:{tenant_id}:{type_rid}:{pk_hash}:{timestamp}
Value: {
  "operation": "update",        // create / update / delete
  "primary_key": { "robot_id": "R2-D2" },
  "diff": { "status": "active", "battery_level": 100 },
  "user_id": "user_123",
  "action_type_rid": "ri.action.{uuid}"
}
```

`pk_hash` 是主键值的确定性序列化哈希（按 primary_key_property_type_rids 顺序拼接各主键列值，SHA-256 取前 16 字节 hex）。完整主键值存储在 Value 中，Key 中的 hash 仅用于分组和定位。

**行级锁**：

```
Key:   lock:{tenant_id}:{type_rid}:{pk_hash}
Value: { "user_id": "user_123", "locked_at": "2026-03-01T10:00:00Z" }
```

利用 FDB 的 ACID 事务特性，行级锁不会出现 Redis 锁自动过期导致并发写穿的问题。锁的获取、EditLog 写入、锁的释放在同一个 FDB 事务中完成。

#### 2.3.3 Schema 缓存

**单体阶段：进程内内存缓存**

单体部署时 OntologyService 是进程内函数调用，无需引入 Redis。使用进程内缓存（Python dict + TTL）：

- Key 格式：`(tenant_id, entity_type, rid)`
- TTL：300 秒（5 分钟）
- 失效策略：Ontology 发布新版本时调用 DataService 的 `invalidate_schema_cache(tenant_id)` 方法清除该租户的全部缓存

**微服务阶段：Redis 缓存**

拆分为独立服务后，OntologyService 调用走 gRPC，引入 Redis 缓存减少网络开销：

- Key 格式：`schema:{tenant_id}:{entity_type}:{rid}`
- TTL：300 秒（5 分钟）
- 失效策略同上，通过 gRPC 回调或消息通知清除

### 2.4 Connector 抽象层

Connector 封装底层数据源的差异，向查询引擎提供统一的访问接口。

#### 2.4.1 Connector 接口

```python
class Connector(Protocol):
    def execute_query(
        self,
        table_path: str,
        columns: list[str],
        filters: list[Filter],
        sort: list[SortSpec],
        pagination: Pagination,
        branch: str | None = None,
    ) -> QueryResult: ...

    def get_row(
        self,
        table_path: str,
        primary_key: dict[str, Any],
        columns: list[str],
        branch: str | None = None,
    ) -> dict[str, Any] | None: ...

    def test_connection(self) -> ConnectionTestResult: ...
```

查询引擎将 PropertyType 映射为物理列名后，通过 Connector 执行查询。Connector 负责生成底层存储的具体查询语句（SQL / Iceberg scan）。

#### 2.4.2 PostgreSQL Connector

- 将 `filters`、`sort`、`pagination` 翻译为标准 SQL
- 使用连接池管理数据库连接
- 支持参数化查询，防止 SQL 注入

#### 2.4.3 Iceberg Connector（via Nessie Catalog）

- 通过 PyIceberg + Nessie Catalog 访问 Iceberg 表
- `branch` 参数通过 Nessie 引用指定读取的分支（默认 `main`）
- 返回 Arrow RecordBatch，在应用层转换为标准结构

#### 2.4.4 Doris Connector（P3）

- 通过 MySQL 协议连接 Doris（Doris 兼容 MySQL 协议）
- 将 `filters`、`sort`、`pagination` 翻译为 SQL
- 作为热数据查询层，查询延迟亚秒级
- 忽略 `branch` 参数（Doris 仅存储 main 分支数据）

### 2.5 读取管道

数据实例的查询经过四个阶段：Schema 加载 → 查询执行 → Virtual Expression 计算 → 脱敏。

```
请求进入
  ↓
① Schema 加载：从 Ontology 获取 ObjectType/LinkType 定义 + AssetMapping
  ↓
② 查询引擎：api_name → 物理列映射 → 生成查询 → Connector 执行
  ↓
③ Virtual Expression：对结果集逐行计算虚拟字段
  ↓
④ 脱敏：按 ComplianceConfig 处理敏感字段
  ↓
返回结果
```

#### 2.5.1 Schema 加载

Data 仅加载 Ontology 的最新 Active 版本。

```
查询请求携带 type_rid（ri.obj.* 或 ri.link.*）
  1. 检查 Schema 缓存 → 命中则直接使用
  2. 缓存未命中 → 调用 OntologyService 获取类型定义（ObjectType 或 LinkType）
  3. 从定义中提取：
     - PropertyType 列表（api_name → physical_column / virtual_expression 映射）
     - AssetMapping（read_connection_id + read_asset_path）
     - ComplianceConfig（每个 PropertyType 的脱敏配置）
     - primary_key_property_type_rids
  4. 写入缓存（TTL 5 分钟）
  5. 根据 ComplianceConfig 计算 sortable_fields 和 filterable_fields（排除脱敏字段）
```

Ontology 发布新版本后 Data 如何感知：OntologyService 在发布完成后调用 DataService 的 `invalidate_schema_cache(tenant_id)` 方法清除该租户的全部 Schema 缓存。下次查询时重新加载最新定义。

#### 2.5.2 查询引擎

查询引擎将用户的高层筛选/排序请求翻译为存储层可执行的查询。

```
输入：
  - 类型定义（ObjectType 或 LinkType 的 PropertyType 列表 + AssetMapping）
  - 用户请求（filters, sort, pagination）

处理：
  1. 解析 AssetMapping → 获取 read_connection_id → 查找 Connection 配置 → 获取对应 Connector
  2. 解析 read_asset_path → 确定表路径
  3. 遍历用户 filters：
     a. field (api_name) → 查找对应 PropertyType
     b. PropertyType 有 physical_column → 映射为物理列名，加入 SQL 条件
     c. PropertyType 有 virtual_expression → 标记为应用层过滤（不下推）
  4. 构建物理列列表（按 PropertyType 的 physical_column 收集，排除 virtual_expression）
  5. 调用 Connector.execute_query(table_path, columns, filters, sort, pagination)

输出：
  - 行数据列表 + 分页信息
```

**Virtual Expression 的筛选和排序**无法下推到数据库，需在应用层完成。当用户对虚拟字段筛选时，查询引擎加载全量物理数据，在应用层计算虚拟字段后执行内存筛选和排序。对大数据量场景有性能影响，后续可优化为将表达式翻译为 SQL fragment 下推。

#### 2.5.3 Virtual Expression 计算

表达式语法支持基本算术运算（`+` `-` `*` `/`）、字段引用和内置函数（如 `CONCAT`、`IF`）。

**P0-P1 阶段：应用层计算**

```
对查询结果集的每一行：
  1. 遍历 PropertyType 中类型为 virtual_expression 的字段
  2. 解析表达式（如 "battery_level * 100"）
  3. 从当前行取出引用的物理字段值
  4. 计算结果，写入该行的虚拟字段
```

**P3 阶段：Doris 物化列**

引入 Doris 后，虚拟字段可作为物化列存储在 Doris 中：

```
Flink 同步 EditLog 到 Doris 时：
  1. 加载 ObjectType 的 PropertyType 定义
  2. 对 virtual_expression 类型的字段，根据表达式和物理字段值计算结果
  3. 将计算结果作为 Doris 表的普通列写入（物化）
  4. 查询时直接读取，无需应用层计算
```

**物化列的维护**：
- Ontology 变更（新增/修改/删除 virtual_expression）发布后，触发 Flink Job 重新全量计算受影响的物化列
- 查询优先级：有 Doris 物化列时直接读取；Doris 不可用或字段未物化时回退到应用层计算

#### 2.5.4 脱敏管道

脱敏在 Data 服务层统一执行，位于查询结果返回给调用方之前。所有消费方（前端、Function、Copilot）获取的都是已脱敏数据。

```
对查询结果集的每一行：
  1. 遍历每个 PropertyType 的 ComplianceConfig
  2. 如果 sensitivity > PUBLIC 且有 masking 策略：
     a. MASK_NULLIFY → 置为 null
     b. MASK_REDACT_FULL → 替换为 "***"
     c. SHOW_LAST_4 → 保留末 4 位
     d. MASK_PHONE_MIDDLE → 138****5678
     e. ...（按 ONTOLOGY.md 第 14 章定义的策略执行）
  3. 返回脱敏后的结果
```

**脱敏字段禁止排序和筛选**：

被脱敏的字段（sensitivity > PUBLIC 且 masking ≠ MASK_NONE）禁止参与排序和筛选。如果允许基于原始值排序，用户可通过排序位置反推原始数据（如手机号脱敏后排序，排序顺序泄露真实号码），属于信息泄露。

```
Schema 加载阶段：
  1. 遍历所有 PropertyType 的 ComplianceConfig
  2. sensitivity > PUBLIC 且 masking ≠ MASK_NONE 的字段标记为「已脱敏」
  3. 已脱敏字段从 sortable_fields 和 filterable_fields 中排除
  4. 前端据此禁用对应列的排序和筛选控件

查询引擎阶段：
  1. 收到 filter/sort 请求时，校验目标字段是否在 filterable_fields/sortable_fields 中
  2. 对已脱敏字段的筛选/排序请求返回 400（DATA_MASKED_FIELD_NOT_SORTABLE）
```

**设计选择**：
- 在服务层而非 SQL 层做脱敏，保证存储无关性（PostgreSQL / Iceberg 切换不影响）
- 初期全局一致（无角色区分），后续引入 RBAC 后在同一层扩展角色判断逻辑
- 已脱敏字段禁止排序和筛选，防止信息泄露

### 2.6 写回管道与读写一致性（Funnel Protocol）

数据写入由 Function 能力域发起（执行 Action），通过写回管道完成持久化。Data 不发起写入，但负责读取时合并未同步的编辑，保证 Read-after-Write 一致性。

#### 2.6.1 写入流程

```
Function 执行 Action（如：更新机器人状态）
  ↓
FoundationDB 事务：
  1. 开启 FDB 事务
  2. 获取行级锁：lock:{tenant_id}:{type_rid}:{pk_hash}
  3. 写入 EditLog：edit:{tenant_id}:{type_rid}:{pk_hash}:{timestamp}
     Value: { operation, primary_key, diff, user_id, action_type_rid, branch }
  4. 提交事务，释放锁
  ↓
返回"执行成功"给用户
  ↓
（此时编辑尚未同步到 Iceberg/Doris，但已可通过 FDB 读取）
```

Function 通过 AssetMapping 的 `writeback_connection_id` + `writeback_asset_path` 确定写入目标。写入不直接操作目标存储，而是先写入 FDB EditLog 作为编辑缓冲，由 Flink 异步同步到最终存储。

**FDB 事务的优势**：
- ACID 保证：行级锁 + EditLog 写入在同一事务中，不会出现"锁过期但写入成功"的不一致
- 极低延迟：FDB 针对小事务优化，写入 EditLog 毫秒级完成
- 顺序保证：同一实例的多次编辑通过 timestamp 排序

#### 2.6.2 Flink 异步同步

Flink CDC Job 持续监听 FDB EditLog 变更，将编辑同步到持久存储和查询服务层。

```
Flink CDC Job
  ↓
监听 FDB EditLog 变更
  ↓
路由分支：根据 EditLog 中的 branch 字段决定写入到哪个 Nessie 分支
  · branch = "main" 或空 → 写入 main 分支（常规操作）
  · branch = "simulation_v1" → 写入 simulation_v1 分支（数据实验）
  ↓
分支 A：Commit 到 Iceberg（冷数据持久化）
  · 根据 AssetMapping 的 writeback_asset_path 定位 Iceberg 表
  · 通过 Nessie Catalog 直接提交到目标分支（不经过暂存分支）
  · 写入 Iceberg 后数据不可丢失
  ↓
分支 B：Upsert 到 Doris（热数据加速）
  · 按主键（包括复合主键）Upsert
  · Doris 使用 Unique Key 模型，自动覆盖旧值
  · 仅同步 main 分支的数据（实验分支不写入 Doris）
  · 写入后亚秒级可查
  ↓
清理：确认 Iceberg + Doris 都落盘后，删除 FDB 中的 EditLog 条目
```

**Iceberg 直接写入目标分支的理由**：FDB EditLog 已经是编辑缓冲层，Iceberg 是最终持久化存储。如果再引入 Iceberg 暂存分支 → 合并的中间步骤，增加了不必要的复杂度。Nessie 分支管理是面向用户的数据实验能力（如 simulation_v1），不是系统内部写入流水线的一部分。

**Exactly-Once 保证**：Flink 启用 Checkpoint，保证 EditLog 不重复消费、不遗漏。

#### 2.6.3 读取时合并

在 Flink 尚未同步完成时，Data 通过合并基准数据和 FDB EditLog 保证 Read-after-Write 一致性。

**FDB 合并适用于所有分支**。无论查询的是 main 还是非 main 分支（如 simulation_v1），都执行相同的合并逻辑：读取当前分支的基准数据（Iceberg 对应分支 / Doris / PostgreSQL）+ 该分支的 FDB EditLog，在内存中合并。

```
Data 接收查询请求（branch 参数指定目标分支）
  ↓
并行查询：
  · AssetMapping 指向的 Connector（Doris / Iceberg / PostgreSQL）: 查询当前分支的基准数据
  · FDB: 扫描该 type_rid 下 branch = 当前分支 的未同步 EditLog
  ↓
内存合并：
  · 按主键（primary_key）匹配基准数据行和 EditLog 条目
  · FDB 中的 diff 覆盖基准数据的对应字段
  · operation = "create" → 新增行
  · operation = "delete" → 标记删除，从结果中移除
  ↓
Virtual Expression 计算
  ↓
脱敏
  ↓
返回合并后的最终结果
```

合并只涉及 FDB 中尚未清理的 EditLog（即 Flink 尚未同步的部分）。Flink 同步完成并清理 EditLog 后，后续查询直接从基准数据源获取最新数据，无需合并。

#### 2.6.4 初期简化方案

P0 阶段无 FDB、Flink、Doris，Data 仅提供只读查询：

```
Data 接收查询请求
  → PostgreSQL Connector 执行 SQL 查询
  → Virtual Expression 应用层计算
  → 脱敏
  → 返回
```

不支持写回，Function 执行 Action 的写入能力在 P2 阶段随 FDB 引入后开启。

### 2.7 热数据加速（Doris）

Doris 作为 OLAP 热数据服务层，承载面向用户的实时查询。

**角色定位**：
- Iceberg 是数据的持久化存储（冷数据、事实来源）
- Doris 是数据的服务层缓存（热数据、亚秒级查询）
- Flink 负责从 FDB EditLog / Iceberg 实时同步到 Doris

**与 AssetMapping 的关系**：

Doris 是另一种 Connection 类型（`type = "doris"`），在 Data 模块中注册为数据源连接。引入 Doris 后，将 ObjectType/LinkType 的 AssetMapping `read_connection_id` 更新为 Doris 连接即可。查询引擎始终通过 AssetMapping 路由到对应的 Connector，不需要特殊的 Doris 优先逻辑。

**Doris 表配置**：
- 使用 **Unique Key 模型**，Unique Key = ObjectType/LinkType 的 `primary_key_property_type_rids` 对应的物理列
- 支持复合主键：`primary_key_property_type_rids` 包含多个 PropertyType RID 时，Doris 建表使用多列作为 Unique Key，Flink 按复合键 Upsert
- 建表示例：ObjectType 的 primary_key 为 `[source_id, target_id]`，Doris 表的 Unique Key 为 `(source_id, target_id)`
- Flink Upsert 按 Unique Key 匹配，自动覆盖旧值
- 表结构包含物理列 + 虚拟字段的物化列（见 2.5.3 P3 阶段）

**Doris 表的自动建表与 Schema 同步**：

```
Ontology 发布新版本时：
  1. 检查变更的 ObjectType/LinkType 是否有 AssetMapping 指向 Doris 连接
  2. 新增 ObjectType/LinkType → 自动在 Doris 中创建对应表（Unique Key + 物理列 + VE 物化列）
  3. 新增 PropertyType（有 physical_column）→ ALTER TABLE 添加列
  4. 删除 PropertyType → ALTER TABLE 删除列
  5. 新增/修改 virtual_expression → 触发 Flink Job 重新计算物化列
  6. 删除 ObjectType/LinkType → 保留 Doris 表（不自动删除，避免误操作）
```

**Doris 存储原始值，不做脱敏**：

Doris 是内部基础设施，用户不直接访问。脱敏始终在 Data 服务层执行（见 2.5.4），无论数据来自 Doris、Iceberg 还是 PostgreSQL。Virtual Expression 物化列也存储原始计算结果——如果 VE 字段本身需要脱敏（其 PropertyType 配置了 ComplianceConfig），脱敏在服务层读出后执行。

### 2.8 数据版本管理（Nessie）

Nessie 为 Iceberg 数据提供 Git 风格的分支管理能力，实现数据隔离实验。

#### 2.8.1 分支操作

| 操作 | 说明 | Nessie API |
|------|------|-----------|
| 创建分支 | 从指定分支分叉，获得数据的隔离副本 | `POST /api/v2/trees` |
| 切换分支 | 所有查询切换到目标分支上下文 | 前端切换，请求携带 `branch` 参数 |
| 合并分支 | 将分支的变更原子性合并到目标分支 | `POST /api/v2/trees/{name}/merge` |
| 删除分支 | 删除不再需要的分支 | `DELETE /api/v2/trees/{name}` |

**典型场景**（数据实验）：

```
1. 数据科学家创建分支 simulation_v1（从 main 分叉）
2. 在 simulation_v1 上执行 Action（如批量更新机器人状态）
   · 写入通过 Flink 提交到 Iceberg 的 simulation_v1 分支
   · main 分支数据不受影响
3. 验证实验结果
4. 合并 simulation_v1 → main（Nessie 原子性合并指针）
5. 删除 simulation_v1 分支
```

#### 2.8.2 查询的分支上下文

实例查询请求通过 `branch` 参数指定读取的数据分支：

```
POST /data/v1/objects/{rid}/instances/query
{ ..., "branch": "simulation_v1" }
```

- 默认值为 `main`
- Iceberg Connector 根据 `branch` 参数设置 Nessie 引用，读取对应分支的表数据
- PostgreSQL 数据源忽略 `branch` 参数（不支持分支，始终返回主数据）
- 前端通过分支选择器切换，选中后所有查询自动携带 `branch` 参数

### 2.9 业务规则

#### 2.9.1 连接引用检测（删除前）

删除 Connection 前检查是否被 AssetMapping 引用：

```
DELETE /data/v1/connections/{rid}
  1. 调用 OntologyService 查询所有 AssetMapping 中引用该 connection_rid 的实体
  2. 存在引用 → 返回 409（DATA_CONNECTION_IN_USE），附带引用列表
  3. 无引用 → 执行删除
```

#### 2.9.2 Schema 变更感知

Ontology 发布新版本（schema 变更）时，Data 侧的处理：

- **新增 PropertyType**：若有 `physical_column`，查询自动包含新列（需物理表中存在该列）
- **删除 PropertyType**：查询不再包含该列，不影响物理表
- **修改 AssetMapping**：切换到新的数据源连接或表路径，下次查询即生效
- **破坏性变更**（如修改 data_type、删除 PropertyType 但物理列仍存在）：Data 侧不主动处理一致性，由 Ontology 发布校验阶段检测并阻止不安全的变更

#### 2.9.3 错误码

遵循 `TECH_DESIGN.md` 第 5 节的错误码体系，前缀 `DATA_`：

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `DATA_SOURCE_UNREACHABLE` | 503 | 数据源连接失败 |
| `DATA_SOURCE_NOT_FOUND` | 404 | Connection RID 不存在 |
| `DATA_CONNECTION_IN_USE` | 409 | 删除连接时被 AssetMapping 引用 |
| `DATA_QUERY_TIMEOUT` | 504 | 查询执行超时 |
| `DATA_SCHEMA_MISMATCH` | 422 | 物理列不存在或类型与 Ontology 定义不匹配 |
| `DATA_ASSET_NOT_FOUND` | 404 | AssetMapping 的 read_asset_path 无法解析（表不存在） |
| `DATA_ASSET_NOT_MAPPED` | 400 | ObjectType/LinkType 未配置 AssetMapping |
| `DATA_BRANCH_NOT_FOUND` | 404 | Nessie 分支不存在 |
| `DATA_BRANCH_CONFLICT` | 409 | 分支合并冲突 |
| `DATA_MASKING_ERROR` | 500 | 脱敏执行异常 |
| `DATA_MASKED_FIELD_NOT_SORTABLE` | 400 | 对已脱敏字段进行排序或筛选 |
| `DATA_EDITLOG_LOCK_CONFLICT` | 409 | FDB 行级锁冲突（实例正在被其他操作写入） |

---

## 3. 前端交互设计

### 3.1 页面结构

数据模块在 Main Stage 内采用 PRODUCT_DESIGN.md 定义的**侧边面板 + 内容区域**结构。

```
┌──────────────┬──────────────────────────────────────────┐
│  侧边面板     │  内容区域                                 │
│              │                                          │
│  概览        │                                          │
│  数据源      │     （类型选择 / 实例列表 / 详情页）        │
│  数据浏览    │                                          │
│  数据版本    │                                          │
│              │                                          │
│ ┌──────────┐ │                                          │
│ │ main  ▾  │ │                                          │
│ └──────────┘ │                                          │
└──────────────┴──────────────────────────────────────────┘
```

**侧边面板说明**：
- 4 个固定导航项：概览、数据源、数据浏览、数据版本
- 侧边面板**不展示**实体列表——点击"数据浏览"后，在内容区域展示类型选择页（见 3.3.1）
- 底部：分支选择器（下拉框），切换 Nessie 分支上下文。初期（无 Nessie）不显示

### 3.2 数据源管理

**列表页**（点击侧边面板"数据源"）：

| 列 | 内容 |
|----|------|
| 名称 | display_name |
| 类型 | postgresql / iceberg |
| 状态 | 连接状态指示灯（绿色 / 红色） |
| 引用数 | 被多少个 AssetMapping 引用 |
| 最近测试 | 时间戳 |

**操作**：
- 新建：弹出表单，填写连接信息 → 测试连接 → 保存
- 编辑：修改连接配置，凭证字段不显示明文
- 测试：手动触发连接测试，显示结果
- 删除：检查引用，有引用则展示引用列表阻止删除

**连接配置表单**（按类型动态渲染）：
- PostgreSQL：Host、Port、Database、Schema、用户名、密码
- Iceberg：Nessie URI、Warehouse 路径、凭证

### 3.3 数据浏览

#### 3.3.1 类型选择页

点击侧边面板"数据浏览"后，在**内容区域**展示类型选择页。

```
从 Ontology 获取所有 Active 的 ObjectType 和 LinkType
  → 过滤：有 AssetMapping 且 read_connection_id 和 read_asset_path 非空
  → 按 display_name 排序
  → 分组展示（ObjectType / LinkType）
```

类型以卡片或列表形式展示在内容区域，每个类型显示 display_name、description、PropertyType 数量。点击类型卡片 → 进入该类型的实例列表页。

#### 3.3.2 实例列表

**列动态生成**：根据 ObjectType/LinkType 的 PropertyType 列表动态生成表格列。

| 列信息来源 | 表头 | 渲染方式 |
|-----------|------|---------|
| PropertyType.display_name | 列标题 | — |
| PropertyType.data_type | 列数据类型 | 影响排序和筛选方式 |
| PropertyType.widget | 单元格渲染 | 按 WidgetConfig 渲染（文本、链接、状态标签、地图标记等） |
| PropertyType.backing | 列标记 | virtual_expression 列标记为"计算"图标 |

**交互**：
- 搜索：按主键或文本字段搜索
- 筛选：按列值筛选（筛选物理列下推到 SQL，筛选虚拟列在前端标注"性能提示"）。已脱敏字段的筛选控件禁用，Tooltip 提示"脱敏字段不支持筛选"
- 排序：点击列头排序。已脱敏字段的排序控件禁用，Tooltip 提示"脱敏字段不支持排序"
- 分页：标准分页控件
- 点击行：打开实例详情页

#### 3.3.3 实例详情

前端详情页并行调用 `/instances/get`（属性）+ 关系端点（关系数据）渲染完整页面。

**Object 实例详情**：

- **属性面板**：按 PropertyType 列表渲染属性字段，每个字段根据 WidgetConfig 选择展示组件。已脱敏字段按脱敏后的值显示
- **关系面板**（数据来自 `/instances/links`）：展示该 Object 通过 LinkType 关联的其他实例，分为出边（outgoing）和入边（incoming）。每条关系显示 LinkType 名称、Link 属性、对端实例标识。点击对端实例 → 打开对端详情页，点击 LinkType 名称 → 跳转到本体模块 LinkType 编辑器
- **操作链接**："在能力模块中执行操作" → 跳转到能力模块，展示可作用于该 ObjectType 的 ActionType 列表

**Inline Edit（设计预留）**：当前不实现。未来方向：实例详情页的属性字段支持直接编辑，背后关联一个 `SAFETY_IDEMPOTENT_WRITE` 级别的 NativeCRUD Action，用户修改属性值后自动触发 Action 执行 + 写回，无需跳转到能力模块。

**Link 实例详情**：

- **属性面板**：按 LinkType 的 PropertyType 列表渲染 Link 自身属性（如 connected_since、priority）
- **关联对象面板**（数据来自 `/instances/objects`）：展示 source Object 和 target Object 的摘要信息。点击 → 打开对应 Object 的详情页

### 3.4 分支管理

**分支管理页**（点击侧边面板"数据版本"）：

- 分支列表：所有 Nessie 分支（名称、创建时间、最新 commit）
- 创建分支：输入名称，选择源分支
- 合并分支：选择源分支和目标分支，预览差异，确认合并
- 删除分支：确认后删除（main 不可删除）

**分支选择器**（侧边面板底部）：

- 下拉框列出所有分支
- 切换分支后，数据浏览的所有查询自动携带新分支参数
- 切换时内容区域刷新，加载目标分支数据
- 当前分支非 main 时，侧边面板分支选择器高亮提示

### 3.5 概览页

侧边面板点击"概览"进入。

**内容**：
- 数据源状态卡片：连接总数、正常/异常数量
- 可浏览类型统计：已映射的 ObjectType / LinkType 数量
- 分支状态：当前活跃分支数、当前选中分支
- 最近活动：最近的查询和操作记录摘要

### 3.6 跨模块跳转

遵循 `PRODUCT_DESIGN.md` 第 6.6 节"引用即链接"原则。

**跳转到本体模块**：
- 实例列表页标题（ObjectType/LinkType 名称）→ 本体模块的对应编辑器
- 实例详情页的 LinkType 名称 → 本体模块的 LinkType 编辑器
- 数据源列表的"引用数"链接 → 本体模块的 AssetMapping 索引页（筛选该 connection）

**跳转到能力模块**：
- 实例详情页的"执行操作"链接 → 能力模块的 Action 执行页（预填实例引用参数）

**从本体模块跳入**：
- AssetMapping 中的 `connection_id` → 数据模块的数据源配置页

---

## 4. 实现优先级

| 阶段 | 范围 | 前置依赖 | 说明 |
|------|------|---------|------|
| P0 | 数据源连接管理 + PostgreSQL Connector + Schema 驱动查询 + 脱敏 + 实例浏览 | Ontology P0（类型定义 + AssetMapping） | 核心只读能力闭环：可配置数据源、浏览数据实例、脱敏生效 |
| P1 | Iceberg Connector + Nessie（Catalog + 分支管理） | MinIO / S3 部署 | 数据湖基础 + 数据版本：Iceberg 作为新数据源类型，Nessie 提供分支隔离 |
| P2 | FDB EditLog + 写回管道 | FDB 部署、Iceberg 可用 | 写入闭环：Function 执行 Action → FDB EditLog → 落盘到 Iceberg |
| P3 | Flink CDC + Doris 热数据层 | Flink 部署、FDB + Iceberg 可用 | 读写一致性加速：Flink 同步 EditLog 到 Doris + Iceberg，Data 读取时合并 FDB 未同步编辑 |

---
