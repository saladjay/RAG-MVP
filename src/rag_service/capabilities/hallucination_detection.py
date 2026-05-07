"""
Hallucination Detection Capability for RAG Service.

This capability verifies that generated answers are based on retrieved content
rather than fabricated information using:
1. Similarity-based comparison (sentence-transformers)
2. LLM-based verification (HTTP API with Qwen3)
"""

import json
import numpy as np
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.logger import get_logger
from rag_service.config import get_settings
from rag_service.inference.gateway import get_http_gateway
from rag_service.services.prompt_client import (
    get_prompt_client,
    TEMPLATE_HALLUCINATION_DETECTION,
)

# Optional sentence-transformers import
# Suppress all errors since torch/DLL issues can cause OSError
SentenceTransformer = None
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from sentence_transformers import SentenceTransformer as _ST
        SentenceTransformer = _ST
        SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    # Import failed - hallucination detection will use LLM method
    pass


# Module logger
logger = get_logger(__name__)


class HallucinationCheckInput(CapabilityInput):
    """Input for hallucination detection."""

    generated_answer: str = Field(..., description="Generated answer to verify")
    retrieved_chunks: List[Dict[str, Any]] = Field(
        ..., description="Retrieved document chunks"
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for passing verification"
    )
    method: str = Field(
        default="llm",
        description="Detection method: 'similarity' or 'llm'"
    )


class HallucinationCheckOutput(CapabilityOutput):
    """Output from hallucination detection."""

    passed: bool = Field(..., description="Whether verification passed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Raw similarity score")
    flagged_claims: List[str] = Field(
        default_factory=list, description="Flagged claims/sections"
    )
    verification_method: str = Field(
        default="llm", description="Method used for verification"
    )
    reasoning: str = Field(
        default="", description="LLM reasoning for the decision"
    )


