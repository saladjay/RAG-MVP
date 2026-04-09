"""
Debug JSON parsing for GLM evaluation
"""

import asyncio
import json
import re
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_service.inference.gateway import get_gateway


async def test_json_parsing():
    """Test JSON parsing from GLM"""

    gateway = await get_gateway()

    # Simple test prompt
    prompt = """请输出JSON格式：{"is_correct": true, "confidence": 0.9, "reason": "测试"}"""

    print("=" * 80)
    print("JSON 解析测试")
    print("=" * 80)
    print(f"Prompt: {prompt}")
    print()

    result = await gateway.acomplete(
        prompt=prompt,
        model_hint="glm-4.5-air",
        max_tokens=100,
        temperature=0.5,
    )

    response_text = result.text.strip()
    print(f"[原始响应]")
    print(f"  长度: {len(response_text)}")
    print(f"  内容: {response_text}")
    print()

    # Try different parsing methods
    print("[解析方法]")

    # Method 1: Direct parse
    print("\n1. 直接解析:")
    try:
        data = json.loads(response_text)
        print(f"   成功: {data}")
    except Exception as e:
        print(f"   失败: {e}")

    # Method 2: Extract from ```json```
    print("\n2. 从 ```json``` 提取:")
    try:
        if "```json" in response_text:
            extracted = response_text.split("```json")[1].split("```")[0].strip()
            print(f"   提取后: {extracted}")
            data = json.loads(extracted)
            print(f"   成功: {data}")
    except Exception as e:
        print(f"   失败: {e}")

    # Method 3: Manual regex extraction
    print("\n3. 手动正则提取:")
    try:
        is_correct_match = re.search(r'"is_correct"\s*:\s*(true|false)', response_text)
        confidence_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', response_text)
        reason_match = re.search(r'"reason"\s*:\s*"([^"]*)"', response_text)

        print(f"   is_correct: {is_correct_match.group(1) if is_correct_match else 'Not found'}")
        print(f"   confidence: {confidence_match.group(1) if confidence_match else 'Not found'}")
        print(f"   reason: {reason_match.group(1) if reason_match else 'Not found'}")
    except Exception as e:
        print(f"   失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_json_parsing())
