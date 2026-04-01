# UV Python 简化完成

## 变更说明

Feature 004 (UV Python Install) 已从复杂的 Python CLI 应用简化为轻量级的 PowerShell/Bash 脚本集合。

## 已移除

- ❌ `src/uv_python/` - 完整的 Python 包（CLI、服务层、数据模型）
- ❌ Typer CLI 框架
- ❌ 复杂的配置系统
- ❌ 完整的测试套件

## 新增

- ✅ `scripts/uv-python/` - 脚本工具集
  - `list.ps1` / `list.sh` - 列出 Python 版本
  - `install.ps1` / `install.sh` - 安装 Python 版本
  - `verify.ps1` / `verify.sh` - 验证 Python 安装
- ✅ `scripts/uv-python/README.md` - 使用文档

## 推荐使用方式

**直接使用 uv 命令：**

```bash
uv python list
uv python install 3.11.8
uv python find 3.11
```

**或使用脚本（提供中文友好输出）：**

```powershell
# Windows
.\scripts\uv-python\list.ps1
.\scripts\uv-python\install.ps1 -Version 3.11.8
```

```bash
# Linux/macOS
./scripts/uv-python/list.sh
./scripts/uv-python/install.sh --version 3.11.8
```

## 项目结构调整

```
src/
├── rag_service/        # Feature 001: RAG Service MVP
├── prompt_service/     # Feature 003: Prompt Service
└── e2e_test/           # Feature 002: E2E Test Framework

scripts/
└── uv-python/          # Feature 004: UV Python 脚本工具集（简化版）
```

## 相关文档

- [Spec 004](../specs/004-uv-python-install/spec.md) - 已更新为简化版本
- [脚本 README](../scripts/uv-python/README.md) - 脚本使用说明
- [CLAUDE.md](../CLAUDE.md) - 已更新项目结构
