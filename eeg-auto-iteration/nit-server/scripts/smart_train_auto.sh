#!/bin/bash

###############################################################################
# GPU 智能选择训练脚本
# 功能: 自动选择空闲的显卡运行训练
# 作者: 小k
# 日期: 2026-03-19
###############################################################################

# 选择空闲显卡
select_free_gpu() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 选择空闲显卡..."
    
    # 获取两张显卡的内存使用情况
    GPU0_MEM=$(nvidia-smi -i 0 --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo "0")
    GPU1_MEM=$(nvidia-smi -i 1 --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo "0")
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] GPU 0 内存使用: ${GPU0_MEM} MiB"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] GPU 1 内存使用: ${GPU1_MEM} MiB"
    
    # 选择内存使用较少的显卡
    if [ "$GPU0_MEM" -le "$GPU1_MEM" ]; then
        export CUDA_VISIBLE_DEVICES="0"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 选择 GPU 0 (内存使用较少)"
    else
        export CUDA_VISIBLE_DEVICES="1"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 选择 GPU 1 (内存使用较少)"
    fi
}

# 调用函数选择显卡
select_free_gpu

# 运行原始训练脚本
exec /home/zengkai/EEGTokenizer/eeg-auto-iteration/nit-server/scripts/github_pull_train.sh "$@"
