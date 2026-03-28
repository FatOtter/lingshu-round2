# LingShu 快速上手指南

> 从零开始，5 分钟跑起来。

---

## 1. 前置条件

你只需要安装以下两样东西：

| 工具 | 最低版本 | 安装方式 |
|------|---------|---------|
| **Docker Desktop** | 24+ | [下载地址](https://www.docker.com/products/docker-desktop/) |
| **Git** | 2.30+ | macOS 自带 / `brew install git` |

> Docker Desktop 安装后，请确保它正在运行（菜单栏能看到 Docker 图标）。
>
> **硬件要求**：4 核 CPU / 8GB 内存 / 10GB 可用磁盘。

---

## 2. 获取代码

### 方式一：SSH（推荐）

需要先配置 SSH 密钥访问 Gitea。如果你还没有 SSH 密钥：

```bash
# 1. 生成密钥（一路回车即可）
ssh-keygen -t ed25519 -C "your-email@example.com"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub
# 将输出的内容复制到剪贴板
```

然后登录 Gitea 添加公钥：
1. 浏览器打开 https://115.191.48.223/gitea/
2. 用你的账号登录
3. 点右上角头像 → **设置** → **SSH / GPG 密钥** → **添加密钥**
4. 粘贴公钥，保存

配置 SSH 连接：

```bash
# 编辑 SSH 配置
cat >> ~/.ssh/config << 'EOF'

Host 115.191.48.223
    HostName 115.191.48.223
    Port 2222
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
EOF
```

然后克隆代码：

```bash
git clone ssh://git@115.191.48.223:2222/yangfan/Lingshu-Round2.git
cd Lingshu-Round2
```

### 方式二：HTTPS

```bash
git clone https://115.191.48.223/gitea/yangfan/Lingshu-Round2.git
cd Lingshu-Round2
```

> 首次克隆如果提示 SSL 证书问题，执行：
> `git -c http.sslVerify=false clone https://115.191.48.223/gitea/yangfan/Lingshu-Round2.git`

---

## 3. 一键启动

```bash
docker compose up -d
```

首次启动需要 **3-5 分钟**（下载镜像 + 构建应用），请耐心等待。

查看启动进度：

```bash
# 查看所有容器状态
docker compose ps

# 实时查看构建/启动日志
docker compose logs -f
```

当你看到所有 5 个服务状态为 `Up (healthy)` 时，就启动成功了：

```
NAME                        STATUS
lingshu-round2-postgres-1   Up (healthy)
lingshu-round2-neo4j-1      Up (healthy)
lingshu-round2-redis-1      Up (healthy)
lingshu-round2-backend-1    Up (healthy)
lingshu-round2-frontend-1   Up
```

> **注意**：Neo4j 启动较慢（约 30 秒），backend 依赖 Neo4j 所以也会稍等。
> 如果 backend 状态显示 `starting` 或 `unhealthy`，多等 30 秒再看。

---

## 4. 打开浏览器

访问 **http://localhost:3100**

登录信息：

| 字段 | 值 |
|------|-----|
| 邮箱 | `admin@lingshu.dev` |
| 密码 | `admin123` |

登录后自动跳转到 Ontology Overview 页面。

---

## 5. 功能导览

登录后，屏幕底部有一个 **Dock 导航栏**，包含 5 个模块图标。点击切换模块。

### 5.1 Ontology（本体建模）

定义你的数据模型 — 就像数据库建表，但更高级。

| 页面 | 路径 | 说明 |
|------|------|------|
| **Overview** | /ontology/overview | 拓扑图总览，可视化查看所有实体类型和关系 |
| **Object Types** | /ontology/object-types | 对象类型管理（类似"表"的概念） |
| **Link Types** | /ontology/link-types | 关系类型管理（对象之间的关联关系） |
| **Interface Types** | /ontology/interface-types | 接口类型（多个类型共享的字段组合） |
| **Action Types** | /ontology/action-types | 动作类型（可执行的原子能力） |
| **Shared Properties** | /ontology/shared-property-types | 共享属性类型 |
| **Versions** | /ontology/versions | 版本管理（草稿 → 暂存 → 发布） |

#### 快速体验：创建一个 Object Type

1. 点击 **Object Types** 进入列表页
2. 点击右上角 **New** 按钮
3. 填写表单：
   - API Name: `employee`（英文标识符）
   - Display Name: `员工`
   - Description: `员工信息`
4. 点击 **Save**
5. 回到列表页，可以看到刚创建的类型

#### 版本管理流程

LingShu 的本体修改不会直接生效，而是经过一个审批流程：

```
你的修改（Draft 草稿）
  ↓ 提交到暂存区
暂存区（Staging）— 所有人可见
  ↓ 发布
快照（Snapshot）— 不可变的历史版本
  ↓ 自动
生效版本（Active）— 当前系统使用的版本
```

1. 创建/修改任何类型后，该修改处于 **Draft** 状态
2. 进入 **Versions** 页面，可以看到 **Staging Summary**（暂存区摘要）
3. 点击 **Publish** 发布暂存区的所有修改为一个新版本快照

### 5.2 Data（数据管理）

连接外部数据源，浏览和查询数据。

| 页面 | 路径 | 说明 |
|------|------|------|
| **Overview** | /data/overview | 数据模块总览 |
| **Sources** | /data/sources | 数据源连接管理 |
| **Browse** | /data/browse | 数据浏览和搜索 |

#### 快速体验：添加数据源

1. 点击 **Sources** 进入数据源页面
2. 点击 **New Connection**
3. 选择连接类型（PostgreSQL / Doris / Iceberg）
4. 填写连接信息（主机、端口、数据库名、用户名、密码）
5. 点击 **Test** 测试连接
6. 连接成功后点击 **Save**

### 5.3 Function（能力管理）

管理可执行的全局函数和工作流。

| 页面 | 路径 | 说明 |
|------|------|------|
| **Overview** | /function/overview | 能力模块总览 |
| **Capabilities** | /function/capabilities | 能力目录（Action + Global Function 统一视图） |
| **Global Functions** | /function/capabilities/globals | 全局函数管理 |
| **Workflows** | /function/workflows | 工作流编排 |

### 5.4 Agent（智能体）

AI Agent 配置和对话。

| 页面 | 路径 | 说明 |
|------|------|------|
| **Overview** | /agent/overview | 智能体模块总览 |
| **Chat** | /agent/chat | 与 AI 助手对话（需配置 LLM API Key） |
| **Models** | /agent/models | 基座模型注册（Gemini / OpenAI / Anthropic） |
| **Skills** | /agent/skills | 技能管理 |
| **MCP** | /agent/mcp | MCP（Model Context Protocol）服务连接 |
| **Sub-Agents** | /agent/sub-agents | 子代理配置 |
| **Sessions** | /agent/sessions | 会话历史 |
| **Monitor** | /agent/monitor | 运行监控 |

#### 启用 AI 对话

默认情况下 AI 对话需要配置 LLM API Key：

1. 进入 **Models** 页面，注册一个模型（如 Gemini）
2. 或者在启动时通过环境变量配置（编辑 `docker-compose.yml`）：
   ```yaml
   LINGSHU_COPILOT_PROVIDER: "gemini"   # gemini / openai / anthropic
   LINGSHU_COPILOT_API_KEY: "your-api-key-here"
   LINGSHU_COPILOT_MODEL: "gemini-2.0-flash"
   ```
3. 修改后重启 backend：`docker compose restart backend`
4. 进入 **Chat** 页面即可对话

### 5.5 Setting（系统设置）

用户管理、租户管理、审计日志。

| 页面 | 路径 | 说明 |
|------|------|------|
| **Overview** | /setting/overview | 系统概览（用户数、租户数等） |
| **Users** | /setting/users | 用户管理（创建、禁用、重置密码） |
| **Tenants** | /setting/tenants | 租户管理（多租户隔离） |
| **Audit** | /setting/audit | 审计日志查询 |

#### 快速体验：创建新用户

1. 点击 **Users** → **New User**
2. 填写邮箱、姓名、密码
3. 新用户使用该邮箱密码登录即可

---

## 6. 端口说明

如果你本机的某些端口已被占用，以下是 LingShu 使用的端口：

| 端口 | 服务 | 说明 |
|------|------|------|
| **3100** | 前端 Web UI | 浏览器访问地址 |
| **8100** | 后端 API | 前端调用的 API 服务 |
| 5440 | PostgreSQL | 关系数据库（可选暴露，调试用） |
| 7480 | Neo4j Browser | 图数据库管理界面 http://localhost:7480 |
| 7690 | Neo4j Bolt | 图数据库连接协议 |
| 6390 | Redis | 缓存服务 |

> 这些端口都做了偏移以避免与常见服务冲突（如默认的 5432、7474 等）。

---

## 7. 常用操作

### 停止服务

```bash
docker compose down          # 停止并移除容器（数据保留）
```

### 重新启动

```bash
docker compose up -d         # 后台启动（不需要重新构建）
```

### 更新代码后重新部署

```bash
git pull                              # 拉取最新代码
docker compose build backend frontend # 重新构建镜像
docker compose up -d                  # 启动新版本
```

### 查看日志

```bash
docker compose logs -f backend    # 后端日志（实时跟踪）
docker compose logs -f frontend   # 前端日志
docker compose logs -f            # 所有服务日志
```

### 完全清除重来

```bash
docker compose down -v       # 停止容器 + 删除数据卷（所有数据将丢失！）
docker compose up -d         # 全新启动
```

---

## 8. API 接口

后端提供 RESTful API，开发环境可以通过 Swagger 文档查看：

- **Swagger UI**: http://localhost:8100/docs
- **ReDoc**: http://localhost:8100/redoc
- **OpenAPI JSON**: http://localhost:8100/openapi.json

API 前缀：

| 模块 | 前缀 | 示例 |
|------|------|------|
| Setting | `/setting/v1/` | `/setting/v1/auth/login` |
| Ontology | `/ontology/v1/` | `/ontology/v1/object-types/query` |
| Data | `/data/v1/` | `/data/v1/connections/query` |
| Function | `/function/v1/` | `/function/v1/capabilities/query` |
| Copilot | `/copilot/v1/` | `/copilot/v1/sessions/query` |

### 快速测试 API

```bash
# 健康检查
curl http://localhost:8100/health

# 登录获取 Cookie
curl -c cookies.txt -X POST http://localhost:8100/setting/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@lingshu.dev","password":"admin123"}'

# 使用 Cookie 调用 API
curl -b cookies.txt http://localhost:8100/setting/v1/auth/me
```

---

## 9. 故障排查

### 问题：`docker compose up` 报错 "port is already in use"

某个端口被占用了。查看哪个进程占用了端口并关闭它：

```bash
# macOS
lsof -i :3100    # 查看占用 3100 端口的进程
kill <PID>       # 杀掉对应进程

# 或者修改 docker-compose.yml 中的端口映射
# 例如把 "3100:3000" 改为 "3200:3000"
```

### 问题：backend 一直 unhealthy

```bash
# 查看后端日志
docker compose logs backend | tail -30

# 常见原因：
# 1. Neo4j 还没启动好 — 等 30 秒再看
# 2. 数据库迁移失败 — 看日志中的 alembic 错误
# 3. 网络问题导致 pip 包下载失败 — 重试 docker compose build backend
```

### 问题：前端页面白屏

```bash
# 确认后端是否正常
curl http://localhost:8100/health
# 如果返回 {"status":"ok"} 说明后端正常

# 清除浏览器缓存，或用无痕模式打开 http://localhost:3100
```

### 问题：登录后页面数据为空

这是正常的 — 系统刚启动，还没有创建任何本体类型或数据。
按照第 5 节的指引创建 Object Type 即可看到数据。

### 问题：Docker 构建太慢

```bash
# 使用 Docker BuildKit 加速（一般默认已启用）
DOCKER_BUILDKIT=1 docker compose build

# 或者只构建有变更的服务
docker compose build backend    # 只重建后端
docker compose build frontend   # 只重建前端
```

---

## 10. 技术架构一览

```
┌─────────────────────────────────────────────────────┐
│                   浏览器 (localhost:3100)              │
│                 Next.js 15 + TypeScript               │
└─────────────────────────┬───────────────────────────┘
                          │ HTTP API
┌─────────────────────────▼───────────────────────────┐
│                 FastAPI (localhost:8100)               │
│    Setting │ Ontology │ Data │ Function │ Copilot     │
└───┬──────────┬──────────────┬───────────────────────┘
    │          │              │
    ▼          ▼              ▼
 ┌──────┐  ┌──────┐     ┌────────┐
 │Postgre│  │Neo4j │     │ Redis  │
 │ SQL   │  │(图DB) │     │(缓存)  │
 └──────┘  └──────┘     └────────┘
  :5440     :7690         :6390
```

- **PostgreSQL**: 存储用户、租户、审计日志、版本快照等关系型数据
- **Neo4j**: 存储本体实体和关系的图结构（Object Types, Link Types 等）
- **Redis**: JWT 黑名单、编辑锁、提交锁等缓存

---

## 有问题？

联系杨帆（yangfan），或在 Gitea 上提 Issue：
https://115.191.48.223/gitea/yangfan/Lingshu-Round2/issues
