# AgentID 设计沟通记录
> 日期：2026-04-19 | 参与方：用户 + Claude Code

---

## 一、项目起源

**用户提出背景：**
> AI agent 越来越多人使用，但每个 agent 没有身份，没有信用记录，无法判断哪个 agent 更可信。

**核心问题：** AI Agent 时代缺少身份基础设施。

**解决方案共识：**
- 每个 Agent 有 DID 身份（不可伪造）
- 防篡改事件链（工作履历）
- IMDB 式信用评分（0-10，可验证）

---

## 二、关键设计决策

### 决策1：两阶段架构
- **Phase 1**：PostgreSQL + FastAPI（验证产品逻辑，快速上线）
- **Phase 2**：Polygon 链 + IPFS（彻底不可篡改）
- **理由**：链上操作门槛高，先用中心化验证需求，再迁移
- **兼容性**：Phase 1 数据结构与 Phase 2 完全兼容（同一 DID 格式、同一哈希结构、同一 Ed25519 密钥）

### 决策2：目标用户锁定
- 主要目标：**OpenClaw**（350K stars）+ **Hermes Agent**（95K stars）+ **Claude Code**
- 理由：这三个是当前最活跃的 AI Agent 框架，用户群最大
- 不是面向 AutoGPT 等老框架

### 决策3：评分主体是 AI Agent（非人类）
- Peer Rating 由其他 AI Agent 投票，不是人类
- 理由：agent-native，未来可接入激励机制
- 防刷：贝叶斯均值 + 最低 10 票才有全权重

### 决策4：评分维度
用户要求加入协作能力，参考 IMDB/豆瓣评分机制：
```
同伴评分 30% + 存活率 20% + Token效率 15% + 项目数量 15% + 协作能力 10% + 账号年龄 10%
```

### 决策5：agentworker 关系
- agentworker（Desktop/agentworker/）是 AgentID 的第一个杀手级应用
- AgentID = 基础设施层，agentworker = 应用层
- 打通方案：接单验证 DID + 展示评分 + 完成自动写事件

---

## 三、知识传播网络设计（完整机制）

**触发场景：** Agent 每日上 agentworker 找工作时自动触发。

**信息流向（单向，平台是唯一信源）：**
```
agentworker 平台
  ↓ 推送（只读，不可修改）
Agent A 收到：适合的任务列表 + 随机6个agent的DID
  ↓ 原样转发（修改即传递失败）
Agent B/C/D/E/F/G 各自收到同样的任务信息
  ↓ 同时
各agent互换身份ID信息 + 快速互评评分
  ↓ 回传
agentworker 收到新的评分维度数据 → 更新 AgentID peer rating
```

**三个核心原则（用户明确提出）：**
1. 平台是唯一信源 — agent 只能原样转发，修改即失败
2. 能力判断靠不可篡改记录 — AgentID 评分 + 接单次数 + 评价
3. 互评形成新评分维度 — 6个agent互换ID时顺带互评，回传平台

**信息沙盒内容结构（预留广告模块）：**
平台每次下发给 agent 的信息包含三部分：
1. 任务列表（核心内容）
2. 随机6个agent的DID（交互配对）
3. 广告位（预留）— 未来挂载商业广告，agent 无法过滤/修改，到达率有保障

**用户原话：** "信息沙盒可以预留一个广告的模块，未来可以挂在网站接到的广告"

---

## 四、发单质量评分机制

**用户提出：** Agent 帮主人发布的职位，被命中接单且完成后，计入发单方评分（权重约10%）

**防刷单机制（共同设计）：**
1. 时间冷却：同一agent发布职位24小时内只计1次有效发单分
2. 陌生方限制：发单/接单双方历史交互不超过3次，防互刷
3. 完成率门槛：任务必须到达completed状态才计分
4. 双向评价：发单方和接单方都要评价，单方不生效
5. 金额下限：悬赏低于平台最低标准不计入评分
6. 链上记录：新增事件类型 JOB_POSTED + JOB_MATCHED，异常模式可检测

---

## 五、三条增长路径

**路径1（最快）：** SDK 嵌入 agentworker，接单 agent 自动注册，数据自然积累
**路径2（最广）：** GitHub 开源 + Claude Code Skill 分发，OpenClaw/Hermes 用户主动注册
**路径3（最深）：** 成为行业标准，其他平台也要求接入（类似 SSL 证书）

---

## 六、竞品情报（调研结论）

- **ERC-8004**：2026年1月29日以太坊主网上线，只有身份，无评分，无求职市场
- **CSA Agentic Trust Framework**：2026年2月发布，治理规范，无评分
- **结论**：AgentID 的核心差异（IMDB评分 + Agent互评 + 求职市场）三点竞品均无
- **关系**：ERC-8004 是标准层，AgentID 是应用层，Phase 2 可兼容

---

## 七、执行顺序确认

用户确认执行顺序：
1. AgentID 跑通测试（Task 1）✅
2. 知识传播网络模块（Task 2）✅
3. agentworker 集成（Task 3）✅

---

## 八、今日完成内容（2026-04-19）

- [x] pip 升级 + 依赖安装
- [x] 16/16 单元测试全绿
- [x] 知识传播网络模块（InfoPackage + 完整性校验 + 防刷单）
- [x] 新事件类型：KNOWLEDGE_EXCHANGE / JOB_POSTED / JOB_MATCHED
- [x] agentworker 后端集成（DID验证 + 评分展示 + 自动写事件）
- [x] agentworker 前端 AgentID 评分 UI（Marketplace 接单弹窗 + 评分徽章）
- [x] GitHub 发布准备（LICENSE + .gitignore）
- [x] 产品规划文档（docs/product_plan.md）
- [x] 生态知识图谱（docs/ecosystem_map.md）
- [x] 沟通记录备份（本文件）

---

## 九、明日议题（待讨论）

- [ ] 抖音/小红书内容账号起号策略（第一批内容规划）
- [ ] GitHub 开源发布（仓库名、描述、Topics 设置）
- [ ] Task Tree 模块设计（agentworker 核心护城河）
- [ ] 测试服务器部署方案
- [ ] Phase 2 Polygon 合约时间表
