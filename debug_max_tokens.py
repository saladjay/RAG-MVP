"""
Debug max_tokens parameter in GLM API calls
"""

import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_glm_gateway


async def debug_max_tokens():
    """Debug max_tokens parameter"""

    gateway = await get_glm_gateway()

    # Test with different max_tokens values
    for max_t in [300, 500, 1000, 2048]:
        print(f"\n{'='*80}")
        print(f"测试 max_tokens={max_t}")
        print('='*80)

        result = await gateway.acomplete(
            prompt="请详细介绍一下中国的春节习俗，要求不少于10个不同的方面。",
            max_tokens=max_t,
            temperature=0.7,
        )

        print(f"[响应信息]")
        print(f"  长度: {len(result.text)}")
        print(f"  Token: input={result.input_tokens}, output={result.output_tokens}")
        print(f"  内容预览: {result.text[:200]}...")
        print(f"  内容结尾: ...{result.text[-200:]}")

        # Check if output tokens hit max_tokens
        if result.output_tokens >= max_t - 10:  # Allow some margin
            print(f"  [WARNING] Response likely truncated by max_tokens!")
        else:
            print(f"  [OK] Response finished naturally")

    # Test evaluation JSON specifically
    print(f"\n{'='*80}")
    print("测试评估 JSON 请求")
    print('='*80)

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

    print(f"Prompt 长度: {len(prompt)}")

    for max_t in [300, 500, 1000]:
        print(f"\n--- max_tokens={max_t} ---")

        result = await gateway.acomplete(
            prompt=prompt,
            max_tokens=max_t,
            temperature=0.5,
        )

        print(f"  长度: {len(result.text)}, Token: input={result.input_tokens}, output={result.output_tokens}")

        # Try to parse JSON
        if result.text:
            cleaned = result.text.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()

            try:
                data = json.loads(cleaned)
                print(f"  ✓ JSON 解析成功: {data}")
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON 解析失败: {e}")
                print(f"     内容: {cleaned[:150]}...")


if __name__ == "__main__":
    asyncio.run(debug_max_tokens())
