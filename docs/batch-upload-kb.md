# Milvus Knowledge Base Batch Upload

批量上传 Mineru 转换的 JSON 文件到 Milvus 知识库。

## 功能特性

- ✅ **批量处理** - 自动扫描并处理目录中的所有 JSON 文件
- ✅ **智能去重** - 基于 PDF 文件路径生成唯一 document_id，防止重复上传
- ✅ **断点续传** - 记录已上传文件，支持中断后继续上传
- ✅ **失败重试** - 记录失败文件，可单独处理
- ✅ **进度跟踪** - 实时显示上传进度和统计信息
- ✅ **错误处理** - 详细的错误日志和失败文件列表
- ✅ **Dry Run** - 模拟运行，测试配置是否正确

## JSON 文件格式

脚本期望的 JSON 文件格式：

```json
{
  "pdf_file": "D:\\project\\OA\\发文(2)\\2024\\文件名.pdf",
  "markdown": "# 文档内容\n\n这里是 Markdown 格式的文档内容...",
  "success": true,
  "error": null,
  "timestamp": "2026-03-10T14:55:00.901397",
  "content_length": 1174
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `pdf_file` | string | 原始 PDF 文件路径，用于提取标题和生成唯一 ID |
| `markdown` | string | 转换后的 Markdown 内容 |
| `success` | boolean | 转换是否成功，为 `false` 时跳过该文件 |
| `error` | string/null | 错误信息（如果有） |

## 使用方法

### 方式 1: 使用 PowerShell 脚本（Windows 推荐）

```powershell
# 基本使用
.\scripts\batch-upload-kb.ps1

# 模拟运行（不实际上传）
.\scripts\batch-upload-kb.ps1 --dry-run

# 强制重新上传所有文件
.\scripts\batch-upload-kb.ps1 --force

# 自定义参数
.\scripts\batch-upload-kb.ps1 --mineru-dir "D:\path\to\mineru" --api "http://localhost:8000/kb/upload"

# 查看帮助
.\scripts\batch-upload-kb.ps1 --help
```

### 方式 2: 使用 Shell 脚本（Linux/Mac）

```bash
# 添加执行权限
chmod +x scripts/batch-upload-kb.sh

# 基本使用
./scripts/batch-upload-kb.sh

# 模拟运行
./scripts/batch-upload-kb.sh --dry-run

# 强制重新上传
./scripts/batch-upload-kb.sh --force

# 查看帮助
./scripts/batch-upload-kb.sh --help
```

### 方式 3: 直接使用 Python 脚本

```bash
# 基本使用
uv run python scripts/batch_upload_kb.py

# 模拟运行
uv run python scripts/batch_upload_kb.py --dry-run

# 强制重新上传
uv run python scripts/batch_upload_kb.py --force

# 自定义参数
uv run python scripts/batch_upload_kb.py \
    --mineru-dir "D:\project\OA\core\query_questions2\mineru" \
    --api "http://localhost:8000/kb/upload" \
    --chunk-size 512 \
    --chunk-overlap 50
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mineru-dir` | `D:\project\OA\core\query_questions2\mineru` | JSON 文件所在目录 |
| `--api` | `http://localhost:8000/kb/upload` | 上传 API 端点 |
| `--chunk-size` | 512 | 文本分块大小（字符数） |
| `--chunk-overlap` | 50 | 分块重叠大小（字符数） |
| `--timeout` | 300 | 请求超时时间（秒） |
| `--dry-run` | false | 模拟运行，不实际上传 |
| `--force` | false | 强制上传所有文件（包括已上传的） |
| `--help` | - | 显示帮助信息 |

## 工作流程

```
1. 扫描目录
   └─> 查找所有 .json 文件

2. 解析 JSON
   └─> 检查 success 字段
   └─> 验证必填字段（pdf_file, markdown）

3. 提取数据
   └─> 从 pdf_file 提取文档标题
   └─> 使用 pdf_file 生成唯一 document_id（SHA256 哈希）
   └─> 获取 markdown 内容

4. 去重检查
   └─> 检查 upload_tracking.json
   └─> 跳过已上传的文件（除非使用 --force）

5. 上传文档
   └─> 调用 KB Upload API
   └─> 记录上传结果

6. 统计报告
   └─> 显示成功/失败数量
   └─> 生成 failed_uploads.json（如果有失败）
```

