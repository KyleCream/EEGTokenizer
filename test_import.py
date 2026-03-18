#!/usr/bin/env python3

# 测试导入
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("测试导入...")
print("=" * 60)

try:
    # 测试 tokenizers 导入
    print("1. 测试 tokenizers 导入...")
    from eegtokenizer_v2.tokenizers import ADCTokenizer, BaseTokenizer
    print("✅ tokenizers 导入成功")

    # 测试 models 导入
    print("2. 测试 models 导入...")
    from eegtokenizer_v2.models import EEGClassifier
    print("✅ models 导入成功")

    # 测试 data 导入
    print("3. 测试 data 导入...")
    from eegtokenizer_v2.data.loader import EEGDataLoader, BCIDataset
    print("✅ data 导入成功")

    # 测试 training 导入
    print("4. 测试 training 导入...")
    from eegtokenizer_v2.training.trainer import Trainer
    print("✅ training 导入成功")

    print("=" * 60)
    print("✅ 所有导入测试通过！")
    print("=" * 60)

except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
