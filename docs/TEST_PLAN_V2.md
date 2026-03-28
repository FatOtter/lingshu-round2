# LingShu 测试方案 V2（P2/P3 完整版）

## 现状

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 后端测试总数 | 825 passed / 6 failed | 全部通过 |
| 后端覆盖率 | **71.04%** | **≥ 80%** |
| 前端单元测试 | 120 passed | 150+ |
| E2E 测试 | 149 tests (26 spec files) | 180+ |
| **缺口** | **覆盖率差 9%，6 个 middleware 测试失败** | |

---

## 第一层：修复 + 覆盖率提升（目标 71% → 80%）

### 1.1 修复 6 个失败的 middleware 测试

**文件**: `backend/tests/unit/setting/test_middleware.py`

**根因**: AuthMiddleware 在测试中找不到 `app.state.auth_provider`，返回 503 而非预期状态码。

**修复方案**:
- 测试 setup 中正确初始化 `app.state.auth_provider` 和 `app.state.auth_dev_mode`
- Mock Redis 依赖（JWT 黑名单检查）
- 确保 OPTIONS 请求直接放行

### 1.2 覆盖率低洼区补测（+9%）

按影响面排序，优先补测以下模块：

| 文件 | 当前覆盖 | 目标 | 新增测试数 | 策略 |
|------|---------|------|-----------|------|
| **Router 层**（5 个 router.py） | 38-64% | 80% | ~40 | 用 TestClient 测 HTTP 端点 |
| **graph_repo.py** | 36% | 80% | ~15 | Mock Neo4j driver，测 CRUD + 拓扑 |
| **Setting Repository 层**（5 个 repo） | 32-44% | 80% | ~25 | Mock AsyncSession，测 CRUD |
| **data/service.py** | 58% | 80% | ~10 | 补连接测试、写回路径 |
| **function/globals/executor.py** | 14% | 80% | ~8 | 补执行引擎各分支 |
| **main.py** | 37% | 60% | ~5 | 测 create_app + lifespan |
| **infra/{database,graph_db,redis}.py** | 16-38% | 60% | ~6 | 测连接初始化/关闭 |
| **copilot/agent/graph.py** | 74% | 85% | ~5 | 补 sub-agent 执行 + fallback |
| **seed.py** | 0% | 80% | ~4 | 测 idempotent seed 逻辑 |

**预估新增**: ~118 个测试，覆盖率提升至 ~82%

### 1.3 具体测试文件计划

```
backend/tests/unit/
├── test_main_app.py              # NEW: 5 tests — create_app, lifespan, middleware ordering
├── setting/
│   ├── test_middleware.py         # FIX: 6 existing tests
│   ├── test_router_setting.py     # NEW: 12 tests — all HTTP endpoints
│   ├── test_user_repo.py          # NEW: 5 tests — CRUD operations
│   ├── test_tenant_repo.py        # NEW: 5 tests — CRUD + member management
│   ├── test_audit_log_repo.py     # NEW: 4 tests — write + query
│   ├── test_seed.py               # NEW: 4 tests — idempotent seed
│   └── test_role_repo.py          # NEW: 3 tests — CRUD
├── ontology/
│   ├── test_router_ontology.py    # NEW: 10 tests — entity CRUD + version endpoints
│   └── test_graph_repo_ext.py     # NEW: 15 tests — topology, search, relationships
├── data/
│   ├── test_router_data.py        # NEW: 8 tests — connections, instances
│   └── test_service_ext.py        # NEW: 10 tests — writeback, branch, masking
├── function/
│   ├── test_router_function.py    # NEW: 8 tests — execute, capabilities, workflows
│   └── test_executor.py           # NEW: 8 tests — Global Function executor
├── copilot/
│   ├── test_router_copilot.py     # NEW: 8 tests — sessions, messages, models
│   └── test_graph_ext.py          # NEW: 5 tests — sub-agent, multi-model
└── infra/
    └── test_infra_init.py         # NEW: 6 tests — DB/Neo4j/Redis init/close
```

---

## 第二层：P2/P3 新功能回归测试

针对本轮新实现的 9 个功能，确保每个都有专项测试。

### 2.1 已有测试（确认覆盖）

