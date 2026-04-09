#!/bin/bash
# Batch Upload Script for Milvus Knowledge Base (Linux/Mac)
# This script uploads JSON files from the mineru directory to Milvus KB

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEFAULT_MINERU_DIR="D:/project/OA/core/query_questions2/mineru"
DEFAULT_API_URL="http://localhost:8000/kb/upload"

# Default values
MINERU_DIR="$DEFAULT_MINERU_DIR"
API_URL="$DEFAULT_API_URL"
DRY_RUN=false
FORCE=false
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mineru-dir)
            MINERU_DIR="$2"
            shift 2
            ;;
        --api)
            API_URL="$2"
            shift 2
            ;;
        --chunk-size)
            CHUNK_SIZE="$2"
            shift 2
            ;;
        --chunk-overlap)
            CHUNK_OVERLAP="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            echo "Batch Upload Script for Milvus Knowledge Base"
            echo ""
            echo "Usage: ./batch-upload-kb.sh [options]"
            echo ""
            echo "Options:"
            echo "  --mineru-dir DIR     Directory containing JSON files (default: $DEFAULT_MINERU_DIR)"
            echo "  --api URL            Upload API endpoint (default: $DEFAULT_API_URL)"
            echo "  --chunk-size SIZE    Chunk size in characters (default: 512)"
            echo "  --chunk-overlap N    Chunk overlap in characters (default: 50)"
            echo "  --dry-run            Simulate upload without calling API"
            echo "  --force              Upload all files including previously uploaded"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./batch-upload-kb.sh"
            echo "  ./batch-upload-kb.sh --dry-run"
            echo "  ./batch-upload-kb.sh --force --chunk-size 1024"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if directory exists
if [ ! -d "$MINERU_DIR" ]; then
    echo "Error: Directory does not exist: $MINERU_DIR"
    exit 1
fi

# Display configuration
echo "========================================"
echo "Milvus KB Batch Upload"
echo "========================================"
echo "Source: $MINERU_DIR"
echo "API: $API_URL"
echo "Chunk Size: $CHUNK_SIZE"
echo "Chunk Overlap: $CHUNK_OVERLAP"
echo "Dry Run: $DRY_RUN"
echo "Force Upload: $FORCE"
echo "========================================"
echo ""

# Build arguments
ARGS=(
    --mineru-dir "$MINERU_DIR"
    --api "$API_URL"
    --chunk-size "$CHUNK_SIZE"
    --chunk-overlap "$CHUNK_OVERLAP"
)

if [ "$DRY_RUN" = true ]; then
    ARGS+=(--dry-run)
fi

if [ "$FORCE" = true ]; then
    ARGS+=(--force)
fi

# Change to project directory
cd "$PROJECT_DIR"

# Run the Python script
uv run python scripts/batch_upload_kb.py "${ARGS[@]}"
