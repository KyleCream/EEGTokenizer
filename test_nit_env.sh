#!/bin/bash

# 测试导入脚本（nit 环境测试）

echo "=========================================="
echo "测试 EEGTokenizer 导入"
echo "=========================================="

# 激活 conda 环境
echo "激活 conda 环境: mamba_cuda121"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate mamba_cuda121

# 进入项目目录
cd ~/EEGTokenizer

echo ""
echo "当前目录: $(pwd)"
echo ""

# 测试导入
echo "测试导入..."
python3 test_import.py

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
