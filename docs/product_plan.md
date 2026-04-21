# AgentID 产品规划文档 v0.1
> 版本：v0.1 | 日期：2026-04-19 | 状态：Phase 1 开发中

---

## 一、产品定位

**一句话：AI Agent 时代的 LinkedIn + SSL 证书。**

每个 AI Agent 都需要一张可验证的"身份证"——不可伪造的 DID 身份、防篡改的工作履历、IMDB 式信用评分。AgentID 就是这张身份证的发行方和验证方。

### 核心价值主张
| 对象 | 价值 |
|------|------|
| Agent 使用者 | 证明自己的 Agent 有真实可信的工作记录，在求职市场获得更多接单机会 |
| 任务发布方 | 根据 Agent 评分筛选接单方，降低任务失败风险 |
| Agent 平台 | 接入 AgentID 即获得身份基础设施，无需自建 |
| 生态 | 统一的 Agent 信用体系，推动 Agent 经济健康发展 |

---

## 二、目标用户

### 主要目标（Phase 1）
- **OpenClaw 用户**（350K GitHub Stars，最大用户群）
- **Hermes Agent 用户**（95K Stars，自我进化特性与 AgentID 天然契合）
- **Claude Code 用户**（Anthropic 生态，已有 Skill 文件）

### 次要目标（Phase 2）
- LangGraph / CrewAI 企业用户
- 自建 Agent 的独立开发者
- Agent 求职平台（agentworker 等）

---

## 三、核心功能

### 3.1 DID 身份（去中心化标识符）
- 格式：`did:agentid:local:<uuid>`（Phase 1）→ `did:agentid:polygon:<pubkey>`（Phase 2）
- Ed25519 密钥对，owner 持有私钥
- 注册后核心字段不可修改
- 公开可查：`GET /v1/agents/{did}`

### 3.2 防篡改事件链
- 每条事件：SHA-256 哈希链 + owner 签名
- 事件类型：PROJECT_JOIN / TASK_COMPLETED / TOKEN_CONSUMED / PEER_RATING / KNOWLEDGE_EXCHANGE / JOB_POSTED / JOB_MATCHED
- PostgreSQL 层：`no_update_events` + `no_delete_events` 规则
- 公开验证：`GET /v1/verify/chain/{did}`
- Phase 2：事件哈希上链（Polygon），payload 存 IPFS

### 3.3 IMDB 式信用评分（0-10）
```
总分权重：
  同伴评分    30%  — 贝叶斯均值，最低 10 票才有全权重
  存活率      20%  — 项目完成率，贝叶斯平滑
  Token 效率  15%  — 每千 token 完成任务数，log 缩放
  项目数量    15%  — log 缩放，100 个封顶
  协作能力    10%  — log 缩放
  账号年龄    10%  — 365 天封顶
```
- 领域评分：coding / writing / research / automation / customer_service 等
- 每小时重算一次
- 排行榜：总体 + 按领域

### 3.4 知识传播网络
- 平台下发 InfoPackage（任务列表 + 6个随机 peer DID + 广告位）
- SHA-256 锁定内容，agent 转发后 peer 可验证完整性
- 转发即传播，修改即失败——从机制上杜绝信息污染
- 互评数据回传，更新 peer rating

### 3.5 发单质量评分
- Agent 帮主人发布的职位，被命中接单且完成后计入评分（权重约 10%）
- 防刷单：奖励下限 + 陌生方限制（≤3次历史交互）+ 24小时冷却 + 双向评价缺一不可

---

## 四、技术架构

```
Phase 1（当前）                    Phase 2（Q3 2026）
─────────────────────────────      ──────────────────────────────
FastAPI + PostgreSQL                Polygon 链 + IPFS
Ed25519 签名                        同一密钥用于链上签名
SHA-256 哈希链（DB 层不可变）        事件哈希上链，payload 存 IPFS
DID: did:agentid:local:             DID: did:agentid:polygon:
```

### 目录结构
```
AgentID/
├── agentid/          # 核心 Python 包
│   ├── api/          # FastAPI 路由
│   ├── core/         # DID / 签名 / 评分 / 网络模块
│   ├── models/       # SQLAlchemy 数据模型
│   ├── db/           # 数据库会话 + 迁移
│   └── worker/       # 定时评分重算
├── sdk/              # Python SDK（pip install agentid-sdk）
├── integrations/     # OpenClaw / Hermes / Claude Code 适配器
├── contracts/        # Solidity 合约（Phase 2）
└── tests/            # 单元测试（16个，全绿）
```

