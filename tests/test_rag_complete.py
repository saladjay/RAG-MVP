"""
完整 RAG 流程测试脚本
"""
import asyncio
import httpx
import json
from datetime import datetime


async def test_rag_flow():
    """测试完整的 RAG 流程"""

    base_url = "http://localhost:8000"

    print("=" * 60)
    print("RAG 服务完整流程测试")
    print("=" * 60)

    # 1. 健康检查
    print("\n[1] 健康检查")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/health")
            print(f"  状态: {resp.status_code}")
    except Exception as e:
        print(f"  失败: {e}")
        return

    # 2. 测试查询列表
    test_queries = [
        {"query": "实习生工资是多少", "desc": "薪资查询"},
        {"query": "春节放假几天", "desc": "节假日查询"},
        {"query": "公司地址在哪里", "desc": "基本信息"},
        {"query": "李志杰用什么电脑", "desc": "资产查询"},
    ]

    print(f"\n[2] QA Pipeline 测试 ({len(test_queries)} 个查询)")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=120) as client:
        for idx, test_case in enumerate(test_queries, 1):
            query = test_case["query"]
            desc = test_case["desc"]

            print(f"\n[{idx}/{len(test_queries)}] {desc}: {query}")

            payload = {
                "query": query,
                "context": {
                    "company_id": "N000131",
                    "file_type": "PublicDocReceive"
                },
                "options": {
                    "top_k": 5,
                    "enable_query_rewrite": True,
                    "enable_hallucination_check": True
                }
            }

            try:
                start = datetime.now()
                resp = await client.post(f"{base_url}/qa/query", json=payload)
                elapsed = (datetime.now() - start).total_seconds() * 1000

                if resp.status_code == 200:
                    data = resp.json()

                    # 提取关键信息
                    answer = data.get("answer", "")[:100]
                    sources_count = len(data.get("sources", []))
                    timing = data.get("metadata", {}).get("timing_ms", {})
                    hallucination = data.get("hallucination_status", {})

                    print(f"  [OK] {elapsed:.0f}ms")
                    print(f"       回答: {answer}...")
                    print(f"       来源: {sources_count} 个文档")

                    if timing:
                        print(f"       时序:")
                        print(f"         - 检索: {timing.get('retrieve_ms', 0):.0f}ms")
                        print(f"         - 生成: {timing.get('generate_ms', 0):.0f}ms")

                    if hallucination.get("checked"):
                        status = "通过" if hallucination.get("passed") else "警告"
                        print(f"       幻觉检测: {status} (置信度: {hallucination.get('confidence', 0):.2f})")

                else:
                    print(f"  [FAIL] HTTP {resp.status_code}")
                    print(f"         {resp.text[:200]}")

            except Exception as e:
                print(f"  [ERROR] {str(e)[:100]}")

    # 3. 测试统计
    print(f"\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_rag_flow())
