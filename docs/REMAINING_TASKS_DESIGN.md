# 未完成功能技术方案设计

> **版本**: 1.0.0
> **创建日期**: 2026-03-13
> **状态**: 待开发
> **范围**: 20 项设计了但未完成的功能

---

## 总览

### 优先级分组与并行策略

```
Group A (Backend Ontology 核心)     ── Worktree 1
  ├── T1: 不可变字段保护
  ├── T2: InterfaceType 契约校验
  ├── T3: Schema 发布通知
  ├── T4: Neo4j 失败重试
  ├── T7: 快照字段级 Diff
  ├── T10: AssetMapping 查询端点
  ├── T12: PropertyType/AssetMapping 独立查询端点
  └── T15: SharedPropertyType 级联覆盖检测改进

Group B (Frontend Ontology + 通用前端)  ── Worktree 2
  ├── T5: 实体删除按钮（前端）
  ├── T8: 快照回滚（前端）
  ├── T9: AssetMapping 配置界面
  ├── T11: 拓扑可视化 (React Flow)
  └── T16: ActionType Monaco Editor

Group C (Frontend Function + Copilot)   ── Worktree 3
  ├── T13: 工作流 DAG 可视化编辑器
  ├── T14: Shell 面板真实 SSE 对话
  ├── T17: Setting 用户列表搜索/筛选
  └── T20: 数据浏览页搜索/筛选

Group D (Backend 进阶)               ── Worktree 4
  ├── T6: FoundationDB EditLog (标记为技术债务，当前 PG 代替可用)
  ├── T18: Sub-Agent 嵌套图集成（框架已有，需端到端测试）
  └── T19: Casbin RBAC 实际执行（model.conf 已有，开关激活）
```

---

## Group A: Backend Ontology 核心

### T1: 不可变字段保护

**问题**: 已发布（Active）实体的 `api_name`、`data_type`、`category`、`source_type` 可被任意修改，破坏下游系统。

**设计方案**:

```python
# ontology/validators/immutable.py

IMMUTABLE_FIELDS: dict[str, frozenset[str]] = {
    "ObjectType": frozenset({"api_name"}),
    "LinkType": frozenset({"api_name", "source_type", "target_type"}),
    "InterfaceType": frozenset({"api_name"}),
    "SharedPropertyType": frozenset({"api_name", "data_type"}),
    "ActionType": frozenset({"api_name"}),
    "PropertyType": frozenset({"api_name", "data_type"}),
}

async def check_immutable_fields(
    graph_repo: GraphRepository,
    label: str,
    rid: str,
    tenant_id: str,
    updates: dict[str, Any],
) -> None:
    """如果实体已有 Active 版本，禁止修改不可变字段。"""
    immutable = IMMUTABLE_FIELDS.get(label, frozenset())
    changed_immutable = immutable & updates.keys()
    if not changed_immutable:
        return

    # 检查是否存在 Active 节点（有 Active 说明已发布过）
    active = await graph_repo.get_active_node(label, rid, tenant_id)
    if not active:
        return  # 从未发布过，允许修改

    # 对比新旧值
    violations = []
    for field in changed_immutable:
        if updates[field] != active.get(field):
            violations.append(field)

    if violations:
        raise AppError(
            code=ErrorCode.ONTOLOGY_IMMUTABLE_FIELD,
            message=f"Cannot modify immutable fields on published {label}: {violations}",
            details={"fields": violations, "rid": rid},
        )
```

**集成点**: `service.py` → `_update_entity()` 方法中，在 `_require_lock` 之后调用。

**需要新增错误码**: `ONTOLOGY_IMMUTABLE_FIELD`

**测试用例**:
1. 未发布实体 → 允许修改 api_name ✓
2. 已发布实体 → 修改 api_name → 抛出 ONTOLOGY_IMMUTABLE_FIELD ✗
3. 已发布实体 → 修改 display_name（可变字段）→ 成功 ✓
4. 已发布实体 → api_name 值相同 → 允许（无实际变更）✓

