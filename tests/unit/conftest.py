"""
Shared fixtures for unit tests.

This module provides common test fixtures used across all unit tests.
Fixtures include mocks for external dependencies and sample data objects.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock

from prompt_service.services.langfuse_client import LangfuseClientWrapper
from prompt_service.models.prompt import (
    PromptTemplate,
    PromptAssemblyContext,
    PromptAssemblyResult,
    StructuredSection,
    VariableDef,
    VariableType,
)
from prompt_service.models.ab_test import (
    ABTest,
    ABTestConfig,
    ABTestStatus,
    PromptVariant,
    VariantMetrics,
)
from prompt_service.models.trace import TraceRecord


@pytest.fixture
def mock_langfuse_client() -> MagicMock:
    """Mock Langfuse client for unit tests.

    Returns a MagicMock that simulates Langfuse operations
    without actually connecting to the service.
    """
    mock = MagicMock(spec=LangfuseClientWrapper)
    mock.is_connected.return_value = True
    mock.get_prompt = MagicMock(return_value={
        "name": "test_prompt",
        "prompt": """[角色]
AI助手

[任务]
{{input}}

[约束]
准确、简洁
""",
        "version": 1,
        "config": {
            "variables": {
                "input": {
                    "type": "string",
                    "description": "User input",
                    "required": True
                }
            }
        },
        "metadata": {
            "created_by": "test@example.com"
        }
    })
    mock.create_prompt = MagicMock(return_value={
        "name": "created_prompt",
        "prompt": "Created: {{input}}",
        "version": 1,
        "config": {},
        "metadata": {}
    })
    mock.update_prompt = MagicMock(return_value={
        "name": "updated_prompt",
        "prompt": "Updated: {{input}}",
        "version": 2,
        "config": {},
        "metadata": {}
    })
    mock.log_trace = MagicMock(return_value=True)
    mock.health = MagicMock(return_value={"status": "connected"})
    mock.flush = MagicMock()
    return mock


@pytest.fixture
def test_prompt_template() -> PromptTemplate:
    """Sample prompt template for testing.

    Returns a PromptTemplate with common sections for unit tests.
    """
    return PromptTemplate(
        template_id="test_prompt",
        name="Test Prompt",
        description="A test prompt template",
        version=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by="test_user",
        tags=["test", "sample"],
        sections=[
            StructuredSection(
                name="角色",
                content="你是一个AI助手",
                order=0
            ),
            StructuredSection(
                name="任务",
                content="{{input}}",
                order=1
            ),
            StructuredSection(
                name="约束",
                content="回答准确、简洁",
                order=2
            ),
        ],
        variables={
            "input": VariableDef(
                name="input",
                description="User input to process",
                type=VariableType.STRING,
                is_required=True
            )
        },
        is_active=True,
        is_published=True,
        metadata={"test": True}
    )


@pytest.fixture
def test_ab_test() -> ABTest:
    """Sample A/B test for testing.

    Returns an ABTest with two variants.
    """
    return ABTest(
        test_id="test_ab_123",
        template_id="test_prompt",
        name="Test A/B Test",
        description="Testing A/B functionality",
        variants=[
            PromptVariant(
                variant_id="variant_a",
                template_id="test_prompt",
                template_version=1,
                traffic_percentage=50,
                is_control=True,
            ),
            PromptVariant(
                variant_id="variant_b",
                template_id="test_prompt",
                template_version=2,
                traffic_percentage=50,
                is_control=False,
            ),
        ],
        status=ABTestStatus.RUNNING,
        success_metric="success_rate",
        min_sample_size=100,
        target_improvement=0.05,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
    )


@pytest.fixture
def test_trace_record() -> TraceRecord:
    """Sample trace record for testing.

    Returns a TraceRecord with typical values.
    """
    return TraceRecord(
        trace_id="trace_test_123",
        template_id="test_prompt",
        template_version=1,
        variant_id="variant_a",
        input_variables={"input": "test input"},
        context={"user_id": "test_user"},
        retrieved_docs=[
            {
                "id": "doc1",
                "content": "Test document content",
                "metadata": {"source": "test"}
            }
        ],
        rendered_prompt="[角色]\nAI助手\n\n[任务]\ntest input",
        model_output="Test response",
        latency_ms=75.5,
        total_latency_ms=150.0,
        success=True,
        timestamp=datetime.utcnow(),
    )


@pytest.fixture
def test_variables() -> Dict[str, Any]:
    """Sample variables for testing.

    Returns a dictionary of common test variables.
    """
    return {
        "input": "What is the capital of France?",
        "user_name": "Test User",
        "language": "en",
    }


@pytest.fixture
def test_retrieved_docs() -> list:
    """Sample retrieved documents for testing.

    Returns a list of mock retrieved documents.
    """
    return [
        {
            "id": "doc_001",
            "content": "Paris is the capital of France.",
            "metadata": {"source": "encyclopedia", "confidence": 0.95}
        },
        {
            "id": "doc_002",
            "content": "France is located in Western Europe.",
            "metadata": {"source": "atlas", "confidence": 0.98}
        }
    ]


@pytest.fixture
def test_context() -> Dict[str, Any]:
    """Sample context for testing.

    Returns a dictionary of common context values.
    """
    return {
        "user_id": "user_12345",
        "session_id": "session_abc",
        "request_id": "req_xyz",
    }


@pytest.fixture
def mock_cache() -> MagicMock:
    """Mock cache for testing.

    Returns a MagicMock that simulates cache operations.
    """
    mock = MagicMock()
    mock.get = MagicMock(return_value=None)
    mock.set = MagicMock()
    mock.invalidate = MagicMock(return_value=1)
    mock.clear = MagicMock()
    return mock


@pytest.fixture
def reset_services() -> None:
    """Reset all global service instances.

    This fixture should be used in tests that need
    clean service state.
    """
    from prompt_service.services.langfuse_client import reset_langfuse_client
    from prompt_service.services.prompt_retrieval import reset_prompt_retrieval_service
    from prompt_service.services.prompt_management import reset_prompt_management_service
    from prompt_service.services.ab_testing import reset_ab_testing_service
    from prompt_service.services.trace_analysis import reset_trace_analysis_service
    from prompt_service.services.version_control import reset_version_control_service
    from prompt_service.middleware.cache import reset_cache

    # Reset all services
    reset_langfuse_client()
    reset_prompt_retrieval_service()
    reset_prompt_management_service()
    reset_ab_testing_service()
    reset_trace_analysis_service()
    reset_version_control_service()
    reset_cache()

    yield

    # Reset again after test
    reset_langfuse_client()
    reset_prompt_retrieval_service()
    reset_prompt_management_service()
    reset_ab_testing_service()
    reset_trace_analysis_service()
    reset_version_control_service()
    reset_cache()


@pytest.fixture
def sample_ab_test_config() -> ABTestConfig:
    """Sample A/B test configuration.

    Returns a valid ABTestConfig for testing.
    """
    return ABTestConfig(
        template_id="test_prompt",
        name="Test A/B Test",
        description="Testing A/B test configuration",
        variants=[
            ("variant_a", 1, 50, True),
            ("variant_b", 2, 50, False),
        ],
        success_metric="success_rate",
        min_sample_size=100,
        target_improvement=0.05,
    )


@pytest.fixture
def sample_sections() -> list:
    """Sample prompt sections for testing.

    Returns a list of StructuredSection objects.
    """
    return [
        StructuredSection(name="角色", content="AI助手", order=0),
        StructuredSection(name="任务", content="{{input}}", order=1),
        StructuredSection(name="约束", content="准确", order=2),
    ]


@pytest.fixture
def sample_variables_dict() -> Dict[str, VariableDef]:
    """Sample variable definitions for testing.

    Returns a dictionary of VariableDef objects.
    """
    return {
        "input": VariableDef(
            name="input",
            description="User input",
            type=VariableType.STRING,
            is_required=True
        ),
        "context": VariableDef(
            name="context",
            description="Additional context",
            type=VariableType.STRING,
            is_required=False,
            default_value=""
        ),
    }