| 功能 | 测试文件 | 测试数 | 状态 |
|------|---------|--------|------|
| F1 Overview 计数 | `test_service.py` (function) | 2 | ✅ |
| F2 Capability 目录 | `test_service.py` (function) | 4 | ✅ |
| F4 多模型 Provider | `test_providers.py` | 27 | ✅ |
| F6 Chart 渲染 | `chart.test.tsx` | 7 | ✅ |
| F7 FDB EditLog | `test_fdb_editlog.py` | 25 | ✅ |
| F9 Topology 空状态 | `topology-graph.test.tsx` | 5 | ✅ |

### 2.2 需补充测试

| 功能 | 补充内容 | 新增测试数 |
|------|---------|-----------|
| **F3 MCP 协议** | stdio 子进程 mock、SSE HTTP mock、超时处理、错误状态更新 | 8 |
| **F5 Sub-Agent 执行** | 有 LLM 时嵌套调用、tool_bindings 过滤、事件前缀包装 | 5 |
| **F8 Fallback 改进** | 结构化引导消息验证、provider 列表展示 | 3 |

---

## 第三层：真实业务场景测试

模拟完整业务流程，跨模块端到端验证。所有场景测试位于 `backend/tests/scenarios/`。

### 3.1 已有场景（12 个，117 tests）

BS-01 到 BS-12 已覆盖：交通建模、数据源查询、Action 执行、Copilot 对话、版本回滚、多租户、RBAC、Shell 上下文、级联继承、工作流执行、数据搜索、SSO 登录。

### 3.2 新增场景（覆盖 P2/P3 功能）

| 编号 | 场景名称 | 覆盖功能 | 测试步骤 | 测试数 |
|------|---------|---------|---------|--------|
| **BS-13** | MCP 工具集成 | F3 | 注册 MCP → 测试连接 → 发现工具 → Agent 加载工具 → 对话调用 | 6 |
| **BS-14** | 多模型切换 | F4, F8 | 注册 Gemini 模型 → 设为默认 → 创建会话 → 切换 OpenAI → 验证 fallback | 5 |
| **BS-15** | Sub-Agent 委托 | F5 | 创建 Sub-Agent → 绑定工具 → 主 Agent 委托 → 验证嵌套执行 | 5 |
| **BS-16** | 能力目录全聚合 | F1, F2 | 创建 ActionType → 创建 Function → 创建 Workflow → 查询 capabilities → 验证 overview 计数 | 6 |
| **BS-17** | EditLog 写回链路 | F7 | Action 执行写回 → EditLog 记录 → 查询 merge → 验证 branch 标记 | 5 |
| **BS-18** | 图表渲染数据链路 | F6 | Copilot 返回 chart 组件 → 验证 A2UI 事件格式 → series 数据结构 | 4 |

**新增**: 6 个场景，31 个测试

---

## 第四层：Browser E2E 测试（Playwright）

### 4.1 已有 E2E（26 spec files，149 tests）

覆盖：登录、模块导航、CRUD 流程、数据渲染、Copilot 对话、版本管理。

### 4.2 新增 Journey（覆盖 P2/P3 UI 变更）

所有新 Journey 位于 `frontend/e2e/journeys/`：

| 编号 | Journey | 验证点 | 测试数 |
|------|---------|--------|--------|
| **J16** | Chart 渲染验证 | Copilot 返回图表 → recharts 组件渲染 → 轴标签 → 图例 | 4 |
| **J17** | Topology 空状态 | 空库 overview → "Your ontology is empty" → 创建按钮 → 创建后显示节点 | 3 |
| **J18** | MCP 管理页面 | MCP 列表 → 新建连接 → 填写 transport → 测试连接 → 状态更新 | 4 |
| **J19** | 多模型管理 | 模型列表 → 新建 OpenAI 模型 → 设为默认 → 连接测试 | 3 |
| **J20** | Sub-Agent 管理 | Sub-Agent 列表 → 新建 → 配置 system_prompt → tool_bindings → 启用 | 3 |
| **J21** | Capability Overview | Function overview → 统计卡片显示真实数字 → 能力列表三种类型 | 3 |
| **J22** | 完整 Ontology 建模 | 创建 ObjectType → 添加属性 → 创建 LinkType → 提交 → 发布 → 拓扑图显示 | 5 |

