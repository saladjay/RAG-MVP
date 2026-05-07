"""
知识库检索性能测试 - 全部2445个问题

只测试检索部分，不调用LLM生成答案，快速完成所有问题测试

功能：
1. 对所有问题进行向量嵌入
2. 执行Milvus检索
3. 分析检索质量
4. 生成检索统计报告
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class RetrievalOnlyTest:
    """知识库检索性能测试"""

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

        # 统计信息
        self.stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "timing": {
                "total_embed_ms": 0,
                "total_search_ms": 0,
                "total_ms": 0,
            },
            "retrieval_quality": {
                "score_distribution": defaultdict(int),  # 分数区间统计
                "avg_top_score": 0,
                "low_score_count": 0,  # top score < 0.5
                "high_score_count": 0,  # top score >= 0.7
            },
            "chunk_stats": {
                "total_chunks": 0,
                "avg_chunks": 0,
            },
            "document_stats": defaultdict(int),  # 各文档出现次数
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

    async def retrieve_single(
        self, query: str, top_k: int = 10
    ) -> Dict[str, Any]:
        """执行单次检索"""

        start_time = time.time()

        try:
            # 初始化
            client = MilvusClient(uri=self.milvus_uri)
            embedding_service = await get_http_embedding_service()

            # 生成查询向量
            embed_start = time.time()
            query_vector = await embedding_service.embed_text(query)
            embed_time = (time.time() - embed_start) * 1000

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
                    "distance": float(hit["distance"]),
                    "score": float(hit["distance"]),
                    "formTitle": entity.get("formTitle", ""),
                    "document_id": entity.get("document_id", ""),
                    "chunk_index": entity.get("chunk_index", 0),
                })

            total_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "chunks": chunks,
                "top_score": float(chunks[0]["score"]) if chunks else 0.0,
                "chunk_count": len(chunks),
                "top_document": chunks[0]["formTitle"] if chunks else "",
                "timing": {
                    "embed_ms": embed_time,
                    "search_ms": search_time,
                    "total_ms": total_time,
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "chunks": [],
                "top_score": 0.0,
                "chunk_count": 0,
            }

    async def run_test(self):
        """运行检索测试"""

        print("=" * 80)
        print("知识库检索性能测试 - 全部问题")
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

        # 运行检索测试
        print(f"\n[3] 执行检索测试 ({len(questions)} 个问题)")
        print("-" * 80)

        start_time = time.time()

        # 批量处理
        batch_size = 100
        for batch_start in range(0, len(questions), batch_size):
            batch_end = min(batch_start + batch_size, len(questions))
            batch = questions[batch_start:batch_end]

            batch_num = batch_start // batch_size + 1
            total_batches = (len(questions) - 1) // batch_size + 1

            print(f"\n  批次 {batch_num}/{total_batches} ({batch_start+1}-{batch_end})...")

            for i, question_data in enumerate(batch, batch_start + 1):
                query = question_data["query"]
                title = question_data["title"]

                # 简化的进度显示
                if i % 20 == 0:
                    print(f"    [{i}/{len(questions)}] {query[:40]}...", flush=True)

                # 执行检索
                result = await self.retrieve_single(query, top_k=10)

                # 更新统计
                if result["success"]:
                    self.stats["successful"] += 1
                    self.stats["timing"]["total_embed_ms"] += result["timing"]["embed_ms"]
                    self.stats["timing"]["total_search_ms"] += result["timing"]["search_ms"]
                    self.stats["timing"]["total_ms"] += result["timing"]["total_ms"]
                    self.stats["retrieval_quality"]["avg_top_score"] = (
                        (self.stats["retrieval_quality"]["avg_top_score"] * (self.stats["successful"] - 1) + result["top_score"])
                        / self.stats["successful"]
                    )

                    # 分数区间统计
                    score = result["top_score"]
                    if score < 0.3:
                        self.stats["retrieval_quality"]["score_distribution"]["<0.3"] += 1
                    elif score < 0.4:
                        self.stats["retrieval_quality"]["score_distribution"]["0.3-0.4"] += 1
                    elif score < 0.5:
                        self.stats["retrieval_quality"]["score_distribution"]["0.4-0.5"] += 1
                    elif score < 0.6:
                        self.stats["retrieval_quality"]["score_distribution"]["0.5-0.6"] += 1
                    elif score < 0.7:
                        self.stats["retrieval_quality"]["score_distribution"]["0.6-0.7"] += 1
                    else:
                        self.stats["retrieval_quality"]["score_distribution"][">=0.7"] += 1

                    if score < 0.5:
                        self.stats["retrieval_quality"]["low_score_count"] += 1
                    if score >= 0.7:
                        self.stats["retrieval_quality"]["high_score_count"] += 1

                    # 文档统计
                    top_doc = result["top_document"]
                    self.stats["document_stats"][top_doc] += 1

                    # chunk统计
                    self.stats["chunk_stats"]["total_chunks"] += result["chunk_count"]
                else:
                    self.stats["failed"] += 1

                # 保存结果
                self.results.append({
                    "index": i,
                    "query": query,
                    "title": title,
                    "retrieval": result,
                })

                # 定期保存进度
                if i % 100 == 0:
                    self.save_progress(i)

        elapsed = time.time() - start_time
        print(f"\n  完成! 耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")

        # 生成报告
        self.generate_reports()

    def save_progress(self, current: int):
        """保存当前进度"""
        progress_file = self.output_dir / "retrieval_progress.json"
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "progress": f"{current}/{self.stats['total']}",
                "stats": self.stats,
            }, f, ensure_ascii=False, indent=2)

    def generate_reports(self):
        """生成检索测试报告"""

        print(f"\n[4] 生成报告")

        total = self.stats["total"]
        successful = self.stats["successful"]
        failed = self.stats["failed"]
        rq = self.stats["retrieval_quality"]
        cs = self.stats["chunk_stats"]

        # 计算平均值
        avg_embed = self.stats["timing"]["total_embed_ms"] / successful if successful > 0 else 0
        avg_search = self.stats["timing"]["total_search_ms"] / successful if successful > 0 else 0
        avg_total = self.stats["timing"]["total_ms"] / successful if successful > 0 else 0
        avg_chunks = cs["total_chunks"] / successful if successful > 0 else 0

        # 生成统计报告
        report = []
        report.append("=" * 80)
        report.append("知识库检索性能测试报告")
        report.append("=" * 80)
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # 总体统计
        report.append("## 总体统计")
        report.append("-" * 60)
        report.append(f"总问题数: {total}")
        report.append(f"检索成功: {successful} ({successful/total*100:.2f}%)")
        report.append(f"检索失败: {failed} ({failed/total*100:.2f}%)")
        report.append("")

        # 性能统计
        report.append("## 性能统计")
        report.append("-" * 60)
        report.append(f"平均嵌入时间: {avg_embed:.2f}ms")
        report.append(f"平均搜索时间: {avg_search:.2f}ms")
        report.append(f"平均总时间: {avg_total:.2f}ms")
        report.append(f"总耗时: {self.stats['timing']['total_ms']/1000:.1f}秒 ({self.stats['timing']['total_ms']/60000:.1f}分钟)")
        report.append("")

        # 检索质量统计
        report.append("## 检索质量统计")
        report.append("-" * 60)
        report.append(f"平均顶部分数: {rq['avg_top_score']:.4f}")
        report.append(f"低分检索(<0.5): {rq['low_score_count']} ({rq['low_score_count']/successful*100:.1f}%)")
        report.append(f"高分检索(>=0.7): {rq['high_score_count']} ({rq['high_score_count']/successful*100:.1f}%)")
        report.append("")

        # 分数分布
        report.append("## 顶部分数分布")
        report.append("-" * 60)
        report.append(f"< 0.3: {rq['score_distribution'].get('<0.3', 0)} ({rq['score_distribution'].get('<0.3', 0)/successful*100:.1f}%)")
        report.append(f"0.3 - 0.4: {rq['score_distribution'].get('0.3-0.4', 0)} ({rq['score_distribution'].get('0.3-0.4', 0)/successful*100:.1f}%)")
        report.append(f"0.4 - 0.5: {rq['score_distribution'].get('0.4-0.5', 0)} ({rq['score_distribution'].get('0.4-0.5', 0)/successful*100:.1f}%)")
        report.append(f"0.5 - 0.6: {rq['score_distribution'].get('0.5-0.6', 0)} ({rq['score_distribution'].get('0.5-0.6', 0)/successful*100:.1f}%)")
        report.append(f"0.6 - 0.7: {rq['score_distribution'].get('0.6-0.7', 0)} ({rq['score_distribution'].get('0.6-0.7', 0)/successful*100:.1f}%)")
        report.append(f">= 0.7: {rq['score_distribution'].get('>=0.7', 0)} ({rq['score_distribution'].get('>=0.7', 0)/successful*100:.1f}%)")
        report.append("")

        # 检索结果统计
        report.append("## 检索结果统计")
        report.append("-" * 60)
        report.append(f"平均检索文档数: {avg_chunks:.1f}")
        report.append(f"总检索chunk数: {cs['total_chunks']}")
        report.append("")

        # 文档分布（前10）
        report.append("## 最常检索到的文档 (Top 10)")
        report.append("-" * 60)
        sorted_docs = sorted(self.stats["document_stats"].items(), key=lambda x: x[1], reverse=True)
        for doc, count in sorted_docs[:10]:
            # 只显示文档名的前60个字符
            doc_name = doc[:60] + "..." if len(doc) > 60 else doc
            report.append(f"  {doc_name}: {count} 次")

        # 保存文本报告
        report_file = self.output_dir / f"retrieval_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report))

        print(f"  文本报告: {report_file}")

        # 保存完整 JSON 结果
        json_file = self.output_dir / f"retrieval_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "results": self.results,
            }, f, ensure_ascii=False, indent=2)

        print(f"  完整结果: {json_file}")

        # 打印报告
        print("\n" + "\n".join(report))
        print("=" * 80)


async def main():
    """主函数"""

    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_dir = Path("retrieval_test_results")
    milvus_uri = "http://localhost:19530"
    collection_name = "knowledge_base"

    tester = RetrievalOnlyTest(
        questions_file=questions_file,
        output_dir=output_dir,
        milvus_uri=milvus_uri,
        collection_name=collection_name,
    )

    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())
