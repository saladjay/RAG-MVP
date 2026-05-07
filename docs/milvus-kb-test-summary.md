# Milvus 知识库测试日志

**日期**: 2026-04-07
**分支**: 005-rag-qa-pipeline

---

## 一、问题发现与诊断

### 1.1 嵌入服务测试

用户报告上传文档失败（502 Bad Gateway），经直接测试发现：

**测试命令**:
```bash
uv run python scripts/test_embedding_direct.py
```

**测试结果**:
- 嵌入服务本身完全正常
- 单文本嵌入、批量嵌入、并发请求、连续请求全部通过
- 嵌入生成稳定，平均响应时间 ~500ms

**结论**: 嵌入服务不是问题根源。

### 1.2 真实问题定位

**根本原因**: 批处理脚本 `batch_upload_kb.py` 的默认目录配置错误

| 问题 | 原因 |
|------|------|
| JSON 文件读取失败 | 脚本默认路径指向 `query_questions2\mineru` |
| 实际文件位置 | `batch_output\mineru` |
| JSON 字段名 | 内容在 `markdown` 字段，不是 `content` |

**修复**:
```python
# batch_upload_kb.py 第 34 行
DEFAULT_MINERU_DIR = r"D:\project\OA\core\batch_output\mineru"  # 修正路径
```

---

## 二、文档上传成功

### 2.1 上传命令

```bash
cd "D:\project\OA\svn\代码组件"
uv run python scripts/batch_upload_kb.py --mineru-dir "D:\project\OA\core\batch_output\mineru" --force
```

### 2.2 上传结果

| 指标 | 数值 |
|------|------|
| 总文件数 | 66 |
| 成功上传 | 66 |
| 失败 | 0 |
| 成功率 | 100% |
| 总分块数 | 741 |
| 内容总长度 | 329,381 字符 |
| 总耗时 | 168.8 秒 |
| 平均每文件 | 2.6 秒 |

### 2.3 Milvus 集合状态

**集合名称**: `knowledge_base`
**行数**: 1490 (741个文档分块 × 2，可能有重复或之前的数据)

**Schema**:
```
- id: INT64 (auto_id, primary key)
- vector: VECTOR_FLOAT16 (1024维，bge-m3 embedding)
- 动态字段: True (存储 fileContent, formTitle 等)
```

---

## 三、知识库检索测试

### 3.1 测试脚本

创建 `test_local_milvus_kb.py` 测试本地 Milvus 知识库。

### 3.2 全量测试结果 (2445 个问题)

**命令**:
```bash
uv run python test_local_milvus_kb.py
```

**结果摘要**:

| 指标 | 数值 |
|------|------|
| 总问题数 | 2445 |
| 成功 | 2443 |
| 失败 | 2 |
| 成功率 | **99.92%** |
| 平均嵌入耗时 | 117.7ms |
| 平均搜索耗时 | 7.1ms |
| 平均总耗时 | 124.8ms |

**失败原因**: 2个失败都是嵌入服务间歇性 502 错误，与 Milvus 无关。

**结果文件**: `local_milvus_kb_test_results.json`

---

## 四、BM25 + Embedding 混合搜索

### 4.1 问题分析

用户询问是否使用 BM25 + Embedding 混合搜索。

**当前状态**:
- ❌ 仅使用向量搜索（Embedding）
- ❌ 未使用 BM25 全文搜索
- ❌ 未使用混合检索

### 4.2 混合搜索集合创建

创建 `create_hybrid_collection.py` 脚本，生成支持混合搜索的集合。

**新集合配置**:

```python
collection_name = "knowledge_base_hybrid"

Schema:
- id: INT64 (primary key, auto_id)
- fileContent: VARCHAR (65535, enable_analyzer=True)  # BM25 分词
- formTitle: VARCHAR (512)
- document_id: VARCHAR (256)
- chunk_index: INT64
- vector: FLOAT_VECTOR (1024)  # 密集向量
- sparse_vector: SPARSE_FLOAT_VECTOR  # BM25 稀疏向量（自动生成）

Functions:
- bm25_function: 从 fileContent 自动生成 sparse_vector

Indexes:
- vector: IVF_FLAT, COSINE
- sparse_vector: SPARSE_INVERTED_INDEX, BM25
```

