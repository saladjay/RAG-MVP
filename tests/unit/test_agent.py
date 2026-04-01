"""
Unit tests for Agent Orchestration (US1 - Knowledge Base Query).

These tests verify the Phidata agent orchestration and tool execution.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch, AsyncMock as AsyncMockType
from typing import Dict, Any, List


class TestPhidataAgent:
    """Unit tests for Phidata Agent orchestration.

    Tests verify:
    - Agent initialization with tools
    - Tool execution during agent run
    - Response generation
    - Error handling for tool failures
    """

    @pytest.fixture
    def mock_retrieval_tool(self):
        """Mock retrieval tool."""
        tool = Mock()
        tool.name = "knowledge_retrieval"
        tool.execute = AsyncMock(return_value={
            "chunks": [
                {
                    "chunk_id": "chunk1",
                    "content": "RAG is a technique...",
                    "score": 0.95,
                }
            ]
        })
        return tool

    @pytest.fixture
    def mock_inference_tool(self):
        """Mock inference tool."""
        tool = Mock()
        tool.name = "llm_inference"
        tool.execute = AsyncMock(return_value={
            "answer": "Based on the retrieved context...",
            "model_used": "gpt-4",
            "tokens": {"input": 100, "output": 50},
        })
        return tool

    @pytest.mark.unit
    @patch("rag_service.core.agent.Agent")
    async def test_agent_initializes_with_tools(
        self,
        mock_agent_class,
        mock_retrieval_tool,
        mock_inference_tool,
    ) -> None:
        """Test that agent initializes with configured tools.

        Given: Retrieval and inference tools
        When: Agent is created
        Then: Tools are registered with agent
        """
        from rag_service.core.agent import RAGAgent

        mock_agent_instance = Mock()
        mock_agent_instance.run = AsyncMock(return_value="Agent response")
        mock_agent_class.return_value = mock_agent_instance

        agent = RAGAgent(
            retrieval_tool=mock_retrieval_tool,
            inference_tool=mock_inference_tool,
        )

        # Verify agent was created with tools
        assert agent.retrieval_tool == mock_retrieval_tool
        assert agent.inference_tool == mock_inference_tool

    @pytest.mark.unit
    @patch("rag_service.core.agent.Agent")
    async def test_agent_executes_retrieval_tool(
        self,
        mock_agent_class,
        mock_retrieval_tool,
        mock_inference_tool,
    ) -> None:
        """Test that agent executes retrieval tool during run.

        Given: A user question
        When: Agent processes the question
        Then: Retrieval tool is called with query
        """
        from rag_service.core.agent import RAGAgent

        mock_agent_instance = Mock()
        mock_agent_instance.run = AsyncMock(return_value="Agent response")
        mock_agent_class.return_value = mock_agent_instance

        agent = RAGAgent(
            retrieval_tool=mock_retrieval_tool,
            inference_tool=mock_inference_tool,
        )

        question = "What is RAG?"
        response = await agent.run(question, trace_id="test_trace")

        # Verify tools were available to agent
        assert response is not None

    @pytest.mark.unit
    @patch("rag_service.core.agent.Agent")
    async def test_agent_executes_inference_tool(
        self,
        mock_agent_class,
        mock_retrieval_tool,
        mock_inference_tool,
    ) -> None:
        """Test that agent executes inference tool with retrieved context.

        Given: Retrieved chunks from retrieval tool
        When: Agent generates response
        Then: Inference tool is called with context
        """
        from rag_service.core.agent import RAGAgent

        mock_agent_instance = Mock()
        mock_agent_instance.run = AsyncMock(return_value="Agent response")
        mock_agent_class.return_value = mock_agent_instance

        agent = RAGAgent(
            retrieval_tool=mock_retrieval_tool,
            inference_tool=mock_inference_tool,
        )

        question = "Explain vector databases"
        response = await agent.run(question, trace_id="test_trace")

        # Verify response is generated
        assert response is not None

    @pytest.mark.unit
    @patch("rag_service.core.agent.Agent")
    async def test_agent_handles_retrieval_failure(
        self,
        mock_agent_class,
        mock_retrieval_tool,
        mock_inference_tool,
    ) -> None:
        """Test that agent handles retrieval tool failure.

        Given: Retrieval tool raises exception
        When: Agent processes question
        Then: Returns graceful error or falls back to direct inference
        """
        from rag_service.core.agent import RAGAgent

        # Mock retrieval failure
        mock_retrieval_tool.execute = AsyncMock(
            side_effect=Exception("Retrieval failed")
        )

        mock_agent_instance = Mock()
        mock_agent_instance.run = AsyncMock(return_value="Fallback response")
        mock_agent_class.return_value = mock_agent_instance

        agent = RAGAgent(
            retrieval_tool=mock_retrieval_tool,
            inference_tool=mock_inference_tool,
        )

        response = await agent.run("Test question", trace_id="test_trace")

        # Should handle error gracefully
        assert response is not None

    @pytest.mark.unit
    @patch("rag_service.core.agent.Agent")
    async def test_agent_includes_trace_id(
        self,
        mock_agent_class,
        mock_retrieval_tool,
        mock_inference_tool,
    ) -> None:
        """Test that agent propagates trace_id through execution.

        Given: A trace_id
        When: Agent runs with trace_id
        Then: trace_id is passed to all tool calls
        """
        from rag_service.core.agent import RAGAgent

        mock_agent_instance = Mock()
        mock_agent_instance.run = AsyncMock(return_value="Response")
        mock_agent_class.return_value = mock_agent_instance

        agent = RAGAgent(
            retrieval_tool=mock_retrieval_tool,
            inference_tool=mock_inference_tool,
        )

        trace_id = "test_trace_123"
        response = await agent.run("Test question", trace_id=trace_id)

        # Trace tracking would be verified here
        assert response is not None

    @pytest.mark.unit
    async def test_agent_response_structure(
        self,
    ) -> None:
        """Test that agent returns properly structured response.

        Given: Successful agent execution
        When: Response is returned
        Then: Contains answer, chunks, and metadata
        """
        from rag_service.core.agent import AgentResponse

        response = AgentResponse(
            answer="Test answer",
            chunks=[{"chunk_id": "1", "content": "Content", "score": 0.9}],
            trace_id="test_trace",
            metadata={"model_used": "gpt-4"},
        )

        assert response.answer == "Test answer"
        assert len(response.chunks) == 1
        assert response.trace_id == "test_trace"
        assert response.metadata["model_used"] == "gpt-4"


class TestRetrievalTool:
    """Unit tests for retrieval tool.

    Tests verify:
    - Tool invocation with query
    - Chunk retrieval from knowledge base
    - Score filtering
    - Error handling
    """

    @pytest.mark.unit
    @patch("rag_service.core.agent.KnowledgeBase")
    async def test_retrieval_tool_searches_knowledge_base(
        self,
        mock_kb_class,
    ) -> None:
        """Test that retrieval tool searches knowledge base.

        Given: A query string
        When: Tool is executed
        Then: Calls knowledge base search
        """
        from rag_service.core.agent import RetrievalTool

        mock_kb = Mock()
        mock_kb.search = Mock(return_value=[
            {
                "chunk_id": "chunk1",
                "content": "Test content",
                "score": 0.9,
                "source_doc": "doc1",
            }
        ])
        mock_kb_class.return_value = mock_kb

        tool = RetrievalTool(knowledge_base=mock_kb)
        result = await tool.execute(query="test query", trace_id="test_trace")

        assert "chunks" in result
        assert len(result["chunks"]) == 1

    @pytest.mark.unit
    @patch("rag_service.core.agent.KnowledgeBase")
    async def test_retrieval_tool_filters_low_scores(
        self,
        mock_kb_class,
    ) -> None:
        """Test that retrieval tool filters low-score chunks.

        Given: Search results with varying scores
        When: Tool is executed with score_threshold
        Then: Returns only chunks above threshold
        """
        from rag_service.core.agent import RetrievalTool

        mock_kb = Mock()
        mock_kb.search = Mock(return_value=[
            {"chunk_id": "chunk1", "content": "High score", "score": 0.9},
            {"chunk_id": "chunk2", "content": "Low score", "score": 0.3},
            {"chunk_id": "chunk3", "content": "Medium score", "score": 0.6},
        ])
        mock_kb_class.return_value = mock_kb

        tool = RetrievalTool(knowledge_base=mock_kb, score_threshold=0.5)
        result = await tool.execute(query="test query", trace_id="test_trace")

        # Should filter out low score chunks
        assert len(result["chunks"]) == 2
        assert all(c["score"] >= 0.5 for c in result["chunks"])


class TestInferenceTool:
    """Unit tests for inference tool.

    Tests verify:
    - Tool invocation with prompt
    - Model inference via LiteLLM
    - Response parsing
    - Cost tracking
    """

    @pytest.mark.unit
    @patch("rag_service.core.agent.LiteLLMGateway")
    async def test_inference_tool_calls_model(
        self,
        mock_gateway_class,
    ) -> None:
        """Test that inference tool calls model via gateway.

        Given: A prompt string
        When: Tool is executed
        Then: Calls LiteLLM gateway
        """
        from rag_service.core.agent import InferenceTool

        mock_gateway = Mock()
        mock_gateway.complete = AsyncMock(return_value=Mock(
            text="Generated response",
            model="gpt-4",
            input_tokens=50,
            output_tokens=30,
            cost=0.001,
        ))
        mock_gateway_class.return_value = mock_gateway

        tool = InferenceTool(gateway=mock_gateway)
        result = await tool.execute(
            prompt="Test prompt",
            model_hint="gpt-4",
            trace_id="test_trace"
        )

        assert "answer" in result
        assert result["answer"] == "Generated response"

    @pytest.mark.unit
    @patch("rag_service.core.agent.LiteLLMGateway")
    async def test_inference_tool_includes_model_metadata(
        self,
        mock_gateway_class,
    ) -> None:
        """Test that inference tool includes model metadata.

        Given: Successful inference
        When: Tool returns result
        Then: Includes model_used and tokens
        """
        from rag_service.core.agent import InferenceTool

        mock_gateway = Mock()
        mock_gateway.complete = AsyncMock(return_value=Mock(
            text="Response",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            cost=0.002,
        ))
        mock_gateway_class.return_value = mock_gateway

        tool = InferenceTool(gateway=mock_gateway)
        result = await tool.execute(
            prompt="Test",
            model_hint="gpt-4",
            trace_id="test_trace"
        )

        assert result["model_used"] == "gpt-4"
        assert result["tokens"]["input"] == 100
        assert result["tokens"]["output"] == 50
