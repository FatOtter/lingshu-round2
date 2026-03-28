# LingShu 完整测试方案

> **版本**: 1.0.0
> **创建日期**: 2026-03-13
> **适用范围**: 全平台（后端 5 模块 + 前端 5 模块 + 基础设施）
> **测试策略**: 金字塔 + 真实场景 + 浏览器自动化

---

## 总览

### 测试金字塔

```
                    ┌─────────────┐
                    │  E2E Browser │  ← 15 个关键用户旅程（Playwright 真实浏览器）
                   ┌┘  Tests (L4) └┐
                  ┌┘               └┐
                 ┌┘  Business Flow   └┐  ← 12 个端到端业务场景（API 级真实调用）
                ┌┘    Tests (L3)      └┐
               ┌┘                      └┐
              ┌┘   Integration Tests    └┐  ← 模块间交互 + 真实 DB（Docker）
             ┌┘        (L2)              └┐
            ┌┘                            └┐
           ┌┘       Unit Tests (L1)        └┐  ← 纯逻辑 + Mock，快速执行
          └────────────────────────────────────┘
```

### 测试分层目标

| 层级 | 名称 | 数量目标 | 执行时间 | 执行频率 | 覆盖率 |
|------|------|---------|---------|---------|--------|
| L1 | 单元测试 | 500+ | < 30s | 每次提交 | ≥ 80% |
| L2 | 集成测试 | 80+ | < 3min | 每次 PR | 关键路径 100% |
| L3 | 业务场景测试 | 12 | < 5min | 每次 PR | 核心业务 100% |
| L4 | 浏览器 E2E | 15 旅程 / 80+ 断言 | < 10min | 每日 + 发布前 | 关键页面 100% |

---

## 第一部分：L1 单元测试

### 1.1 回归测试（现有功能保护）

> 目标：确保 20 项新功能的代码不破坏已有行为

#### 1.1.1 后端回归矩阵

| 模块 | 已有测试文件 | 回归重点 |
|------|------------|---------|
| Ontology Service | `test_service.py` (28 tests) | `_update_entity` 流程未被不可变字段校验破坏；`commit_staging` 流程未被重试/通知逻辑破坏 |
| Ontology Validators | `test_validators.py` (14 tests) | 依赖检测、循环检测逻辑不变 |
| Ontology Graph Repo | `test_graph_repo.py` | 节点 CRUD、关系管理不变 |
| Setting Enforcer | `test_enforcer.py` | RBAC 开关 off 时行为与改动前完全一致 |
| Setting Provider | `test_provider.py` | JWT 签发/校验不受影响 |
| Setting Middleware | `test_middleware.py` | Auth 中间件不受影响 |
| Copilot Agent | `test_agent.py` | Agent graph 构建不受 sub-agent bug 修复影响 |
| Function Service | `test_service.py` | 执行管道不受影响 |
| Data Pipeline | `test_query_engine.py` | 查询引擎不受影响 |

**执行命令**:
```bash
cd backend && uv run pytest tests/unit/ -v --tb=short -x  # -x 首个失败即停止
```

#### 1.1.2 前端回归矩阵

| 模块 | 已有测试文件 | 回归重点 |
|------|------------|---------|
| API Clients | `ontology.test.ts`, `data.test.ts`, `setting.test.ts`, `copilot.test.ts`, `function.test.ts` | 分页格式、请求参数不变 |
| Auth Hook | `use-auth.test.ts` | 认证流程不变 |
| Stores | `auth-store.test.ts`, `shell-store.test.ts`, `tab-store.test.ts` | 状态管理不变 |
| A2UI Renderer | `renderer.test.tsx` | 组件渲染分发不变 |
| SSE Client | `sse.test.ts` | SSE 连接管理不变 |

**执行命令**:
```bash
cd frontend && pnpm test -- --run  # 单次运行
```

---

### 1.2 新功能单元测试（20 项新功能）

#### Group A: 后端 Ontology 新功能（已完成 111 tests）

| 测试文件 | 覆盖任务 | 测试数 | 关键用例 |
|---------|---------|--------|---------|
| `test_immutable_fields.py` | T1 | 12 | 未发布可改、已发布禁改、相同值允许、可变字段放行 |
| `test_contract.py` | T2 | 10 | 缺属性报错、满足契约通过、发布前批量校验 |
| `test_schema_notification.py` | T3 | 5 | 缓存清除、Pub/Sub 广播、空缓存无异常 |
| `test_retry.py` | T4 | 9 | 首次成功、重试后成功、全部失败入队列、延迟验证 |
| `test_field_diff.py` | T7 | 13 | 新建/更新/删除 diff、entity_data 存储、空快照处理 |
| `test_asset_mapping_query.py` | T10 | 5 | 有引用返回、无引用空列表、多实体引用 |
| `test_independent_queries.py` | T12 | 9 | PropertyType 分页、AssetMapping 分页、搜索过滤 |
| `test_cascade_improved.py` | T15 | 8 | 值相同级联、值不同不级联、混合场景 |

#### Group D: 后端进阶（已完成 28 tests）

| 测试文件 | 覆盖任务 | 测试数 | 关键用例 |
|---------|---------|--------|---------|
| `test_rbac_activation.py` | T19 | 14 | RBAC off 放行、RBAC on + admin 全权、viewer 只读、member 限写、无角色拒绝 |
| `test_subagent_integration.py` | T18 | 14 | 工具加载、Schema 生成、执行结构、错误处理 |

---

### 1.3 需要新增的单元测试

