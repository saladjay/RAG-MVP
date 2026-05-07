"""
测试 Dify 工作流 API
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import httpx


DIFY_API_URL = "http://128.23.74.4/v1/chat-messages"
DIFY_API_KEY = "app-cfSS1P9f54NMCE8lvbStqnsq"  # 用于 Authorization header
DIFY_APP_ID = "d7da8601-7a9f-4ee0-9d1a-528d9cdeaf3a"
DIFY_APPLICATION_KEY = "ApiSecretKey_kVsvUcvcModZXJwVsdvJfRpbbaicXJFq"
USER_ID = "N10070128"

# Dify 工作流所需的输入参数
OLD_PARAM_TEMPLATE = {
    "matchMode": "matchQuery",
    "matchQueryField": "titleContentAttachment",
    "searchKey": "查询收文",
    "searchType": "documentManagement",
    "userId": "N10070128",
    "userName": "唐亚军",
    "belongCompanyName": "广东东方思维科技有限公司",
    "companyIds": ["N000131", "N006964"],
    "departmentIds": ["N001709"],
    "systemCode": "cloudoadev",
    "advancedQueryList": [
        {"fieldsId": "serialNumber", "fieldsValue": "", "compareType": "LIKE"},
        {"fieldsId": "fromCompany", "fieldsValue": "", "compareType": "LIKE"}
    ],
    "belongDepartmentName": "",
    "page": 1,
    "size": 20,
    "belongUserName": "",
    "orderBy": "",
    "remark": "查询收文",
    "module": "dispatchmanger,receivemanger,publicdochandworkmanger",
    "matchQueryTime": "",
    "filterRelationBelongDepartmentName": "or"
}
XTOKEN = "XAT-02489ed8-c490-4298-8653-fa904cca3a5d"


async def test_dify_workflow(
    questions_file: str = "questions/fianl_version_qa.jsonl",
    output_file: str = "dify_workflow_test_results.json",
    limit: int = 10,
):
    """测试 Dify 工作流 API"""

    questions_path = Path(questions_file)
    output_path = Path(output_file)

    print("=" * 60)
    print("Dify 工作流 API 测试")
    print("=" * 60)
    print(f"问题文件: {questions_path}")
    print(f"输出文件: {output_path}")
    print(f"API 地址: {DIFY_API_URL}")
    print("-" * 60)

    # 读取问题
    print(f"\n[读取问题文件]")
    inputs: List[Dict[str, Any]] = []

    try:
        with open(questions_path, "r", encoding="utf-8") as f:
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

    # 创建 HTTP 客户端
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    results = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for idx, input_data in enumerate(inputs, 1):
            query = input_data["query"]
            title = input_data["title"]

            print(f"\n[{idx}/{len(inputs)}] {query[:60]}...")

            query_result = {
                "title": title,
                "query": query,
            }

            try:
                start_time = time.time()

                # 构建请求体
                # 将查询字符串更新到 oldParam 的 searchKey 中
                old_param = OLD_PARAM_TEMPLATE.copy()
                old_param["searchKey"] = query
                old_param["remark"] = query

                # 获取当前时间
                chat_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                payload = {
                    "query": query,
                    "conversation_id": "",
                    "user": USER_ID,  # Dify 要求的 user 字段
                    "userId": USER_ID,
                    "appId": DIFY_APP_ID,
                    "inputs": {
                        "systemId": "oa",
                        "xtoken": XTOKEN,
                        "oldParam": json.dumps(old_param, ensure_ascii=False),  # JSON 字符串
                    },
                    "difyApplicationKey": DIFY_APPLICATION_KEY,
                    "chatTime": chat_time,
                    "response_mode": "blocking",
                }

                # 发送请求
                response = await client.post(
                    DIFY_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                elapsed = (time.time() - start_time) * 1000

                result_data = response.json()

                # 提取响应信息
                query_result["response"] = {
                    "answer": result_data.get("answer", ""),
                    "conversation_id": result_data.get("conversation_id", ""),
                    "message_id": result_data.get("message_id", ""),
                    "created_at": result_data.get("created_at", ""),
                }

                # 提取元数据
                if "metadata" in result_data:
                    query_result["metadata"] = result_data["metadata"]

                # 提取检索信息（如果有）
                if "retriever_resources" in result_data:
                    query_result["retriever_resources"] = result_data["retriever_resources"]

                query_result["timing_ms"] = elapsed
                query_result["success"] = True

                print(f"  [成功] {elapsed:.0f}ms")
                answer_preview = result_data.get("answer", "")[:80]
                print(f"  答案预览: {answer_preview}...")

            except httpx.HTTPStatusError as e:
                elapsed = (time.time() - start_time) * 1000
                error_detail = ""
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text

                query_result["error"] = {
                    "status_code": e.response.status_code,
                    "detail": error_detail,
                }
                query_result["timing_ms"] = elapsed
                query_result["success"] = False

                print(f"  [HTTP错误] {e.response.status_code} - {elapsed:.0f}ms")

            except httpx.RequestError as e:
                elapsed = (time.time() - start_time) * 1000
                query_result["error"] = {
                    "type": type(e).__name__,
                    "message": str(e),
                }
                query_result["timing_ms"] = elapsed
                query_result["success"] = False

                print(f"  [请求错误] {type(e).__name__}: {str(e)[:60]}...")

            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                query_result["error"] = {
                    "type": type(e).__name__,
                    "message": str(e),
                }
                query_result["timing_ms"] = elapsed
                query_result["success"] = False

                print(f"  [错误] {type(e).__name__}: {str(e)[:60]}...")

            results.append(query_result)

            # 避免请求过快
            await asyncio.sleep(0.5)

    # 保存结果
    print(f"\n[保存结果]")
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "api_url": DIFY_API_URL,
        "total_tests": len(inputs),
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  结果已保存到: {output_path}")

    # 打印摘要
    print(f"\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)

    success_count = sum(1 for r in results if r.get("success", False))
    total_time = sum(r.get("timing_ms", 0) for r in results)
    avg_time = total_time / len(results) if results else 0

    print(f"成功: {success_count}/{len(inputs)}")
    print(f"总耗时: {total_time:.0f}ms")
    print(f"平均耗时: {avg_time:.0f}ms")

    # 统计错误类型
    errors = [r.get("error", {}) for r in results if not r.get("success", False)]
    if errors:
        print(f"\n错误统计:")
        for error in errors:
            if error.get("status_code"):
                print(f"  HTTP {error['status_code']}")
            elif error.get("type"):
                print(f"  {error['type']}")

    print(f"\n结果文件: {output_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试 Dify 工作流 API")
    parser.add_argument(
        "--questions",
        default="questions/fianl_version_qa.jsonl",
        help="问题文件路径",
    )
    parser.add_argument(
        "--output",
        default="dify_workflow_test_results.json",
        help="输出结果文件路径",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="测试问题数量限制（0表示全部）",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(test_dify_workflow(
        questions_file=args.questions,
        output_file=args.output,
        limit=args.limit,
    ))
    sys.exit(exit_code)