---

### T2: InterfaceType 契约校验

**问题**: 修改 InterfaceType 的 required_properties 时，不会校验已实现此接口的 ObjectType/LinkType 是否满足新契约。

**设计方案**:

```python
# ontology/validators/contract.py

async def check_contract_satisfaction(
    graph_repo: GraphRepository,
    interface_rid: str,
    tenant_id: str,
    required_properties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """校验所有实现此 InterfaceType 的实体是否满足新契约。

    返回违规列表 [{"rid": ..., "missing_properties": [...]}]
    """
    # 1. 获取所有 IMPLEMENTS 此 interface 的 ObjectType/LinkType
    implementors = await graph_repo.get_incoming_referencing_rids(
        "InterfaceType", interface_rid, tenant_id, "IMPLEMENTS"
    )

    violations = []
    required_api_names = {p["api_name"] for p in required_properties}

    for impl_rid in implementors:
        # 2. 获取 implementor 的 PropertyTypes
        props = await graph_repo.get_related_nodes(
            "ObjectType", impl_rid, tenant_id,
            "BELONGS_TO", direction="incoming"
        )
        if not props:
            props = await graph_repo.get_related_nodes(
                "LinkType", impl_rid, tenant_id,
                "BELONGS_TO", direction="incoming"
            )

        existing_api_names = {p.get("api_name") for p in props}
        missing = required_api_names - existing_api_names

        if missing:
            violations.append({
                "rid": impl_rid,
                "missing_properties": sorted(missing),
            })

    return violations
```

**集成点**:
- `service.py` → `update_interface_type()` 中，当 `required_properties` 字段变更时调用
- `service.py` → `commit_staging()` 中，发布前校验所有 Staging 中的 InterfaceType 变更

**行为**:
- 更新 InterfaceType 时：违规则抛错 `ONTOLOGY_CONTRACT_VIOLATION`（附带违规详情）
- 发布时：违规则阻止发布（列出所有不满足契约的实体）

**测试用例**:
1. InterfaceType 新增 required_property → ObjectType 缺少该属性 → 报错
2. InterfaceType 新增 required_property → ObjectType 已有该属性 → 通过
3. ObjectType 实现新 InterfaceType → 缺少属性 → 报错
4. 发布时批量校验所有 Staging InterfaceType 变更

---

### T3: Schema 发布通知

**问题**: `on_schema_published()` 是 `pass`，发布后 Data 模块的 Schema 缓存不会刷新。

**设计方案**:

```python
# ontology/service.py → on_schema_published()

async def on_schema_published(
    self, tenant_id: str, snapshot_id: str, session: AsyncSession,
) -> None:
    """Schema 发布回调：通知依赖模块刷新缓存。"""
    # 1. 通过 Redis Pub/Sub 广播 schema_published 事件
    event = json.dumps({
        "event": "schema_published",
        "tenant_id": tenant_id,
        "snapshot_id": snapshot_id,
        "timestamp": datetime.utcnow().isoformat(),
    })
    await self._redis.publish(f"lingshu:schema:{tenant_id}", event)

    # 2. 直接失效 Data 模块的 schema 缓存 key
    cache_pattern = f"schema_cache:{tenant_id}:*"
    cursor = 0
    while True:
        cursor, keys = await self._redis.scan(cursor, match=cache_pattern, count=100)
        if keys:
            await self._redis.delete(*keys)
        if cursor == 0:
            break
```

**集成点**: `commit_staging()` 方法末尾，在 `session.commit()` 之后调用 `on_schema_published()`。

**Data 模块侧配合**: `data/pipeline/schema_loader.py` 中的缓存 key 需使用 `schema_cache:{tenant_id}:{entity_rid}` 格式。

**测试用例**:
1. 发布后 Redis 缓存 key 被清除
2. 发布后 Redis Pub/Sub 收到事件
3. Data 模块 SchemaLoader 在缓存失效后重新加载

