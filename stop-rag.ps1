# RAG Service Stop Script
# Simple script to stop RAG Service

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  RAG Service Stop" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Stopping Python processes..." -ForegroundColor Yellow
$procs = Get-Process python -ErrorAction SilentlyContinue
$stopped = 0

if ($procs) {
    foreach ($p in $procs) {
        Stop-Process -Id $p.Id -Force
        $stopped++
        Write-Host "  Stopped PID: $($p.Id)" -ForegroundColor Green
    }
} else {
    Write-Host "  No Python processes found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Stopped $stopped process(es)" -ForegroundColor Green
Write-Host ""
