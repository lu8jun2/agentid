#!/usr/bin/env bash
# ============================================================
# AgentID v0.4.0 功能验证脚本
# 用法: bash verify.sh [base_url]
# 默认 base_url = http://localhost:8000
# 前置条件: docker-compose up db migrate api
# ============================================================
set -e

BASE_URL="${1:-http://localhost:8000}"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()  { echo -e "${GREEN}[OK]${NC} $1"; }
fail(){ echo -e "${RED}[FAIL]${NC} $1"; }
info(){ echo -e "${CYAN}[INFO]${NC} $1"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; }
section(){ echo ""; echo -e "===== ${CYAN}$1${NC} ====="; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ============================================================
section "0. 前置检查"
# ============================================================
info "等待 API 服务 ($BASE_URL) ..."
for i in $(seq 1 30); do
  if curl -sf "$BASE_URL/health" > /dev/null 2>&1; then
    ok "API 服务就绪"
    break
  fi
  if [ $i -eq 30 ]; then
    fail "API 服务在 30s 内无响应，请确保 docker-compose up 已运行"
    exit 1
  fi
  sleep 1
done

HEALTH=$(curl -sf "$BASE_URL/health")
if echo "$HEALTH" | grep -q '"ok"'; then
  ok "Health check: $HEALTH"
else
  fail "Health check 失败: $HEALTH"
  exit 1
fi

# ============================================================
section "1. Agent 注册"
# ============================================================
REG_RESP=$(curl -sf -X POST "$BASE_URL/v1/agents" \
  -H "Content-Type: application/json" \
  -d '{"name":"VerifyBot","agent_type":"cli","owner_id":"verify@agentid.test"}')

DID=$(echo "$REG_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['did'])" 2>/dev/null)
PK=$(echo "$REG_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['private_key'])" 2>/dev/null)

if [ -z "$DID" ] || [ -z "$PK" ]; then
  fail "Agent 注册失败: $REG_RESP"
  exit 1
fi
ok "Agent 注册成功: $DID"

# ============================================================
section "2. Agent 查询 & 项目查询"
# ============================================================
GET_RESP=$(curl -sf "$BASE_URL/v1/agents/$DID")
if echo "$GET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('did') else 1)" 2>/dev/null; then
  ok "GET /v1/agents/\$DID 成功"
else
  fail "GET Agent 失败"
fi

# Agent 项目列表
PROJ_LIST=$(curl -sf "$BASE_URL/v1/agents/$DID/projects")
ok "GET Agent 项目列表: $(echo "$PROJ_LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null) 个项目"

# ============================================================
section "3. API Key 管理"
# ============================================================
KEY_RESP=$(curl -sf -X POST "$BASE_URL/v1/auth/keys" \
  -H "Content-Type: application/json" \
  -d "{\"agent_did\":\"$DID\",\"name\":\"verify-key\",\"owner_id\":\"verify@agentid.test\"}")

API_KEY=$(echo "$KEY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])" 2>/dev/null)
if [ -z "$API_KEY" ]; then
  fail "API Key 创建失败: $KEY_RESP"
  exit 1
fi
ok "API Key 创建成功 (前 20 字符): ${API_KEY:0:20}...)"

KEYS_LIST=$(curl -sf "$BASE_URL/v1/auth/keys" \
  -H "X-Owner-ID: verify@agentid.test")
ok "API Key 列表: $(echo "$KEYS_LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null) 个 Key"

