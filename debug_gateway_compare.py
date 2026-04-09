"""
Test direct GLM Gateway vs LiteLLM Gateway
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway, get_glm_gateway


async def test_both_gateways():
    """Test both gateways"""

    print("=" * 80)
    print("Gateway 对比测试")
    print("=" * 80)

    prompt = "1+1等于几？输出JSON格式: {\"answer\": 2}"

    # Test 1: LiteLLM Gateway with glm-4.5-air
    print("\n[测试1] LiteLLM Gateway (glm-4.5-air)")
    try:
        gateway = await get_gateway()
        result = await gateway.acomplete(
            prompt=prompt,
            model_hint="glm-4.5-air",
            max_tokens=50,
            temperature=0.7,
        )
        print(f"  响应长度: {len(result.text)}")
        print(f"  响应内容: '{result.text}'")
    except Exception as e:
        print(f"  错误: {e}")

    # Test 2: Direct GLM Gateway
    print("\n[测试2] 直接 GLM Gateway")
    try:
        gateway = await get_glm_gateway()
        result = await gateway.acomplete(
            prompt=prompt,
            max_tokens=50,
            temperature=0.7,
        )
        print(f"  响应长度: {len(result.text)}")
        print(f"  响应内容: '{result.text}'")
    except Exception as e:
        print(f"  错误: {e}")

    # Test 3: Simple question with both
    print("\n[测试3] 简单问题对比")
    simple_prompt = "1+1等于几？"

    print("  LiteLLM Gateway:")
    gateway = await get_gateway()
    result1 = await gateway.acomplete(
        prompt=simple_prompt,
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.7,
    )
    print(f"    响应: '{result1.text}'")

    print("  GLM Gateway:")
    gateway = await get_glm_gateway()
    result2 = await gateway.acomplete(
        prompt=simple_prompt,
        max_tokens=50,
        temperature=0.7,
    )
    print(f"    响应: '{result2.text}'")


if __name__ == "__main__":
    asyncio.run(test_both_gateways())