#### 1.3.1 前端新组件测试

```
frontend/src/components/ontology/topology-graph.test.tsx     — T11
frontend/src/components/ontology/asset-mapping-editor.test.tsx — T9
frontend/src/components/ontology/execution-config-editor.test.tsx — T16
frontend/src/components/workflow/dag-viewer.test.tsx          — T13
frontend/src/hooks/use-debounce.test.ts                       — T17/T20
```

| 测试文件 | 用例数 | 关键断言 |
|---------|--------|---------|
| `topology-graph.test.tsx` | 5 | 空数据渲染空状态；有数据渲染 SVG 节点；节点颜色按类型；点击节点触发导航回调 |
| `asset-mapping-editor.test.tsx` | 6 | 空映射显示空表单；回显已有配置；添加/删除列映射行；保存调用 API；连接列表加载 |
| `execution-config-editor.test.tsx` | 4 | 回显 JSON；无效 JSON 显示错误；格式化按钮；保存调用 API |
| `dag-viewer.test.tsx` | 5 | 空 DAG 渲染空状态；节点按类型着色；边渲染曲线；条件边显示标签；多层布局正确 |
| `use-debounce.test.ts` | 3 | 延迟触发；快速输入只触发一次；延迟值正确 |

#### 1.3.2 前端页面删除功能测试

```
frontend/src/app/(authenticated)/ontology/object-types/[rid]/page.test.tsx
```

| 测试文件 | 用例数 | 关键断言 |
|---------|--------|---------|
| 各实体 `[rid]/page.test.tsx` | 4×5 | 删除按钮渲染；确认对话框弹出；确认后 API 调用；依赖冲突错误提示 |

---

## 第二部分：L2 集成测试

### 2.1 已有集成测试（6 个文件，需回归）

| 文件 | 场景 | 用例数 |
|------|------|--------|
| `test_auth_flow.py` | 登录→JWT→刷新→登出→审计日志 | ~15 |
| `test_ontology_workflow.py` | 创建→编辑→提交→发布 | ~12 |
| `test_data_pipeline.py` | 数据源→查询→脱敏 | ~10 |
| `test_function_execution.py` | Action 加载→参数解析→执行→审计 | ~12 |
| `test_copilot_session.py` | 会话创建→消息→checkpoint | ~10 |
| `test_rbac.py` | 角色分配→权限执行→拒绝 | ~12 |

### 2.2 新增集成测试（覆盖 20 项新功能的跨模块交互）

#### IT-01: 不可变字段 + 版本管理集成

```python
# backend/tests/integration/test_immutable_integration.py

class TestImmutableFieldIntegration:
    """端到端验证：创建 → 发布 → 尝试修改不可变字段。"""

    async def test_unpublished_entity_allows_api_name_change(self):
        """Draft 状态可改 api_name"""
        # 1. 创建 ObjectType（Draft 状态）
        # 2. 获取编辑锁
        # 3. 修改 api_name → 成功
        # 4. 释放锁

    async def test_published_entity_blocks_api_name_change(self):
        """发布后不可改 api_name"""
        # 1. 创建 ObjectType
        # 2. submit_to_staging → commit_staging（发布）
        # 3. 获取编辑锁
        # 4. 修改 api_name → ONTOLOGY_IMMUTABLE_FIELD 错误
        # 5. 修改 display_name → 成功

    async def test_published_link_type_blocks_source_target_change(self):
        """发布后不可改 source_type/target_type"""
```

#### IT-02: 契约校验 + 发布流程集成

```python
# backend/tests/integration/test_contract_integration.py

class TestContractIntegration:
    """端到端验证：InterfaceType 契约 → ObjectType 实现 → 发布校验。"""

    async def test_publish_fails_with_unsatisfied_contract(self):
        """发布时 ObjectType 不满足 InterfaceType 契约 → 阻止发布"""
        # 1. 创建 InterfaceType（required: [prop_a, prop_b]）
        # 2. 创建 ObjectType IMPLEMENTS InterfaceType（只有 prop_a）
        # 3. 两者 submit_to_staging
        # 4. commit_staging → ONTOLOGY_CONTRACT_VIOLATION（缺 prop_b）

    async def test_publish_succeeds_with_satisfied_contract(self):
        """ObjectType 满足所有契约 → 发布成功"""

    async def test_update_interface_contract_after_publish(self):
        """已发布后修改 InterfaceType 契约 → 校验已实现的 ObjectType"""
```

#### IT-03: Schema 发布通知 + 缓存刷新集成

```python
# backend/tests/integration/test_schema_notification_integration.py

class TestSchemaNotificationIntegration:
    """端到端验证：发布 → Redis 缓存清除 → Data 模块重新加载。"""

    async def test_publish_clears_schema_cache(self):
        """发布后相关 Redis 缓存 key 被删除"""
        # 1. 预设 Redis 缓存 key: ontology:cache:tenant1:ri.obj.xxx
        # 2. 发布 Staging
        # 3. 验证缓存 key 已被删除

    async def test_publish_sends_pubsub_event(self):
        """发布后 Redis Pub/Sub 收到 schema_published 事件"""
        # 1. 订阅 ontology:schema_published:tenant1
        # 2. 发布 Staging
        # 3. 验证收到事件（包含 tenant_id, snapshot_id）
```

#### IT-04: Neo4j 重试 + 一致性验证

