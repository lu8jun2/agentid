# AI Agent 生态知识图谱
> 更新时间：2026-04-19 | 用于 AgentID 产品定位与竞品分析

---

## 一、生态全景图

```
                        AI Agent 生态
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
      框架层               平台层              基础设施层
   (Framework)           (Platform)         (Infrastructure)
          │                   │                   │
   ┌──────┴──────┐      ┌─────┴─────┐      ┌─────┴──────┐
   │             │      │           │      │            │
 编排框架      自主框架  代码Agent  通用Agent  身份/信任   支付/经济
LangGraph    OpenClaw  Claude Code  Manus   ERC-8004   AP2协议
CrewAI       Hermes    Cursor      Devin   AgentID    Stripe
MS Agent     AutoGPT   OpenHands           CSA ATF    链上结算
```

---

## 二、主要玩家详情

### 🦞 OpenClaw（最高热度）
| 项目 | 详情 |
|------|------|
| 定位 | 开源自主 Agent 框架，AI 软件工厂 |
| 架构 | Node.js，连接 WhatsApp/Discord/Telegram/Slack |
| 用户 | 自由职业者、小团队、企业 |
| 热度 | **350,000 GitHub Stars**（2026年3月最快增长） |
| 上线 | 2025年11月，2026年1月爆发（与 Anthropic 商标纠纷后两次改名） |
| 商业 | 开源 + ClawHub 技能市场 + DenchClaw Cloud（规划中） |
| 关键 | 技能市场、多 Agent 协作、生产级安全部署 |

### 🔮 Hermes Agent（增速最快）
| 项目 | 详情 |
|------|------|
| 定位 | 自我进化 Agent，持久记忆 + 涌现技能 |
| 开发 | Nous Research（MIT 协议，2026年2月） |
| 架构 | 持久运行时，从经验中创建可复用技能并存储 |
| 热度 | **95,600 GitHub Stars**（上线7周，2026年增速最快） |
| 关键 | 自学习循环：agent 总结新技能 → 存储 → 下次加载 |

### 📊 LangGraph（生产标准）
| 项目 | 详情 |
|------|------|
| 定位 | 图结构有状态 Agent 工作流框架 |
| 开发 | LangChain Inc. |
| 热度 | **126,000 GitHub Stars** |
| 状态 | 2025年10月 GA 1.0 |
| 关键 | 企业级标准，显式状态管理，断点续跑，人工介入 |

### 🤝 CrewAI（角色协作）
| 项目 | 详情 |
|------|------|
| 定位 | 基于角色的多 Agent 协作框架 |
| 架构 | Agent 组成 Crew，有角色/层级/任务委派 |
| 关键 | 最快上手的多 Agent 角色系统 |

### 🏢 Microsoft Agent Framework（企业整合）
| 项目 | 详情 |
|------|------|
| 定位 | 企业级统一 Agent 开发平台 |
| 状态 | 2026年2月19日 RC，AutoGen 进入维护模式 |
| 架构 | AutoGen（多 Agent 模式）+ Semantic Kernel（类型安全技能）合并 |
| 关键 | 微软生态整合，企业首选 |

### 💻 Claude Code（Agentic 编码平台）
| 项目 | 详情 |
|------|------|
| 定位 | 终端原生 AI 编码 Agent，远程控制 + 自主调度 |
| 开发 | Anthropic |
| 热度 | 开发者"最喜爱"46%（Cursor 19%，Copilot 9%） |
| 关键 | 2026年2月推出远程控制，hooks/技能/子 Agent 编排 |

### 🤖 Devin（自主软件工程师）
| 项目 | 详情 |
|------|------|
| 定位 | 端到端自主 AI 软件工程 Agent |
| 开发 | Cognition Labs（2023年成立） |
| 架构 | 沙盒环境：代码编辑器 + 终端 + 浏览器 |
| 关键 | Jira → 计划 → 写代码 → 测试 → 修 bug → 提 PR |

### ✏️ Cursor（AI 代码编辑器）
| 项目 | 详情 |
|------|------|
| 定位 | AI 优先代码编辑器 + Agentic 自动化 |
| 开发 | Anysphere（2022年成立） |
| 营收 | **$2B ARR**（2026年2月，3个月翻倍，SaaS 史上最快增长） |
| 估值 | 谈判中 $50B（2026年4月） |
| 用户 | 100万+ 日活 |

### 🌐 Manus AI（通用 Agent）
| 项目 | 详情 |
|------|------|
| 定位 | 全球首个通用自主 AI Agent，可访问虚拟计算机 |
| 上线 | 2025年3月 |
| 收购 | Meta $20亿+（2026年1月，中国监管审查中） |
| 关键 | 规划/编码/部署/深度研究/数据分析/旅行规划 |

---

## 三、身份/信任/声誉系统（AgentID 直接竞品）

### ⚠️ 重要发现：这个赛道正在快速形成

| 项目 | 类型 | 状态 | 核心方案 |
|------|------|------|---------|
| **ERC-8004** | 区块链标准 | **2026年1月29日以太坊主网上线** | Agent 身份+声誉+第三方验证的最小标准 |
| **Open Agent Identity Spec** | 去中心化标准 | 活跃开发中 | DID + 密钥 + 可验证凭证 |
| **CSA Agentic Trust Framework** | 治理规范 | **2026年2月2日发布** | 零信任原则应用于 AI Agent（5层模型） |
| **IETF Agent Identity Framework** | 互联网标准草案 | 草案阶段 | 5层模型，填补现有互联网标准空白 |
| **Agent Trust Hub (ATH)** | 商业产品 | 上线 | GenDigital，全生命周期保护 |
| **Agent Payments Protocol (AP2)** | 支付协议 | 开发中 | DID + 可验证凭证 + 链上结算 + ZKP |

