# LingShu 平台部署指南

## 环境要求

- Docker 24+ & Docker Compose v2
- 最低配置：4 核 CPU / 8GB 内存 / 20GB 磁盘
- 端口：3100、8100、5440、7480、7690、6390（确保未被占用）

## 一键部署（开发环境）

```bash
# 1. 克隆代码
git clone ssh://git@115.191.48.223:2222/yangfan/Lingshu-Round2.git
cd Lingshu-Round2

# 2. 启动所有服务（首次启动约 3-5 分钟）
docker compose up -d

# 3. 查看启动状态
docker compose ps

# 4. 等待所有服务 healthy 后，访问前端
open http://localhost:3100
```

## 生产环境部署

### 1. 准备环境变量

```bash
git clone ssh://git@115.191.48.223:2222/yangfan/Lingshu-Round2.git
cd Lingshu-Round2

# 复制环境变量模板
cp .env.example .env

# 编辑 .env，替换所有 CHANGE_ME 占位符为真实值
# 必须修改的关键变量：
#   POSTGRES_PASSWORD    — PostgreSQL 密码
#   NEO4J_PASSWORD       — Neo4j 密码
#   REDIS_PASSWORD       — Redis 密码
#   LINGSHU_JWT_SECRET   — JWT 签名密钥（用 openssl rand -hex 32 生成）
#   LINGSHU_SEED_ADMIN_PASSWORD — 初始管理员密码
#   LINGSHU_CORS_ORIGINS — 前端公网 URL
#   NEXT_PUBLIC_API_URL  — 后端公网 URL
vi .env
```

### 2. 启动生产服务

```bash
# 构建并启动（使用生产配置）
docker compose -f docker-compose.prod.yml up -d --build

# 查看状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f backend
```

### 3. 验证部署

```bash
# 检查所有服务健康
docker compose -f docker-compose.prod.yml ps

# 检查 API 健康
curl http://localhost:8100/health

# 测试登录（使用 .env 中配置的管理员账号）
curl -X POST http://localhost:8100/setting/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@your-domain.example.com","password":"your-password"}'
```

### 生产配置特性

`docker-compose.prod.yml` 包含以下生产级增强：

| 特性 | 说明 |
|------|------|
| 重启策略 | 所有服务 `restart: unless-stopped` |
| 健康检查 | 所有服务配置 healthcheck（含 start_period） |
| 资源限制 | CPU/内存上限和预留（防止单服务耗尽主机资源） |
| 网络隔离 | 数据库仅在 `lingshu-backend` 内网可访问，不暴露端口到宿主机 |
| 日志轮转 | `json-file` driver + max-size/max-file 限制（防止磁盘撑满） |
| 数据持久化 | 独立命名卷（`r2_prod_*`）持久化数据库文件 |
| 密码保护 | Redis 启用 requirepass，PostgreSQL/Neo4j 密码从 .env 注入 |
| 性能调优 | PostgreSQL 调整 shared_buffers/max_connections，Neo4j 配置堆内存和 pagecache |

### 资源限制参考

| 服务 | CPU 上限 | 内存上限 | 内存预留 |
|------|---------|---------|---------|
| backend | 2.0 | 1 GB | 512 MB |
| frontend | 1.0 | 512 MB | 256 MB |
| postgres | 2.0 | 2 GB | 512 MB |
| neo4j | 2.0 | 2 GB | 1 GB |
| redis | 1.0 | 512 MB | 128 MB |

> 资源限制可在 `docker-compose.prod.yml` 的 `deploy.resources` 中按实际硬件调整。

## 服务端口

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3100 | Next.js 15 Web UI |
| 后端 API | http://localhost:8100 | FastAPI |
| PostgreSQL | localhost:5440 | 关系数据库（仅开发环境暴露） |
| Neo4j Browser | http://localhost:7480 | 图数据库管理界面（仅开发环境暴露） |
| Neo4j Bolt | localhost:7690 | 图数据库连接（仅开发环境暴露） |
| Redis | localhost:6390 | 缓存/锁（仅开发环境暴露） |

> 生产环境中，数据库端口不对外暴露。仅 frontend (3100) 和 backend (8100) 端口映射到宿主机。

## 默认账号

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 管理员 | admin@lingshu.dev | admin123 |

> 首次启动时系统自动创建管理员账号和默认租户。生产环境请在 .env 中配置强密码，并在首次登录后立即修改。

## 验证部署

```bash
# 1. 检查 API 健康
curl http://localhost:8100/health
# 期望返回: {"status":"ok"}

# 2. 测试登录
curl -X POST http://localhost:8100/setting/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@lingshu.dev","password":"admin123"}'
# 期望返回包含 "data": {"user": {...}}

# 3. 打开浏览器访问
open http://localhost:3100
# 用上面的账号密码登录
```