class HallucinationDetectionCapability(Capability[HallucinationCheckInput, HallucinationCheckOutput]):
    """
    Capability for hallucination detection.

    This capability verifies that generated answers are supported by
    the retrieved content using multiple methods:

    Methods:
    - LLM-based verification (default): Uses Qwen3 model via HTTP API
    - Similarity-based: Uses sentence-transformers embeddings

    LLM-based detection works by:
    1. Constructing a prompt with retrieved context
    2. Asking the LLM to verify if the answer is supported by context
    3. Extracting confidence score and reasoning from LLM response
    """

    def __init__(self, embeddings_model: Optional[Any] = None) -> None:
        """
        Initialize Hallucination Detection Capability.

        Args:
            embeddings_model: Sentence-transformers model for embeddings.
                            If None, will load from config.
        """
        super().__init__()
        self._embeddings_model = embeddings_model
        self._llm_gateway = None
        self._prompt_client = None  # Will be initialized lazily

        # Check available methods
        self._llm_available = self._check_llm_available()
        self._similarity_available = SENTENCE_TRANSFORMERS_AVAILABLE

        logger.info(
            "Hallucination detection initialization",
            extra={
                "llm_available": self._llm_available,
                "similarity_available": self._similarity_available,
            },
        )

        # Lazy load similarity model if needed
        if self._similarity_available and self._embeddings_model is None:
            self._load_embeddings_model()

    def _check_llm_available(self) -> bool:
        """Check if LLM gateway is available."""
        try:
            settings = get_settings()
            return settings.cloud_completion.enabled
        except Exception:
            return False

    async def _get_llm_gateway(self):
        """Get or create LLM gateway."""
        if self._llm_gateway is None:
            self._llm_gateway = await get_http_gateway()
        return self._llm_gateway

    async def _get_prompt_client(self):
        """Get or create the prompt client."""
        if self._prompt_client is None:
            self._prompt_client = await get_prompt_client()
        return self._prompt_client

    def _load_embeddings_model(self) -> None:
        """Load sentence-transformers model from configuration."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            return

        try:
            settings = get_settings()
            model_name = settings.embedding.model
            device = settings.embedding.device

            logger.info(
                f"Loading embeddings model: {model_name} on {device}",
                extra={"trace_id": "system"},
            )

            self._embeddings_model = SentenceTransformer(model_name, device=device)

            logger.info(
                "Embeddings model loaded successfully",
                extra={"trace_id": "system"},
            )

        except Exception as e:
            logger.error(
                f"Failed to load embeddings model: {e}",
                extra={"trace_id": "system"},
            )
            self._embeddings_model = None
            self._similarity_available = False

    async def execute(self, input_data: HallucinationCheckInput) -> HallucinationCheckOutput:
        """
        Execute hallucination detection.

        Args:
            input_data: Detection input with answer and chunks.

        Returns:
            Verification result with confidence and flagged claims.

        Raises:
            ValueError: If no detection method is available.
        """
        trace_id = input_data.trace_id
        method = input_data.method or "llm"

        # Handle edge cases
        if not input_data.generated_answer or not input_data.generated_answer.strip():
            logger.warning(
                "Empty answer provided for hallucination detection",
                extra={"trace_id": trace_id},
            )
            return HallucinationCheckOutput(
                passed=False,
                confidence=0.0,
                similarity_score=0.0,
                flagged_claims=["Empty answer"],
                verification_method=method,
                trace_id=trace_id,
            )

        if not input_data.retrieved_chunks:
            logger.warning(
                "No retrieved chunks provided for hallucination detection",
                extra={"trace_id": trace_id},
            )
            return HallucinationCheckOutput(
                passed=False,
                confidence=0.0,
                similarity_score=0.0,
                flagged_claims=["No context available for verification"],
                verification_method=method,
                trace_id=trace_id,
            )

        # Choose detection method
        if method == "llm" and self._llm_available:
            return await self._detect_with_llm(input_data)
        elif method == "similarity" and self._similarity_available:
            return await self._detect_with_similarity(input_data)
        elif method == "llm":
            # LLM requested but not available, fallback to similarity
            if self._similarity_available:
                logger.warning(
                    "LLM method requested but not available, using similarity method",
                    extra={"trace_id": trace_id},
                )
                return await self._detect_with_similarity(input_data)
            else:
                logger.error(
                    "No detection method available (both LLM and similarity unavailable)",
                    extra={"trace_id": trace_id},
                )
                return HallucinationCheckOutput(
                    passed=True,  # Default to pass to allow operation
                    confidence=0.0,
                    similarity_score=0.0,
                    flagged_claims=[],
                    verification_method="disabled",
                    reasoning="Detection unavailable - no LLM or sentence-transformers configured",
                    trace_id=trace_id,
                )
        else:
            # Similarity requested but not available
            logger.error(
                f"Similarity method requested but not available",
                extra={"trace_id": trace_id},
            )
            return HallucinationCheckOutput(
                passed=True,
                confidence=0.0,
                similarity_score=0.0,
                flagged_claims=[],
                verification_method="disabled",
                reasoning="Similarity detection unavailable - sentence-transformers not configured",
                trace_id=trace_id,
            )

    async def _detect_with_llm(
        self, input_data: HallucinationCheckInput
    ) -> HallucinationCheckOutput:
        """
        Detect hallucination using LLM-based verification.

        Args:
            input_data: Detection input.

        Returns:
            Verification result from LLM analysis.
        """
        trace_id = input_data.trace_id

        logger.info(
            "Starting LLM-based hallucination detection",
            extra={
                "trace_id": trace_id,
                "threshold": input_data.threshold,
                "chunk_count": len(input_data.retrieved_chunks),
            },
        )

        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(input_data.retrieved_chunks, 1):
            content = chunk.get("content", "")
            source = chunk.get("source_doc", chunk.get("metadata", {}).get("document_name", f"Source {i}"))
            context_parts.append(f"[Source {i}: {source}]\n{content}")

        context = "\n\n".join(context_parts)

        # Get prompt from Prompt Service
        prompt_client = await self._get_prompt_client()

        variables = {
            "context": context,
            "answer": input_data.generated_answer,
        }

        prompt = await prompt_client.get_prompt(
            template_id=TEMPLATE_HALLUCINATION_DETECTION,
            variables=variables,
            trace_id=trace_id,
        )

        try:
            gateway = await self._get_llm_gateway()

            result = await gateway.acomplete(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent analysis
            )

            response_text = result.text.strip()

            # Try to extract JSON from response
            # Handle various formats:
            # 1. Pure JSON response
            # 2. JSON with text before/after
            # 3. JSON in markdown code blocks

            analysis = None

            # First try to find JSON between code blocks
            if "```json" in response_text and analysis is None:
                # Extract from markdown code block
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    json_str = response_text[start:end].strip()
                    try:
                        analysis = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass  # Try other methods

            if "```" in response_text and analysis is None:
                # Extract from generic code block
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end > start:
                    json_str = response_text[start:end].strip()
                    try:
                        analysis = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass  # Try other methods

            # Try to find JSON object by matching braces
            if analysis is None:
                json_start = response_text.find("{")
                if json_start >= 0:
                    # Find matching closing brace
                    brace_count = 0
                    for i in range(json_start, len(response_text)):
                        if response_text[i] == '{':
                            brace_count += 1
                        elif response_text[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_str = response_text[json_start:i+1]
                                try:
                                    analysis = json.loads(json_str)
                                    break
                                except json.JSONDecodeError:
                                    pass

            # Check if we successfully parsed JSON
            if analysis is not None:

                is_supported = analysis.get("is_supported", True)
                confidence = float(analysis.get("confidence", 0.7))
                reasoning = analysis.get("reasoning", "")
                issues = analysis.get("issues", [])

                # Determine pass/fail based on both is_supported and threshold
                passed = is_supported and confidence >= input_data.threshold

                # Build flagged claims from issues
                flagged_claims = issues if isinstance(issues, list) else []

                logger.info(
                    "LLM hallucination detection completed",
                    extra={
                        "trace_id": trace_id,
                        "is_supported": is_supported,
                        "confidence": confidence,
                        "passed": passed,
                    },
                )

                return HallucinationCheckOutput(
                    passed=passed,
                    confidence=confidence,
                    similarity_score=confidence,  # Use same value for compatibility
                    flagged_claims=flagged_claims,
                    verification_method="llm",
                    reasoning=reasoning,
                    trace_id=trace_id,
                )
            else:
                # Couldn't parse JSON, use fallback
                logger.warning(
                    "Failed to parse LLM response as JSON, using fallback analysis",
                    extra={"trace_id": trace_id, "response": response_text[:200]},
                )
                return self._fallback_llm_analysis(response_text, input_data)

        except Exception as e:
            logger.error(
                "LLM hallucination detection failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            # Return pass with error note to allow operation to continue
            return HallucinationCheckOutput(
                passed=True,
                confidence=0.0,
                similarity_score=0.0,
                flagged_claims=[],
                verification_method="llm_error",
                reasoning=f"LLM检测失败: {str(e)}",
                trace_id=trace_id,
            )

    def _fallback_llm_analysis(
        self, response_text: str, input_data: HallucinationCheckInput
    ) -> HallucinationCheckOutput:
        """
        Fallback analysis when JSON parsing fails.

        Args:
            response_text: Raw LLM response.
            input_data: Original input data.

        Returns:
            Best-effort analysis result.
        """
        trace_id = input_data.trace_id

        # Simple keyword-based analysis
        response_lower = response_text.lower()

        # Check for positive indicators
        positive_indicators = ["符合", "正确", "准确", "有依据", "支持", "true", "supported"]
        negative_indicators = ["不符合", "错误", "不准确", "没有依据", "不支持", "false", "not supported", "hallucination"]

        positive_count = sum(1 for indicator in positive_indicators if indicator in response_text)
        negative_count = sum(1 for indicator in negative_indicators if indicator in response_text)

        if positive_count > negative_count:
            confidence = 0.8
            passed = True
            reasoning = "基于关键词分析，回答似乎符合参考内容。"
        elif negative_count > positive_count:
            confidence = 0.3
            passed = False
            reasoning = "基于关键词分析，回答可能不符合参考内容。"
        else:
            confidence = 0.5
            passed = confidence >= input_data.threshold
            reasoning = "无法确定回答是否符合参考内容。"

        return HallucinationCheckOutput(
            passed=passed,
            confidence=confidence,
            similarity_score=confidence,
            flagged_claims=[] if passed else ["需要人工核查"],
            verification_method="llm_fallback",
            reasoning=reasoning,
            trace_id=trace_id,
        )

    async def _detect_with_similarity(
        self, input_data: HallucinationCheckInput
    ) -> HallucinationCheckOutput:
        """
        Detect hallucination using similarity-based comparison.

        Args:
            input_data: Detection input.

        Returns:
            Verification result from similarity analysis.
        """
        trace_id = input_data.trace_id

        logger.info(
            "Starting similarity-based hallucination detection",
            extra={
                "trace_id": trace_id,
                "threshold": input_data.threshold,
                "chunk_count": len(input_data.retrieved_chunks),
            },
        )

        # Step 1: Generate embedding for the answer
        answer_embedding = self._encode_text(input_data.generated_answer)

        # Step 2: Generate embeddings for all chunks
        chunk_texts = [
            chunk.get("content", "") for chunk in input_data.retrieved_chunks
        ]
        chunk_embeddings = self._embeddings_model.encode(
            chunk_texts,
            convert_to_numpy=True,
        )

        # Step 3: Compute cosine similarities
        similarities = self._compute_cosine_similarity(
            answer_embedding,
            chunk_embeddings,
        )

        # Step 4: Get max similarity as confidence score
        max_similarity = float(np.max(similarities)) if len(similarities) > 0 else 0.0

        # Step 5: Compare to threshold
        passed = max_similarity >= input_data.threshold

        # Step 6: Generate flagged claims if failed
        flagged_claims = []
        if not passed:
            flagged_claims.append(input_data.generated_answer[:200])

        logger.info(
            "Similarity hallucination detection completed",
            extra={
                "trace_id": trace_id,
                "similarity": max_similarity,
                "threshold": input_data.threshold,
                "passed": passed,
            },
        )

        return HallucinationCheckOutput(
            passed=passed,
            confidence=max_similarity,
            similarity_score=max_similarity,
            flagged_claims=flagged_claims,
            verification_method="similarity",
            trace_id=trace_id,
        )

    def _encode_text(self, text: str) -> np.ndarray:
        """
        Encode text into embedding vector.

        Args:
            text: Text to encode.

        Returns:
            Embedding vector as numpy array.
        """
        embedding = self._embeddings_model.encode(
            text,
            convert_to_numpy=True,
        )
        return embedding

    def _compute_cosine_similarity(
        self,
        query_embedding: np.ndarray,
        chunk_embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Compute cosine similarity between query and chunks.

        Args:
            query_embedding: Query embedding vector.
            chunk_embeddings: Array of chunk embedding vectors.

        Returns:
            Array of similarity scores.
        """
        # Normalize embeddings
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        chunk_norms = chunk_embeddings / (
            np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-8
        )

        # Compute dot product (cosine similarity for normalized vectors)
        similarities = np.dot(chunk_norms, query_norm)

        return similarities

    def validate_input(self, input_data: HallucinationCheckInput) -> CapabilityValidationResult:
        """Validate hallucination detection input."""
        errors = []
        warnings = []

        # Validate answer
        if not input_data.generated_answer:
            warnings.append("Empty generated answer")

        # Validate chunks
        if not input_data.retrieved_chunks:
            warnings.append("No retrieved chunks provided")

        # Validate threshold
        if not 0.0 <= input_data.threshold <= 1.0:
            errors.append("Threshold must be between 0.0 and 1.0")

        # Validate method
        if input_data.method not in ("llm", "similarity"):
            errors.append("Method must be 'llm' or 'similarity'")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_health(self) -> Dict[str, Any]:
        """Get health status of hallucination detection."""
        health = {
            "llm_available": self._llm_available,
            "similarity_available": self._similarity_available,
            "default_method": "llm" if self._llm_available else ("similarity" if self._similarity_available else "none"),
        }

        if self._similarity_available and self._embeddings_model:
            try:
                settings = get_settings()
                health["similarity_model"] = settings.embedding.model
                health["similarity_device"] = settings.embedding.device
            except Exception:
                pass

        return health