```python
# backend/tests/integration/test_retry_integration.py

class TestRetryIntegration:
    """验证 Neo4j 失败重试机制。"""

    async def test_neo4j_transient_failure_retry_succeeds(self):
        """Neo4j 瞬时失败 → 重试成功 → PG/Neo4j 状态一致"""

    async def test_neo4j_permanent_failure_queues_retry(self):
        """Neo4j 持续失败 → 写入 Redis 死信队列"""

    async def test_pg_committed_neo4j_failed_state(self):
        """PG 已提交但 Neo4j 失败 → 检查不一致标记"""
```

#### IT-05: RBAC + 跨模块权限集成

```python
# backend/tests/integration/test_rbac_cross_module.py

class TestRbacCrossModule:
    """端到端验证 RBAC 在各模块的实际效果。"""

    async def test_viewer_can_read_ontology_but_not_write(self):
        """viewer 角色可查询 ObjectType 但不可创建"""

    async def test_member_can_create_ontology_but_not_manage_users(self):
        """member 角色可创建 ObjectType 但不可管理用户"""

    async def test_admin_can_do_everything(self):
        """admin 角色无限制"""

    async def test_rbac_disabled_allows_viewer_to_write(self):
        """RBAC 关闭时 viewer 也可写"""
```

#### IT-06: AssetMapping 引用检测 + 数据源删除集成

```python
# backend/tests/integration/test_asset_mapping_integration.py

class TestAssetMappingIntegration:
    """端到端验证：AssetMapping 引用检测 → 阻止删除。"""

    async def test_delete_connection_blocked_by_asset_mapping(self):
        """ObjectType 引用了 Connection → 删除 Connection 被阻止"""
        # 1. 创建 Connection
        # 2. 创建 ObjectType + AssetMapping 引用此 Connection
        # 3. 尝试删除 Connection → 返回引用列表

    async def test_delete_connection_allowed_when_no_references(self):
        """无引用 → 删除成功"""
```

#### IT-07: 级联更新 + 值比较集成

```python
# backend/tests/integration/test_cascade_integration.py

class TestCascadeIntegration:
    """端到端验证：SharedPropertyType 级联更新的值比较策略。"""

    async def test_cascade_updates_non_overridden_properties(self):
        """PropertyType 未覆盖 → 跟随 SharedPropertyType 更新"""
        # 1. 创建 SharedPropertyType（display_name="原始"）
        # 2. 创建 ObjectType → PropertyType 继承自 SharedPropertyType
        # 3. 更新 SharedPropertyType display_name="新名称"
        # 4. 验证 PropertyType display_name == "新名称"

    async def test_cascade_skips_overridden_properties(self):
        """PropertyType 已手动修改 → 不跟随级联"""
        # 1. 创建 SharedPropertyType（display_name="原始"）
        # 2. 创建 PropertyType 继承自 SharedPropertyType
        # 3. 手动修改 PropertyType display_name="自定义"
        # 4. 更新 SharedPropertyType display_name="新名称"
        # 5. 验证 PropertyType display_name 仍为 "自定义"
```

**执行命令**:
```bash
# 需要 Docker 环境
cd backend && uv run pytest tests/integration/ -v --tb=short
```

---

## 第三部分：L3 业务场景测试（真实场景）

> 使用真实 Docker 环境、真实数据库、真实 API 调用，模拟完整业务流程。

### 3.1 场景定义

#### BS-01: 智慧城市交通管理系统建模

```
角色: 数据架构师
目标: 建立交通管理本体模型

步骤:
1. 登录系统（admin@lingshu.dev）
2. 创建 SharedPropertyType:
   - "地理坐标" (data_type: GeoPoint)
   - "状态码" (data_type: Integer, validation: enum [0,1,2])
3. 创建 InterfaceType "可定位设备":
   - required_properties: ["地理坐标"]
4. 创建 ObjectType "交通信号灯":
   - implements: ["可定位设备"]
   - properties: ["地理坐标"(继承), "信号状态"(data_type: Integer), "路口名称"(String)]
5. 创建 ObjectType "摄像头":
   - implements: ["可定位设备"]
   - properties: ["地理坐标"(继承), "在线状态"(Boolean), "安装日期"(Date)]
6. 创建 LinkType "监控范围":
   - source: 摄像头, target: 交通信号灯
   - cardinality: many-to-many
7. 创建 ActionType "重启设备":
   - operates_on: 交通信号灯
   - safety_level: high
   - parameters: [device_rid, reason]
8. 提交所有到 Staging
9. 发布（commit_staging）
10. 验证 Active 版本所有实体可查询
11. 验证拓扑图展示正确的节点和关系

验证点:
✓ 继承的属性自动填充
✓ InterfaceType 契约校验通过
✓ 发布后 api_name 不可修改
✓ 依赖检测：删除"可定位设备"被阻止（有实现者）
✓ LinkType source/target 关联正确
```

#### BS-02: 数据源接入与实例查询

```
角色: 数据工程师
目标: 连接 PostgreSQL 数据源，浏览交通信号灯实例

步骤:
1. 创建数据源连接（PostgreSQL）
2. 测试连接（test connection）
3. 为 ObjectType "交通信号灯" 配置 AssetMapping:
   - connection_rid: 步骤 1 的连接
   - schema: public
   - table: traffic_lights
   - 列映射: 信号状态 → signal_status, 路口名称 → intersection_name
4. 查询实例列表（分页、排序、筛选）
5. 查看单个实例详情
6. 验证脱敏字段显示 "***"

验证点:
✓ 连接测试成功
✓ AssetMapping 保存并回显
✓ 查询返回正确数据
✓ 分页/排序/筛选工作正常
✓ 脱敏配置生效
```

