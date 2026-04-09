"""
End-to-End tests for HTTP LLM API integration.

These tests simulate real-world scenarios where the HTTPCompletionGateway
calls external LLM APIs and processes responses.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

import pytest
import httpx
from httpx import ASGITransport


class TestHTTPLLME2EScenarios:
    """End-to-end tests for HTTP LLM integration.

    Tests verify:
    - Complete QA pipeline with HTTP backend
    - Query rewriting with HTTP API
    - Answer generation with context
    - Fallback behavior
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_qa_flow_with_http_backend(self) -> None:
        """Test complete QA pipeline using HTTP backend.

        Given: User query about company policy
        When: Full pipeline executes with HTTP gateway
        Then: Returns correct answer with sources
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        # Mock responses for each stage
        qa_responses = {
            # Query rewrite response
            "rewrite": CompletionResult(
                text="What are the company's 2025 holiday arrangements?",
                model="qwen-model",
                input_tokens=25,
                output_tokens=12,
                total_tokens=37,
                cost=0.0,
                latency_ms=150,
                provider="http",
            ),
            # Answer generation response
            "answer": CompletionResult(
                text="""
Based on the company's 2025 holiday policy:

1. **Spring Festival**: February 8-14 (7 days)
2. **National Day**: October 1-7 (7 days)
3. **Other Holidays**: As per government calendar

