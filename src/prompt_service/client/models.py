"""
Data models for Prompt Service SDK.

These classes provide a clean, typed API for interacting with
the prompt service responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Section:
    """A section in a prompt template.

    Attributes:
        name: Section name
        content: Section content
    """

    name: str
    content: str


@dataclass
class PromptOptions:
    """Options for prompt retrieval.

    Attributes:
        version_id: Specific version to retrieve (None for active)
        include_metadata: Include version metadata in response
    """

    version_id: Optional[int] = None
    include_metadata: bool = False


@dataclass
class RetrievedDoc:
    """A retrieved document for prompt inclusion.

    Attributes:
        id: Document identifier
        content: Document content
        metadata: Additional metadata
    """

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptResponse:
    """Response from prompt retrieval.

    Attributes:
        content: Fully rendered prompt text
        template_id: Template identifier
        version_id: Version that was used
        variant_id: A/B test variant ID (if applicable)
        sections: Rendered sections (if include_metadata)
        metadata: Version metadata
        trace_id: Request trace identifier
        from_cache: Whether response was cached
    """

    content: str
    template_id: str
    version_id: int
    variant_id: Optional[str] = None
    sections: Optional[List[Section]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    from_cache: bool = False


@dataclass
class VariableDef:
    """Variable definition for a prompt template.

    Attributes:
        name: Variable name
        description: Variable description
        type: Variable type
        default_value: Default value
        is_required: Whether value is required
    """

    name: str
    description: str
    type: str
    default_value: Optional[Any] = None
    is_required: bool = True


@dataclass
class PromptInfo:
    """Information about a prompt template.

    Attributes:
        template_id: Template identifier
        name: Human-readable name
        description: Purpose and usage
        version: Current version
        sections: Ordered prompt sections
        variables: Variable definitions
        tags: Categorization tags
        is_active: Whether this is the active version
        is_published: Whether published
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: Creator user ID
    """

    template_id: str
    name: str
    description: str
    version: int
    sections: List[Section]
    variables: Dict[str, VariableDef]
    tags: List[str]
    is_active: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime
    created_by: str


@dataclass
class PromptListResponse:
    """Response from listing prompts.

    Attributes:
        prompts: List of prompt templates
        total: Total count
        page: Current page number
        page_size: Page size
    """

    prompts: List[PromptInfo]
    total: int
    page: int
    page_size: int


@dataclass
class HealthStatus:
    """Health check response.

    Attributes:
        status: Health status (healthy, degraded, unhealthy)
        version: Service version
        components: Status of individual components
        uptime_ms: Service uptime in milliseconds
    """

    status: str
    version: str
    components: Dict[str, str] = field(default_factory=dict)
    uptime_ms: float = 0.0
