"""
LiteLLM + GLM Integration Test Script

Test script for using GLM (智谱AI) models through LiteLLM.

Prerequisites:
1. Set GLM_API_KEY in .env file or as environment variable
2. LiteLLM config should include GLM models (see litellm_config.yaml)

Usage:
    uv run python test_litellm_glm.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_litellm_glm():
    """Test GLM through LiteLLM."""

    print("=" * 80)
    print("LiteLLM + GLM Integration Test")
    print("=" * 80)

    # Check environment
    print("\n[1] Checking Environment")
    api_key = os.getenv("GLM_API_KEY")
    config_path = os.getenv("LITELLM_CONFIG_PATH", "litellm_config.yaml")

    print(f"  GLM_API_KEY: {'***' + api_key[-4:] if api_key else 'Not set'}")
    print(f"  LITELLM_CONFIG_PATH: {config_path}")

    # Check if config file exists
    if not Path(config_path).exists():
        print(f"  [WARNING] Config file not found: {config_path}")
        print("  [INFO] Will use direct model specification")
    else:
        print(f"  [OK] Config file found")

    # Test 1: Direct GLM call without config file
    print("\n[2] Testing Direct GLM Call (glm-4.5-air)")
    print("  [INFO] Using OpenAI-compatible format for GLM")

    try:
        from litellm import acompletion

        # GLM uses OpenAI-compatible API, need to specify api_base
        response = await acompletion(
            model="openai/glm-4.5-air",  # Use openai/ prefix with custom api_base
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
            api_base="https://open.bigmodel.cn/api/paas/v4",
            api_key=api_key,
            max_tokens=100,
            temperature=0.7,
        )

        content = response.choices[0].message.content
        print(f"  [OK] Direct call successful")
        print(f"  Response: {content[:100]}...")

    except Exception as e:
        print(f"  [ERROR] Direct call failed: {e}")
        if "api_key" in str(e).lower() or "auth" in str(e).lower() or "401" in str(e):
            print("  [HINT] Please set GLM_API_KEY environment variable")
        return False

    # Test 2: Using LiteLLMGateway (if available)
    print("\n[3] Testing LiteLLMGateway (if available)")

    try:
        from rag_service.inference.gateway import get_gateway

        gateway = await get_gateway()

        # Try to use GLM model
        result = await gateway.acomplete(
            prompt="什么是Python？请用一句话回答。",
            model_hint="glm-4.5-air",
            max_tokens=100,
            temperature=0.5,
        )

        print(f"  [OK] Gateway call successful")
        print(f"  Model: {result.model}")
        print(f"  Response: {result.text[:100]}...")

    except Exception as e:
        print(f"  [INFO] Gateway test skipped: {e}")

    # Test 3: Different GLM models
    print("\n[4] Testing Different GLM Models")

    models = [
        ("openai/glm-4.5", "GLM-4.5 (Flagship)"),
        ("openai/glm-4.5-air", "GLM-4.5-air (Cost-effective)"),
        ("openai/glm-4-flash", "GLM-4-flash (Fast)"),
    ]

    from litellm import acompletion

    for model_id, model_name in models:
        try:
            response = await acompletion(
                model=model_id,
                messages=[{"role": "user", "content": "1+1=?"}],
                api_base="https://open.bigmodel.cn/api/paas/v4",
                api_key=api_key,
                max_tokens=50,
                timeout=10,
            )
            content = response.choices[0].message.content
            print(f"  [OK] {model_name}: {content.strip()[:50]}")
        except Exception as e:
            print(f"  [SKIP] {model_name}: {str(e)[:50]}...")

    # Test 4: Chat format with system message
    print("\n[5] Testing Chat Format with System Message")

    try:
        response = await acompletion(
            model="openai/glm-4.5-air",
            messages=[
                {"role": "system", "content": "你是一个专业的AI助手。"},
                {"role": "user", "content": "请用三个词描述你自己。"},
            ],
            api_base="https://open.bigmodel.cn/api/paas/v4",
            api_key=api_key,
            max_tokens=50,
        )

        content = response.choices[0].message.content
        print(f"  [OK] Chat format successful")
        print(f"  Response: {content}")

    except Exception as e:
        print(f"  [ERROR] Chat format failed: {e}")

    print("\n" + "=" * 80)
    print("LiteLLM + GLM Integration Test: COMPLETED")
    print("=" * 80)

    return True


async def main():
    """Main test entry point."""
    try:
        success = await test_litellm_glm()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INFO] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
