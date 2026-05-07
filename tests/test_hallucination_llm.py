"""Test LLM-based Hallucination Detection"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rag_service.capabilities.hallucination_detection import (
    HallucinationDetectionCapability,
    HallucinationCheckInput,
)


async def test_llm_hallucination_detection():
    """Test LLM-based hallucination detection."""
    print("=" * 60)
    print("LLM-based Hallucination Detection Test")
    print("=" * 60)
    print()

    # Test case 1: Answer based on context (should pass)
    print("Test 1: Answer based on context (should PASS)")
    print("-" * 60)

    detector = HallucinationDetectionCapability()

    input1 = HallucinationCheckInput(
        generated_answer="根据公司规定，春节假期为7天，具体安排将根据国家法定节假日确定。",
        retrieved_chunks=[
            {
                "id": "1",
                "content": "公司假期管理制度：春节假期按照国家法定节假日执行，通常为7天。",
                "source_doc": "假期管理制度.doc",
            },
            {
                "id": "2",
                "content": "员工请休年假需提前15天申请，经部门领导批准后方可休假。",
                "source_doc": "考勤管理办法.doc",
            },
        ],
        threshold=0.6,
        method="llm",
        trace_id="test-1",
    )

    result1 = await detector.execute(input1)

    print(f"Passed: {result1.passed}")
    print(f"Confidence: {result1.confidence}")
    print(f"Method: {result1.verification_method}")
    print(f"Reasoning: {result1.reasoning[:200] if result1.reasoning else 'N/A'}...")
    print()

    # Test case 2: Answer NOT based on context (should fail)
    print("Test 2: Answer NOT based on context (should FAIL)")
    print("-" * 60)

    input2 = HallucinationCheckInput(
        generated_answer="公司提供免费午餐和下午茶，员工可以享受弹性工作时间，周末双休。",
        retrieved_chunks=[
            {
                "id": "1",
                "content": "公司假期管理制度：春节假期按照国家法定节假日执行，通常为7天。",
                "source_doc": "假期管理制度.doc",
            },
            {
                "id": "2",
                "content": "员工请休年假需提前15天申请，经部门领导批准后方可休假。",
                "source_doc": "考勤管理办法.doc",
            },
        ],
        threshold=0.6,
        method="llm",
        trace_id="test-2",
    )

    result2 = await detector.execute(input2)

    print(f"Passed: {result2.passed}")
    print(f"Confidence: {result2.confidence}")
    print(f"Method: {result2.verification_method}")
    print(f"Reasoning: {result2.reasoning[:200] if result2.reasoning else 'N/A'}...")
    print(f"Flagged claims: {result2.flagged_claims}")
    print()

    # Test case 3: Partially correct answer (edge case)
    print("Test 3: Partially correct answer (EDGE CASE)")
    print("-" * 60)

    input3 = HallucinationCheckInput(
        generated_answer="春节假期为7天，员工还可以享受每年10天带薪年假。",
        retrieved_chunks=[
            {
                "id": "1",
                "content": "公司假期管理制度：春节假期按照国家法定节假日执行，通常为7天。",
                "source_doc": "假期管理制度.doc",
            },
        ],
        threshold=0.6,
        method="llm",
        trace_id="test-3",
    )

    result3 = await detector.execute(input3)

    print(f"Passed: {result3.passed}")
    print(f"Confidence: {result3.confidence}")
    print(f"Method: {result3.verification_method}")
    print(f"Reasoning: {result3.reasoning[:200] if result3.reasoning else 'N/A'}...")
    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Test 1 (should pass): {'PASS' if result1.passed else 'FAIL'}")
    print(f"Test 2 (should fail): {'FAIL' if not result2.passed else 'PASS (unexpected)'}")
    print(f"Test 3 (edge case): {'PASS' if result3.passed else 'FAIL'}")
    print()

    # Health check
    print("Health Status:")
    health = detector.get_health()
    for key, value in health.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    print("Note: Make sure CLOUD_COMPLETION_URL is configured in .env")
    print()

    asyncio.run(test_llm_hallucination_detection())
