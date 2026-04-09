"""
Batch Upload Script for Milvus Knowledge Base.

This script reads JSON files from the mineru directory and uploads
them to the Milvus knowledge base using the KB upload API.

JSON Structure:
- pdf_file: Original PDF file path (used for title extraction and deduplication)
- markdown: Converted markdown content
- success: Boolean flag (skip if false)
- error: Error message if failed

Features:
- Batch processing with progress tracking
- Duplicate prevention using document_id (based on file path hash)
- Resume capability (can skip already uploaded files)
- Detailed error logging and statistics
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


# Configuration
DEFAULT_MINERU_DIR = r"D:\project\OA\core\batch_output\mineru"
DEFAULT_UPLOAD_API = "http://localhost:8000/kb/upload"
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_TIMEOUT = 300  # 5 minutes per upload

# Upload tracking file (stores already uploaded file hashes)
UPLOAD_TRACKING_FILE = "upload_tracking.json"


class BatchUploader:
    """Batch uploader for Milvus knowledge base."""

    def __init__(
        self,
        mineru_dir: str,
        upload_api: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        timeout: int = DEFAULT_TIMEOUT,
        dry_run: bool = False,
        skip_existing: bool = True,
    ):
        """Initialize the batch uploader.

        Args:
            mineru_dir: Directory containing JSON files
            upload_api: Upload API endpoint URL
            chunk_size: Chunk size for text splitting
            chunk_overlap: Overlap between chunks
            timeout: Request timeout in seconds
            dry_run: If True, simulate upload without actually calling API
            skip_existing: If True, skip files that were already uploaded
        """
        self.mineru_dir = Path(mineru_dir)
        self.upload_api = upload_api
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.timeout = timeout
        self.dry_run = dry_run
        self.skip_existing = skip_existing

        # Statistics
        self.stats = {
            "total_files": 0,
            "skipped_failed": 0,
            "skipped_existing": 0,
            "uploaded": 0,
            "failed": 0,
            "total_chunks": 0,
            "total_content_length": 0,
        }

        # Tracking
        self.uploaded_hashes: set = set()
        self.failed_files: List[Dict[str, Any]] = []

        # Load tracking data if skipping existing
        if self.skip_existing:
            self._load_tracking_data()

    def _load_tracking_data(self) -> None:
        """Load upload tracking data from file."""
        tracking_file = Path(UPLOAD_TRACKING_FILE)
        if tracking_file.exists():
            try:
                with open(tracking_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.uploaded_hashes = set(data.get("uploaded_hashes", []))
                print(f"Loaded tracking data: {len(self.uploaded_hashes)} previously uploaded files")
            except Exception as e:
                print(f"Warning: Failed to load tracking data: {e}")

    def _save_tracking_data(self) -> None:
        """Save upload tracking data to file."""
        try:
            tracking_file = Path(UPLOAD_TRACKING_FILE)
            with open(tracking_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "uploaded_hashes": list(self.uploaded_hashes),
                        "last_update": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            print(f"Warning: Failed to save tracking data: {e}")

    def _get_document_id(self, pdf_file: str) -> str:
        """Generate a unique document ID from the PDF file path.

        Args:
            pdf_file: PDF file path

        Returns:
            Unique document ID based on SHA256 hash of file path
        """
        # Use SHA256 hash of the file path for unique, consistent document ID
        hash_obj = hashlib.sha256(pdf_file.encode("utf-8"))
        return f"doc_{hash_obj.hexdigest()[:32]}"

    def _extract_title(self, pdf_file: str) -> str:
        """Extract document title from PDF file path.

        Args:
            pdf_file: PDF file path

        Returns:
            Document title (filename without path and extension)
        """
        # Get the filename from the path
        filename = Path(pdf_file).name
        # Remove extension
        title = filename.rsplit(".", 1)[0] if "." in filename else filename
        return title

    def _load_json_files(self) -> List[Path]:
        """Load all JSON files from the mineru directory.

        Returns:
            List of JSON file paths
        """
        json_files = list(self.mineru_dir.glob("*.json"))
        print(f"Found {len(json_files)} JSON files in {self.mineru_dir}")
        return json_files

    def _parse_json_file(self, json_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a JSON file and return its contents.

        Args:
            json_path: Path to JSON file

        Returns:
            Parsed JSON data or None if parsing failed
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Warning: Failed to parse {json_path.name}: {e}")
            return None

    def _check_can_upload(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if the document can be uploaded.

        Args:
            data: Parsed JSON data

        Returns:
            Tuple of (can_upload, reason)
        """
        # Check success flag
        if not data.get("success", False):
            return False, "success flag is false"

        # Check required fields
        if "pdf_file" not in data:
            return False, "missing pdf_file field"

        if "markdown" not in data:
            return False, "missing markdown field"

        # Check if markdown is not empty
        markdown = data.get("markdown", "")
        if not markdown or not markdown.strip():
            return False, "markdown content is empty"

        return True, None

    def _upload_document(
        self,
        title: str,
        content: str,
        document_id: str,
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Upload a document to the knowledge base.

        Args:
            title: Document title
            content: Document content (markdown)
            document_id: Unique document identifier

        Returns:
            Tuple of (success, error_message, response_data)
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would upload: {title[:50]}...")
            return True, None, {
                "document_id": document_id,
                "chunk_count": len(content) // self.chunk_size + 1,
            }

        payload = {
            "form_title": title,
            "file_content": content,
            "document_id": document_id,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.upload_api,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return True, None, response.json()

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f": {error_detail.get('detail', '')}"
            except:
                if e.response.text:
                    error_msg += f": {e.response.text[:200]}"
            return False, error_msg, None

        except httpx.TimeoutException:
            return False, "Request timeout", None

        except Exception as e:
            return False, str(e), None

    def process_file(self, json_path: Path) -> bool:
        """Process a single JSON file.

        Args:
            json_path: Path to JSON file

        Returns:
            True if upload succeeded, False otherwise
        """
        # Parse JSON
        data = self._parse_json_file(json_path)
        if data is None:
            return False

        # Check if can upload
        can_upload, reason = self._check_can_upload(data)
        if not can_upload:
            print(f"  Skipping: {reason}")
            self.stats["skipped_failed"] += 1
            return False

        # Extract data
        pdf_file = data["pdf_file"]
        content = data["markdown"]
        title = self._extract_title(pdf_file)
        document_id = self._get_document_id(pdf_file)

        # Check if already uploaded
        if self.skip_existing and document_id in self.uploaded_hashes:
            print(f"  Already uploaded, skipping...")
            self.stats["skipped_existing"] += 1
            return True

        # Upload
        print(f"  Uploading: {title[:50]}...")
        success, error, response = self._upload_document(title, content, document_id)

        if success:
            chunk_count = response.get("chunk_count", 0) if response else 0
            print(f"  [OK] Uploaded ({chunk_count} chunks)")
            self.stats["uploaded"] += 1
            self.stats["total_chunks"] += chunk_count
            self.stats["total_content_length"] += len(content)

            # Add to tracking
            if self.skip_existing:
                self.uploaded_hashes.add(document_id)

            return True
        else:
            print(f"  [FAILED] {error}")
            self.stats["failed"] += 1
            self.failed_files.append({
                "json_file": str(json_path),
                "title": title,
                "document_id": document_id,
                "error": error,
            })
            return False

    def run(self) -> Dict[str, Any]:
        """Run the batch upload process.

        Returns:
            Statistics dictionary
        """
        print("=" * 60)
        print("Milvus Knowledge Base Batch Upload")
        print("=" * 60)
        print(f"Source directory: {self.mineru_dir}")
        print(f"Upload API: {self.upload_api}")
        print(f"Chunk size: {self.chunk_size}")
        print(f"Chunk overlap: {self.chunk_overlap}")
        print(f"Dry run: {self.dry_run}")
        print(f"Skip existing: {self.skip_existing}")
        print("=" * 60)

        # Load JSON files
        json_files = self._load_json_files()
        self.stats["total_files"] = len(json_files)

        if not json_files:
            print("No JSON files found. Exiting.")
            return self.stats

        # Process each file
        start_time = time.time()

        for i, json_path in enumerate(json_files, 1):
            print(f"\n[{i}/{len(json_files)}] {json_path.name}")

            try:
                self.process_file(json_path)
            except Exception as e:
                print(f"  [ERROR] Error processing file: {e}")
                self.stats["failed"] += 1

            # Save tracking data periodically
            if self.skip_existing and i % 10 == 0:
                self._save_tracking_data()

        # Final save of tracking data
        if self.skip_existing:
            self._save_tracking_data()

        # Print summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("Upload Summary")
        print("=" * 60)
        print(f"Total files: {self.stats['total_files']}")
        print(f"Skipped (failed conversion): {self.stats['skipped_failed']}")
        print(f"Skipped (already uploaded): {self.stats['skipped_existing']}")
        print(f"Uploaded successfully: {self.stats['uploaded']}")
        print(f"Failed to upload: {self.stats['failed']}")
        print(f"Total chunks uploaded: {self.stats['total_chunks']}")
        print(f"Total content length: {self.stats['total_content_length']:,} characters")
        print(f"Elapsed time: {elapsed:.1f} seconds")

        if self.stats['uploaded'] > 0:
            print(f"Average time per file: {elapsed / self.stats['uploaded']:.1f} seconds")

        # Save failed files list
        if self.failed_files:
            failed_file = Path("failed_uploads.json")
            with open(failed_file, "w", encoding="utf-8") as f:
                json.dump(self.failed_files, f, indent=2, ensure_ascii=False)
            print(f"\nFailed uploads saved to: {failed_file}")

        return self.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch upload JSON files to Milvus knowledge base"
    )
    parser.add_argument(
        "--mineru-dir",
        type=str,
        default=DEFAULT_MINERU_DIR,
        help=f"Directory containing JSON files (default: {DEFAULT_MINERU_DIR})",
    )
    parser.add_argument(
        "--api",
        type=str,
        default=DEFAULT_UPLOAD_API,
        help=f"Upload API endpoint (default: {DEFAULT_UPLOAD_API})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Chunk size in characters (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Chunk overlap in characters (default: {DEFAULT_CHUNK_OVERLAP})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate upload without actually calling API",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload all files including previously uploaded ones",
    )

    args = parser.parse_args()

    # Validate directory
    if not Path(args.mineru_dir).exists():
        print(f"Error: Directory does not exist: {args.mineru_dir}")
        sys.exit(1)

    # Create uploader
    uploader = BatchUploader(
        mineru_dir=args.mineru_dir,
        upload_api=args.api,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        timeout=args.timeout,
        dry_run=args.dry_run,
        skip_existing=not args.force,
    )

    # Run upload
    stats = uploader.run()

    # Exit with error code if there were failures
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