#### BS-03: Action 执行与安全确认

```
角色: 运维人员
目标: 执行"重启设备"Action

步骤:
1. 进入能力模块 → 能力列表
2. 找到"重启设备"Action
3. 填写参数（device_rid, reason）
4. 因为 safety_level=high → 系统弹出确认
5. 用户确认执行
6. 查看执行结果
7. 查看执行历史
8. 审计日志记录此操作

验证点:
✓ 安全级别提示正确
✓ 确认流程完整
✓ 执行结果返回
✓ 审计日志可查
```

#### BS-04: Copilot 对话与 A2UI 渲染

```
角色: 业务分析师
目标: 通过 Copilot 查询数据

步骤:
1. 打开 Agent Chat 页面
2. 发送消息："列出所有交通信号灯"
3. Agent 调用 list_object_types + query_instances
4. 返回 A2UI Table 组件渲染结果
5. 发送消息："重启编号 TL-001 的信号灯"
6. Agent 调用"重启设备"Action → 触发确认
7. A2UI ConfirmationCard 渲染
8. 用户点击"确认"
9. Agent 完成执行并返回结果

验证点:
✓ SSE 流式响应正常
✓ A2UI Table 渲染数据表格
✓ A2UI ConfirmationCard 可交互
✓ Human-in-the-loop 流程完整
✓ 会话历史可回溯
```

#### BS-05: 版本管理与回滚

```
角色: 数据架构师
目标: 发布新版本 → 发现问题 → 回滚

步骤:
1. 修改 ObjectType "交通信号灯"：添加属性"维护周期"
2. submit_to_staging
3. 查看 Staging 摘要（确认变更内容）
4. commit_staging（发布）
5. 验证新属性出现在 Active 版本
6. 查看 Snapshot 历史（应有新快照）
7. 查看 Diff（字段级差异："维护周期"为 added）
8. 发现问题 → 执行回滚到上一个 Snapshot
9. 验证"维护周期"属性消失
10. 验证 Active 版本恢复到回滚点

验证点:
✓ Staging 摘要正确显示变更
✓ 快照记录包含 entity_data
✓ Diff 显示字段级差异
✓ 回滚后状态完全恢复
✓ Active pointer 更新正确
```

#### BS-06: 多租户隔离

```
角色: 系统管理员
目标: 验证不同租户的数据隔离

步骤:
1. admin 登录 → 创建新租户 "交通局"
2. 为"交通局"添加成员用户
3. 切换到"交通局"租户
4. 在"交通局"下创建 ObjectType
5. 切换回 "Default" 租户
6. 验证 Default 租户看不到"交通局"的 ObjectType
7. "交通局"成员登录后只能看到自己的数据

验证点:
✓ tenant_id 隔离生效
✓ 跨租户不可见
✓ 租户切换后数据正确
```

#### BS-07: RBAC 权限管控

```
角色: 系统管理员
目标: 验证不同角色的权限边界

步骤:
1. 开启 RBAC（LINGSHU_RBAC_ENABLED=true）
2. 创建 viewer 角色用户
3. viewer 登录 → 可查看 ObjectType 列表
4. viewer 尝试创建 ObjectType → 403 Forbidden
5. 创建 member 角色用户
6. member 登录 → 可创建 ObjectType
7. member 尝试管理用户 → 403 Forbidden
8. admin 登录 → 一切操作允许

验证点:
✓ admin 全权
✓ member 可读写业务数据，不可管理用户
✓ viewer 只读
✓ 403 错误消息清晰
```

#### BS-08: Copilot Shell 上下文感知

```
角色: 业务分析师
目标: 在不同页面使用 Shell Copilot，验证上下文同步

步骤:
1. 在 Ontology → ObjectType 详情页打开 Shell
2. Shell 自动知道当前在看哪个 ObjectType
3. 发送"这个类型有哪些属性？"→ 返回当前 ObjectType 的属性列表
4. 切换到 Data → Browse 页面
5. Shell 上下文自动更新
6. 发送"查询最近 10 条数据"→ 返回当前浏览类型的实例

验证点:
✓ Shell 会话持久化（开关不丢失）
✓ 页面切换后上下文自动更新
✓ Agent 工具范围按上下文裁剪
```

#### BS-09: 级联更新与继承一致性

```
角色: 数据架构师
目标: 修改 SharedPropertyType → 验证级联传播

步骤:
1. 创建 SharedPropertyType "通用名称"（display_name="名称"）
2. 创建 ObjectType A → PropertyType "名称"继承自"通用名称"
3. 创建 ObjectType B → PropertyType "名称"继承自"通用名称"
4. 手动修改 ObjectType B 的"名称"属性 display_name 为 "自定义名称"
5. 修改 SharedPropertyType "通用名称" display_name 为 "标准名称"
6. 验证 ObjectType A 的属性 → "标准名称"（级联更新）
7. 验证 ObjectType B 的属性 → "自定义名称"（不级联，因为已覆盖）

验证点:
✓ 未覆盖 → 级联
✓ 已覆盖 → 不级联
✓ 值比较策略正确
```

#### BS-10: 工作流编排与执行

```
角色: 自动化工程师
目标: 创建并执行多步工作流

步骤:
1. 创建工作流"批量重启故障设备"
2. 添加节点: 查询故障设备(Global Function) → 条件判断(>5台) → 批量重启(Action) / 单台重启(Action)
3. 配置边和条件
4. 保存工作流
5. 在可视化 DAG 查看器中确认拓扑正确
6. 执行工作流
7. 查看执行进度和结果

验证点:
✓ DAG 拓扑排序正确
✓ 条件分支执行正确
✓ 并行节点正确执行
✓ 执行记录完整
```

