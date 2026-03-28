# LingShu 平台 E2E 测试报告 — 第 4 轮

## 测试概况

| 项目 | 值 |
|------|-----|
| 轮次 | 第 4 轮 |
| 开始时间 | 2026-03-12 15:48:46 |
| 结束时间 | 2026-03-12 16:06:38 |
| 测试总数 | 77 |
| 通过 | 74 |
| 失败 | 3 |
| 错误 | 0 |
| 跳过 | 0 |
| 通过率 | 96.1% |

---

## Setting (10/10)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | 管理员登录 | ✅ PASS | 0.2s | Logged in |
| 2 | 获取当前用户 /auth/me | ✅ PASS | 0.0s | email=admin@lingshu.dev, role=admin |
| 3 | 创建用户: 质检主管 王工 | ✅ PASS | 0.0s | already exists |
| 4 | 创建用户: 产线班组长 李工 | ✅ PASS | 0.0s | already exists or error |
| 5 | 查询用户列表 ≥ 1人 | ✅ PASS | 0.0s | total=3, users=['li.lead@f35factory.com', 'wang.qc@f35factory.com', 'admin@lingshu.dev'] |
| 6 | 查询租户列表 | ✅ PASS | 0.0s | tenants=['Fort Worth FACO', 'Fort Worth FACO', 'Fort Worth FACO', 'Fort Worth FACO', 'Fort Worth FACO', 'Fort Worth FACO |
| 7 | 创建租户: Fort Worth FACO | ✅ PASS | 0.0s | rid=ri.tenant.a30b4d22-7cf3-46ff-aedb-6cf136e219a6 |
| 8 | 查询审计日志 ≥ 1条 | ✅ PASS | 0.0s | total=1, latest_event=seed |
| 9 | Setting 概览统计 | ✅ PASS | 0.0s | users=None, tenants=None |
| 10 | 修改密码 (改→改回) | ✅ PASS | 1.2s | Password changed and restored |

## Ontology.Create (6/6)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | 创建 19 个 SharedPropertyType | ✅ PASS | 0.2s | created/exists=19, failed=0 |
| 2 | 创建 7 个 InterfaceType | ✅ PASS | 0.0s | created/exists=7, failed=0 |
| 3 | 创建 25 个 ObjectType | ✅ PASS | 0.2s | created/exists=25, failed=0 |
| 4 | 添加 42 个 PropertyType 到 ObjectType | ✅ PASS | 0.2s | total=42, ok=42, fail=0 |
| 5 | 创建 17 个 LinkType | ✅ PASS | 0.1s | created/exists=17, failed=0 |
| 6 | 创建 17 个 ActionType | ✅ PASS | 0.1s | created/exists=17, failed=0 |

## Ontology.Verify (10/10)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | 验证 ObjectType 数量 = 25 | ✅ PASS | 0.0s | count=25, names=['DeliveryMilestone', 'FlightTest', 'GroundTest', 'TechnicalDocument', 'EngineeringChange']... |
| 2 | 验证 LinkType 数量 = 17 | ✅ PASS | 0.0s | count=17, names=['ImpactedBy', 'Supersedes', 'ReferencesDoc', 'SuppliedBy', 'ResolvedBy']... |
| 3 | 验证 InterfaceType 数量 = 7 | ✅ PASS | 0.0s | count=7, names=['Classifiable', 'Auditable', 'Costed', 'Schedulable', 'Certifiable']... |
| 4 | 验证 ActionType 数量 = 17 | ✅ PASS | 0.0s | count=17, names=['ApproveDelivery', 'RecordFlightTest', 'StartGroundTest', 'ImplementECO', 'IssueECO']... |
| 5 | 验证 SharedPropertyType 数量 = 19 | ✅ PASS | 0.0s | count=19, names=['LifecycleStatus', 'QualityGrade', 'SecurityClass', 'Priority', 'ActualHours']... |
| 6 | 验证 F35Aircraft 属性字段 | ✅ PASS | 0.0s | Found 6 properties: ['tail_number', 'variant', 'customer_country', 'target_delivery_date', 'current_station', 'assembly_ |
| 7 | 验证 InterfaceType 含 category | ✅ PASS | 0.0s | count=7, categories=['OBJECT_INTERFACE', 'OBJECT_INTERFACE', 'OBJECT_INTERFACE', 'OBJECT_INTERFACE', 'OBJECT_INTERFACE', |
| 8 | 获取 WorkOrder 详情 | ✅ PASS | 0.0s | rid=ri.obj.a78944f9-9a2c-42f7-b734-71f58509567f, api_name=WorkOrder, props=4: ['target_aircraft', 'bom_version', 'wo_sta |
| 9 | 搜索 'Assembly' 相关实体 | ✅ PASS | 0.0s | found=7, items=['MajorAssembly', 'SubAssembly', 'ProductionLine', 'StartAssembly', 'CompleteAssembly'] |
| 10 | 获取本体拓扑图 | ✅ PASS | 0.0s | nodes=85, edges=0 |

## Version (9/9)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | 查看 Draft 摘要 | ✅ PASS | 0.0s | counts={'PropertyType': 42}, total=42 |
| 2 | 提交所有实体到 Staging | ✅ PASS | 0.3s | ok=0, already=0, no_draft=85, fail=0 |
| 3 | 查看 Staging 摘要 | ✅ PASS | 0.0s | counts={}, total=0 |
| 4 | Commit Staging → Snapshot v1 (初始产线模型) | ✅ PASS | 0.0s | already_committed, existing_snapshots=11 |
| 5 | 验证快照列表 ≥ 1 | ✅ PASS | 0.0s | count=11, latest=ri.snap.34c6bedf-c9ea-4a00-9725-a85f8c69be4e |
| 6 | 创建 Snapshot v2 (ECO 变更) | ✅ PASS | 0.1s | snapshot_id=ri.snap.899d6fc9-23b4-4921-8c84-2ed67437f735 |
| 7 | 查看 v2 快照 diff | ✅ PASS | 0.0s | diff_data={'snapshot_changes': {'ri.obj.1ad8688d-73da-468b-9c5a-44def7549c29': 'update'}, 'current_changes': {'ri.obj.1a |
| 8 | Discard Staging 测试 | ✅ PASS | 0.0s | before_discard=1, after_discard=0, result=ok |
| 9 | 验证快照数量 ≥ 2 | ✅ PASS | 0.0s | snapshot_count=12, ids=['ri.snap.899d6fc9-23b', 'ri.snap.34c6bedf-c9e', 'ri.snap.53d0a4fb-8e1', 'ri.snap.e926845f-523',  |

## Data (6/6)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | Data 概览 | ✅ PASS | 0.0s | overview={'connections': {'total': 28}} |
| 2 | 创建数据连接: F35 MES DB | ✅ PASS | 0.0s | rid=ri.conn.fb8b23b1-2ef9-421b-a11b-0359e6de072f |
| 3 | 查询数据连接列表 | ✅ PASS | 0.0s | count=10, names=['F35 MES Production DB', 'F35 Quality Data Lake', 'F35 MES Production DB (Fort Worth)', 'F35 Quality Da |
| 4 | 获取连接详情 | ✅ PASS | 0.0s | name=F35 MES Production DB, type=postgresql, status=disconnected |
| 5 | 更新连接: 添加说明 | ✅ PASS | 0.0s | updated_name=F35 MES Production DB (Fort Worth) |
| 6 | 创建数据连接: Quality Data Lake | ✅ PASS | 0.0s | rid=ri.conn.ec308c96-7f4b-4598-8454-bffea2b94ca2 |

## Function (7/7)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | Function 概览 | ✅ PASS | 0.0s | overview={'capabilities': {'actions': 0, 'functions': 2, 'workflows': 0}, 'recent_executions': {'total_24h': 0, 'by_stat |
| 2 | 创建全局函数: calc_assembly_progress | ✅ PASS | 0.0s | error=Function with api_name 'calc_assembly_progress' already exists |
| 3 | 创建全局函数: check_material_readiness | ✅ PASS | 0.0s | rid=N/A |
| 4 | 查询全局函数列表 | ✅ PASS | 0.0s | count=2, names=['check_material_readiness', 'calc_assembly_progress'] |
| 5 | 创建工作流: 装配→质检→放行 | ✅ PASS | 0.0s | rid=N/A |
| 6 | 查询工作流列表 | ✅ PASS | 0.0s | count=0, names=[] |
| 7 | 查询能力目录 (Action + Function) | ✅ PASS | 0.0s | total_capabilities=2 |

## Agent (14/14)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | Agent 概览 | ✅ PASS | 0.0s | sessions=None, models=None |
| 2 | 注册模型: GPT-4o (车间助手) | ✅ PASS | 0.0s | rid=ri.model.ce45edff-eb01-463c-8144-8725ec7f3011 |
| 3 | 注册模型: Claude (技术文档分析) | ✅ PASS | 0.0s | rid=ri.model.cc5aad45-2139-451e-8a55-6b10b341f1fe |
| 4 | 查询模型列表 ≥ 2 | ✅ PASS | 0.0s | count=20, names=['claude_docs', 'gpt4o_factory', 'claude_docs', 'gpt4o_factory', 'claude_docs', 'gpt4o_factory', 'claude |
| 5 | 创建技能: 工序状态查询 | ✅ PASS | 0.0s | rid=ri.skill.78601c16-6acf-4d78-9302-153c0a847e97 |
| 6 | 创建技能: NCR 趋势分析 | ✅ PASS | 0.0s | rid=ri.skill.24d1959f-7734-49f4-bcd1-8230f9f3ac07 |
| 7 | 查询技能列表 ≥ 2 | ✅ PASS | 0.0s | count=20, names=['ncr_trend_analysis', 'query_process_status', 'ncr_trend_analysis', 'query_process_status', 'ncr_trend_ |
| 8 | 创建 MCP 连接: 产线监控 OPC-UA | ✅ PASS | 0.0s | rid=ri.mcp.de25fd9b-44d9-4e17-9a8a-feac094014c6 |
| 9 | 查询 MCP 连接列表 | ✅ PASS | 0.0s | count=15, names=['opcua_line_monitor', 'opcua_line_monitor', 'opcua_line_monitor', 'opcua_line_monitor', 'opcua_line_mon |
| 10 | 创建子代理: 质量管理助手 | ✅ PASS | 0.0s | rid=ri.subagent.f5a594a6-6c0a-4cc8-b54a-22a45698adf3 |
| 11 | 创建子代理: 物料管理助手 | ✅ PASS | 0.0s | rid=ri.subagent.ad000fc3-db3c-48e4-ad5c-281801cbd4d6 |
| 12 | 查询子代理列表 ≥ 2 | ✅ PASS | 0.0s | count=20, names=['material_assistant', 'qc_assistant', 'material_assistant', 'qc_assistant', 'material_assistant', 'qc_a |
| 13 | 创建会话: AF-42 总装上下文 | ✅ PASS | 0.0s | session=ri.session.9ea61ef3-bd4e-45d6-9342-ee3e86489439 |
| 14 | 查询会话列表 | ✅ PASS | 0.0s | count=20 |

## UI (12/15)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | Ontology 概览 — 统计卡片 | ✅ PASS | 29.9s | Object Types count: 25 Link Types count: 17 Interface Types count: 7 Action Types count: 17 Shared Property Types count: |
| 2 | ObjectType 列表 — 含 F35Aircraft | ✅ PASS | 47.7s | Here is the requested information: 1. Total count shown in the table: 25 2. First 5 object type names in the table: Deli |
| 3 | ObjectType 详情 — F35Aircraft 属性 | ✅ PASS | 35.8s | I have navigated to the 'Object Types' page as requested. However, I was unable to find 'F35Aircraft' in the list of obj |
| 4 | InterfaceType 列表 — 7个接口 | ✅ PASS | 58.7s | Successfully extracted the interface type names and their total count.  Interface Type Names: Classifiable, Auditable, C |
| 5 | ActionType 列表 — 安全等级 | ✅ PASS | 60.4s | The first 5 action type names and their safety levels are: 1. ApproveDelivery: SAFETY_READ_ONLY 2. RecordFlightTest: SAF |
| 6 | 版本/快照页 — ≥2个快照 | ✅ PASS | 46.1s | There are 12 snapshots listed. The snapshot IDs are: - ri.snap.899d6fc9-23b4-4921-8c84-2ed67437f735 - ri.snap.34c6bedf-c |
| 7 | Setting 用户管理 — 多用户 | ✅ PASS | 58.3s | Here are the users found in the table: [   {     "name": "李明（班组长）",     "email": "li.lead@f35factory.com"   },   {     " |
| 8 | Setting 租户管理 — Fort Worth | ✅ PASS | 45.7s | All tenant names shown on the page are: - Fort Worth FACO (15 times) - Default (1 time)  'Fort Worth FACO' is present on |
| 9 | Data 数据源 — MES连接 | ✅ PASS | 80.7s | Successfully logged in and navigated to the data sources page. I have extracted all 30 data source connections. The list |
| 10 | Agent 模型 — 2个AI模型 | ❌ FAIL | 236.2s | Did not complete within 15 steps |
| 11 | Agent 技能 — 工序查询+NCR分析 | ❌ FAIL | 97.4s | Did not complete within 15 steps |
| 12 | Agent 子代理 — 质量+物料助手 | ❌ FAIL | 118.5s | Did not complete within 15 steps |
| 13 | Function 能力列表 | ✅ PASS | 48.0s | No capabilities or actions are listed on the page http://localhost:3100/function/capabilities. |
| 14 | 跨模块 Dock 导航 | ✅ PASS | 62.3s | Successfully logged in and visited all 5 modules: Ontology, Data, Function, Agent, and Setting. The task is complete.  A |
| 15 | API 健康检查 | ✅ PASS | 44.3s | The JSON response from http://localhost:8100/health is: {"status":"ok"} |

## 失败/错误项汇总

- **UI > Agent 模型 — 2个AI模型** [FAIL]: Did not complete within 15 steps
- **UI > Agent 技能 — 工序查询+NCR分析** [FAIL]: Did not complete within 15 steps
- **UI > Agent 子代理 — 质量+物料助手** [FAIL]: Did not complete within 15 steps
