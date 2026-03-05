---
name: discourse-recommender-plus
description: Discourse 论坛个性化帖子推荐系统（混合版）。Tags为主 + 人工分析 + 关键词保底，对上下文影响小，稳定可靠。
---

# Discourse Recommender Plus Skill (混合版)

Discourse 论坛个性化帖子推荐系统（**混合版**）。

## 核心原则

**Tags 为主（60%），人工分析为辅（30%），关键词提取保底（10%）**

---

## 配置信息

- **论坛地址**: https://zyt.discourse.diy
- **API Key**: 0955e767959917cf2dad58a53b676cac93ccba34975330f1b42acd38ae952bbb
- **API 用户名**: Kayle

---

## 技术路线（混合版）

### 1. 数据收集
- 获取用户活动、帖子、分类、**Tags**

### 2. 兴趣画像构建（混合模式）
| 部分 | 权重 | 说明 |
|------|------|------|
| Tags 偏好 | 60% | 从用户互动过的帖子中提取 Tags |
| 小k补充关键词 | 30% | 小k分析后补充的关键词 |
| 关键词保底 | 10% | 仅当 Tags 不足时用 TF-IDF 从标题提取 |

### 3. 帖子召回（Tags优先）
1. **Tags 匹配**（权重最高）
2. **分类匹配**
3. **作者匹配**
4. **小k补充关键词匹配**
5. **热门帖子保底**

### 4. 排序精排
- Tags 相关性权重 ↑
- 关键词相关性权重 ↓
- 保留新鲜度、热度、多样性

### 5. 推荐呈现

---

## 使用流程

### 模式 A：全自动（只用 Tags + 保底关键词）

```bash
# 直接运行，不需要小k分析
python3 scripts/recommend.py --username zekang.chen --top 10
```

### 模式 B：混合模式（推荐，Tags + 人工分析）

```bash
# 步骤 1：收集数据 + 生成初步画像 + 导出供分析
python3 scripts/recommend.py --username <目标用户名> --human-analysis

# 步骤 2：分析 human_analysis_xxx.json 文件
# （创建 profile_with_human_xxx.json，包含 human_keywords

# 步骤 3：用补充后的画像做推荐
python3 scripts/recommend.py --username <目标用户名> --profile profile_with_human_<目标用户名>.json
```

---

## 文件结构

```
discourse-recommender-plus/
├── SKILL.md
├── scripts/
│   ├── recommend.py          # 主推荐脚本（混合版）
│   ├── collect_data.py     # 数据收集模块
│   ├── build_profile.py    # 兴趣画像构建（混合版）
│   ├── recall.py          # 帖子召回模块（Tags优先）
│   ├── rank.py           # 排序精排模块
│   └── utils.py          # 工具函数
├── cache/                # 缓存目录
└── scripts.bak/          # 原版备份
```

## 依赖

- Python 3.7+
- requests
- jieba
- scikit-learn
- numpy

（已安装完成）

---

## 注意事项

- API Key 已保存，请勿泄露
- 日常使用优先用 **模式 A（全自动）
- 需要更精准推荐用 **模式 B（混合模式）