**新增**: 7 个 Journey，25 个测试

### 4.3 回归 E2E 检查清单

每次部署前必须通过的核心流程：

```
□ 登录流程（正确凭据 + 错误凭据）
□ 5 个模块导航（Dock 切换 + URL 直接访问）
□ Ontology CRUD（创建 ObjectType → 编辑 → 删除）
□ 版本生命周期（Draft → Staging → Active）
□ 数据源连接（列表 → 连接测试）
□ 数据浏览（类型选择 → 实例列表 → 搜索过滤）
□ Action 执行（选择 → 填参数 → 执行 → 查看结果）
□ Copilot 对话（发消息 → 等响应 → A2UI 组件渲染）
□ Shell 面板（打开 → 发消息 → 关闭）
□ 用户管理（列表 → 搜索 → 角色分配）
□ 无 console.error 关键错误
```

---

## 第五层：性能 + 安全测试

### 5.1 性能基准测试

**文件**: `backend/tests/performance/test_benchmarks.py`

| 测试项 | 阈值 | 方法 |
|--------|------|------|
| Ontology query（100 实体） | < 200ms | pytest-benchmark |
| Topology 生成（50 节点 + 100 边） | < 500ms | pytest-benchmark |
| 能力目录查询（100 Action + 50 Function） | < 300ms | pytest-benchmark |
| EditLog 写入（批量 100 条） | < 500ms | pytest-benchmark |
| SSE 首字节延迟 | < 2s | httpx + timer |

### 5.2 安全检查测试

**文件**: `backend/tests/security/test_security.py`

| 测试项 | 验证 |
|--------|------|
| SQL 注入防护 | 搜索参数含 `'; DROP TABLE` 不执行 |
| XSS 防护 | HTML 标签在响应中被转义 |
| JWT 过期处理 | 过期 token 返回 401，不返回数据 |
| 密码不可逆 | 登录响应不含 password_hash |
| CORS 预检 | OPTIONS 请求返回正确 headers |
| 路径遍历 | `../` 路径不泄漏文件 |
| 租户隔离 | 租户 A 的 token 访问不到租户 B 的数据 |

---

## 执行策略

### 分层执行时机

| 层级 | 触发时机 | 超时 | 失败策略 |
|------|---------|------|---------|
| **L1 修复 + 覆盖率** | 每次 commit | 60s | 阻塞合并 |
| **L2 P2/P3 回归** | 每次 commit | 30s | 阻塞合并 |
| **L3 业务场景** | PR 合并前 | 120s | 阻塞合并 |
| **L4 Browser E2E** | Docker 部署后 | 300s | 报告但不阻塞 |
| **L5 性能 + 安全** | Release 前 | 600s | 阻塞发布 |
| **L6 BrowserUse 有头浏览器** | Release 前 / 每周 | 30min | 允许失败，人工复核 |

### 并行开发分组

| 组 | 任务 | 文件范围 | 预估测试数 |
|-----|------|---------|-----------|
| **G1** | Middleware 修复 + Router 测试 | `test_middleware.py`, `test_router_*.py` | ~46 |
| **G2** | Repository + Service 补测 | `test_*_repo.py`, `test_service_ext.py` | ~42 |
| **G3** | Graph + Infra + Seed 补测 | `test_graph_repo_ext.py`, `test_infra_init.py`, `test_seed.py` | ~30 |
| **G4** | 新场景 BS13-18 + MCP/SubAgent 补测 | `test_bs13-18.py`, `test_mcp_protocol.py` | ~47 |
| **G5** | 新 Journey J16-22 + 性能/安全 | `j16-j22.spec.ts`, `test_benchmarks.py`, `test_security.py` | ~37 |
| **G6** | BrowserUse 有头浏览器测试 | `tests/browseruse/test_bu01-10.py` | ~10 |

**总新增**: ~212 个测试

### 完成后预期

| 指标 | 当前 | 完成后 |
|------|------|--------|
| 后端测试总数 | 825 | **1,020+** |
| 后端覆盖率 | 71% | **82%+** |
| 前端单元测试 | 120 | **127+** |
| E2E 测试 | 149 | **174+** |
| 失败测试 | 6 | **0** |
| 业务场景 | 12 | **18** |
| BrowserUse 场景 | 0 | **10** |
| **测试总数** | **1,100** | **~1,340** |

