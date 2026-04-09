"""
Debug GLM response with different prompts
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway


async def test_glm_response():
    """Test different prompts with GLM"""

    gateway = await get_gateway()

    print("=" * 80)
    print("GLM 响应测试")
    print("=" * 80)

    # Test 1: Simple prompt
    print("\n[测试1] 简单问题")
    result = await gateway.acomplete(
        prompt="1+1=?",
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.7,
    )
    print(f"响应: '{result.text}'")
    print(f"长度: {len(result.text)}")

    # Test 2: JSON request (简单)
    print("\n[测试2] 简单 JSON 请求")
    result = await gateway.acomplete(
        prompt='请输出JSON: {"answer": "2"}',
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.1,
    )
    print(f"响应: '{result.text}'")
    print(f"长度: {len(result.text)}")

    # Test 3: Complex JSON prompt (评估用的)
    print("\n[测试3] 复杂 JSON 请求")
    prompt = """请只输出JSON格式：
{
    "is_correct": true,
    "reason": "测试"
}"""
    result = await gateway.acomplete(
        prompt=prompt,
        model_hint="glm-4.5-air",
        max_tokens=100,
        temperature=0.1,
    )
    print(f"响应: '{result.text}'")
    print(f"长度: {len(result.text)}")

    # Test 4: Higher temperature
    print("\n[测试4] 使用更高温度 (0.7)")
    prompt = """请输出JSON: {"result": true}"""
    result = await gateway.acomplete(
        prompt=prompt,
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.7,
    )
    print(f"响应: '{result.text}'")
    print(f"长度: {len(result.text)}")

    # Test 5: With system message style
    print("\n[测试5] 消息格式")
    result = await gateway.acomplete(
        prompt="请输出JSON: {\"ok\": true}",
        messages=[
            {"role": "system", "content": "你是一个JSON助手，只输出JSON。"},
            {"role": "user", "content": "输出 {\"ok\": true}"}
        ],
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.1,
    )
    print(f"响应: '{result.text}'")
    print(f"长度: {len(result.text)}")


if __name__ == "__main__":
    asyncio.run(test_glm_response())
