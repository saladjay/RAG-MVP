"""
Test short prompt and see actual response
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway


async def test_short_prompt():
    """Test short prompt"""

    gateway = await get_gateway()

    print("=" * 80)
    print("短 Prompt 测试")
    print("=" * 80)

    prompt = "请输出JSON: {\"ok\": true}"
    print(f"Prompt: '{prompt}'")

    result = await gateway.acomplete(
        prompt=prompt,
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.5,
    )

    print(f"\n响应:")
    print(f"  长度: {len(result.text)}")
    print(f"  内容: '{result.text}'")
    print(f"  Repr: {repr(result.text)}")

    # Also try with normal questions
    print("\n" + "=" * 80)
    print("对比：正常问答")
    print("=" * 80)

    result2 = await gateway.acomplete(
        prompt="1+1等于几？",
        model_hint="glm-4.5-air",
        max_tokens=50,
        temperature=0.5,
    )
    print(f"响应: '{result2.text}'")


if __name__ == "__main__":
    asyncio.run(test_short_prompt())
