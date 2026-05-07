"""
Conversational Query Enhancement Capability.

This capability implements multi-turn conversation with structured query
extraction, business domain classification, and colloquial term mapping.

Key features:
- Structured slot extraction from user queries
- Query type classification (meta_info, business_query, unknown)
- Business domain classification (10 domains with keyword-based routing)
- Follow-up detection with context inheritance
- Colloquial term normalization
- Structured query generation with slot filling and keyword expansion
"""

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.config import ConversationalQueryConfig, get_settings
from rag_service.core.exceptions import RAGServiceError
from rag_service.core.logger import get_logger
from rag_service.models.conversational_query import (
    BeliefState,
    BusinessDomain,
    ColloquialTermMapping,
    ContentElements,
    ContentElements,
    DocumentElements,
    ExtractedQueryElements,
    QueryGenerationResult,
    QueryType,
    SpatialElements,
    TemporalElements,
    QuantityElements,
)
from rag_service.services.belief_state_store import BeliefStateStoreService, get_belief_state_store
from rag_service.services.colloquial_mapper import ColloquialMapperService, get_colloquial_mapper
from rag_service.services.prompt_client import PromptClient

logger = get_logger(__name__)


class ConversationalQueryInput(CapabilityInput):
    """Input for ConversationalQueryCapability.

    Attributes:
        query: User's query text
        session_id: Optional session ID for multi-turn conversations
        enable_colloquial_mapping: Enable colloquial term mapping
        enable_domain_routing: Enable business domain routing
        enable_followup_detection: Enable follow-up detection
    """

    query: str = Field(..., min_length=1, description="User's query text")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn")
    enable_colloquial_mapping: bool = Field(default=True, description="Enable colloquial mapping")
    enable_domain_routing: bool = Field(default=True, description="Enable domain routing")
    enable_followup_detection: bool = Field(default=True, description="Enable follow-up detection")


