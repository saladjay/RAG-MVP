# Feature Specification: UV Python 脚本工具集

**Feature Branch**: `004-uv-python-install`
**Created**: 2026-03-20
**Updated**: 2026-04-01
**Status**: Completed (简化为脚本集合)

## 概述

这是一个**简化实现**，仅提供 PowerShell/Bash 脚本来包装 uv 的内置 Python 管理功能。

## 实现说明

### 已移除

- ❌ 复杂的 Python CLI 应用（Typer 框架）
- ❌ 服务层架构
- ❌ 数据模型层
- ❌ 完整的测试套件

### 保留

- ✅ PowerShell 脚本（Windows）
- ✅ Bash 脚本（Linux/macOS）
- ✅ 中文友好输出
- ✅ 安装完整性验证

## 脚本列表

| 脚本 | 功能 |
|------|------|
| `list.ps1` / `list.sh` | 列出可用的 Python 版本 |
| `install.ps1` / `install.sh` | 安装指定的 Python 版本 |
| `verify.ps1` / `verify.sh` | 验证 Python 安装完整性 |

## 使用方法

```powershell
# Windows PowerShell
.\list.ps1
.\install.ps1 -Version 3.11.8
.\verify.ps1 -Version 3.11.8
```

```bash
# Linux/macOS
./list.sh
./install.sh --version 3.11.8
./verify.sh --version 3.11.8
```

## 推荐做法

**直接使用 uv 命令更简单：**

```bash
uv python list
uv python install 3.11.8
uv python find 3.11
```

这些脚本主要提供：
1. 中文友好输出
2. 安装验证功能
3. 简化的参数格式