## 功能模块导航

登录后，通过底部 Dock 栏切换 5 大模块：

| 模块 | 路径 | 功能 |
|------|------|------|
| **Ontology（本体）** | /ontology | 实体类型/关系类型/接口/动作/属性定义，版本管理 |
| **Data（数据）** | /data | 数据源连接管理，数据浏览 |
| **Function（能力）** | /function | 全局函数、工作流、能力目录 |
| **Agent（智能体）** | /agent | AI 模型注册、技能、MCP 连接、子代理、会话管理 |
| **Setting（设置）** | /setting | 用户/租户管理、审计日志、系统概览 |

## 常用运维命令

```bash
# 查看日志
docker compose logs -f backend    # 后端日志
docker compose logs -f frontend   # 前端日志

# 重启单个服务
docker compose restart backend

# 重建并更新（代码更新后）
docker compose build backend frontend
docker compose up -d backend frontend

# 停止所有服务
docker compose down

# 完全清除（含数据库数据）
docker compose down -v
```

生产环境运维命令需加 `-f docker-compose.prod.yml`：

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml build backend frontend
docker compose -f docker-compose.prod.yml up -d backend frontend
docker compose -f docker-compose.prod.yml down
```

## 安全加固

### 密钥管理

- 所有密码和密钥通过 `.env` 文件注入，`.env` 已在 `.gitignore` 中排除
- JWT 密钥必须使用强随机值：`openssl rand -hex 32`
- 数据库密码至少 16 字符，包含大小写字母、数字、特殊字符
- 首次部署后立即修改 seed 管理员密码

### 网络安全

- 生产配置（`docker-compose.prod.yml`）中数据库不对外暴露端口
- 数据库服务位于 `lingshu-backend` 内部网络，仅后端可访问
- 在后端服务前部署反向代理（Nginx/Caddy），启用 HTTPS
- 配置防火墙仅开放 80/443 端口（或自定义的前后端端口）

### 反向代理示例（Nginx）

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.example.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端 API
    location /ontology/ { proxy_pass http://127.0.0.1:8100; }
    location /data/     { proxy_pass http://127.0.0.1:8100; }
    location /function/ { proxy_pass http://127.0.0.1:8100; }
    location /copilot/  { proxy_pass http://127.0.0.1:8100; }
    location /setting/  { proxy_pass http://127.0.0.1:8100; }
    location /health    { proxy_pass http://127.0.0.1:8100; }
}
```

### 运行时安全

- 后端容器以非 root 用户（`lingshu`）运行
- 前端容器以非 root 用户（`nextjs`）运行
- Redis 启用密码认证（`requirepass`）
- 启用 RBAC 后（`LINGSHU_RBAC_ENABLED=true`），所有 API 请求受 Casbin 策略约束
- 定期审查 `/setting` 模块中的审计日志

### 数据备份

```bash
# PostgreSQL 备份
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U lingshu lingshu > backup_$(date +%Y%m%d).sql

# Neo4j 备份（需要停止服务）
docker compose -f docker-compose.prod.yml stop neo4j
docker run --rm \
  -v r2_prod_neo4j_data:/data \
  -v $(pwd)/backups:/backups \
  neo4j:5-community neo4j-admin database dump neo4j --to-path=/backups
docker compose -f docker-compose.prod.yml start neo4j

# Redis 备份（RDB 快照）
docker compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD BGSAVE
docker cp $(docker compose -f docker-compose.prod.yml ps -q redis):/data/dump.rdb ./backup_redis_$(date +%Y%m%d).rdb
```

## 故障排查

### 前端打不开（3100 端口无响应）

```bash
# 检查前端容器状态
docker compose logs frontend | tail -20
# 确认后端 healthcheck 通过（前端依赖后端）
docker compose ps backend
```

### 登录失败

```bash
# 检查后端日志
docker compose logs backend | grep -i error | tail -10
# 确认数据库迁移完成
docker compose exec backend alembic current
```

### 页面数据为空

```bash
# 确认 Neo4j 正常
docker compose exec neo4j cypher-shell -u neo4j -p lingshu123 "MATCH (n) RETURN count(n)"
# 确认 Redis 正常
docker compose exec redis redis-cli ping
```

## 数据库连接信息（调试用）

| 数据库 | 连接方式 |
|--------|---------|
| PostgreSQL | `psql -h localhost -p 5440 -U lingshu -d lingshu`（密码: lingshu123） |
| Neo4j | 浏览器访问 http://localhost:7480，用户: neo4j，密码: lingshu123 |
| Redis | `redis-cli -h localhost -p 6390` |

> 以上为开发环境默认值。生产环境密码在 `.env` 文件中配置，且数据库端口不对外暴露。