class ConversationalQueryCapabilityOutput(CapabilityOutput):
    """Output from ConversationalQueryCapability.

    Attributes:
        query_type: Classified query type
        generated_queries: Generated query variations
        extracted_elements: Structured extraction result
        belief_state: Current belief state
        is_followup: Whether this was a follow-up
        confidence: Confidence score
        clarification_needed: Whether clarification is needed
        clarification_prompt: Optional prompt for user
        session_id: Session ID for continuation
        turn_count: Current turn count
    """

    query_type: QueryType = Field(..., description="Classified query type")
    generated_queries: QueryGenerationResult = Field(..., description="Generated queries")
    extracted_elements: ExtractedQueryElements = Field(..., description="Extracted elements")
    belief_state: Dict[str, Any] = Field(default_factory=dict, description="Belief state")
    is_followup: bool = Field(default=False, description="Is follow-up query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    clarification_needed: bool = Field(default=False, description="Needs clarification")
    clarification_prompt: Optional[str] = Field(default=None, description="Clarification prompt")
    session_id: str = Field(..., description="Session ID")
    turn_count: int = Field(default=0, description="Turn count")


class ConversationalQueryCapability(Capability[ConversationalQueryInput, ConversationalQueryCapabilityOutput]):
    """Capability for conversational query enhancement through multi-turn dialogue.

    This capability analyzes user queries, extracts structured elements, classifies
    query type and business domain, and generates optimized search queries.

    Example:
        capability = ConversationalQueryCapability()
        output = await capability.execute(ConversationalQueryInput(
            query="差旅费报销标准是什么",
            trace_id="abc123"
        ))
        # Output will have query_type=business_query, generated queries, etc.
    """

    def __init__(
        self,
        config: Optional[ConversationalQueryConfig] = None,
        belief_state_store: Optional[BeliefStateStoreService] = None,
        colloquial_mapper: Optional[ColloquialMapperService] = None,
        prompt_client: Optional[PromptClient] = None,
    ):
        """Initialize the Conversational Query capability.

        Args:
            config: Optional configuration (uses default if not provided)
            belief_state_store: Optional belief state store (uses default if not provided)
            colloquial_mapper: Optional colloquial mapper (uses default if not provided)
            prompt_client: Optional prompt client (uses default if not provided)
        """
        super().__init__()
        settings = get_settings()
        self._config = config or settings.conversational_query
        self._belief_state_store = belief_state_store or get_belief_state_store()
        self._colloquial_mapper = colloquial_mapper or get_colloquial_mapper()
        self._prompt_client = prompt_client or PromptClient()

        logger.info(
            "ConversationalQueryCapability initialized",
            extra={
                "session_timeout": self._config.session_timeout,
                "max_turns": self._config.max_turns,
                "enable_colloquial_mapping": self._config.enable_colloquial_mapping,
                "enable_domain_routing": self._config.enable_domain_routing,
            },
        )

    def validate_input(self, input_data: ConversationalQueryInput) -> CapabilityValidationResult:
        """Validate input data for conversational query enhancement.

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

        # Warn if session is approaching turn limit
        if input_data.session_id:
            warnings.append("Session turn limit will be checked during execution")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def execute(self, input_data: ConversationalQueryInput) -> ConversationalQueryCapabilityOutput:
        """Execute conversational query enhancement.

        This is the main entry point for the capability. It:
        1. Gets or creates a belief state for the session
        2. Extracts structured elements from the query
        3. Classifies query type and business domain
        4. Applies colloquial term mapping if enabled
        5. Generates optimized search queries
        6. Returns the appropriate response

        Args:
            input_data: Input data with query and context

        Returns:
            Output with query type, generated queries, and extracted elements

        Raises:
            RAGServiceError: If execution fails
        """
        trace_id = input_data.trace_id or str(uuid.uuid4())

        try:
            # Step 1: Get or create belief state
            belief_state = await self._get_or_create_belief_state(input_data, trace_id)

            # Step 2: Apply colloquial mapping if enabled
            mapped_query = input_data.query
            if input_data.enable_colloquial_mapping:
                domain = self._classify_domain_from_history(belief_state, trace_id)
                mapped_query = self._colloquial_mapper.map_query(
                    input_data.query,
                    domain=domain,
                    trace_id=trace_id,
                )

            # Step 3: Extract structured elements
            extracted_elements = await self._extract_elements(
                query=mapped_query,
                original_query=input_data.query,
                belief_state=belief_state,
                trace_id=trace_id,
            )

            # Step 4: Detect follow-up if enabled
            if input_data.enable_followup_detection:
                is_followup = self._detect_followup(
                    input_data.query,
                    belief_state,
                    trace_id,
                )
                extracted_elements.is_followup = is_followup

            # Step 5: Classify domain if enabled
            domain = None
            if input_data.enable_domain_routing:
                domain = self._colloquial_mapper.classify_domain(
                    mapped_query,
                    trace_id=trace_id,
                )
                extracted_elements.detected_domain = domain

            # Step 6: Generate queries
            generated_queries = await self._generate_queries(
                query=mapped_query,
                extracted_elements=extracted_elements,
                belief_state=belief_state,
                domain=domain,
                trace_id=trace_id,
            )

            # Step 7: Update belief state
            await self._update_belief_state(
                belief_state,
                input_data.query,
                extracted_elements,
                trace_id,
            )

            # Step 8: Build response
            return self._build_response(
                query_type=extracted_elements.query_type,
                generated_queries=generated_queries,
                extracted_elements=extracted_elements,
                belief_state=belief_state,
                trace_id=trace_id,
            )

        except RAGServiceError:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error in ConversationalQueryCapability",
                extra={"error": str(e), "trace_id": trace_id},
            )
            raise RAGServiceError(
                message=f"Conversational query enhancement failed: {e}",
                trace_id=trace_id,
            ) from e

    async def _get_or_create_belief_state(
        self,
        input_data: ConversationalQueryInput,
        trace_id: str,
    ) -> BeliefState:
        """Get existing belief state or create new one.

        Args:
            input_data: Input data with optional session_id
            trace_id: Trace ID for correlation

        Returns:
            Belief state
        """
        if input_data.session_id:
            state = await self._belief_state_store.get_state(input_data.session_id, trace_id)
            if state:
                logger.info(
                    "Retrieved existing belief state",
                    extra={"session_id": input_data.session_id, "trace_id": trace_id},
                )
                return state

        # Create new belief state
        session_id = input_data.session_id or str(uuid.uuid4())
        state = await self._belief_state_store.create_state(
            session_id=session_id,
            trace_id=trace_id,
        )
        return state

    def _classify_domain_from_history(
        self,
        belief_state: BeliefState,
        trace_id: str,
    ) -> Optional[BusinessDomain]:
        """Classify domain from conversation history.

        Args:
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            Classified business domain or None
        """
        # Check if domain is in belief state slots
        domain_slot = belief_state.get_slot("domain")
        if domain_slot:
            try:
                return BusinessDomain(domain_slot)
            except ValueError:
                pass
        return None

    async def _extract_elements(
        self,
        query: str,
        original_query: str,
        belief_state: BeliefState,
        trace_id: str,
    ) -> ExtractedQueryElements:
        """Extract structured elements from query using LLM.

        Args:
            query: Mapped query (after colloquial mapping)
            original_query: Original user query
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            Extracted query elements
        """
        try:
            # Call LLM via Prompt Service for slot extraction
            prompt_template = self._config.slot_extraction_template

            # Prepare variables for prompt
            current_date = datetime.now().strftime("%Y-%m-%d")
            conversation_history = belief_state.query_history[-3:] if belief_state.query_history else []

            # Build prompt variables
            prompt_variables = {
                "user_query": original_query,
                "current_date": current_date,
                "conversation_history": conversation_history,
            }

            # Call Prompt Service (async)
            llm_response = await self._prompt_client.get_prompt(
                template_id=prompt_template,
                variables=prompt_variables,
                trace_id=trace_id,
            )

            # Parse LLM response
            extracted = self._parse_slot_response(llm_response, trace_id)

            # Calculate confidence
            confidence = self._calculate_confidence(extracted, belief_state, trace_id)
            extracted.confidence = confidence

            # Determine if clarification is needed
            extracted.clarification_needed = (
                confidence < self._config.min_confidence_threshold
                and not extracted.is_followup
            )

            # Log extraction results
            self._log_extraction_results(original_query, extracted, trace_id)

            return extracted

        except Exception as e:
            logger.error(
                "Slot extraction failed, using fallback",
                extra={"error": str(e), "trace_id": trace_id},
            )
            # Return basic extraction on failure
            return self._create_fallback_extraction(query, trace_id)

    def _parse_slot_response(
        self,
        llm_response: str,
        trace_id: str,
    ) -> ExtractedQueryElements:
        """Parse LLM response into structured extraction result.

        Args:
            llm_response: Raw LLM response text
            trace_id: Trace ID for correlation

        Returns:
            Parsed extraction result
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
                data = self._parse_text_response(llm_response, trace_id)

            # Build ExtractedQueryElements from parsed data
            return ExtractedQueryElements(
                query_type=QueryType(data.get("query_type", "unknown")),
                is_followup=data.get("is_followup", False),
                temporal=TemporalElements(**data.get("extracted_elements", {}).get("temporal", {})),
                spatial=SpatialElements(**data.get("extracted_elements", {}).get("spatial", {})),
                document=DocumentElements(**data.get("extracted_elements", {}).get("document", {})),
                content=ContentElements(
                    **data.get("extracted_elements", {}).get("content", {}),
                    business_domain=self._parse_domain(data.get("detected_domain")),
                ),
                quantity=QuantityElements(**data.get("extracted_elements", {}).get("quantity", {})),
                confidence=data.get("confidence", 0.5),
                missing_slots=data.get("missing_slots", []),
                clarification_needed=data.get("clarification_needed", False),
                detected_domain=self._parse_domain(data.get("detected_domain")),
                trace_id=trace_id,
            )

        except Exception as e:
            logger.warning(
                "Failed to parse LLM response, using fallback",
                extra={"error": str(e), "trace_id": trace_id},
            )
            raise

    def _parse_text_response(
        self,
        response: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Parse plain text response into structured data.

        Args:
            response: Plain text response
            trace_id: Trace ID for correlation

        Returns:
            Structured data dictionary
        """
        # Simple keyword-based extraction for text response
        query_type = QueryType.UNKNOWN
        if any(word in response for word in ["有哪些", "什么是", "文档", "文件"]):
            query_type = QueryType.META_INFO
        elif any(word in response for word in ["怎么", "如何", "是什么", "标准"]):
            query_type = QueryType.BUSINESS_QUERY

        return {
            "query_type": query_type.value,
            "is_followup": False,
            "confidence": 0.3,
            "clarification_needed": True,
            "missing_slots": ["query_type_uncertain"],
            "extracted_elements": {},
        }

    def _parse_domain(self, domain_str: Any) -> Optional[BusinessDomain]:
        """Parse domain string into BusinessDomain enum.

        Args:
            domain_str: Domain string or None

        Returns:
            BusinessDomain or None
        """
        if domain_str is None:
            return None
        try:
            if isinstance(domain_str, str):
                return BusinessDomain(domain_str.lower())
            return BusinessDomain(domain_str)
        except (ValueError, AttributeError):
            return None

    def _classify_query_type(
        self,
        query: str,
        extracted_elements: Dict[str, Any],
        belief_state: BeliefState,
        trace_id: str,
    ) -> QueryType:
        """Classify query type (meta_info vs business_query).

        Args:
            query: User query text
            extracted_elements: Extracted elements from LLM
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            Classified query type
        """
        # Priority pattern matching for meta_info queries
        meta_info_patterns = [
            r"有哪些",  # what are there
            r"什么是",  # what is
            r".*文档",  # documents
            r".*文件",  # files
            r"多少.*?(文件|文档|个)",  # how many documents
            r"列出",   # list
            r"显示",   # show
        ]

        import re
        for pattern in meta_info_patterns:
            if re.search(pattern, query):
                logger.info(
                    "Query classified as meta_info",
                    extra={"query": query, "pattern": pattern, "trace_id": trace_id},
                )
                return QueryType.META_INFO

        # Business query patterns
        business_query_patterns = [
            r"怎么.*?(办|做|申请)",  # how to do/apply
            r"如何.*?(办|做|申请)",  # how to do/apply
            r".*?标准",  # standards
            r".*?流程",  # process
            r".*?规定",  # regulations
            r"可以.*?吗",  # can I/can we
            r"需要.*?吗",  # do I need
        ]

        for pattern in business_query_patterns:
            if re.search(pattern, query):
                logger.info(
                    "Query classified as business_query",
                    extra={"query": query, "pattern": pattern, "trace_id": trace_id},
                )
                return QueryType.BUSINESS_QUERY

        # Default classification based on context
        if belief_state.conversation_turn > 1:
            # Follow-up queries are often business queries
            return QueryType.BUSINESS_QUERY

        logger.info(
            "Query classified as unknown",
            extra={"query": query, "trace_id": trace_id},
        )
        return QueryType.UNKNOWN

    def _detect_followup(
        self,
        query: str,
        belief_state: BeliefState,
        trace_id: str,
    ) -> bool:
        """Detect if query is a follow-up with enhanced detection.

        Args:
            query: User query
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            True if this is a follow-up query
        """
        # Check conversation history
        if belief_state.conversation_turn == 0:
            return False

        # Check for pronouns that indicate follow-up
        followup_indicators = {
            "它", "这个", "那个", "这些", "那些", "他", "她",  # pronouns
            "那", "咋",  # colloquial follow-up
        }

        query_lower = query.lower()
        has_pronoun = any(indicator in query for indicator in followup_indicators)

        # Check for very short queries (likely follow-ups)
        is_short_query = len(query.strip()) <= 10

        # Check for continuation patterns
        continuation_patterns = ["还有", "别的", "其他的", "以及"]
        has_continuation = any(pattern in query for pattern in continuation_patterns)

        result = has_pronoun or (is_short_query and belief_state.conversation_turn > 0) or has_continuation

        if result:
            logger.info(
                "Follow-up query detected",
                extra={
                    "query": query,
                    "has_pronoun": has_pronoun,
                    "is_short": is_short_query,
                    "has_continuation": has_continuation,
                    "turn": belief_state.conversation_turn,
                    "trace_id": trace_id,
                },
            )

        return result

    def _calculate_confidence(
        self,
        extracted: ExtractedQueryElements,
        belief_state: BeliefState,
        trace_id: str,
    ) -> float:
        """Calculate confidence score for extraction quality.

        Args:
            extracted: Extracted query elements
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 0.0

        # Base confidence from query type
        if extracted.query_type != QueryType.UNKNOWN:
            confidence += 0.3

        # Content elements (most important)
        if extracted.content.topic:
            confidence += 0.2
        if extracted.content.keywords:
            confidence += min(0.1 * len(extracted.content.keywords), 0.2)

        # Temporal elements
        if extracted.temporal.year or extracted.temporal.time_range:
            confidence += 0.1

        # Spatial elements
        if extracted.spatial.city or extracted.spatial.province:
            confidence += 0.1

        # Document elements
        if extracted.document.doc_type:
            confidence += 0.1

        # Penalty for missing critical info
        if extracted.missing_slots:
            confidence -= min(0.1 * len(extracted.missing_slots), 0.3)

        # Follow-up queries have lower base confidence (more context needed)
        if extracted.is_followup:
            confidence = max(confidence - 0.1, 0.0)

        # Boost if we have belief state context
        if belief_state.conversation_turn > 0:
            confidence += 0.1

        # Clamp to valid range
        confidence = max(0.0, min(confidence, 1.0))

        logger.info(
            "Confidence calculated",
            extra={"confidence": confidence, "trace_id": trace_id},
        )

        return confidence

    def _create_fallback_extraction(
        self,
        query: str,
        trace_id: str,
    ) -> ExtractedQueryElements:
        """Create fallback extraction when LLM fails.

        Args:
            query: User query
            trace_id: Trace ID for correlation

        Returns:
            Basic extraction result
        """
        # Use colloquial mapper for basic domain classification
        domain = self._colloquial_mapper.classify_domain(query, trace_id)

        # Extract basic keywords
        keywords = []
        if domain:
            domain_keywords = self._colloquial_mapper._domain_keywords.get(domain.value, [])
            keywords = [kw for kw in domain_keywords if kw in query]

        return ExtractedQueryElements(
            query_type=QueryType.UNKNOWN,
            is_followup=False,
            temporal=TemporalElements(),
            spatial=SpatialElements(),
            document=DocumentElements(),
            content=ContentElements(
                topic=query[:20],  # Use first 20 chars as topic
                keywords=keywords,
                business_domain=domain,
            ),
            quantity=QuantityElements(),
            confidence=0.3,  # Lower confidence for fallback
            missing_slots=["query_type", "structured_extraction_failed"],
            clarification_needed=True,
            detected_domain=domain,
            trace_id=trace_id,
        )

    def _log_extraction_results(
        self,
        query: str,
        extracted: ExtractedQueryElements,
        trace_id: str,
    ) -> None:
        """Log structured extraction results for observability.

        Args:
            query: User query
            extracted: Extracted elements
            trace_id: Trace ID for correlation
        """
        logger.info(
            "Slot extraction completed",
            extra={
                "query": query[:50],  # Truncate for logging
                "query_type": extracted.query_type.value,
                "is_followup": extracted.is_followup,
                "confidence": extracted.confidence,
                "detected_domain": extracted.detected_domain.value if extracted.detected_domain else None,
                "missing_slots": extracted.missing_slots,
                "clarification_needed": extracted.clarification_needed,
                "temporal": {
                    "year": extracted.temporal.year,
                    "time_range": extracted.temporal.time_range,
                },
                "spatial": {
                    "city": extracted.spatial.city,
                    "province": extracted.spatial.province,
                },
                "document": {
                    "doc_type": extracted.document.doc_type,
                },
                "content": {
                    "topic": extracted.content.topic,
                    "keyword_count": len(extracted.content.keywords),
                },
                "trace_id": trace_id,
            },
        )

    async def _generate_queries(
        self,
        query: str,
        extracted_elements: ExtractedQueryElements,
        belief_state: BeliefState,
        domain: Optional[BusinessDomain],
        trace_id: str,
    ) -> QueryGenerationResult:
        """Generate optimized search queries using LLM.

        Args:
            query: Mapped query
            extracted_elements: Extracted elements
            belief_state: Current belief state
            domain: Business domain
            trace_id: Trace ID for correlation

        Returns:
            Generated query result
        """
        try:
            # Call LLM via Prompt Service for query generation
            prompt_template = self._config.query_generation_template

            # Prepare variables for prompt
            query_type = extracted_elements.query_type.value
            extracted_slots = {
                "temporal": extracted_elements.temporal.model_dump(),
                "spatial": extracted_elements.spatial.model_dump(),
                "document": extracted_elements.document.model_dump(),
                "content": extracted_elements.content.model_dump(),
                "quantity": extracted_elements.quantity.model_dump(),
            }
            belief_slots = belief_state.slots.copy()
            business_domain = domain.value if domain else None
            conversation_history = belief_state.query_history[-3:] if belief_state.query_history else []

            # Build prompt variables
            prompt_variables = {
                "user_query": query,
                "query_type": query_type,
                "extracted_slots": extracted_slots,
                "belief_state": belief_slots,
                "business_domain": business_domain,
                "conversation_history": conversation_history,
            }

            # Call Prompt Service (async)
            llm_response = await self._prompt_client.get_prompt(
                template_id=prompt_template,
                variables=prompt_variables,
                trace_id=trace_id,
            )

            # Parse LLM response
            result = self._parse_query_generation_response(llm_response, trace_id)

            # Log generation results
            self._log_generation_results(query, result, trace_id)

            return result

        except Exception as e:
            logger.error(
                "Query generation failed, using fallback",
                extra={"error": str(e), "trace_id": trace_id},
            )
            # Return basic generation on failure
            return self._create_fallback_generation(query, domain, belief_state, trace_id)

    def _parse_query_generation_response(
        self,
        llm_response: str,
        trace_id: str,
    ) -> QueryGenerationResult:
        """Parse LLM response into query generation result.

        Args:
            llm_response: Raw LLM response text
            trace_id: Trace ID for correlation

        Returns:
            Parsed query generation result
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
                # Parse as plain text
                data = self._parse_generation_text_response(llm_response, trace_id)

            # Ensure required fields have values
            must_include = data.get("must_include", [])
            if len(must_include) < 3:
                must_include = list(set(must_include + self._extract_core_keywords(data.get("q1", ""))))[:6]

            expanded_keywords = data.get("expanded_keywords", [])
            if len(expanded_keywords) < 5:
                expanded_keywords = self._expand_keywords_from_response(data, expanded_keywords)

            return QueryGenerationResult(
                q1=data.get("q1", ""),
                q2=data.get("q2", ""),
                q3=data.get("q3", ""),
                must_include=must_include,
                expanded_keywords=expanded_keywords,
                slot_filled=data.get("slot_filled", {}),
                location_context=data.get("location_context"),
                domain_specific_terms=data.get("domain_specific_terms", []),
                trace_id=trace_id,
            )

        except Exception as e:
            logger.warning(
                "Failed to parse query generation response",
                extra={"error": str(e), "trace_id": trace_id},
            )
            raise

    def _parse_generation_text_response(
        self,
        response: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Parse plain text generation response.

        Args:
            response: Plain text response
            trace_id: Trace ID for correlation

        Returns:
            Structured data dictionary
        """
        # Extract queries from text (one per line)
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        queries = [line for line in lines if len(line) > 5][:3]

        # Pad with original if needed
        while len(queries) < 3:
            queries.append(response.strip())

        return {
            "q1": queries[0] if len(queries) > 0 else response,
            "q2": queries[1] if len(queries) > 1 else queries[0],
            "q3": queries[2] if len(queries) > 2 else queries[0],
            "must_include": self._extract_core_keywords(response),
            "expanded_keywords": self._extract_expanded_keywords(response),
        }

    def _extract_core_keywords(self, query: str) -> List[str]:
        """Extract core keywords from query.

        Args:
            query: Query text

        Returns:
            List of core keywords (3-6)
        """
        # Simple extraction: meaningful words longer than 1 char
        import re
        words = re.findall(r'[\u4e00-\u9fff]{2,}', query)  # Chinese words >= 2 chars
        return list(set(words))[:6]

    def _expand_keywords_from_response(self, data: Dict[str, Any], existing: List[str]) -> List[str]:
        """Expand keywords from response data.

        Args:
            data: Parsed response data
            existing: Existing keywords

        Returns:
            Expanded keyword list (5-10)
        """
        expanded = list(existing)

        # Add from must_include
        must_include = data.get("must_include", [])
        expanded.extend(must_include)

        # Add domain-specific terms
        domain_terms = data.get("domain_specific_terms", [])
        expanded.extend(domain_terms)

        # Remove duplicates and limit
        result = list(dict.fromkeys(expanded))  # Preserve order while deduping
        return result[:10]

    def _extract_expanded_keywords(self, query: str) -> List[str]:
        """Extract expanded keywords from query.

        Args:
            query: Query text

        Returns:
            List of expanded keywords (5-10)
        """
        import re
        words = re.findall(r'[\u4e00-\u9fff]+', query)  # All Chinese words
        return list(set(words))[:10]

    def _create_fallback_generation(
        self,
        query: str,
        domain: Optional[BusinessDomain],
        belief_state: BeliefState,
        trace_id: str,
    ) -> QueryGenerationResult:
        """Create fallback query generation when LLM fails.

        Args:
            query: User query
            domain: Business domain
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            Basic query generation result
        """
        # Generate simple query variations
        q1 = query  # Direct query

        # q2: Add domain context if available
        if domain:
            domain_context = {
                BusinessDomain.FINANCE: "费用",
                BusinessDomain.HR: "人事",
                BusinessDomain.SAFETY: "安全",
                BusinessDomain.GOVERNANCE: "制度",
                BusinessDomain.IT: "信息化",
                BusinessDomain.PROCUREMENT: "采购",
                BusinessDomain.ADMIN: "行政",
                BusinessDomain.PARTY: "党建",
                BusinessDomain.UNION: "工会",
            }
            q2 = f"{domain_context.get(domain, '')} {query}"
        else:
            q2 = query

        # q3: Add slot context if available
        slot_parts = []
        for key, value in belief_state.slots.items():
            if value and key not in ["domain"]:
                slot_parts.append(str(value))
        if slot_parts:
            q3 = " ".join([query] + slot_parts)
        else:
            q3 = query

        # Extract keywords
        must_include = self._extract_core_keywords(query)
        expanded_keywords = self._extract_expanded_keywords(query)

        # Slot filled
        slot_filled = {k: v for k, v in belief_state.slots.items() if v}

        return QueryGenerationResult(
            q1=q1,
            q2=q2,
            q3=q3,
            must_include=must_include[:6],
            expanded_keywords=expanded_keywords[:10],
            slot_filled=slot_filled,
            location_context=belief_state.get_slot("city"),
            domain_specific_terms=[],
            trace_id=trace_id,
        )

    def _log_generation_results(
        self,
        query: str,
        result: QueryGenerationResult,
        trace_id: str,
    ) -> None:
        """Log query generation results for observability.

        Args:
            query: Original query
            result: Generated query result
            trace_id: Trace ID for correlation
        """
        logger.info(
            "Query generation completed",
            extra={
                "original_query": query[:50],
                "q1": result.q1[:50],
                "q2": result.q2[:50],
                "q3": result.q3[:50],
                "must_include_count": len(result.must_include),
                "expanded_keywords_count": len(result.expanded_keywords),
                "slot_filled_keys": list(result.slot_filled.keys()),
                "location_context": result.location_context,
                "domain_specific_terms_count": len(result.domain_specific_terms),
                "trace_id": trace_id,
            },
        )

    async def _update_belief_state(
        self,
        belief_state: BeliefState,
        query: str,
        extracted_elements: ExtractedQueryElements,
        trace_id: str,
    ) -> None:
        """Update belief state with new information.

        Args:
            belief_state: Current belief state
            query: User query
            extracted_elements: Extracted elements
            trace_id: Trace ID for correlation
        """
        # Add query to history
        belief_state.add_query(query)

        # Update slots from extraction
        if extracted_elements.temporal.year:
            belief_state.set_slot("year", extracted_elements.temporal.year)
        if extracted_elements.spatial.city:
            belief_state.set_slot("city", extracted_elements.spatial.city)
        if extracted_elements.content.topic:
            belief_state.set_slot("topic", extracted_elements.content.topic)
        if extracted_elements.detected_domain:
            belief_state.set_slot("domain", extracted_elements.detected_domain.value)

        # Save to store
        await self._belief_state_store.update_state(belief_state, trace_id=trace_id)

    def _build_response(
        self,
        query_type: QueryType,
        generated_queries: QueryGenerationResult,
        extracted_elements: ExtractedQueryElements,
        belief_state: BeliefState,
        trace_id: str,
    ) -> ConversationalQueryCapabilityOutput:
        """Build the capability output response.

        Args:
            query_type: Classified query type
            generated_queries: Generated queries
            extracted_elements: Extracted elements
            belief_state: Current belief state
            trace_id: Trace ID for correlation

        Returns:
            Capability output
        """
        return ConversationalQueryCapabilityOutput(
            query_type=query_type,
            generated_queries=generated_queries,
            extracted_elements=extracted_elements,
            belief_state=belief_state.to_dict(),
            is_followup=extracted_elements.is_followup,
            confidence=extracted_elements.confidence,
            clarification_needed=extracted_elements.clarification_needed,
            session_id=belief_state.session_id,
            turn_count=belief_state.conversation_turn,
            trace_id=trace_id,
        )

    def _classify_domain(
        self,
        query: str,
        trace_id: str,
    ) -> Optional[BusinessDomain]:
        """Classify query into business domain with enhanced logic.

        Wraps ColloquialMapperService with priority ordering and fallback.

        Args:
            query: User query text
            trace_id: Trace ID for correlation

        Returns:
            Classified business domain or None
        """
        try:
            # Use ColloquialMapperService for primary classification
            domain = self._colloquial_mapper.classify_domain(query, trace_id)

            if domain and domain != BusinessDomain.OTHER:
                logger.info(
                    "Domain classified",
                    extra={
                        "query": query[:50],
                        "domain": domain.value,
                        "trace_id": trace_id,
                    },
                )
                return domain

            # If OTHER or None, try to infer from common patterns
            inferred_domain = self._infer_domain_from_patterns(query, trace_id)
            if inferred_domain:
                return inferred_domain

            return None

        except Exception as e:
            logger.warning(
                "Domain classification failed",
                extra={"error": str(e), "trace_id": trace_id},
            )
            return None

    def _infer_domain_from_patterns(
        self,
        query: str,
        trace_id: str,
    ) -> Optional[BusinessDomain]:
        """Infer domain from common query patterns.

        Args:
            query: User query text
            trace_id: Trace ID for correlation

        Returns:
            Inferred business domain or None
        """
        # Domain priority patterns (checked in order)
        domain_patterns = {
            BusinessDomain.FINANCE: [
                r"报销", r"费用", r"预算", r"差旅", r"住宿", r"用餐", r"交通",
            ],
            BusinessDomain.HR: [
                r"人事", r"招聘", r"入职", r"离职", r"考勤", r"薪酬", r"工资", r"培训",
            ],
            BusinessDomain.SAFETY: [
                r"安全", r"消防", r"环保", r"隐患", r"事故", r"检查", r"整改",
            ],
            BusinessDomain.GOVERNANCE: [
                r"治理", r"合规", r"审计", r"内控", r"制度", r"章程",
            ],
            BusinessDomain.IT: [
                r"信息化", r"系统", r"软件", r"硬件", r"网络", r"服务器",
            ],
            BusinessDomain.PROCUREMENT: [
                r"采购", r"招标", r"供应商", r"合同",
            ],
            BusinessDomain.ADMIN: [
                r"行政", r"后勤", r"接待", r"车辆", r"办公",
            ],
            BusinessDomain.PARTY: [
                r"党建", r"党委", r"支部", r"党员", r"组织",
            ],
            BusinessDomain.UNION: [
                r"工会", r"职代会", r"福利", r"经审",
            ],
            BusinessDomain.COMMITTEE: [
                r"专业委员会", r"提案", r"女职工",
            ],
        }

        import re
        for domain, patterns in domain_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    logger.info(
                        "Domain inferred from pattern",
                        extra={
                            "query": query[:50],
                            "domain": domain.value,
                            "pattern": pattern,
                            "trace_id": trace_id,
                        },
                    )
                    return domain

        return None

    def _route_to_domain_processing(
        self,
        query: str,
        extracted_elements: ExtractedQueryElements,
        belief_state: BeliefState,
        domain: Optional[BusinessDomain],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Route query to domain-specific processing pipeline.

        Args:
            query: User query text
            extracted_elements: Extracted elements
            belief_state: Current belief state
            domain: Classified business domain
            trace_id: Trace ID for correlation

        Returns:
            Routing context with domain-specific parameters
        """
        routing_context = {
            "domain": domain.value if domain else None,
            "use_domain_template": False,
            "domain_specific_terms": [],
            "processing_priority": "standard",
        }

        if domain and domain != BusinessDomain.OTHER:
            # Enable domain-specific processing
            routing_context["use_domain_template"] = True
            routing_context["processing_priority"] = "domain_specific"

            # Get domain-specific mappings
            domain_mappings = self._colloquial_mapper.get_domain_mappings(domain, trace_id)
            routing_context["domain_specific_terms"] = list(domain_mappings.keys())[:5]

            # Add domain to belief state for context inheritance
            belief_state.set_slot("domain", domain.value)

            logger.info(
                "Routed to domain-specific processing",
                extra={
                    "domain": domain.value,
                    "term_count": len(routing_context["domain_specific_terms"]),
                    "trace_id": trace_id,
                },
            )

        return routing_context

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
                "enable_colloquial_mapping": self._config.enable_colloquial_mapping,
                "enable_domain_routing": self._config.enable_domain_routing,
                "enable_followup_detection": self._config.enable_followup_detection,
                "min_confidence_threshold": self._config.min_confidence_threshold,
                "high_confidence_threshold": self._config.high_confidence_threshold,
            },
        }