#### BS-11: 数据浏览搜索与筛选

```
角色: 业务分析师
目标: 通过搜索和筛选快速定位数据

步骤:
1. 进入 Data → Browse 页面
2. 搜索 "信号灯" → 过滤显示匹配的 ObjectType
3. 点击进入实例列表
4. 使用搜索框搜索实例
5. 使用排序按"更新时间"降序
6. 使用分页翻页
7. 验证搜索/排序/分页联动正确

验证点:
✓ 搜索实时过滤（防抖 300ms）
✓ 排序与服务端一致
✓ 分页重置于筛选变更
✓ 空结果显示友好提示
```

#### BS-12: 完整的 SSO 登录流程

```
角色: 企业用户
目标: 通过 SSO 首次登录

步骤:
1. 访问登录页 → 看到 SSO 登录按钮
2. 点击 SSO → 跳转 OIDC Provider
3. 在 OIDC Provider 完成认证
4. 回调到 LingShu
5. JIT Provisioning 自动创建用户
6. 自动加入默认租户
7. 正常使用系统

验证点:
✓ SSO 配置正确加载
✓ OIDC 授权码流程完整
✓ JIT 用户创建正确
✓ 租户自动分配
```

### 3.2 业务场景测试实现

每个场景对应一个 Python 测试文件：

```
backend/tests/scenarios/
├── conftest.py                       # 共享 fixtures：登录、创建实体辅助函数
├── test_bs01_traffic_modeling.py     # 智慧交通建模
├── test_bs02_data_source_query.py    # 数据源接入
├── test_bs03_action_execution.py     # Action 执行
├── test_bs04_copilot_conversation.py # Copilot 对话
├── test_bs05_version_rollback.py     # 版本回滚
├── test_bs06_multi_tenant.py         # 多租户隔离
├── test_bs07_rbac_permissions.py     # RBAC 权限
├── test_bs08_shell_context.py        # Shell 上下文
├── test_bs09_cascade_inheritance.py  # 级联继承
├── test_bs10_workflow_execution.py   # 工作流
├── test_bs11_data_search_filter.py   # 数据搜索
└── test_bs12_sso_login.py           # SSO 登录
```

**执行命令**:
```bash
# 需要完整 Docker 环境运行
docker compose up -d
cd backend && uv run pytest tests/scenarios/ -v --tb=long
```

---

## 第四部分：L4 浏览器 E2E 测试（Playwright）

### 4.1 已有 E2E（回归 — 33 个用例）

```
frontend/e2e/docker-e2e.spec.ts
```

所有页面加载 + 数据渲染 + 导航 + API 健康 + 控制台错误检测。

### 4.2 新增：关键用户旅程 E2E

> 在真实浏览器中模拟用户完整操作流程，验证 UI + API + 数据库的端到端正确性。

#### 文件规划

```
frontend/e2e/
├── docker-e2e.spec.ts              # 已有：页面加载回归（33 tests）
├── journeys/
│   ├── helpers.ts                   # 共享辅助：realLogin, createObjectType, waitForToast
│   ├── j01-ontology-crud.spec.ts   # 旅程 1：Ontology CRUD 完整流程
│   ├── j02-version-lifecycle.spec.ts # 旅程 2：版本生命周期
│   ├── j03-entity-delete.spec.ts   # 旅程 3：实体删除与依赖阻止
│   ├── j04-data-source-browse.spec.ts # 旅程 4：数据源 + 浏览
│   ├── j05-action-execute.spec.ts  # 旅程 5：Action 执行
│   ├── j06-copilot-chat.spec.ts    # 旅程 6：Copilot 对话
│   ├── j07-shell-sse.spec.ts       # 旅程 7：Shell SSE 对话
│   ├── j08-user-management.spec.ts # 旅程 8：用户管理 + 搜索
│   ├── j09-topology-view.spec.ts   # 旅程 9：拓扑可视化
│   ├── j10-asset-mapping.spec.ts   # 旅程 10：AssetMapping 编辑
│   ├── j11-workflow-dag.spec.ts    # 旅程 11：工作流 DAG 编辑
│   ├── j12-rollback.spec.ts        # 旅程 12：版本回滚
│   ├── j13-rbac-boundary.spec.ts   # 旅程 13：RBAC 权限边界
│   ├── j14-search-filter.spec.ts   # 旅程 14：全局搜索与筛选
│   └── j15-cross-module-nav.spec.ts # 旅程 15：跨模块导航与上下文
```

#### 旅程详细设计

##### J01: Ontology CRUD 完整流程

```typescript
test.describe("J01: Ontology CRUD Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("create → edit → save ObjectType", async ({ page }) => {
    // 1. 导航到 ObjectType 列表页
    await page.goto(`${BASE}/ontology/object-types`);

    // 2. 点击 "New" 按钮
    await page.getByRole("button", { name: /new/i }).click();

    // 3. 填写表单：api_name, display_name, description
    await page.fill('input[name="api_name"]', "test_vehicle");
    await page.fill('input[name="display_name"]', "测试车辆");
    await page.fill('textarea[name="description"]', "E2E 测试创建的车辆类型");

    // 4. 保存
    await page.getByRole("button", { name: /save/i }).click();

    // 5. 验证跳转到详情页
    await page.waitForURL(/object-types\/ri\.obj\./);

    // 6. 验证数据回显正确
    await expect(page.getByText("test_vehicle")).toBeVisible();
    await expect(page.getByText("测试车辆")).toBeVisible();
  });

  test("add PropertyType to ObjectType", async ({ page }) => {
    // 1. 进入已有 ObjectType 详情页
    // 2. 切换到 Properties tab
    // 3. 添加属性
    // 4. 验证属性出现在列表中
  });

  test("list page shows created ObjectType", async ({ page }) => {
    // 验证列表页展示新创建的 ObjectType
  });
});
```

