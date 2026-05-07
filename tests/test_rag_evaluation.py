"""
RAG 服务完整评估测试

功能：
1. 读取 questions/fianl_version_qa.jsonl 测试问题
2. 调用 RAG QA Pipeline 获取回答
3. 记录每个节点的输入输出
4. 使用 LLM 判断回答是否与预期答案接近
5. 生成完整的评估报告和准确率统计
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


class RAGEvaluationTest:
    """RAG 评估测试类"""

    def __init__(
        self,
        questions_file: Path,
        output_dir: Path,
        base_url: str = "http://localhost:8000",
        limit: int = 0,  # 0 表示测试全部
    ):
        self.questions_file = questions_file
        self.output_dir = output_dir
        self.base_url = base_url
        self.limit = limit

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 测试结果存储
        self.results: List[Dict[str, Any]] = []
        self.detailed_logs: List[Dict[str, Any]] = []

        # 统计信息
        self.stats = {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "error": 0,
            "evaluation_scores": [],
        }

    def parse_question_line(self, line_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析单行问题数据"""
        title_question = line_data.get("title_question", "")
        answer_list = line_data.get("answear_list", [])

        # 分割标题和问题
        if "###" in title_question:
            parts = title_question.split("###", 1)
            title = parts[0].strip()
            query = parts[1].strip()
        else:
            title = title_question
            query = title_question

        return {
            "title": title,
            "query": query,
            "expected_answers": answer_list,
        }

    async def call_rag_api(
        self, query: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用 RAG API 获取回答"""
        url = f"{self.base_url}/qa/query"

        payload = {
            "query": query,
            "context": context,
            "options": {
                "top_k": 10,
                "enable_query_rewrite": True,
                "enable_hallucination_check": True,
                "stream": False,
            },
        }

        # 记录请求
        request_log = {
            "url": url,
            "payload": payload,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                start_time = time.time()
                response = await client.post(url, json=payload)
                elapsed_ms = (time.time() - start_time) * 1000

                request_log["response_status"] = response.status_code
                request_log["elapsed_ms"] = elapsed_ms

                if response.status_code == 200:
                    data = response.json()
                    request_log["response_data"] = data
                    return {
                        "success": True,
                        "data": data,
                        "log": request_log,
                    }
                else:
                    request_log["error"] = response.text
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "log": request_log,
                    }

        except Exception as e:
            request_log["error"] = str(e)
            return {
                "success": False,
                "error": str(e),
                "log": request_log,
            }

    async def evaluate_with_llm(
        self, query: str, generated_answer: str, expected_answers: List[str]
    ) -> Dict[str, Any]:
        """使用 LLM 评估生成的答案是否符合预期"""

        # 构建评估提示
        expected_str = "\n".join([f"- {a}" for a in expected_answers[:3]])

        prompt = f"""你是一个专业的答案质量评估专家。请比较生成的答案与预期答案，判断回答是否正确。

# 用户问题
{query}

# 生成的答案
{generated_answer}

# 预期答案（任一匹配即正确）
{expected_str}

# 评估要求
1. 判断生成的答案是否回答了用户的问题
2. 判断生成的答案中的关键信息是否与预期答案一致
3. 对于"找不到相关信息"的回答，如果预期答案确实不在文档中，应判定为正确

# 输出格式（严格 JSON）
{{
    "is_correct": true/false,
    "confidence": 0.0-1.0,
    "reason": "判断理由",
    "key_points_matched": ["匹配的关键点1", "关键点2"],
    "missing_points": ["缺失的关键点"]
}}

请只输出 JSON，不要有其他内容："""

        try:
            # 调用 LLM 进行评估 - 使用 gateway
            from rag_service.inference.gateway import get_http_gateway

            gateway = await get_http_gateway()
            result = await gateway.acomplete(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1,
            )

            response_text = result.text.strip()

            # 尝试提取 JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            evaluation = json.loads(response_text)

            return {
                "success": True,
                "evaluation": evaluation,
                "raw_response": response_text,
            }

        except Exception as e:
            # 如果 LLM 评估失败，使用简单的关键词匹配
            return {
                "success": False,
                "error": str(e),
                "fallback": self._simple_evaluation(
                    generated_answer, expected_answers
                ),
            }

    def _simple_evaluation(
        self, generated_answer: str, expected_answers: List[str]
    ) -> Dict[str, Any]:
        """简单的关键词匹配评估（LLM 评估失败时的后备方案）"""
        generated_lower = generated_answer.lower()

        best_match_score = 0
        best_match_answer = ""

        for expected in expected_answers:
            expected_lower = expected.lower()
            # 简单的包含匹配
            if expected_lower in generated_lower or generated_lower in expected_lower:
                match_score = len(expected_lower) / max(len(generated_lower), 1)
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match_answer = expected

        is_correct = best_match_score > 0.3

        return {
            "is_correct": is_correct,
            "confidence": min(best_match_score + 0.5, 1.0),
            "reason": f"关键词匹配: {best_match_score:.2f}",
            "method": "simple_matching",
        }

    def save_detailed_log(self, log_entry: Dict[str, Any]):
        """保存详细日志到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"rag_eval_log_{timestamp}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    async def run_test(self):
        """运行完整的评估测试"""

        print("=" * 80)
        print("RAG 服务评估测试")
        print("=" * 80)
        print(f"问题文件: {self.questions_file}")
        print(f"输出目录: {self.output_dir}")
        print(f"API 地址: {self.base_url}")
        print("-" * 80)

        # 读取问题文件
        print("\n[1] 读取测试问题")
        questions = []

        try:
            with open(self.questions_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        parsed = self.parse_question_line(data)
                        parsed["line_num"] = line_num
                        questions.append(parsed)
                    except json.JSONDecodeError as e:
                        print(f"  [警告] 第 {line_num} 行 JSON 解析失败: {e}")

        except FileNotFoundError:
            print(f"  [错误] 文件不存在: {self.questions_file}")
            return

        if not questions:
            print(f"  [错误] 没有找到有效的问题")
            return

        # 限制测试数量
        if self.limit > 0:
            questions = questions[:self.limit]
            print(f"  读取到 {len(questions)} 个问题 (限制模式)")
        else:
            print(f"  读取到 {len(questions)} 个问题 (完整模式)")

        # 运行测试
        print(f"\n[2] 执行 RAG 查询和评估")
        print("-" * 80)

        for idx, question_data in enumerate(questions, 1):
            title = question_data["title"]
            query = question_data["query"]
            expected_answers = question_data["expected_answers"]

            print(f"\n[{idx}/{len(questions)}] {query[:60]}...")

            # 调用 RAG API
            result = await self.call_rag_api(
                query=query,
                context={
                    "company_id": "N000131",
                    "file_type": "PublicDocReceive"
                }
            )

            # 准备日志条目
            log_entry = {
                "index": idx,
                "title": title,
                "query": query,
                "expected_answers": expected_answers,
                "timestamp": datetime.now().isoformat(),
            }

            if result["success"]:
                data = result["data"]
                generated_answer = data.get("answer", "")
                sources = data.get("sources", [])
                metadata = data.get("metadata", {})
                timing = metadata.get("timing_ms", {})

                log_entry["rag_response"] = {
                    "answer": generated_answer,
                    "sources_count": len(sources),
                    "sources": [
                        {
                            "document_name": s.get("document_name", ""),
                            "score": s.get("score", 0),
                            "content_preview": s.get("content_preview", ""),
                        }
                        for s in sources[:3]
                    ],
                    "timing": timing,
                    "hallucination_status": data.get("hallucination_status", {}),
                    "query_rewritten": metadata.get("query_rewritten", False),
                }

                print(f"  [OK] 回答: {generated_answer[:80]}...")
                print(f"       来源: {len(sources)} 个文档 | 时长: {timing.get('total_ms', 0):.0f}ms")

                # LLM 评估
                print(f"  [EVAL] 评估中...", end="", flush=True)
                evaluation_result = await self.evaluate_with_llm(
                    query=query,
                    generated_answer=generated_answer,
                    expected_answers=expected_answers
                )

                if evaluation_result["success"]:
                    evaluation = evaluation_result["evaluation"]
                    is_correct = evaluation.get("is_correct", False)
                    confidence = evaluation.get("confidence", 0)

                    log_entry["evaluation"] = evaluation
                    log_entry["evaluation_method"] = "llm"

                    status = "[PASS]" if is_correct else "[FAIL]"
                    print(f"\r  [EVAL] {status} {'正确' if is_correct else '错误'} (置信度: {confidence:.2f})")

                    if is_correct:
                        self.stats["correct"] += 1
                    else:
                        self.stats["incorrect"] += 1

                    self.stats["evaluation_scores"].append(confidence)

                else:
                    # 使用后备评估
                    fallback = evaluation_result.get("fallback", {})
                    is_correct = fallback.get("is_correct", False)

                    log_entry["evaluation"] = fallback
                    log_entry["evaluation_method"] = "fallback"
                    log_entry["evaluation_error"] = evaluation_result.get("error")

                    status = "[PASS]" if is_correct else "[FAIL]"
                    print(f"\r  [EVAL] {status} {'正确' if is_correct else '错误'} (后备方案)")

                    if is_correct:
                        self.stats["correct"] += 1
                    else:
                        self.stats["incorrect"] += 1

                log_entry["success"] = True

            else:
                # API 调用失败
                error = result.get("error", "Unknown error")
                log_entry["error"] = error
                log_entry["success"] = False
                log_entry["request_log"] = result.get("log", {})

                print(f"  [ERROR] API 错误: {error[:100]}...")
                self.stats["error"] += 1

            self.stats["total"] += 1

            # 保存详细日志
            self.detailed_logs.append(log_entry)
            self.save_detailed_log(log_entry)

        # 生成最终报告
        self.generate_report()

    def generate_report(self):
        """生成评估报告"""

        print(f"\n" + "=" * 80)
        print("评估报告")
        print("=" * 80)

        # 计算准确率
        total = self.stats["total"]
        correct = self.stats["correct"]
        incorrect = self.stats["incorrect"]
        error = self.stats["error"]

        accuracy = (correct / total * 100) if total > 0 else 0
        scores = self.stats["evaluation_scores"]
        avg_confidence = sum(scores) / len(scores) if scores else 0

        print(f"\n总体统计:")
        print(f"  总测试数: {total}")
        print(f"  正确: {correct}")
        print(f"  错误: {incorrect}")
        print(f"  API 错误: {error}")
        print(f"  准确率: {accuracy:.2f}%")
        print(f"  平均置信度: {avg_confidence:.2f}")

        # 保存完整报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_config": {
                "questions_file": str(self.questions_file),
                "base_url": self.base_url,
                "limit": self.limit,
            },
            "statistics": {
                "total": total,
                "correct": correct,
                "incorrect": incorrect,
                "error": error,
                "accuracy": accuracy,
                "avg_confidence": avg_confidence,
            },
            "detailed_logs": self.detailed_logs,
        }

        report_file = self.output_dir / f"rag_eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n报告已保存:")
        print(f"  完整报告: {report_file}")
        print(f"  详细日志: {self.output_dir}/rag_eval_log_*.jsonl")

        # 打印错误案例
        if incorrect > 0:
            print(f"\n错误案例分析:")
            print("-" * 80)

            error_cases = [
                log for log in self.detailed_logs
                if not log.get("evaluation", {}).get("is_correct", True)
            ][:5]  # 只显示前5个

            for case in error_cases:
                query = case["query"]
                answer = case.get("rag_response", {}).get("answer", "")[:100]
                reason = case.get("evaluation", {}).get("reason", "")
                print(f"  问题: {query}")
                print(f"  回答: {answer}...")
                print(f"  原因: {reason}")
                print()

        print("=" * 80)


async def main():
    """主函数"""

    # 配置
    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_dir = Path("rag_evaluation_results")
    base_url = "http://localhost:8000"

    # 限制测试数量（0 表示测试全部）
    # 设置为 5 进行快速测试，设置为 0 进行完整测试
    limit = 5

    # 运行测试
    tester = RAGEvaluationTest(
        questions_file=questions_file,
        output_dir=output_dir,
        base_url=base_url,
        limit=limit,
    )

    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())
