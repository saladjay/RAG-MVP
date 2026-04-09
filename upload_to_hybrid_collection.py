"""
将 batch_output 中的文档上传到混合搜索集合
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[Dict[str, Any]]:
    """分块文本"""
    chunks = []
    start = 0
    chunk_index = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_text = text[start:end]

        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "start": start,
                "end": end,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

        if end >= text_length:
            break
        start = end - overlap

    return chunks


async def upload_to_hybrid_collection():
    """上传文档到混合搜索集合"""

    # 配置
    batch_dir = Path(r"D:\project\OA\core\batch_output\mineru")
    milvus_uri = "http://localhost:19530"
    collection_name = "knowledge_base_hybrid"
    chunk_size = 512
    chunk_overlap = 50

    # 初始化
    client = MilvusClient(uri=milvus_uri)
    embedding_service = await get_http_embedding_service()

    print("=" * 60)
    print("上传文档到混合搜索集合")
    print("=" * 60)
    print(f"源目录: {batch_dir}")
    print(f"目标集合: {collection_name}")
    print(f"分块大小: {chunk_size}")
    print(f"重叠: {chunk_overlap}")
    print("-" * 60)

    # 检查集合
    if not client.has_collection(collection_name):
        print(f"[ERROR] 集合不存在: {collection_name}")
        return 1

    # 获取现有行数
    stats_before = client.get_collection_stats(collection_name)
    row_count_before = stats_before.get("row_count", 0)
    print(f"\n集合现有行数: {row_count_before}")

    # 查找 JSON 文件
    json_files = list(batch_dir.glob("*.json"))
    print(f"找到 {len(json_files)} 个 JSON 文件")

    if not json_files:
        print("[ERROR] 没有找到 JSON 文件")
        return 1

    # 上传统计
    total_files = len(json_files)
    uploaded_files = 0
    total_chunks = 0
    failed_files = 0

    start_time = time.time()

    # 处理每个文件
    for i, json_path in enumerate(json_files, 1):
        print(f"\n[{i}/{total_files}] {json_path.name[:60]}...")

        try:
            # 读取 JSON
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查是否有效
            if not data.get("success", False):
                print("  跳过: success=false")
                continue

            # 提取内容
            content = data.get("markdown") or data.get("content", "")
            if not content:
                print("  跳过: 内容为空")
                continue

            pdf_file = data.get("pdf_file", "")
            title = Path(pdf_file).name if pdf_file else json_path.stem

            # 分块
            chunks = chunk_text(content, chunk_size, chunk_overlap)
            if not chunks:
                print("  跳过: 没有分块")
                continue

            # 生成 embeddings
            chunk_texts = [c["text"] for c in chunks]
            embeddings = await embedding_service.embed_batch(chunk_texts)

            if len(embeddings) != len(chunks):
                print(f"  [ERROR] Embedding 数量不匹配: {len(embeddings)} != {len(chunks)}")
                failed_files += 1
                continue

            # 准备插入数据
            # 注意：不需要包含 sparse_vector，BM25 函数会自动生成
            documents = []
            for chunk, embedding in zip(chunks, embeddings):
                documents.append({
                    "fileContent": chunk["text"],
                    "formTitle": title,
                    "document_id": json_path.stem,
                    "chunk_index": chunk["chunk_index"],
                    "vector": embedding,
                    # sparse_vector 由 BM25 函数自动生成，不需要包含
                })

            # 插入 Milvus
            result = client.insert(
                collection_name=collection_name,
                data=documents
            )

            inserted = result.get("insert_count", len(documents))
            print(f"  [OK] 插入 {inserted} chunks")

            uploaded_files += 1
            total_chunks += inserted

        except Exception as e:
            print(f"  [ERROR] {str(e)[:100]}")
            failed_files += 1

    # 检查最终状态
    stats_after = client.get_collection_stats(collection_name)
    row_count_after = stats_after.get("row_count", 0)

    elapsed = time.time() - start_time

    # 打印摘要
    print("\n" + "=" * 60)
    print("上传摘要")
    print("=" * 60)
    print(f"总文件数: {total_files}")
    print(f"成功上传: {uploaded_files}")
    print(f"失败: {failed_files}")
    print(f"总 chunks: {total_chunks}")
    print(f"原有行数: {row_count_before}")
    print(f"现有行数: {row_count_after}")
    print(f"新增行数: {row_count_after - row_count_before}")
    print(f"耗时: {elapsed:.1f}秒")

    if uploaded_files > 0:
        print(f"平均每文件: {elapsed / uploaded_files:.1f}秒")

    print("=" * 60)

    return 0 if failed_files == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(upload_to_hybrid_collection())
    sys.exit(exit_code)