##### J02: 版本生命周期

```typescript
test.describe("J02: Version Lifecycle Journey", () => {
  test("draft → staging → publish → verify active", async ({ page }) => {
    // 1. 创建 ObjectType（自动 Draft）
    // 2. 进入版本管理页
    // 3. 查看 Draft 摘要 → 显示 1 个变更
    // 4. 点击 "Submit to Staging"
    // 5. 查看 Staging 摘要 → 显示 1 个变更
    // 6. 点击 "Publish" → 确认对话框 → 确认
    // 7. 等待发布完成
    // 8. 验证 Snapshot History 多了一条
    // 9. 验证 ObjectType 在列表页可查询（Active 版本）
  });
});
```

##### J03: 实体删除与依赖阻止

```typescript
test.describe("J03: Entity Delete Journey", () => {
  test("delete ObjectType succeeds when no dependencies", async ({ page }) => {
    // 1. 创建孤立 ObjectType（无 LinkType 引用）
    // 2. 进入详情页
    // 3. 点击 Delete 按钮
    // 4. 确认对话框 → 确认
    // 5. 验证跳转回列表页
    // 6. 验证列表中不再显示
  });

  test("delete ObjectType blocked by LinkType dependency", async ({ page }) => {
    // 1. 创建 ObjectType A
    // 2. 创建 LinkType source=A
    // 3. 发布两者
    // 4. 尝试删除 ObjectType A
    // 5. 验证错误提示："Referenced by X entities"
  });
});
```

##### J06: Copilot 对话

```typescript
test.describe("J06: Copilot Chat Journey", () => {
  test("send message and receive streaming response", async ({ page }) => {
    await realLogin(page);
    await page.goto(`${BASE}/agent/chat`);

    // 等待 session 创建
    await page.waitForTimeout(2000);

    // 输入消息
    const input = page.locator("textarea");
    await input.fill("Hello, what can you do?");

    // 发送
    await page.getByRole("button", { name: /send/i }).click();

    // 验证用户消息显示
    await expect(page.getByText("Hello, what can you do?")).toBeVisible();

    // 等待 assistant 响应（SSE 流）
    await page.waitForSelector('[class*="bg-muted"]', { timeout: 30000 });

    // 验证有 assistant 回复内容
    const assistantMessages = page.locator('[class*="bg-muted"]');
    await expect(assistantMessages.first()).toBeVisible();
  });
});
```

##### J07: Shell SSE 对话

```typescript
test.describe("J07: Shell SSE Journey", () => {
  test("open shell → send message → receive SSE response", async ({ page }) => {
    await realLogin(page);
    await page.goto(`${BASE}/ontology/overview`);

    // 点击 Shell 打开按钮
    const shellButton = page.locator('button:has-text("Copilot")');
    if (await shellButton.isVisible()) {
      await shellButton.click();
    }

    // 等待 Shell 面板出现
    await expect(page.locator("text=Ask Copilot")).toBeVisible({ timeout: 5000 });

    // 输入消息
    const shellInput = page.locator('textarea[placeholder*="Copilot"]');
    await shellInput.fill("What ontology types exist?");

    // 发送
    await page.locator("button:has(svg)").last().click();

    // 验证消息发送成功（用户消息出现）
    await expect(page.getByText("What ontology types exist?")).toBeVisible();

    // 等待 assistant 响应（不再是 "Echo:" 开头）
    await page.waitForTimeout(5000);
    const messages = await page.locator('[class*="bg-muted"]').allInnerTexts();
    const hasRealResponse = messages.some((m) => !m.startsWith("Echo:") && m.length > 0);
    expect(hasRealResponse).toBeTruthy();
  });
});
```

##### J09: 拓扑可视化

```typescript
test.describe("J09: Topology Visualization", () => {
  test("topology graph renders nodes and edges", async ({ page }) => {
    await realLogin(page);
    // 先创建一些实体确保有数据
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // 查找 SVG 元素（拓扑图）
    const svg = page.locator("svg").first();
    await expect(svg).toBeVisible({ timeout: 10000 });

    // 验证有节点渲染
    const nodes = page.locator("svg rect, svg circle");
    // 如果有实体数据，应该有节点
  });

  test("click node navigates to entity detail", async ({ page }) => {
    await realLogin(page);
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // 点击一个节点
    const nodeText = page.locator("svg text").first();
    if (await nodeText.isVisible()) {
      await nodeText.click();
      // 验证导航到了详情页
      await page.waitForURL(/ontology\/(object-types|link-types|interface-types)/);
    }
  });
});
```

##### J12: 版本回滚

```typescript
test.describe("J12: Rollback Journey", () => {
  test("publish → rollback → verify state restored", async ({ page }) => {
    await realLogin(page);

    // 1. 确保有至少一个已发布快照
    // 2. 修改并发布新版本
    // 3. 进入版本管理页
    // 4. 找到历史快照的 Rollback 按钮
    // 5. 点击 Rollback → 确认
    // 6. 验证成功消息
    // 7. 验证 Active 版本恢复
  });

  test("rollback blocked when staging exists", async ({ page }) => {
    // 有未提交的 Staging → 回滚被阻止 → 显示错误
  });
});
```