---

### T4: Neo4j 失败重试

**问题**: `commit_staging()` 中 PG Snapshot 已提交但 Neo4j `promote_staging_to_active()` 失败时，状态不一致。

**设计方案**:

```python
# ontology/retry.py

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 5.0, 15.0]  # 秒

async def retry_neo4j_operation(
    operation: Callable[..., Awaitable[None]],
    *args: Any,
    operation_name: str = "neo4j_operation",
    redis: Redis | None = None,
    retry_key: str | None = None,
) -> bool:
    """带指数退避的 Neo4j 重试。

    失败后将任务写入 Redis 队列用于后台重试。
    返回 True 表示成功，False 表示所有重试均失败。
    """
    for attempt in range(MAX_RETRIES):
        try:
            await operation(*args)
            return True
        except Exception as e:
            logger.warning(
                "Neo4j %s failed (attempt %d/%d): %s",
                operation_name, attempt + 1, MAX_RETRIES, str(e),
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])

    # 所有重试失败 → 写入 Redis 死信队列
    if redis and retry_key:
        await redis.rpush(
            "lingshu:neo4j:retry_queue",
            json.dumps({
                "operation": operation_name,
                "args": [str(a) for a in args],
                "retry_key": retry_key,
                "failed_at": datetime.utcnow().isoformat(),
            })
        )
        logger.error(
            "Neo4j %s failed after %d retries. Queued for background retry: %s",
            operation_name, MAX_RETRIES, retry_key,
        )
    return False
```

**集成点**: `commit_staging()` 中替换直接调用：

```python
# 原来
await self._graph.promote_staging_to_active(tenant_id, snapshot_id)

# 改为
success = await retry_neo4j_operation(
    self._graph.promote_staging_to_active,
    tenant_id, snapshot_id,
    operation_name="promote_staging_to_active",
    redis=self._redis,
    retry_key=f"{tenant_id}:{snapshot_id}",
)
if not success:
    logger.error("Neo4j promotion failed for %s, PG committed. Manual intervention required.", snapshot_id)
```

**测试用例**:
1. Neo4j 首次成功 → 直接返回
2. Neo4j 首次失败、第二次成功 → 重试后成功
3. 所有重试失败 → 写入 Redis 队列 + 返回 False
4. 重试延迟符合预期

---

### T7: 快照字段级 Diff

**问题**: `get_diff()` 只返回实体级变更（哪些 RID 变了），不返回字段级差异。

**设计方案**:

```python
# ontology/repository/snapshot_repo.py → 新增 get_field_diff()

async def get_field_diff(
    self,
    snapshot_id: str,
    current_snapshot_id: str | None,
    graph_repo: GraphRepository,
    tenant_id: str,
) -> dict[str, Any]:
    """获取字段级 diff：对比快照中每个变更实体的具体字段差异。"""
    snap = await self.get_by_id(snapshot_id)
    if not snap:
        return {"changes": []}

    changes = []
    for rid, operation in snap.entity_changes.items():
        change_entry = {
            "rid": rid,
            "operation": operation,
            "field_changes": [],
        }

        if operation == "update":
            # 从 Neo4j 获取当前 Active 节点（代表快照后的状态）
            # 从快照时的 parent_snapshot 获取历史状态（需存储完整快照数据）
            # P0 简化方案：只标记"已变更"，不做字段级 diff
            # 完整方案：在 snapshot.entity_data 中存储快照时的完整节点数据
            pass

        changes.append(change_entry)

    return {"snapshot_id": snapshot_id, "changes": changes}
```

**完整实现需要**:
1. `Snapshot` 模型新增 `entity_data: dict[str, dict]` JSONB 列，存储快照时每个实体的完整属性
2. `commit_staging()` 发布时，将每个 Staging 节点的完整属性存入 `entity_data`
3. Diff 时对比 `entity_data[rid]` 与当前 Active 节点

