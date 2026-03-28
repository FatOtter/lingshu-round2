# CLAUDE.md

## 文档地图

| 文档 | 职责 | 何时必读 |
|------|------|----------|
| `DESIGN.md` | 整体设计：四个能力域的定位、边界、依赖关系、数据流 | 涉及能力域边界划分、跨域数据流、新增能力域职责 |
| `TECH_DESIGN.md` | 技术设计：API 规范、RID、错误处理、存储架构、模块通信、演进策略 | 涉及 API 设计、RID 生成、错误码、日志、配置管理、服务拆分 |
| `PRODUCT_DESIGN.md` | 产品设计：页面布局、模块结构、侧边面板、Sitemap、通用交互原则 | 涉及前端页面结构、模块导航、路由设计、UI 交互模式 |
| `ONTOLOGY_DESIGN.md` | 本体模块：Ontology CRUD、版本发布流程、继承/级联、Neo4j 存储 | 涉及本体实体增删改查、Draft→Active 发布流程、图数据库操作 |
| `DATA_DESIGN.md` | 数据模块：数据源连接、实例查询/写入、EditLog、分支 | 涉及数据源管理、实例 CRUD、FDB EditLog、Iceberg/Doris |
| `FUNCTION_DESIGN.md` | 能力模块：原子能力注册、工作流编排、执行引擎、沙箱 | 涉及 Action 执行、Global Function、工作流 DAG、沙箱隔离 |
| `COPILOT_DESIGN.md` | 智能体模块：Agent 引擎、A2UI 协议、会话管理、MCP/Sub-Agent | 涉及 LangGraph Agent、流式对话、Tool 绑定、基座模型管理 |
| `SETTING_DESIGN.md` | 设置模块：认证（JWT）、用户管理、审计日志、租户管理、RBAC | 涉及认证流程、用户/租户 CRUD、审计日志查询、权限设计 |
| `ONTOLOGY.md` | 本体系统：实体定义、关系、版本管理、级联更新、数据映射 | 涉及 Ontology 实体、版本生命周期、图数据库、数据模型 |
| `proto/*.proto` | 源头真理：所有实体的字段定义 | 涉及实体字段、数据类型、枚举值、校验规则 |

## 核心术语

| 术语 | 含义 |
|------|------|
| 四个能力域（后端） | Ontology、Data、Function、Copilot |
| 五个前端模块 | 本体、数据、能力、智能体、设置 |
| 原子能力 | Ontology Action + Global Function 的统称 |
| 工作流 | 由多个原子能力编排而成的组合执行流程 |
| RID | 资源标识符，格式 `ri.{resource_type}.{uuid}` |

## Ontology 系统

Proto 是源头真理。

**源头文件**：
- `ONTOLOGY.md` - 本体系统完整指南（实体定义、关系、版本管理、级联更新）
- `proto/ontology.proto` - 核心实体定义（SharedPropertyType、PropertyType、InterfaceType、ObjectType、LinkType、ActionType）
- `proto/common.proto` - 数据类型、AssetMapping
- `proto/interaction.proto` - UI 组件配置
- `proto/validation.proto` - 校验规则定义

## 强制规则

1. 涉及以下工作时，必须先读取 ONTOLOGY.md 和相关 proto 文件：
   - 设计/实现数据模型相关代码
   - 实现版本管理功能（Draft/Staging/Snapshot/Active 四阶段）
   - 实现继承、级联更新、依赖检测逻辑
   - 实现图数据库相关功能（Neo4j）
   - 处理 ObjectType、LinkType、PropertyType、SharedPropertyType、InterfaceType、ActionType 等实体
   - 实现 Action 参数解析和执行逻辑
   - 实现校验规则（PropertyValidationConfig / EntityValidationConfig）

2. 涉及能力域职责划分、跨域调用时，必须先读取 DESIGN.md

3. 涉及 API 设计、RID 生成、错误处理时，必须先读取 TECH_DESIGN.md

4. 涉及前端页面结构、模块导航、路由时，必须先读取 PRODUCT_DESIGN.md

5. 任何偏离 ONTOLOGY.md 和 Proto 定义的实现都是错误的

6. 新增或修改实体字段必须先改 proto，再改 ONTOLOGY.md，最后改代码
