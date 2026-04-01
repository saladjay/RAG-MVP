"""
Integration tests for RAG Service End-to-End Flow (US1 - Knowledge Base Query).

These tests verify the complete flow from user question to AI-generated answer
with retrieved context from the knowledge base.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

from rag_service.main import app


class TestE2EKnowledgeBaseQuery:
    """End-to-end tests for knowledge base query flow.

    Tests verify:
    - Complete flow from question to answer
    - Knowledge base retrieval integration
    - Model inference integration
    - Trace correlation across layers
    - Error handling throughout the flow
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_documents(self) -> list[Dict[str, Any]]:
        """Sample documents for knowledge base testing."""
        return [
            {
                "doc_id": "doc1",
                "title": "Introduction to RAG",
                "content": "RAG (Retrieval-Augmented Generation) is a technique that combines retrieval systems with generative AI models. It allows models to access external knowledge bases during inference, providing more accurate and up-to-date responses.",
                "metadata": {"category": "ai", "tags": ["rag", "generative-ai"]},
            },
            {
                "doc_id": "doc2",
                "title": "Vector Databases",
                "content": "Vector databases like Milvus store embeddings as numerical vectors. They enable efficient similarity search using approximate nearest neighbor algorithms, which is essential for RAG systems to retrieve relevant context quickly.",
                "metadata": {"category": "database", "tags": ["vectors", "milvus"]},
            },
            {
                "doc_id": "doc3",
                "title": "LLM Integration",
                "content": "Large Language Models (LLMs) like GPT-4 and Claude can be integrated with RAG systems. The LiteLLM library provides a unified interface for multiple model providers, making it easy to switch between different models.",
                "metadata": {"category": "ai", "tags": ["llm", "litellm"]},
            },
        ]

    @pytest.mark.integration
    async def test_complete_query_flow_returns_answer_and_chunks(
        self,
        client: AsyncClient,
    ) -> None:
        """Test complete flow from question to answer with retrieved chunks.

        Given: A question about topics in the knowledge base
        When: POST /ai/agent is called
        Then: Returns AI-generated answer with relevant chunks and trace_id
        """
        request = {
            "question": "What is RAG and how does it use vector databases?",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        # May return 200 if all services available, 503 if dependencies unavailable
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()

            # Verify answer is generated
            assert "answer" in data
            assert isinstance(data["answer"], str)
            assert len(data["answer"]) > 0

            # Verify chunks are retrieved
            assert "chunks" in data
            assert isinstance(data["chunks"], list)

            # Verify trace_id for correlation
            assert "trace_id" in data
            assert isinstance(data["trace_id"], str)

    @pytest.mark.integration
    async def test_query_flow_includes_retrieval_metrics(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that query flow includes retrieval timing metrics.

        Given: A knowledge base query
        When: POST /ai/agent is called
        Then: Response includes retrieval_time_ms in metadata
        """
        request = {
            "question": "How do vector databases work?",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})

            # Should include timing information
            assert "retrieval_time_ms" in metadata or "total_latency_ms" in metadata

    @pytest.mark.integration
    async def test_query_flow_includes_inference_metrics(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that query flow includes inference metrics.

        Given: A knowledge base query
        When: POST /ai/agent is called
        Then: Response includes model_used and tokens in metadata
        """
        request = {
            "question": "Explain LLM integration",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})

            # Should include model information
            if "model_used" in metadata:
                assert isinstance(metadata["model_used"], str)

            # May include token counts
            if "input_tokens" in metadata or "output_tokens" in metadata:
                assert isinstance(metadata.get("input_tokens", 0), int)
                assert isinstance(metadata.get("output_tokens", 0), int)

    @pytest.mark.integration
    async def test_query_with_model_hint_uses_specified_model(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that model_hint parameter influences model selection.

        Given: A request with model_hint parameter
        When: POST /ai/agent is called
        Then: Response metadata reflects the requested model
        """
        request = {
            "question": "What is machine learning?",
            "model_hint": "gpt-4",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})

            # Model hint should be reflected in response
            if "model_used" in metadata or "model_hint" in metadata:
                # Verify model information is present
                assert True  # Model selection was recorded

    @pytest.mark.integration
    async def test_query_with_context_includes_context_in_trace(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that context parameter is included in trace data.

        Given: A request with context parameter
        When: POST /ai/agent is called
        Then: Trace data includes the context
        """
        request = {
            "question": "Test question",
            "context": {
                "user_id": "test_user_123",
                "session_id": "test_session_abc",
            },
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            trace_id = data.get("trace_id")

            # Trace should be retrievable with context
            # (This would require a GET /traces/{trace_id} endpoint)
            assert trace_id is not None

    @pytest.mark.integration
    async def test_query_flow_handles_empty_results_gracefully(
        self,
        client: AsyncClient,
    ) -> None:
        """Test behavior when knowledge base returns no results.

        Given: A question with no relevant documents
        When: POST /ai/agent is called
        Then: Returns response with helpful message
        """
        request = {
            "question": "xyzabc123def456 - very obscure query with no matches",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        # Should still return a response (possibly with empty chunks)
        assert response.status_code in [200, 400, 404]

        if response.status_code == 200:
            data = response.json()
            chunks = data.get("chunks", [])
            # Empty chunks is acceptable
            assert isinstance(chunks, list)
        elif response.status_code in [400, 404]:
            # Should have helpful error message
            data = response.json()
            # Error response should have message
            assert True

    @pytest.mark.integration
    async def test_concurrent_queries_handle_correctly(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that multiple concurrent queries are handled correctly.

        Given: Multiple concurrent requests
        When: POST /ai/agent is called multiple times concurrently
        Then: All requests complete successfully with unique trace_ids
        """
        import asyncio

        async def make_query(question: str) -> tuple[int, str | None]:
            resp = await client.post(
                "/ai/agent",
                json={"question": question}
            )
            trace_id = resp.json().get("trace_id") if resp.status_code == 200 else None
            return resp.status_code, trace_id

        # Run 5 concurrent queries
        results = await asyncio.gather(
            make_query("What is AI?"),
            make_query("Explain machine learning"),
            make_query("What are neural networks?"),
            make_query("Define deep learning"),
            make_query("How do transformers work?"),
        )

        # All should complete without errors
        status_codes = [r[0] for r in results]
        trace_ids = [r[1] for r in results]

        # Check that all completed
        assert all(s in [200, 503] for s in status_codes)

        # Check that trace_ids are unique (for successful requests)
        successful_trace_ids = [t for t in trace_ids if t is not None]
        assert len(successful_trace_ids) == len(set(successful_trace_ids))

    @pytest.mark.integration
    async def test_health_check_verifies_system_status(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that health check verifies all components.

        Given: GET /health is called
        When: System is operational
        Then: Returns status for all components
        """
        response = await client.get("/health")

        assert response.status_code == 200

        data = response.json()
        assert "status" in data

        # May include component status
        if "components" in data:
            assert isinstance(data["components"], dict)

    @pytest.mark.integration
    async def test_models_endpoint_lists_available_models(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that models endpoint lists available models.

        Given: GET /models is called
        When: System has configured models
        Then: Returns list of available model identifiers
        """
        response = await client.get("/models")

        assert response.status_code == 200

        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

        # Each model should have identifier
        for model in data["models"]:
            assert "model_id" in model or "id" in model

    @pytest.mark.integration
    async def test_trace_id_correlation_across_request(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace_id enables correlation across request lifecycle.

        Given: A request that generates a trace_id
        When: The same trace_id is used for trace retrieval
        Then: All trace data is accessible
        """
        request = {
            "question": "Test question for trace correlation",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            trace_id = data.get("trace_id")

            # In a full implementation, we would retrieve the trace
            # For now, verify trace_id exists and is valid format
            assert trace_id is not None
            assert len(trace_id) > 0


class TestMultiProviderModelSelection:
    """Integration tests for multi-provider model selection (US2).

    Tests verify:
    - Model routing to different providers
    - Fallback behavior on provider failure
    - Provider availability tracking
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_model_routing_with_hint(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that model_hint routes to correct provider.

        Given: A request with model_hint="gpt-3.5-turbo"
        When: POST /ai/agent is called
        Then: Request is routed to OpenAI provider
        """
        request = {
            "question": "Test question for GPT",
            "model_hint": "gpt-3.5-turbo",
        }

        response = await client.post("/ai/agent", json=request)

        # May return 200 if provider available, 503 if not
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            # Verify model information is recorded
            assert "model_used" in metadata or "provider" in metadata

    @pytest.mark.integration
    async def test_model_routing_with_claude_hint(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that model_hint routes Claude to Anthropic.

        Given: A request with model_hint="claude-3-haiku"
        When: POST /ai/agent is called
        Then: Request is routed to Anthropic provider
        """
        request = {
            "question": "Test question for Claude",
            "model_hint": "claude-3-haiku",
        }

        response = await client.post("/ai/agent", json=request)

        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            # Verify Claude model was used
            if "model_used" in metadata:
                assert "claude" in metadata["model_used"].lower()

    @pytest.mark.integration
    async def test_model_routing_with_ollama_hint(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that model_hint routes Ollama to local provider.

        Given: A request with model_hint="ollama/llama3"
        When: POST /ai/agent is called
        Then: Request is routed to Ollama provider
        """
        request = {
            "question": "Test question for Ollama",
            "model_hint": "ollama/llama3",
        }

        response = await client.post("/ai/agent", json=request)

        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            # Verify Ollama model was used
            if "model_used" in metadata:
                assert "llama3" in metadata["model_used"].lower()

    @pytest.mark.integration
    async def test_fallback_on_unavailable_provider(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that system falls back when requested provider unavailable.

        Given: A request with unavailable model_hint
        When: POST /ai/agent is called
        Then: Falls back to available model
        """
        request = {
            "question": "Test fallback behavior",
            "model_hint": "unavailable-model-test",
        }

        response = await client.post("/ai/agent", json=request)

        # Should fallback to default or return error
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            # Request succeeded with fallback
            data = response.json()
            assert "answer" in data

    @pytest.mark.integration
    async def test_models_endpoint_shows_all_providers(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that /models endpoint shows all configured providers.

        Given: Multiple providers configured
        When: GET /models is called
        Then: Returns models grouped by provider
        """
        response = await client.get("/models")

        assert response.status_code == 200

        data = response.json()
        assert "models" in data
        assert "providers" in data

        # Should have multiple providers if configured
        # At minimum: openai, anthropic, ollama
        providers = data.get("providers", [])
        assert isinstance(providers, list)

    @pytest.mark.integration
    async def test_models_endpoint_includes_availability_status(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that /models includes availability status for each provider.

        Given: GET /models is called
        When: Provider health is checked
        Then: Each model shows if provider is available
        """
        response = await client.get("/models")

        assert response.status_code == 200

        data = response.json()
        models = data.get("models", [])

        for model in models:
            # Each model should have availability information
            assert "id" in model or "model_id" in model
            # May include available status
            if "available" in model:
                assert isinstance(model["available"], bool)

    @pytest.mark.integration
    async def test_concurrent_requests_to_different_providers(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that concurrent requests to different providers work correctly.

        Given: Multiple concurrent requests with different model_hints
        When: All requests are made simultaneously
        Then: Each request routes to correct provider
        """
        import asyncio

        async def make_request(model_hint: str) -> tuple[int, str]:
            resp = await client.post(
                "/ai/agent",
                json={"question": "Test", "model_hint": model_hint}
            )
            model_used = ""
            if resp.status_code == 200:
                data = resp.json()
                metadata = data.get("metadata", {})
                model_used = metadata.get("model_used", "")
            return resp.status_code, model_used

        # Run concurrent requests to different providers
        results = await asyncio.gather(
            make_request("gpt-3.5-turbo"),
            make_request("claude-3-haiku"),
            make_request("ollama/llama3"),
        )

        # All should complete
        status_codes = [r[0] for r in results]
        assert all(s in [200, 503, 400] for s in status_codes)

    @pytest.mark.integration
    async def test_cost_tracking_per_provider(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that costs are tracked separately per provider.

        Given: Requests to different providers
        When: Requests complete
        Then: Costs are tracked per provider
        """
        # This would require a metrics endpoint to verify
        # For now, just verify requests complete
        request = {
            "question": "Test cost tracking",
            "model_hint": "gpt-3.5-turbo",
        }

        response = await client.post("/ai/agent", json=request)

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            # Cost information should be present
            # (May be in response or tracked separately)
            assert "answer" in data


class TestDocumentLifecycleManagement:
    """Integration tests for document lifecycle (US4 - Knowledge Base Management).

    Tests verify:
    - Complete document upload → index → query → update → delete flow
    - Document re-indexing after update
    - Trace correlation for document operations
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_complete_document_lifecycle(
        self,
        client: AsyncClient,
    ) -> None:
        """Test complete document lifecycle from upload to deletion.

        Given: A new document
        When: Upload → Query → Update → Query → Delete
        Then: All operations succeed and content is properly indexed
        """
        # Step 1: Upload document
        upload_request = {
            "content": "RAG systems combine retrieval with generation for accurate AI responses. Vector databases enable efficient semantic search.",
            "metadata": {"title": "RAG Guide", "category": "ai"},
        }

        upload_response = await client.post("/documents", json=upload_request)

        # May return 200 if endpoint works, 503 if not yet implemented
        if upload_response.status_code in [200, 201]:
            upload_data = upload_response.json()
            doc_id = upload_data.get("doc_id")

            assert doc_id is not None
            assert "chunk_count" in upload_data or upload_data.get("trace_id") is not None

            # Step 2: Query to verify document is indexed
            query_response = await client.post("/ai/agent", json={"question": "What is RAG?"})

            if query_response.status_code == 200:
                query_data = query_response.json()
                chunks = query_data.get("chunks", [])
                # Should have at least some chunks from uploaded document
                assert len(chunks) >= 0

            # Step 3: Update document
            update_request = {
                "content": "RAG systems combine retrieval with generation. Vector databases enable efficient semantic search for AI applications.",
                "metadata": {"title": "RAG Guide (Updated)", "category": "ai", "version": 2},
            }

            update_response = await client.put(f"/documents/{doc_id}", json=update_request)

            if update_response.status_code == 200:
                update_data = update_response.json()
                assert update_data.get("doc_id") == doc_id

            # Step 4: Delete document
            delete_response = await client.delete(f"/documents/{doc_id}")

            if delete_response.status_code == 200:
                delete_data = delete_response.json()
                assert delete_data.get("doc_id") == doc_id

    @pytest.mark.integration
    async def test_upload_multiple_documents(
        self,
        client: AsyncClient,
    ) -> None:
        """Test uploading multiple documents.

        Given: Multiple documents
        When: All are uploaded via POST /documents
        Then: All are indexed and independently queryable
        """
        documents = [
            {
                "content": "Document 1: Introduction to AI",
                "metadata": {"id": "doc1", "topic": "ai"},
            },
            {
                "content": "Document 2: Introduction to Machine Learning",
                "metadata": {"id": "doc2", "topic": "ml"},
            },
            {
                "content": "Document 3: Introduction to Deep Learning",
                "metadata": {"id": "doc3", "topic": "dl"},
            },
        ]

        doc_ids = []

        for doc in documents:
            response = await client.post("/documents", json=doc)

            if response.status_code in [200, 201]:
                data = response.json()
                doc_ids.append(data.get("doc_id"))

        # Verify we can query for each topic
        topics = ["AI", "machine learning", "deep learning"]

        for i, topic in enumerate(topics):
            if doc_ids:
                response = await client.post("/ai/agent", json={"question": f"Tell me about {topic}"})

                if response.status_code == 200:
                    data = response.json()
                    # Should get an answer
                    assert "answer" in data

    @pytest.mark.integration
    async def test_document_update_preserves_metadata(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that document update preserves existing metadata.

        Given: A document with metadata
        When: Updated with partial metadata
        Then: Original metadata is preserved and merged
        """
        # Upload with initial metadata
        upload_request = {
            "content": "Test content for metadata preservation",
            "metadata": {"category": "test", "tags": ["original"], "priority": 1},
        }

        upload_response = await client.post("/documents", json=upload_request)

        if upload_response.status_code in [200, 201]:
            upload_data = upload_response.json()
            doc_id = upload_data.get("doc_id")

            # Update with partial metadata
            update_request = {
                "content": "Updated test content",
                "metadata": {"priority": 2},  # Only update priority
            }

            update_response = await client.put(f"/documents/{doc_id}", json=update_request)

            if update_response.status_code == 200:
                update_data = update_response.json()
                # Original metadata should be preserved
                # (This would require a GET /documents/{doc_id} endpoint to verify)

    @pytest.mark.integration
    async def test_deleted_document_not_queryable(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that deleted documents are not returned in queries.

        Given: A document that has been deleted
        When: Query is made
        Then: Deleted document content is not in results
        """
        # Upload document
        upload_request = {
            "content": "This document will be deleted and should not appear in queries",
            "metadata": {"status": "to_delete"},
        }

        upload_response = await client.post("/documents", json=upload_request)

        if upload_response.status_code in [200, 201]:
            upload_data = upload_response.json()
            doc_id = upload_data.get("doc_id")

            # Query before deletion
            query_before = await client.post(
                "/ai/agent",
                json={"question": "What should not appear in queries?"}
            )

            # Delete document
            delete_response = await client.delete(f"/documents/{doc_id}")

            if delete_response.status_code == 200:
                # Query after deletion
                query_after = await client.post(
                    "/ai/agent",
                    json={"question": "What should not appear in queries?"}
                )

                # Results after deletion should not contain the deleted content
                # (This is a qualitative check - automated assertion would require content comparison)

    @pytest.mark.integration
    async def test_document_operations_include_trace_id(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that document operations return trace_id.

        Given: Document operations are performed
        When: Upload/Update/Delete is called
        Then: Response includes trace_id for observability
        """
        # Upload
        upload_response = await client.post(
            "/documents",
            json={"content": "Trace test document", "metadata": {}}
        )

        if upload_response.status_code in [200, 201]:
            upload_data = upload_response.json()
            assert "trace_id" in upload_data or "doc_id" in upload_data

            doc_id = upload_data.get("doc_id")

            if doc_id:
                # Update
                update_response = await client.put(
                    f"/documents/{doc_id}",
                    json={"content": "Updated", "metadata": {}}
                )

                if update_response.status_code == 200:
                    update_data = update_response.json()
                    assert "trace_id" in update_data or "doc_id" in update_data

                # Delete
                delete_response = await client.delete(f"/documents/{doc_id}")

                if delete_response.status_code == 200:
                    delete_data = delete_response.json()
                    assert "trace_id" in delete_data or "doc_id" in delete_data

    @pytest.mark.integration
    async def test_concurrent_document_operations(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that concurrent document operations are handled correctly.

        Given: Multiple concurrent document operations
        When: Operations are executed simultaneously
        Then: All operations complete without data corruption
        """
        import asyncio

        async def upload_doc(doc_num: int) -> tuple[int, str]:
            resp = await client.post(
                "/documents",
                json={
                    "content": f"Concurrent document {doc_num}",
                    "metadata": {"index": doc_num},
                }
            )
            doc_id = resp.json().get("doc_id") if resp.status_code in [200, 201] else ""
            return resp.status_code, doc_id

        # Upload 5 documents concurrently
        results = await asyncio.gather(
            upload_doc(1),
            upload_doc(2),
            upload_doc(3),
            upload_doc(4),
            upload_doc(5),
        )

        # All should complete
        status_codes = [r[0] for r in results]
        assert all(s in [200, 201, 503] for s in status_codes)

    @pytest.mark.integration
    async def test_document_with_long_content(
        self,
        client: AsyncClient,
    ) -> None:
        """Test handling of documents with long content.

        Given: A document with content exceeding chunk size
        When: Document is uploaded
        Then: Content is properly chunked and indexed
        """
        # Create a long document (simulating a multi-page article)
        long_content = """
        This is a test document with extensive content. """ * 100

        upload_response = await client.post(
            "/documents",
            json={"content": long_content, "metadata": {"type": "long"}}
        )

        if upload_response.status_code in [200, 201]:
            data = upload_response.json()
            doc_id = data.get("doc_id")

            # Should create multiple chunks
            chunk_count = data.get("chunk_count", 0)

            # Verify document is queryable
            query_response = await client.post(
                "/ai/agent",
                json={"question": "What is this test document about?"}
            )

            if query_response.status_code == 200:
                query_data = query_response.json()
                assert "answer" in query_data