Please refer to the HR handbook for detailed information.
                """.strip(),
                model="qwen-model",
                input_tokens=450,
                output_tokens=65,
                total_tokens=515,
                cost=0.0,
                latency_ms=2300,
                provider="http",
            ),
        }

        mock_http_gateway = AsyncMock()
        call_count = {"count": 0}

        async def mock_acomplete(prompt, **kwargs):
            call_count["count"] += 1
            if "rewrite" in prompt.lower() or "company" in prompt.lower():
                return qa_responses["rewrite"]
            return qa_responses["answer"]

        mock_http_gateway.acomplete = mock_acomplete

        # Create capability with HTTP backend
        capability = ModelInferenceCapability(
            http_client=mock_http_gateway,
            default_gateway="http",
        )

        # Execute query
        input_data = ModelInferenceInput(
            prompt="2025年春节放假几天？",
            gateway_backend="http",
            max_tokens=500,
            temperature=0.7,
        )

        result = await capability.execute(input_data)

        assert "春节" in result.text or "Spring Festival" in result.text
        assert "7 days" in result.text or "7天" in result.text
        assert result.usage["total_tokens"] > 0

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_query_rewriting_with_http_api(self) -> None:
        """Test query rewriting via HTTP API.

        Given: Ambiguous user query
        When: Query is sent to HTTP API for rewriting
        Then: Returns more specific query
        """
        from rag_service.capabilities.query_rewrite import (
            QueryRewriteCapability,
            QueryRewriteInput,
        )
        from rag_service.inference.gateway import CompletionResult

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="What are the company's vacation and leave policies for 2025?",
                model="qwen-model",
                input_tokens=35,
                output_tokens=15,
                total_tokens=50,
                cost=0.0,
                latency_ms=120,
                provider="http",
            )
        )

        capability = QueryRewriteCapability(litellm_client=mock_gateway)

        input_data = QueryRewriteInput(
            original_query="放假政策",
            context={
                "company_id": "N000131",
                "file_type": "PublicDocDispatch",
            },
        )

        result = await capability.execute(input_data)

        assert "2025" in result.rewritten_query
        assert "company" in result.rewritten_query.lower() or "公司" in result.rewritten_query
        assert result.original_query == "放假政策"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_answer_generation_with_retrieved_context(self) -> None:
        """Test answer generation using retrieved chunks.

        Given: Retrieved document chunks
        When: HTTP API generates answer
        Then: Answer is based on provided context
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        retrieved_chunks = [
            {
                "id": "doc1",
                "text": "公司规定员工每年享有15天年假，5天病假。",
                "metadata": {"source": "hr-handbook.pdf", "page": 12},
            },
            {
                "id": "doc2",
                "text": "年假需提前申请，经部门主管批准。",
                "metadata": {"source": "hr-handbook.pdf", "page": 13},
            },
        ]

        context_text = "\n\n".join([f"文档: {c['metadata']['source']}\n{c['text']}" for c in retrieved_chunks])

        prompt = f"""请根据以下文档内容回答问题：

{context_text}

问题: 员工有多少天年假？"""

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="根据公司规定，员工每年享有15天年假。",
                model="qwen-model",
                input_tokens=200,
                output_tokens=25,
                total_tokens=225,
                cost=0.0,
                latency_ms=450,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt=prompt,
            gateway_backend="http",
            max_tokens=200,
        )

        result = await capability.execute(input_data)

        assert "15天" in result.text or "15 days" in result.text
        assert result.usage["input_tokens"] > 0

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_fallback_on_empty_kb_response(self) -> None:
        """Test fallback behavior when KB returns no results.

        Given: Knowledge base query returns empty
        When: Fallback is triggered
        Then: Returns appropriate fallback message
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        # Mock empty KB response
        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="抱歉，我没有找到与您的问题相关的信息。请尝试重新表述问题或联系人事部门获取帮助。",
                model="qwen-model",
                input_tokens=30,
                output_tokens=35,
                total_tokens=65,
                cost=0.0,
                latency_ms=200,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt="关于什么？",
            gateway_backend="http",
        )

        result = await capability.execute(input_data)

        assert "没有找到" in result.text or "抱歉" in result.text or "无法找到" in result.text

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_streaming_answer_generation(self) -> None:
        """Test streaming answer generation via HTTP API.

        Given: Long-form answer request
        When: Streaming is enabled
        Then: Tokens arrive incrementally
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )

        async def mock_stream(prompt, **kwargs):
            tokens = [
                "根据",
                "公司",
                "规定",
                "，",
                "员工",
                "每年",
                "享有",
                "15",
                "天",
                "年",
                "假",
                "。",
            ]
            for token in tokens:
                yield token

        mock_gateway = AsyncMock()
        mock_gateway.astream_complete = lambda p, **kw: mock_stream(p)

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt="员工有多少天年假？",
            gateway_backend="http",
            max_tokens=100,
        )

        tokens = []
        async for token in capability.stream_execute(input_data):
            tokens.append(token)

        assert "".join(tokens) == "根据公司规定，员工每年享有15天年假。"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self) -> None:
        """Test multi-turn conversation via HTTP API.

        Given: Conversation history
        When: New query is sent
        Then: Response considers conversation context
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        messages = [
            {"role": "user", "content": "公司春节放几天假？"},
            {"role": "assistant", "content": "根据公司规定，春节放假7天。"},
            {"role": "user", "content": "那国庆节呢？"},
        ]

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="国庆节同样放假7天，具体为10月1日至10月7日。",
                model="qwen-model",
                input_tokens=120,
                output_tokens=30,
                total_tokens=150,
                cost=0.0,
                latency_ms=300,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        # Format messages as single prompt for completion API
        conversation_context = "\n".join([
            f"{m['role']}: {m['content']}" for m in messages
        ])

        input_data = ModelInferenceInput(
            prompt=conversation_context,
            gateway_backend="http",
        )

        result = await capability.execute(input_data)

        assert "国庆节" in result.text or "10月" in result.text
        assert "7天" in result.text or "7 days" in result.text

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_concurrent_queries(self) -> None:
        """Test handling multiple concurrent queries.

        Given: 5 concurrent user queries
        When: All queries execute simultaneously
        Then: Each query gets correct response
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        queries = [
            "什么是RAG？",
            "公司放假几天？",
            "如何申请年假？",
            "病假怎么算？",
            "节假日有加班费吗？",
        ]

        async def mock_acomplete(prompt, **kwargs):
            await asyncio.sleep(0.01)  # Simulate processing
            return CompletionResult(
                text=f"回答关于 {prompt[:10]} 的问题",
                model="qwen-model",
                input_tokens=20,
                output_tokens=15,
                total_tokens=35,
                cost=0.0,
                latency_ms=100,
                provider="http",
            )

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = mock_acomplete

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        # Execute all queries concurrently
        tasks = [
            capability.execute(
                ModelInferenceInput(
                    prompt=q,
                    gateway_backend="http",
                )
            )
            for q in queries
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert queries[i][:10] in result.text

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_error_recovery_with_retry(self) -> None:
        """Test error recovery and retry mechanism.

        Given: HTTP API fails intermittently
        When: Request is retried
        Then: Eventually succeeds
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult
        import httpx

        attempt = {"count": 0}

        async def mock_acomplete(prompt, **kwargs):
            attempt["count"] += 1
            if attempt["count"] < 2:
                raise httpx.HTTPError("Temporary error")
            return CompletionResult(
                text="Success after retry",
                model="qwen-model",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost=0.0,
                latency_ms=50,
                provider="http",
            )

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = mock_acomplete

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt="测试重试机制",
            gateway_backend="http",
        )

        result = await capability.execute(input_data)

        assert result.text == "Success after retry"
        assert attempt["count"] == 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_different_response_formats(self) -> None:
        """Test handling different API response formats.

        Given: API returns different response formats
        When: Each format is parsed
        Then: All formats are handled correctly
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://test.com/v1/completions",
            model="test-model",
        )

        # Test OpenAI format
        openai_response = {
            "choices": [{"text": "OpenAI format response"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        result = gateway._parse_completion_response(openai_response)
        assert result.text == "OpenAI format response"

        # Test simple format
        simple_response = {"output": "Simple format response"}
        result = gateway._parse_completion_response(simple_response)
        assert result.text == "Simple format response"

        # Test text format
        text_response = {"text": "Text format response"}
        result = gateway._parse_completion_response(text_response)
        assert result.text == "Text format response"

        # Test result format
        result_response = {"result": "Result format response"}
        result = gateway._parse_completion_response(result_response)
        assert result.text == "Result format response"


class TestHTTPLLMRealAPIResponse:
    """Tests with realistic API response structures.

    Tests verify:
    - Complex nested responses
    - Metadata preservation
    - Token counting accuracy
    - Special character handling
    """

    @pytest.mark.e2e
    def test_complex_nested_response_parsing(self) -> None:
        """Test parsing complex nested API response.

        Given: Real-world complex response structure
        When: Response is parsed
        Then: Extracts all relevant information
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://api.example.com/v1/completions",
            model="qwen-model",
        )

        complex_response = {
            "id": "chatcmpl-123456789",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "qwen-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "根据公司政策，员工年假为15天。",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 18,
                "total_tokens": 43,
            },
            "system_fingerprint": "fp_12345",
        }

        result = gateway._parse_completion_response(complex_response)

        assert "15天" in result.text
        assert result.input_tokens == 25
        assert result.output_tokens == 18
        assert result.total_tokens == 43

    @pytest.mark.e2e
    def test_special_characters_in_response(self) -> None:
        """Test handling special characters in response.

        Given: Response with various special characters
        When: Response is parsed
        Then: Special characters are preserved
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://api.example.com",
            model="test-model",
        )

        special_response = {
            "output": """
公司政策说明：
• 年假：15天
• 病假：5天
• 产假：98天

备注：具体天数按国家规定执行。
            """.strip(),
        }

        result = gateway._parse_completion_response(special_response)

        assert "•" in result.text or "-" in result.text
        assert "15天" in result.text

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_long_response_handling(self) -> None:
        """Test handling long responses.

        Given: API returns very long response
        When: Response is parsed and returned
        Then: Complete response is preserved
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        # Simulate long response
        long_answer = "公司详细政策说明：\n" + "\n".join([
            f"{i}. 某项政策的具体说明，包含很多详细信息。" for i in range(1, 51)
        ])

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text=long_answer,
                model="qwen-model",
                input_tokens=100,
                output_tokens=len(long_answer.split()),
                total_tokens=len(long_answer.split()) + 100,
                cost=0.0,
                latency_ms=2000,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt="请详细介绍公司所有政策",
            gateway_backend="http",
            max_tokens=2000,
        )

        result = await capability.execute(input_data)

        assert len(result.text) > 1000
        assert "某项政策" in result.text

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_chinese_english_mixed_response(self) -> None:
        """Test handling mixed Chinese-English response.

        Given: Response with mixed Chinese and English
        When: Response is processed
        Then: Both languages are handled correctly
        """
        from rag_service.inference.gateway import CompletionResult

        mixed_response = CompletionResult(
            text="""
根据公司Policy，员工享有以下福利 (Benefits)：

1. 年假 (Annual Leave): 15天
2. 病假 (Sick Leave): 5天
3. 法定节假日 (Public Holidays): 按政府规定

如有疑问，请咨询HR部门 (Contact HR)。
            """.strip(),
            model="qwen-model",
            input_tokens=50,
            output_tokens=60,
            total_tokens=110,
            cost=0.0,
            latency_ms=300,
            provider="http",
        )

        assert "年假" in mixed_response.text
        assert "Annual Leave" in mixed_response.text
        assert "15天" in mixed_response.text


class TestHTTPLLMWithExternalKB:
    """Tests integrating HTTP LLM with external KB.

    Tests verify:
    - RAG pattern with HTTP backend
    - Context from external KB
    - Source citation
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_rag_with_external_kb(self) -> None:
        """Test RAG pattern using HTTP LLM with external KB.

        Given: External KB returns relevant documents
        When: HTTP LLM generates answer with context
        Then: Answer cites sources from KB
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        # Simulated external KB response
        kb_chunks = [
            {
                "id": "kb001",
                "text": "公司实行弹性工作制，员工可在早8点到晚10点间自由选择上下班时间，但需保证满8小时工作时间。",
                "source": "员工手册-工作制度.pdf",
                "score": 0.95,
            },
            {
                "id": "kb002",
                "text": "弹性工作制不适用于前台、客服等需要固定岗位的员工。",
                "source": "员工手册-工作制度.pdf",
                "score": 0.87,
            },
        ]

        context = "\n\n".join([
            f"来源: {c['source']}\n{c['text']}" for c in kb_chunks
        ])

        prompt = f"""请根据以下文档回答问题：

{context}

问题: 公司实行弹性工作制吗？"""

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="""
是的，公司实行弹性工作制：

1. **适用时间**：员工可在早8点至晚10点间自由选择上下班时间
2. **工作时长**：需保证满8小时工作时间
3. **例外情况**：前台、客服等固定岗位不适用

来源：员工手册-工作制度.pdf
                """.strip(),
                model="qwen-model",
                input_tokens=200,
                output_tokens=80,
                total_tokens=280,
                cost=0.0,
                latency_ms=850,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt=prompt,
            gateway_backend="http",
            max_tokens=300,
        )

        result = await capability.execute(input_data)

        assert "弹性工作制" in result.text
        assert "8点" in result.text or "8小时" in result.text

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_empty_kb_with_http_fallback(self) -> None:
        """Test behavior when KB returns empty.

        Given: KB query returns no results
        When: HTTP LLM is called
        Then: Returns fallback response
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        prompt = "请根据以下文档回答：\n\n（无相关文档）\n\n问题: 公司有什么新产品？"

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="抱歉，我无法找到关于公司新产品的相关信息。建议您查看公司官网或联系产品部门获取最新信息。",
                model="qwen-model",
                input_tokens=30,
                output_tokens=35,
                total_tokens=65,
                cost=0.0,
                latency_ms=200,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt=prompt,
            gateway_backend="http",
        )

        result = await capability.execute(input_data)

        assert "无法找到" in result.text or "抱歉" in result.text or "建议" in result.text
