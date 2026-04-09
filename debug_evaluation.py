"""
Debug script for LLM evaluation

Test the evaluate_with_llm function to see why it's failing.
"""

import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway


async def debug_llm_evaluation():
    """Debug LLM evaluation"""

    # Test data
    query = "2025年春节放假共计几天？"
    generated_answer = "根据提供的文档，2025年春节放假共计8天。"
    expected_answers = ["8天", "2025年春节放假共计8天"]

    print("=" * 80)
    print("LLM 评估调试")
    print("=" * 80)
    print(f"问题: {query}")
    print(f"生成答案: {generated_answer}")
    print(f"预期答案: {expected_answers}")
    print()

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
4. 关注答案的核心内容是否正确，而不是措辞完全一致

# 输出格式（严格 JSON）
{{
    "is_correct": true/false,
    "confidence": 0.0-1.0,
    "reason": "判断理由（简短）"
}}

请只输出 JSON，不要有其他内容："""

    print("[1] 调用 LLM 进行评估...")
    print()

    try:
        gateway = await get_gateway()
        result = await gateway.acomplete(
            prompt=prompt,
            model_hint="glm-4.5-air",
            max_tokens=300,
            temperature=0.1,
        )

        response_text = result.text.strip()

        print(f"[原始响应]")
        print(f"  长度: {len(response_text)} 字符")
        print(f"  内容: {response_text}")
        print()

        # 尝试提取 JSON
        cleaned_text = response_text
        if "```json" in cleaned_text:
            print("[检测到 ```json 标记，尝试提取...]")
            cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_text:
            print("[检测到 ``` 标记，尝试提取...]")
            cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

        print(f"[清理后的文本]")
        print(f"  内容: {cleaned_text}")
        print()

        # 尝试解析 JSON
        try:
            evaluation = json.loads(cleaned_text)
            print(f"[JSON 解析成功]")
            print(f"  is_correct: {evaluation.get('is_correct')}")
            print(f"  confidence: {evaluation.get('confidence')}")
            print(f"  reason: {evaluation.get('reason')}")
        except json.JSONDecodeError as e:
            print(f"[JSON 解析失败: {e}]")
            print(f"  这是回退到关键词匹配的原因！")

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_llm_evaluation())
