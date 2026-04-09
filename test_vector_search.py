"""
本地向量搜索测试 (纯 Embedding)
注意: BM25 混合搜索需要更新的 pymilvus 版本
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service


async def main():
    """测试向量搜索"""

    # 配置
    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_file = Path("vector_search_test_results.json")

    milvus_uri = "http://localhost:19530"

    # 测试两个集合对比
    collections = {
        "knowledge_base": "原始集合 (仅向量)",
        "knowledge_base_hybrid": "混合集合 (向量 + BM25配置)",
    }

    limit = 10  # 测试前10个问题
    top_k = 5

    print("=" * 60)
    print("向量搜索对比测试")
    print("=" * 60)
    print(f"问题文件: {questions_file}")
    print(f"输出文件: {output_file}")
    print(f"测试集合: {list(collections.keys())}")
    print("-" * 60)

    # 初始化
    client = MilvusClient(uri=milvus_uri)
    embedding_service = await get_http_embedding_service()

    # 检查集合
    for coll_name, desc in collections.items():
        if not client.has_collection(coll_name):
            print(f"[WARNING] 集合不存在: {coll_name}")
        else:
            stats = client.get_collection_stats(coll_name)
            row_count = stats.get("row_count", 0)
            print(f"\n{desc}: {row_count} 行")

    # 读取问题
    print(f"\n[读取问题文件]")
    inputs: List[Dict[str, Any]] = []

    try:
        with open(questions_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    title_question = data.get("title_question", "")

                    if "###" in title_question:
                        parts = title_question.split("###", 1)
                        title = parts[0].strip()
                        query = parts[1].strip()
                    else:
                        title = title_question
                        query = title_question

                    inputs.append({
                        "line": line_num,
                        "title": title,
                        "query": query,
                    })

                except json.JSONDecodeError:
                    pass

    except FileNotFoundError:
        print(f"  错误: 文件不存在")
        return 1

    if limit > 0:
        inputs = inputs[:limit]

    print(f"  解析到 {len(inputs)} 个问题")

    # 测试每个集合的向量搜索
    results = []

    for idx, input_data in enumerate(inputs, 1):
        query = input_data["query"]
        title = input_data["title"]

        print(f"\n[{idx}/{len(inputs)}] {query[:60]}...")

        # 生成查询向量
        start_time = time.time()
        query_vector = await embedding_service.embed_text(query)
        embed_time = (time.time() - start_time) * 1000

        query_result = {
            "title": title,
            "query": query,
            "collections": {},
        }

        # 测试每个集合
        for coll_name in collections.keys():
            if not client.has_collection(coll_name):
                continue

            try:
                search_start = time.time()
                # 对于混合集合，需要指定使用哪个向量字段
                search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
                if coll_name == "knowledge_base_hybrid":
                    search_results = client.search(
                        collection_name=coll_name,
                        data=[query_vector],
                        limit=top_k,
                        output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
                        search_params=search_params,
                        anns_field="vector",  # 指定使用密集向量字段
                    )
                else:
                    search_results = client.search(
                        collection_name=coll_name,
                        data=[query_vector],
                        limit=top_k,
                        output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
                    )
                search_time = (time.time() - search_start) * 1000

                hits = search_results[0]
                chunks = [{"distance": h["distance"], **h["entity"]} for h in hits]

                print(f"  [{coll_name[:20]}] {len(hits)} 结果 (搜索: {search_time:.0f}ms)")

                query_result["collections"][coll_name] = {
                    "chunk_count": len(hits),
                    "chunks": chunks[:1],  # 只保存第一个结果
                    "timing": {"embed_ms": embed_time, "search_ms": search_time},
                    "success": True,
                }

            except Exception as e:
                print(f"  [{coll_name[:20]}] 错误: {str(e)[:60]}...")
                query_result["collections"][coll_name] = {
                    "success": False,
                    "error": str(e)
                }

        results.append(query_result)

    # 保存结果
    print(f"\n[保存结果]")
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "collections_tested": list(collections.keys()),
        "total_tests": len(inputs),
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  结果已保存到: {output_file}")

    # 打印摘要
    print(f"\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)

    for coll_name in collections.keys():
        success_count = sum(1 for r in results if r["collections"].get(coll_name, {}).get("success", False))
        if success_count > 0:
            times = [r["collections"][coll_name].get("timing", {}).get("search_ms", 0)
                    for r in results if r["collections"].get(coll_name, {}).get("success", False)]
            avg_time = sum(times) / len(times) if times else 0
            print(f"\n{coll_name}:")
            print(f"  成功: {success_count}/{len(inputs)}")
            print(f"  平均搜索时间: {avg_time:.0f}ms")

    print(f"\n结果文件: {output_file}")
    print("=" * 60)

    # 说明
    print(f"\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("Current status:")
    print("  - Vector search (Embedding): Working")
    print("  - BM25 hybrid search: Requires newer pymilvus version")
    print(f"\nCollections:")
    print("  - knowledge_base: Vector search only")
    print("  - knowledge_base_hybrid: Has BM25 config but can't use API")
    print(f"\nTo enable BM25 hybrid search:")
    print("  1. Upgrade pymilvus to support SPARSESearchRequest")
    print("  2. Use hybrid_search API with AnnSearchRequest + SPARSESearchRequest")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