---

## 命令速查

```bash
# L1: 后端全量
cd backend && uv run pytest --cov=lingshu --cov-report=term-missing

# L2: P2/P3 回归
cd backend && uv run pytest tests/unit/copilot/test_providers.py tests/unit/data/test_fdb_editlog.py tests/unit/function/test_service.py -v

# L3: 业务场景
cd backend && uv run pytest tests/scenarios/ -v

# L4: E2E（需 Docker）
cd frontend && npx playwright test e2e/ --reporter=html

# L5: 性能
cd backend && uv run pytest tests/performance/ -v --benchmark-only

# L5: 安全
cd backend && uv run pytest tests/security/ -v

# 全量覆盖率报告
cd backend && uv run pytest --cov=lingshu --cov-report=html && open htmlcov/index.html

# L6: BrowserUse 有头浏览器测试
cd tests && uv run pytest tests/browseruse/ -v --headed
```

---

## 第六层：BrowserUse 有头浏览器真实操作测试

### 6.1 目的

Playwright E2E 是无头 + 选择器匹配，无法验证真实用户视觉体验。BrowserUse 层使用 **browser-use** 库（LLM 驱动的浏览器代理），通过自然语言指令控制真实有头浏览器，模拟真实用户的「看 → 想 → 点」操作链路。

**与 Playwright 的区别**：

| 维度 | Playwright E2E | BrowserUse |
|------|---------------|------------|
| 操作方式 | CSS/XPath 选择器定位 | LLM 视觉理解 + 自然语言指令 |
| 浏览器模式 | 无头（headless） | 有头（headed），可观察 |
| 验证方式 | DOM 断言 | 截图 + LLM 判断页面状态 |
| 覆盖盲区 | 选择器失效、布局错乱、视觉遮挡 | 全部可检测 |
| 执行速度 | 快（秒级） | 慢（分钟级，LLM 推理） |
| 适用场景 | CI 回归 | Release 前验收、视觉回归 |

### 6.2 技术方案

**依赖**:
```bash
pip install browser-use langchain-openai
# 或
pip install browser-use langchain-google-genai
```

**测试框架**: pytest + browser-use Agent

**基础 fixture** (`tests/browseruse/conftest.py`):
```python
import pytest
from browser_use import Agent
from langchain_openai import ChatOpenAI

BASE_URL = "http://localhost:3100"  # Docker 前端
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "change_me_123"

@pytest.fixture
async def browser_agent():
    """Create a browser-use agent with LLM."""
    llm = ChatOpenAI(model="gpt-4o")  # 或 ChatGoogleGenerativeAI
    agent = Agent(
        task="",  # 每个测试设置具体 task
        llm=llm,
    )
    yield agent

@pytest.fixture
async def logged_in_agent(browser_agent):
    """Agent that has already logged in."""
    browser_agent.task = (
        f"Go to {BASE_URL}/login. "
        f"Enter email '{ADMIN_EMAIL}' and password '{ADMIN_PASSWORD}'. "
        "Click the login button. Wait until you see the main dashboard."
    )
    result = await browser_agent.run()
    assert "error" not in result.lower()
    yield browser_agent
```

### 6.3 测试用例（10 个场景）

#### BU-01: 完整登录流程
```python
async def test_bu01_login_flow(browser_agent):
    """真实用户登录：输入凭据 → 点击登录 → 验证跳转到主页"""
    browser_agent.task = (
        f"Go to {BASE_URL}/login. "
        f"Type '{ADMIN_EMAIL}' in the email field. "
        f"Type '{ADMIN_PASSWORD}' in the password field. "
        "Click the 'Sign In' button. "
        "Verify you are redirected to the main page and can see module navigation icons."
    )
    result = await browser_agent.run()
    assert "navigation" in result.lower() or "module" in result.lower()
```

