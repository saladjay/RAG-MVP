"""
Quickstart: Build a RAG Agent using the 001 spec architecture.

This example demonstrates the core pattern of the RAG Service MVP:
    HTTP Route → Capability → Agent (Retrieval + Inference) → Three-layer Observability

Architecture:
    ┌──────────────────────────────────────────────────┐
    │  FastAPI Route (POST /api/v1/ai/agent)           │
    │       ↓                                          │
    │  Capability Interface Layer                      │
    │       ↓                                          │
    │  RAGAgent                                        │
    │    ├── RetrievalTool  → Milvus (vector search)   │
    │    └── InferenceTool  → LiteLLM (model gateway)  │
    │       ↓                                          │
    │  Three-layer Observability                       │
    │    ├── LiteLLM Observer (cost, tokens, routing)  │
    │    ├── Phidata Observer (steps, tools, reasoning)│
    │    └── Langfuse Observer (prompt version, vars)  │
    └──────────────────────────────────────────────────┘

Usage:
    # 1. Set environment variables (or use .env):
    export MILVUS_HOST=localhost
    export MILVUS_PORT=19530
    export LITELLM_API_KEY=your-key
    export LITELLM_MODEL=openai/gpt-4o-mini

    # 2. Run:
    uv run python examples/quickstart_agent.py
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# ============================================================================
# Step 1: Define Data Models (Pydantic)
# ============================================================================

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """Agent query request — maps to POST /ai/agent body."""

    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of chunks to retrieve")
    model_hint: Optional[str] = Field(None, description="Optional model hint, e.g. 'ollama/llama3'")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extra context")
    trace_id: Optional[str] = Field(None, description="Pre-assigned trace ID")


class RetrievedChunk(BaseModel):
    """A single retrieved knowledge chunk."""

    chunk_id: str
    content: str
    score: float
    source_doc: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentQueryResponse(BaseModel):
    """Agent query response — matches spec QueryResponse."""

    answer: str
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    trace_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Step 2: Create Agent Tools (Retrieval + Inference)
# ============================================================================

from rag_service.retrieval.knowledge_base import KnowledgeBase, get_knowledge_base
from rag_service.inference.gateway import LiteLLMGateway, get_gateway


class RetrievalTool:
    """Knowledge base retrieval tool — wraps Milvus vector search."""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.name = "knowledge_retrieval"

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        trace_id: str = "",
        score_threshold: float | None = None,
    ) -> List[Dict[str, Any]]:
        chunks = await self.knowledge_base.asearch(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return [
            {
                "chunk_id": c.get("chunk_id", ""),
                "content": c.get("content", ""),
                "score": c.get("score", 0.0),
                "source_doc": c.get("source_doc", ""),
                "metadata": c.get("metadata", {}),
            }
            for c in chunks
        ]


class InferenceTool:
    """LLM inference tool — wraps LiteLLM gateway."""

    def __init__(self, gateway: LiteLLMGateway):
        self.gateway = gateway
        self.name = "llm_inference"

    async def execute(
        self,
        prompt: str,
        model_hint: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        result = await self.gateway.acomplete(
            prompt=prompt,
            model_hint=model_hint,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "answer": result.text,
            "model_used": result.model,
            "tokens": {"input": result.input_tokens, "output": result.output_tokens},
            "latency_ms": result.latency_ms,
            "cost": result.cost,
            "provider": result.provider,
        }


# ============================================================================
# Step 3: Create RAG Agent (orchestrates Retrieval → Inference)
# ============================================================================


class RAGAgent:
    """
    RAG Agent: retrieval-augmented generation.

    Flow:
        1. Retrieve relevant chunks from Milvus
        2. Build prompt with context + question
        3. Generate answer via LLM gateway
    """

    def __init__(
        self,
        retrieval_tool: RetrievalTool,
        inference_tool: InferenceTool,
        system_prompt: str = "You are a helpful assistant. Answer based on the provided context.",
    ):
        self.retrieval_tool = retrieval_tool
        self.inference_tool = inference_tool
        self.system_prompt = system_prompt

    async def run(self, request: AgentQueryRequest) -> AgentQueryResponse:
        """Execute the full RAG pipeline."""
        trace_id = request.trace_id or f"trace_{uuid.uuid4().hex}"
        start = asyncio.get_event_loop().time()

        # --- Step 1: Retrieve ---
        chunks = await self.retrieval_tool.execute(
            query=request.question,
            top_k=request.top_k,
            trace_id=trace_id,
        )

        # --- Step 2: Build prompt ---
        if chunks:
            context_text = "\n\n".join(
                f"[Doc {i+1}] (Source: {c['source_doc']}, Score: {c['score']:.2f})\n{c['content']}"
                for i, c in enumerate(chunks)
            )
            prompt = (
                f"{self.system_prompt}\n\n"
                f"[Retrieved Context]\n{context_text}\n\n"
                f"[User Question]\n{request.question}\n\n"
                f"Answer based on the context above. Cite sources when possible."
            )
        else:
            prompt = f"{self.system_prompt}\n\n[User Question]\n{request.question}"

        # --- Step 3: Generate ---
        inference = await self.inference_tool.execute(
            prompt=prompt,
            model_hint=request.model_hint,
        )

        latency_ms = (asyncio.get_event_loop().time() - start) * 1000

        return AgentQueryResponse(
            answer=inference["answer"],
            chunks=[RetrievedChunk(**c) for c in chunks],
            trace_id=trace_id,
            metadata={
                "model_used": inference["model_used"],
                "tokens": inference["tokens"],
                "total_latency_ms": latency_ms,
                "inference_time_ms": inference["latency_ms"],
                "chunks_count": len(chunks),
                "cost": inference["cost"],
            },
        )


# ============================================================================
# Step 4: Wrap Agent as a Capability (adheres to 001 spec architecture)
# ============================================================================

from rag_service.capabilities.base import Capability, CapabilityValidationResult


class AgentQueryInput(BaseModel):
    """Input for the agent query capability."""

    trace_id: str = ""
    question: str
    top_k: int = 5
    model_hint: str | None = None
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentQueryOutput(BaseModel):
    """Output from the agent query capability."""

    success: bool = True
    trace_id: str = ""
    answer: str = ""
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentQueryCapability(Capability[AgentQueryInput, AgentQueryOutput]):
    """
    Agent Query Capability — the 001 spec's core capability.

    This is what HTTP routes interact with. The capability wraps
    the RAGAgent and provides the clean abstraction boundary.
    """

    def __init__(self, agent: RAGAgent):
        super().__init__()
        self.agent = agent

    def validate_input(self, input_data: AgentQueryInput) -> CapabilityValidationResult:
        if not input_data.question or not input_data.question.strip():
            return CapabilityValidationResult(
                is_valid=False,
                errors=["question is required"],
            )
        return CapabilityValidationResult(is_valid=True)

    async def execute(self, input_data: AgentQueryInput) -> AgentQueryOutput:
        request = AgentQueryRequest(
            question=input_data.question,
            top_k=input_data.top_k,
            model_hint=input_data.model_hint,
            context=input_data.context,
            trace_id=input_data.trace_id,
        )
        response = await self.agent.run(request)
        return AgentQueryOutput(
            success=True,
            trace_id=response.trace_id,
            answer=response.answer,
            chunks=[c.model_dump() for c in response.chunks],
            metadata=response.metadata,
        )


# ============================================================================
# Step 5: Create FastAPI App with Route → Capability pattern
# ============================================================================

from fastapi import FastAPI, HTTPException
from rag_service.capabilities.base import CapabilityRegistry, get_capability_registry
from rag_service.core.logger import get_logger, set_trace_id

logger = get_logger(__name__)

app = FastAPI(title="RAG Agent Quickstart", version="1.0.0")


@app.on_event("startup")
async def startup():
    """Initialize components and register capabilities."""
    kb = await get_knowledge_base()
    gateway = await get_gateway()

    retrieval_tool = RetrievalTool(knowledge_base=kb)
    inference_tool = InferenceTool(gateway=gateway)
    agent = RAGAgent(retrieval_tool=retrieval_tool, inference_tool=inference_tool)
    capability = AgentQueryCapability(agent)

    registry = get_capability_registry()
    registry.register(capability)
    logger.info("Agent capability registered")


@app.post("/api/v1/ai/agent", response_model=AgentQueryResponse)
async def query_agent(request: AgentQueryRequest) -> AgentQueryResponse:
    """
    Main agent endpoint — matches 001 spec POST /ai/agent.

    Flow: HTTP Request → Capability → RAGAgent → Response
    """
    # Generate trace_id
    trace_id = request.trace_id or f"trace_{uuid.uuid4().hex}"
    set_trace_id(trace_id)

    # Get capability from registry
    registry = get_capability_registry()
    capability = registry.get("AgentQueryCapability")

    # Execute via capability (not directly accessing agent)
    input_data = AgentQueryInput(
        trace_id=trace_id,
        question=request.question,
        top_k=request.top_k,
        model_hint=request.model_hint,
        context=request.context or {},
    )

    # Validate input
    validation = capability.validate_input(input_data)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.errors)

    # Execute
    result = await capability.execute(input_data)
    if not result.success:
        raise HTTPException(status_code=500, detail="Agent execution failed")

    return AgentQueryResponse(
        answer=result.answer,
        chunks=[RetrievedChunk(**c) for c in result.chunks],
        trace_id=result.trace_id,
        metadata=result.metadata,
    )


# ============================================================================
# Step 6: Standalone test (no FastAPI, direct agent usage)
# ============================================================================

async def demo():
    """
    Demo: Run the agent directly without FastAPI.

    Useful for quick testing and development.
    """
    from rag_service.config import get_settings

    settings = get_settings()
    print(f"=== RAG Agent Quickstart ===")
    print(f"  Milvus:  {settings.milvus.host}:{settings.milvus.port}")
    print(f"  Model:   {settings.litellm.model}")
    print(f"  Gateway: litellm\n")

    # Initialize components
    kb = await get_knowledge_base()
    gateway = await get_gateway()

    retrieval_tool = RetrievalTool(knowledge_base=kb)
    inference_tool = InferenceTool(gateway=gateway)
    agent = RAGAgent(
        retrieval_tool=retrieval_tool,
        inference_tool=inference_tool,
    )

    # Ask a question
    request = AgentQueryRequest(
        question="What is RAG?",
        top_k=3,
    )

    print(f"Question: {request.question}")
    response = await agent.run(request)

    print(f"\nAnswer: {response.answer}")
    print(f"\nRetrieved {len(response.chunks)} chunks:")
    for c in response.chunks:
        print(f"  - [{c.score:.2f}] {c.source_doc}: {c.content[:80]}...")

    print(f"\nMetadata:")
    for k, v in response.metadata.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(demo())
