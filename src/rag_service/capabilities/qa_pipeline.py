"""
QA Pipeline Capability for RAG Service.

This capability orchestrates the complete question-answering workflow:
query rewriting → knowledge base retrieval → answer generation → hallucination detection.
"""

import time
from typing import Any, Dict, List, Optional, AsyncGenerator

from pydantic import BaseModel, Field

from rag_service.api.qa_schemas import (
    QAContext,
    QAOptions,
    QASourceInfo,
    HallucinationStatus,
    QATiming,
    FallbackErrorType,
)
from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.capabilities.external_kb_query import ExternalKBQueryCapability, ExternalKBQueryInput
from rag_service.capabilities.model_inference import ModelInferenceCapability, ModelInferenceInput
from rag_service.capabilities.hallucination_detection import (
    HallucinationDetectionCapability,
    HallucinationCheckInput,
)
from rag_service.capabilities.query_rewrite import (
    QueryRewriteCapability,
    QueryRewriteInput,
)
from rag_service.capabilities.query_quality import (
    QueryQualityCapability,
    QueryQualityInput,
)
from rag_service.core.exceptions import GenerationError, RetrievalError, QueryQualityPromptRequired
from rag_service.core.logger import get_logger
from rag_service.config import get_settings
from rag_service.utils.chain_logger import get_chain_logger
from rag_service.services.prompt_client import (
    get_prompt_client,
    TEMPLATE_ANSWER_GENERATION,
    TEMPLATE_ANSWER_GENERATION_STRICT,
)


# Module logger
logger = get_logger(__name__)


class QAPipelineInput(CapabilityInput):
    """Input for QA pipeline execution."""

    query: str = Field(..., description="User's natural language question")
    context: Optional[QAContext] = Field(default=None, description="Query context for retrieval")
    options: QAOptions = Field(
        default_factory=lambda: QAOptions(),
        description="Processing options"
    )


class QAPipelineMetadata(BaseModel):
    """QA pipeline execution metadata."""

    trace_id: str = Field(..., description="Trace ID")
    query_rewritten: bool = Field(..., description="Whether query was rewritten")
    original_query: str = Field(..., description="Original user query")
    rewritten_query: Optional[str] = Field(default=None, description="Rewritten query if applicable")
    rewrite_reason: Optional[str] = Field(default=None, description="Reason for query rewrite")
    retrieval_count: int = Field(..., description="Number of chunks retrieved")
    generation_model: str = Field(..., description="Model used for generation")
    timing: QATiming = Field(..., description="Timing breakdown")
    # Query quality enhancement fields
    quality_enhanced: bool = Field(default=False, description="Whether query was quality enhanced")
    quality_score: float = Field(default=0.0, description="Query quality score (0.0-1.0)")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn conversations")
    dimension_feedback: Optional[str] = Field(default=None, description="Quality feedback from dimension analysis")


class QAPipelineOutput(CapabilityOutput):
    """Output from QA pipeline execution."""

    answer: str = Field(..., description="Generated answer")
    sources: List[QASourceInfo] = Field(..., description="Source document information")
    hallucination_status: HallucinationStatus = Field(..., description="Verification result")
    pipeline_metadata: QAPipelineMetadata = Field(..., description="Pipeline metadata")


