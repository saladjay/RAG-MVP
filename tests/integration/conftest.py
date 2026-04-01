"""
Shared fixtures for integration tests.

This module provides common test fixtures used across all integration tests.
Fixtures include FastAPI test app, database cleanup, and service setup.
"""

import asyncio
import pytest
from datetime import datetime
from typing import AsyncGenerator, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from prompt_service.main import app
from prompt_service.config import get_config
from prompt_service.services.langfuse_client import LangfuseClientWrapper


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for FastAPI.

    This fixture provides an httpx AsyncClient configured
    to make requests to the test FastAPI application.

    Yields:
        AsyncClient: Configured test client
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_app() -> FastAPI:
    """Get the test FastAPI application.

    Returns:
        FastAPI: The test application instance
    """
    return app


@pytest.fixture
def mock_langfuse_for_integration() -> MagicMock:
    """Mock Langfuse client for integration tests.

    This fixture provides a more realistic mock that simulates
    Langfuse behavior for integration testing.

    Returns:
        MagicMock: Mocked Langfuse client
    """
    mock = MagicMock(spec=LangfuseClientWrapper)
    mock.is_connected.return_value = True

    # Simulate getting prompts
    mock.get_prompt = MagicMock(side_effect=lambda template_id, version=None: {
        "name": template_id,
        "prompt": f"[角色]\nAI助手 for {template_id}\n\n[任务]\n{{{{input}}}}\n",
        "version": version or 1,
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
            "created_by": "integration_test",
            "created_at": datetime.utcnow().isoformat()
        }
    })

    # Simulate creating prompts
    mock.create_prompt = MagicMock(return_value={
        "name": "created_prompt",
        "prompt": "[角色]\nNew prompt\n\n[任务]\n{{input}}\n",
        "version": 1,
        "config": {},
        "metadata": {}
    })

    # Simulate updating prompts
    mock.update_prompt = MagicMock(return_value={
        "name": "updated_prompt",
        "prompt": "[角色]\nUpdated prompt\n\n[任务]\n{{input}}\n",
        "version": 2,
        "config": {},
        "metadata": {}
    })

    # Simulate trace logging
    mock.log_trace = MagicMock(return_value=True)

    # Simulate health check
    mock.health = MagicMock(return_value={
        "status": "connected",
        "host": "https://mock-langfuse.example.com"
    })

    mock.flush = MagicMock()

    return mock


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Get test configuration.

    Returns test configuration values that can be used
    to configure services for testing.

    Returns:
        Dict with test configuration values
    """
    return {
        "langfuse": {
            "enabled": True,
            "host": "https://mock-langfuse.example.com",
            "public_key": "test_public_key",
            "secret_key": "test_secret_key",
        },
        "cache": {
            "enabled": True,
            "ttl": 300,
        },
        "service": {
            "port": 8000,
            "log_level": "DEBUG",
        }
    }


@pytest.fixture
async def clean_database():
    """Clean up test database state.

    This fixture runs before and after each test to ensure
    clean state for integration tests.

    For this service, we mainly need to reset in-memory
    service state since we're using Langfuse for storage.
    """
    from prompt_service.services.langfuse_client import reset_langfuse_client
    from prompt_service.services.prompt_retrieval import reset_prompt_retrieval_service
    from prompt_service.services.prompt_management import reset_prompt_management_service
    from prompt_service.services.ab_testing import reset_ab_testing_service
    from prompt_service.services.trace_analysis import reset_trace_analysis_service
    from prompt_service.services.version_control import reset_version_control_service
    from prompt_service.middleware.cache import reset_cache

    # Clean up before test
    reset_langfuse_client()
    reset_prompt_retrieval_service()
    reset_prompt_management_service()
    reset_ab_testing_service()
    reset_trace_analysis_service()
    reset_version_control_service()
    reset_cache()

    yield

    # Clean up after test
    reset_langfuse_client()
    reset_prompt_retrieval_service()
    reset_prompt_management_service()
    reset_ab_testing_service()
    reset_trace_analysis_service()
    reset_version_control_service()
    reset_cache()


@pytest.fixture
def sample_prompt_data() -> Dict[str, Any]:
    """Sample prompt data for integration tests.

    Returns a complete prompt creation request payload.
    """
    return {
        "template_id": "integration_test_prompt",
        "name": "Integration Test Prompt",
        "description": "A prompt for integration testing",
        "sections": [
            {
                "name": "角色",
                "content": "你是一个测试助手",
                "is_required": True,
                "order": 0
            },
            {
                "name": "任务",
                "content": "{{input}}",
                "is_required": True,
                "order": 1
            },
            {
                "name": "约束",
                "content": "测试中保持准确",
                "is_required": True,
                "order": 2
            },
            {
                "name": "输出格式",
                "content": "JSON格式",
                "is_required": True,
                "order": 3
            }
        ],
        "variables": {
            "input": {
                "name": "input",
                "description": "Test input",
                "type": "string",
                "is_required": True
            }
        },
        "tags": ["test", "integration"],
        "is_published": True
    }


@pytest.fixture
def sample_ab_test_data() -> Dict[str, Any]:
    """Sample A/B test data for integration tests.

    Returns a complete A/B test creation request payload.
    """
    return {
        "template_id": "integration_test_prompt",
        "name": "Integration Test A/B",
        "description": "Testing A/B functionality",
        "variants": [
            {
                "variant_id": "control",
                "template_version": 1,
                "traffic_percentage": 50,
                "is_control": True
            },
            {
                "variant_id": "treatment",
                "template_version": 2,
                "traffic_percentage": 50,
                "is_control": False
            }
        ],
        "success_metric": "success_rate",
        "min_sample_size": 100,
        "target_improvement": 0.05
    }


@pytest.fixture
def mock_external_services():
    """Mock all external services for integration tests.

    This fixture patches all external dependencies to allow
    integration tests to run without requiring actual services.

    Yields:
        Dict of mock objects
    """
    from prompt_service.services import langfuse_client

    mock_langfuse = MagicMock(spec=LangfuseClientWrapper)
    mock_langfuse.is_connected.return_value = True
    mock_langfuse.get_prompt = MagicMock(return_value={
        "name": "test",
        "prompt": "Test: {{input}}",
        "version": 1,
        "config": {},
        "metadata": {}
    })
    mock_langfuse.create_prompt = MagicMock(return_value={
        "name": "created",
        "prompt": "Created",
        "version": 1,
        "config": {},
        "metadata": {}
    })
    mock_langfuse.update_prompt = MagicMock(return_value={
        "name": "updated",
        "prompt": "Updated",
        "version": 2,
        "config": {},
        "metadata": {}
    })
    mock_langfuse.log_trace = MagicMock(return_value=True)
    mock_langfuse.health = MagicMock(return_value={"status": "connected"})

    with patch.object(
        langfuse_client,
        "get_langfuse_client",
        return_value=mock_langfuse,
    ):
        yield {
            "langfuse": mock_langfuse,
        }


@pytest.fixture
def test_user_context() -> Dict[str, Any]:
    """Sample user context for testing.

    Returns context data that simulates a real user request.
    """
    return {
        "user_id": "integration_test_user",
        "session_id": "test_session_123",
        "request_id": "test_req_abc",
        "timestamp": datetime.utcnow().isoformat(),
    }
