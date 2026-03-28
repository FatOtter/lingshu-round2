# P2/P3 技术方案

## 待完成项目清单（9 项）

| # | 模块 | 问题 | 优先级 | 分组 |
|---|------|------|--------|------|
| F1 | Function | Overview 计数硬编码 `actions:0, workflows:0` | P2 | A |
| F2 | Function | Capability 目录缺少 Action 和 Workflow | P2 | A |
| F3 | Copilot | MCP 工具发现 + 连接测试是占位符 | P2 | B |
| F4 | Copilot | 多模型支持（目前只有 Gemini） | P2 | B |
| F5 | Copilot | Sub-Agent 嵌套执行是占位符 | P3 | B |
| F6 | Frontend | A2UI Chart 组件无真实图表渲染 | P2 | C |
| F7 | Data | EditLog FDB 后端（当前 PostgreSQL 代理） | P3 | D |
| F8 | Copilot | LLM 无 API Key 时 fallback 改进 | P2 | B |
| F9 | Frontend | Topology 空状态体验优化 | P2 | C |

---

## Group A: Function 模块补全

### F1: Overview 真实计数

**现状**: `function/service.py:716-720` 硬编码 `actions: 0, workflows: 0`

**方案**:
- `workflows` 计数：已有 `WorkflowRepository.count_by_tenant()`，直接调用
- `actions` 计数：通过 `OntologyService.query()` 获取 ActionType 总数
  - FunctionService 已持有 `_ontology_service: OntologyService` 引用
  - 调用 `_ontology_service.query_entities("action_type", limit=1)` 取 pagination.total

**改动文件**: `backend/src/lingshu/function/service.py`

```python
async def get_overview(self, session: AsyncSession) -> FunctionOverviewResponse:
    tenant_id = get_tenant_id()

    func_repo = GlobalFunctionRepository(session)
    func_count = await func_repo.count_by_tenant(tenant_id)

    wf_repo = WorkflowRepository(session)
    wf_count = await wf_repo.count_by_tenant(tenant_id)

    # ActionType count via ontology service
    action_count = 0
    if self._ontology_service:
        try:
            result = await self._ontology_service.query_entities(
                "action_type", page=1, page_size=1,
            )
            action_count = result.get("total", 0)
        except Exception:
            pass  # ontology unavailable, use 0

    exec_repo = ExecutionRepository(session)
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    by_status = await exec_repo.count_recent(tenant_id, since)
    total_24h = sum(by_status.values())

    return FunctionOverviewResponse(
        capabilities={"actions": action_count, "functions": func_count, "workflows": wf_count},
        recent_executions={"total_24h": total_24h, "by_status": by_status},
    )
```

### F2: Capability 目录聚合 Action + Workflow

**现状**: `function/service.py:696-699` 只返回 GlobalFunction

**方案**:
- 添加 ActionType 查询：通过 OntologyService 获取所有 ActionType，转为 CapabilityDescriptor
- 添加 Workflow 查询：通过 WorkflowRepository 获取所有 Workflow，转为 CapabilityDescriptor

```python
async def list_capabilities(self, session, *, capability_type=None):
    results = []

    # Functions
    if capability_type in (None, "function"):
        # ... existing code ...

    # Actions from ontology
    if capability_type in (None, "action") and self._ontology_service:
        action_types = await self._ontology_service.query_entities(
            "action_type", page=1, page_size=1000,
        )
        for at in action_types.get("items", []):
            results.append(CapabilityDescriptor(
                type="action",
                rid=at["rid"],
                api_name=at["api_name"],
                display_name=at.get("display_name", at["api_name"]),
                description=at.get("description", ""),
                parameters=at.get("parameters", []),
                outputs=at.get("outputs", []),
                safety_level=at.get("safety_level", "SAFETY_READ_ONLY"),
                side_effects=at.get("side_effects", []),
            ))

    # Workflows
    if capability_type in (None, "workflow"):
        wf_repo = WorkflowRepository(session)
        workflows, _ = await wf_repo.list_by_tenant(tenant_id, limit=1000)
        for wf in workflows:
            results.append(CapabilityDescriptor(
                type="workflow",
                rid=wf.rid,
                api_name=wf.api_name,
                display_name=wf.display_name,
                description=wf.description or "",
                parameters=[],
                outputs=[],
                safety_level="SAFETY_READ_ONLY",
                side_effects=[],
            ))

    return results
```

---

## Group B: Copilot 模块补全

### F3: MCP 真实工具发现 + 连接测试

**现状**: `copilot/infra/mcp.py:128-146` 返回空列表和 placeholder 状态

**方案**:
- MCP 协议支持两种传输：`stdio`（子进程）和 `sse`（HTTP SSE）
- 使用 `mcp` Python SDK（`pip install mcp`）实现真实协议通信
- 如果 MCP SDK 不可用，回退到 HTTP JSON-RPC 方式