### AgentID vs 竞品差异化分析

| 维度 | ERC-8004 | CSA ATF | AgentID |
|------|---------|---------|---------|
| 身份 | 链上 | 治理框架 | DID + 链下（Phase 1）→ 链上（Phase 2）|
| 声誉评分 | 无 | 无 | **IMDB 式贝叶斯评分（核心差异）** |
| 评分主体 | 无 | 无 | **AI Agent 互评（非人类）** |
| 集成 | 以太坊生态 | 企业 | **OpenClaw + Hermes + Claude Code** |
| 上手难度 | 高（需链上操作） | 高（治理文档） | **低（pip install + API）** |
| 求职市场 | 无 | 无 | **agentworker 集成（杀手级应用）** |
| 阶段 | 已上线 | 已发布 | Phase 1 开发中 |

**结论：AgentID 的核心差异是"声誉评分 + Agent 互评 + 求职市场集成"，这三点现有竞品都没有。**

---

## 四、关键趋势（2026年4月）

### 🔴 趋势1：Agent 安全危机
- OWASP 2026 Agentic AI Top 10 已发布
- **#1 威胁**：提示注入 / Agent 目标劫持
- **新型攻击**：记忆投毒（Memory Poisoning）— 向长期记忆注入恶意指令，跨会话持久存在
- 2024年的理论研究到2025年底已成为生产级攻击
- **行业转向**：从"给 Agent 钥匙"到"给 Agent 可验证的持续身份"
- **AgentID 机会**：防篡改事件链 + 可验证身份 = 天然的安全基础设施

### 🟡 趋势2：Agent 经济爆发
- 市场规模：2026年预计 $896亿（2025年 $76亿，1年12倍）
- 每周 10,000+ 自定义 Agent 发布
- Agent 已成为经济主体：提供服务、定价、接单、收款
- 2025年黑五：Agentic 商业影响 $30亿美国销售额
- **AgentID 机会**：Agent 经济需要身份基础设施，就像互联网需要 SSL

### 🟢 趋势3：多 Agent 编排成主流
- 单 Agent → 多 Agent 协作系统
- LangGraph（有状态图）、CrewAI（角色团队）、MS Agent Framework（对话式）三足鼎立
- **AgentID 机会**：多 Agent 协作需要互相验证身份和能力

### 🔵 趋势4：自我进化 Agent
- Hermes Agent 模式：Agent 写自己的 playbook，技能随时间提升
- 持久记忆让 Agent 构建可复用技能库
- **AgentID 机会**：技能进化历史 = 最有价值的评分数据

### 🟣 趋势5：MCP 协议普及
- Model Context Protocol 成为工具集成标准
- n8n、Claude Code、主流框架原生支持
- **AgentID 机会**：提供 AgentID MCP Server，让任何支持 MCP 的 Agent 都能接入

---

## 五、市场规模与商业机会

```
2025年 AI Agent 市场：$76亿
2026年预测：$896亿（12倍增长）
2030年预测：$1000亿+

Agent 身份/信任基础设施市场（新兴）：
- 类比：SSL 证书市场（$2亿/年）× AI Agent 数量爆炸
- 每周新增 10,000+ Agent
- 每个 Agent 都需要身份
```

---

## 六、内容账号策略（抖音/小红书）

### 目标受众
1. **AI 工具用户**（最大群体）：用 OpenClaw/Hermes/Claude Code 的人
2. **开发者**：想给自己的 Agent 加身份的人
3. **创业者/投资人**：关注 AI Agent 赛道的人

### 内容方向
| 类型 | 示例 | 频率 |
|------|------|------|
| 生态科普 | "2026年最火的10个AI Agent框架" | 每周2篇 |
| 竞品分析 | "OpenClaw vs Hermes Agent，谁更强？" | 每周1篇 |
| 趋势解读 | "AI Agent 安全危机：记忆投毒攻击" | 每周1篇 |
| AgentID 进展 | "我们在做什么：给AI Agent发身份证" | 每月2篇 |
| 技术教程 | "5分钟给你的Agent注册DID身份" | 每月2篇 |

### 差异化定位
> "AI Agent 生态的观察者和建设者"
> 不只是科普，而是**亲历者视角**：我们在做 AgentID，同时观察整个生态

---

## 七、AgentID 战略定位（基于生态分析）

### 核心叙事
> "AI Agent 时代的 LinkedIn + SSL 证书"
> - LinkedIn：职业身份 + 工作履历 + 声誉评分
> - SSL：基础设施，每个 Agent 都需要，不可或缺

### 切入顺序（基于生态热度）
1. **OpenClaw**（350K stars，最大用户群）→ 优先集成
2. **Hermes Agent**（95K stars，自我进化特性与 AgentID 天然契合）→ 第二优先
3. **Claude Code**（Anthropic 生态）→ 已有 Skill 文件
4. **LangGraph/CrewAI**（企业市场）→ Phase 2

### 与 ERC-8004 的关系
- 不是竞争，是互补：ERC-8004 是链上标准，AgentID 是应用层
- Phase 2 可以兼容 ERC-8004，成为其在应用层的实现
- 类比：ERC-20 是标准，Uniswap 是应用

---

*数据来源：GitHub、TechCrunch、HackerNoon、CSA、IETF、各框架官网（2026年4月）*