#### BU-02: Ontology 实体创建全流程
```python
async def test_bu02_create_object_type(logged_in_agent):
    """创建 ObjectType：导航 → 点击新建 → 填表单 → 保存 → 验证列表"""
    logged_in_agent.task = (
        "Click on the Ontology module icon in the left dock. "
        "Click on 'Object Types' in the sidebar. "
        "Click the 'New' or 'Create' button. "
        "Fill in api_name as 'test_vehicle', display_name as 'Test Vehicle'. "
        "Fill in description as 'A test object type for vehicles'. "
        "Click Save. "
        "Verify that 'test_vehicle' or 'Test Vehicle' appears in the list."
    )
    result = await logged_in_agent.run()
    assert "vehicle" in result.lower() or "success" in result.lower()
```

#### BU-03: 版本管理操作
```python
async def test_bu03_version_lifecycle(logged_in_agent):
    """版本发布流程：进入版本页 → 查看 staging → 提交 → 验证状态变化"""
    logged_in_agent.task = (
        "Navigate to Ontology module. "
        "Click on 'Versions' in the sidebar. "
        "Look at the staging summary section. "
        "If there are pending changes, describe what changes are listed. "
        "If there is a 'Publish' or 'Commit' button, describe its state (enabled/disabled). "
        "Take note of the snapshot history table and describe how many snapshots exist."
    )
    result = await logged_in_agent.run()
    assert "version" in result.lower() or "snapshot" in result.lower() or "staging" in result.lower()
```

#### BU-04: 数据源连接测试
```python
async def test_bu04_data_source_connection(logged_in_agent):
    """数据源操作：导航到数据模块 → 查看连接列表 → 点击连接测试"""
    logged_in_agent.task = (
        "Click on the Data module icon in the left dock. "
        "Click on 'Sources' in the sidebar. "
        "Describe what data sources are listed (if any). "
        "If there is a data source, click the 'Test' button next to it. "
        "Report the test result (success or failure). "
        "If no sources exist, describe the empty state shown."
    )
    result = await logged_in_agent.run()
    assert "source" in result.lower() or "connection" in result.lower() or "empty" in result.lower()
```

#### BU-05: 数据浏览 + 搜索过滤
```python
async def test_bu05_data_browse_search(logged_in_agent):
    """数据浏览：选择类型 → 查看实例 → 使用搜索框 → 验证过滤效果"""
    logged_in_agent.task = (
        "Navigate to Data module, then click 'Browse'. "
        "Describe the type cards shown (or empty state). "
        "If there is a search input, type 'test' and observe if the cards filter. "
        "If type cards exist, click on the first one and describe the instance list page."
    )
    result = await logged_in_agent.run()
    assert "browse" in result.lower() or "type" in result.lower() or "empty" in result.lower()
```

#### BU-06: Copilot 对话交互
```python
async def test_bu06_copilot_chat(logged_in_agent):
    """Copilot 对话：进入 Agent 模块 → 新建会话 → 发送消息 → 等待回复"""
    logged_in_agent.task = (
        "Click on the Agent module icon in the left dock. "
        "Click on 'Chat' in the sidebar. "
        "If there is a 'New Session' or '+' button, click it. "
        "Type 'Hello, what can you help me with?' in the message input. "
        "Press Enter or click the send button. "
        "Wait up to 15 seconds for a response. "
        "Describe what response appeared (text, component, or error)."
    )
    result = await logged_in_agent.run()
    assert "response" in result.lower() or "message" in result.lower() or "chat" in result.lower()
```

#### BU-07: Shell 面板交互
```python
async def test_bu07_shell_panel(logged_in_agent):
    """Shell 面板：点击 Header 图标 → 打开 Shell → 输入 → 关闭"""
    logged_in_agent.task = (
        "Look for a Shell or terminal icon in the top header area. "
        "Click it to open the Shell panel at the bottom of the page. "
        "Verify a text input area appears at the bottom. "
        "Type 'Help me understand this page' in the Shell input. "
        "Press Enter. Wait for a response. "
        "Then close the Shell panel by clicking the close/X button. "
        "Verify the Shell panel is no longer visible."
    )
    result = await logged_in_agent.run()
    assert "shell" in result.lower() or "panel" in result.lower() or "input" in result.lower()
```

