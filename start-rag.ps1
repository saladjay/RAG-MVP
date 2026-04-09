# RAG Service Start Script
# Simple script to start RAG Service

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  RAG Service Start" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Stop old processes
Write-Host "[1/2] Stopping old processes..." -ForegroundColor Yellow
$procs = Get-Process python -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        Stop-Process -Id $p.Id -Force
        Write-Host "  Stopped PID: $($p.Id)" -ForegroundColor Green
    }
}
Write-Host ""

# Start service
Write-Host "[2/2] Starting RAG Service..." -ForegroundColor Yellow
Write-Host ""
Write-Host "URL: http://0.0.0.0:8000" -ForegroundColor Cyan
Write-Host "Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

uv run uvicorn src.rag_service.main:app --host 0.0.0.0 --port 8000 --log-level info
