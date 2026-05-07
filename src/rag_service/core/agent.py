"""
Phidata Agent Orchestration for RAG Service.

This module provides agent orchestration using Phidata framework.
It handles:
- Agent initialization with tools
- Tool execution (retrieval, inference)
- Response generation
- Trace ID propagation through agent flow

API Reference:
- Location: src/rag_service/core/agent.py
- Class: RAGAgent
- Classes: RetrievalTool, InferenceTool
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from rag_service.core.logger import get_logger
from rag_service.services.prompt_client import (
    get_prompt_client,
    TEMPLATE_RAG_AGENT_INSTRUCTIONS,
)

logger = get_logger(__name__)


@dataclass
class AgentResponse:
    """Response from agent execution.

    Attributes:
        answer: Generated answer text
        chunks: Retrieved document chunks
        trace_id: Associated trace ID
        metadata: Additional response metadata
    """
    answer: str
    chunks: List[Dict[str, Any]]
    trace_id: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "answer": self.answer,
            "chunks": self.chunks,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }


class RetrievalTool:
    """
    Tool for knowledge base retrieval in Phidata agent.

    This tool wraps the KnowledgeQueryCapability to provide
    semantic search functionality to the agent.
    """

    def __init__(self, knowledge_base=None):
        """Initialize retrieval tool.

        Args:
            knowledge_base: Optional KnowledgeBase instance
        """
        self.knowledge_base = knowledge_base
        self.name = "knowledge_retrieval"

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        trace_id: str = "",
        score_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute knowledge base retrieval.

        Args:
            query: Query text
            top_k: Maximum results to return
            trace_id: Trace ID for observability
            score_threshold: Optional minimum similarity score

        Returns:
            Dictionary with chunks list
        """
        if not self.knowledge_base:
            logger.warning("Knowledge base not available")
            return {"chunks": []}

        try:
            chunks = await self.knowledge_base.asearch(
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
            )

            logger.debug(
                "Retrieval tool executed",
                extra={
                    "trace_id": trace_id,
                    "query_length": len(query),
                    "chunks_count": len(chunks),
                },
            )

            return {"chunks": chunks}

        except Exception as e:
            logger.error(
                "Retrieval tool failed",
                extra={"error": str(e), "trace_id": trace_id},
            )
            return {"chunks": []}


