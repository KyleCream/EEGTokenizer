---
name: discourse-recommender-service
description: Discourse 论坛交互式推荐服务。用户主动问询 → 获取用户信息 → 交互确认需求 → 加载用户画像 → 结合聊天内容和画像生成推荐 → agent 编写推荐理由 → 发送给用户 → 更新用户画像。
---

# Discourse Recommender Service (交互式版)

Discourse 论坛交互式推荐服务。

## 核心架构（新版）

**用户主动问询 → 获取用户ID/用户名 → 交互确认需求 → 加载用户画像 → 结合聊天内容和画像从推荐池获取帖子 → agent 编写推荐理由 → 返回给用户 → 更新用户画像**

```
用户主动问询:
  ↓
获取用户ID/用户名
  ↓
与用户交互，确认推荐内容（关键词、类型等）
  ↓
找寻/加载用户画像
  ↓
结合聊天内容和画像从推荐池中获取帖子
  ↓
生成推荐列表
  ↓
agent 根据帖子内容编写智能推荐理由
  ↓
返回给用户（飞书 + 站内信）
  ↓
agent 根据此次推荐更新用户画像
```

## 多领域分层缓存设计

每个领域有独立的两层缓存：

| 层级 | 说明 | 容量 | 更新频率 |
|------|------|------|---------|
| L1 | 领域热门池 | 50 帖 | 重新聚类/初始化时 |
| L3 | 领域新鲜池 | 100 帖 | Webhook 实时 |

## 用户画像结构

```json
{
  "username": "用户名",
  "created_at": "创建时间",
  "updated_at": "更新时间",
  "interests": {
    "keywords": ["AI", "编程", "GitHub"],
    "categories": [],
    "recent_topics": [1, 2, 3]
  },
  "preferences": {
    "freshness_weight": 0.3,
    "popularity_weight": 0.4,
    "personalization_weight": 0.3
  },
  "interaction_history": [],
  "recommendation_history": [
    {
      "timestamp": "时间",
      "recommended_post_ids": [1, 2, 3],
      "feedback": "用户反馈（可选）"
    }
  ]
}
```

## 目录结构

```
discourse-recommender-service/
├── SKILL.md
├── config/
│   ├── config.json.example
│   └── config.json          # (用户创建，不提交)
├── domains/                 # 每个领域一个子目录
│   ├── domain_0/
│   │   ├── l1_hot.json
│   │   └── l3_fresh.json
│   ├── domain_1/
│   │   ├── l1_hot.json
│   │   └── l3_fresh.json
│   └── ...
├── profiles/                # 用户画像存储
│   ├── zekang.chen.json
│   ├── Kayle.json
│   └── ...
├── domains.json            # 领域定义
├── user_domains.json       # 用户-领域映射
└── scripts/
    ├── init_cache.py        # 初始化（冷启动：分类为领域）
    ├── build_user_profile.py # 为单个用户构建画像
    ├── cluster_domains.py   # 定时领域聚类 + agent 审核
    ├── webhook_handler.py   # Webhook 接收 + 分发更新
    ├── recommend.py         # 从用户所属领域推荐（旧版）
    ├── utils.py             # 工具函数
    ├── interactive_recommend.py    # 【新】交互式推荐 - 数据准备阶段
    └── update_profile_after_recommend.py  # 【新】推荐完成后更新用户画像
```

## 配置

首次使用前，复制 `config/config.json.example` 为 `config/config.json` 并填写：

```json
{
  "discourse_url": "https://your-discourse.example.com",
  "api_key": "your-discourse-api-key",
  "api_username": "system-username-for-api"
}
```

## Webhook 配置

在 Discourse 管理后台设置 webhook：

- **Payload URL**: `https://your-openclaw-server/webhook/discourse`
- **Content Type**: `application/json`
- **触发事件**: `topic_created`

---

## 交互式推荐使用流程（新版）

### 步骤 1：用户主动问询，获取用户信息

用户说："给我推荐一些帖子"

Agent 应该：
1. 获取用户名（从消息上下文或询问用户）
2. 询问用户想要什么类型的推荐

示例交互：
> Agent: "好的，你想要什么类型的帖子？比如：AI 相关、GitHub 项目、技术分享等"

---

### 步骤 2：运行交互式推荐脚本（数据准备阶段）

获取用户和关键词后，运行：

```bash
cd /path/to/discourse-recommender-service

# 交互式推荐 - 数据准备
python3 scripts/interactive_recommend.py \
  --config config/config.json \
  --username zekang.chen \
  --keywords "GitHub,AI,编程" \
  --top 5 \
  --output recommendation_result.json
```

