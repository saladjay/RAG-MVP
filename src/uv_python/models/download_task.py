"""
Download task data model.

This module provides the DownloadTask dataclass for representing
in-progress Python version downloads.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class DownloadStatus(Enum):
    """Download task status."""
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadTask:
    """
    Represents an in-progress Python version download.

    This dataclass captures download progress including bytes downloaded,
    status, and retry information.

    Attributes:
        task_id: Unique task identifier (UUID).
        target_version: Python version being downloaded.
        download_url: Source URL.
        destination_path: Local file destination.
        total_bytes: Total file size in bytes.
        downloaded_bytes: Bytes downloaded so far.
        started_at: Download start time.
        status: Current download status.
        retry_count: Number of retry attempts.
        error_message: Error details if failed.
        completed_at: Completion timestamp (if completed).
    """

    task_id: str
    target_version: str
    download_url: str
    destination_path: Path
    total_bytes: int
    downloaded_bytes: int
    started_at: datetime
    status: DownloadStatus
    retry_count: int
    error_message: Optional[str]
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate DownloadTask fields after initialization."""
        # Validate task_id is a UUID
        try:
            uuid.UUID(self.task_id)
        except ValueError:
            raise ValueError(f"Invalid task_id '{self.task_id}'. Must be a UUID")

        # Validate URL
        if not self.download_url.startswith(("http://", "https://")):
            raise ValueError("download_url must use http:// or https://")

        # Validate destination path
        if not isinstance(self.destination_path, Path):
            self.destination_path = Path(self.destination_path)

        # Validate byte counts
        if self.total_bytes <= 0:
            raise ValueError("total_bytes must be positive")
        if not 0 <= self.downloaded_bytes <= self.total_bytes:
            raise ValueError(f"downloaded_bytes must be between 0 and {self.total_bytes}")

        # Validate retry count
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")

        # Validate status
        if not isinstance(self.status, DownloadStatus):
            try:
                self.status = DownloadStatus(self.status)
            except ValueError:
                raise ValueError(f"Invalid status '{self.status}'")

        # Validate error message for failed status
        if self.status == DownloadStatus.FAILED and not self.error_message:
            raise ValueError("error_message is required when status is FAILED")

    @property
    def progress(self) -> float:
        """Get download progress as a percentage (0-100)."""
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100

    @property
    def is_downloading(self) -> bool:
        """Check if download is in progress."""
        return self.status == DownloadStatus.DOWNLOADING

    @property
    def is_paused(self) -> bool:
        """Check if download is paused."""
        return self.status == DownloadStatus.PAUSED

    @property
    def is_completed(self) -> bool:
        """Check if download is completed."""
        return self.status == DownloadStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if download has failed."""
        return self.status == DownloadStatus.FAILED

    @property
    def remaining_bytes(self) -> int:
        """Get remaining bytes to download."""
        return max(0, self.total_bytes - self.downloaded_bytes)

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds since start."""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()

    def update_progress(self, bytes_downloaded: int) -> None:
        """
        Update download progress.

        Args:
            bytes_downloaded: Number of bytes downloaded so far.
        """
        if bytes_downloaded < 0:
            raise ValueError("bytes_downloaded cannot be negative")
        if bytes_downloaded > self.total_bytes:
            bytes_downloaded = self.total_bytes

        self.downloaded_bytes = bytes_downloaded

        # Auto-complete if fully downloaded
        if self.downloaded_bytes >= self.total_bytes and self.status == DownloadStatus.DOWNLOADING:
            self.complete()

    def start(self) -> None:
        """Start or resume the download."""
        if self.status in (DownloadStatus.FAILED, DownloadStatus.PAUSED):
            self.started_at = datetime.now()
            self.retry_count += 1 if self.status == DownloadStatus.FAILED else 0
            self.error_message = None

        self.status = DownloadStatus.DOWNLOADING

    def pause(self) -> None:
        """Pause the download."""
        if self.status == DownloadStatus.DOWNLOADING:
            self.status = DownloadStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused download."""
        if self.status == DownloadStatus.PAUSED:
            self.status = DownloadStatus.DOWNLOADING

    def complete(self) -> None:
        """Mark download as completed."""
        self.status = DownloadStatus.COMPLETED
        self.downloaded_bytes = self.total_bytes
        self.completed_at = datetime.now()

    def fail(self, error_message: str) -> None:
        """
        Mark download as failed.

        Args:
            error_message: Description of the failure.
        """
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now()

    def reset(self) -> None:
        """Reset the download task for retry."""
        self.status = DownloadStatus.DOWNLOADING
        self.downloaded_bytes = 0
        self.started_at = datetime.now()
        self.error_message = None
        self.completed_at = None

    def to_dict(self) -> dict:
        """
        Convert DownloadTask to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "task_id": self.task_id,
            "target_version": self.target_version,
            "download_url": self.download_url,
            "destination_path": str(self.destination_path),
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "started_at": self.started_at.isoformat(),
            "status": self.status.value,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadTask":
        """
        Create DownloadTask from dictionary.

        Args:
            data: Dictionary containing download task data.

        Returns:
            DownloadTask instance.
        """
        started_at = data["started_at"]
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))

        completed_at = data.get("completed_at")
        if completed_at and isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))

        status = data["status"]
        if isinstance(status, str):
            status = DownloadStatus(status)

        return cls(
            task_id=data["task_id"],
            target_version=data["target_version"],
            download_url=data["download_url"],
            destination_path=Path(data["destination_path"]),
            total_bytes=data["total_bytes"],
            downloaded_bytes=data["downloaded_bytes"],
            started_at=started_at,
            status=status,
            retry_count=data["retry_count"],
            error_message=data.get("error_message"),
            completed_at=completed_at,
        )

    @classmethod
    def create(
        cls,
        target_version: str,
        download_url: str,
        destination_path: Path,
        total_bytes: int,
    ) -> "DownloadTask":
        """
        Create a new DownloadTask.

        Args:
            target_version: Python version being downloaded.
            download_url: Source URL.
            destination_path: Local file destination.
            total_bytes: Total file size in bytes.

        Returns:
            New DownloadTask instance.
        """
        return cls(
            task_id=str(uuid.uuid4()),
            target_version=target_version,
            download_url=download_url,
            destination_path=destination_path,
            total_bytes=total_bytes,
            downloaded_bytes=0,
            started_at=datetime.now(),
            status=DownloadStatus.DOWNLOADING,
            retry_count=0,
            error_message=None,
        )

    def __str__(self) -> str:
        """Return string representation."""
        status_symbol = {
            DownloadStatus.DOWNLOADING: "↓",
            DownloadStatus.PAUSED: "⏸",
            DownloadStatus.COMPLETED: "✓",
            DownloadStatus.FAILED: "✗",
        }
        symbol = status_symbol.get(self.status, "?")
        progress_pct = f"{self.progress:.1f}%"
        return f"{self.target_version} [{symbol}] {progress_pct}"
