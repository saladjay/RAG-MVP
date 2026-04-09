"""
Test different temperatures for GLM
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway


async def test_temperatures():
    """Test different temperatures"""

    gateway = await get_gateway()

    print("=" * 80)
    print("GLM 温度测试")
    print("=" * 80)

    prompt = "请输出JSON: {\"answer\": 2}"

    for temp in [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
        print(f"\n[Temperature: {temp}]")
        result = await gateway.acomplete(
            prompt=prompt,
            model_hint="glm-4.5-air",
            max_tokens=50,
            temperature=temp,
        )
        response = result.text.strip()
        print(f"  长度: {len(response)}")
        print(f"  内容: '{response}'")


if __name__ == "__main__":
    asyncio.run(test_temperatures())
