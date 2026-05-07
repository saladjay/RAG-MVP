"""
测试 BM25 + Embedding 混合搜索
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
from pymilvus import AnnSearchRequest, SPARSESearchRequest, RRFRanker
from rag_service.retrieval.embeddings import get_http_embedding_service


async def test_hybrid_search():
    """测试混合搜索"""

    # 配置
    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_file = Path("hybrid_search_test_results.json")

    milvus_uri = "http://localhost:19530"
    collection_name = "knowledge_base_hybrid"

    limit = 10  # 测试前10个问题
    top_k = 5

    print("=" * 60)
    print("BM25 + Embedding 混合搜索测试")
    print("=" * 60)
    print(f"问题文件: {questions_file}")
    print(f"输出文件: {output_file}")
    print(f"集合: {collection_name}")
    print("-" * 60)

    # 初始化
    client = MilvusClient(uri=milvus_uri)
    embedding_service = await get_http_embedding_service()

    # 检查集合
    if not client.has_collection(collection_name):
        print(f"[ERROR] 集合不存在: {collection_name}")
        return 1

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

    # 测试不同搜索模式
    search_modes = ["vector", "bm25", "hybrid"]

    results = []

    for idx, input_data in enumerate(inputs, 1):
        query = input_data["query"]
        title = input_data["title"]

        print(f"\n[{idx}/{len(inputs)}] {query[:60]}...")

        query_result = {
            "title": title,
            "query": query,
            "searches": {},
        }

        for mode in search_modes:
            try:
                start_time = time.time()

                if mode == "vector":
                    # 纯向量搜索
                    query_vector = await embedding_service.embed_text(query)
                    embed_time = (time.time() - start_time) * 1000

                    search_start = time.time()
                    search_results = client.search(
                        collection_name=collection_name,
                        data=[query_vector],
                        limit=top_k,
                        output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
                    )
                    search_time = (time.time() - search_start) * 1000

                    hits = search_results[0]
                    chunks = [{"distance": h["distance"], **h["entity"]} for h in hits]

                    print(f"  [{mode.upper()}] {len(hits)} 结果 (嵌入: {embed_time:.0f}ms, 搜索: {search_time:.0f}ms)")

                    query_result["searches"][mode] = {
                        "chunk_count": len(hits),
                        "chunks": chunks[:1],  # 只保存第一个结果
                        "timing": {"embed_ms": embed_time, "search_ms": search_time},
                        "success": True,
                    }

                elif mode == "bm25":
                    # 纯 BM25 搜索 (使用稀疏向量)
                    search_start = time.time()

                    # 使用 hybrid_search 但只用稀疏向量
                    try:
                        sparse_req = SPARSESearchRequest(
                            data=[query],  # BM25 会自动从查询文本生成稀疏向量
                            anns_field="sparse_vector",
                            param={"metric_type": "BM25"},
                            limit=top_k,
                        )

                        search_results = client.hybrid_search(
                            collection_name=collection_name,
                            reqs=[sparse_req],
                            limit=top_k,
                            output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
                        )

                        search_time = (time.time() - search_start) * 1000
                        hits = search_results[0] if search_results else []
                        chunks = [{"distance": h.get("distance", 0), **h.get("entity", {})} for h in hits]

                        print(f"  [{mode.upper()}] {len(hits)} 结果 (搜索: {search_time:.0f}ms)")

                        query_result["searches"][mode] = {
                            "chunk_count": len(hits),
                            "chunks": chunks[:1],
                            "timing": {"search_ms": search_time},
                            "success": True,
                        }
                    except Exception as e:
                        # BM25 可能不可用，跳过
                        print(f"  [{mode.upper()}] 跳过: {str(e)[:60]}...")
                        query_result["searches"][mode] = {"success": False, "error": str(e)}

                elif mode == "hybrid":
                    # 混合搜索 (向量 + BM25)
                    query_vector = await embedding_service.embed_text(query)
                    embed_time = (time.time() - start_time) * 1000

                    search_start = time.time()

                    try:
                        # 密集向量搜索请求
                        dense_req = AnnSearchRequest(
                            data=[query_vector],
                            anns_field="vector",
                            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                            limit=top_k,
                        )

                        # 稀疏向量搜索请求 (BM25)
                        sparse_req = SPARSESearchRequest(
                            data=[query],
                            anns_field="sparse_vector",
                            param={"metric_type": "BM25"},
                            limit=top_k,
                        )

                        # RRF 排序器
                        ranker = RRFRanker(k=60)

                        # 混合搜索
                        search_results = client.hybrid_search(
                            collection_name=collection_name,
                            reqs=[dense_req, sparse_req],
                            ranker=ranker,
                            limit=top_k,
                            output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
                        )

                        search_time = (time.time() - search_start) * 1000
                        hits = search_results[0] if search_results else []
                        chunks = [{"distance": h.get("distance", 0), **h.get("entity", {})} for h in hits]

                        print(f"  [{mode.upper()}] {len(hits)} 结果 (嵌入: {embed_time:.0f}ms, 搜索: {search_time:.0f}ms)")

                        query_result["searches"][mode] = {
                            "chunk_count": len(hits),
                            "chunks": chunks[:1],
                            "timing": {"embed_ms": embed_time, "search_ms": search_time},
                            "success": True,
                        }
                    except Exception as e:
                        # 混合搜索可能不可用
                        print(f"  [{mode.upper()}] 跳过: {str(e)[:60]}...")
                        query_result["searches"][mode] = {"success": False, "error": str(e)}

            except Exception as e:
                print(f"  [{mode.upper()}] 错误: {str(e)[:80]}...")
                query_result["searches"][mode] = {"success": False, "error": str(e)}

        results.append(query_result)

    # 保存结果
    print(f"\n[保存结果]")
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "collection": collection_name,
        "total_tests": len(inputs),
        "search_modes": search_modes,
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  结果已保存到: {output_file}")

    # 打印摘要
    print(f"\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)

    for mode in search_modes:
        success_count = sum(1 for r in results if r["searches"].get(mode, {}).get("success", False))
        avg_time = 0
        if success_count > 0:
            times = [r["searches"][mode].get("timing", {}).get("search_ms", 0)
                    for r in results if r["searches"].get(mode, {}).get("success", False)]
            avg_time = sum(times) / len(times) if times else 0

        print(f"\n{mode.upper()}:")
        print(f"  成功: {success_count}/{len(inputs)}")
        print(f"  平均搜索时间: {avg_time:.0f}ms")

    print(f"\n结果文件: {output_file}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_hybrid_search())
    sys.exit(exit_code)