**Alembic 迁移**: 新增 `entity_data` 列到 `snapshots` 表。

**测试用例**:
1. 创建快照时 entity_data 包含完整节点数据
2. Diff 返回字段级变更（old_value / new_value）
3. 新建实体 → 所有字段为 "added"
4. 删除实体 → 所有字段为 "removed"

---

### T10: AssetMapping 查询端点

**问题**: Data 模块无法查询哪些 AssetMapping 引用了某个 Connection，删除连接前无法检测引用。

**设计方案**:

```python
# ontology/service.py → 新增 query_asset_mapping_references()

async def query_asset_mapping_references(
    self,
    connection_rid: str,
) -> list[dict[str, Any]]:
    """查询引用指定 Connection 的所有 AssetMapping。"""
    tenant_id = get_tenant_id()
    references = []

    for label in ("ObjectType", "LinkType"):
        nodes, _ = await self._graph.list_active_nodes(
            label, tenant_id, offset=0, limit=1000
        )
        for node in nodes:
            data = _deserialize_from_neo4j(node)
            asset_mapping = data.get("asset_mapping")
            if asset_mapping and asset_mapping.get("connection_rid") == connection_rid:
                references.append({
                    "entity_rid": data.get("rid"),
                    "entity_type": label,
                    "api_name": data.get("api_name"),
                    "asset_mapping": asset_mapping,
                })

    return references
```

**Router 端点**: `GET /ontology/v1/asset-mappings/references?connection_rid=ri.conn.xxx`

**Data 模块集成**: `data/service.py` → `delete_connection()` 调用此端点检查引用。

**测试用例**:
1. ObjectType A 引用 connection_rid X → 返回 A
2. 无引用 → 返回空列表
3. 多个实体引用同一连接 → 全部返回

---

### T12: PropertyType/AssetMapping 独立查询端点

**设计方案**:

```python
# ontology/router.py → 新增端点

@router.post("/property-types/query")
async def query_property_types(request: QueryEntitiesRequest):
    """跨实体的 PropertyType 索引查询。"""
    service = get_ontology_service()
    results, total = await service.query_all_property_types(
        search=request.search,
        offset=request.pagination.offset if request.pagination else 0,
        limit=request.pagination.limit if request.pagination else 20,
    )
    ...

@router.post("/asset-mappings/query")
async def query_asset_mappings(request: QueryEntitiesRequest):
    """跨实体的 AssetMapping 索引查询。"""
    ...
```

**Service 层**: 遍历所有 ObjectType/LinkType 的 PropertyType 节点，聚合返回。

**测试用例**:
1. 查询所有 PropertyType → 返回分页结果
2. 按 api_name 搜索 → 过滤匹配
3. AssetMapping 查询 → 返回所有配置了映射的实体

---

### T15: SharedPropertyType 级联覆盖检测改进

**问题**: 当前用 `_override_{field}` flag 判断是否覆盖，但该字段未在 Proto 中定义，也未在 UI 中设置。

**设计方案**: 改为**值比较**策略：

```python
# ontology/validators/cascade.py → 改进

async def cascade_shared_property_update(
    graph_repo: GraphRepository,
    shared_rid: str,
    tenant_id: str,
    updated_fields: dict[str, Any],
    old_shared_values: dict[str, Any],  # 新增参数：更新前的 SharedProperty 值
) -> list[str]:
    """值比较策略：如果 PropertyType 的值 == SharedProperty 的旧值，说明未被覆盖，执行级联。"""
    cascadable = {k: v for k, v in updated_fields.items() if k in CASCADE_FIELDS}
    if not cascadable:
        return []

    inheritors = await graph_repo.get_related_nodes(
        "SharedPropertyType", shared_rid, tenant_id,
        "BASED_ON", direction="incoming",
    )

    affected_rids: list[str] = []
    for prop_node in inheritors:
        prop_rid = prop_node.get("rid", "")
        updates: dict[str, Any] = {}
        for field, new_value in cascadable.items():
            old_shared_value = old_shared_values.get(field)
            current_prop_value = prop_node.get(field)
            # 如果 PropertyType 当前值 == SharedProperty 旧值 → 未被覆盖 → 级联
            if current_prop_value == old_shared_value:
                updates[field] = new_value

        if updates:
            await graph_repo.update_node("PropertyType", prop_rid, tenant_id, updates)
            affected_rids.append(prop_rid)

    return affected_rids
```

