#!/bin/bash
# UV Python Install Script
# 安装指定的 Python 版本

VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --help|-h)
            echo "UV Python Install - 安装 Python 版本"
            echo ""
            echo "用法:"
            echo "  ./install.sh --version <版本号>"
            echo ""
            echo "参数:"
            echo "  --version    要安装的 Python 版本 (例如: 3.11.8)"
            echo ""
            echo "示例:"
            echo "  ./install.sh --version 3.11.8"
            echo "  ./install.sh --version 3.12.0"
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

echo "正在安装 Python $VERSION..."

# 检查是否已安装
if uv python list 2>&1 | grep -q "cpython-$VERSION"; then
    echo "Python $VERSION 已安装"
    exit 0
fi

# 执行安装
if uv python install "$VERSION"; then
    echo "Python $VERSION 安装成功"

    # 验证安装
    echo ""
    echo "验证安装..."
    if uv python list 2>&1 | grep -q "cpython-$VERSION"; then
        echo "安装验证成功"
        exit 0
    else
        echo "警告: 安装验证失败" >&2
        exit 1
    fi
else
    echo "错误: 安装失败" >&2
    exit 1
fi
