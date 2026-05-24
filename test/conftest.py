"""pytest 共享配置"""
import os
import sys
import tempfile
import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def temp_dir():
    """创建临时目录，测试结束后自动清理"""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_txt_file(temp_dir):
    """创建示例文本文件"""
    p = os.path.join(temp_dir, "test.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("Hello World\n" * 1000)
    return p
