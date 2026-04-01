#!/bin/bash
# UV Python List Script
# 列出可用的 Python 版本

INSTALLED=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --installed|-i)
            INSTALLED=true
            shift
            ;;
        --help|-h)
            echo "UV Python List - 列出 Python 版本"
            echo ""
            echo "用法:"
            echo "  ./list.sh              - 列出所有可用的 Python 版本"
            echo "  ./list.sh --installed  - 仅列出已安装的版本"
            echo ""
            echo "示例:"
            echo "  ./list.sh"
            echo "  ./list.sh --installed"
            exit 0
            ;;
        *)
            echo "错误: 未知参数 '$1'"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

echo "正在获取 Python 版本信息..."

if uv python list 2>&1; then
    echo ""
    echo "可用的 Python 版本:"
    uv python list 2>&1 | while IFS= read -r line; do
        if [[ $line =~ cpython-([0-9]+\.[0-9]+\.[0-9]+) ]]; then
            version="${BASH_REMATCH[1]}"
            if [[ $line == *"@"* ]]; then
                echo "  * $version (当前)"
            else
                echo "    $version"
            fi
        fi
    done
else
    echo "错误: 获取版本列表失败" >&2
    exit 1
fi
