---
name: discourse-recommender-service
description: Discourse 论坛实时推荐服务。Webhook 驱动 + 分层缓存（L1 热门/L2 分类/L3 新鲜）+ 按需推荐，资源高效，实时感知新帖。
---

# Discourse Recommender Service

Discourse 论坛实时推荐服务。

## 核心架构

**分层缓存 + Webhook 驱动 + 按需推荐**

```
Webhook (新帖通知) → 更新分层缓存 → 用户请求时实时推荐
```

## 分层缓存设计

| 层级 | 说明 | 容量 | 更新频率 |
|------|------|------|---------|
| L1 | 全局热门池 | 50 帖 | 每小时 |
| L2 | 分类池 | 每类 30 帖 | 每 30 分钟 |
| L3 | 全局新鲜池 | 100 帖 | Webhook 实时 |

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

### 1. 初始化缓存（首次）

```bash
python3 scripts/init_cache.py --config config/config.json
```

### 2. 接收 Webhook 更新

通过 OpenClaw webhook 调用：

```bash
python3 scripts/webhook_handler.py --config config/config.json --payload webhook_payload.json
```

### 3. 为用户推荐

```bash
python3 scripts/recommend.py --config config/config.json --username target_user --top 10
```

## 文件结构

```
discourse-recommender-service/
├── SKILL.md
├── config/
│   ├── config.json.example
│   └── config.json          # (用户创建，不提交)
├── cache/
│   ├── l1_hot.json
│   ├── l2_category.json
│   └── l3_fresh.json
└── scripts/
    ├── init_cache.py
    ├── webhook_handler.py
    ├── recommend.py
    └── utils.py
```

## 注意事项

- 配置文件 `config/config.json` 包含敏感信息，请勿提交到版本控制
- 缓存文件位于 `cache/` 目录，可随时删除重建
- API Key 需要有足够权限（读取帖子、用户信息）
