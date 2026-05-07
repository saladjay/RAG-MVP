"""
Dify 工作流测试结果评估脚本

功能：
1. 读取 dify_workflow_test_results.json 测试结果
2. 使用 GLM 对每个答案进行质量评估
3. 将错误原因归类到预定义类别
4. 生成完整的评估报告和统计分析
"""

import asyncio
import json
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_http_gateway


# 错误类别定义
ERROR_CATEGORIES = {
    "SUCCESS": {
        "name": "成功/正常",
        "description": "工作流正常执行，返回了有效的答案",
        "keywords": ["成功", "正常", "有效答案"],
    },
    "USER_INFO_ERROR": {
        "name": "用户信息/权限问题",
        "description": "用户信息获取失败、权限验证失败、认证错误",
        "keywords": ["用户信息", "权限", "认证", "登录", "user", "auth", "permission"],
    },
    "KB_RETRIEVAL_ERROR": {
        "name": "知识库检索失败",
        "description": "知识库连接失败、检索超时、索引错误",
        "keywords": ["知识库", "检索", "retrieval", "index", "search", "milvus", "向量"],
    },
    "PARAM_ERROR": {
        "name": "参数配置错误",
        "description": "输入参数格式错误、缺少必需参数、参数类型不匹配",
        "keywords": ["参数", "param", "invalid", "missing", "format", "type"],
    },
    "WORKFLOW_CODE_ERROR": {
        "name": "工作流代码错误",
        "description": "工作流内部代码执行错误、Python 异常、逻辑错误",
        "keywords": ["代码", "code", "exception", "traceback", "error", "bug", "list indices"],
    },
    "DATASOURCE_ERROR": {
        "name": "数据源问题",
        "description": "外部数据源连接失败、API 调用失败、数据库问题",
        "keywords": ["数据源", "database", "api", "external", "连接", "connection"],
    },
    "NETWORK_ERROR": {
        "name": "网络连接问题",
        "description": "网络超时、连接断开、DNS 解析失败",
        "keywords": ["网络", "network", "timeout", "connection", "dns", "unreachable"],
    },
    "POOR_ANSWER": {
        "name": "回答质量差",
        "description": "工作流执行成功但答案质量不高（答非所问、信息不完整、过于笼统）",
        "keywords": ["质量", "不准确", "不完整", "答非所问"],
    },
    "OTHER": {
        "name": "其他/未分类",
        "description": "无法归入以上类别的其他问题",
        "keywords": ["其他", "未知"],
    },
}


