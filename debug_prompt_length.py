"""
Test with longer prompts
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway


async def test_longer_prompts():
    """Test with longer prompts"""

    gateway = await get_gateway()

    print("=" * 80)
    print("GLM Prompt 长度测试")
    print("=" * 80)

    # Short prompt
    print("\n[测试1] 短 prompt")
    short_prompt = "请输出JSON: {\"ok\": true}"
    result = await gateway.acomplete(
        prompt=short_prompt,
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.5,
    )
    print(f"  响应长度: {len(result.text)}")

    # Medium prompt
    print("\n[测试2] 中等 prompt")
    medium_prompt = """你是一个助手。
请输出JSON: {\"ok\": true}"""
    result = await gateway.acomplete(
        prompt=medium_prompt,
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.5,
    )
    print(f"  响应长度: {len(result.text)}")

    # Long prompt with context
    print("\n[测试3] 长 prompt with context")
    long_prompt = """你是一个专业的JSON助手，擅长输出结构化数据。

请按照以下要求输出JSON：
1. 使用 JSON 格式
2. 包含 is_correct 字段（布尔值）
3. 包含 confidence 字段（0-1之间的浮点数）
4. 包含 reason 字段（字符串）

输出示例：{"is_correct": true, "confidence": 0.9, "reason": "测试"}

现在请输出：{"is_correct": true, "confidence": 0.8, "reason": "成功"}"""
    result = await gateway.acomplete(
        prompt=long_prompt,
        model_hint="glm-4.5-air",
        max_tokens=100,
        temperature=0.5,
    )
    print(f"  响应长度: {len(result.text)}")
    print(f"  响应内容: {result.text}")

    # Test with messages format
    print("\n[测试4] Messages 格式")
    result = await gateway.acomplete(
        prompt="输出JSON",
        messages=[
            {"role": "system", "content": "你是一个JSON输出助手，只输出JSON格式。"},
            {"role": "user", "content": "请输出: {\"result\": true}"}
        ],
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.5,
    )
    print(f"  响应长度: {len(result.text)}")


if __name__ == "__main__":
    asyncio.run(test_longer_prompts())