**参数说明：**
- `--config`: 配置文件路径
- `--username`: 用户名
- `--keywords`: 推荐关键词，逗号分隔（可选）
- `--top`: 推荐数量（默认 5）
- `--output`: 输出推荐结果到 JSON 文件（可选）
- `--skill-dir`: Skill 目录路径（可选）

**脚本会输出：**
1. 用户画像加载情况
2. 候选帖子加载情况
3. 关键词匹配结果
4. 排序后的推荐列表（供 agent 编写推荐理由）

---

### 步骤 3：Agent 编写智能推荐理由

**重要：推荐理由必须由 Agent 手动编写，不能用代码自动生成！**

Agent 应该：
1. 查看脚本输出的推荐列表
2. 逐个查看帖子内容（通过 API 获取或点击链接）
3. 为每个帖子写个性化的推荐理由
4. 格式：标题 + 链接 + 推荐理由

**推荐理由示例：**
```
### 1. ai-code-reviewer - 基于大语言模型的自动化代码审查工具
🔗 链接：https://zyt.discourse.diy/t/topic/54

**推荐理由**：这是一个基于大语言模型的自动化代码审查工具。对于开发者来说非常实用，可以自动审查代码质量、发现潜在问题、提供改进建议，大幅提升代码审查效率。
```

---

### 步骤 4：发送给用户

通过飞书和站内信发送推荐：
- **飞书**：直接在对话中发送
- **站内信**：调用 discourse API 发送

---

### 步骤 5：更新用户画像

推荐完成后，运行更新脚本：

```bash
python3 scripts/update_profile_after_recommend.py \
  --config config/config.json \
  --username zekang.chen \
  --feedback "用户反馈（可选）"
```

**参数说明：**
- `--config`: 配置文件路径
- `--username`: 用户名
- `--feedback`: 用户反馈（可选）
- `--temp-file`: 临时推荐数据文件路径（可选，默认自动查找）
- `--skill-dir`: Skill 目录路径（可选）

**脚本会自动：**
1. 加载用户画像
2. 从临时文件加载推荐数据
3. 提取推荐帖子中的关键词，加入用户兴趣
4. 记录推荐历史
5. 更新最近浏览的帖子列表
6. 保存用户画像
7. 清理临时文件

---

## 旧版功能（保留）

### 0. 构建用户画像（可选，用于聚类）

```bash
# 为单个用户构建画像
python3 scripts/build_user_profile.py --config config/config.json --username target_user
```

### 1. 冷启动初始化（首次）

```bash
# 用分类作为初始领域，初始化缓存
python3 scripts/init_cache.py --config config/config.json
```

### 2. 定时领域聚类（每天一次，Cron）

```bash
# 步骤 1: 收集画像 + 聚类 + 生成待审核文件
python3 scripts/cluster_domains.py --config config/config.json --output pending_audit.json

# 步骤 2: agent 审核后，应用新领域划分
python3 scripts/cluster_domains.py --config config/config.json --approve pending_audit.json
```

### 3. 接收 Webhook 更新

通过 OpenClaw webhook 调用：

```bash
python3 scripts/webhook_handler.py --config config/config.json --payload webhook_payload.json
```

### 4. 为用户推荐（旧版）

```bash
# 从所有领域推荐
python3 scripts/recommend.py --config config/config.json --top 10

# 从指定领域推荐
python3 scripts/recommend.py --config config/config.json --domain 4 --top 10
```

---

## 完整使用示例

### 场景：用户要 AI-coding 相关推荐

**1. 用户询问**
> 用户："给我推荐一些 AI-coding 相关的帖子"

**2. Agent 交互（可选，如果需要更明确的需求）**
> Agent："好的，你是想要 AI 编程工具、代码审查、还是其他特定类型？"
> 用户："AI 编程工具就行"

**3. 运行数据准备脚本**
```bash
python3 scripts/interactive_recommend.py \
  --config config/config.json \
  --username zekang.chen \
  --keywords "AI,coding,编程,代码" \
  --top 3
```

**4. Agent 查看输出，编写推荐理由**
（查看脚本输出的推荐列表，逐个写理由）

**5. 发送给用户**
（飞书 + 站内信）

**6. 更新用户画像**
```bash
python3 scripts/update_profile_after_recommend.py \
  --config config/config.json \
  --username zekang.chen
```

---

## 注意事项

- **推荐理由必须由 Agent 手动编写**，禁止使用代码自动生成的模板理由
- 配置文件 `config/config.json` 包含敏感信息，请勿提交到版本控制
- 领域缓存位于 `domains/` 目录，可随时删除重建
- 用户画像位于 `profiles/` 目录
- 冷启动时（无领域定义）使用分类作为初始领域
- API Key 需要有足够权限（读取帖子、用户信息）
- 临时文件会在更新画像后自动清理