**discover_tools 实现**:
```python
async def discover_tools(self, rid, session):
    conn = await self.get(rid, session)
    transport = conn.transport or {}
    transport_type = transport.get("type", "stdio")

    try:
        if transport_type == "stdio":
            tools = await self._discover_stdio(transport)
        elif transport_type == "sse":
            tools = await self._discover_sse(transport)
        else:
            raise AppError(code=ErrorCode.COMMON_VALIDATION,
                          message=f"Unknown transport type: {transport_type}")

        # Cache discovered tools in DB
        await self.update(rid, {
            "discovered_tools": tools,
            "status": "connected",
        }, session)
        return tools
    except Exception as e:
        await self.update(rid, {"status": "error"}, session)
        raise AppError(code=ErrorCode.COMMON_EXTERNAL,
                      message=f"MCP tool discovery failed: {e}")

async def _discover_stdio(self, transport):
    """Discover via stdio subprocess (JSON-RPC over stdin/stdout)."""
    import asyncio, json
    cmd = transport.get("command", "")
    args = transport.get("args", [])

    proc = await asyncio.create_subprocess_exec(
        cmd, *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Send tools/list JSON-RPC request
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    stdout, _ = await asyncio.wait_for(
        proc.communicate(request.encode()), timeout=30
    )

    response = json.loads(stdout.decode().strip().split("\n")[-1])
    tools = response.get("result", {}).get("tools", [])
    return [{"name": t["name"], "description": t.get("description", ""),
             "inputSchema": t.get("inputSchema", {})} for t in tools]

async def _discover_sse(self, transport):
    """Discover via SSE transport (HTTP)."""
    import httpx
    base_url = transport.get("url", "")
    auth = transport.get("auth", {})
    headers = {}
    if auth.get("type") == "bearer":
        headers["Authorization"] = f"Bearer {auth.get('token', '')}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/tools/list",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        tools = data.get("result", {}).get("tools", [])
        return [{"name": t["name"], "description": t.get("description", ""),
                 "inputSchema": t.get("inputSchema", {})} for t in tools]
```

**test_connection 实现**:
```python
async def test_connection(self, rid, session):
    conn = await self.get(rid, session)
    transport = conn.transport or {}
    transport_type = transport.get("type", "stdio")

    try:
        if transport_type == "stdio":
            # Test by launching and sending initialize
            import asyncio, json
            cmd = transport.get("command", "")
            args = transport.get("args", [])
            proc = await asyncio.create_subprocess_exec(
                cmd, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2024-11-05",
                                            "capabilities": {},
                                            "clientInfo": {"name": "lingshu", "version": "1.0"}}}) + "\n"
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(request.encode()), timeout=10
            )
            response = json.loads(stdout.decode().strip().split("\n")[-1])
            server_info = response.get("result", {}).get("serverInfo", {})
            return {"rid": rid, "status": "connected",
                    "server_name": server_info.get("name", "unknown"),
                    "server_version": server_info.get("version", "unknown")}
        elif transport_type == "sse":
            import httpx
            base_url = transport.get("url", "")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{base_url}/initialize",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05",
                                    "capabilities": {},
                                    "clientInfo": {"name": "lingshu", "version": "1.0"}}},
                )
                resp.raise_for_status()
                data = resp.json()
                server_info = data.get("result", {}).get("serverInfo", {})
                return {"rid": rid, "status": "connected",
                        "server_name": server_info.get("name", "unknown"),
                        "server_version": server_info.get("version", "unknown")}
    except Exception as e:
        return {"rid": rid, "status": "error", "message": str(e)}
```

### F4: 多模型 Provider 支持

**现状**: `copilot/agent/graph.py` 和 `copilot/agent/llm.py` 只支持 Gemini

**方案**: 创建 `LLMProvider` 抽象，支持 OpenAI、Anthropic、Azure、Gemini

**新文件**: `backend/src/lingshu/copilot/agent/providers.py`

```python
class LLMProvider(Protocol):
    async def chat(self, system_prompt, messages, tools=None) -> AsyncGenerator[str]: ...
    async def chat_with_tools(self, system_prompt, messages, tools) -> dict: ...

class OpenAIProvider(LLMProvider):
    """Uses openai SDK (also works for Azure with base_url)."""

class AnthropicProvider(LLMProvider):
    """Uses anthropic SDK."""

class GeminiProvider(LLMProvider):
    """Wraps existing GeminiClient."""
```

**AgentGraph 改造**:
```python
class AgentGraph:
    def __init__(self, function_service=None, *, llm_provider: LLMProvider | None = None):
        self._llm = llm_provider  # 替换 _gemini_client
```

**main.py 中根据配置初始化**:
```python
# Read default model config from DB at startup
# Or use env vars for quick setup
provider = create_provider(settings.copilot_provider, settings.copilot_api_key, settings.copilot_model)
agent_graph = AgentGraph(function_service=func_svc, llm_provider=provider)
```

### F5: Sub-Agent 真实嵌套执行

**现状**: `copilot/agent/graph.py:87-129` 返回占位文本

