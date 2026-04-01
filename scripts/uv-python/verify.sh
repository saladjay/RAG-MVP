#!/bin/bash
# UV Python Verify Script
# 验证 Python 安装完整性

VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --help|-h)
            echo "UV Python Verify - 验证 Python 安装"
            echo ""
            echo "用法:"
            echo "  ./verify.sh --version <版本号>"
            echo ""
            echo "参数:"
            echo "  --version    要验证的 Python 版本 (例如: 3.11.8)"
            echo ""
            echo "示例:"
            echo "  ./verify.sh --version 3.11.8"
            exit 0
            ;;
        *)
            echo "错误: 未知参数 '$1'"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    echo "错误: 必须指定 --version 参数"
    echo "使用 --help 查看帮助"
    exit 1
fi

echo "正在验证 Python $VERSION 安装..."

# 检查是否已安装
if ! uv python list 2>&1 | grep -q "cpython-$VERSION"; then
    echo "错误: Python $VERSION 未安装" >&2
    exit 1
fi

# 获取 Python 路径
PYTHON_PATH=$(uv python dir "$VERSION" 2>&1)

if [[ $? -ne 0 ]]; then
    echo "错误: 无法获取 Python 路径" >&2
    exit 1
fi

PYTHON_PATH=$(echo "$PYTHON_PATH" | tr -d '\n\r')
PYTHON_BIN="$PYTHON_PATH/python"

echo "Python 路径: $PYTHON_BIN"

# 检查可执行文件
if [[ ! -f "$PYTHON_BIN" ]]; then
    echo "错误: Python 可执行文件不存在" >&2
    exit 1
fi

# 执行简单测试
echo "运行 Python 测试..."
if TEST_RESULT=$("$PYTHON_BIN" --version 2>&1); then
    echo "验证成功: $TEST_RESULT"
    exit 0
else
    echo "错误: Python 测试失败" >&2
    exit 1
fi
