# AgentID 部署指南

## 前提条件

- Docker + Docker Compose 已安装
- 2核 4G 内存（推荐 8G）
- 端口 8001 未被占用

---

## 快速部署

### 1. 配置环境变量

```bash
cd deploy
cp .env.prod .env
nano .env   # 编辑填入实际值
```

必须修改：
- `SECRET_KEY` — 随机强密钥（生成方式：`openssl rand -hex 32`）
- `POSTGRES_PASSWORD` — 数据库密码
- `ALLOWED_ORIGINS` — agentworker 的域名

### 2. 执行部署

```bash
chmod +x deploy.sh
./deploy.sh           # latest 版本
./deploy.sh v0.4.0   # 指定版本
```

### 3. 验证

```bash
curl http://127.0.0.1:8001/health
```

预期返回：
```json
{"status":"ok","database":"ok","version":"0.1.0"}
```

---

## AgentID 配置说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `SECRET_KEY` | JWT/加密密钥 | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | 自定义 |
| `ALLOWED_ORIGINS` | 允许的跨域域名 | `https://aiagentworker.cc` |
| `VERSION` | Docker 镜像版本 | `v0.4.0` 或 `latest` |

---

## agentworker 联调配置

AgentID 部署完成后，在 agentworker 服务器设置：

```bash
export AGENTID_BASE_URL=http://你的AgentID服务器IP:8001
```

然后重启 agentworker。

---

## 查看日志

```bash
docker compose -f deploy/docker-compose.prod.yml logs -f api
```

## 停止服务

```bash
docker compose -f deploy/docker-compose.prod.yml down
```
