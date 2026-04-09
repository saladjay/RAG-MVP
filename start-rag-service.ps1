# RAG Service 启动脚本
# 功能: 停止旧进程并启动新的 RAG Service

param(
    [string]$HostName = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$Reload = $false
)

$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput "==========================================" "Cyan"
Write-ColorOutput "  RAG Service 启动脚本" "Cyan"
Write-ColorOutput "==========================================" "Cyan"
Write-Host ""

# 1. 停止旧的进程
Write-ColorOutput "[1/4] 检查并停止旧进程..." "Yellow"

$stopped = 0
$oldProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like "*python*"
}

if ($oldProcesses) {
    Write-ColorOutput "  发现 $($oldProcesses.Count) 个 Python 进程" "Gray"
    foreach ($proc in $oldProcesses) {
        try {
            $proc.Kill()
            $stopped++
            Write-ColorOutput "  [停止] PID=$($proc.Id)" "Green"
        } catch {
            Write-ColorOutput "  [失败] PID=$($proc.Id)" "Red"
        }
    }
    Start-Sleep -Milliseconds 500
} else {
    Write-ColorOutput "  没有发现旧进程" "Gray"
}

Write-ColorOutput "  已停止 $stopped 个进程" "Green"
Write-Host ""

# 2. 检查端口占用
Write-ColorOutput "[2/4] 检查端口 $Port..." "Yellow"

try {
    $portInUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

    if ($portInUse) {
        $owningPid = $portInUse.OwningProcess
        Write-ColorOutput "  端口 $Port 被 PID $owningPid 占用" "Red"

        try {
            Stop-Process -Id $owningPid -Force
            Write-ColorOutput "  [停止] 已释放端口" "Green"
        } catch {
            Write-ColorOutput "  [失败] 无法释放端口" "Red"
            exit 1
        }
    } else {
        Write-ColorOutput "  [OK] 端口 $Port 可用" "Green"
    }
} catch {
    Write-ColorOutput "  [跳过] 无法检查端口" "Gray"
}

Write-Host ""

# 3. 检查环境配置
Write-ColorOutput "[3/4] 检查环境配置..." "Yellow"

$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-ColorOutput "  [错误] 未找到 .env 文件" "Red"
    exit 1
}

# 检查关键配置
$configOk = $true
if (Select-String -Path $envFile -Pattern "CLOUD_COMPLETION_AUTH_TOKEN" -Quiet) {
    $line = Select-String -Path $envFile -Pattern "CLOUD_COMPLETION_AUTH_TOKEN"
    if ($line.Line -match "CLOUD_COMPLETION_AUTH_TOKEN=\s*$") {
        Write-ColorOutput "  [警告] CLOUD_COMPLETION_AUTH_TOKEN 未设置" "Yellow"
        $configOk = $false
    }
} else {
    Write-ColorOutput "  [警告] CLOUD_COMPLETION_AUTH_TOKEN 未配置" "Yellow"
    $configOk = $false
}

if ($configOk) {
    Write-ColorOutput "  [OK] 环境配置检查通过" "Green"
}

Write-Host ""

# 4. 启动服务
Write-ColorOutput "[4/4] 启动 RAG Service..." "Yellow"
Write-Host ""

$reloadFlag = if ($Reload) { "--reload" } else { "" }
$serviceUrl = "http://$HostName`:$Port"
$docsUrl = "$serviceUrl/docs"

Write-ColorOutput "命令: uv run uvicorn src.rag_service.main:app --host $HostName --port $Port $reloadFlag" "Cyan"
Write-ColorOutput "地址: $serviceUrl" "Cyan"
Write-ColorOutput "文档: $docsUrl" "Cyan"
Write-Host ""
Write-ColorOutput "==========================================" "Green"
Write-ColorOutput "  服务启动中... (Ctrl+C 停止)" "Green"
Write-ColorOutput "==========================================" "Green"
Write-Host ""

# 执行启动命令
uv run uvicorn src.rag_service.main:app --host $HostName --port $Port $reloadFlag
