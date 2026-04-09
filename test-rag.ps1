# RAG Service Test Script
# Simple script to test RAG Service

$BaseUrl = "http://localhost:8000"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  RAG Service Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "URL: $BaseUrl" -ForegroundColor Gray
Write-Host ""

# Test 1: Health
Write-Host "[Test 1/3] Health Check..." -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health" -Method Get
    Write-Host "  OK - Status: $($resp.status)" -ForegroundColor Green
} catch {
    Write-Host "  FAILED - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Capabilities
Write-Host "[Test 2/3] Capabilities..." -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/capabilities" -Method Get
    Write-Host "  OK - $($resp.capabilities.Count) capabilities" -ForegroundColor Green
} catch {
    Write-Host "  FAILED" -ForegroundColor Red
}

# Test 3: QA Query
Write-Host "[Test 3/3] QA Query..." -ForegroundColor Yellow
Write-Host "  Query: 2025年春节放假共计几天？" -ForegroundColor Gray

$body = @{
    query = "2025年春节放假共计几天？"
    context = @{
        company_id = "N000131"
        file_type = "PublicDocDispatch"
    }
} | ConvertTo-Json -Depth 3

try {
    $resp = Invoke-RestMethod -Uri "$BaseUrl/qa/query" -Method Post -Body $body -ContentType "application/json"
    Write-Host "  OK - Query successful" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Answer Preview:" -ForegroundColor Cyan
    $preview = $resp.answer
    if ($preview.Length -gt 150) { $preview = $preview.Substring(0, 150) + "..." }
    Write-Host "    $preview" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Sources: $($resp.sources.Count)" -ForegroundColor Cyan
    Write-Host "  Timing: $($resp.metadata.timing_ms.total_ms)ms total" -ForegroundColor Cyan
} catch {
    Write-Host "  FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Test Complete" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