##### J14: 搜索与筛选

```typescript
test.describe("J14: Search & Filter Journey", () => {
  test("user list search filters by name", async ({ page }) => {
    await realLogin(page);
    await page.goto(`${BASE}/setting/users`);
    await page.waitForLoadState("networkidle");

    // 在搜索框输入 "admin"
    const searchInput = page.locator('input[placeholder*="Search"]');
    await searchInput.fill("admin");

    // 等待防抖（300ms）
    await page.waitForTimeout(500);

    // 验证只显示包含 "admin" 的结果
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible();
  });

  test("data browse search filters types", async ({ page }) => {
    await realLogin(page);
    await page.goto(`${BASE}/data/browse`);
    await page.waitForLoadState("networkidle");

    // 搜索框存在并可输入
    const searchInput = page.locator('input[placeholder*="Search"], input[placeholder*="search"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill("test");
      await page.waitForTimeout(500);
    }
  });
});
```

### 4.3 Playwright 配置更新

```typescript
// playwright.config.ts — 建议更新

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // 旅程测试有数据依赖，顺序执行更稳定
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1, // 单 worker 避免数据竞争
  reporter: [
    ["html", { open: "never" }],
    ["json", { outputFile: "e2e-results.json" }],
  ],
  use: {
    baseURL: "http://localhost:3100",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "regression",
      testMatch: "docker-e2e.spec.ts",
    },
    {
      name: "journeys",
      testDir: "./e2e/journeys",
      dependencies: ["regression"], // 回归通过后才跑旅程
    },
  ],
});
```

### 4.4 E2E 辅助工具

```typescript
// frontend/e2e/journeys/helpers.ts

export const BASE = "http://localhost:3100";
export const API = "http://localhost:8100";

/** 真实登录并注入 Cookie */
export async function realLogin(page: Page) { ... }

/** 创建 ObjectType 并返回 RID */
export async function createObjectType(page: Page, apiName: string): Promise<string> {
  const resp = await page.request.post(`${API}/ontology/v1/object-types`, {
    data: { api_name: apiName, display_name: apiName, description: "E2E test" },
  });
  const body = await resp.json();
  return body.data.rid;
}

/** 等待 Toast 消息 */
export async function waitForToast(page: Page, text: string | RegExp) {
  await expect(page.getByText(text)).toBeVisible({ timeout: 5000 });
}

/** 清理测试数据（测试后调用） */
export async function cleanupEntity(page: Page, type: string, rid: string) {
  await page.request.delete(`${API}/ontology/v1/${type}/${rid}`);
}
```

---

## 第五部分：测试执行策略

### 5.1 执行矩阵

| 触发时机 | 运行测试 | 环境 | 超时 |
|---------|---------|------|------|
| 每次 `git commit` | L1 单元测试（后端 + 前端） | 本地 | 30s |
| 每次 `git push` / PR | L1 + L2 集成测试 | CI (GitHub Actions) | 5min |
| 每日自动 (cron) | L1 + L2 + L3 业务场景 | CI + Docker | 15min |
| 发布前 | L1 + L2 + L3 + L4 全部 | CI + Docker + Playwright | 30min |
| 紧急修复 | L1 + 相关模块 L2 + 相关旅程 L4 | CI | 10min |

### 5.2 CI/CD 流水线更新

```yaml
# .github/workflows/ci.yml — 建议更新

jobs:
  unit-tests:
    name: "L1: Unit Tests"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Backend unit tests
        run: cd backend && uv run pytest tests/unit/ -v --cov=lingshu --cov-report=term-missing
      - name: Frontend unit tests
        run: cd frontend && pnpm test -- --run

  integration-tests:
    name: "L2: Integration Tests"
    needs: unit-tests
    runs-on: ubuntu-latest
    services:
      postgres: ...
      neo4j: ...
      redis: ...
    steps:
      - run: cd backend && uv run pytest tests/integration/ -v

  scenario-tests:
    name: "L3: Business Scenarios"
    needs: integration-tests
    runs-on: ubuntu-latest
    steps:
      - run: docker compose up -d --wait
      - run: cd backend && uv run pytest tests/scenarios/ -v

  e2e-tests:
    name: "L4: Browser E2E"
    needs: scenario-tests
    runs-on: ubuntu-latest
    steps:
      - run: docker compose up -d --wait
      - run: cd frontend && npx playwright install chromium
      - run: cd frontend && npx playwright test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: e2e-results
          path: |
            frontend/playwright-report/
            frontend/test-results/
```

### 5.3 测试数据管理

```
测试数据策略:
├── L1: 纯 Mock，无真实数据
├── L2: Docker 临时数据库（tmpfs），测试后销毁
├── L3: Docker compose seed（admin 用户 + Default 租户），场景内自建
└── L4: 同 L3，通过 API 创建测试数据，测试后通过 API 清理
```

### 5.4 失败处理

| 级别 | 失败策略 |
|------|---------|
| L1 失败 | 阻止提交（pre-commit hook 可选） |
| L2 失败 | 阻止 PR 合并 |
| L3 失败 | 标记 PR 为 "需要调查"，不阻塞但需 24h 内修复 |
| L4 失败 | 截图 + 视频 + trace 自动上传，重试 2 次后标记 flaky |

### 5.5 Flaky 测试管理

