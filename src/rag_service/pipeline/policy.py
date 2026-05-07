"""
PipelinePolicy — execution control parameters for the atomic pipeline.

Constructed from existing QueryConfig values. No new environment variables.

Controls which steps run, thresholds, and prompt template IDs.

API Reference:
- Location: src/rag_service/pipeline/policy.py
- Used by: PipelineRunner._should_run()
"""

from typing import Any

from pydantic import BaseModel, Field

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class PipelinePolicy(BaseModel):
    """Execution control parameters for the pipeline.

    Maps from existing QueryConfig — no new env vars needed.
    """

    # === Step enable/disable flags ===
    enable_extraction: bool = Field(default=True)
    enable_rewrite: bool = Field(default=True)
    enable_reasoning: bool = Field(default=False, description="Phase 1: always off")
    enable_verification: bool = Field(default=True)
    enable_execution: bool = Field(default=True)

    # === Execution parameters ===
    rewrite_depth: int = Field(default=1, description="Phase 1: always 1")
    max_regen_attempts: int = Field(default=0)
    hallucination_threshold: float = Field(default=0.7)

    # === Strategy selection ===
    extraction_mode: str = Field(default="basic")
    retrieval_backend: str = Field(default="external_kb")
    verification_method: str = Field(default="similarity")

    # === Prompt template IDs ===
    prompt_extraction: str = Field(default="query_dimension_analysis")
    prompt_rewrite: str = Field(default="qa_query_rewrite")
    prompt_reasoning: str = Field(default="qa_reasoning")
    prompt_generation: str = Field(default="qa_answer_generate")
    prompt_verification: str = Field(default="qa_hallucination_detection")

    # === Step name → enable flag mapping ===
    _STEP_ENABLE_MAP: dict[str, str] = {
        "extraction": "enable_extraction",
        "rewrite": "enable_rewrite",
        "reasoning": "enable_reasoning",
        "verification": "enable_verification",
        "execution": "enable_execution",
    }

    def _should_run(self, step_name: str) -> bool:
        """Check if a step should execute based on policy.

        Retrieval and generation always run. Other steps check their
        enable flag.

        Args:
            step_name: The step's name property.

        Returns:
            True if the step should execute.
        """
        # Always-run steps
        if step_name in ("retrieval", "generation"):
            return True

        flag_name = self._STEP_ENABLE_MAP.get(step_name)
        if flag_name is None:
            # Unknown step defaults to running
            logger.warning(
                f"Unknown step '{step_name}' not in policy, defaulting to run"
            )
            return True

        return getattr(self, flag_name, True)

    @classmethod
    def from_config(cls, config: Any) -> "PipelinePolicy":
        """Create PipelinePolicy from existing QueryConfig.

        Args:
            config: QueryConfig instance from get_settings().query.

        Returns:
            PipelinePolicy with values mapped from config.
        """
        return cls(
            enable_extraction=True,
            enable_rewrite=getattr(config, "enable_query_rewrite", True),
            enable_reasoning=False,  # Phase 1: always off
            enable_verification=getattr(config, "enable_hallucination_check", True),
            enable_execution=True,
            max_regen_attempts=getattr(config, "max_regen_attempts", 0),
            hallucination_threshold=getattr(config, "hallucination_threshold", 0.7),
            extraction_mode=getattr(config, "quality_mode", "basic"),
            retrieval_backend=getattr(config, "retrieval_backend", "external_kb"),
            verification_method=getattr(config, "hallucination_method", "similarity"),
            prompt_extraction=getattr(
                config, "dimension_analysis_template", "query_dimension_analysis"
            ),
            prompt_rewrite=getattr(
                config, "prompt_query_rewrite", "qa_query_rewrite"
            ),
            prompt_generation=getattr(
                config, "prompt_answer_generate", "qa_answer_generate"
            ),
        )
