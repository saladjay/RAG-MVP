"""
RAG 服务本地 Milvus 评估测试

功能：
1. 读取 questions/fianl_version_qa.jsonl 测试问题
2. 使用本地 Milvus 进行向量检索
3. 使用 LLM 生成回答（GLM-4.5-air via LiteLLM）
4. 使用 LLM 判断回答是否与预期答案接近
5. 生成完整的评估报告和准确率统计
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service
from rag_service.inference.gateway import get_gateway, get_glm_gateway
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class LocalMilvusEvaluationTest:
    """使用本地 Milvus 的 RAG 评估测试"""

    def __init__(
        self,
        questions_file: Path,
        output_dir: Path,
        milvus_uri: str = "http://localhost:19530",
        collection_name: str = "knowledge_base",
        limit: int = 0,
        start: int = 1,
    ):
        self.questions_file = questions_file
        self.output_dir = output_dir
        self.milvus_uri = milvus_uri
        self.collection_name = collection_name
        self.limit = limit
        self.start = start

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

    async def retrieve_from_milvus(
        self, query: str, top_k: int = 10
    ) -> Dict[str, Any]:
        """从本地 Milvus 检索相关文档"""

        start_time = time.time()

        try:
            # 初始化
            client = MilvusClient(uri=self.milvus_uri)
            embedding_service = await get_http_embedding_service()

            # 生成查询向量
            query_vector = await embedding_service.embed_text(query)
            embed_time = (time.time() - start_time) * 1000

            # 搜索 Milvus
            search_start = time.time()
            search_results = client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
            )
            search_time = (time.time() - search_start) * 1000

            hits = search_results[0]

            # 格式化结果
            chunks = []
            for hit in hits:
                entity = hit["entity"]
                chunks.append({
                    "distance": hit["distance"],
                    "score": hit["distance"],  # 标准化为 score
                    "formTitle": entity.get("formTitle", ""),
                    "fileContent": entity.get("fileContent", ""),
                    "document_id": entity.get("document_id", ""),
                    "chunk_index": entity.get("chunk_index", 0),
                })

            return {
                "success": True,
                "chunks": chunks,
                "timing": {
                    "embed_ms": embed_time,
                    "search_ms": search_time,
                    "total_ms": embed_time + search_time,
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def generate_answer(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用 LLM 生成回答"""

        try:
            # 构建上下文
            context_parts = []
            for i, chunk in enumerate(chunks[:5], 1):
                content = chunk.get("fileContent", "")
                title = chunk.get("formTitle", "")
                context_parts.append(f"[文档{i}] {title}\n{content}\n")

            context = "\n".join(context_parts)

            # 构建提示
            prompt = f"""你是一个专业的文档问答助手。请根据以下文档内容回答用户的问题。

# 用户问题
{query}

# 参考文档
{context}

# 回答要求
1. 请使用中文回答
2. 回答要准确、简洁，直接回答问题
3. 如果文档中没有相关信息，请明确说明"根据提供的文档，没有找到相关信息"
4. 如果能找到答案，请引用文档中的具体内容

# 回答："""

            start_time = time.time()

            # 使用直接 GLM Gateway（避免 LiteLLM 的 thinking_mode 问题）
            gateway = await get_glm_gateway()
            result = await gateway.acomplete(
                prompt=prompt,
                max_tokens=2048,  # 增加 max_tokens 以避免答案被截断
                temperature=0.3,
            )

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "answer": result.text.strip(),
                "timing": {
                    "generate_ms": latency_ms,
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def evaluate_with_llm(
        self, query: str, generated_answer: str, expected_answers: List[str]
    ) -> Dict[str, Any]:
        """使用 LLM 评估生成的答案"""

        expected_str = "\n".join([f"- {a}" for a in expected_answers[:3]])

        # 简化评估提示以减少 token 使用
        prompt = f"""比较答案与预期，判断是否正确。

问题: {query}

生成答案: {generated_answer}

预期答案（任一匹配即可）:
{expected_str}

判断标准: 核心信息一致即为正确，措辞差异不影响。

输出JSON: {{"is_correct": true/false, "confidence": 0.0-1.0, "reason": "简短理由"}}"""

        try:
            # 使用直接 GLM Gateway
            gateway = await get_glm_gateway()
            result = await gateway.acomplete(
                prompt=prompt,
                max_tokens=2048,  # 进一步增加 max_tokens 以确保 JSON 完整
                temperature=0.5,
            )

            response_text = result.text.strip()

            # 检查空响应
            if not response_text or len(response_text) < 10:
                raise ValueError(f"Empty or too short response: '{response_text}'")

            # 尝试提取 JSON
            cleaned_text = response_text
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

            # 更健壮的 JSON 解析
            evaluation = json.loads(cleaned_text)

            # 验证必要字段
            if "is_correct" not in evaluation:
                evaluation["is_correct"] = False
                evaluation["reason"] = "Missing is_correct field"
            if "confidence" not in evaluation:
                evaluation["confidence"] = 0.0
            if "reason" not in evaluation:
                evaluation["reason"] = "Missing reason field"

            return {
                "success": True,
                "evaluation": evaluation,
            }

        except json.JSONDecodeError as e:
            # JSON 解析失败，尝试手动提取字段
            logger.warning(f"JSON decode error: {e}, attempting manual extraction")
            try:
                import re
                is_correct_match = re.search(r'"is_correct"\s*:\s*(true|false)', cleaned_text)
                confidence_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', cleaned_text)
                reason_match = re.search(r'"reason"\s*:\s*"([^"]*)"', cleaned_text)

                evaluation = {
                    "is_correct": bool(is_correct_match) if is_correct_match else False,
                    "confidence": float(confidence_match.group(1)) if confidence_match else 0.0,
                    "reason": reason_match.group(1) if reason_match else "Could not parse",
                }
                return {
                    "success": True,
                    "evaluation": evaluation,
                    "parsed_manually": True,
                }
            except:
                raise  # 如果手动提取也失败，抛出原始异常

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
        """简单的关键词匹配评估"""
        generated_lower = generated_answer.lower()

        best_match_score = 0
        for expected in expected_answers:
            expected_lower = expected.lower()
            if expected_lower in generated_lower or generated_lower in expected_lower:
                match_score = len(expected_lower) / max(len(generated_lower), 1)
                if match_score > best_match_score:
                    best_match_score = match_score

        is_correct = best_match_score > 0.3

        return {
            "is_correct": is_correct,
            "confidence": min(best_match_score + 0.5, 1.0),
            "reason": f"关键词匹配: {best_match_score:.2f}",
            "method": "simple_matching",
        }

    def save_detailed_log(self, log_entry: Dict[str, Any]):
        """保存详细日志"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"milvus_eval_log_{timestamp}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    async def run_test(self):
        """运行评估测试"""

        print("=" * 80)
        print("本地 Milvus RAG 评估测试")
        print("=" * 80)
        print(f"问题文件: {self.questions_file}")
        print(f"输出目录: {self.output_dir}")
        print(f"Milvus: {self.milvus_uri}")
        print(f"集合: {self.collection_name}")
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
                        print(f"  [警告] 第 {line_num} 行解析失败: {e}")

        except FileNotFoundError:
            print(f"  [错误] 文件不存在: {self.questions_file}")
            return

        if not questions:
            print(f"  [错误] 没有找到有效的问题")
            return

        if self.limit > 0:
            questions = questions[:self.limit]
            print(f"  读取到 {len(questions)} 个问题 (限制模式)")
        else:
            print(f"  读取到 {len(questions)} 个问题 (完整模式)")

        # 应用起始位置
        if self.start > 1:
            questions = questions[self.start - 1:]
            print(f"  从第 {self.start} 条开始测试")
        elif self.start < 1:
            print(f"  [警告] 起始位置必须 >= 1，已自动调整为 1")
            self.start = 1

        # 检查 Milvus 连接
        print(f"\n[2] 检查 Milvus 连接")
        try:
            client = MilvusClient(uri=self.milvus_uri)
            if not client.has_collection(self.collection_name):
                print(f"  [错误] 集合不存在: {self.collection_name}")
                return

            stats = client.get_collection_stats(self.collection_name)
            print(f"  集合存在，行数: {stats.get('row_count', 0)}")
        except Exception as e:
            print(f"  [错误] Milvus 连接失败: {e}")
            return

        # 运行测试
        print(f"\n[3] 执行 RAG 测试")
        print("-" * 80)

        for offset, question_data in enumerate(questions):
            idx = self.start + offset  # 实际索引
            title = question_data["title"]
            query = question_data["query"]
            expected_answers = question_data["expected_answers"]

            total_count = self.limit if self.limit > 0 else len(questions) + self.start - 1
            print(f"\n[{idx}/{total_count}] {query[:60]}...")

            # 准备日志条目
            log_entry = {
                "index": idx,
                "title": title,
                "query": query,
                "expected_answers": expected_answers,
                "timestamp": datetime.now().isoformat(),
            }

            try:
                # 1. 检索
                print(f"  [1] 检索中...", end="", flush=True)
                retrieve_result = await self.retrieve_from_milvus(query, top_k=10)

                if not retrieve_result["success"]:
                    print(f"\r  [ERROR] 检索失败: {retrieve_result.get('error', 'Unknown')}")
                    log_entry["error"] = retrieve_result.get("error")
                    log_entry["success"] = False
                    self.stats["error"] += 1
                    self.save_detailed_log(log_entry)
                    continue

                chunks = retrieve_result["chunks"]
                retrieve_timing = retrieve_result["timing"]

                # 显示顶部结果
                if chunks:
                    top_title = chunks[0].get("formTitle", "")[:40]
                    top_score = chunks[0].get("score", 0)
                    print(f"\r  [OK] 检索到 {len(chunks)} 个文档 | 顶部: {top_title}... ({top_score:.4f})")
                else:
                    print(f"\r  [WARN] 未检索到文档")

                log_entry["retrieval"] = {
                    "chunk_count": len(chunks),
                    "top_chunks": [
                        {
                            "title": c.get("formTitle", ""),
                            "score": c.get("score", 0),
                            "content_preview": c.get("fileContent", "")[:100],
                        }
                        for c in chunks[:3]
                    ],
                    "timing": retrieve_timing,
                }

                # 2. 生成答案
                print(f"  [2] 生成中...", end="", flush=True)
                generate_result = await self.generate_answer(query, chunks)

                if not generate_result["success"]:
                    print(f"\r  [ERROR] 生成失败: {generate_result.get('error', 'Unknown')}")
                    log_entry["error"] = generate_result.get("error")
                    log_entry["success"] = False
                    self.stats["error"] += 1
                    self.save_detailed_log(log_entry)
                    continue

                answer = generate_result["answer"]
                generate_timing = generate_result["timing"]

                print(f"\r  [OK] 回答: {answer[:60]}...")
                log_entry["answer"] = answer
                log_entry["generation_timing"] = generate_timing

                # 3. 评估
                print(f"  [3] 评估中...", end="", flush=True)
                eval_result = await self.evaluate_with_llm(
                    query=query,
                    generated_answer=answer,
                    expected_answers=expected_answers
                )

                if eval_result["success"]:
                    evaluation = eval_result["evaluation"]
                    is_correct = evaluation.get("is_correct", False)
                    confidence = evaluation.get("confidence", 0)
                    reason = evaluation.get("reason", "")

                    status = "[PASS]" if is_correct else "[FAIL]"
                    print(f"\r  [EVAL] {status} {'正确' if is_correct else '错误'} (置信度: {confidence:.2f})")
                    print(f"         理由: {reason}")

                    if is_correct:
                        self.stats["correct"] += 1
                    else:
                        self.stats["incorrect"] += 1

                    self.stats["evaluation_scores"].append(confidence)
                    log_entry["evaluation"] = evaluation
                    log_entry["evaluation_method"] = "llm"

                else:
                    fallback = eval_result.get("fallback", {})
                    is_correct = fallback.get("is_correct", False)
                    reason = fallback.get("reason", "")

                    status = "[PASS]" if is_correct else "[FAIL]"
                    print(f"\r  [EVAL] {status} {'正确' if is_correct else '错误'} (后备方案)")
                    print(f"         理由: {reason}")

                    if is_correct:
                        self.stats["correct"] += 1
                    else:
                        self.stats["incorrect"] += 1

                    log_entry["evaluation"] = fallback
                    log_entry["evaluation_method"] = "fallback"

                log_entry["success"] = True
                self.stats["total"] += 1

            except Exception as e:
                print(f"\r  [ERROR] {str(e)[:100]}")
                log_entry["error"] = str(e)
                log_entry["success"] = False
                self.stats["error"] += 1
                self.stats["total"] += 1

            # 保存日志到内存和文件
            self.detailed_logs.append(log_entry)
            self.save_detailed_log(log_entry)

        # 生成报告
        self.generate_report()

    def generate_report(self):
        """生成评估报告"""

        print(f"\n" + "=" * 80)
        print("评估报告")
        print("=" * 80)

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
        print(f"  错误: {error}")
        print(f"  准确率: {accuracy:.2f}%")
        print(f"  平均置信度: {avg_confidence:.2f}")

        # 保存完整报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_config": {
                "questions_file": str(self.questions_file),
                "milvus_uri": self.milvus_uri,
                "collection_name": self.collection_name,
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

        report_file = self.output_dir / f"milvus_eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n报告已保存:")
        print(f"  完整报告: {report_file}")
        print(f"  详细日志: {self.output_dir}/milvus_eval_log_*.jsonl")

        print("=" * 80)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="RAG 服务本地 Milvus 评估测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试前 10 个问题（默认）
  uv run python test_milvus_evaluation.py

  # 测试前 100 个问题
  uv run python test_milvus_evaluation.py --limit 100

  # 测试全部问题
  uv run python test_milvus_evaluation.py --limit 0

  # 从第 543 条继续测试（中断后恢复）
  uv run python test_milvus_evaluation.py --limit 0 --start 543

  # 从第 100 条开始，测试 50 条
  uv run python test_milvus_evaluation.py --limit 50 --start 100

  # 指定输出目录
  uv run python test_milvus_evaluation.py --limit 50 --output-dir custom_results

  # 使用自定义问题文件
  uv run python test_milvus_evaluation.py --questions-file custom_questions.jsonl

  # 完整配置
  uv run python test_milvus_evaluation.py --limit 0 --start 543 --output-dir custom_results --milvus-uri http://localhost:19530 --collection-name knowledge_base
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="限制测试问题数量（0 表示测试全部问题，默认: 10）"
    )

    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="从第几条开始测试（默认: 1，从中断处继续时指定）"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("milvus_evaluation_results"),
        help="输出目录路径（默认: milvus_evaluation_results）"
    )

    parser.add_argument(
        "--questions-file",
        type=Path,
        default=Path("questions/fianl_version_qa.jsonl"),
        help="问题文件路径（默认: questions/fianl_version_qa.jsonl）"
    )

    parser.add_argument(
        "--milvus-uri",
        type=str,
        default="http://localhost:19530",
        help="Milvus 服务地址（默认: http://localhost:19530）"
    )

    parser.add_argument(
        "--collection-name",
        type=str,
        default="knowledge_base",
        help="Milvus 集合名称（默认: knowledge_base）"
    )

    return parser.parse_args()


async def main():
    """主函数"""

    args = parse_args()

    questions_file = args.questions_file
    output_dir = args.output_dir
    milvus_uri = args.milvus_uri
    collection_name = args.collection_name
    limit = args.limit
    start = args.start

    print("=" * 80)
    print("RAG 服务本地 Milvus 评估测试")
    print("=" * 80)
    print(f"配置信息:")
    print(f"  问题文件: {questions_file}")
    print(f"  输出目录: {output_dir}")
    print(f"  Milvus: {milvus_uri}")
    print(f"  集合: {collection_name}")
    print(f"  起始位置: {start}")
    print(f"  限制数量: {limit if limit > 0 else '全部'}")
    print("=" * 80)

    tester = LocalMilvusEvaluationTest(
        questions_file=questions_file,
        output_dir=output_dir,
        milvus_uri=milvus_uri,
        collection_name=collection_name,
        limit=limit,
        start=start,
    )

    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())