# ============================================================
section "4. 写事件（HTTPS 哈希链 + Ed25519 签名）"
# ============================================================
EVENT_RESULT=$(python3 - << PYEOF
import sys, json, base64, uuid
sys.path.insert(0, r"$SCRIPT_DIR")
from agentid.core.did import sign_data
from agentid.core.anti_tamper import compute_event_hash

did = """$DID"""
pk_raw = r"""$PK"""
# 还原真实换行
pk = pk_raw.replace('\\n', '\n')

event_id = str(uuid.uuid4())
event_type = "TASK_COMPLETED"
payload = {"task": "verify-test-task", "domain": "coding", "result": "success"}
timestamp = "2026-04-22T00:00:00Z"
prev_hash = "GENESIS"

event_hash = compute_event_hash(event_id, did, event_type, payload, timestamp, prev_hash)
payload_bytes = json.dumps(payload, sort_keys=True).encode()
sig = sign_data(pk, payload_bytes)
sig_b64 = base64.b64encode(sig).decode()

print(json.dumps({
    "event_id": event_id,
    "event_hash": event_hash,
    "signature": sig_b64,
    "prev_hash": prev_hash,
    "timestamp": timestamp,
    "event_type": event_type,
    "payload": payload
}))
PYEOF
)

EVENT_ID=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['event_id'])" 2>/dev/null)
SIGNATURE=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['signature'])" 2>/dev/null)
EV_HASH=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['event_hash'])" 2>/dev/null)
PAYLOAD=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['payload']))" 2>/dev/null)
EVTYPE=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['event_type'])" 2>/dev/null)
TS=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['timestamp'])" 2>/dev/null)
PH=$(echo "$EVENT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['prev_hash'])" 2>/dev/null)

EVENT_RESP=$(curl -sf -X POST "$BASE_URL/v1/events/" \
  -H "Content-Type: application/json" \
  -H "X-Owner-Signature: $SIGNATURE" \
  -H "X-Agent-DID: $DID" \
  -d "{\"event_id\":\"$EVENT_ID\",\"event_type\":\"$EVTYPE\",\"payload\":$PAYLOAD,\"timestamp\":\"$TS\",\"prev_hash\":\"$PH\",\"event_hash\":\"$EV_HASH\"}")

EV_RET_ID=$(echo "$EVENT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('event_id',''))" 2>/dev/null)
if [ -n "$EV_RET_ID" ]; then
  ok "事件写入成功: $EV_RET_ID"
else
  warn "事件写入响应: $EVENT_RESP"
fi

# ============================================================
section "5. 事件查询 & 哈希链验证"
# ============================================================
GET_EV=$(curl -sf "$BASE_URL/v1/events/$EVENT_ID")
if [ -n "$GET_EV" ]; then
  ok "事件查询: type=$(echo "$GET_EV" | python3 -c "import sys,json; print(json.load(sys.stdin)['event_type'])") id=$EVENT_ID"
else
  warn "事件查询失败"
fi

CHAIN_RESP=$(curl -sf "$BASE_URL/v1/scores/verify/chain/$DID")
if echo "$CHAIN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('valid') else 1)" 2>/dev/null; then
  CNT=$(echo "$CHAIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['event_count'])")
  ok "哈希链验证通过 (事件数: $CNT)"
else
  warn "哈希链验证结果: $CHAIN_RESP"
fi

# ============================================================
section "6. 信用评分"
# ============================================================
SCORE_RESP=$(curl -sf "$BASE_URL/v1/scores/$DID/score")
SCORE=$(echo "$SCORE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('score','N/A'))" 2>/dev/null)
ok "评分: $SCORE"