**集成点**: `service.py` → `update_shared_property_type()` 中，更新前先读取旧值传入。

**测试用例**:
1. PropertyType 值 == SharedProperty 旧值 → 级联更新 ✓
2. PropertyType 值 != SharedProperty 旧值（用户已覆盖）→ 不级联 ✓
3. 混合场景 → 部分级联 ✓

---

## Group B: Frontend Ontology + 通用前端

### T5: 实体删除按钮（前端）

**设计方案**: 在所有 Ontology 实体详情页（ObjectType/LinkType/InterfaceType/SharedPropertyType/ActionType）添加删除按钮。

```tsx
// 在每个 [rid]/page.tsx 的 header 区域添加：
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive" size="sm">
      <Trash2 className="size-4 mr-1" /> Delete
    </Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete {entity.api_name}?</AlertDialogTitle>
      <AlertDialogDescription>
        This will create a deletion marker in Draft. The entity will be
        permanently removed when published. This action cannot be undone after publishing.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

**API 调用**: 复用已有 `ontologyApi.deleteObjectType(rid)` 等方法。

**流程**: 点击删除 → 确认对话框 → 调用 DELETE API → 成功后跳转列表页。

**注意**: 需要先获取编辑锁才能删除（与后端逻辑一致），UI 需要提示 "需要先锁定实体"。

**测试用例**:
1. 删除按钮可见
2. 点击删除 → 弹出确认对话框
3. 确认后 → 调用 API → 跳转列表页
4. 有依赖时 → 显示错误消息（哪些实体引用了它）

---

### T8: 快照回滚（前端）

**设计方案**: 在 `ontology/versions/page.tsx` 的 Snapshot History 表格中，每行添加 "Rollback" 按钮。

```tsx
// versions/page.tsx → Snapshot 表格列新增
{
  id: "actions",
  header: "Actions",
  cell: ({ row }) => (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={row.original.snapshot_id === currentSnapshotId}>
          <RotateCcw className="size-3 mr-1" /> Rollback
        </Button>
      </AlertDialogTrigger>
      ...
    </AlertDialog>
  ),
}
```

**API**: `POST /ontology/v1/snapshots/{snapshot_id}/rollback`（已有后端实现）

**前置条件提示**: 如果有未提交的 Draft/Staging 变更，显示错误 "请先提交或丢弃当前变更"。

**测试用例**:
1. 当前快照 → Rollback 按钮禁用
2. 历史快照 → 点击 Rollback → 确认 → 成功
3. 有 Draft/Staging → Rollback → 显示错误

---

### T9: AssetMapping 配置界面

**设计方案**: 替换 ObjectType 详情页 "Data Mapping" tab 的 placeholder。

```tsx
// 新建 components/ontology/asset-mapping-editor.tsx

interface AssetMappingEditorProps {
  entityRid: string;
  assetMapping: AssetMapping | null;
  onSave: (mapping: AssetMapping) => void;
  readOnly?: boolean;
}

