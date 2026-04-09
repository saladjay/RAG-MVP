"""
快速问题分类分析脚本

读取 questions/fianl_version_qa.jsonl 并对所有问题进行分类统计
不需要调用 RAG API，快速分析问题分布
"""

import json
import sys
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Any

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


class QuestionClassifier:
    """问题分类器"""

    def __init__(self, questions_file: Path, output_dir: Path):
        self.questions_file = questions_file
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.questions: List[Dict[str, Any]] = []
        self.categories: Dict[str, List[Dict]] = defaultdict(list)

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
        """对问题进行多维度分类"""
        categories = {
            # 按文档来源分类
            "source": "其他",

            # 按领域分类
            "domain": "其他",

            # 按问题类型分类
            "question_type": "其他",

            # 按答案类型分类
            "answer_type": "其他",

            # 按问题复杂度分类
            "complexity": "中等",

            # 按关键词分类
            "keywords": [],
        }

        query_lower = query.lower()
        title_lower = title.lower()

        # ===== 文档来源分类 =====
        if "节假日" in title_lower or "放假" in title_lower:
            categories["source"] = "节假日通知"
        elif "资产" in title_lower or "盘点" in title_lower:
            categories["source"] = "资产通知"
        elif "工资" in title_lower or "薪酬" in title_lower or "提成" in title_lower:
            categories["source"] = "薪酬制度"
        elif "保险" in title_lower or "公积金" in title_lower:
            categories["source"] = "保险福利"
        elif "会议" in title_lower or "纪要" in title_lower:
            categories["source"] = "会议纪要"
        elif "销售" in title_lower or "合同" in title_lower:
            categories["source"] = "销售业务"
        elif "职工" in title_lower or "工会" in title_lower or "代表" in title_lower:
            categories["source"] = "职工管理"
        elif "制度" in title_lower or "办法" in title_lower or "规定" in title_lower:
            categories["source"] = "规章制度"

        # ===== 领域分类 =====
        if any(x in query_lower for x in ["放假", "调休", "节假日", "春节", "国庆", "元旦", "清明", "劳动", "中秋", "休假"]):
            categories["domain"] = "节假日管理"
        elif any(x in query_lower for x in ["工资", "薪酬", "待遇", "补贴", "提成", "奖金", "发放"]):
            categories["domain"] = "薪酬福利"
        elif any(x in query_lower for x in ["资产", "设备", "车辆", "电脑", "电话", "领用", "配置"]):
            categories["domain"] = "资产管理"
        elif any(x in query_lower for x in ["值班", "值守", "轮班", "电话"]):
            categories["domain"] = "值班管理"
        elif any(x in query_lower for x in ["保险", "公积金", "社保", "缴纳"]):
            categories["domain"] = "保险福利"
        elif any(x in query_lower for x in ["实习生", "试用", "入职", "招聘", "面试"]):
            categories["domain"] = "人事管理"
        elif any(x in query_lower for x in ["报销", "费用", "预算", "采购", "发票"]):
            categories["domain"] = "财务报销"
        elif any(x in query_lower for x in ["合同", "协议", "条款", "违约"]):
            categories["domain"] = "合同管理"
        elif any(x in query_lower for x in ["培训", "学习", "教育", "考试"]):
            categories["domain"] = "培训教育"
        elif any(x in query_lower for x in ["安全", "消防", "应急", "预案"]):
            categories["domain"] = "安全消防"
        elif any(x in query_lower for x in ["会议", "时间", "地点", "参加", "出席"]):
            categories["domain"] = "会议活动"

        # ===== 问题类型分类 =====
        if any(x in query for x in ["几天", "多久", "时长", "时间", "何时", "日期", "什么时候", "从哪天", "到哪天"]):
            categories["question_type"] = "时间数量查询"
        elif any(x in query for x in ["是否", "有没有", "是否是", "是不是", "有没有有", "是否需要"]):
            categories["question_type"] = "是非判断"
        elif any(x in query for x in ["是什么", "是什么叫", "什么叫", "是什么是", "哪些", "谁", "姓名"]):
            categories["question_type"] = "事实查询"
        elif any(x in query for x in ["怎么", "如何", "怎样", "流程", "步骤"]):
            categories["question_type"] = "方法流程"
        elif any(x in query for x in ["多少", "号码", "牌号", "地址", "位置", "邮箱"]):
            categories["question_type"] = "具体信息"
        elif any(x in query for x in ["为什么", "原因", "为何", "怎么是"]):
            categories["question_type"] = "原因解释"
        elif any(x in query for x in ["对比", "区别", "差异", "不同"]):
            categories["question_type"] = "对比分析"
        elif any(x in query for x in ["列表", "都有", "包括", "包含"]):
            categories["question_type"] = "列表查询"
        elif any(x in query for x in ["要求", "标准", "条件", "资格"]):
            categories["question_type"] = "要求查询"

        # ===== 答案类型分类 =====
        if any(x in query for x in ["几天", "多久", "多少天", "时长"]):
            categories["answer_type"] = "数字日期"
        elif any(x in query for x in ["是否", "有没有"]):
            categories["answer_type"] = "是与否"
        elif any(x in query for x in ["什么", "叫什么", "是谁", "姓名"]):
            categories["answer_type"] = "名称描述"
        elif any(x in query for x in ["哪天", "何时", "日期"]):
            categories["answer_type"] = "日期"
        elif any(x in query for x in ["多少", "号码", "牌号"]):
            categories["answer_type"] = "号码标识"
        elif any(x in query for x in ["哪里", "地址", "位置"]):
            categories["answer_type"] = "位置信息"

        # ===== 复杂度分类 =====
        query_length = len(query)
        has_conditions = any(x in query for x in ["如果", "当", "在什么情况下", "满足"])
        has_multiple = any(x in query for x in ["和", "或", "以及", "分别"]) and query.count("和") + query.count("或") > 1

        if query_length <= 15 and not has_conditions and not has_multiple:
            categories["complexity"] = "简单"
        elif query_length <= 35 and not has_conditions:
            categories["complexity"] = "中等"
        else:
            categories["complexity"] = "复杂"

        # ===== 关键词提取 =====
        keywords = []
        # 文档编号
        if "〔" in title_lower and "〕" in title_lower:
            import re
            match = re.search(r'〔[^〕]+〕', title_lower)
            if match:
                keywords.append(match.group().replace("〔", "").replace("〕", ""))
        # 年份
        if "2025" in query_lower:
            keywords.append("2025年")
        if "2024" in query_lower:
            keywords.append("2024年")
        # 节日
        for holiday in ["春节", "国庆", "元旦", "清明", "劳动节", "中秋"]:
            if holiday in query:
                keywords.append(holiday)

        categories["keywords"] = keywords

        return categories

    def analyze(self):
        """分析所有问题"""

        print("=" * 80)
        print("问题分类分析")
        print("=" * 80)
        print(f"问题文件: {self.questions_file}")
        print(f"输出目录: {self.output_dir}")
        print("-" * 80)

        # 读取问题
        print("\n[1] 读取问题文件")
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
                        self.questions.append(parsed)
                    except json.JSONDecodeError as e:
                        print(f"  [警告] 第 {line_num} 行解析失败: {e}")

        except FileNotFoundError:
            print(f"  [错误] 文件不存在: {self.questions_file}")
            return

        print(f"  读取到 {len(self.questions)} 个问题")

        # 分类所有问题
        print(f"\n[2] 分析分类")
        for i, question in enumerate(self.questions, 1):
            if i % 500 == 0:
                print(f"  处理进度: {i}/{len(self.questions)}")

            title = question["title"]
            query = question["query"]

            # 分类
            categories = self.classify_question(title, query)

            # 存储分类结果
            question["categories"] = categories

            # 按各维度分类存储
            for key, value in categories.items():
                if key == "keywords":
                    for kw in value:
                        self.categories[f"keyword_{kw}"].append(question)
                else:
                    self.categories[f"{key}_{value}"].append(question)

        print(f"  完成! 分类维度: {len([k for k in self.categories.keys() if not k.startswith('keyword_')])}")

        # 生成报告
        self.generate_reports()

    def generate_reports(self):
        """生成分类报告"""

        print(f"\n[3] 生成报告")

        report = []
        report.append("=" * 80)
        report.append("问题分类分析报告")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"总问题数: {len(self.questions)}")
        report.append("=" * 80)

        # 按文档来源分类
        report.append("\n## 1. 按文档来源分类")
        report.append("-" * 60)
        source_keys = sorted([k for k in self.categories.keys() if k.startswith("source_")])
        for key in source_keys:
            source = key.replace("source_", "")
            count = len(self.categories[key])
            report.append(f"  {source}: {count} 个问题")

            # 每个来源的前3个问题示例
            if count <= 10:
                report.append(f"    示例问题:")
                for q in self.categories[key][:3]:
                    report.append(f"      - {q['query'][:60]}...")

        # 按领域分类
        report.append("\n## 2. 按业务领域分类")
        report.append("-" * 60)
        domain_keys = sorted([k for k in self.categories.keys() if k.startswith("domain_")])
        for key in domain_keys:
            domain = key.replace("domain_", "")
            count = len(self.categories[key])
            report.append(f"  {domain}: {count} 个问题")

        # 按问题类型分类
        report.append("\n## 3. 按问题类型分类")
        report.append("-" * 60)
        type_keys = sorted([k for k in self.categories.keys() if k.startswith("question_type_")])
        for key in type_keys:
            qtype = key.replace("question_type_", "")
            count = len(self.categories[key])
            report.append(f"  {qtype}: {count} 个问题")

        # 按答案类型分类
        report.append("\n## 4. 按答案类型分类")
        report.append("-" * 60)
        answer_keys = sorted([k for k in self.categories.keys() if k.startswith("answer_type_")])
        for key in answer_keys:
            atype = key.replace("answer_type_", "")
            count = len(self.categories[key])
            report.append(f"  {atype}: {count} 个问题")

        # 按复杂度分类
        report.append("\n## 5. 按问题复杂度分类")
        report.append("-" * 60)
        for complexity in ["简单", "中等", "复杂"]:
            key = f"complexity_{complexity}"
            count = len(self.categories.get(key, []))
            pct = count / len(self.questions) * 100
            report.append(f"  {complexity}: {count} 个问题 ({pct:.1f}%)")

        # 按关键词分类
        report.append("\n## 6. 关键词统计")
        report.append("-" * 60)
        keyword_keys = sorted([k for k in self.categories.keys() if k.startswith("keyword_")])
        for key in keyword_keys[:20]:  # 只显示前20个
            kw = key.replace("keyword_", "")
            count = len(self.categories[key])
            if count >= 10:  # 只显示出现10次以上的关键词
                report.append(f"  {kw}: {count} 个问题")

        # 详细分析 - 各领域的问题类型分布
        report.append("\n## 7. 各领域问题类型分布")
        report.append("-" * 60)
        domains = [k.replace("domain_", "") for k in self.categories.keys() if k.startswith("domain_")]
        for domain in domains:
            domain_questions = self.categories.get(f"domain_{domain}", [])
            if len(domain_questions) >= 20:  # 只分析问题数>=20的领域
                report.append(f"\n  {domain} (共 {len(domain_questions)} 个问题):")
                type_counter = Counter()
                for q in domain_questions:
                    qtype = q["categories"]["question_type"]
                    type_counter[qtype] += 1
                for qtype, count in type_counter.most_common():
                    report.append(f"    - {qtype}: {count} 个")

        # 保存文本报告
        report_file = self.output_dir / f"question_classification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report))

        print(f"  文本报告: {report_file}")

        # 保存 JSON 数据
        json_file = self.output_dir / f"question_classification_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_questions": len(self.questions),
                "categories": {k: len(v) for k, v in self.categories.items()},
                "questions": self.questions,
            }, f, ensure_ascii=False, indent=2)

        print(f"  JSON 数据: {json_file}")

        # 打印报告
        print("\n" + "\n".join(report))
        print("\n" + "=" * 80)


from datetime import datetime


def main():
    """主函数"""

    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_dir = Path("question_classification_results")

    classifier = QuestionClassifier(
        questions_file=questions_file,
        output_dir=output_dir,
    )

    classifier.analyze()


if __name__ == "__main__":
    main()
