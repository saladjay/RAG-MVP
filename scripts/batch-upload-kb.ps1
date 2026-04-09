# Batch Upload Script for Milvus Knowledge Base (Windows)
# This script uploads JSON files from the mineru directory to Milvus KB

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$DefaultMineruDir = "D:\project\OA\core\query_questions2\mineru"
$DefaultApiUrl = "http://localhost:8000/kb/upload"

# Parse command line arguments
$MineruDir = $DefaultMineruDir
$ApiUrl = $DefaultApiUrl
$DryRun = $false
$Force = $false
$ChunkSize = 512
$ChunkOverlap = 50

# Parse arguments
for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--mineru-dir" {
            $MineruDir = $args[++$i]
        }
        "--api" {
            $ApiUrl = $args[++$i]
        }
        "--dry-run" {
            $DryRun = $true
        }
        "--force" {
            $Force = $true
        }
        "--chunk-size" {
            $ChunkSize = [int]$args[++$i]
        }
        "--chunk-overlap" {
            $ChunkOverlap = [int]$args[++$i]
        }
        "--help" {
            Write-Host "Batch Upload Script for Milvus Knowledge Base"
            Write-Host ""
            Write-Host "Usage: .\batch-upload-kb.ps1 [options]"
            Write-Host ""
            Write-Host "Options:"
            Write-Host "  --mineru-dir DIR     Directory containing JSON files (default: $DefaultMineruDir)"
            Write-Host "  --api URL            Upload API endpoint (default: $DefaultApiUrl)"
            Write-Host "  --chunk-size SIZE    Chunk size in characters (default: 512)"
            Write-Host "  --chunk-overlap N    Chunk overlap in characters (default: 50)"
            Write-Host "  --dry-run            Simulate upload without calling API"
            Write-Host "  --force              Upload all files including previously uploaded"
            Write-Host "  --help               Show this help message"
            Write-Host ""
            Write-Host "Examples:"
            Write-Host "  .\batch-upload-kb.ps1"
            Write-Host "  .\batch-upload-kb.ps1 --dry-run"
            Write-Host "  .\batch-upload-kb.ps1 --force --chunk-size 1024"
            exit 0
        }
    }
}

# Check if directory exists
if (-not (Test-Path $MineruDir)) {
    Write-Host "Error: Directory does not exist: $MineruDir" -ForegroundColor Red
    exit 1
}

# Build Python command
$PythonCmd = "uv run python scripts\batch_upload_kb.py"
$ArgsList = @(
    "--mineru-dir", "`"$MineruDir`""
    "--api", "`"$ApiUrl`""
    "--chunk-size", $ChunkSize
    "--chunk-overlap", $ChunkOverlap
)

if ($DryRun) {
    $ArgsList += "--dry-run"
}

if ($Force) {
    $ArgsList += "--force"
}

# Display configuration
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Milvus KB Batch Upload" -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Source: $MineruDir"
Write-Host "API: $ApiUrl"
Write-Host "Chunk Size: $ChunkSize"
Write-Host "Chunk Overlap: $ChunkOverlap"
Write-Host "Dry Run: $DryRun"
Write-Host "Force Upload: $Force"
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# Run the Python script
try {
    Push-Location $ProjectDir
    & uv run python scripts\batch_upload_kb.py $ArgsList
    $ExitCode = $LASTEXITCODE
}
catch {
    Write-Host "Error running upload script: $_" -ForegroundColor Red
    $ExitCode = 1
}
finally {
    Pop-Location
}

exit $ExitCode
