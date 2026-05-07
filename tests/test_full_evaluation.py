"""
RAG 服务完整评估与问题分类分析

功能：
1. 读取 questions/fianl_version_qa.jsonl 测试问题（全部2445个）
2. 使用本地 Milvus 进行向量检索
3. 使用 LLM 生成回答
4. 对所有问题进行分类统计
5. 生成完整的评估报告和问题分类分析
"""

import asyncio
import json
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Set
import re

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service
from rag_service.inference.gateway import get_http_gateway
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class FullRAGEvaluation:
    """完整 RAG 评估与问题分类分析"""

    def __init__(
        self,
        questions_file: Path,
        output_dir: Path,
        milvus_uri: str = "http://localhost:19530",
        collection_name: str = "knowledge_base",
    ):
        self.questions_file = questions_file
        self.output_dir = output_dir
        self.milvus_uri = milvus_uri
        self.collection_name = collection_name

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 测试结果存储
        self.results: List[Dict[str, Any]] = []

        # 问题分类存储
        self.categories: Dict[str, List[Dict]] = defaultdict(list)

        # 统计信息
        self.stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "timing": {
                "total_embed_ms": 0,
                "total_search_ms": 0,
                "total_generate_ms": 0,
                "total_ms": 0,
            },
            "retrieval_stats": {
                "total_chunks": 0,
                "avg_top_score": 0,
                "low_score_count": 0,  # top score < 0.5
            },
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

    def classify_question(self, title: str, query: str) -> Dict[str, str]:
        """对问题进行分类"""
        categories = {
            "domain": "其他",
            "type": "其他",
            "category": "其他",
        }

        query_lower = query.lower()
        title_lower = title.lower()

        # 按领域分类
        if any(x in query_lower or x in title_lower for x in ["放假", "调休", "节假日", "春节", "国庆", "元旦", "清明", "劳动", "中秋"]):
            categories["domain"] = "节假日管理"
        elif any(x in query_lower or x in title_lower for x in ["工资", "薪酬", "待遇", "补贴", "提成", "奖金"]):
            categories["domain"] = "薪酬福利"
        elif any(x in query_lower or x in title_lower for x in ["资产", "设备", "车辆", "电脑", "电话"]):
            categories["domain"] = "资产管理"
        elif any(x in query_lower or x in title_lower for x in ["值班", "值守", "轮班"]):
            categories["domain"] = "值班管理"
        elif any(x in query_lower or x in title_lower for x in ["保险", "公积金", "社保"]):
            categories["domain"] = "保险福利"
        elif any(x in query_lower or x in title_lower for x in ["实习生", "试用", "入职"]):
            categories["domain"] = "人事管理"

        # 按问题类型分类
        if any(x in query for x in ["几天", "多久", "时长", "时间", "何时", "日期", "什么时候"]):
            categories["type"] = "时间数量类"
        elif any(x in query for x in ["是否", "有没有", "是否是", "是不是"]):
            categories["type"] = "是非判断类"
        elif any(x in query for x in ["是什么", "是什么叫", "什么叫", "哪些", "谁"]):
            categories["type"] = "事实查询类"
        elif any(x in query for x in ["怎么", "如何", "怎样"]):
            categories["type"] = "方法流程类"
        elif any(x in query for x in ["多少", "号码", "牌号", "地址"]):
            categories["type"] = "具体信息类"

        # 按问题复杂度分类
        if len(query) <= 15:
            categories["category"] = "简单查询"
        elif len(query) <= 30:
            categories["category"] = "中等查询"
        else:
            categories["category"] = "复杂查询"

        return categories

    def classify_result(self, result: Dict[str, Any]) -> Dict[str, str]:
        """对测试结果进行分类"""
        classifications = {
            "retrieval_quality": "良好",
            "answer_quality": "良好",
            "issue_type": "无",
        }

        # 检索质量分类
        if result.get("error"):
            classifications["retrieval_quality"] = "错误"
            classifications["issue_type"] = "检索错误"
        elif result.get("top_score", 1.0) < 0.5:
            classifications["retrieval_quality"] = "低分"
            classifications["issue_type"] = "检索相关性低"
        elif result.get("chunk_count", 0) < 3:
            classifications["retrieval_quality"] = "结果少"
            classifications["issue_type"] = "检索结果不足"

        # 答案质量分类
        answer = result.get("answer", "")
        if not answer:
            classifications["answer_quality"] = "无答案"
            classifications["issue_type"] = "生成失败"
        elif len(answer) > 2000:
            classifications["answer_quality"] = "冗长"
            classifications["issue_type"] = "答案过长"
        elif answer.count("根据提供的文档") > 3 or any(word in answer for word in ["文档中", "文档摘录"]):
            classifications["answer_quality"] = "模板化"
        elif "未找到" in answer or "没有" in answer or "无法" in answer:
            classifications["answer_quality"] = "无信息"
            if classifications["issue_type"] == "无":
                classifications["issue_type"] = "文档无相关内容"

        return classifications

    async def retrieve_from_milvus(
        self, query: str, top_k: int = 10
    ) -> Dict[str, Any]:
        """从本地 Milvus 检索相关文档"""

        start_time = time.time()

        try:
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
                    "score": hit["distance"],
                    "formTitle": entity.get("formTitle", ""),
                    "fileContent": entity.get("fileContent", ""),
                    "document_id": entity.get("document_id", ""),
                    "chunk_index": entity.get("chunk_index", 0),
                })

            return {
                "success": True,
                "chunks": chunks,
                "top_score": chunks[0]["score"] if chunks else 0,
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
                "top_score": 0,
            }

    async def generate_answer(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用 LLM 生成回答"""

        try:
            # 构建上下文 - 只取前3个chunk以减少重复
            context_parts = []
            for i, chunk in enumerate(chunks[:3], 1):
                content = chunk.get("fileContent", "")
                # 截断过长的内容
                if len(content) > 500:
                    content = content[:500] + "..."
                title = chunk.get("formTitle", "")
                context_parts.append(f"[文档{i}] {title}\n{content}\n")

            context = "\n".join(context_parts)

            # 构建提示 - 强调简洁和不重复
            prompt = f"""你是一个专业的文档问答助手。请根据以下文档内容回答用户的问题。

# 用户问题
{query}

# 参考文档
{context}

# 回答要求
1. 请使用中文回答
2. 回答要准确、简洁，直接回答问题，不要过多解释
3. 如果文档中有明确答案，请直接给出答案
4. 如果文档中没有相关信息，请明确说明"根据提供的文档，没有找到相关信息"
5. 不要重复相同的语句

# 回答："""

            start_time = time.time()

            gateway = await get_http_gateway()
            result = await gateway.acomplete(
                prompt=prompt,
                max_tokens=500,  # 减少最大token数
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
                "answer": "",
            }

    async def process_single_question(
        self, idx: int, total: int, question_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理单个问题"""

        title = question_data["title"]
        query = question_data["query"]
        expected_answers = question_data["expected_answers"]

        print(f"\r[{idx}/{total}] 处理中...", end="", flush=True)

        # 问题分类
        question_categories = self.classify_question(title, query)

        # 检索
        retrieve_result = await self.retrieve_from_milvus(query, top_k=10)

        # 生成答案
        if retrieve_result["success"]:
            generate_result = await self.generate_answer(query, retrieve_result["chunks"])
        else:
            generate_result = {"success": False, "error": "检索失败", "answer": ""}

        # 结果分类
        result_for_classification = {
            "error": retrieve_result.get("error") or generate_result.get("error"),
            "top_score": retrieve_result.get("top_score", 0),
            "chunk_count": len(retrieve_result.get("chunks", [])),
            "answer": generate_result.get("answer", ""),
        }
        result_categories = self.classify_result(result_for_classification)

        # 组装完整结果
        result = {
            "index": idx,
            "title": title,
            "query": query,
            "expected_answers": expected_answers,
            "question_categories": question_categories,
            "retrieval": {
                "success": retrieve_result["success"],
                "chunk_count": len(retrieve_result.get("chunks", [])),
                "top_score": retrieve_result.get("top_score", 0),
                "top_title": retrieve_result["chunks"][0]["formTitle"] if retrieve_result.get("chunks") else "",
                "timing": retrieve_result.get("timing", {}),
                "error": retrieve_result.get("error"),
            },
            "generation": {
                "success": generate_result["success"],
                "answer": generate_result.get("answer", ""),
                "answer_length": len(generate_result.get("answer", "")),
                "timing": generate_result.get("timing", {}),
                "error": generate_result.get("error"),
            },
            "result_categories": result_categories,
            "success": retrieve_result["success"] and generate_result["success"],
        }

        return result

    async def run_test(self):
        """运行完整评估测试"""

        print("=" * 80)
        print("RAG 服务完整评估与问题分类分析")
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

        self.stats["total"] = len(questions)
        print(f"  读取到 {len(questions)} 个问题")

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
        print(f"\n[3] 执行完整 RAG 测试 ({len(questions)} 个问题)")
        print("-" * 80)

        start_time = time.time()

        # 批量处理问题（每100个一批）
        batch_size = 100
        for batch_start in range(0, len(questions), batch_size):
            batch_end = min(batch_start + batch_size, len(questions))
            batch = questions[batch_start:batch_end]

            print(f"\n  批次 {batch_start//batch_size + 1}/{(len(questions)-1)//batch_size + 1}")

            for i, question_data in enumerate(batch, batch_start + 1):
                result = await self.process_single_question(i, len(questions), question_data)
                self.results.append(result)

                # 更新统计
                if result["success"]:
                    self.stats["successful"] += 1
                else:
                    self.stats["failed"] += 1

                # 更新时序统计
                self.stats["timing"]["total_embed_ms"] += result["retrieval"]["timing"].get("embed_ms", 0)
                self.stats["timing"]["total_search_ms"] += result["retrieval"]["timing"].get("search_ms", 0)
                self.stats["timing"]["total_generate_ms"] += result["generation"]["timing"].get("generate_ms", 0)

                # 更新检索统计
                self.stats["retrieval_stats"]["total_chunks"] += result["retrieval"]["chunk_count"]
                top_score = result["retrieval"]["top_score"]
                if top_score > 0:
                    self.stats["retrieval_stats"]["avg_top_score"] = (
                        (self.stats["retrieval_stats"]["avg_top_score"] * (self.stats["successful"] + self.stats["failed"] - 1) + top_score)
                        / (self.stats["successful"] + self.stats["failed"])
                    )
                if top_score < 0.5:
                    self.stats["retrieval_stats"]["low_score_count"] += 1

                # 定期保存进度
                if i % 50 == 0:
                    self.save_progress()

        elapsed = time.time() - start_time
        self.stats["timing"]["total_ms"] = elapsed * 1000

        print(f"\n  完成! 耗时: {elapsed:.1f}秒")

        # 生成报告
        self.generate_reports()

    def save_progress(self):
        """保存当前进度"""
        progress_file = self.output_dir / "evaluation_progress.json"
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "processed": len(self.results),
            }, f, ensure_ascii=False, indent=2)

    def generate_reports(self):
        """生成完整报告"""

        print(f"\n[4] 生成分析报告")

        # 对结果进行分类
        for result in self.results:
            qc = result["question_categories"]
            rc = result["result_categories"]

            # 按领域分类
            self.categories[f"domain_{qc['domain']}"].append(result)

            # 按问题类型分类
            self.categories[f"type_{qc['type']}"].append(result)

            # 按问题复杂度分类
            self.categories[f"category_{qc['category']}"].append(result)

            # 按结果问题分类
            if rc["issue_type"] != "无":
                self.categories[f"issue_{rc['issue_type']}"].append(result)

        # 保存完整结果
        results_file = self.output_dir / f"full_evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "results": self.results,
            }, f, ensure_ascii=False, indent=2)

        print(f"  完整结果: {results_file}")

        # 生成分类报告
        self.generate_category_report()

        # 生成统计摘要
        self.generate_summary_report()

    def generate_category_report(self):
        """生成分类分析报告"""

        report = []
        report.append("=" * 80)
        report.append("问题分类分析报告")
        report.append("=" * 80)

        # 按领域分类统计
        report.append("\n## 按领域分类")
        report.append("-" * 60)
        for key in sorted(self.categories.keys()):
            if key.startswith("domain_"):
                domain = key.replace("domain_", "")
                count = len(self.categories[key])
                success = sum(1 for r in self.categories[key] if r["success"])
                report.append(f"  {domain}: {count} 个问题 (成功: {success}, 失败: {count-success})")

        # 按问题类型分类
        report.append("\n## 按问题类型分类")
        report.append("-" * 60)
        for key in sorted(self.categories.keys()):
            if key.startswith("type_"):
                qtype = key.replace("type_", "")
                count = len(self.categories[key])
                success = sum(1 for r in self.categories[key] if r["success"])
                report.append(f"  {qtype}: {count} 个问题 (成功率: {success/count*100:.1f}%)")

        # 按问题复杂度分类
        report.append("\n## 按问题复杂度分类")
        report.append("-" * 60)
        for key in sorted(self.categories.keys()):
            if key.startswith("category_"):
                category = key.replace("category_", "")
                count = len(self.categories[key])
                avg_score = sum(r["retrieval"]["top_score"] for r in self.categories[key]) / max(count, 1)
                report.append(f"  {category}: {count} 个问题 (平均分数: {avg_score:.4f})")

        # 按问题类型分类
        report.append("\n## 按结果问题分类")
        report.append("-" * 60)
        for key in sorted(self.categories.keys()):
            if key.startswith("issue_"):
                issue = key.replace("issue_", "")
                count = len(self.categories[key])
                if count > 0:
                    report.append(f"  {issue}: {count} 个问题")

        # 保存分类报告
        category_file = self.output_dir / f"category_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(category_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report))

        print(f"  分类报告: {category_file}")

        # 打印报告
        print("\n" + "\n".join(report))

    def generate_summary_report(self):
        """生成统计摘要报告"""

        stats = self.stats
        total = stats["total"]
        successful = stats["successful"]
        failed = stats["failed"]

        report = []
        report.append("=" * 80)
        report.append("评估统计摘要")
        report.append("=" * 80)

        # 总体统计
        report.append(f"\n总体统计:")
        report.append(f"  总问题数: {total}")
        report.append(f"  成功: {successful} ({successful/total*100:.1f}%)")
        report.append(f"  失败: {failed} ({failed/total*100:.1f}%)")

        # 时序统计
        timing = stats["timing"]
        report.append(f"\n时序统计:")
        report.append(f"  平均嵌入时间: {timing['total_embed_ms']/total:.0f}ms")
        report.append(f"  平均搜索时间: {timing['total_search_ms']/total:.0f}ms")
        report.append(f"  平均生成时间: {timing['total_generate_ms']/successful:.0f}ms" if successful > 0 else "  平均生成时间: N/A")
        report.append(f"  平均总时间: {timing['total_ms']/total:.0f}ms")

        # 检索统计
        retrieval = stats["retrieval_stats"]
        report.append(f"\n检索统计:")
        report.append(f"  平均检索文档数: {retrieval['total_chunks']/total:.1f}")
        report.append(f"  平均顶部分数: {retrieval['avg_top_score']:.4f}")
        report.append(f"  低分检索数量: {retrieval['low_score_count']} ({retrieval['low_score_count']/total*100:.1f}%)")

        # 问题示例
        report.append(f"\n问题示例:")
        report.append(f"  成功案例:")
        success_results = [r for r in self.results if r["success"]][:3]
        for r in success_results:
            report.append(f"    - {r['query'][:50]}...")
            report.append(f"      检索分数: {r['retrieval']['top_score']:.4f}, 回答长度: {r['generation']['answer_length']}")

        if failed > 0:
            report.append(f"  失败案例:")
            fail_results = [r for r in self.results if not r["success"]][:3]
            for r in fail_results:
                error = r.get("retrieval", {}).get("error") or r.get("generation", {}).get("error", "Unknown")
                report.append(f"    - {r['query'][:50]}...")
                report.append(f"      错误: {error[:50]}...")

        report.append("\n" + "=" * 80)

        # 保存摘要报告
        summary_file = self.output_dir / f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report))

        print(f"\n  摘要报告: {summary_file}")

        # 打印报告
        print("\n" + "\n".join(report))


async def main():
    """主函数"""

    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_dir = Path("full_evaluation_results")
    milvus_uri = "http://localhost:19530"
    collection_name = "knowledge_base"

    tester = FullRAGEvaluation(
        questions_file=questions_file,
        output_dir=output_dir,
        milvus_uri=milvus_uri,
        collection_name=collection_name,
    )

    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())