// 表单字段：
// - connection_rid: Select（从 Data 模块获取可用连接列表）
// - schema_name: Input
// - table_name: Input
// - column_mappings: 动态表格（property_api_name → physical_column_name）
```

**数据流**:
1. 从 `dataApi.queryConnections()` 获取可用连接列表
2. 用户选择连接 → 填写 schema/table → 配置列映射
3. 保存时调用 `ontologyApi.updateObjectType(rid, { asset_mapping: {...} })`

**测试用例**:
1. 无映射时显示空表单
2. 有映射时回显已有配置
3. 修改并保存 → 调用 updateObjectType

---

### T11: 拓扑可视化 (React Flow)

**设计方案**: 替换 Overview 页面 "Topology View (Coming Soon)" 占位符。

```tsx
// 新建 components/ontology/topology-graph.tsx

import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react';

// 从 ontologyApi.getTopology() 获取 { nodes, edges }
// 节点类型映射颜色:
// - ObjectType → 蓝色
// - LinkType → 绿色
// - InterfaceType → 紫色
// - ActionType → 橙色
// - SharedPropertyType → 青色

// 边类型:
// - IMPLEMENTS → 虚线
// - EXTENDS → 粗线
// - CONNECTS → 实线 + 箭头
// - OPERATES_ON → 点线
// - BASED_ON → 细线
```

**依赖**: `@xyflow/react`（检查是否已安装，否则 `pnpm add @xyflow/react`）

**交互**: 点击节点 → 导航到对应实体详情页

**测试用例**:
1. 空数据 → 显示 "No entities yet"
2. 有数据 → 渲染节点和边
3. 点击节点 → 路由跳转

---

### T16: ActionType Monaco Editor

**设计方案**: 替换 ActionType 详情页 "Execution Config" tab 的 placeholder。

```tsx
// 使用已安装的 @monaco-editor/react

import Editor from '@monaco-editor/react';

<Editor
  height="400px"
  language="json"
  value={JSON.stringify(actionType.execution, null, 2)}
  onChange={(value) => setExecutionConfig(value)}
  options={{
    minimap: { enabled: false },
    lineNumbers: 'on',
    scrollBeyondLastLine: false,
    automaticLayout: true,
  }}
/>
```

**验证**: 保存前 JSON.parse 校验，失败显示错误提示。

---

## Group C: Frontend Function + Copilot

### T13: 工作流 DAG 可视化编辑器

**设计方案**: 在 `function/workflows/[rid]/page.tsx` 中添加 React Flow 可视化编辑。

```tsx
// 保留现有表单编辑作为 "Source" tab
// 新增 "Visual" tab 使用 React Flow

// 自定义节点类型:
// - ActionNode: 显示 Action 名称 + safety badge
// - FunctionNode: 显示 Global Function 名称
// - ConditionNode: 菱形节点，显示条件表达式
// - WaitNode: 沙漏图标

// 交互:
// - 从侧边面板拖入新节点
// - 连线创建边
// - 双击节点编辑参数
// - Visual ↔ Source 双向同步
```

**测试用例**:
1. 现有 workflow 数据 → 正确渲染 DAG 图
2. 添加节点 → 反映到 Source tab
3. 连线 → 创建边关系

---

### T14: Shell 面板真实 SSE 对话

**设计方案**: 替换 Shell 面板的 echo stub，接入真实 Copilot SSE。

```tsx
// components/layout/shell.tsx → 改造

import { useCopilot } from "@/hooks/use-copilot";
import { A2UIRenderer } from "@/components/a2ui/renderer";

// 1. 使用 useCopilot hook 管理 SSE 连接
// 2. Shell 打开时自动创建/恢复 session
// 3. 发送消息 → copilotApi.sendMessage() → SSE 流
// 4. 渲染 A2UI 组件（表格、卡片等）
// 5. 同步当前页面上下文（module, page, entity_rid）

// 关键改动:
// - 移除 setTimeout echo stub
// - 引入 useCopilot hook
// - 添加 A2UIRenderer 渲染
// - 添加 context 同步逻辑
```

**测试用例**:
1. 打开 Shell → 创建/恢复 session
2. 发送消息 → 流式接收响应
3. 收到 A2UI 事件 → 正确渲染组件
4. 页面切换 → 上下文更新

---

### T17: Setting 用户列表搜索/筛选

**设计方案**: 连接 UI 搜索框到 API 查询。

```tsx
// setting/users/page.tsx

