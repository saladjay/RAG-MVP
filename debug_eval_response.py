"""
Debug evaluation response
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_glm_gateway


async def debug_evaluation_response():
    """Debug evaluation response"""

    gateway = await get_glm_gateway()

    query = "2025年春节放假共计几天？"
    generated_answer = "根据提供的文档，2025年春节放假共计8天。"
    expected_answers = ["8天", "2025年春节放假共计8天"]

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

请输出JSON格式：{{"is_correct": true/false, "confidence": 0.0-1.0, "reason": "简短理由"}}"""

    print("=" * 80)
    print("评估响应调试")
    print("=" * 80)
    print(f"Prompt 长度: {len(prompt)}")
    print()

    result = await gateway.acomplete(
        prompt=prompt,
        max_tokens=300,
        temperature=0.5,
    )

    print(f"[响应信息]")
    print(f"  长度: {len(result.text)}")
    print(f"  Token: input={result.input_tokens}, output={result.output_tokens}")
    print()

    print(f"[响应内容]")
    print(f"  Raw: {repr(result.text[:500])}")
    print()

    # Try to parse
    if result.text:
        import json
        import re

        cleaned = result.text.strip()

        # Remove ```json``` if present
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        print(f"[清理后]")
        print(f"  长度: {len(cleaned)}")
        print(f"  内容: {cleaned[:200]}")
        print()

        # Try to parse JSON
        try:
            data = json.loads(cleaned)
            print(f"[JSON 解析成功]")
            print(f"  is_correct: {data.get('is_correct')}")
            print(f"  confidence: {data.get('confidence')}")
            print(f"  reason: {data.get('reason')}")
        except json.JSONDecodeError as e:
            print(f"[JSON 解析失败: {e}]")

            # Manual extraction
            is_correct_match = re.search(r'"is_correct"\s*:\s*(true|false)', cleaned)
            if is_correct_match:
                print(f"  手动提取 is_correct: {is_correct_match.group(1)}")


if __name__ == "__main__":
    asyncio.run(debug_evaluation_response())
