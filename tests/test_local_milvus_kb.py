"""
本地 Milvus 知识库测试脚本

读取 questions/fianl_version_qa.jsonl 中的问题，
查询本地 Milvus 知识库，并将结果记录到输出文件。
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


async def main():
    """主测试函数"""
    # 配置
    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_file = Path("local_milvus_kb_test_results.json")

    # Milvus 配置
    milvus_uri = "http://localhost:19530"
    collection_name = "knowledge_base"

    # 查询配置
    limit = 0   # 限制测试数量（0表示测试全部）
    top_k = 5   # 返回 top-k 结果

    print("=" * 60)
    print("本地 Milvus 知识库测试")
    print("=" * 60)
    print(f"问题文件: {questions_file}")
    print(f"输出文件: {output_file}")
    print(f"Milvus: {milvus_uri}")
    print(f"集合: {collection_name}")
    print("-" * 60)

    # 初始化 Milvus 客户端
    client = MilvusClient(uri=milvus_uri)

    # 检查集合是否存在
    if not client.has_collection(collection_name):
        print(f"错误: 集合不存在: {collection_name}")
        print(f"可用的集合: {client.list_collections()}")
        return 1

    # 获取集合信息
    stats = client.get_collection_stats(collection_name)
    row_count = stats.get("row_count", 0)
    print(f"\n[集合信息]")
    print(f"  行数: {row_count}")

    desc = client.describe_collection(collection_name)
    print(f"  动态字段: {desc.get('enable_dynamic_field', False)}")

    # 初始化嵌入服务
    print(f"\n[初始化嵌入服务]")
    try:
        embedding_service = await get_http_embedding_service()
        print(f"  嵌入服务已就绪")
    except Exception as e:
        print(f"  错误: {e}")
        return 1

    # 连通性测试
    print(f"\n[连通性测试]")
    test_query = "李志杰"
    print(f"  测试查询: '{test_query}'")
    try:
        query_vector = await embedding_service.embed_text(test_query)
        print(f"  向量维度: {len(query_vector)}")

        results = client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
        )

        print(f"  检索结果: {len(results[0])} 个 chunks")
        if results[0]:
            top_hit = results[0][0]
            print(f"  顶部结果:")
            print(f"    - 距离: {top_hit['distance']:.4f}")
            print(f"    - 标题: {top_hit['entity'].get('formTitle', 'N/A')[:60]}...")
            print(f"    - 内容: {top_hit['entity'].get('fileContent', 'N/A')[:80]}...")
    except Exception as e:
        print(f"  失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 读取问题文件
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
                    answer_list = data.get("answear_list", [])

                    # 分割标题和问题
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
                        "expected_answers": answer_list,
                    })

                except json.JSONDecodeError as e:
                    print(f"  [警告] 第 {line_num} 行 JSON 解析失败: {e}")

    except FileNotFoundError:
        print(f"  错误: 文件不存在: {questions_file}")
        return 1
    except Exception as e:
        print(f"  错误: 读取文件失败: {e}")
        return 1

    if not inputs:
        print(f"  错误: 没有找到有效的问题")
        return 1

    print(f"  解析到 {len(inputs)} 个问题")

    # 限制测试数量
    if limit > 0:
        inputs = inputs[:limit]
        print(f"  限制测试: 前 {len(inputs)} 个问题")

    # 运行查询测试
    print(f"\n[执行查询测试]")
    print(f"共 {len(inputs)} 个问题，开始查询...")
    print("-" * 60)

    results = []
    successful = 0
    failed = 0

    for idx, input_data in enumerate(inputs, 1):
        query = input_data["query"]
        title = input_data["title"]
        expected_answers = input_data["expected_answers"]

        print(f"\n[{idx}/{len(inputs)}] {query[:60]}...")

        try:
            # 生成查询向量
            start_time = time.time()
            query_vector = await embedding_service.embed_text(query)
            embed_time = (time.time() - start_time) * 1000

            # 搜索 Milvus
            start_time = time.time()
            search_results = client.search(
                collection_name=collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
            )
            search_time = (time.time() - start_time) * 1000

            hits = search_results[0]
            print(f"  [OK] 检索到 {len(hits)} 个 chunks")
            print(f"       嵌入: {embed_time:.0f}ms, 搜索: {search_time:.0f}ms")

            # 格式化结果
            chunks = []
            for hit in hits:
                entity = hit["entity"]
                chunks.append({
                    "distance": hit["distance"],
                    "formTitle": entity.get("formTitle", ""),
                    "fileContent": entity.get("fileContent", ""),
                    "document_id": entity.get("document_id", ""),
                    "chunk_index": entity.get("chunk_index", 0),
                })

            # 显示顶部结果
            if chunks:
                top = chunks[0]
                print(f"       顶部: {top['formTitle'][:50]}... (距离: {top['distance']:.4f})")

            results.append({
                "title": title,
                "query": query,
                "expected_answers": expected_answers,
                "chunk_count": len(hits),
                "chunks": chunks,
                "timing": {
                    "embed_ms": embed_time,
                    "search_ms": search_time,
                    "total_ms": embed_time + search_time,
                },
                "success": True,
            })
            successful += 1

        except Exception as e:
            print(f"  [FAIL] 查询失败: {e}")
            results.append({
                "title": title,
                "query": query,
                "expected_answers": expected_answers,
                "chunk_count": 0,
                "chunks": [],
                "success": False,
                "error": str(e),
            })
            failed += 1

    # 计算统计
    total_embed_time = sum(r.get("timing", {}).get("embed_ms", 0) for r in results if r.get("success"))
    total_search_time = sum(r.get("timing", {}).get("search_ms", 0) for r in results if r.get("success"))

    # 保存结果
    print(f"\n[保存结果]")
    output_data = {
        "test_info": {
            "timestamp": datetime.now().isoformat(),
            "questions_file": str(questions_file),
            "total_tests": len(inputs),
            "successful": successful,
            "failed": failed,
        },
        "config": {
            "milvus_uri": milvus_uri,
            "collection_name": collection_name,
            "top_k": top_k,
            "row_count": row_count,
        },
        "connectivity_test": {
            "query": test_query,
            "success": True,
        },
        "statistics": {
            "avg_embed_ms": total_embed_time / max(successful, 1),
            "avg_search_ms": total_search_time / max(successful, 1),
            "avg_total_ms": (total_embed_time + total_search_time) / max(successful, 1),
        },
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  结果已保存到: {output_file}")

    # 打印摘要
    print(f"\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    print(f"  问题文件: {questions_file}")
    print(f"  总问题数: {len(inputs)}")
    print(f"  成功: {successful}")
    print(f"  失败: {failed}")
    print(f"  成功率: {successful / len(inputs) * 100:.1f}%")
    print(f"\n  平均耗时:")
    print(f"    - 嵌入: {output_data['statistics']['avg_embed_ms']:.0f}ms")
    print(f"    - 搜索: {output_data['statistics']['avg_search_ms']:.0f}ms")
    print(f"    - 总计: {output_data['statistics']['avg_total_ms']:.0f}ms")
    print(f"  结果文件: {output_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