class DifyResultEvaluation:
    """Dify 测试结果评估类"""

    def __init__(
        self,
        results_file: Path,
        output_dir: Path,
    ):
        self.results_file = results_file
        self.output_dir = output_dir

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 评估结果存储
        self.evaluations: List[Dict[str, Any]] = []

        # 统计信息
        self.stats = {
            "total": 0,
            "by_category": {code: 0 for code in ERROR_CATEGORIES.keys()},
            "timing": {
                "total_eval_ms": 0,
                "avg_eval_ms": 0,
            },
        }

    def load_results(self) -> Dict[str, Any]:
        """加载测试结果文件"""
        print(f"[1] 加载测试结果文件: {self.results_file}")

        try:
            with open(self.results_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            results = data.get("results", [])
            print(f"  加载到 {len(results)} 条测试结果")
            return data

        except FileNotFoundError:
            print(f"  [错误] 文件不存在: {self.results_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"  [错误] JSON 解析失败: {e}")
            return {}

    async def evaluate_single_result(
        self,
        gateway,
        idx: int,
        total: int,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """评估单个测试结果"""

        query = result.get("query", "")
        answer = result.get("response", {}).get("answer", "")
        retriever_resources = result.get("metadata", {}).get("retriever_resources", [])
        metadata = result.get("metadata", {})
        timing = result.get("timing_ms", 0)

        print(f"\r[{idx}/{total}] 评估中...", end="", flush=True)

        # 构建评估提示
        categories_desc = "\n".join([
            f"{code}: {cat['name']} - {cat['description']}"
            for code, cat in ERROR_CATEGORIES.items()
        ])

        # 检查是否有检索资源
        has_retrieval = len(retriever_resources) > 0
        retrieval_info = ""
        if has_retrieval:
            top_scores = [r.get("score", 0) for r in retriever_resources[:3]]
            retrieval_info = f"检索到 {len(retriever_resources)} 个文档，top-3 分数: {top_scores}"

        prompt = f"""你是一个专业的 RAG 系统评估专家。请分析以下 Dify 工作流的执行结果，评估答案质量并归类错误原因。

# 用户问题
{query}

# Dify 返回的答案
{answer}

# 检索信息
{retrieval_info if retrieval_info else "无检索资源"}

# 元数据
- 响应时间: {timing}ms
- Token 使用: {metadata.get('usage', {})}

# 评估要求

## 1. 判断执行状态
首先判断这次请求是**成功**还是**失败**：
- **成功**：返回了有效的答案内容，且检索到了相关文档
- **失败**：返回了错误信息、无法回答、或检索失败

## 2. 错误分类
如果执行失败，请将错误归类到以下类别中最合适的一个：

{categories_desc}

## 3. 答案质量评估（如果执行成功）
如果执行成功，请评估：
- **相关性**：答案是否与问题相关 (1-5分)
- **完整性**：答案是否完整回答了问题 (1-5分)
- **准确性**：答案信息是否准确 (1-5分)
- 综合评分 (1-5分，3分及以上为质量合格)

# 输出格式（严格 JSON）
{{
    "status": "success/failure",
    "category_code": "类别代码（如 SUCCESS, USER_INFO_ERROR 等）",
    "category_name": "类别名称",
    "confidence": 0.0-1.0,
    "reason": "判断理由（50字以内）",
    "quality_score": null 或 1-5的分数（仅当status=success时）,
    "issues": ["问题1", "问题2"]  # 发现的具体问题列表
}}

请只输出 JSON，不要有其他内容："""

        try:
            start_time = time.time()

            # 调用 GLM 进行评估
            llm_result = await gateway.acomplete(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1,
            )

            eval_time_ms = (time.time() - start_time) * 1000

            response_text = llm_result.text.strip()

            # 提取 JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            evaluation = json.loads(response_text)

            return {
                "index": idx,
                "query": query,
                "answer_preview": answer[:100],
                "evaluation": evaluation,
                "has_retrieval": has_retrieval,
                "retrieval_count": len(retriever_resources),
                "timing_ms": timing,
                "eval_time_ms": eval_time_ms,
                "raw_response": response_text,
            }

        except Exception as e:
            # 失败时使用简单的关键词匹配
            return {
                "index": idx,
                "query": query,
                "answer_preview": answer[:100],
                "evaluation": self._fallback_evaluation(answer, has_retrieval),
                "has_retrieval": has_retrieval,
                "retrieval_count": len(retriever_resources),
                "timing_ms": timing,
                "eval_error": str(e),
            }

    def _fallback_evaluation(self, answer: str, has_retrieval: bool) -> Dict[str, Any]:
        """后备评估方案（关键词匹配）"""

        answer_lower = answer.lower()

        # 检查是否成功
        success_indicators = ["根据", "文档", "如下", "具体", "是", "天", "号"]
        failure_indicators = ["失败", "错误", "无法", "异常", "500", "401", "400"]

        is_success = (
            has_retrieval and
            any(word in answer for word in success_indicators) and
            not any(word in answer_lower for word in failure_indicators)
        )

        if is_success:
            return {
                "status": "success",
                "category_code": "SUCCESS",
                "category_name": "成功/正常",
                "confidence": 0.8,
                "reason": "基于关键词匹配判断为成功",
                "quality_score": 3,
                "issues": [],
            }

        # 错误分类
        category_code = "OTHER"
        for code, cat in ERROR_CATEGORIES.items():
            if code == "SUCCESS":
                continue
            if any(keyword in answer_lower for keyword in cat["keywords"]):
                category_code = code
                break

        return {
            "status": "failure",
            "category_code": category_code,
            "category_name": ERROR_CATEGORIES[category_code]["name"],
            "confidence": 0.6,
            "reason": "基于关键词匹配归类",
            "quality_score": None,
            "issues": [f"答案包含错误信息: {answer[:50]}"],
        }

    async def run_evaluation(self):
        """运行完整评估"""

        print("=" * 80)
        print("Dify 工作流测试结果评估")
        print("=" * 80)
        print(f"结果文件: {self.results_file}")
        print(f"输出目录: {self.output_dir}")
        print("-" * 80)

        # 加载结果
        data = self.load_results()
        if not data:
            print("\n[错误] 无法加载测试结果")
            return

        results = data.get("results", [])
        if not results:
            print("\n[错误] 没有找到测试结果")
            return

        self.stats["total"] = len(results)

        # 获取 GLM gateway
        print(f"\n[2] 初始化 GLM Gateway...")
        try:
            gateway = await get_http_gateway()
            print("  Gateway 初始化成功")
        except Exception as e:
            print(f"  [错误] Gateway 初始化失败: {e}")
            return

        # 执行评估
        print(f"\n[3] 执行评估 ({len(results)} 条结果)")
        print("-" * 80)

        for idx, result in enumerate(results, 1):
            evaluation = await self.evaluate_single_result(
                gateway=gateway,
                idx=idx,
                total=len(results),
                result=result,
            )
            self.evaluations.append(evaluation)

            # 更新统计
            cat_code = evaluation["evaluation"].get("category_code", "OTHER")
            self.stats["by_category"][cat_code] += 1

            if "eval_time_ms" in evaluation:
                self.stats["timing"]["total_eval_ms"] += evaluation["eval_time_ms"]

            # 定期保存
            if idx % 20 == 0:
                self.save_progress()

        self.stats["timing"]["avg_eval_ms"] = (
            self.stats["timing"]["total_eval_ms"] / len(results)
            if results else 0
        )

        print(f"\n  评估完成! 平均评估时间: {self.stats['timing']['avg_eval_ms']:.0f}ms")

        # 生成报告
        self.generate_reports()

    def save_progress(self):
        """保存当前进度"""
        progress_file = self.output_dir / "evaluation_progress.json"
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "processed": len(self.evaluations),
            }, f, ensure_ascii=False, indent=2)

    def generate_reports(self):
        """生成评估报告"""

        print(f"\n[4] 生成评估报告")

        # 计算成功率和质量分数
        success_count = self.stats["by_category"].get("SUCCESS", 0)
        total = self.stats["total"]
        success_rate = (success_count / total * 100) if total > 0 else 0

        # 计算平均质量分数（仅成功的）
        quality_scores = [
            e["evaluation"].get("quality_score", 0)
            for e in self.evaluations
            if e["evaluation"].get("status") == "success" and e["evaluation"].get("quality_score")
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        # 保存完整结果
        results_file = self.output_dir / f"dify_eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "source_file": str(self.results_file),
                "statistics": {
                    "total": total,
                    "success_rate": success_rate,
                    "avg_quality_score": avg_quality,
                    "by_category": self.stats["by_category"],
                },
                "evaluations": self.evaluations,
            }, f, ensure_ascii=False, indent=2)

        print(f"  完整结果: {results_file}")

        # 生成分类报告
        self.generate_category_report(success_rate, avg_quality)

        # 生成详细分析
        self.generate_detailed_analysis()

    def generate_category_report(self, success_rate: float, avg_quality: float):
        """生成分类统计报告"""

        report = []
        report.append("=" * 80)
        report.append("Dify 工作流评估报告")
        report.append("=" * 80)

        # 总体统计
        report.append(f"\n## 总体统计")
        report.append(f"  总测试数: {self.stats['total']}")
        report.append(f"  成功率: {success_rate:.2f}%")
        report.append(f"  平均质量分数: {avg_quality:.2f}/5 (仅成功的)")

        # 分类统计
        report.append(f"\n## 错误类别统计")
        report.append("-" * 60)

        # 按数量排序
        sorted_categories = sorted(
            self.stats["by_category"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        for code, count in sorted_categories:
            if count == 0:
                continue
            cat = ERROR_CATEGORIES[code]
            percentage = (count / self.stats['total'] * 100)
            report.append(f"  {cat['name']}: {count} ({percentage:.1f}%)")

        # 问题详情
        report.append(f"\n## 主要问题分析")

        for code, count in sorted_categories:
            if count == 0 or code == "SUCCESS":
                continue

            cat = ERROR_CATEGORIES[code]
            report.append(f"\n### {cat['name']} ({count} 个)")
            report.append(f"  描述: {cat['description']}")

            # 找出该类别的案例
            cases = [
                e for e in self.evaluations
                if e["evaluation"].get("category_code") == code
            ][:3]  # 只显示前3个

            for case in cases:
                report.append(f"  - 问题: {case['query'][:50]}...")
                reason = case["evaluation"].get("reason", "")[:50]
                report.append(f"    原因: {reason}...")

        # 保存报告
        report_file = self.output_dir / f"category_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report))

        print(f"  分类报告: {report_file}")

        # 打印报告
        print("\n" + "\n".join(report))

    def generate_detailed_analysis(self):
        """生成详细分析报告"""

        # 按问题类型分析
        by_quality = defaultdict(list)
        for eval in self.evaluations:
            quality = eval["evaluation"].get("quality_score", 0)
            if quality:
                if quality >= 4:
                    by_quality["优秀"].append(eval)
                elif quality >= 3:
                    by_quality["良好"].append(eval)
                else:
                    by_quality["需改进"].append(eval)

        # 生成详细分析
        analysis = []
        analysis.append("=" * 80)
        analysis.append("详细质量分析")
        analysis.append("=" * 80)

        for quality_level, cases in by_quality.items():
            if not cases:
                continue
            analysis.append(f"\n## {quality_level} ({len(cases)} 个)")
            for case in cases[:5]:  # 只显示前5个
                analysis.append(f"  - {case['query'][:60]}...")
                analysis.append(f"    评分: {case['evaluation'].get('quality_score', 'N/A')}")
                answer = case.get('answer_preview', '')[:50]
                analysis.append(f"    答案: {answer}...")

        # 保存详细分析
        analysis_file = self.output_dir / f"detailed_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(analysis_file, "w", encoding="utf-8") as f:
            f.write("\n".join(analysis))

        print(f"  详细分析: {analysis_file}")


async def main():
    """主函数"""

    # 配置
    results_file = Path("dify_workflow_test_results.json")
    output_dir = Path("dify_evaluation_results")

    # 运行评估
    evaluator = DifyResultEvaluation(
        results_file=results_file,
        output_dir=output_dir,
    )

    await evaluator.run_evaluation()


if __name__ == "__main__":
    asyncio.run(main())
