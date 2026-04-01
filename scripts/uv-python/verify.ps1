# UV Python Verify Script
# 验证 Python 安装完整性

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [switch]$Help
)

if ($Help) {
    Write-Host "UV Python Verify - 验证 Python 安装" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "用法:"
    Write-Host "  .\verify.ps1 -Version <版本号>"
    Write-Host ""
    Write-Host "参数:"
    Write-Host "  -Version    要验证的 Python 版本 (例如: 3.11.8)"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\verify.ps1 -Version 3.11.8"
    exit 0
}

Write-Host "正在验证 Python $Version 安装..." -ForegroundColor Yellow

try {
    # 检查是否已安装
    $checkResult = uv python list 2>&1
    if (-not ($checkResult -match "cpython-$Version")) {
        Write-Host "错误: Python $Version 未安装" -ForegroundColor Red
        exit 1
    }

    # 获取 Python 路径
    $pythonPath = uv python dir $Version 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 无法获取 Python 路径" -ForegroundColor Red
        exit 1
    }

    $pythonPath = $pythonPath.Trim()
    $pythonExe = Join-Path $pythonPath "python.exe"

    Write-Host "Python 路径: $pythonExe" -ForegroundColor Cyan

    # 检查可执行文件
    if (-not (Test-Path $pythonExe)) {
        Write-Host "错误: Python 可执行文件不存在" -ForegroundColor Red
        exit 1
    }

    # 执行简单测试
    Write-Host "运行 Python 测试..." -ForegroundColor Yellow
    $testResult = & $pythonExe --version 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "验证成功: $testResult" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "错误: Python 测试失败" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "错误: $_" -ForegroundColor Red
    exit 1
}
