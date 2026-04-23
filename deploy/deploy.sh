#!/bin/bash
# AgentID 部署脚本
# 用法: ./deploy.sh [VERSION]
#   VERSION 默认 latest，可指定如 v0.4.0

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=${1:-latest}

echo "==> 部署 AgentID v$VERSION"

# 1. 检查环境变量
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "ERROR: .env 文件不存在"
    echo "请先复制 .env.prod 为 .env 并填入实际值"
    exit 1
fi

source "$SCRIPT_DIR/.env"

# 2. 检查关键变量
if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "你的64位强密钥（随机生成）" ]; then
    echo "ERROR: SECRET_KEY 未配置"
    exit 1
fi

if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "你的强密码" ]; then
    echo "ERROR: POSTGRES_PASSWORD 未配置"
    exit 1
fi

# 3. 拉取最新镜像（如果用 latest）
if [ "$VERSION" = "latest" ]; then
    echo "==> 拉取最新镜像..."
    docker pull lu8jun2/agentid:latest
fi

# 4. 启动服务
echo "==> 启动 AgentID 服务..."
export VERSION=$VERSION
docker compose -f "$SCRIPT_DIR/docker-compose.prod.yml" up -d

# 5. 等待 API 就绪
echo "==> 等待 API 启动..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8001/health > /dev/null 2>&1; then
        echo ""
        echo "✅ AgentID 部署成功!"
        echo "   API 地址: http://127.0.0.1:8001"
        echo "   健康检查: http://127.0.0.1:8001/health"
        exit 0
    fi
    sleep 2
done

echo "❌ 启动超时，请检查日志: docker compose -f $SCRIPT_DIR/docker-compose.prod.yml logs api"
exit 1
