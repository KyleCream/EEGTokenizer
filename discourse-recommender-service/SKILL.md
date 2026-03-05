---
name: discourse-recommender-service
description: Discourse 论坛高级实时推荐服务。Webhook 驱动 + 自动领域聚类 + 多领域分层缓存 + agent 审核 + 按需推荐，资源高效，实时感知新帖。
---

# Discourse Recommender Service (高级版)

Discourse 论坛高级实时推荐服务。

## 核心架构

**自动领域聚类 + 多领域分层缓存 + Webhook 驱动 + agent 审核 + 按需推荐**

```
定时任务（每天）:
  收集所有用户画像 → 自动领域聚类 → agent 审核 → 更新领域定义

Webhook 实时:
  新帖通知 → 分类到相关领域 → 更新对应领域的 L3 新鲜池

用户请求时:
  查用户所属领域 → 从这些领域的 L1/L2/L3 合并候选 → 按画像精排 → Top N
```

## 多领域分层缓存设计

每个领域有独立的三层缓存：

| 层级 | 说明 | 容量 | 更新频率 |
|------|------|------|---------|
| L1 | 领域热门池 | 50 帖 | 每小时 |
| L2 | 领域分类池 | 每类 30 帖 | 每 30 分钟 |
| L3 | 领域新鲜池 | 100 帖 | Webhook 实时 |

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
│   │   ├── l2_category.json
│   │   └── l3_fresh.json
│   ├── domain_1/
│   │   ├── l1_hot.json
│   │   ├── l2_category.json
│   │   └── l3_fresh.json
│   └── ...
├── profiles/                # 用户画像存储
│   ├── user_001.json
│   ├── user_002.json
│   └── ...
├── cache/                   # 全局/冷启动缓存
│   ├── global_l1_hot.json
│   ├── global_l2_category.json
│   └── global_l3_fresh.json
└── scripts/
    ├── init_cache.py        # 初始化全局/领域缓存
    ├── cluster_domains.py   # 定时领域聚类 + agent 审核
    ├── webhook_handler.py   # Webhook 接收 + 分发更新
    ├── recommend.py         # 从用户所属领域推荐
    └── utils.py             # 工具函数
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

## 使用方式

### 1. 初始化（首次）

```bash
# 初始化全局冷启动缓存
python3 scripts/init_cache.py --config config/config.json --global-only
```

### 2. 定时领域聚类（每天一次，Cron）

```bash
# 聚类 + 生成待审核文件
python3 scripts/cluster_domains.py --config config/config.json --output pending_audit.json

# agent 审核后，应用新领域划分
python3 scripts/cluster_domains.py --config config/config.json --approve pending_audit.json
```

### 3. 接收 Webhook 更新

通过 OpenClaw webhook 调用：

```bash
python3 scripts/webhook_handler.py --config config/config.json --payload webhook_payload.json
```

### 4. 为用户推荐

```bash
python3 scripts/recommend.py --config config/config.json --username target_user --top 10
```

## 注意事项

- 配置文件 `config/config.json` 包含敏感信息，请勿提交到版本控制
- 领域缓存位于 `domains/` 目录，可随时删除重建
- 用户画像位于 `profiles/` 目录
- 冷启动时（无领域）使用 `cache/` 下的全局池
- API Key 需要有足够权限（读取帖子、用户信息）