class QAPipelineCapability(Capability[QAPipelineInput, QAPipelineOutput]):
    """
    Capability for complete QA pipeline orchestration.

    This capability coordinates the entire question-answering workflow:
    1. Query rewriting (optional)
    2. Knowledge base retrieval
    3. Answer generation
    4. Hallucination detection (optional)

    Features:
    - Configurable query rewriting
    - External KB integration
    - LLM-based answer generation
    - LLM-based hallucination detection
    - Fallback responses for KB errors
    - End-to-end traceability
    """

    def __init__(
        self,
        external_kb_capability: Optional[ExternalKBQueryCapability] = None,
        model_inference_capability: Optional[ModelInferenceCapability] = None,
        query_rewrite_capability: Optional[QueryRewriteCapability] = None,
        query_quality_capability: Optional[QueryQualityCapability] = None,
        hallucination_detector: Optional[Any] = None,
        fallback_service: Optional[Any] = None,
    ) -> None:
        """
        Initialize QA Pipeline Capability.

        Args:
            external_kb_capability: External KB query capability.
            model_inference_capability: Model inference capability.
            query_rewrite_capability: Query rewrite capability.
            query_quality_capability: Query quality enhancement capability.
            hallucination_detector: Hallucination detection capability.
            fallback_service: Default fallback service.
        """
        super().__init__()
        self._external_kb_capability = external_kb_capability or ExternalKBQueryCapability()
        self._model_inference_capability = model_inference_capability
        self._query_rewrite_capability = query_rewrite_capability
        self._query_quality_capability = query_quality_capability
        self._hallucination_detector = hallucination_detector
        self._fallback_service = fallback_service
        self._prompt_client = None  # Will be initialized lazily

        # Lazy load fallback service if not provided
        if self._fallback_service is None:
            from rag_service.services.default_fallback import DefaultFallbackService
            self._fallback_service = DefaultFallbackService()

    async def _get_prompt_client(self):
        """Get or create the prompt client."""
        if self._prompt_client is None:
            self._prompt_client = await get_prompt_client()
        return self._prompt_client

    async def execute(self, input_data: QAPipelineInput) -> QAPipelineOutput:
        """
        Execute the QA pipeline.

        Args:
            input_data: Pipeline input with query, context, and options.

        Returns:
            Generated answer with sources and verification status.

        Raises:
            RetrievalError: If retrieval fails and no fallback available.
            GenerationError: If answer generation fails.
        """
        start_time = time.time()
        trace_id = input_data.trace_id

        # Start chain logging
        chain_logger = get_chain_logger()
        chain_logger.start_request(trace_id, {
            "query": input_data.query,
            "company_id": (input_data.context or QAContext()).company_id,
            "file_type": (input_data.context or QAContext()).file_type,
            "options": (input_data.options or QAOptions()).model_dump(),
        })

        # Extract context with defaults
        context = input_data.context or QAContext()
        options = input_data.options or QAOptions()

        # Initialize timing
        timing_data = {
            "quality_ms": None,
            "rewrite_ms": None,
            "retrieve_ms": 0,
            "generate_ms": 0,
            "verify_ms": None,
        }

        # Step 0: Query Quality Enhancement (if enabled)
        session_id = None
        quality_score = 0.0
        dimension_feedback = None

        if options.enable_query_quality:
            logger.info(
                "QA Pipeline: Starting query quality enhancement",
                extra={"trace_id": trace_id, "original_query": input_data.query[:100]},
            )

            quality_start = time.time()

            try:
                # Initialize query quality capability if not already done
                if self._query_quality_capability is None:
                    self._query_quality_capability = QueryQualityCapability()

                quality_input = QueryQualityInput(
                    query=input_data.query,
                    company_id=context.company_id,
                    session_id=None,  # First query has no session
                    enable_auto_enrich=True,
                    require_all_dimensions=False,
                    trace_id=trace_id,
                )
                quality_result = await self._query_quality_capability.execute(quality_input)

                timing_data["quality_ms"] = (time.time() - quality_start) * 1000
                session_id = quality_result.session_id
                quality_score = quality_result.quality_score
                dimension_feedback = quality_result.feedback

                # Handle prompt action - need more information from user
                if quality_result.action == "prompt":
                    logger.info(
                        "QA Pipeline: Query quality enhancement requires more info",
                        extra={
                            "trace_id": trace_id,
                            "quality_score": quality_score,
                            "prompt_text": quality_result.prompt_text,
                        },
                    )

                    # Raise QueryQualityPromptRequired exception with all necessary info
                    raise QueryQualityPromptRequired(
                        prompt_text=quality_result.prompt_text or "请提供更多信息以便更准确地查找文档。",
                        session_id=session_id,
                        quality_score=quality_score,
                        dimensions={k: v.model_dump() for k, v in quality_result.dimensions.items()},
                        feedback=quality_result.feedback,
                    )

                # Use enriched query if available
                final_query = quality_result.enriched_query or input_data.query

                logger.info(
                    "QA Pipeline: Query quality enhancement completed",
                    extra={
                        "trace_id": trace_id,
                        "quality_score": quality_score,
                        "session_id": session_id,
                        "final_query": final_query[:100],
                    },
                )

            except RetrievalError as e:
                # Re-raise RetrievalError for prompt handling
                raise
            except Exception as e:
                logger.warning(
                    "QA Pipeline: Query quality enhancement failed, using original query",
                    extra={"trace_id": trace_id, "error": str(e)},
                )
                # Continue with original query on failure
                final_query = input_data.query
        else:
            final_query = input_data.query

        # Step 1: Query rewriting (if enabled)
        query_rewritten = False
        rewrite_reason = None

        if options.enable_query_rewrite:
            logger.info(
                "QA Pipeline: Starting query rewriting",
                extra={"trace_id": trace_id, "original_query": final_query[:100]},
            )

            rewrite_start = time.time()

            try:
                # Initialize query rewrite capability if not already done
                if self._query_rewrite_capability is None:
                    if self._model_inference_capability:
                        # Reuse the model inference capability's client
                        self._query_rewrite_capability = QueryRewriteCapability(
                            litellm_client=self._model_inference_capability._litellm_client
                        )
                    else:
                        self._query_rewrite_capability = QueryRewriteCapability()

                rewrite_input = QueryRewriteInput(
                    original_query=final_query,
                    context=context,
                    trace_id=trace_id,
                )
                rewrite_result = await self._query_rewrite_capability.execute(rewrite_input)

                timing_data["rewrite_ms"] = (time.time() - rewrite_start) * 1000
                final_query = rewrite_result.rewritten_query
                query_rewritten = rewrite_result.was_rewritten
                rewrite_reason = rewrite_result.rewrite_reason

                # Log stage to chain logger
                chain_logger.log_stage(
                    "query_rewrite",
                    {
                        "original_query": input_data.query,
                        "rewritten_query": final_query,
                        "was_rewritten": query_rewritten,
                        "reason": rewrite_reason,
                    },
                    timing_data["rewrite_ms"],
                )

                logger.info(
                    "QA Pipeline: Query rewriting completed",
                    extra={
                        "trace_id": trace_id,
                        "was_rewritten": query_rewritten,
                        "final_query": final_query[:100],
                        "rewrite_reason": rewrite_reason,
                    },
                )

            except Exception as e:
                logger.warning(
                    "QA Pipeline: Query rewriting failed, using original query",
                    extra={"trace_id": trace_id, "error": str(e)},
                )
                # Continue with enriched query on failure
                query_rewritten = False

        # Step 1: Knowledge base retrieval
        logger.info("QA Pipeline: Starting retrieval", extra={"trace_id": trace_id})

        try:
            retrieve_start = time.time()
            kb_input = ExternalKBQueryInput(
                query=final_query,
                comp_id=context.company_id,
                file_type=context.file_type or "PublicDocDispatch",
                doc_date=context.doc_date,
                topk=options.top_k,
                search_type=1,  # fulltext search
            )
            kb_result = await self._external_kb_capability.execute(kb_input)
            timing_data["retrieve_ms"] = (time.time() - retrieve_start) * 1000

            chunks = kb_result.chunks
            retrieval_count = len(chunks)

            # Log stage to chain logger
            chain_logger.log_stage(
                "retrieval",
                {
                    "query_used": final_query,
                    "chunk_count": retrieval_count,
                    "top_k": options.top_k,
                    "sources": [
                        {
                            "document_name": c.get("source_doc", "N/A"),
                            "score": c.get("score", 0),
                        }
                        for c in chunks[:5]  # Top 5 sources
                    ],
                },
                timing_data["retrieve_ms"],
            )

            logger.info(
                "QA Pipeline: Retrieval complete",
                extra={
                    "trace_id": trace_id,
                    "chunk_count": retrieval_count,
                },
            )

        except RetrievalError as e:
            logger.error(
                "QA Pipeline: Retrieval failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            # Return fallback response
            return self._create_fallback_response(
                error_type=FallbackErrorType.KB_UNAVAILABLE,
                original_query=input_data.query,
                trace_id=trace_id,
                timing_data=timing_data,
                start_time=start_time,
            )

        # Step 2: Check if KB returned empty results
        if retrieval_count == 0:
            logger.info(
                "QA Pipeline: KB returned empty results",
                extra={"trace_id": trace_id},
            )
            return self._create_fallback_response(
                error_type=FallbackErrorType.KB_EMPTY,
                original_query=input_data.query,
                trace_id=trace_id,
                timing_data=timing_data,
                start_time=start_time,
            )

        # Step 3: Generate answer using retrieved chunks
        logger.info("QA Pipeline: Generating answer", extra={"trace_id": trace_id})

        try:
            generate_start = time.time()

            # Build prompt with retrieved chunks
            chunks_text = self._format_chunks_for_prompt(chunks)
            prompt = await self._build_generation_prompt(input_data.query, chunks_text, trace_id)

            if self._model_inference_capability is None:
                # Check configured default gateway
                settings = get_settings()
                default_gateway = settings.default_gateway  # "http" or "litellm"

                if default_gateway == "http":
                    # Try to use HTTP gateway for cloud completion service
                    try:
                        from rag_service.inference.gateway import get_http_gateway
                        http_gateway = await get_http_gateway()
                        self._model_inference_capability = ModelInferenceCapability(
                            http_client=http_gateway,
                            default_gateway="http"
                        )
                        logger.info("QA Pipeline: Using HTTP gateway for model inference")
                    except Exception as e:
                        logger.warning(f"QA Pipeline: HTTP gateway not available, using LiteLLM: {e}")
                        from rag_service.inference.gateway import get_gateway
                        gateway = await get_gateway()
                        self._model_inference_capability = ModelInferenceCapability(
                            litellm_client=gateway,
                            default_gateway="litellm"
                        )
                else:
                    # Use LiteLLM gateway
                    from rag_service.inference.gateway import get_gateway
                    gateway = await get_gateway()
                    self._model_inference_capability = ModelInferenceCapability(
                        litellm_client=gateway,
                        default_gateway="litellm"
                    )

            inference_input = ModelInferenceInput(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.7,
                trace_id=trace_id,
                # Use the default gateway configured in settings
                gateway_backend=self._model_inference_capability._default_gateway,
            )
            inference_result = await self._model_inference_capability.execute(inference_input)

            timing_data["generate_ms"] = (time.time() - generate_start) * 1000
            generated_answer = inference_result.text
            generation_model = inference_result.model

            # Log stage to chain logger
            chain_logger.log_stage(
                "generation",
                {
                    "model": generation_model,
                    "gateway_backend": self._model_inference_capability._default_gateway,
                    "answer_length": len(generated_answer),
                    "answer_preview": generated_answer[:200],
                    "chunks_used": retrieval_count,
                },
                timing_data["generate_ms"],
            )

            logger.info(
                "QA Pipeline: Answer generated",
                extra={
                    "trace_id": trace_id,
                    "model": generation_model,
                    "answer_length": len(generated_answer),
                },
            )

        except Exception as e:
            logger.error(
                "QA Pipeline: Generation failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            raise GenerationError(
                message="Failed to generate answer",
                detail=str(e),
            ) from e

        # Step 4: Build sources list
        sources = self._build_sources_list(chunks)

        # Step 5: Hallucination detection (if enabled)
        hallucination_status = None
        verify_attempts = 0
        max_attempts = get_settings().qa.max_regen_attempts if options.enable_hallucination_check else 0

        while options.enable_hallucination_check and verify_attempts <= max_attempts:
            verify_attempts += 1
            logger.info(
                f"QA Pipeline: Hallucination check attempt {verify_attempts}",
                extra={"trace_id": trace_id},
            )

            try:
                verify_start = time.time()

                # Initialize hallucination detector if not already done
                if self._hallucination_detector is None:
                    self._hallucination_detector = HallucinationDetectionCapability()

                # Perform hallucination check
                check_input = HallucinationCheckInput(
                    generated_answer=generated_answer,
                    retrieved_chunks=chunks,
                    threshold=get_settings().qa.hallucination_threshold,
                    method="llm",  # Use LLM-based verification by default
                    trace_id=trace_id,
                )
                check_result = await self._hallucination_detector.execute(check_input)

                timing_data["verify_ms"] = (time.time() - verify_start) * 1000

                logger.info(
                    "QA Pipeline: Hallucination check completed",
                    extra={
                        "trace_id": trace_id,
                        "confidence": check_result.confidence,
                        "threshold": get_settings().qa.hallucination_threshold,
                        "passed": check_result.passed,
                        "attempt": verify_attempts,
                    },
                )

                # If check passed, we're done
                if check_result.passed:
                    hallucination_status = HallucinationStatus(
                        checked=True,
                        passed=True,
                        confidence=check_result.confidence,
                        flagged_claims=[],
                    )
                    break

                # If check failed but this is the last attempt, return with warning
                if verify_attempts > max_attempts:
                    hallucination_status = HallucinationStatus(
                        checked=True,
                        passed=False,
                        confidence=check_result.confidence,
                        flagged_claims=check_result.flagged_claims,
                        warning_message="无法验证答案的准确性，请谨慎参考。" if len(check_result.flagged_claims) > 0 else None,
                    )
                    logger.warning(
                        "QA Pipeline: Hallucination check failed after max attempts",
                        extra={
                            "trace_id": trace_id,
                            "confidence": check_result.confidence,
                            "attempts": verify_attempts,
                        },
                    )
                    break

                # Regenerate answer with stricter prompt
                logger.info(
                    "QA Pipeline: Regenerating answer with stricter prompt",
                    extra={"trace_id": trace_id, "attempt": verify_attempts},
                )

                generate_start = time.time()
                strict_prompt = await self._build_strict_generation_prompt(
                    input_data.query,
                    self._format_chunks_for_prompt(chunks),
                    trace_id,
                )

                inference_input = ModelInferenceInput(
                    prompt=strict_prompt,
                    max_tokens=1500,
                    temperature=0.3,  # Lower temperature for more deterministic output
                    trace_id=trace_id,
                )
                inference_result = await self._model_inference_capability.execute(inference_input)

                timing_data["generate_ms"] += (time.time() - generate_start) * 1000
                generated_answer = inference_result.text

                # Re-build sources with potentially new chunks
                sources = self._build_sources_list(chunks)

            except Exception as e:
                logger.error(
                    f"QA Pipeline: Hallucination check attempt {verify_attempts} failed",
                    extra={"trace_id": trace_id, "error": str(e)},
                )
                # On error, if not the last attempt, try regeneration
                if verify_attempts <= max_attempts:
                    continue
                # Otherwise mark as not checked
                hallucination_status = HallucinationStatus(
                    checked=False,
                    passed=False,
                    confidence=0.0,
                    warning_message="验证过程中发生错误",
                )
                break

        # If hallucination check was not enabled, create unchecked status
        if hallucination_status is None:
            hallucination_status = HallucinationStatus(
                checked=False,
                passed=False,
                confidence=0.0,
            )

        # Step 6: Create response
        timing_data["total_ms"] = (time.time() - start_time) * 1000

        timing = QATiming(**timing_data)

        metadata = QAPipelineMetadata(
            trace_id=trace_id,
            query_rewritten=query_rewritten,
            original_query=input_data.query,
            rewritten_query=final_query if query_rewritten else None,
            rewrite_reason=rewrite_reason,
            retrieval_count=retrieval_count,
            generation_model=generation_model,
            timing=timing,
            quality_enhanced=options.enable_query_quality and quality_score > 0,
            quality_score=quality_score,
            session_id=session_id,
            dimension_feedback=dimension_feedback,
        )

        # End chain logging
        chain_logger.end_request(
            {
                "answer": generated_answer,
                "answer_length": len(generated_answer),
                "source_count": len(sources),
                "hallucination_checked": hallucination_status.checked,
                "hallucination_passed": hallucination_status.passed if hallucination_status.checked else None,
            },
            timing_data["total_ms"],
        )

        return QAPipelineOutput(
            answer=generated_answer,
            sources=sources,
            hallucination_status=hallucination_status,
            pipeline_metadata=metadata,
        )

    def _format_chunks_for_prompt(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks for prompt."""
        formatted = []
        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})
            doc_name = metadata.get("document_name", metadata.get("source_doc", f"Document {i+1}"))
            formatted.append(f"[{doc_name}]\n{content}")
        return "\n\n".join(formatted)

    async def _build_generation_prompt(self, query: str, chunks_text: str, trace_id: str) -> str:
        """Build prompt for answer generation using Prompt Service."""
        prompt_client = await self._get_prompt_client()

        variables = {
            "query": query,
            "chunks_text": chunks_text,
        }

        return await prompt_client.get_prompt(
            template_id=TEMPLATE_ANSWER_GENERATION,
            variables=variables,
            trace_id=trace_id,
        )

    async def _build_strict_generation_prompt(self, query: str, chunks_text: str, trace_id: str) -> str:
        """Build strict prompt for answer regeneration using Prompt Service.

        This prompt is more restrictive to reduce hallucination:
        - Explicitly forbids information outside the chunks
        - Requires citations for every claim
        - Uses lower temperature for more deterministic output
        """
        prompt_client = await self._get_prompt_client()

        variables = {
            "query": query,
            "chunks_text": chunks_text,
        }

        return await prompt_client.get_prompt(
            template_id=TEMPLATE_ANSWER_GENERATION_STRICT,
            variables=variables,
            trace_id=trace_id,
        )

    def _build_sources_list(self, chunks: List[Dict[str, Any]]) -> List[QASourceInfo]:
        """Build sources list from retrieved chunks."""
        sources = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            content = chunk.get("content", "")
            sources.append(QASourceInfo(
                chunk_id=chunk.get("chunk_id", chunk.get("id", "")),
                document_id=metadata.get("document_id", ""),
                document_name=metadata.get("document_name", metadata.get("source_doc", "")),
                dataset_id=metadata.get("dataset_id", ""),
                dataset_name=metadata.get("dataset_name", ""),
                score=chunk.get("score", 0.0),
                content_preview=content[:200] if content else "",
            ))
        return sources

    def _create_fallback_response(
        self,
        error_type: FallbackErrorType,
        original_query: str,
        trace_id: str,
        timing_data: Dict[str, Any],
        start_time: float,
    ) -> QAPipelineOutput:
        """Create fallback response for error scenarios."""
        from rag_service.services.default_fallback import DefaultFallbackService, FallbackRequest

        if self._fallback_service is None:
            self._fallback_service = DefaultFallbackService()

        # Pass error_type directly, not as FallbackRequest object
        fallback_resp = self._fallback_service.get_fallback(error_type)

        timing_data["total_ms"] = (time.time() - start_time) * 1000
        timing = QATiming(**timing_data)

        metadata = QAPipelineMetadata(
            trace_id=trace_id,
            query_rewritten=False,
            original_query=original_query,
            retrieval_count=0,
            generation_model="none",
            timing=timing,
        )

        return QAPipelineOutput(
            answer=fallback_resp.message,
            sources=[],
            hallucination_status=HallucinationStatus(
                checked=False,
                passed=False,
                confidence=0.0,
                warning_message=fallback_resp.message,
            ),
            pipeline_metadata=metadata,
        )

    def validate_input(self, input_data: QAPipelineInput) -> CapabilityValidationResult:
        """Validate QA pipeline input."""
        errors = []
        warnings = []

        # Validate query
        if not input_data.query or not input_data.query.strip():
            errors.append("Query cannot be empty")

        # Validate context if provided
        if input_data.context:
            if not input_data.context.company_id:
                errors.append("company_id is required in context")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def get_health(self) -> Dict[str, Any]:
        """Get health status of QA pipeline components."""
        health = {
            "status": "initializing",
        }

        # Check external KB
        try:
            kb_health = await self._external_kb_capability.get_health()
            health["external_kb"] = kb_health.get("external_kb", "unknown")
        except Exception:
            health["external_kb"] = "error"

        # Check model inference
        if self._model_inference_capability:
            try:
                model_health = self._model_inference_capability.get_health()
                health["litellm"] = model_health.get("litellm", "unknown")
            except Exception:
                health["litellm"] = "error"
        else:
            health["litellm"] = "not_configured"

        # Check fallback service
        health["fallback_ready"] = "ready" if self._fallback_service else "not_configured"

        # Check hallucination detector
        if self._hallucination_detector:
            try:
                detector_health = self._hallucination_detector.get_health()
                health["hallucination_detector"] = detector_health.get("status", "unknown")
            except Exception:
                health["hallucination_detector"] = "error"
        else:
            health["hallucination_detector"] = "not_configured"

        # Overall status
        if health.get("external_kb") == "connected" and health.get("litellm") == "connected":
            health["status"] = "healthy"
        else:
            health["status"] = "degraded"

        return health

    async def stream_execute(
        self,
        input_data: QAPipelineInput,
    ) -> AsyncGenerator[str, None]:
        """
        Execute the QA pipeline with streaming response.

        This method streams answer tokens as they are generated.
        Hallucination detection runs asynchronously after streaming completes.

        Args:
            input_data: Pipeline input with query, context, and options.

        Yields:
            Individual tokens of the generated answer.

        Raises:
            RetrievalError: If retrieval fails and no fallback available.
            GenerationError: If answer generation fails.
        """
        start_time = time.time()
        trace_id = input_data.trace_id

        # Extract context with defaults
        context = input_data.context or QAContext()
        options = input_data.options or QAOptions()

        # Query rewriting (same as non-streaming)
        final_query = input_data.query

        if options.enable_query_rewrite:
            try:
                if self._query_rewrite_capability is None:
                    if self._model_inference_capability:
                        self._query_rewrite_capability = QueryRewriteCapability(
                            litellm_client=self._model_inference_capability._litellm_client
                        )
                    else:
                        self._query_rewrite_capability = QueryRewriteCapability()

                rewrite_input = QueryRewriteInput(
                    original_query=input_data.query,
                    context=context,
                    trace_id=trace_id,
                )
                rewrite_result = await self._query_rewrite_capability.execute(rewrite_input)
                final_query = rewrite_result.rewritten_query

            except Exception as e:
                logger.warning(
                    "QA Pipeline Stream: Query rewriting failed",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        # Knowledge base retrieval
        try:
            kb_input = ExternalKBQueryInput(
                query=final_query,
                comp_id=context.company_id,
                file_type=context.file_type or "PublicDocDispatch",
                doc_date=context.doc_date,
                topk=options.top_k,
                search_type=1,
            )
            kb_result = await self._external_kb_capability.execute(kb_input)
            chunks = kb_result.chunks

            if not chunks:
                # Return fallback message token by token
                fallback_msg = "抱歉，没有找到与您的问题相关的信息。"
                for char in fallback_msg:
                    yield char
                return

        except RetrievalError as e:
            logger.error(
                "QA Pipeline Stream: Retrieval failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            # Return fallback message token by token
            fallback_msg = "知识库暂时无法访问，请稍后再试。"
            for char in fallback_msg:
                yield char
            return

        # Generate answer with streaming
        try:
            # Build prompt
            chunks_text = self._format_chunks_for_prompt(chunks)
            prompt = await self._build_generation_prompt(input_data.query, chunks_text, trace_id)

            if self._model_inference_capability is None:
                from rag_service.inference.gateway import get_gateway
                gateway = await get_gateway()
                self._model_inference_capability = ModelInferenceCapability(
                    litellm_client=gateway
                )

            # Stream tokens from model inference
            async for token in self._model_inference_capability.stream_execute(
                ModelInferenceInput(
                    prompt=prompt,
                    max_tokens=1500,
                    temperature=0.7,
                    trace_id=trace_id,
                )
            ):
                yield token

        except Exception as e:
            logger.error(
                "QA Pipeline Stream: Generation failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            raise GenerationError(
                message="Failed to generate streaming answer",
                detail=str(e),
            ) from e
