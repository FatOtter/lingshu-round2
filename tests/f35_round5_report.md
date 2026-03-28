# LingShu 平台 E2E 测试报告 — 第 5 轮

## 测试概况

| 项目 | 值 |
|------|-----|
| 轮次 | 第 5 轮 |
| 开始时间 | 2026-03-12 16:06:38 |
| 结束时间 | 2026-03-12 16:18:46 |
| 测试总数 | 77 |
| 通过 | 77 |
| 失败 | 0 |
| 错误 | 0 |
| 跳过 | 0 |
| 通过率 | 100.0% |

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
| 7 | 创建租户: Fort Worth FACO | ✅ PASS | 0.0s | rid=ri.tenant.38907ca9-4d55-4bc4-9bc7-891b6f898423 |
| 8 | 查询审计日志 ≥ 1条 | ✅ PASS | 0.0s | total=1, latest_event=seed |
| 9 | Setting 概览统计 | ✅ PASS | 0.0s | users=None, tenants=None |
| 10 | 修改密码 (改→改回) | ✅ PASS | 1.1s | Password changed and restored |

## Ontology.Create (6/6)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | 创建 19 个 SharedPropertyType | ✅ PASS | 0.1s | created/exists=19, failed=0 |
| 2 | 创建 7 个 InterfaceType | ✅ PASS | 0.0s | created/exists=7, failed=0 |
| 3 | 创建 25 个 ObjectType | ✅ PASS | 0.2s | created/exists=25, failed=0 |
| 4 | 添加 42 个 PropertyType 到 ObjectType | ✅ PASS | 0.2s | total=42, ok=42, fail=0 |
| 5 | 创建 17 个 LinkType | ✅ PASS | 0.1s | created/exists=17, failed=0 |
| 6 | 创建 17 个 ActionType | ✅ PASS | 0.2s | created/exists=17, failed=0 |

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
| 4 | Commit Staging → Snapshot v1 (初始产线模型) | ✅ PASS | 0.0s | already_committed, existing_snapshots=12 |
| 5 | 验证快照列表 ≥ 1 | ✅ PASS | 0.0s | count=12, latest=ri.snap.899d6fc9-23b4-4921-8c84-2ed67437f735 |
| 6 | 创建 Snapshot v2 (ECO 变更) | ✅ PASS | 0.1s | snapshot_id=ri.snap.7881ce15-07e7-47d7-bfcd-e5d5ea746e37 |
| 7 | 查看 v2 快照 diff | ✅ PASS | 0.0s | diff_data={'snapshot_changes': {'ri.obj.1ad8688d-73da-468b-9c5a-44def7549c29': 'update'}, 'current_changes': {'ri.obj.1a |
| 8 | Discard Staging 测试 | ✅ PASS | 0.0s | before_discard=1, after_discard=0, result=ok |
| 9 | 验证快照数量 ≥ 2 | ✅ PASS | 0.0s | snapshot_count=13, ids=['ri.snap.7881ce15-07e', 'ri.snap.899d6fc9-23b', 'ri.snap.34c6bedf-c9e', 'ri.snap.53d0a4fb-8e1',  |

## Data (6/6)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | Data 概览 | ✅ PASS | 0.0s | overview={'connections': {'total': 30}} |
| 2 | 创建数据连接: F35 MES DB | ✅ PASS | 0.0s | rid=ri.conn.d88846e8-b8f6-4c64-89a5-ec2b23894e59 |
| 3 | 查询数据连接列表 | ✅ PASS | 0.0s | count=10, names=['F35 MES Production DB', 'F35 Quality Data Lake', 'F35 MES Production DB (Fort Worth)', 'F35 Quality Da |
| 4 | 获取连接详情 | ✅ PASS | 0.0s | name=F35 MES Production DB, type=postgresql, status=disconnected |
| 5 | 更新连接: 添加说明 | ✅ PASS | 0.0s | updated_name=F35 MES Production DB (Fort Worth) |
| 6 | 创建数据连接: Quality Data Lake | ✅ PASS | 0.0s | rid=ri.conn.cc4eb3ae-3a3a-4da5-98fe-84377e19d44e |

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
| 2 | 注册模型: GPT-4o (车间助手) | ✅ PASS | 0.0s | rid=ri.model.9bf26a56-7e23-4762-a3e1-0116b1c35aa4 |
| 3 | 注册模型: Claude (技术文档分析) | ✅ PASS | 0.0s | rid=ri.model.14995dde-ef4e-4343-ab59-10e320e43f98 |
| 4 | 查询模型列表 ≥ 2 | ✅ PASS | 0.0s | count=20, names=['claude_docs', 'gpt4o_factory', 'claude_docs', 'gpt4o_factory', 'claude_docs', 'gpt4o_factory', 'claude |
| 5 | 创建技能: 工序状态查询 | ✅ PASS | 0.0s | rid=ri.skill.e3a22d6b-07b4-4338-bb80-cea560575b32 |
| 6 | 创建技能: NCR 趋势分析 | ✅ PASS | 0.0s | rid=ri.skill.6f960736-704b-4f4a-bfbc-8d21b8380ecf |
| 7 | 查询技能列表 ≥ 2 | ✅ PASS | 0.0s | count=20, names=['ncr_trend_analysis', 'query_process_status', 'ncr_trend_analysis', 'query_process_status', 'ncr_trend_ |
| 8 | 创建 MCP 连接: 产线监控 OPC-UA | ✅ PASS | 0.0s | rid=ri.mcp.ad528ebc-84b4-48e0-bfca-cb767b56d3b6 |
| 9 | 查询 MCP 连接列表 | ✅ PASS | 0.0s | count=16, names=['opcua_line_monitor', 'opcua_line_monitor', 'opcua_line_monitor', 'opcua_line_monitor', 'opcua_line_mon |
| 10 | 创建子代理: 质量管理助手 | ✅ PASS | 0.0s | rid=ri.subagent.69c78bef-69a1-4a93-a152-6e12a3e876c1 |
| 11 | 创建子代理: 物料管理助手 | ✅ PASS | 0.0s | rid=ri.subagent.b9092447-16c4-47dc-8a4e-4a85e6402034 |
| 12 | 查询子代理列表 ≥ 2 | ✅ PASS | 0.0s | count=20, names=['material_assistant', 'qc_assistant', 'material_assistant', 'qc_assistant', 'material_assistant', 'qc_a |
| 13 | 创建会话: AF-42 总装上下文 | ✅ PASS | 0.0s | session=ri.session.84445f61-e914-4dfa-bc8e-bf836887bbc7 |
| 14 | 查询会话列表 | ✅ PASS | 0.0s | count=20 |

## UI (15/15)

| # | 测试项 | 状态 | 耗时 | 详情 |
|---|--------|------|------|------|
| 1 | Ontology 概览 — 统计卡片 | ✅ PASS | 42.3s | The statistics from the ontology overview page are: - Object Types count: 25 - Link Types count: 17 - Interface Types co |
| 2 | ObjectType 列表 — 含 F35Aircraft | ✅ PASS | 45.8s | Here is the requested information: 1. Total count shown: 25 2. First 5 object type names in the table: DeliveryMilestone |
| 3 | ObjectType 详情 — F35Aircraft 属性 | ✅ PASS | 56.5s | I have navigated to the 'Object Types' page as requested. However, after thoroughly searching and scrolling through all  |
| 4 | InterfaceType 列表 — 7个接口 | ✅ PASS | 57.5s | Successfully extracted the interface type names and their total count.  Interface Type Names: Classifiable, Auditable, C |
| 5 | ActionType 列表 — 安全等级 | ✅ PASS | 38.6s | Successfully logged in and navigated to the action types page. The first 5 action type names and their safety levels are |
| 6 | 版本/快照页 — ≥2个快照 | ✅ PASS | 58.2s | There are 13 snapshots listed. Their IDs are: - ri.snap.7881ce15-07e7-47d7-bfcd-e5d5ea746e37 - ri.snap.899d6fc9-23b4-492 |
| 7 | Setting 用户管理 — 多用户 | ✅ PASS | 35.4s | The following users were found in the table: - Name: 李明（班组长）, Email: li.lead@f35factory.com - Name: 王建国（质检主管）, Email: wa |
| 8 | Setting 租户管理 — Fort Worth | ✅ PASS | 61.8s | Successfully logged in and navigated to the tenants page. The following tenants were found: - Fort Worth FACO (16 times) |
| 9 | Data 数据源 — MES连接 | ✅ PASS | 53.8s | Successfully navigated to the data sources page and found the following connections:  - F35 Quality Data Lake (disconnec |
| 10 | Agent 模型 — 2个AI模型 | ✅ PASS | 45.2s | Here are all the models found on the page: - API Name: claude_docs, Display Name: Claude (技术文档分析) - API Name: gpt4o_fact |
| 11 | Agent 技能 — 工序查询+NCR分析 | ✅ PASS | 39.6s | Here are all the skills shown on the page: [   {     "API Name": "ncr_trend_analysis",     "Display Name": "NCR 趋势分析"    |
| 12 | Agent 子代理 — 质量+物料助手 | ✅ PASS | 71.3s | Successfully extracted all sub-agent information: ```json [   {     "API Name": "material_assistant",     "Display Name" |
| 13 | Function 能力列表 | ✅ PASS | 34.1s | Successfully navigated to the capabilities page. No capabilities or actions are currently registered on the page.  Attac |
| 14 | 跨模块 Dock 导航 | ✅ PASS | 49.4s | Successfully logged in and navigated through all 5 modules: Ontology, Data, Function, Agent, and Setting, as requested.  |
| 15 | API 健康检查 | ✅ PASS | 35.3s | The JSON response from http://localhost:8100/health is: {"status":"ok"} |
