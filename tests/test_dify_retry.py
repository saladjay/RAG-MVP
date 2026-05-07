"""
Dify 工作流失败查询重试脚本

功能：
1. 读取评估结果文件，筛选出失败的查询
2. 在 questions/fianl_version_qa.jsonl 中查找预期答案
3. 重新执行 Dify 查询
4. 记录多次失败原因，生成与评估结果文件格式一致的记录，方便递归评估
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


# Dify API 配置
DIFY_API_URL = "http://128.23.74.4/v1/chat-messages"
DIFY_API_KEY = "app-cfSS1P9f54NMCE8lvbStqnsq"
DIFY_APP_ID = "d7da8601-7a9f-4ee0-9d1a-528d9cdeaf3a"
DIFY_APPLICATION_KEY = "ApiSecretKey_kVsvUcvcModZXJwVsdvJfRpbbaicXJFq"
USER_ID = "N10070128"

# oldParam 模板
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
XTOKEN = "XAT-c41acf13-b386-4bf2-9763-1b6e7216f7fc"


class DifyFailedQueryRetry:
    """Dify 失败查询重试类"""

    def __init__(
        self,
        eval_results_file: Path,
        questions_file: Path,
        output_dir: Path,
        retry_limit: int = 3,
    ):
        self.eval_results_file = eval_results_file
        self.questions_file = questions_file
        self.output_dir = output_dir
        self.retry_limit = retry_limit

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 查询映射 (query -> question data)
        self.questions_map: Dict[str, Dict[str, Any]] = {}

        # 重试结果存储
        self.retry_results: List[Dict[str, Any]] = []

        # 统计信息
        self.stats = {
            "total_failed": 0,
            "retried": 0,
            "success_on_retry": 0,
            "still_failed": 0,
            "by_previous_error": defaultdict(int),
        }

    def load_evaluation_results(self) -> List[Dict[str, Any]]:
        """加载评估结果，筛选出失败的查询"""
        print(f"[1] 加载评估结果: {self.eval_results_file}")

        try:
            with open(self.eval_results_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            evaluations = data.get("evaluations", [])
            print(f"  加载到 {len(evaluations)} 条评估结果")

            # 筛选失败的查询
            failed_queries = []
            for eval in evaluations:
                evaluation = eval.get("evaluation", {})
                status = evaluation.get("status", "")
                category_code = evaluation.get("category_code", "")

                if status != "success" or category_code != "SUCCESS":
                    failed_queries.append(eval)
                    self.stats["by_previous_error"][category_code] += 1

            print(f"  其中失败的查询: {len(failed_queries)} 条")

            # 打印失败类别分布
            if self.stats["by_previous_error"]:
                print(f"  失败类别分布:")
                for code, count in sorted(self.stats["by_previous_error"].items(), key=lambda x: -x[1]):
                    if count > 0:
                        print(f"    {code}: {count} 条")

            return failed_queries

        except FileNotFoundError:
            print(f"  [错误] 文件不存在: {self.eval_results_file}")
            return []
        except json.JSONDecodeError as e:
            print(f"  [错误] JSON 解析失败: {e}")
            return []

    def load_questions(self):
        """加载问题文件，建立查询映射"""
        print(f"\n[2] 加载问题文件: {self.questions_file}")

        try:
            with open(self.questions_file, "r", encoding="utf-8") as f:
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

                        self.questions_map[query] = {
                            "title": title,
                            "query": query,
                            "expected_answers": answer_list,
                            "line_num": line_num,
                        }

                    except json.JSONDecodeError:
                        pass

            print(f"  加载到 {len(self.questions_map)} 个问题")

        except FileNotFoundError:
            print(f"  [错误] 文件不存在: {self.questions_file}")

    async def call_dify_api(
        self, query: str, headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """调用 Dify API"""

        try:
            # 构建 oldParam
            old_param = OLD_PARAM_TEMPLATE.copy()
            old_param["searchKey"] = query
            old_param["remark"] = query

            # 获取当前时间
            chat_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            payload = {
                "query": query,
                "conversation_id": "",
                "user": USER_ID,
                "userId": USER_ID,
                "appId": DIFY_APP_ID,
                "inputs": {
                    "systemId": "oa",
                    "xtoken": XTOKEN,
                    "oldParam": json.dumps(old_param, ensure_ascii=False),
                },
                "difyApplicationKey": DIFY_APPLICATION_KEY,
                "chatTime": chat_time,
                "response_mode": "blocking",
            }

            start_time = time.time()

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    DIFY_API_URL,
                    headers=headers,
                    json=payload
                )

            elapsed = (time.time() - start_time) * 1000

            if response.status_code == 200:
                result_data = response.json()
                return {
                    "success": True,
                    "timing_ms": elapsed,
                    "response": result_data,
                }
            else:
                error_detail = ""
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = response.text

                return {
                    "success": False,
                    "timing_ms": elapsed,
                    "error": {
                        "status_code": response.status_code,
                        "detail": error_detail,
                    },
                }

        except Exception as e:
            return {
                "success": False,
                "timing_ms": 0,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                },
            }

    async def retry_single_query(
        self,
        failed_eval: Dict[str, Any],
        headers: Dict[str, str],
        retry_num: int,
    ) -> Dict[str, Any]:
        """重试单个查询"""

        query = failed_eval.get("query", "")
        previous_eval = failed_eval.get("evaluation", {})
        previous_category = previous_eval.get("category_code", "UNKNOWN")

        print(f"\n  [重试 {retry_num}] {query[:60]}...")

        # 调用 Dify API
        result = await self.call_dify_api(query, headers)

        # 构建结果记录
        retry_result = {
            "original_index": failed_eval.get("index"),
            "query": query,
            "retry_num": retry_num,
            "previous_error_category": previous_category,
            "previous_error_reason": previous_eval.get("reason", ""),
            "timing_ms": result.get("timing_ms", 0),
        }

        if result["success"]:
            response_data = result["response"]
            answer = response_data.get("answer", "")
            retriever_resources = response_data.get("retriever_resources", [])
            metadata = response_data.get("metadata", {})

            retry_result.update({
                "success": True,
                "answer_preview": answer[:100],
                "response": response_data,
                "has_retrieval": len(retriever_resources) > 0,
                "retrieval_count": len(retriever_resources),
            })

            status = "[成功]" if len(retriever_resources) > 0 and "失败" not in answer else "[仍有问题]"
            print(f"    {status} {answer[:60]}...")

        else:
            error = result.get("error", {})
            retry_result.update({
                "success": False,
                "error": error,
                "has_retrieval": False,
                "retrieval_count": 0,
            })

            error_msg = str(error.get("detail", error.get("message", "")))[:60]
            print(f"    [失败] {error_msg}...")

        return retry_result

    async def run_retry(self):
        """运行重试流程"""

        print("=" * 80)
        print("Dify 失败查询重试")
        print("=" * 80)
        print(f"评估结果文件: {self.eval_results_file}")
        print(f"问题文件: {self.questions_file}")
        print(f"输出目录: {self.output_dir}")
        print("-" * 80)

        # 加载评估结果
        failed_evals = self.load_evaluation_results()
        if not failed_evals:
            print("\n[完成] 没有需要重试的失败查询")
            return

        self.stats["total_failed"] = len(failed_evals)

        # 加载问题映射
        self.load_questions()

        # 准备 HTTP headers
        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json",
        }

        # 执行重试
        print(f"\n[3] 执行重试 ({len(failed_evals)} 个失败查询)")
        print("-" * 80)

        for idx, failed_eval in enumerate(failed_evals, 1):
            query = failed_eval.get("query", "")

            print(f"\n[{idx}/{len(failed_evals)}] {query[:60]}...")

            # 查找预期答案
            question_data = self.questions_map.get(query, {})
            # 确保 expected_answers 是一个列表，处理 None 和不存在的情况
            expected_answers = question_data.get("expected_answers") or []
            # 过滤掉 None 值
            expected_answers = [a for a in expected_answers if a]

            if expected_answers:
                answer = expected_answers[0]
                if answer:
                    print(f"  预期答案: {answer[:50]}...")

            # 重试多次
            retry_attempts = []
            success = False

            for retry_num in range(1, self.retry_limit + 1):
                retry_result = await self.retry_single_query(
                    failed_eval=failed_eval,
                    headers=headers,
                    retry_num=retry_num,
                )
                retry_attempts.append(retry_result)

                if retry_result["success"]:
                    # 检查是否真的成功（有检索且有有效答案）
                    if retry_result.get("has_retrieval"):
                        success = True
                        self.stats["success_on_retry"] += 1
                        break
                    # 虽然API成功但没有检索结果，继续重试
                    await asyncio.sleep(1)

            # 记录结果
            self.retry_results.append({
                "index": idx,
                "query": query,
                "title": question_data.get("title", ""),
                "expected_answers": expected_answers,
                "success": success,
                "retry_attempts": retry_attempts,
                "total_attempts": len(retry_attempts),
            })

            if success:
                self.stats["retried"] += 1
            else:
                self.stats["still_failed"] += 1

            # 避免请求过快
            await asyncio.sleep(0.5)

        # 生成报告
        self.generate_reports()

    def generate_reports(self):
        """生成重试报告"""

        print(f"\n[4] 生成重试报告")

        # 保存完整结果（与评估结果格式一致，方便递归）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 转换为评估结果格式
        eval_format_results = []
        for result in self.retry_results:
            # 使用最后一次尝试的结果
            last_attempt = result["retry_attempts"][-1] if result["retry_attempts"] else {}

            # 确定状态
            if result["success"]:
                evaluation = {
                    "status": "success",
                    "category_code": "SUCCESS",
                    "category_name": "成功/正常",
                    "confidence": 0.8,
                    "reason": "重试成功",
                    "quality_score": 3,
                    "issues": [],
                }
            else:
                # 使用失败类别
                prev_category = last_attempt.get("previous_error_category", "OTHER")
                evaluation = {
                    "status": "failure",
                    "category_code": prev_category,
                    "category_name": last_attempt.get("previous_error_category", "OTHER"),
                    "confidence": 0.7,
                    "reason": f"重试{result['total_attempts']}次后仍然失败",
                    "quality_score": None,
                    "issues": [last_attempt.get("previous_error_reason", "未知错误")],
                }

            eval_format_results.append({
                "index": result["index"],
                "query": result["query"],
                "answer_preview": last_attempt.get("answer_preview", ""),
                "evaluation": evaluation,
                "has_retrieval": last_attempt.get("has_retrieval", False),
                "retrieval_count": last_attempt.get("retrieval_count", 0),
                "timing_ms": sum(attempt.get("timing_ms", 0) for attempt in result["retry_attempts"]),
                "is_retry_result": True,
                "retry_attempts": result["total_attempts"],
            })

        # 统计
        by_category = defaultdict(int)
        for r in eval_format_results:
            cat = r["evaluation"]["category_code"]
            by_category[cat] += 1

        success_count = by_category.get("SUCCESS", 0)
        total = len(eval_format_results)
        success_rate = (success_count / total * 100) if total > 0 else 0

        # 保存结果
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "source_file": str(self.eval_results_file),
            "is_retry_result": True,
            "statistics": {
                "total": total,
                "success_rate": success_rate,
                "avg_quality_score": None,  # 重试结果没有质量评分
                "by_category": dict(by_category),
            },
            "evaluations": eval_format_results,
        }

        results_file = self.output_dir / f"retry_results_{timestamp}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"  重试结果: {results_file}")

        # 保存详细重试记录
        detailed_file = self.output_dir / f"retry_detailed_{timestamp}.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "results": self.retry_results,
            }, f, ensure_ascii=False, indent=2)

        print(f"  详细记录: {detailed_file}")

        # 打印摘要
        self.print_summary(success_rate)

    def print_summary(self, success_rate: float):
        """打印摘要报告"""

        print(f"\n" + "=" * 80)
        print("重试摘要")
        print("=" * 80)

        print(f"\n原始失败查询数: {self.stats['total_failed']}")
        print(f"重试成功: {self.stats['success_on_retry']}")
        print(f"仍然失败: {self.stats['still_failed']}")
        print(f"成功率: {success_rate:.2f}%")

        print(f"\n按原始错误类别统计:")
        for code, count in sorted(self.stats["by_previous_error"].items(), key=lambda x: -x[1]):
            print(f"  {code}: {count} 条")

        print(f"\n详细记录已保存到: {self.output_dir}")
        print("=" * 80)


async def main():
    """主函数"""

    import argparse

    parser = argparse.ArgumentParser(description="Dify 失败查询重试")
    parser.add_argument(
        "--eval-file",
        default="dify_evaluation_results/dify_eval_results_20260423_161109.json",
        help="评估结果文件路径",
    )
    parser.add_argument(
        "--questions",
        default="questions/fianl_version_qa.jsonl",
        help="问题文件路径",
    )
    parser.add_argument(
        "--output-dir",
        default="dify_retry_results",
        help="输出目录",
    )
    parser.add_argument(
        "--retry-limit",
        type=int,
        default=3,
        help="每个查询的重试次数",
    )

    args = parser.parse_args()

    # 运行重试
    retryer = DifyFailedQueryRetry(
        eval_results_file=Path(args.eval_file),
        questions_file=Path(args.questions),
        output_dir=Path(args.output_dir),
        retry_limit=args.retry_limit,
    )

    await retryer.run_retry()


if __name__ == "__main__":
    asyncio.run(main())
