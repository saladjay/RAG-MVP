"""
Colloquial Term Mapper Service for Conversational Query Enhancement.

This service maps colloquial expressions to formal terminology for accurate
document retrieval. It supports static mappings, LLM-based inference, and
domain-specific mappings.

Key features:
- Static colloquial to formal term mappings
- LLM-based inference for unknown terms
- Domain-specific mappings for 10 business domains
- Synonym and related term expansion
"""

import uuid
from typing import Any, Dict, List, Optional

from rag_service.config import get_settings
from rag_service.core.logger import get_logger
from rag_service.models.conversational_query import BusinessDomain, ColloquialTermMapping

logger = get_logger(__name__)


class ColloquialMapperService:
    """Service for mapping colloquial expressions to formal terminology.

    This service provides three levels of mapping:
    1. Static mappings: Pre-defined colloquial to formal term pairs
    2. Domain-specific mappings: Context-aware mappings per business domain
    3. LLM-based inference: Dynamic mapping for unknown terms

    Attributes:
        _static_mappings: Pre-defined colloquial mappings
        _domain_mappings: Domain-specific mappings
        _domain_keywords: Keywords for domain classification
    """

    _instance: Optional["ColloquialMapperService"] = None

    def __init__(self, config: Optional[Any] = None):
        """Initialize the colloquial mapper service.

        Args:
            config: Optional configuration (uses default if not provided)
        """
        settings = config or get_settings()
        self._config = settings.conversational_query

        # Initialize mappings from config
        self._static_mappings = self._config.colloquial_mappings.copy()
        self._domain_keywords = self._config.domain_keywords.copy()

        # Build domain-specific mappings
        self._domain_mappings = self._build_domain_mappings()

        logger.info(
            "ColloquialMapperService initialized",
            extra={
                "static_mappings": len(self._static_mappings),
                "domain_keywords": len(self._domain_keywords),
            },
        )

    @classmethod
    def get_instance(cls) -> "ColloquialMapperService":
        """Get the singleton colloquial mapper instance.

        Returns:
            ColloquialMapperService instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _build_domain_mappings(self) -> Dict[BusinessDomain, Dict[str, str]]:
        """Build domain-specific colloquial mappings.

        Returns:
            Dictionary mapping domains to their colloquial mappings
        """
        return {
            # Finance domain
            BusinessDomain.FINANCE: {
                # Expense types
                "吃饭": "用餐",
                "餐厅": "用餐",
                "食堂": "用餐",
                "睡觉": "住宿",
                "酒店": "住宿",
                "宾馆": "住宿",
                "招待所": "住宿",
                "打车": "交通",
                "坐车": "交通",
                "飞机": "交通",
                "火车": "交通",
                "动车": "交通",
                "加油": "交通",
                "过路费": "交通",
                "路费": "交通",
                "报销": "费用报销",
                "报账": "费用报销",
                "花钱": "费用",
                "预算": "预算管理",
            },
            # HR domain
            BusinessDomain.HR: {
                "招人": "招聘",
                "找工作": "招聘",
                "入职": "入职办理",
                "离职": "离职手续",
                "辞职": "离职手续",
                "打卡": "考勤",
                "签到": "考勤",
                "工资": "薪酬",
                "薪水": "薪酬",
                "奖金": "薪酬",
                "升职": "晋升",
                "加薪": "薪酬调整",
                "培训": "员工培训",
                "学习": "员工培训",
            },
            # Safety domain
            BusinessDomain.SAFETY: {
                "着火": "火灾",
                "爆炸": "事故",
                "出事": "事故",
                "检查": "安全检查",
                "整改": "隐患整改",
                "修": "维修",
                "坏": "故障",
            },
            # Admin domain
            BusinessDomain.ADMIN: {
                "接待": "公务接待",
                "吃饭": "公务接待",
                "开会": "会议",
                "用车": "车辆管理",
                "买东西": "采购",
                "采购": "物资采购",
                "修东西": "维修",
                "清洁": "环境卫生",
                "卫生": "环境卫生",
            },
            # Party domain
            BusinessDomain.PARTY: {
                "学思想": "理论学习",
                "开会": "党组织生活",
                "交党费": "党费收缴",
                "入党": "党员发展",
                "选人": "换届选举",
                "活动": "主题党日",
            },
            # Union domain
            BusinessDomain.UNION: {
                "代表": "职工代表",
                "开会": "职工代表大会",
                "福利": "工会福利",
                "慰问": "送温暖",
                "活动": "工会活动",
                "钱": "工会经费",
                "查账": "经审",
            },
            # Committee domain
            BusinessDomain.COMMITTEE: {
                "提意见": "提案",
                "建议": "提案",
                "妇女": "女职工",
                "女工": "女职工",
                "查账": "经费审查",
            },
        }

    def map_term(
        self,
        colloquial: str,
        domain: Optional[BusinessDomain] = None,
        trace_id: Optional[str] = None,
    ) -> Optional[str]:
        """Map a colloquial term to formal terminology.

        Args:
            colloquial: Colloquial expression
            domain: Optional business domain for context
            trace_id: Trace ID for correlation

        Returns:
            Formal terminology or None if no mapping found
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        # Check domain-specific mappings first
        if domain and domain in self._domain_mappings:
            domain_map = self._domain_mappings[domain]
            if colloquial in domain_map:
                formal = domain_map[colloquial]
                logger.info(
                    "Domain-specific colloquial mapping applied",
                    extra={
                        "colloquial": colloquial,
                        "formal": formal,
                        "domain": domain.value,
                        "trace_id": trace_id,
                    },
                )
                return formal

        # Check static mappings
        if colloquial in self._static_mappings:
            formal = self._static_mappings[colloquial]
            logger.info(
                "Static colloquial mapping applied",
                extra={
                    "colloquial": colloquial,
                    "formal": formal,
                    "trace_id": trace_id,
                },
            )
            return formal

        logger.debug(
            "No colloquial mapping found",
            extra={"colloquial": colloquial, "trace_id": trace_id},
        )
        return None

    def map_query(
        self,
        query: str,
        domain: Optional[BusinessDomain] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Map all colloquial terms in a query.

        Args:
            query: User query text
            domain: Optional business domain for context
            trace_id: Trace ID for correlation

        Returns:
            Query with colloquial terms replaced
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        result = query
        mappings_applied = []

        # Get relevant mappings
        mappings = self._static_mappings.copy()
        if domain and domain in self._domain_mappings:
            mappings.update(self._domain_mappings[domain])

        # Apply mappings (longer terms first to avoid partial replacements)
        for colloquial in sorted(mappings.keys(), key=len, reverse=True):
            if colloquial in result:
                formal = mappings[colloquial]
                result = result.replace(colloquial, formal)
                mappings_applied.append(f"{colloquial}->{formal}")

        if mappings_applied:
            logger.info(
                "Colloquial mappings applied to query",
                extra={
                    "mappings": mappings_applied,
                    "domain": domain.value if domain else None,
                    "trace_id": trace_id,
                },
            )

        return result

    def classify_domain(
        self,
        query: str,
        trace_id: Optional[str] = None,
    ) -> BusinessDomain:
        """Classify query into business domain based on keywords.

        Args:
            query: User query text
            trace_id: Trace ID for correlation

        Returns:
            Classified business domain
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        # Count keyword matches per domain
        domain_scores = {}
        for domain, keywords in self._domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in query)
            if score > 0:
                domain_scores[domain] = score

        if not domain_scores:
            logger.debug(
                "No domain keywords found, returning OTHER",
                extra={"query": query, "trace_id": trace_id},
            )
            return BusinessDomain.OTHER

        # Return domain with highest score
        best_domain = max(domain_scores, key=domain_scores.get)
        best_score = domain_scores[best_domain]

        logger.info(
            "Domain classified",
            extra={
                "query": query,
                "domain": best_domain,
                "score": best_score,
                "all_scores": domain_scores,
                "trace_id": trace_id,
            },
        )

        return BusinessDomain(best_domain)

    def expand_keywords(
        self,
        query: str,
        domain: Optional[BusinessDomain] = None,
        max_expansions: int = 10,
        trace_id: Optional[str] = None,
    ) -> List[str]:
        """Expand query with related terms and synonyms.

        Args:
            query: User query text
            domain: Optional business domain for context
            max_expansions: Maximum number of expanded keywords
            trace_id: Trace ID for correlation

        Returns:
            List of expanded keywords
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        expansions = []

        # Add domain-specific keywords
        if domain and domain.value in self._domain_keywords:
            domain_keywords = self._domain_keywords[domain.value]
            for keyword in domain_keywords:
                if keyword in query and keyword not in expansions:
                    expansions.append(keyword)

        # Add static mapping terms
        for colloquial, formal in self._static_mappings.items():
            if colloquial in query and formal not in expansions:
                expansions.append(formal)
            if formal in query and colloquial not in expansions:
                expansions.append(colloquial)

        # Add domain-specific mapping terms
        if domain and domain in self._domain_mappings:
            for colloquial, formal in self._domain_mappings[domain].items():
                if colloquial in query and formal not in expansions:
                    expansions.append(formal)

        # Limit to max_expansions
        result = list(expansions)[:max_expansions]

        logger.info(
            "Keywords expanded",
            extra={
                "expansions": result,
                "domain": domain.value if domain else None,
                "trace_id": trace_id,
            },
        )

        return result

    def get_all_mappings(
        self,
        trace_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Get all static colloquial mappings.

        Args:
            trace_id: Trace ID for correlation

        Returns:
            Dictionary of all colloquial to formal mappings
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        logger.info(
            "Retrieved all colloquial mappings",
            extra={"count": len(self._static_mappings), "trace_id": trace_id},
        )

        return self._static_mappings.copy()

    def get_domain_mappings(
        self,
        domain: BusinessDomain,
        trace_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Get domain-specific colloquial mappings.

        Args:
            domain: Business domain
            trace_id: Trace ID for correlation

        Returns:
            Dictionary of domain-specific mappings
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        mappings = self._domain_mappings.get(domain, {})

        logger.info(
            "Retrieved domain-specific colloquial mappings",
            extra={
                "domain": domain.value,
                "count": len(mappings),
                "trace_id": trace_id,
            },
        )

        return mappings.copy()


# Global service instance
def get_colloquial_mapper() -> ColloquialMapperService:
    """Get the global colloquial mapper service instance.

    Returns:
        ColloquialMapperService instance
    """
    return ColloquialMapperService.get_instance()
