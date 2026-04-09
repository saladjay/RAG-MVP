"""
外部知识库测试脚本

读取 questions/final_version_qa.jsonl 中的问题，
查询外部知识库，并将结果记录到输出文件。
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.clients.external_kb_client import ExternalKBClient, ExternalKBClientConfig
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


async def main():
    """主测试函数"""
    # 配置
    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_file = Path("external_kb_test_results.json")

    # 外部知识库配置
    base_url = "http://128.23.77.226:6719"
    endpoint = "/cloudoa-ai/ai/file-knowledge/queryKnowledge"
    comp_id = "N000131"
    file_type = "PublicDocDispatch"
    search_type = 1
    topk = 10
    limit = 10  # 限制测试数量（默认前10个）

    # 认证配置 - 选择以下任一模式：
    # 模式1: 自定义 headers（推荐，最灵活）
    auth_headers = {"xtoken": "12345fdsaga6"}  # 正确的 xtoken（没有 6）
    # 或者使用其他认证模式:
    # auth_headers = {"Authorization": "Bearer your-token"}
    # auth_headers = {"x-api-key": "your-api-key"}
    # auth_headers = {"X-Custom-Auth": "value"}

    # 模式2: Bearer token（标准 OAuth2/JWT）
    # auth_token = "your-bearer-token"

    # 模式3: 简单 xtoken（已废弃，仅用于向后兼容）
    # xtoken = "12345fdsaga6"

    print("=" * 60)
    print("外部知识库测试")
    print("=" * 60)
    print(f"问题文件: {questions_file}")
    print(f"输出文件: {output_file}")
    print(f"知识库: {base_url}{endpoint}")
    print(f"认证方式: headers={list(auth_headers.keys())}")
    print("-" * 60)

    # 检查问题文件是否存在
    if not questions_file.exists():
        print(f"错误: 问题文件不存在: {questions_file}")
        print(f"请检查文件路径，或创建文件: {questions_file}")
        return 1

    # 创建客户端（使用新的认证模式）
    config = ExternalKBClientConfig(
        base_url=base_url,
        endpoint=endpoint,
        headers=auth_headers,  # 使用自定义 headers
        # 或者使用 auth_token="..." 作为 Bearer token
        timeout=30,
        max_retries=3,
    )
    client = ExternalKBClient(config)

    # 连通性测试
    print("\n[连通性测试]")
    print("测试查询: '东方思维'")
    try:
        chunks = await client.query(
            query="东方思维",
            comp_id=comp_id,
            file_type=file_type,
            doc_date="",
            keyword="",
            topk=2,
            score_min=0.5,
            search_type=search_type,
        )
        print(f"  结果: {len(chunks)} 个 chunks")
        if chunks:
            print(f"  示例: {chunks[0].get('content', '')[:80]}...")
    except Exception as e:
        print(f"  失败: {e}")
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

        print(f"\n[{idx}/{len(inputs)}] {query[:50]}...")

        try:
            chunks = await client.query(
                query=query,
                comp_id=comp_id,
                file_type=file_type,
                search_type=search_type,
                topk=topk,
            )

            print(f"  [OK] 检索到 {len(chunks)} 个 chunks")

            results.append({
                "title": title,
                "query": query,
                "expected_answers": expected_answers,
                "chunk_count": len(chunks),
                "chunks": chunks,
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
            "base_url": base_url,
            "endpoint": endpoint,
            "comp_id": comp_id,
            "file_type": file_type,
            "search_type": search_type,
            "topk": topk,
        },
        "connectivity_test": {
            "query": "东方思维",
            "success": True,
            "chunk_count": len(chunks) if chunks else 0,
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
    print(f"  结果文件: {output_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