**方案**: 使用 AgentGraph 自身递归执行

```python
async def execute_subagent(self, subagent_tool, user_input, db_session):
    metadata = subagent_tool.get("metadata", {})
    system_prompt = metadata.get("system_prompt", "")
    agent_name = subagent_tool.get("name", "unknown")

    events = [{"type": "tool_start", "tool_name": agent_name, "params": {"input": user_input}}]

    if self._llm is None:
        # No LLM configured, return informational stub
        events.append({"type": "text_delta", "content": f"[{agent_name}] No model configured."})
        events.append({"type": "tool_end", "tool_name": agent_name, "status": "skipped"})
        return events

    # Create sub-state with sub-agent's system prompt
    sub_state = CopilotState(context=SessionContext(mode="agent"))

    # Execute with overridden system prompt
    sub_events = await self._process_with_llm(
        system_prompt or self.get_system_prompt(sub_state["context"]),
        user_input,
        [],  # Sub-agent tools from tool_bindings
        [],
        db_session,
        "main",
    )

    # Wrap sub-agent events
    for evt in sub_events:
        if evt["type"] == "text_delta":
            events.append({"type": "text_delta", "content": f"[{agent_name}] {evt['content']}"})
        elif evt["type"] != "done":
            events.append(evt)

    events.append({"type": "tool_end", "tool_name": agent_name, "status": "success"})
    return events
```

### F8: LLM Fallback 改进

**现状**: 无 API Key 时返回纯文本占位

**方案**: fallback 消息改为结构化引导，告诉用户如何配置模型

---

## Group C: Frontend 补全

### F6: A2UI Chart 真实渲染

**现状**: `components/a2ui/chart.tsx` 只显示图标

**方案**: 安装 `recharts`，实现真实图表渲染

```bash
cd frontend && pnpm add recharts
```

```tsx
// 支持 bar, line, pie, area 四种图表类型
import { BarChart, Bar, LineChart, Line, PieChart, Pie, AreaChart, Area,
         XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from "recharts";

export function A2UIChartView({ data }: { data: A2UIChart }) {
  const chartData = data.series.flatMap(s => s.data_points.map(dp => ({
    label: dp.label, [s.name]: dp.value
  })));
  // Merge data points by label
  // Render based on data.chart_type
}
```

### F9: Topology 空状态优化

**现状**: 空库显示 "No entities to display"

**方案**:
- 空状态显示引导卡片："Create your first ObjectType to see the topology"
- 添加快捷创建按钮链接到 `/ontology/object-types/new`
- 显示实体类型图例说明

---

## Group D: Data 模块

### F7: EditLog FDB 后端

**现状**: `data/writeback/fdb_client.py` 使用 PostgreSQL 代理

**方案**:
- FoundationDB 需要外部安装 `fdb` 客户端库 + 运行 FDB 集群
- 创建 `FdbEditLogStore` 实现相同接口
- 通过环境变量 `LINGSHU_EDITLOG_BACKEND=fdb|postgres` 切换
- 保持 PostgreSQL 作为默认后端（无需 FDB 集群即可运行）

```python
class FdbEditLogStore:
    """Real FoundationDB-backed EditLog store."""

    def __init__(self, cluster_file: str = "/etc/foundationdb/fdb.cluster"):
        import fdb
        fdb.api_version(730)
        self._db = fdb.open(cluster_file)

    async def write(self, entry: EditLogEntry) -> str:
        """Write entry in FDB transaction with row-level lock."""
        # Key: edit:{tenant}:{type_rid}:{pk_hash}:{timestamp}
        # Value: msgpack(entry)

    async def read_by_key(self, tenant_id, type_rid, primary_key, branch="main") -> list:
        """Range read by key prefix."""

    async def read_recent(self, tenant_id, *, branch="main", limit=100) -> list:
        """Range read recent entries."""
```

**注意**: FDB Python 客户端是同步的，需要 `run_in_executor` 包装

---

## 并行分组

| Group | 任务 | 改动文件 | 无冲突 |
|-------|------|---------|--------|
| **A** | F1, F2 | `function/service.py` | ✅ |
| **B** | F3, F4, F5, F8 | `copilot/infra/mcp.py`, `copilot/agent/graph.py`, 新建 `providers.py` | ✅ |
| **C** | F6, F9 | `components/a2ui/chart.tsx`, `components/ontology/topology-graph.tsx`, `package.json` | ✅ |
| **D** | F7 | `data/writeback/fdb_client.py`, `config.py`, `main.py` | ✅ |

四组无文件冲突，可以并行 Worktree 开发。

---

## 测试策略

每个 Group 对应测试：
- **A**: `test_capability_catalog.py`, `test_overview_stats.py`
- **B**: `test_mcp_protocol.py`, `test_multi_model.py`, `test_subagent_execution.py`
- **C**: `chart.test.tsx`, `topology-graph.test.tsx` (更新)
- **D**: `test_fdb_editlog.py`
