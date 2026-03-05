# Discourse API 文档参考

## 基础信息

- **Base URL**: https://zyt.discourse.diy
- **认证方式**: API Key + API Username
- **请求头**:
  ```
  Api-Key: <your-api-key>
  Api-Username: <username>
  Accept: application/json
  ```

## 用户相关 API

### 获取用户信息
```
GET /users/{username}.json
```

### 获取用户活动
```
GET /u/{username}/activity.json
```
注意：不是 `/user_actions.json`，是 `/u/{username}/activity.json`

### 获取用户发布的话题
```
GET /topics/created-by/{username}.json?page=0
```

### 获取用户发布的帖子
```
GET /posts.json?username={username}&page=0
```

## 话题相关 API

### 获取最新话题
```
GET /latest.json?page=0&per_page=30
```

### 获取热门话题
```
GET /top/{period}.json?page=0
period: daily | weekly | monthly | yearly
```

### 获取新话题
```
GET /new.json?page=0
```

### 获取单个话题详情
```
GET /t/{topic_id}.json?include_raw=true
```

### 获取话题下的帖子
```
GET /t/{topic_id}/posts.json
```

### 获取分类下的话题
```
GET /c/{category_id}.json?page=0
```

### 获取标签下的话题
```
GET /tag/{tag_name}.json?page=0
```

## 分类和标签 API

### 获取所有分类
```
GET /categories.json
```

### 获取单个分类详情
```
GET /c/{category_id}/show.json
```

### 获取所有标签
```
GET /tags.json
```

## 搜索 API

### 搜索
```
GET /search.json?q={query}&type={type}&page=0
type: topic | post | user | category
```

### 搜索话题
```
GET /search.json?q={query}&type=topic&page=0
```

### 搜索帖子
```
GET /search.json?q={query}&type=post&page=0
```

## 帖子操作 API

### 创建新帖子
```
POST /posts.json
Content-Type: application/json

{
  "title": "帖子标题",
  "raw": "帖子内容（Markdown）",
  "category": 分类ID
}
```

### 创建回复
```
POST /posts.json
Content-Type: application/json

{
  "topic_id": 话题ID,
  "raw": "回复内容"
}
```

### 创建站内信（Private Message）
```
POST /posts.json
Content-Type: application/json

{
  "title": "站内信标题",
  "raw": "站内信内容（Markdown）",
  "target_recipients": "目标用户名",
  "archetype": "private_message"
}
```
注意：用 `target_recipients`，不是 `target_usernames`

## 响应字段说明

### Topic 对象
```json
{
  "id": 话题ID,
  "title": "标题",
  "fancy_title": "美化标题",
  "slug": "URL别名",
  "posts_count": 帖子数,
  "reply_count": 回复数,
  "highest_post_number": 最高楼层,
  "image_url": "图片URL",
  "created_at": "创建时间",
  "last_posted_at": "最后回复时间",
  "bumped": true,
  "bumped_at": "置顶时间",
  "archetype": "regular",
  "unseen": false,
  "pinned": false,
  "visible": true,
  "closed": false,
  "archived": false,
  "bookmarked": false,
  "liked": false,
  "views": 浏览数,
  "like_count": 点赞数,
  "category_id": 分类ID,
  "has_accepted_answer": false,
  "tags": ["标签1", "标签2"],
  "last_poster": {
    "id": 用户ID,
    "username": "用户名",
    "name": "姓名",
    "avatar_template": "头像模板"
  }
}
```

### User Action 对象
```json
{
  "action_type": 动作类型,
  "created_at": "创建时间",
  "topic_id": 话题ID,
  "post_id": 帖子ID,
  "post_number": 楼层号,
  "username": "用户名",
  "avatar_template": "头像模板",
  "slug": "URL别名",
  "title": "标题",
  "excerpt": "摘要",
  "category_id": 分类ID,
  "truncated": false
}
```

动作类型说明：
- `1`: 点赞
- `2`: 回复
- `3`: 引用
- `4`: 编辑
- `5`: 发帖
- `6`: 移动话题
- `7`: 拆分话题
- `8`: 合并话题
- `9`: 删除帖子
- `11`: 关闭话题
- `12`: 重新打开话题
- `14`: 标记为不感兴趣
- `15`: 点赞已撤销

## 分页参数

大部分列表 API 支持分页：
- `page`: 页码（从0开始）
- `per_page`: 每页数量（默认30，最大100）

## 注意事项

1. API 调用频率限制：避免短时间内大量请求
2. 时间格式：ISO 8601（例如：`2026-03-04T03:24:21.634Z`）
3. 分类ID可以通过 `/categories.json` 获取