```
规则:
1. E2E 测试允许 retry 2 次
2. 连续 3 次 flaky 的测试进入隔离队列（quarantine）
3. 隔离测试每日独立运行，修复后回归主套件
4. 所有 E2E 失败保留 screenshot + video + trace
```

---

## 第六部分：测试覆盖率目标

### 6.1 覆盖率指标

| 维度 | 目标 | 当前 | 差距 |
|------|------|------|------|
| 后端代码覆盖率 | ≥ 80% | ~75% (估) | 需补充新功能覆盖 |
| 前端代码覆盖率 | ≥ 60% | ~30% (估) | 需大量补充组件测试 |
| API 端点覆盖率 | 100% | ~90% | 新增 3 个端点需覆盖 |
| 关键业务流程 | 100% | ~60% | 12 个场景需全部补齐 |
| 页面加载覆盖率 | 100% | 100% | docker-e2e.spec.ts 已覆盖 |
| CRUD 操作覆盖率 | 100% | ~70% | 删除操作需 E2E 覆盖 |

### 6.2 新功能覆盖率矩阵（20 项）

| 任务 | L1 单元 | L2 集成 | L3 场景 | L4 E2E |
|------|--------|--------|--------|--------|
| T1 不可变字段 | ✅ 12 tests | IT-01 | BS-01, BS-05 | J02 |
| T2 契约校验 | ✅ 10 tests | IT-02 | BS-01 | J02 |
| T3 发布通知 | ✅ 5 tests | IT-03 | BS-05 | - |
| T4 Neo4j 重试 | ✅ 9 tests | IT-04 | - | - |
| T5 删除按钮 | 需新增 | - | BS-01 | J03 |
| T6 FDB 文档 | - | - | - | - |
| T7 字段 Diff | ✅ 13 tests | - | BS-05 | J12 |
| T8 回滚按钮 | 需新增 | - | BS-05 | J12 |
| T9 AssetMapping 编辑 | 需新增 | IT-06 | BS-02 | J10 |
| T10 AssetMapping 查询 | ✅ 5 tests | IT-06 | BS-02 | - |
| T11 拓扑可视化 | 需新增 | - | BS-01 | J09 |
| T12 独立查询端点 | ✅ 9 tests | - | - | - |
| T13 工作流 DAG | 需新增 | - | BS-10 | J11 |
| T14 Shell SSE | 需新增 | - | BS-08 | J07 |
| T15 级联改进 | ✅ 8 tests | IT-07 | BS-09 | - |
| T16 Monaco Editor | 需新增 | - | - | - |
| T17 用户搜索 | 需新增 | - | BS-07 | J14 |
| T18 Sub-Agent | ✅ 14 tests | - | - | - |
| T19 RBAC 开关 | ✅ 14 tests | IT-05 | BS-07 | J13 |
| T20 数据搜索 | 需新增 | - | BS-11 | J14 |

---

## 第七部分：测试命令速查

```bash
# ═══ L1: 单元测试 ═══
cd backend && uv run pytest tests/unit/ -v                    # 全部后端单元
cd backend && uv run pytest tests/unit/ontology/ -v            # 仅 Ontology 模块
cd backend && uv run pytest tests/unit/ --cov=lingshu --cov-report=html  # 带覆盖率报告
cd frontend && pnpm test -- --run                              # 全部前端单元

# ═══ L2: 集成测试 ═══
docker compose -f docker/docker-compose.test.yml up -d         # 启动测试基础设施
cd backend && uv run pytest tests/integration/ -v              # 全部集成测试

# ═══ L3: 业务场景测试 ═══
docker compose up -d                                           # 启动完整环境
cd backend && uv run pytest tests/scenarios/ -v --tb=long      # 全部场景

# ═══ L4: 浏览器 E2E ═══
docker compose up -d                                           # 启动完整环境
cd frontend && npx playwright test e2e/docker-e2e.spec.ts      # 回归测试
cd frontend && npx playwright test e2e/journeys/               # 旅程测试
cd frontend && npx playwright test --headed                    # 有头模式（调试用）
cd frontend && npx playwright show-report                      # 查看 HTML 报告

# ═══ 全量测试 ═══
make test-all   # 建议在 Makefile 中添加此目标
```

---

## 附录：测试文件清单

### 待新增文件总览

```
后端 (7 个集成测试文件):
  backend/tests/integration/test_immutable_integration.py
  backend/tests/integration/test_contract_integration.py
  backend/tests/integration/test_schema_notification_integration.py
  backend/tests/integration/test_retry_integration.py
  backend/tests/integration/test_rbac_cross_module.py
  backend/tests/integration/test_asset_mapping_integration.py
  backend/tests/integration/test_cascade_integration.py

后端 (12 个场景测试文件):
  backend/tests/scenarios/conftest.py
  backend/tests/scenarios/test_bs01_traffic_modeling.py
  ... (共 12 个)

前端 (5 个组件测试文件):
  frontend/src/components/ontology/topology-graph.test.tsx
  frontend/src/components/ontology/asset-mapping-editor.test.tsx
  frontend/src/components/ontology/execution-config-editor.test.tsx
  frontend/src/components/workflow/dag-viewer.test.tsx
  frontend/src/hooks/use-debounce.test.ts

前端 (16 个 E2E 文件):
  frontend/e2e/journeys/helpers.ts
  frontend/e2e/journeys/j01-ontology-crud.spec.ts
  ... (共 15 个旅程)
```

**新增测试总计**: ~40 个文件，预计 200+ 测试用例
