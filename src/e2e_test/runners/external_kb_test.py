"""
External Knowledge Base Query Test Runner.

This module provides functionality to test the external knowledge base
by reading questions from a JSONL file and querying the external KB service.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from e2e_test.core.exceptions import E2ETestError
from e2e_test.core.logger import get_logger


# Module logger
logger = get_logger()


class ExternalKBTestInput:
    """Input data from JSONL file."""

    def __init__(self, title: str, query: str, answer_list: List[str]) -> None:
        """Initialize test input.

        Args:
            title: Document title.
            query: Query question.
            answer_list: List of expected answers.
        """
        self.title = title
        self.query = query
        self.answer_list = answer_list


class ExternalKBTestResult:
    """Result of a single external KB query."""

    def __init__(
        self,
        title: str,
        query: str,
        expected_answers: List[str],
        chunks: List[Dict[str, Any]],
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Initialize test result.

        Args:
            title: Document title.
            query: Query question.
            expected_answers: List of expected answers.
            chunks: Retrieved chunks from external KB.
            success: Whether query was successful.
            error: Error message if failed.
        """
        self.title = title
        self.query = query
        self.expected_answers = expected_answers
        self.chunks = chunks
        self.success = success
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the result.
        """
        return {
            "title": self.title,
            "query": self.query,
            "expected_answers": self.expected_answers,
            "chunk_count": len(self.chunks),
            "chunks": self.chunks,
            "success": self.success,
            "error": self.error,
        }


class ExternalKBTestRunner:
    """
    Runner for external knowledge base tests.

    This runner reads test data from a JSONL file, queries the external KB,
    and records results for analysis.
    """

    def __init__(
        self,
        base_url: str,
        comp_id: str = "N000131",
        file_type: str = "PublicDocDispatch",
        search_type: int = 1,
        topk: int = 10,
        endpoint: str = "/cloudoa-ai/ai/file-knowledge/queryKnowledge",
        xtoken: str = "",
    ) -> None:
        """Initialize the external KB test runner.

        Args:
            base_url: External KB service base URL.
            comp_id: Company ID for queries.
            file_type: File type filter.
            search_type: Search type (0=vector, 1=fulltext, 2=hybrid).
            topk: Number of results to retrieve.
            endpoint: API endpoint path.
            xtoken: X-Token header for authentication.
        """
        self.base_url = base_url
        self.comp_id = comp_id
        self.file_type = file_type
        self.search_type = search_type
        self.topk = topk
        self.endpoint = endpoint
        self.xtoken = xtoken
        self._client: Optional[Any] = None

    async def _get_client(self) -> Any:
        """Get or create external KB client.

        Returns:
            External KB client instance.
        """
        if self._client is None:
            from rag_service.clients.external_kb_client import ExternalKBClient, ExternalKBClientConfig

            config = ExternalKBClientConfig(
                base_url=self.base_url,
                endpoint=self.endpoint,
                xtoken=self.xtoken,
                timeout=30,
                max_retries=3,
            )
            self._client = ExternalKBClient(config)
        return self._client

    async def close(self) -> None:
        """Close the external KB client."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    @staticmethod
    def parse_jsonl(file_path: Path) -> List[ExternalKBTestInput]:
        """Parse JSONL test file.

        Args:
            file_path: Path to JSONL file.

        Returns:
            List of test inputs.

        Raises:
            E2ETestError: If file cannot be parsed.
        """
        inputs = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        title_question = data.get("title_question", "")
                        answer_list = data.get("answear_list", [])

                        # Split title_question by ###
                        if "###" in title_question:
                            parts = title_question.split("###", 1)
                            title = parts[0].strip()
                            query = parts[1].strip()
                        else:
                            title = title_question
                            query = title_question

                        inputs.append(ExternalKBTestInput(
                            title=title,
                            query=query,
                            answer_list=answer_list,
                        ))

                    except json.JSONDecodeError as e:
                        raise E2ETestError(
                            message=f"Invalid JSON on line {line_num}",
                            details={"error": str(e)},
                        )

            logger.info(f"Parsed {len(inputs)} test inputs from {file_path}")
            return inputs

        except E2ETestError:
            # Re-raise E2ETestError as-is
            raise
        except FileNotFoundError:
            raise E2ETestError(
                message=f"File not found: {file_path}",
            )
        except Exception as e:
            raise E2ETestError(
                message=f"Error reading file: {file_path}",
                details={"error": str(e)},
            )

    async def query_external_kb(self, query: str, mock: bool = False) -> List[Dict[str, Any]]:
        """Query the external knowledge base.

        Args:
            query: Search query.
            mock: If True, return mock data instead of calling real service.

        Returns:
            List of retrieved chunks.

        Raises:
            E2ETestError: If query fails.
        """
        if mock:
            # Return mock data
            return [
                {
                    "id": f"mock_chunk_{i}",
                    "chunk_id": f"mock_chunk_{i}",
                    "content": f"Mock content for query: {query} (chunk {i})",
                    "metadata": {
                        "title": "Mock Document",
                        "document_name": "mock_document.txt",
                        "score": 0.95 - (i * 0.05),
                        "position": i + 1,
                        "doc_metadata": {},
                    },
                    "score": 0.95 - (i * 0.05),
                    "source_doc": "mock_document.txt",
                }
                for i in range(min(self.topk, 5))
            ]

        client = await self._get_client()

        try:
            chunks = await client.query(
                query=query,
                comp_id=self.comp_id,
                file_type=self.file_type,
                search_type=self.search_type,
                topk=self.topk,
            )
            return chunks

        except Exception as e:
            logger.error(f"External KB query failed: {e}", exc_info=True)
            raise E2ETestError(
                message=f"Query failed for: {query}",
                details={"error": str(e)},
            )

    async def run_test_file(self, file_path: Path, mock: bool = False, limit: int = 0) -> List[ExternalKBTestResult]:
        """Run all tests from a JSONL file.

        Args:
            file_path: Path to JSONL test file.
            mock: If True, use mock data instead of calling real service.
            limit: Maximum number of tests to run (0 = all).

        Returns:
            List of test results.
        """
        inputs = self.parse_jsonl(file_path)
        if limit > 0:
            inputs = inputs[:limit]

        results = []

        for idx, input_data in enumerate(inputs, 1):
            logger.info(f"Processing test {idx}/{len(inputs)}: {input_data.query[:50]}...")

            try:
                chunks = await self.query_external_kb(input_data.query, mock=mock)

                result = ExternalKBTestResult(
                    title=input_data.title,
                    query=input_data.query,
                    expected_answers=input_data.answer_list,
                    chunks=chunks,
                    success=True,
                )
                results.append(result)

                logger.info(f"Test {idx} successful: {len(chunks)} chunks retrieved")

            except Exception as e:
                result = ExternalKBTestResult(
                    title=input_data.title,
                    query=input_data.query,
                    expected_answers=input_data.answer_list,
                    chunks=[],
                    success=False,
                    error=str(e),
                )
                results.append(result)

                logger.warning(f"Test {idx} failed: {e}")

        return results

    def save_results(self, results: List[ExternalKBTestResult], output_path: Path) -> None:
        """Save test results to JSON file.

        Args:
            results: List of test results.
            output_path: Path to output file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "total_tests": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "results": [r.to_dict() for r in results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Results saved to: {output_path}")


async def run_external_kb_test(
    file_path: Path,
    base_url: str,
    output_path: Optional[Path] = None,
    comp_id: str = "N000131",
    file_type: str = "PublicDocDispatch",
    search_type: int = 1,
    topk: int = 10,
    endpoint: str = "/cloudoa-ai/ai/file-knowledge/queryKnowledge",
    xtoken: str = "",
    mock: bool = False,
    limit: int = 0,
) -> List[ExternalKBTestResult]:
    """Run external KB test from file.

    Args:
        file_path: Path to JSONL test file.
        base_url: External KB service base URL.
        output_path: Optional path to save results.
        comp_id: Company ID for queries.
        file_type: File type filter.
        search_type: Search type (0=vector, 1=fulltext, 2=hybrid).
        topk: Number of results to retrieve.
        endpoint: API endpoint path.
        xtoken: X-Token header for authentication.
        mock: If True, use mock data instead of calling real service.
        limit: Maximum number of tests to run (0 = all).

    Returns:
        List of test results.
    """
    runner = ExternalKBTestRunner(
        base_url=base_url,
        comp_id=comp_id,
        file_type=file_type,
        search_type=search_type,
        topk=topk,
        endpoint=endpoint,
        xtoken=xtoken,
    )

    try:
        results = await runner.run_test_file(file_path, mock=mock, limit=limit)

        if output_path:
            runner.save_results(results, output_path)

        return results

    finally:
        await runner.close()