## 去重机制

脚本使用 PDF 文件路径的 SHA256 哈希值作为唯一 document_id：

```python
document_id = f"doc_{sha256(pdf_file_path).hexdigest()[:32]}"
```

- 同一 PDF 文件无论转换多少次，都会生成相同的 document_id
- Milvus 会根据 document_id 避免重复插入
- upload_tracking.json 记录已上传文件的 document_id

## 输出示例

```
============================================================
Milvus Knowledge Base Batch Upload
============================================================
Source directory: D:\project\OA\core\query_questions2\mineru
Upload API: http://localhost:8000/kb/upload
Chunk size: 512
Chunk overlap: 50
Dry run: False
Skip existing: True
============================================================
Found 100 JSON files in D:\project\OA\core\query_questions2\mineru

[1/100] 会议纪要（安全生产与应急管理工作专题会议）——〔2024〕6号_mineru.json
  Uploading: 会议纪要（安全生产与应急管理工作专题会议）——〔2024〕6号...
  ✓ Uploaded (3 chunks)

[2/100] 关于印发《东方思维"龙舟水"特别防护期防御工作方案》的通知_mineru.json
  Uploading: 关于印发《东方思维"龙舟水"特别防护期防御工作方案》的通知...
  ✓ Uploaded (45 chunks)

...

============================================================
Upload Summary
============================================================
Total files: 100
Skipped (failed conversion): 2
Skipped (already uploaded): 10
Uploaded successfully: 85
Failed to upload: 3
Total chunks uploaded: 1245
Total content length: 523,456 characters
Elapsed time: 234.5 seconds
Average time per file: 2.8 seconds
```

## 生成的文件

### upload_tracking.json
记录已上传文件的 document_id，用于断点续传：

```json
{
  "uploaded_hashes": [
    "doc_a1b2c3d4...",
    "doc_e5f6g7h8...",
    ...
  ],
  "last_update": "2026-04-07T12:34:56.789012"
}
```

### failed_uploads.json
记录上传失败的文件信息：

```json
[
  {
    "json_file": "D:\\path\\to\\file_mineru.json",
    "title": "文件标题",
    "document_id": "doc_...",
    "error": "错误信息"
  },
  ...
]
```

## 故障排查

### 问题：连接失败
```
Error: Failed to connect to API
```
**解决方案**：
1. 确认 RAG 服务正在运行
2. 检查 API 地址是否正确
3. 检查防火墙设置

### 问题：上传超时
```
Error: Request timeout
```
**解决方案**：
1. 增加超时时间：`--timeout 600`
2. 减小 chunk_size：`--chunk-size 256`
3. 检查网络连接

### 问题：部分文件上传失败
**解决方案**：
1. 查看 `failed_uploads.json` 了解失败原因
2. 修复问题后使用 `--force` 重新上传
3. 或者手动删除失败的记录后重新运行

### 问题：需要重新上传所有文件
```bash
# 使用 --force 参数
.\scripts\batch-upload-kb.ps1 --force
```

## 最佳实践

1. **首次使用**：先用 `--dry-run` 测试配置
   ```powershell
   .\scripts\batch-upload-kb.ps1 --dry-run
   ```

2. **大批量上传**：分批上传，每批 100-200 个文件
   - 便于监控进度
   - 出错时影响范围小

3. **定期备份**：备份 `upload_tracking.json` 文件
   - 避免重新上传已完成的工作

4. **检查失败文件**：及时查看并处理 `failed_uploads.json`

5. **调整参数**：根据文档特点调整 chunk_size 和 chunk_overlap
   - 长文档：增大 chunk_size
   - 短文档：减小 chunk_size

## API 依赖

此脚本依赖以下 RAG Service API 端点：

- `POST /kb/upload` - 上传文档
- `GET /kb/collection/info` - 获取集合信息（可选）
- `GET /kb/health` - 健康检查（可选）

确保 RAG Service 已部署并可访问。

## 相关文档

- [API 文档](../docs/qa-pipeline-api.md)
- [Milvus 集合配置](../docs/milvus-collection-setup.md)
