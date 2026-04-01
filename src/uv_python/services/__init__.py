"""
Service layer for uv_python.

This module provides high-level services for Python version management,
including version discovery, installation, verification, and configuration.
"""

from uv_python.services.version_discovery import VersionDiscoveryService
from uv_python.services.installer import PythonInstaller
from uv_python.services.installed_versions import InstalledVersionsService
from uv_python.services.uninstaller import PythonUninstaller
from uv_python.services.project_detector import ProjectDetector
from uv_python.services.version_resolver import VersionResolver
from uv_python.services.global_config import GlobalConfigService
from uv_python.services.verifier import VerificationService

__all__ = [
    "VersionDiscoveryService",
    "PythonInstaller",
    "InstalledVersionsService",
    "PythonUninstaller",
    "ProjectDetector",
    "VersionResolver",
    "GlobalConfigService",
    "VerificationService",
]