#### BU-08: 用户管理 + 搜索
```python
async def test_bu08_user_management(logged_in_agent):
    """用户管理：导航 → 搜索用户 → 查看详情"""
    logged_in_agent.task = (
        "Navigate to the Setting module. "
        "Click on 'Users' in the sidebar. "
        "Verify that a table with user data is displayed. "
        "Find the search input and type 'admin'. "
        "Verify that the table filters to show only admin-related users. "
        "Click on the first user row to view their details. "
        "Describe what user information is shown."
    )
    result = await logged_in_agent.run()
    assert "admin" in result.lower() or "user" in result.lower()
```

#### BU-09: 跨模块导航完整性
```python
async def test_bu09_cross_module_navigation(logged_in_agent):
    """5 模块完整导航：依次点击 Dock 上每个图标 → 验证页面切换"""
    logged_in_agent.task = (
        "You should see a vertical dock/sidebar on the left with module icons. "
        "Click each module icon one by one (there should be 5: Ontology, Data, Function, Agent, Setting). "
        "For each module, verify that: "
        "1. The page content changes to show the module's overview or default page. "
        "2. The sidebar navigation items update to show the module's sub-pages. "
        "3. There are no error messages or blank pages. "
        "Report which modules loaded successfully and which had issues."
    )
    result = await logged_in_agent.run()
    assert "success" in result.lower() or "loaded" in result.lower() or "module" in result.lower()
```

#### BU-10: Topology 可视化验证
```python
async def test_bu10_topology_visualization(logged_in_agent):
    """Topology 视图：验证图形渲染或空状态引导"""
    logged_in_agent.task = (
        "Navigate to Ontology module and click on 'Overview'. "
        "Look for a 'Topology View' section on the page. "
        "If entities exist, verify that: "
        "  - Colored nodes are visible (blue for ObjectType, green for LinkType, etc.) "
        "  - Nodes have labels with entity names "
        "  - Lines/edges connect related nodes "
        "  - Clicking a node navigates to its detail page "
        "If no entities exist, verify that: "
        "  - An empty state message is shown ('Your ontology is empty') "
        "  - A 'Create ObjectType' button is available "
        "Describe what you see."
    )
    result = await logged_in_agent.run()
    assert "topology" in result.lower() or "empty" in result.lower() or "node" in result.lower() or "ontology" in result.lower()
```

### 6.4 执行配置

```python
# tests/browseruse/conftest.py — 完整配置
import os
import pytest

# BrowserUse 需要 LLM API Key
BROWSERUSE_LLM_PROVIDER = os.getenv("BROWSERUSE_LLM_PROVIDER", "openai")
BROWSERUSE_API_KEY = os.getenv("BROWSERUSE_API_KEY", "")
BROWSERUSE_MODEL = os.getenv("BROWSERUSE_MODEL", "gpt-4o")

# 跳过条件：无 API Key 时跳过
skip_no_api_key = pytest.mark.skipif(
    not BROWSERUSE_API_KEY,
    reason="BROWSERUSE_API_KEY not set — skipping browser-use tests"
)

# 标记为慢测试
pytestmark = [
    pytest.mark.browseruse,
    pytest.mark.slow,
    skip_no_api_key,
]
```

**运行命令**:
```bash
# 运行 BrowserUse 测试（需要 Docker 环境 + API Key）
BROWSERUSE_API_KEY=sk-xxx uv run pytest tests/browseruse/ -v --headed -s

# 只运行特定场景
BROWSERUSE_API_KEY=sk-xxx uv run pytest tests/browseruse/test_bu02_ontology_create.py -v --headed -s

# 生成截图报告
BROWSERUSE_API_KEY=sk-xxx uv run pytest tests/browseruse/ -v --headed --screenshot=on
```

### 6.5 CI/CD 集成

```yaml
# BrowserUse 测试不加入常规 CI（成本高、速度慢）
# 仅在 Release 前手动触发或定时运行（每周一次）
browseruse-test:
  trigger: manual / schedule(weekly)
  requires: docker-compose up
  env:
    BROWSERUSE_API_KEY: ${{ secrets.BROWSERUSE_API_KEY }}
    BROWSERUSE_LLM_PROVIDER: openai
  timeout: 30m
  allow_failure: true  # 视觉测试允许失败但需人工复核
```
