# UV Python 脚本工具集

简化的 Python 版本管理脚本，基于 [uv](https://github.com/astral-sh/uv) 工具。

## 前置要求

- 已安装 [uv](https://github.com/astral-sh/uv)
- Windows: PowerShell 5.1+
- Linux/macOS: Bash 4.0+

## 安装 uv

```bash
# 使用 pip 安装
pip install uv

# 或使用官方安装脚本
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 脚本列表

| 脚本 | 功能 |
|------|------|
| `list.ps1` / `list.sh` | 列出可用的 Python 版本 |
| `install.ps1` / `install.sh` | 安装指定的 Python 版本 |
| `verify.ps1` / `verify.sh` | 验证 Python 安装完整性 |

## 使用方法

### Windows (PowerShell)

```powershell
# 列出可用版本
.\list.ps1

# 安装 Python 3.11.8
.\install.ps1 -Version 3.11.8

# 验证安装
.\verify.ps1 -Version 3.11.8
```

### Linux/macOS (Bash)

```bash
# 赋予执行权限
chmod +x *.sh

# 列出可用版本
./list.sh

# 安装 Python 3.11.8
./install.sh --version 3.11.8

# 验证安装
./verify.sh --version 3.11.8
```

## 直接使用 uv 命令

你也可以直接使用 uv 的内置命令：

```bash
# 列出可用版本
uv python list

# 安装 Python
uv python install 3.11.8

# 查找 Python
uv python find 3.11

# 设置项目 Python 版本
echo "3.11.8" > .python-version
```

## 项目配置

在项目根目录创建 `.python-version` 文件指定 Python 版本：

```
3.11.8
```

或者在 `pyproject.toml` 中指定：

```toml
[project]
requires-python = ">=3.11"
```

## 故障排除

### 安装失败

1. 检查网络连接
2. 尝试使用国内镜像：`uv python install 3.11.8 --index-url https://pypi.tuna.tsinghua.edu.cn/simple`
3. 检查磁盘空间

### 验证失败

1. 确认 Python 已正确安装
2. 检查可执行文件路径
3. 尝试重新安装

## 参考链接

- [uv 官方文档](https://github.com/astral-sh/uv)
- [uv Python 管理](https://astral.sh/blog/uv#python-version-management)