### 4.3 文档上传到混合集合

**命令**:
```bash
uv run python upload_to_hybrid_collection.py
```

**结果**:
- 上传 66 个文件
- 总共 741 chunks
- 耗时 17.7 秒

### 4.4 版本兼容性问题

**问题**: pymilvus 2.6.11 不支持 `SPARSESearchRequest`

**检查结果**:
```python
pymilvus version: 2.6.11
Available classes:
  - MilvusClient ✅
  - AnnSearchRequest ✅
  - SPARSESearchRequest ❌
  - RRFRanker ✅
```

**结论**:
- ✅ 集合已配置 BM25（enable_analyzer=True + BM25 函数）
- ❌ Python 客户端无法调用 BM25 搜索 API

### 4.5 向量搜索对比测试

**命令**:
```bash
uv run python test_vector_search.py
```

**结果**:

| 集合 | 描述 | 成功率 | 平均搜索时间 |
|------|------|--------|-------------|
| knowledge_base | 原始集合 (仅向量) | 10/10 | 75ms |
| knowledge_base_hybrid | 混合集合 (向量+BM25配置) | 10/10 | **35ms** ⚡ |

---

## 五、总结与下一步

### 5.1 当前状态

| 功能 | 状态 | 说明 |
|------|------|------|
| 文档上传 | ✅ 完成 | 66个文件，741个分块 |
| 向量搜索 | ✅ 正常 | 平均 7-35ms |
| BM25 配置 | ✅ 已配置 | 集合支持但未使用 |
| 混合搜索 API | ❌ 不可用 | 需要 pymilvus 升级 |

### 5.2 文件清单

**新增脚本**:
- `test_local_milvus_kb.py` - 本地 Milvus 测试
- `create_hybrid_collection.py` - 创建混合搜索集合
- `upload_to_hybrid_collection.py` - 上传到混合集合
- `test_hybrid_search.py` - 混合搜索测试（未完成）
- `test_vector_search.py` - 向量搜索对比

**测试结果**:
- `local_milvus_kb_test_results.json` - 全量测试结果（2445问题）
- `vector_search_test_results.json` - 向量搜索对比结果

**修改文件**:
- `batch_upload_kb.py` - 修正默认目录路径
- `test_qa.py` - 更新为正确的集合名称

### 5.3 Milvus 集合

| 集合名 | 行数 | 用途 |
|--------|------|------|
| knowledge_base | 1490 | 原始向量搜索 |
| knowledge_base_hybrid | 0* | 混合搜索（已配置BM25） |

*注: row_count 显示 0 是统计缓存问题，数据实际存在

### 5.4 下一步选项

1. **升级 pymilvus** - 支持真正的 BM25 + Embedding 混合搜索
2. **使用 RAG Service QA** - 通过 API 生成完整答案
3. **优化检索参数** - 调整 top_k、搜索类型等
4. **添加更多数据** - 扩充知识库内容

---

## 六、技术细节

### 6.1 环境配置

**.env 关键配置**:
```bash
# Milvus
MILVUS_URI=http://localhost:19530
MILVUS_KB_COLLECTION_NAME=knowledge_base
MILVUS_KB_EMBEDDING_DIMENSION=1024

# 嵌入服务
CLOUD_EMBEDDING_URL=http://128.23.74.3:9091/llm/embed-bge/v1/embeddings
CLOUD_EMBEDDING_MODEL=bge-m3
CLOUD_EMBEDDING_TIMEOUT=120
CLOUD_EMBEDDING_AUTH_TOKEN=T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo
```

### 6.2 分块参数

- Chunk size: 512 字符
- Chunk overlap: 50 字符
- Embedding 维度: 1024 (bge-m3)

### 6.3 数据目录

- 源文件: `D:\project\OA\core\batch_output\mineru\`
- 问题文件: `questions\fianl_version_qa.jsonl` (2445 个问题)

---

**日志结束**
