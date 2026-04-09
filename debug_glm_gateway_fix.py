"""
Test GLM Gateway directly with reasoning_content fix
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_glm_gateway


async def test_glm_gateway():
    """Test GLM gateway after fix"""

    gateway = await get_glm_gateway()

    print("=" * 80)
    print("GLM Gateway 测试 (reasoning_content 修复后)")
    print("=" * 80)

    # Test 1: Simple question
    print("\n[测试1] 简单问题")
    result = await gateway.acomplete(
        prompt="1+1等于几？",
        max_tokens=50,
        temperature=0.7,
    )
    print(f"  响应长度: {len(result.text)}")
    print(f"  响应内容: '{result.text}'")

    # Test 2: JSON request
    print("\n[测试2] JSON 请求")
    result = await gateway.acomplete(
        prompt="请输出JSON: {\"answer\": 2}",
        max_tokens=100,
        temperature=0.7,
    )
    print(f"  响应长度: {len(result.text)}")
    print(f"  响应内容: '{result.text}'")


if __name__ == "__main__":
    asyncio.run(test_glm_gateway())
