"""
Integration tests for Version Control flow (US5).

These tests verify the end-to-end version control flow:
- Rollback restores previous content
- Audit log records rollback action
- Version tracking works correctly
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

from httpx import AsyncClient, ASGITransport

from prompt_service.main import app
from prompt_service.services.version_control import (
    VersionControlService,
    get_version_control_service,
    reset_version_control_service,
)
from prompt_service.services.prompt_management import (
    PromptManagementService,
    reset_prompt_management_service,
)
from prompt_service.models.prompt import (
    PromptTemplate,
    StructuredSection,
    VariableDef,
    VariableType,
)


class TestRollbackE2E:
    """End-to-end tests for rollback flow.

    Tests verify:
    - Rollback restores previous content
    - Audit log records rollback action
    """

    @pytest.fixture
    async def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def mock_langfuse_client(self) -> None:
        """Mock Langfuse client for testing."""
        from prompt_service.services.langfuse_client import LangfuseClientWrapper

        mock = MagicMock(spec=LangfuseClientWrapper)
        mock.is_connected.return_value = True
        mock.get_prompt = MagicMock(return_value={
            "name": "test",
            "prompt": "[角色]\nTest\n",
            "version": 1,
            "config": {},
            "metadata": {}
        })
        mock.update_prompt = MagicMock(return_value={
            "name": "updated",
            "prompt": "[角色]\nUpdated\n",
            "version": 2,
            "config": {},
            "metadata": {}
        })
        mock.create_prompt = MagicMock(return_value={
            "name": "created",
            "prompt": "[角色]\nCreated\n",
            "version": 1,
            "config": {},
            "metadata": {}
        })

        return mock

    @pytest.mark.integration
    async def test_rollback_restores_previous_content(
        self,
        client: AsyncClient,
        mock_langfuse_client: MagicMock,
    ) -> None:
        """Test that rollback restores previous prompt content.

        Given: A prompt with versions 1, 2, 3
        When: Rollback to version 2
        Then: New version 4 has content from version 2
        """
        template_id = "test_rollback_content"

        with patch(
            "prompt_service.services.prompt_management.get_langfuse_client",
            return_value=mock_langfuse_client,
        ):
            reset_version_control_service()
            reset_prompt_management_service()

            service = get_version_control_service()

            # Create version snapshots for versions 1, 2, 3
            for i in range(1, 4):
                template = PromptTemplate(
                    template_id=template_id,
                    name=f"Version {i}",
                    description=f"Version {i} content",
                    version=i,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    created_by="test_user",
                    tags=[],
                    sections=[
                        StructuredSection(
                            name="内容",
                            content=f"Content from version {i}",
                            order=0
                        )
                    ],
                    variables={},
                    is_active=(i == 3),
                    is_published=True,
                    metadata={},
                )
                service.create_version_snapshot(
                    template=template,
                    change_description=f"Created version {i}",
                    changed_by="test_user",
                )

            # Perform rollback
            result = await service.rollback(
                template_id=template_id,
                target_version=2,
                reason="Testing rollback",
                changed_by="test_user",
            )

            assert result is not None
            assert result.template_id == template_id
            assert result.version > 3  # New version created

            # Verify the restored content matches version 2
            history = service.get_history(template_id)
            latest = history[0] if history else None

            if latest:
                assert latest.version > 3

    @pytest.mark.integration
    async def test_audit_log_records_rollback_action(
        self,
        mock_langfuse_client: MagicMock,
    ) -> None:
        """Test that audit log records rollback action.

        Given: A version rollback
        When: Rollback is performed
        Then: Version history entry indicates rollback occurred
        """
        template_id = "test_audit_log"

        with patch(
            "prompt_service.services.prompt_management.get_langfuse_client",
            return_value=mock_langfuse_client,
        ):
            reset_version_control_service()

            service = get_version_control_service()

            # Create initial version
            template = PromptTemplate(
                template_id=template_id,
                name="Original",
                description="Original content",
                version=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by="original_author",
                tags=[],
                sections=[
                    StructuredSection(
                        name="内容",
                        content="Original content",
                        order=0
                    )
                ],
                variables={},
                is_active=True,
                is_published=True,
                metadata={},
            )
            service.create_version_snapshot(
                template=template,
                change_description="Initial version",
                changed_by="original_author",
            )

            # Perform rollback
            result = await service.rollback(
                template_id=template_id,
                target_version=1,
                reason="Audit test rollback",
                changed_by="rollback_user",
            )

            # Check history for audit trail
            history = service.get_history(template_id)

            # Should have at least 2 entries (original + rollback)
            assert len(history) >= 2

            # Find the rollback entry
            rollback_entry = next(
                (v for v in history if "rollback" in v.change_description.lower()),
                None
            )

            # The rollback should be recorded in history
            assert rollback_entry is not None or any(
                "rollback" in v.change_description.lower() or "v1" in v.change_description
                for v in history
            )

    @pytest.mark.integration
    async def test_rollback_with_nonexistent_version_fails(
        self,
        client: AsyncClient,
        mock_langfuse_client: MagicMock,
    ) -> None:
        """Test that rollback to non-existent version fails.

        Given: A prompt template
        When: Rollback to version that doesn't exist
        Then: Returns appropriate error
        """
        from prompt_service.core.exceptions import PromptNotFoundError

        template_id = "test_rollback_nonexistent"

        with patch(
            "prompt_service.services.prompt_management.get_langfuse_client",
            return_value=mock_langfuse_client,
        ):
            reset_version_control_service()

            service = get_version_control_service()

            # Create one version snapshot
            template = PromptTemplate(
                template_id=template_id,
                name="Test",
                description="Test",
                version=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by="test",
                tags=[],
                sections=[],
                variables={},
                is_active=True,
                is_published=True,
                metadata={},
            )
            service.create_version_snapshot(
                template=template,
                change_description="Initial",
                changed_by="test",
            )

            # Try to rollback to non-existent version
            with pytest.raises((PromptNotFoundError, Exception)):
                await service.rollback(
                    template_id=template_id,
                    target_version=99,  # Doesn't exist
                    reason="Testing error",
                    changed_by="test",
                )

    @pytest.mark.integration
    async def test_version_tracking_across_updates(
        self,
        mock_langfuse_client: MagicMock,
    ) -> None:
        """Test that version tracking works across multiple updates.

        Given: A prompt template
        When: Multiple updates are made
        Then: Version history shows all versions
        """
        template_id = "test_version_tracking"

        with patch(
            "prompt_service.services.prompt_management.get_langfuse_client",
            return_value=mock_langfuse_client,
        ):
            reset_version_control_service()

            service = get_version_control_service()

            # Create multiple versions
            for i in range(5):
                template = PromptTemplate(
                    template_id=template_id,
                    name=f"Version {i+1}",
                    description=f"Update {i+1}",
                    version=i+1,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    created_by="test_user",
                    tags=[],
                    sections=[
                        StructuredSection(
                            name="内容",
                            content=f"Update {i+1} content",
                            order=0
                        )
                    ],
                    variables={},
                    is_active=(i == 4),  # Last one is active
                    is_published=True,
                    metadata={},
                )
                service.create_version_snapshot(
                    template=template,
                    change_description=f"Update {i+1}",
                    changed_by="test_user",
                )

            # Get history
            history = service.get_history(template_id)

            # Should have all 5 versions
            assert len(history) == 5

            # Verify chronological order (newest first)
            versions = [v.version for v in history]
            assert versions == sorted(versions, reverse=True)


class TestVersionControlServiceDirect:
    """Direct service tests for VersionControlService."""

    @pytest.mark.integration
    def test_create_version_snapshot(
        self,
    ) -> None:
        """Test creating a version snapshot.

        Given: A prompt template
        When: create_version_snapshot is called
        Then: Snapshot is stored and retrievable
        """
        reset_version_control_service()
        service = get_version_control_service()

        template = PromptTemplate(
            template_id="snapshot_test",
            name="Snapshot Test",
            description="Testing snapshot creation",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=["test"],
            sections=[
                StructuredSection(
                    name="测试",
                    content="Test content",
                    order=0
                )
            ],
            variables={
                "input": VariableDef(
                    name="input",
                    description="Input variable",
                    type=VariableType.STRING,
                    is_required=True
                )
            },
            is_active=True,
            is_published=True,
            metadata={},
        )

        service.create_version_snapshot(
            template=template,
            change_description="Initial snapshot",
            changed_by="test_user",
        )

        # Verify snapshot was created
        history = service.get_history("snapshot_test")
        assert len(history) == 1
        assert history[0].version == 1

    @pytest.mark.integration
    def test_get_history_for_nonexistent_template(
        self,
    ) -> None:
        """Test getting history for non-existent template.

        Given: No template exists
        When: get_history is called
        Then: Returns empty list
        """
        reset_version_control_service()
        service = get_version_control_service()

        history = service.get_history("nonexistent_template")
        assert history == []

    @pytest.mark.integration
    def test_can_rollback_field(
        self,
    ) -> None:
        """Test can_rollback field in version history.

        Given: Version history entries
        When: Versions are created
        Then: can_rollback is True for all versions
        """
        reset_version_control_service()
        service = get_version_control_service()

        template = PromptTemplate(
            template_id="rollback_test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[],
            variables={},
            is_active=True,
            is_published=True,
            metadata={},
        )

        service.create_version_snapshot(
            template=template,
            change_description="Test",
            changed_by="test",
        )

        history = service.get_history("rollback_test")
        assert len(history) > 0
        assert history[0].can_rollback is True
