"""
Debug GLM API response
"""

import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import httpx


async def test_glm_api_direct():
    """Test GLM API directly"""

    api_key = os.getenv("GLM_API_KEY")
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    print("=" * 80)
    print("GLM API 直接调用测试")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"API Key: {'...' + api_key[-4:] if api_key else 'Not set'}")
    print()

    # Test 1: Simple question
    print("[测试1] 简单问题")
    payload = {
        "model": "glm-4.5-air",
        "messages": [{"role": "user", "content": "1+1等于几？"}],
        "max_tokens": 50,
        "temperature": 0.7,
    }

    print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            print(f"\n[响应状态码] {response.status_code}")
            print(f"[响应 JSON]")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                print(f"\n[提取的内容] 长度: {len(content)}")
                print(f"[提取的内容] '{content}'")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: JSON request
    print("\n" + "=" * 80)
    print("[测试2] JSON 请求")
    payload2 = {
        "model": "glm-4.5-air",
        "messages": [{"role": "user", "content": "请输出JSON: {\"answer\": 2}"}],
        "max_tokens": 50,
        "temperature": 0.7,
    }

    print(f"Payload: {json.dumps(payload2, ensure_ascii=False)}")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload2, headers=headers)
            response.raise_for_status()
            data = response.json()

            print(f"\n[响应状态码] {response.status_code}")
            print(f"[响应 JSON]")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                print(f"\n[提取的内容] 长度: {len(content)}")
                print(f"[提取的内容] '{content}'")

    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(test_glm_api_direct())
