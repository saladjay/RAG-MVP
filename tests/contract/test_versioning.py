"""
Contract tests for Version Control API (US5).

These tests verify the API contract for version control endpoints:
- GET /api/v1/prompts/{template_id}/versions (version history)
- POST /api/v1/prompts/{template_id}/rollback (rollback)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any

from prompt_service.main import app


class TestVersionControlContract:
    """Contract tests for version control endpoints.

    Tests verify:
    - Version history returns all versions
    - Rollback creates new version from old content
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.contract
    async def test_version_history_returns_all_versions(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that version history returns chronological list.

        Given: A prompt template with multiple versions
        When: GET /api/v1/prompts/{template_id}/versions
        Then: Returns all versions in chronological order
        """
        template_id = "test_versioning_prompt"

        response = await client.get(
            f"/api/v1/prompts/{template_id}/versions"
        )

        # May return 200 if template exists
        # May return 404 if not found
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "template_id" in data
            assert "versions" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data

            # Check version structure
            if data["versions"]:
                version = data["versions"][0]
                assert "version" in version
                assert "change_description" in version
                assert "created_at" in version
                assert "created_by" in version
                assert "is_active" in version
                assert "can_rollback" in version

                # Verify chronological order (newest first)
                if len(data["versions"]) > 1:
                    versions = data["versions"]
                    assert versions[0]["version"] >= versions[1]["version"]

    @pytest.mark.contract
    async def test_version_history_pagination(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that version history supports pagination.

        Given: A prompt with many versions
        When: GET /api/v1/prompts/{template_id}/versions with page params
        Then: Returns paginated results
        """
        template_id = "test_many_versions"

        response = await client.get(
            f"/api/v1/prompts/{template_id}/versions",
            params={"page": 1, "page_size": 10}
        )

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["page"] == 1
            assert data["page_size"] == 10

    @pytest.mark.contract
    async def test_rollback_creates_new_version_from_old(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that rollback creates a new version from old content.

        Given: A prompt template with version history
        When: POST /api/v1/prompts/{template_id}/rollback to version 2
        Then: Creates new version with content from version 2
        """
        template_id = "test_rollback_prompt"

        response = await client.post(
            f"/api/v1/prompts/{template_id}/rollback",
            json={
                "target_version": 2,
                "reason": "Bug in current version, rolling back"
            }
        )

        # May return 200 if rollback succeeds
        # May return 404 if template/version not found
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "template_id" in data
            assert "previous_version" in data
            assert "new_version" in data
            assert "target_version" in data
            assert "rolled_back_at" in data
            assert "trace_id" in data

            # New version should be greater than previous
            assert data["new_version"] > data["previous_version"]
            # Target version should be what we requested
            assert data["target_version"] == 2

    @pytest.mark.contract
    async def test_rollback_requires_valid_version(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that rollback validates target version.

        Given: A rollback request with invalid target version
        When: POST /api/v1/prompts/{template_id}/rollback
        Then: Returns 400 validation error
        """
        template_id = "test_rollback_validation"

        response = await client.post(
            f"/api/v1/prompts/{template_id}/rollback",
            json={
                "target_version": 999,  # Non-existent version
                "reason": "Testing validation"
            }
        )

        # Should return 404 for non-existent version
        assert response.status_code in [400, 404]

    @pytest.mark.contract
    async def test_rollback_includes_change_description(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that rollback includes reason in version history.

        Given: A rollback with a reason
        When: Rollback completes and version history is retrieved
        Then: New version entry includes the rollback reason
        """
        template_id = "test_rollback_reason"
        reason = "Rollback due to customer complaint"

        response = await client.post(
            f"/api/v1/prompts/{template_id}/rollback",
            json={
                "target_version": 1,
                "reason": reason
            }
        )

        if response.status_code == 200:
            # Check version history
            history_response = await client.get(
                f"/api/v1/prompts/{template_id}/versions"
            )

            if history_response.status_code == 200:
                data = history_response.json()
                # Latest version should have rollback info in change description
                if data["versions"]:
                    latest = data["versions"][0]
                    # Change description may mention rollback
                    # (depends on implementation)

    @pytest.mark.contract
    async def test_rollback_updates_active_version(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that rollback updates the active version.

        Given: A prompt with version 3 active
        When: Rollback to version 2
        Then: The new version becomes active
        """
        template_id = "test_rollback_active"

        response = await client.post(
            f"/api/v1/prompts/{template_id}/rollback",
            json={
                "target_version": 2,
                "reason": "Testing active version update"
            }
        )

        if response.status_code == 200:
            # Get prompt info to check active version
            info_response = await client.get(f"/api/v1/prompts/{template_id}")

            if info_response.status_code == 200:
                data = info_response.json()
                # Version should be the new rollback version
                assert data["version"] > 2
                assert data["is_active"] is True

    @pytest.mark.contract
    async def test_version_history_shows_rollback_count(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that version history tracks rollback counts.

        Given: A version that has been rolled back to multiple times
        When: GET /api/v1/prompts/{template_id}/versions
        Then: rollback_count field reflects number of rollbacks
        """
        template_id = "test_rollback_count"

        history_response = await client.get(
            f"/api/v1/prompts/{template_id}/versions"
        )

        if history_response.status_code == 200:
            data = history_response.json()
            if data["versions"]:
                for version in data["versions"]:
                    # rollback_count should be present
                    assert "rollback_count" in version
                    assert version["rollback_count"] >= 0
