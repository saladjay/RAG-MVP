# RAG Service 停止脚本
# 功能: 停止所有 RAG Service 相关进程

$ErrorActionPreference = "Stop"

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput "==========================================" "Cyan"
Write-ColorOutput "  RAG Service 停止脚本" "Cyan"
Write-ColorOutput "==========================================" "Cyan"
Write-Host ""

$stopped = 0

# 方法1: 按端口查找
Write-ColorOutput "[1/2] 检查端口 8000..." "Yellow"

try {
    $portConnections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

    if ($portConnections) {
        $pids = $portConnections | Select-Object -ExpandProperty OwningProcess -Unique

        foreach ($pid in $pids) {
            try {
                $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($proc) {
                    Stop-Process -Id $pid -Force
                    $stopped++
                    Write-ColorOutput "  [停止] PID=$pid - $($proc.ProcessName)" "Green"
                }
            } catch {
                Write-ColorOutput "  [失败] PID=$pid" "Red"
            }
        }
    } else {
        Write-ColorOutput "  端口 8000 未被占用" "Gray"
    }
} catch {
    Write-ColorOutput "  [跳过] 无法检查端口" "Gray"
}

Write-Host ""

# 方法2: 按进程名查找
Write-ColorOutput "[2/2] 检查 Python 进程..." "Yellow"

$pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue

if ($pythonProcs) {
    foreach ($proc in $pythonProcs) {
        try {
            # 检查是否是 uvicorn 进程
            $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId=$($proc.Id)").CommandLine
            if ($cmdLine -match "uvicorn" -or $cmdLine -match "rag_service") {
                Stop-Process -Id $proc.Id -Force
                $stopped++
                Write-ColorOutput "  [停止] PID=$($proc.Id) - uvicorn" "Green"
            }
        } catch {
            # 忽略无法访问的进程
        }
    }

    if ($stopped -eq 0) {
        Write-ColorOutput "  没有发现 uvicorn 进程" "Gray"
    }
} else {
    Write-ColorOutput "  没有发现 Python 进程" "Gray"
}

Write-Host ""
Write-ColorOutput "==========================================" "Green"
Write-ColorOutput "  已停止 $stopped 个进程" "Green"
Write-ColorOutput "==========================================" "Green"