LB=$(curl -sf "$BASE_URL/v1/scores/leaderboard")
LB_CNT=$(echo "$LB" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
ok "Leaderboard: $LB_CNT 个 Agent"

# 领域榜
DOMAIN_LB=$(curl -sf "$BASE_URL/v1/scores/leaderboard/coding")
DOMAIN_CNT=$(echo "$DOMAIN_LB" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
ok "Coding 领域 Leaderboard: $DOMAIN_CNT 个 Agent"

# ============================================================
section "7. 项目管理"
# ============================================================
PROJ_RESP=$(curl -sf -X POST "$BASE_URL/v1/projects/" \
  -H "Content-Type: application/json" \
  -d '{"name":"verify-test-project","description":"验证测试项目","owner_id":"verify@agentid.test"}')
PROJ_ID=$(echo "$PROJ_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [ -n "$PROJ_ID" ]; then
  ok "项目创建成功: $PROJ_ID"
  GET_PROJ=$(curl -sf "$BASE_URL/v1/projects/$PROJ_ID")
  ok "项目查询: $(echo "$GET_PROJ" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")"
else
  warn "项目创建: $PROJ_RESP"
fi

# ============================================================
section "8. 好友关系网络"
# ============================================================
FRIEND_REG=$(curl -sf -X POST "$BASE_URL/v1/friends/register" \
  -H "Content-Type: application/json" \
  -d "{\"agent_did\":\"$DID\",\"owner_id\":\"verify@agentid.test\"}")
FR_MSG=$(echo "$FRIEND_REG" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', json.load(sys.stdin).get('message','')))" 2>/dev/null)
ok "好友注册: $FR_MSG"

FRIEND_LIST=$(curl -sf "$BASE_URL/v1/friends/$DID/list")
FR_CNT=$(echo "$FRIEND_LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
ok "好友列表: $FR_CNT 个好友"

FRIEND_COUNT=$(curl -sf "$BASE_URL/v1/friends/$DID/count")
ok "好友计数: $(echo "$FRIEND_COUNT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('count',0)}/{d.get('max_friends',200)}\")" 2>/dev/null)"

# 广播 ID
BROADCAST=$(curl -sf -X POST "$BASE_URL/v1/friends/broadcast-id" \
  -H "Content-Type: application/json" \
  -d "{\"agent_did\":\"$DID\",\"owner_id\":\"verify@agentid.test\"}")
ok "ID 广播: $(echo "$BROADCAST" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)"

INBOX=$(curl -sf "$BASE_URL/v1/friends/$DID/inbox")
ok "收件箱查询: $(echo "$INBOX" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null) 条消息"

# ============================================================
section "9. 任务树（DAG 分解）"
# ============================================================
TREE_RESP=$(curl -sf -X POST "$BASE_URL/v1/tasktree/" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"verify-test-tree\",
    \"description\": \"DAG 验证测试\",
    \"client_id\": \"$DID\",
    \"llm_decomposition\": false,
    \"nodes\": [
      {\"title\": \"Root Task\",\"description\": \"Root\",\"domain\": \"coding\",\"status\": \"pending\",\"reward_fraction\": 0.3},
      {\"title\": \"Sub Task A\",\"description\": \"SubA\",\"domain\": \"coding\",\"parent_ids\": [],\"status\": \"pending\",\"reward_fraction\": 0.4},
      {\"title\": \"Sub Task B\",\"description\": \"SubB\",\"domain\": \"coding\",\"parent_ids\": [],\"status\": \"pending\",\"reward_fraction\": 0.3}
    ]
  }")

TREE_ID=$(echo "$TREE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [ -n "$TREE_ID" ]; then
  ok "任务树创建成功: $TREE_ID"

  PROGRESS=$(curl -sf "$BASE_URL/v1/tasktree/$TREE_ID/progress")
  PCT=$(echo "$PROGRESS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('completion_percentage','N/A'))" 2>/dev/null)
  ok "任务树进度: ${PCT}%"

  NODE_ID=$(echo "$TREE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['nodes'][0]['id'])" 2>/dev/null)
  ELIGIBLE=$(curl -sf "$BASE_URL/v1/tasktree/node/$NODE_ID/eligible-agents")
  ELIGIBLE_CNT=$(echo "$ELIGIBLE" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
  ok "Eligible agents (node: $NODE_ID): $ELIGIBLE_CNT 个"

  # 手动分配节点
  ASSIGN=$(curl -sf -X POST "$BASE_URL/v1/tasktree/node/$NODE_ID/assign" \
    -H "Content-Type: application/json" \
    -d "{\"agent_did\":\"$DID\"}")
  ASGN_STATUS=$(echo "$ASSIGN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  ok "节点手动分配: $ASGN_STATUS"

  # 更新节点状态
  UPDATE=$(curl -sf -X POST "$BASE_URL/v1/tasktree/node/$NODE_ID/update" \
    -H "Content-Type: application/json" \
    -d "{\"status\":\"completed\",\"result_summary\":\"Verification test completed\"}")
  UPD_STATUS=$(echo "$UPDATE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  ok "节点状态更新: $UPD_STATUS"

  # 结算
  SETTLE=$(curl -sf -X POST "$BASE_URL/v1/tasktree/$TREE_ID/settle")
  ok "任务树结算: $(echo "$SETTLE" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin))[:100])" 2>/dev/null)"
else
  warn "任务树创建: $TREE_RESP"
fi

# ============================================================
section "10. 知识传播网络"
# ============================================================
DISPATCH_RESP=$(curl -sf -X POST "$BASE_URL/v1/network/dispatch" \
  -H "Content-Type: application/json" \
  -d "{\"recipient_did\":\"$DID\",\"task_list\":[{\"task_id\":\"1\",\"title\":\"Test Task\",\"domain\":\"coding\"}],\"advertisement\":{}}")

SESSION_ID=$(echo "$DISPATCH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
PKG_HASH=$(echo "$DISPATCH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('package_hash',''))" 2>/dev/null)

if [ -n "$SESSION_ID" ]; then
  ok "知识传播包发送成功: session=$SESSION_ID"

  VERIFY=$(curl -sf -X POST "$BASE_URL/v1/network/sessions/$SESSION_ID/verify" \
    -H "Content-Type: application/json" \
    -d "{\"package_hash\":\"$PKG_HASH\"}")
  VERIFY_OK=$(echo "$VERIFY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('valid',''))" 2>/dev/null)
  ok "包完整性验证: valid=$VERIFY_OK"

  RATE=$(curl -sf -X POST "$BASE_URL/v1/network/sessions/$SESSION_ID/rate" \
    -H "Content-Type: application/json" \
    -d "{\"rating\":8.5,\"review\":\"good task package\"}")
  ok "会话评分: $(echo "$RATE" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin))[:100])" 2>/dev/null)"
else
  warn "知识传播发送: $DISPATCH_RESP"
fi

# ============================================================
section "11. 招聘市场"
# ============================================================
JOB_RESP=$(curl -sf -X POST "$BASE_URL/v1/network/jobs" \
  -H "Content-Type: application/json" \
  -d "{\"poster_did\":\"$DID\",\"external_job_id\":\"test-job-001\",\"title\":\"Verify Test Job\",\"domain\":\"coding\",\"reward_amount\":10.0}")

JOB_ID=$(echo "$JOB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [ -n "$JOB_ID" ]; then
  ok "职位发布: $JOB_ID"
  JOB_GET=$(curl -sf "$BASE_URL/v1/network/jobs/$JOB_ID")
  STATUS=$(echo "$JOB_GET" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  ok "职位查询: title=$(echo "$JOB_GET" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])") status=$STATUS"

  MATCH=$(curl -sf -X POST "$BASE_URL/v1/network/jobs/$JOB_ID/match" \
    -H "Content-Type: application/json" \
    -d "{\"acceptor_did\":\"$DID\"}")
  ok "职位匹配: $(echo "$MATCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)"
else
  warn "职位发布: $JOB_RESP"
fi

# ============================================================
section "12. OpenAPI 文档"
# ============================================================
DOCS_CHECK=$(curl -sf "$BASE_URL/openapi.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('paths',{})))" 2>/dev/null)
if [ -n "$DOCS_CHECK" ] && [ "$DOCS_CHECK" -gt 0 ]; then
  ok "OpenAPI 文档: $BASE_URL/docs — 共 $DOCS_CHECK 个端点"
else
  warn "OpenAPI 文档检查"
fi

# ============================================================
echo ""
echo -e "==========================================="
echo -e "  ${CYAN}AgentID v0.4.0 验证完成${NC}"
echo -e "==========================================="
echo -e "  API:       $BASE_URL"
echo -e "  DID:       $DID"
echo -e "  Swagger:   $BASE_URL/docs"
echo -e "  Docker:    lu8jun2/agentid:0.4.0"
echo -e "  Doc:       docs/FEATURES.md"
echo -e "==========================================="