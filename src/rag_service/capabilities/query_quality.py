"""
Query Quality Enhancement Capability.

This capability implements multi-turn conversation for gathering missing query
dimensions before executing document searches. It analyzes user queries against
required document dimensions and prompts users for missing information.

Key features:
- Dimension analysis using LLM via Prompt Service
- Redis-based session state management
- Multi-turn conversation with turn limit enforcement
- Automatic query enrichment with inferred defaults
- Knowledge base routing based on company_id and file_type

Document Dimensions (from 2025 analysis):
- Company ID (公司标识): Provided by external system
- File Category (文件类别): PublicDocDispatch (发文), PublicDocReceive (收文)
- Document Type (公文类型): Including 2025 additions (会议纪要)
- Organization (发文单位): Including 2025 additions (职工代表大会, 专业委员会)
- Year/Number (年份文号): Year and document number format
- Subject/Content (主题内容): Including 2025 expanded categories
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.config import QueryQualityConfig, get_settings
from rag_service.core.exceptions import RAGServiceError, RetrievalError
from rag_service.core.logger import get_logger
from rag_service.models.query_quality import (
    DimensionAnalysisResult,
    DimensionInfo,
    DimensionStatus,
    DimensionType,
    FileType,
    KnowledgeBaseRoute,
    QueryQualityRequest,
    QueryQualityResponse,
    SessionState,
)
from rag_service.services.prompt_client import PromptClient
from rag_service.services.session_store import SessionStoreService, get_session_store

logger = get_logger(__name__)


class QueryQualityInput(CapabilityInput):
    """Input for QueryQualityCapability.

    Attributes:
        query: User's query text
        company_id: Company identifier (from external system)
        session_id: Optional session ID for multi-turn conversations
        enable_auto_enrich: Enable automatic query enrichment
        require_all_dimensions: Require all dimensions before proceeding
    """

    query: str = Field(..., min_length=1, description="User's query text")
    company_id: str = Field(..., description="Company identifier")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn")
    enable_auto_enrich: bool = Field(default=True, description="Enable auto enrichment")
    require_all_dimensions: bool = Field(default=False, description="Require all dimensions")


class QueryQualityCapabilityOutput(CapabilityOutput):
    """Output from QueryQualityCapability.

    Attributes:
        action: Action to take (proceed/prompt/complete)
        enriched_query: The enriched query (if action is proceed)
        prompt_text: Prompt text to show user (if action is prompt)
        quality_score: Query completeness score (0.0-1.0)
        dimensions: Current dimension states
        session_id: Session ID for continuation
        turn_count: Number of conversation turns
        feedback: Optional quality feedback for user
    """

    action: str = Field(..., description="Action: proceed/prompt/complete")
    enriched_query: Optional[str] = Field(default=None, description="Enriched query for search")
    prompt_text: Optional[str] = Field(default=None, description="Prompt text for user")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Query completeness score")
    dimensions: Dict[str, DimensionInfo] = Field(default_factory=dict, description="Current dimensions")
    session_id: str = Field(..., description="Session ID for continuation")
    turn_count: int = Field(default=0, description="Conversation turn count")
    feedback: Optional[str] = Field(default=None, description="Quality feedback")


class QueryQualityCapability(Capability[QueryQualityInput, QueryQualityCapabilityOutput]):
    """Capability for query quality enhancement through multi-turn conversation.

    This capability analyzes user queries for missing document dimensions and
    engages users in multi-turn dialogue to gather necessary information before
    executing searches.

    Example:
        capability = QueryQualityCapability()
        output = await capability.execute(QueryQualityInput(
            query="关于安全管理的通知",
            company_id="N000002",
            trace_id="abc123"
        ))
        # Output will have action="prompt" with prompt_text asking for year
    """

    def __init__(
        self,
        config: Optional[QueryQualityConfig] = None,
        session_store: Optional[SessionStoreService] = None,
        prompt_client: Optional[PromptClient] = None,
    ):
        """Initialize the QueryQuality capability.

        Args:
            config: Optional configuration (uses default if not provided)
            session_store: Optional session store (uses default if not provided)
            prompt_client: Optional prompt client (uses default if not provided)
        """
        super().__init__()
        settings = get_settings()
        self._config = config or settings.query_quality
        self._session_store = session_store or get_session_store()
        self._prompt_client = prompt_client or PromptClient()

        logger.info(
            "QueryQualityCapability initialized",
            extra={
                "session_timeout": self._config.session_timeout,
                "max_turns": self._config.max_turns,
                "enable_auto_enrich": self._config.enable_auto_enrich,
            },
        )

    def validate_input(self, input_data: QueryQualityInput) -> CapabilityValidationResult:
        """Validate input data for query quality enhancement.

        Args:
            input_data: Input data to validate

        Returns:
            Validation result with any errors or warnings
        """
        errors = []
        warnings = []

        # Validate query is not empty
        if not input_data.query or not input_data.query.strip():
            errors.append("Query cannot be empty")

        # Validate company_id
        if not input_data.company_id or not input_data.company_id.strip():
            errors.append("Company ID cannot be empty")

        # Warn if session is approaching turn limit
        if input_data.session_id:
            try:
                # Try to get session to check turn count
                # Note: This is async, so we'll check during execute
                warnings.append("Session turn limit will be checked during execution")
            except Exception:
                pass

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def execute(self, input_data: QueryQualityInput) -> QueryQualityCapabilityOutput:
        """Execute query quality enhancement.

        This is the main entry point for the capability. It:
        1. Gets or creates a session for the query
        2. Analyzes the query for missing dimensions
        3. Determines the appropriate action (proceed/prompt/complete)
        4. Returns the appropriate response

        Args:
            input_data: Input data with query and context

        Returns:
            Output with action, enriched query, or prompt text

        Raises:
            RAGServiceError: If execution fails
        """
        trace_id = input_data.trace_id or str(uuid.uuid4())

        try:
            # Step 1: Get or create session
            session = await self._get_or_create_session(input_data, trace_id)

            # Step 2: Analyze dimensions
            analysis = await self._analyze_dimensions(
                query=input_data.query,
                company_id=input_data.company_id,
                session=session,
                trace_id=trace_id,
            )

            # Step 3: Update session with new dimensions
            session = await self._update_session_dimensions(session, analysis, trace_id)

            # Step 4: Determine action
            action = await self._determine_action(session, analysis, input_data, trace_id)

            # Step 5: Generate response based on action
            if action == "proceed":
                return await self._generate_proceed_response(session, analysis, trace_id)
            elif action == "prompt":
                return await self._generate_prompt_response(session, analysis, trace_id)
            else:  # complete
                return await self._generate_complete_response(session, analysis, trace_id)

        except RAGServiceError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error in QueryQualityCapability",
                extra={"error": str(e), "trace_id": trace_id},
            )
            raise RAGServiceError(
                message=f"Query quality enhancement failed: {e}",
                trace_id=trace_id,
            ) from e

    def _calculate_quality_score(
        self,
        analysis: DimensionAnalysisResult,
        required_dimensions: Optional[List[DimensionType]] = None,
    ) -> float:
        """Calculate query quality score based on dimension completeness.

        Args:
            analysis: Dimension analysis result
            required_dimensions: List of required dimensions (uses all if None)

        Returns:
            Quality score between 0.0 and 1.0
        """
        if required_dimensions is None:
            required_dimensions = list(DimensionType)

        # Count present and inferred dimensions
        present_count = 0
        total_count = len(required_dimensions)

        for dim_type in required_dimensions:
            if dim_type in analysis.dimensions:
                dim_info = analysis.dimensions[dim_type]
                if dim_info.status in (DimensionStatus.PRESENT, DimensionStatus.INFERRED):
                    present_count += 1

        # Calculate base score
        quality_score = present_count / total_count if total_count > 0 else 0.0

        # Apply confidence weighting
        if analysis.dimensions:
            avg_confidence = sum(
                d.confidence for d in analysis.dimensions.values()
            ) / len(analysis.dimensions)
            quality_score = quality_score * (0.5 + 0.5 * avg_confidence)

        return round(quality_score, 2)

    async def _get_or_create_session(
        self,
        input_data: QueryQualityInput,
        trace_id: str,
    ) -> SessionState:
        """Get existing session or create new one.

        Args:
            input_data: Input data with optional session_id
            trace_id: Trace ID for correlation

        Returns:
            Session state
        """
        if input_data.session_id:
            session = await self._session_store.get_session(input_data.session_id, trace_id)
            if session:
                logger.info(
                    "Retrieved existing session",
                    extra={"session_id": input_data.session_id, "trace_id": trace_id},
                )
                return session

        # Create new session
        session = await self._session_store.create_session(
            company_id=input_data.company_id,
            original_query=input_data.query,
            trace_id=trace_id,
        )
        return session

    async def _analyze_dimensions(
        self,
        query: str,
        company_id: str,
        session: SessionState,
        trace_id: str,
    ) -> DimensionAnalysisResult:
        """Analyze query for required dimensions using LLM.

        Args:
            query: User's query text
            company_id: Company identifier
            session: Current session state
            trace_id: Trace ID for correlation

        Returns:
            Dimension analysis result
        """
        try:
            # Call LLM via Prompt Service for dimension analysis
            prompt_template = self._config.dimension_analysis_template

            # Prepare variables for prompt
            current_year = str(datetime.now().year)
            conversation_history = session.query_history[-3:] if session.query_history else []

            # Build prompt variables
            prompt_variables = {
                "user_query": query,
                "company_id": company_id,
                "current_year": current_year,
                "conversation_history": conversation_history,
            }

            # Call Prompt Service (async)
            llm_response = await self._prompt_client.get_prompt(
                template_id=prompt_template,
                variables=prompt_variables,
                trace_id=trace_id,
            )

            # Parse LLM response
            analysis = self._parse_dimension_response(llm_response, trace_id)

            # Calculate quality score using the dedicated method
            analysis.quality_score = self._calculate_quality_score(analysis)

            # Calculate action based on analysis
            if not analysis.action or analysis.action == "prompt":
                # Check if auto-enrich can help
                if self._config.enable_auto_enrich and self._can_auto_enrich(analysis):
                    analysis = self._apply_auto_enrichment(analysis, current_year, trace_id)
                    # Recalculate quality score after enrichment
                    analysis.quality_score = self._calculate_quality_score(analysis)
                    if analysis.quality_score >= 0.7:
                        analysis.action = "proceed"

            # Log analysis results
            self._log_dimension_analysis(query, analysis, trace_id)

            return analysis

        except Exception as e:
            logger.error(
                "Dimension analysis failed, using fallback",
                extra={"error": str(e), "trace_id": trace_id},
            )
            # Return basic analysis on failure
            return self._create_fallback_analysis(query, company_id, trace_id)

    def _parse_dimension_response(
        self,
        llm_response: str,
        trace_id: str,
    ) -> DimensionAnalysisResult:
        """Parse LLM response into dimension analysis result.

        Args:
            llm_response: Raw LLM response text
            trace_id: Trace ID for correlation

        Returns:
            Parsed analysis result
        """
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'```json\s*({.*?})\s*```', llm_response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'({.*?})', llm_response, re.DOTALL)

            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # Parse plain text response
                data = self._parse_text_dimension_response(llm_response, trace_id)

            # Build DimensionAnalysisResult from parsed data
            dimensions = {}
            for dim_name, dim_data in data.get("dimensions", {}).items():
                try:
                    dim_type = DimensionType(dim_name)
                    dimensions[dim_type] = DimensionInfo(
                        dimension_type=dim_type,
                        status=DimensionStatus(dim_data.get("status", "absent")),
                        value=dim_data.get("value"),
                        confidence=dim_data.get("confidence", 0.5),
                    )
                except ValueError:
                    pass  # Skip unknown dimension types

            # Get missing dimensions
            missing_dims_str = data.get("missing_dimensions", [])
            missing_dimensions = []
            for dim_str in missing_dims_str:
                try:
                    missing_dimensions.append(DimensionType(dim_str))
                except ValueError:
                    pass

            return DimensionAnalysisResult(
                dimensions=dimensions,
                quality_score=data.get("quality_score", 0.5),
                action=data.get("action", "prompt"),
                missing_dimensions=missing_dimensions,
                suggested_prompts=data.get("suggested_prompts", []),
                trace_id=trace_id,
            )

        except Exception as e:
            logger.warning(
                "Failed to parse dimension response, using fallback",
                extra={"error": str(e), "trace_id": trace_id},
            )
            raise

    def _parse_text_dimension_response(
        self,
        response: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Parse plain text dimension response.

        Args:
            response: Plain text response
            trace_id: Trace ID for correlation

        Returns:
            Structured data dictionary
        """
        # Simple pattern-based extraction for text response
        quality_score = 0.3
        missing_dimensions = []

        # Check for year
        import re
        year_match = re.search(r'(20\d{2})', response)
        if not year_match:
            missing_dimensions.append(DimensionType.YEAR_NUMBER)

        # Check for document type keywords
        doc_types = ["通知", "通报", "报告", "请示", "纪要", "公示", "方案", "办法", "细则", "规则", "规划", "要点", "会议纪要"]
        has_doc_type = any(dt in response for dt in doc_types)
        if not has_doc_type:
            missing_dimensions.append(DimensionType.DOCUMENT_TYPE)

        return {
            "dimensions": {},
            "quality_score": quality_score,
            "action": "prompt" if missing_dimensions else "proceed",
            "missing_dimensions": [d.value for d in missing_dimensions],
            "suggested_prompts": [],
        }

    def _can_auto_enrich(
        self,
        analysis: DimensionAnalysisResult,
    ) -> bool:
        """Check if query can be auto-enriched.

        Args:
            analysis: Dimension analysis result

        Returns:
            True if auto-enrichment is possible
        """
        # Can auto-enrich if only missing year and current year is reasonable default
        missing = set(analysis.missing_dimensions)
        return missing == {DimensionType.YEAR_NUMBER} or (
            missing == {DimensionType.YEAR_NUMBER, DimensionType.FILE_CATEGORY}
        )

    def _apply_auto_enrichment(
        self,
        analysis: DimensionAnalysisResult,
        current_year: str,
        trace_id: str,
    ) -> DimensionAnalysisResult:
        """Apply auto-enrichment to analysis result.

        Args:
            analysis: Dimension analysis result
            current_year: Current year
            trace_id: Trace ID for correlation

        Returns:
            Enriched analysis result
        """
        # Add year dimension if missing
        if DimensionType.YEAR_NUMBER in analysis.missing_dimensions:
            analysis.dimensions[DimensionType.YEAR_NUMBER] = DimensionInfo(
                dimension_type=DimensionType.YEAR_NUMBER,
                status=DimensionStatus.INFERRED,
                value=current_year,
                confidence=0.7,
                source="auto_enriched",
            )
            analysis.missing_dimensions.remove(DimensionType.YEAR_NUMBER)
            analysis.quality_score += 0.2

        logger.info(
            "Auto-enrichment applied",
            extra={
                "added_dimensions": ["YEAR_NUMBER"],
                "enriched_year": current_year,
                "new_quality_score": analysis.quality_score,
                "trace_id": trace_id,
            },
        )

        return analysis

    def _create_fallback_analysis(
        self,
        query: str,
        company_id: str,
        trace_id: str,
    ) -> DimensionAnalysisResult:
        """Create fallback dimension analysis when LLM fails.

        Args:
            query: User query
            company_id: Company identifier
            trace_id: Trace ID for correlation

        Returns:
            Basic dimension analysis result
        """
        # Pattern-based dimension detection
        missing_dimensions = []
        dimensions = {}

        # Company ID is always provided
        dimensions[DimensionType.COMPANY_ID] = DimensionInfo(
            dimension_type=DimensionType.COMPANY_ID,
            status=DimensionStatus.PRESENT,
            value=company_id,
            confidence=1.0,
        )

        # Check for year
        import re
        year_match = re.search(r'(20\d{2})', query)
        if year_match:
            dimensions[DimensionType.YEAR_NUMBER] = DimensionInfo(
                dimension_type=DimensionType.YEAR_NUMBER,
                status=DimensionStatus.PRESENT,
                value=year_match.group(1),
                confidence=0.9,
            )
        else:
            missing_dimensions.append(DimensionType.YEAR_NUMBER)

        # Check for document type
        doc_types = {
            "通知": DimensionType.DOCUMENT_TYPE,
            "通报": DimensionType.DOCUMENT_TYPE,
            "报告": DimensionType.DOCUMENT_TYPE,
            "请示": DimensionType.DOCUMENT_TYPE,
            "纪要": DimensionType.DOCUMENT_TYPE,
            "会议纪要": DimensionType.DOCUMENT_TYPE,
            "公示": DimensionType.DOCUMENT_TYPE,
            "方案": DimensionType.DOCUMENT_TYPE,
            "办法": DimensionType.DOCUMENT_TYPE,
            "细则": DimensionType.DOCUMENT_TYPE,
            "规则": DimensionType.DOCUMENT_TYPE,
            "规划": DimensionType.DOCUMENT_TYPE,
            "要点": DimensionType.DOCUMENT_TYPE,
        }
        for doc_name, dim_type in doc_types.items():
            if doc_name in query:
                dimensions[dim_type] = DimensionInfo(
                    dimension_type=dim_type,
                    status=DimensionStatus.PRESENT,
                    value=query[:20],  # First 20 chars as value
                    confidence=0.8,
                )
                break

        # Calculate quality score using the dedicated method
        temp_analysis = DimensionAnalysisResult(
            dimensions=dimensions,
            quality_score=0.0,  # Will be calculated
            action="",
            missing_dimensions=missing_dimensions,
            suggested_prompts=[],
            trace_id=trace_id,
        )
        quality_score = self._calculate_quality_score(temp_analysis)

        # Determine action
        action = "proceed" if quality_score >= 0.5 else "prompt"

        # Generate suggested prompts for missing dimensions
        suggested_prompts = []
        if DimensionType.YEAR_NUMBER in missing_dimensions:
            suggested_prompts.append("请问您需要查找哪一年的文档？")
        if action == "prompt" and quality_score < 0.3:
            suggested_prompts.append("请提供更多信息以便更准确地查找文档。")

        return DimensionAnalysisResult(
            dimensions=dimensions,
            quality_score=quality_score,
            action=action,
            missing_dimensions=missing_dimensions,
            suggested_prompts=suggested_prompts,
            trace_id=trace_id,
        )

    def _log_dimension_analysis(
        self,
        query: str,
        analysis: DimensionAnalysisResult,
        trace_id: str,
    ) -> None:
        """Log dimension analysis results for observability.

        Args:
            query: User query
            analysis: Analysis result
            trace_id: Trace ID for correlation
        """
        logger.info(
            "Dimension analysis completed",
            extra={
                "query": query[:50],  # Truncate for logging
                "action": analysis.action,
                "quality_score": analysis.quality_score,
                "missing_dimensions": [d.value for d in analysis.missing_dimensions],
                "suggested_prompts": analysis.suggested_prompts,
                "dimension_count": len(analysis.dimensions),
                "trace_id": trace_id,
            },
        )

    async def _update_session_dimensions(
        self,
        session: SessionState,
        analysis: DimensionAnalysisResult,
        trace_id: str,
    ) -> SessionState:
        """Update session with new dimension analysis.

        Args:
            session: Current session state
            analysis: Dimension analysis result
            trace_id: Trace ID for correlation

        Returns:
            Updated session state
        """
        # Add new dimensions to session
        for dim_type, dim_info in analysis.dimensions.items():
            session.add_dimension(dim_info)

        # Update in Redis
        await self._session_store.update_session(session, trace_id=trace_id)

        return session

    async def _determine_action(
        self,
        session: SessionState,
        analysis: DimensionAnalysisResult,
        input_data: QueryQualityInput,
        trace_id: str,
    ) -> str:
        """Determine what action to take based on analysis.

        Args:
            session: Current session state
            analysis: Dimension analysis result
            input_data: Original input data
            trace_id: Trace ID for correlation

        Returns:
            Action: "proceed", "prompt", or "complete"
        """
        # Check turn limit
        if session.turn_count >= self._config.max_turns:
            logger.info(
                "Turn limit reached, forcing proceed",
                extra={
                    "turn_count": session.turn_count,
                    "max_turns": self._config.max_turns,
                    "trace_id": trace_id,
                },
            )
            return "proceed"

        # If requiring all dimensions, check if complete
        if input_data.require_all_dimensions:
            required_dims = list(DimensionType)
            missing = session.get_missing_dimensions(required_dims)
            if missing:
                return "prompt"

        # Check if we have enough to proceed
        if session.can_proceed():
            return "proceed"

        # Otherwise, prompt for more info
        return "prompt"

    async def _generate_proceed_response(
        self,
        session: SessionState,
        analysis: DimensionAnalysisResult,
        trace_id: str,
    ) -> QueryQualityCapabilityOutput:
        """Generate response for proceeding with search.

        Args:
            session: Current session state
            analysis: Dimension analysis result
            trace_id: Trace ID for correlation

        Returns:
            Output with enriched query for search
        """
        enriched_query = self._build_enriched_query(session, analysis)

        await self._session_store.complete_session(
            session,
            enriched_query,
            trace_id=trace_id,
        )

        feedback = self._generate_quality_feedback(analysis)

        return QueryQualityCapabilityOutput(
            action="proceed",
            enriched_query=enriched_query,
            quality_score=analysis.quality_score,
            dimensions={k.value: v for k, v in analysis.dimensions.items()},
            session_id=session.session_id,
            turn_count=session.turn_count,
            feedback=feedback,
            trace_id=trace_id,
        )

    async def _generate_prompt_response(
        self,
        session: SessionState,
        analysis: DimensionAnalysisResult,
        trace_id: str,
    ) -> QueryQualityCapabilityOutput:
        """Generate response with prompt for missing dimensions.

        Args:
            session: Current session state
            analysis: Dimension analysis result
            trace_id: Trace ID for correlation

        Returns:
            Output with prompt text for user
        """
        await self._session_store.increment_turn_count(session, trace_id=trace_id)

        # Generate prompt text
        prompt_text = self._generate_prompt_text(analysis)

        return QueryQualityCapabilityOutput(
            action="prompt",
            prompt_text=prompt_text,
            quality_score=analysis.quality_score,
            dimensions={k.value: v for k, v in analysis.dimensions.items()},
            session_id=session.session_id,
            turn_count=session.turn_count + 1,
            trace_id=trace_id,
        )

    async def _generate_complete_response(
        self,
        session: SessionState,
        analysis: DimensionAnalysisResult,
        trace_id: str,
    ) -> QueryQualityCapabilityOutput:
        """Generate response when session is complete.

        Args:
            session: Current session state
            analysis: Dimension analysis result
            trace_id: Trace ID for correlation

        Returns:
            Output with complete status
        """
        return QueryQualityCapabilityOutput(
            action="complete",
            quality_score=analysis.quality_score,
            dimensions={k.value: v for k, v in analysis.dimensions.items()},
            session_id=session.session_id,
            turn_count=session.turn_count,
            feedback="查询信息已完整，可以开始搜索。",
            trace_id=trace_id,
        )

    def _build_enriched_query(
        self,
        session: SessionState,
        analysis: DimensionAnalysisResult,
    ) -> str:
        """Build enriched query from session and analysis.

        Args:
            session: Current session state
            analysis: Dimension analysis result

        Returns:
            Enriched query string
        """
        parts = [session.original_query]

        # Add dimension context
        for dim_type, dim_info in analysis.dimensions.items():
            if dim_info.status == DimensionStatus.INFERRED and dim_info.value:
                parts.append(f"{dim_type.value}: {dim_info.value}")

        return " | ".join(parts)

    def _generate_prompt_text(self, analysis: DimensionAnalysisResult) -> str:
        """Generate natural language prompt for missing dimensions.

        Args:
            analysis: Dimension analysis result

        Returns:
            Prompt text for user
        """
        if analysis.suggested_prompts:
            return analysis.suggested_prompts[0]

        # Generate default prompt
        missing = [d.value for d in analysis.missing_dimensions]
        return f"请提供以下信息以优化搜索: {', '.join(missing)}"

    def _generate_quality_feedback(self, analysis: DimensionAnalysisResult) -> str:
        """Generate quality feedback for user.

        Args:
            analysis: Dimension analysis result

        Returns:
            Quality feedback message
        """
        if analysis.quality_score >= 0.8:
            return "您的查询非常完整，包含了所有关键维度。"
        elif analysis.quality_score >= 0.5:
            return "您的查询比较完整，可以开始搜索。"
        else:
            missing = [d.value for d in analysis.missing_dimensions]
            return f"您的查询缺少以下维度: {', '.join(missing)}。"

    def get_health(self) -> Dict[str, Any]:
        """Get health status of the capability.

        Returns:
            Health status information
        """
        return {
            "capability": self._name,
            "status": "healthy",
            "config": {
                "session_timeout": self._config.session_timeout,
                "max_turns": self._config.max_turns,
                "enable_auto_enrich": self._config.enable_auto_enrich,
                "require_all_dimensions": self._config.require_all_dimensions,
            },
        }