// 将 search 和 roleFilter state 连接到 queryFn:
const { data } = useQuery({
  queryKey: ["users", search, roleFilter, page],
  queryFn: () => settingApi.queryUsers({
    pagination: { page, page_size: 20 },
    search: search || undefined,
    filters: roleFilter ? [{ field: "role", operator: "eq", value: roleFilter }] : undefined,
  }),
});

// 添加防抖搜索:
const debouncedSearch = useDebouncedValue(searchInput, 300);
```

---

### T20: 数据浏览页搜索/筛选

**设计方案**: 连接 Data Browse 页面的搜索/筛选 UI 到实例查询 API。

```tsx
// data/browse/[typeKind]/[typeRid]/page.tsx

// 将 filter/sort state 传入查询:
const { data } = useQuery({
  queryKey: ["instances", typeRid, filters, sortBy, page],
  queryFn: () => dataApi.queryInstances(typeRid, {
    pagination: { page, page_size: 20 },
    filters,
    sort: sortBy ? [{ field: sortBy.field, direction: sortBy.direction }] : undefined,
  }),
});
```

---

## Group D: Backend 进阶

### T6: FoundationDB EditLog（标记为技术债务）

**现状**: PostgreSQL `edit_logs` 表作为 FDB 代理，抽象层 (`EditLogStore`) 已就绪。

**方案**: 当前阶段保持 PG 代理不变，添加 TODO 注释和文档标记。后续 P3 阶段接入真实 FDB 时只需替换 `EditLogStore` 实现。

**本次行动**: 添加 `# TODO(P3): Replace with real FoundationDB client` 注释 + 在 CLAUDE.md 踩坑记录中记录。

---

### T18: Sub-Agent 嵌套图集成

**现状**: `SubAgentManager` 框架已搭好，但缺少端到端测试和模型配置文档。

**方案**: 添加集成测试 + 配置示例，确保当 Model 表中有配置好的 LLM 时，Sub-Agent 能正确调用。

---

### T19: Casbin RBAC 实际执行

**现状**: `model.conf` 已支持 RBAC，但 enforcer 在 P0 默认 allow-all。

**设计方案**: 添加环境变量开关 `LINGSHU_RBAC_ENABLED=true`

```python
# setting/authz/enforcer.py

class CasbinEnforcer:
    def __init__(self, model_path: str, adapter, rbac_enabled: bool = False):
        self._rbac_enabled = rbac_enabled
        ...

    async def check_permission(self, sub: str, obj: str, act: str) -> bool:
        if not self._rbac_enabled:
            return True  # P0 allow-all
        return await self._enforcer.enforce(sub, obj, act)
```

**测试用例**:
1. `RBAC_ENABLED=false` → 所有请求通过
2. `RBAC_ENABLED=true` + admin → 所有请求通过
3. `RBAC_ENABLED=true` + viewer → 写操作拒绝

---

## 开发顺序与依赖

```
第一批（无依赖，可并行）:
  Group A: T1, T4, T15 → T2, T3 → T7, T10, T12
  Group B: T5, T8, T16 → T9, T11
  Group C: T14, T17, T20 → T13
  Group D: T6, T19 → T18

第二批（有依赖）:
  T3 依赖 T7 (发布通知需要快照数据)
  T9 依赖 T10 (AssetMapping UI 需要查询端点)
  T2 依赖 T12 (契约校验需要 PropertyType 查询)
```

---

## TDD 验证清单

每个任务完成后必须通过：

- [ ] 测试先写（RED）
- [ ] 实现代码（GREEN）
- [ ] 覆盖率 ≥ 80%
- [ ] ruff check + ruff format（后端）
- [ ] pnpm lint + pnpm build（前端）
- [ ] 已有 E2E 测试不回归
