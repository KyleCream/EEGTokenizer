# EEGTokenizer 训练触发流程

**重要！这是核心工作流程，必须牢记！**

---

## 🔄 完整工作流程

### 1. 本地修改代码/配置

```bash
cd /root/.openclaw/workspace/EEGTokenizer

# 修改配置文件
vim eegtokenizer_v2/configs/experiments.yaml

# 或者修改代码
vim eegtokenizer_v2/tokenizers/adc.py
```

### 2. 创建/更新训练标志文件

```bash
# 写入配置名（触发训练）
echo "adc_4bit" > .needs_training

# 或者其他配置名
echo "adc_8bit" > .needs_training
echo "adc_attention" > .needs_training
```

### 3. 提交到 GitHub

```bash
git add .needs_training
# 如果修改了其他文件，也要一起添加
git add eegtokenizer_v2/configs/experiments.yaml

git commit -m "触发训练: adc_4bit"
git push origin main
```

### 4. nit 自动训练

- **nit 的 Cron 任务**会定期检查 GitHub 仓库
- 检测到 `.needs_training` 文件后：
  1. 读取文件内容（配置名，如 `adc_4bit`）
  2. 从 GitHub 拉取最新代码
  3. 检查文件内容：
     - 如果是 `idle` 或 `done` → 不训练，退出
     - 如果是配置名 → 开始训练
  4. 运行训练：`python train.py --config eegtokenizer_v2/configs/experiments.yaml::adc_4bit`
  5. 训练完成后：
     - 将 `.needs_training` 内容改为 `idle`
     - 提交并推送回 GitHub

### 5. 查看训练结果

```bash
# 从 GitHub 拉取最新结果
git pull origin main

# 查看训练日志
cat eegtokenizer_v2/logs/train.log

# 查看训练历史
cat eegtokenizer_v2/checkpoints/*/training_history.json
```

---

## 📋 .needs_training 文件状态

| 状态 | 内容 | 行为 |
|------|------|------|
| 空闲 | `idle` | 不训练 |
| 完成 | `done` | 不训练 |
| 训练中 | 配置名（如 `adc_4bit`） | 开始训练 |

---

## 📋 可用的实验配置

当前 `experiments.yaml` 中定义的配置：

1. **baseline_stf** - 时空频编码器基线
2. **adc_4bit** - ADC 4bit 标量量化（当前使用）
3. **adc_8bit** - ADC 8bit 标量量化
4. **adc_attention** - ADC 4bit + 注意力聚合
5. **adc_4bit_reconstruction** - 重构任务
6. **adc_4bit_probe** - 线性探针评估

---

## ⚠️ 重要注意事项

1. **`.needs_training` 文件必须被 Git 跟踪**
   - 不要在 `.gitignore` 中忽略此文件
   - 每次训练都会更新文件内容（配置名 → idle）

2. **文件内容必须是有效的配置名**
   - 配置名在 `eegtokenizer_v2/configs/experiments.yaml` 中定义
   - 错误的配置名会导致训练失败

3. **训练完成后文件会被设置为 `idle`**
   - 不会删除文件，只会修改内容
   - 这样下次 Cron 运行时不会重复训练

4. **提交信息格式建议**
   ```
   触发训练: <配置名>
   ```
   例如：`触发训练: adc_4bit`

---

## 🚀 快速参考

```bash
# 完整流程示例（ adc_4bit 配置）
cd /root/.openclaw/workspace/EEGTokenizer
echo "adc_4bit" > .needs_training
git add .needs_training
git commit -m "触发训练: adc_4bit"
git push origin main

# 等待 nit 完成训练后
git pull origin main
# 查看日志: cat eegtokenizer_v2/logs/train.log
```

---

**Created:** 2026-03-20
**Last Updated:** 2026-03-20
**Status:** ✅ 核心工作流程
