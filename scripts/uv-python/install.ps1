# UV Python Install Script
# 安装指定的 Python 版本

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [switch]$Help
)

if ($Help) {
    Write-Host "UV Python Install - 安装 Python 版本" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "用法:"
    Write-Host "  .\install.ps1 -Version <版本号>"
    Write-Host ""
    Write-Host "参数:"
    Write-Host "  -Version    要安装的 Python 版本 (例如: 3.11.8)"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\install.ps1 -Version 3.11.8"
    Write-Host "  .\install.ps1 -Version 3.12.0"
    exit 0
}

Write-Host "正在安装 Python $Version..." -ForegroundColor Yellow

try {
    # 检查是否已安装
    $checkResult = uv python list 2>&1
    if ($checkResult -match "cpython-$Version") {
        Write-Host "Python $Version 已安装" -ForegroundColor Green
        exit 0
    }

    # 执行安装
    $process = Start-Process -FilePath "uv" -ArgumentList "python install $Version" -NoNewWindow -PassThru -Wait

    if ($process.ExitCode -eq 0) {
        Write-Host "Python $Version 安装成功" -ForegroundColor Green

        # 验证安装
        Write-Host ""
        Write-Host "验证安装..." -ForegroundColor Yellow
        $verifyResult = uv python list 2>&1
        if ($verifyResult -match "cpython-$Version") {
            Write-Host "安装验证成功" -ForegroundColor Green
        } else {
            Write-Host "警告: 安装验证失败" -ForegroundColor Yellow
        }
    } else {
        Write-Host "错误: 安装失败 (退出码: $($process.ExitCode))" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "错误: $_" -ForegroundColor Red
    exit 1
}