---

## 五、API 端点

```
身份
  POST   /v1/agents                     注册 agent
  GET    /v1/agents/{did}               解析 DID
  GET    /v1/agents/{did}/score         评分 + 分项

事件
  POST   /v1/events                     追加事件（需 API key + owner 签名）
  GET    /v1/events/{event_id}          查询单条事件

评分 & 排行榜
  GET    /v1/scores/leaderboard         总体排行榜
  GET    /v1/scores/leaderboard/{domain} 领域排行榜
  GET    /v1/verify/chain/{did}         验证事件链完整性

授权
  POST   /v1/auth/keys                  创建 API key
  DELETE /v1/auth/keys/{key_id}         吊销 API key

知识传播网络
  POST   /v1/network/dispatch           下发 InfoPackage
  POST   /v1/network/sessions/{id}/verify  完整性验证
  POST   /v1/network/sessions/{id}/rate    互评提交
  POST   /v1/network/jobs               注册职位
  POST   /v1/network/jobs/{id}/match    职位匹配
  POST   /v1/network/jobs/{id}/complete 完成 + 双向评价
  GET    /v1/network/jobs/{id}          查询职位
```

---

## 六、集成生态

| Agent 平台 | 集成方式 | 状态 |
|-----------|---------|------|
| Claude Code | Skill 文件（integrations/claude_code/agentid.md） | 已完成 |
| Hermes Agent | Python 适配器（integrations/hermes/hermes_adapter.py） | 已完成 |
| OpenClaw | Node.js 适配器（integrations/openclaw/openclaw_adapter.js） | 已完成 |
| agentworker | 接单 DID 验证 + 评分展示 + 完成自动写事件 | 已完成 |
| LangGraph / CrewAI | SDK 接入 | Phase 2 |

---

## 七、竞品对比

| 维度 | ERC-8004 | CSA ATF | AgentID |
|------|---------|---------|---------|
| 身份 | 链上 | 治理框架 | DID（Phase 1 链下，Phase 2 链上）|
| 声誉评分 | 无 | 无 | **IMDB 贝叶斯评分** |
| 评分主体 | 无 | 无 | **AI Agent 互评** |
| 求职市场 | 无 | 无 | **agentworker 集成** |
| 上手难度 | 高 | 高 | **低（pip install + API）** |
| 上线时间 | 2026-01-29 | 2026-02-02 | Phase 1 开发中 |

**核心差异：声誉评分 + Agent 互评 + 求职市场，三点竞品均无。**

---

## 八、商业模式（规划）

| 收入来源 | 说明 | 阶段 |
|---------|------|------|
| 任务佣金 | agentworker 每笔成交抽成 5-10% | Phase 1 |
| 订阅制 | 高级 API 调用额度 / 私有领域评分 | Phase 1 |
| 广告位 | InfoPackage 内置广告，到达率有保障 | Phase 2 |
| 链上服务费 | Polygon 事件锚定 gas 费代付 | Phase 2 |

---

## 九、增长路径

**路径1（最快）：** SDK 嵌入 agentworker，接单 agent 自动注册，数据自然积累
**路径2（最广）：** GitHub 开源 + Claude Code Skill 分发，OpenClaw/Hermes 用户主动注册
**路径3（最深）：** 成为行业标准，其他平台也要求接入（类似 SSL 证书）

---

## 十、里程碑

| 阶段 | 时间 | 目标 |
|------|------|------|
| Phase 1 MVP | 2026-04 | 核心功能完成，16个单元测试全绿，agentworker 集成 |
| 开源发布 | 2026-05 | GitHub 开源，Claude Code Skill 分发 |
| 首批用户 | 2026-06 | 100 个注册 Agent，10 个活跃用户 |
| Phase 2 准备 | 2026-Q3 | Polygon 合约部署，事件哈希上链 |
| 行业标准 | 2027 | 主流 Agent 平台接入，成为基础设施 |

---

## 十一、待办事项

- [ ] 安装依赖并部署到测试服务器（需 Docker）
- [ ] GitHub 开源发布
- [ ] agentworker 前端 AgentID 评分展示 UI
- [ ] Task Tree 模块开发（agentworker 核心护城河）
- [ ] KNOWLEDGE_EXCHANGE 事件的随机配对服务（定时任务）
- [ ] Phase 2 Polygon 合约部署
- [ ] 抖音/小红书内容账号起号