class InferenceTool:
    """
    Tool for LLM inference in Phidata agent.

    This tool wraps the ModelInferenceCapability to provide
    text generation functionality to the agent.
    """

    def __init__(self, gateway=None):
        """Initialize inference tool.

        Args:
            gateway: Optional LiteLLMGateway instance
        """
        self.gateway = gateway
        self.name = "llm_inference"

    async def execute(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        trace_id: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Execute LLM inference.

        Args:
            prompt: Input prompt
            model_hint: Optional model hint
            trace_id: Trace ID for observability
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dictionary with answer and metadata
        """
        if not self.gateway:
            logger.warning("Gateway not available")
            return {
                "answer": "LLM service unavailable",
                "model_used": None,
                "tokens": {"input": 0, "output": 0},
            }

        try:
            result = await self.gateway.acomplete(
                prompt=prompt,
                model_hint=model_hint,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            logger.debug(
                "Inference tool executed",
                extra={
                    "trace_id": trace_id,
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": result.latency_ms,
                },
            )

            return {
                "answer": result.text,
                "model_used": result.model,
                "tokens": {
                    "input": result.input_tokens,
                    "output": result.output_tokens,
                },
                "latency_ms": result.latency_ms,
                "cost": result.cost,
                "provider": result.provider,
            }

        except Exception as e:
            logger.error(
                "Inference tool failed",
                extra={"error": str(e), "trace_id": trace_id},
            )
            return {
                "answer": f"Inference failed: {str(e)}",
                "model_used": None,
                "tokens": {"input": 0, "output": 0},
            }


class RAGAgent:
    """
    RAG Agent orchestration using Phidata framework.

    This agent coordinates retrieval and inference tools to provide
    knowledge-augmented question answering.

    Attributes:
        retrieval_tool: Tool for knowledge base search
        inference_tool: Tool for LLM inference
        instructions: System instructions for the agent
    """

    def __init__(
        self,
        retrieval_tool: Optional[RetrievalTool] = None,
        inference_tool: Optional[InferenceTool] = None,
        instructions: Optional[str] = None,
        use_prompt_service: bool = True,
    ):
        """Initialize RAG agent.

        Args:
            retrieval_tool: Optional retrieval tool
            inference_tool: Optional inference tool
            instructions: System instructions for agent behavior (deprecated, use Prompt Service)
            use_prompt_service: Whether to use Prompt Service for instructions
        """
        self.retrieval_tool = retrieval_tool or RetrievalTool()
        self.inference_tool = inference_tool or InferenceTool()
        self._use_prompt_service = use_prompt_service
        self._prompt_client = None  # Will be initialized lazily

        # Use provided instructions or None (will use Prompt Service)
        self.instructions = instructions

        logger.info("Initialized RAG agent")

    async def _get_prompt_client(self):
        """Get or create the prompt client."""
        if self._prompt_client is None:
            self._prompt_client = await get_prompt_client()
        return self._prompt_client

    async def get_instructions(self, trace_id: str = "") -> str:
        """Get agent instructions from Prompt Service.

        Args:
            trace_id: Request trace identifier

        Returns:
            Agent instructions string
        """
        if self._use_prompt_service:
            prompt_client = await self._get_prompt_client()
            return await prompt_client.get_prompt(
                template_id=TEMPLATE_RAG_AGENT_INSTRUCTIONS,
                trace_id=trace_id,
            )
        return self.instructions or "You are a helpful AI assistant that answers questions based on retrieved context."

    async def run(
        self,
        question: str,
        trace_id: str = "",
        top_k: int = 5,
        model_hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Run agent to answer question using retrieved context.

        Args:
            question: User question
            trace_id: Trace ID for observability
            top_k: Number of chunks to retrieve
            model_hint: Optional model hint
            context: Optional additional context

        Returns:
            AgentResponse with answer and retrieved chunks
        """
        start_time = asyncio.get_event_loop().time()

        # Step 1: Retrieve relevant chunks
        retrieval_result = await self.retrieval_tool.execute(
            query=question,
            top_k=top_k,
            trace_id=trace_id,
        )

        chunks = retrieval_result.get("chunks", [])

        # Handle no-retrieval-results scenario
        if not chunks:
            logger.warning(
                "No chunks retrieved for question",
                extra={"trace_id": trace_id, "question_length": len(question)},
            )

            # Generate direct answer without context
            inference_result = await self.inference_tool.execute(
                prompt=question,
                model_hint=model_hint,
                trace_id=trace_id,
            )

            return AgentResponse(
                answer=inference_result.get("answer", "I couldn't find relevant information to answer your question."),
                chunks=[],
                trace_id=trace_id,
                metadata={
                    "model_used": inference_result.get("model_used"),
                    "tokens": inference_result.get("tokens", {}),
                    "chunks_count": 0,
                    "retrieval_time_ms": 0,
                    "inference_time_ms": inference_result.get("latency_ms", 0),
                },
            )

        # Step 2: Build prompt with retrieved context
        context_text = self._build_context_prompt(chunks)
        prompt = await self._build_prompt(question, context_text, trace_id)

        # Step 3: Generate answer with context
        inference_result = await self.inference_tool.execute(
            prompt=prompt,
            model_hint=model_hint,
            trace_id=trace_id,
        )

        total_latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        answer = inference_result.get("answer", "")

        logger.info(
            "Agent execution completed",
            extra={
                "trace_id": trace_id,
                "chunks_count": len(chunks),
                "answer_length": len(answer),
                "latency_ms": total_latency_ms,
            },
        )

        return AgentResponse(
            answer=answer,
            chunks=chunks,
            trace_id=trace_id,
            metadata={
                "model_used": inference_result.get("model_used"),
                "tokens": inference_result.get("tokens", {}),
                "chunks_count": len(chunks),
                "total_latency_ms": total_latency_ms,
                "retrieval_time_ms": 0,  # Would be tracked by retrieval tool
                "inference_time_ms": inference_result.get("latency_ms", 0),
            },
        )

    def _build_context_prompt(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context section from retrieved chunks.

        Args:
            chunks: List of retrieved chunks

        Returns:
            Formatted context text
        """
        if not chunks:
            return "No relevant context found."

        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            source = chunk.get("source_doc", "")
            score = chunk.get("score", 0.0)

            context_parts.append(
                f"[Document {i}] (Source: {source}, Relevance: {score:.2f})\n{content}"
            )

        return "\n\n".join(context_parts)

    async def _build_prompt(self, question: str, context: str, trace_id: str = "") -> str:
        """Build full prompt for LLM using Prompt Service.

        Args:
            question: User question
            context: Retrieved context
            trace_id: Request trace identifier

        Returns:
            Formatted prompt
        """
        # Get instructions from Prompt Service
        instructions = await self.get_instructions(trace_id)

        # Build prompt with instructions from template
        if self._use_prompt_service:
            prompt_client = await self._get_prompt_client()
            variables = {
                "context": context,
                "question": question,
            }
            return await prompt_client.get_prompt(
                template_id=TEMPLATE_RAG_AGENT_INSTRUCTIONS,
                variables=variables,
                trace_id=trace_id,
            )

        # Fallback to original format
        return f"""{instructions}

[Retrieved Context]
{context}

[User Question]
{question}

[Instructions]
Based on the retrieved context above, answer the user's question. If the context doesn't contain relevant information, say so explicitly. Use specific details from the context when possible."""


# Global singleton instance
_agent: Optional[RAGAgent] = None
_agent_lock = asyncio.Lock()


async def get_rag_agent() -> RAGAgent:
    """Get or create the global RAG agent singleton.

    Returns:
        The global RAGAgent instance
    """
    global _agent

    async with _agent_lock:
        if _agent is None:
            # Initialize tools
            from rag_service.retrieval.knowledge_base import get_knowledge_base
            from rag_service.inference.gateway import get_gateway

            kb = await get_knowledge_base()
            gateway = await get_gateway()

            retrieval_tool = RetrievalTool(knowledge_base=kb)
            inference_tool = InferenceTool(gateway=gateway)

            _agent = RAGAgent(
                retrieval_tool=retrieval_tool,
                inference_tool=inference_tool,
            )
            logger.info("Initialized global RAG agent")

    return _agent


def reset_rag_agent() -> None:
    """Reset the global RAG agent instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _agent
    _agent = None
    logger.debug("Reset global RAG agent")
