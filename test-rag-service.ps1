# RAG Service 测试脚本
# 功能: 测试 RAG Service 各个端点

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Query = "2025年春节放假共计几天？",
    [string]$CompanyId = "N000131",
    [string]$FileType = "PublicDocDispatch"
)

$ErrorActionPreference = "Stop"

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput "==========================================" "Cyan"
Write-ColorOutput "  RAG Service 测试" "Cyan"
Write-ColorOutput "==========================================" "Cyan"
Write-Host ""
Write-ColorOutput "服务地址: $BaseUrl" "Gray"
Write-Host ""

# 测试1: 健康检查
Write-ColorOutput "[测试 1/4] 健康检查..." "Yellow"

try {
    $healthResponse = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
    Write-ColorOutput "  [OK] 服务运行正常" "Green"
    Write-ColorOutput "  状态: $($healthResponse.status)" "Gray"
    Write-ColorOutput "  版本: $($healthResponse.version)" "Gray"
} catch {
    Write-ColorOutput "  [失败] $($_.Exception.Message)" "Red"
    exit 1
}

Write-Host ""

# 测试2: 能力列表
Write-ColorOutput "[测试 2/4] 能力列表..." "Yellow"

try {
    $capsResponse = Invoke-RestMethod -Uri "$BaseUrl/capabilities" -Method Get
    Write-ColorOutput "  [OK] 已注册 $($capsResponse.capabilities.Count) 个能力" "Green"
    foreach ($cap in $capsResponse.capabilities) {
        Write-ColorOutput "    - $cap" "Gray"
    }
} catch {
    Write-ColorOutput "  [失败] $($_.Exception.Message)" "Red"
}

Write-Host ""

# 测试3: 模型发现
Write-ColorOutput "[测试 3/4] 模型发现..." "Yellow"

try {
    $modelsResponse = Invoke-RestMethod -Uri "$BaseUrl/models" -Method Get
    Write-ColorOutput "  [OK] 发现 $($modelsResponse.models.Count) 个模型" "Green"
    foreach ($model in $modelsResponse.models) {
        Write-ColorOutput "    - $($model.model_id) [$($model.provider)]" "Gray"
    }
} catch {
    Write-ColorOutput "  [失败] $($_.Exception.Message)" "Red"
}

Write-Host ""

# 测试4: QA 查询
Write-ColorOutput "[测试 4/4] QA 查询..." "Yellow"
Write-ColorOutput "  问题: $Query" "Gray"

$qaPayload = @{
    query = $Query
    context = @{
        company_id = $CompanyId
        file_type = $FileType
    }
} | ConvertTo-Json -Depth 3

try {
    $qaResponse = Invoke-RestMethod -Uri "$BaseUrl/qa/query" -Method Post -Body $qaPayload -ContentType "application/json"

    Write-ColorOutput "  [OK] 查询成功" "Green"
    Write-Host ""

    Write-ColorOutput "  答案:" "Cyan"
    $answerText = $qaResponse.answer
    if ($answerText.Length -gt 200) {
        $answerText = $answerText.Substring(0, 200) + "..."
    }
    Write-ColorOutput "    $answerText" "Gray"
    Write-Host ""

    Write-ColorOutput "  来源: $($qaResponse.sources.Count) 个" "Cyan"
    foreach ($source in $qaResponse.sources | Select-Object -First 3) {
        Write-ColorOutput "    - $($source.document_name) (score: $($source.score))" "Gray"
    }

    Write-Host ""
    Write-ColorOutput "  时序:" "Cyan"
    $timing = $qaResponse.metadata.timing_ms
    Write-ColorOutput "    - 检索: $($timing.retrieve_ms)ms" "Gray"
    Write-ColorOutput "    - 生成: $($timing.generate_ms)ms" "Gray"
    Write-ColorOutput "    - 总计: $($timing.total_ms)ms" "Gray"

} catch {
    Write-ColorOutput "  [失败] $($_.Exception.Message)" "Red"
}

Write-Host ""
Write-ColorOutput "==========================================" "Green"
Write-ColorOutput "  测试完成" "Green"
Write-ColorOutput "==========================================" "Green"
