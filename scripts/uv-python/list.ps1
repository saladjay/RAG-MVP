# UV Python List Script
# 列出可用的 Python 版本

param(
    [switch]$Installed,
    [switch]$Help
)

if ($Help) {
    Write-Host "UV Python List - 列出 Python 版本" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "用法:"
    Write-Host "  .\list.ps1              - 列出所有可用的 Python 版本"
    Write-Host "  .\list.ps1 -Installed   - 仅列出已安装的版本"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\list.ps1"
    Write-Host "  .\list.ps1 -Installed"
    exit 0
}

Write-Host "正在获取 Python 版本信息..." -ForegroundColor Yellow

try {
    if ($Installed) {
        $result = uv python list 2>&1
    } else {
        $result = uv python list 2>&1
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "可用的 Python 版本:" -ForegroundColor Green

        # 解析并格式化输出
        $lines = $result -split "`n"
        foreach ($line in $lines) {
            if ($line -match "cpython-(\d+\.\d+\.\d+)") {
                $version = $matches[1]
                if ($line -match "\*") {
                    Write-Host "  * $version (当前)" -ForegroundColor Cyan
                } else {
                    Write-Host "    $version" -ForegroundColor White
                }
            }
        }
    } else {
        Write-Host "错误: 获取版本列表失败" -ForegroundColor Red
        Write-Host $result
        exit 1
    }
} catch {
    Write-Host "错误: $_" -ForegroundColor Red
    exit 1
}
