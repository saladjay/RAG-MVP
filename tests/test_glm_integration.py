"""
GLM Integration Test Script

Test script for verifying GLM (智谱AI) integration with RAG Service.

Usage:
    # Make sure GLM_API_KEY is set in .env file
    uv run python test_glm_integration.py
"""

import asyncio
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_glm_gateway():
    """Test GLM gateway basic functionality."""

    print("=" * 80)
    print("GLM Integration Test")
    print("=" * 80)

    # Import after path is set
    from rag_service.inference.gateway import get_glm_gateway
    from rag_service.config import get_settings

    # Check configuration
    print("\n[1] Checking Configuration")
    settings = get_settings()

    print(f"  GLM URL: {settings.glm.url}")
    print(f"  GLM Model: {settings.glm.model}")
    print(f"  GLM API Key: {'***' + settings.glm.api_key[-4:] if settings.glm.api_key else 'Not configured'}")
    print(f"  GLM Timeout: {settings.glm.timeout}s")
    print(f"  GLM Enabled: {settings.glm.enabled}")

    if not settings.glm.enabled:
        print("\n  [ERROR] GLM is not configured. Please set GLM_API_KEY in .env file")
        return False

    # Get gateway
    print("\n[2] Initializing GLM Gateway")
    try:
        gateway = await get_glm_gateway()
        print(f"  [OK] Gateway initialized successfully")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize gateway: {e}")
        return False

    # Test simple completion
    print("\n[3] Testing Simple Completion")
    test_prompt = "你好，请用一句话介绍你自己。"

    try:
        result = await gateway.acomplete(
            prompt=test_prompt,
            max_tokens=100,
            temperature=0.7,
        )

        print(f"  [OK] Completion successful")
        print(f"  Model: {result.model}")
        print(f"  Input Tokens: {result.input_tokens}")
        print(f"  Output Tokens: {result.output_tokens}")
        print(f"  Total Tokens: {result.total_tokens}")
        print(f"  Latency: {result.latency_ms:.2f}ms")
        print(f"  Response: {result.text[:200]}...")

    except Exception as e:
        print(f"  [ERROR] Completion failed: {e}")
        return False

    # Test chat format
    print("\n[4] Testing Chat Format (Messages)")
    test_messages = [
        {"role": "system", "content": "你是一个专业的AI助手。"},
        {"role": "user", "content": "什么是Python？请用一句话回答。"},
    ]

    try:
        result = await gateway.acomplete(
            prompt="",  # Ignored when messages are provided
            messages=test_messages,
            max_tokens=100,
            temperature=0.5,
        )

        print(f"  [OK] Chat completion successful")
        print(f"  Response: {result.text[:200]}...")

    except Exception as e:
        print(f"  [ERROR] Chat completion failed: {e}")
        return False

    # Test available models
    print("\n[5] Checking Available Models")
    models = gateway.get_available_models()
    print(f"  Available models: {len(models)}")
    for model in models:
        print(f"    - {model['model_id']} ({model['provider']})")

    print("\n" + "=" * 80)
    print("GLM Integration Test: PASSED")
    print("=" * 80)

    return True


async def main():
    """Main test entry point."""
    try:
        success = await test_glm_gateway()
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
