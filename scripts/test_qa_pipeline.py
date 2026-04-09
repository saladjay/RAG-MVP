"""
Test script to run RAG Service QA pipeline with external KB.

This script tests the first 10 queries from questions/fianl_version_qa.jsonl
using the RAG Service with external knowledge base integration.
"""

import asyncio
import json
import time
from typing import List, Dict, Any
from datetime import datetime

import httpx


# Configuration
RAG_SERVICE_URL = "http://localhost:8000"
EXTERNAL_KB_URL = "http://128.23.77.226:6719"
COMPANY_ID = "N000131"
FILE_TYPE = "PublicDocDispatch"

# First 10 queries from fianl_version_qa.jsonl
TEST_QUERIES = [
    "2025年春节放假共计几天？",
    "春节调休需上班日期是哪天？",
    "国庆中秋放假时长是几天？",
    "值班车辆牌号是什么？",
    "元旦放假是否安排调休？",
    "值班电话需保障通畅吗？",
    "2025年春节从哪天开始放假？",
    "节假日自家车要停在什么地方？",
    "值班期间手机必须24小时开机吗？",
    "清明节放假几天？",  # Assuming this is the 10th based on context
]


class RAGServiceTester:
    """Tester for RAG Service with external KB."""

    def __init__(
        self,
        base_url: str = RAG_SERVICE_URL,
        external_kb_url: str = EXTERNAL_KB_URL,
        company_id: str = COMPANY_ID,
        file_type: str = FILE_TYPE,
    ):
        """Initialize tester.

        Args:
            base_url: RAG Service base URL
            external_kb_url: External KB base URL
            company_id: Company ID for queries
            file_type: Document type filter
        """
        self.base_url = base_url
        self.external_kb_url = external_kb_url
        self.company_id = company_id
        self.file_type = file_type
        self.results = []

    async def test_external_kb_direct(self, query: str) -> Dict[str, Any]:
        """Test query against external KB directly.

        Args:
            query: Query text

        Returns:
            KB response data
        """
        url = f"{self.external_kb_url}/cloudoa-ai/ai/file-knowledge/queryKnowledge"

        payload = {
            "compId": self.company_id,
            "fileType": self.file_type,
            "query": query,
            "searchType": 1,
            "topk": 10,
        }

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "latency_ms": latency_ms,
                "chunk_count": len(data.get("data", [])),
                "chunks": data.get("data", []),
            }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms,
                "chunk_count": 0,
            }

    async def test_rag_service_qa(self, query: str) -> Dict[str, Any]:
        """Test query through RAG Service QA endpoint.

        Args:
            query: Query text

        Returns:
            QA response data
        """
        url = f"{self.base_url}/qa/query"

        payload = {
            "query": query,
            "context": {
                "company_id": self.company_id,
                "file_type": self.file_type,
            },
            "options": {
                "enable_query_rewrite": False,
                "enable_hallucination_check": False,
                "top_k": 10,
            },
        }

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Extract key fields
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            metadata = data.get("metadata", {})

            return {
                "success": True,
                "latency_ms": latency_ms,
                "answer": answer,
                "source_count": len(sources),
                "sources": sources,
                "metadata": metadata,
            }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms,
            }

    async def run_comparison_test(self, query: str) -> Dict[str, Any]:
        """Run comparison test: KB direct vs RAG Service.

        Args:
            query: Query text

        Returns:
            Comparison results
        """
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print(f"{'=' * 60}")

        # Test external KB directly
        print("\n[1/2] Testing External KB directly...")
        kb_result = await self.test_external_kb_direct(query)

        if kb_result["success"]:
            print(f"  ✓ KB returned {kb_result['chunk_count']} chunks")
            print(f"  ⏱ Latency: {kb_result['latency_ms']:.0f}ms")

            if kb_result["chunks"]:
                print(f"  Top chunk: {kb_result['chunks'][0].get('document_name', 'N/A')}")
        else:
            print(f"  ✗ KB failed: {kb_result.get('error', 'Unknown error')}")

        # Test RAG Service QA
        print("\n[2/2] Testing RAG Service QA endpoint...")
        qa_result = await self.test_rag_service_qa(query)

        if qa_result["success"]:
            print(f"  ✓ QA returned answer")
            print(f"  ⏱ Total latency: {qa_result['latency_ms']:.0f}ms")
            print(f"  📄 Sources: {qa_result['source_count']}")
            print(f"\n  💡 Answer:")
            print(f"  {qa_result['answer'][:200]}{'...' if len(qa_result['answer']) > 200 else ''}")

            # Show timing breakdown if available
            metadata = qa_result.get("metadata", {})
            if "timing" in metadata:
                timing = metadata["timing"]
                print(f"\n  ⏱ Timing breakdown:")
                print(f"    - Retrieval: {timing.get('retrieval_ms', 0):.0f}ms")
                print(f"    - Generation: {timing.get('generation_ms', 0):.0f}ms")
                if timing.get('rewrite_ms'):
                    print(f"    - Rewrite: {timing.get('rewrite_ms'):.0f}ms")
                if timing.get('verify_ms'):
                    print(f"    - Verify: {timing.get('verify_ms'):.0f}ms")

            # Show sources if available
            if qa_result["sources"]:
                print(f"\n  📚 Top sources:")
                for i, source in enumerate(qa_result["sources"][:3], 1):
                    doc_name = source.get("metadata", {}).get("doc_metadata", {}).get("doctype", "N/A")
                    score = source.get("score", 0)
                    print(f"    {i}. {doc_name} (score: {score:.2f})")
        else:
            print(f"  ✗ QA failed: {qa_result.get('error', 'Unknown error')}")

        # Compile comparison result
        return {
            "query": query,
            "kb_success": kb_result.get("success", False),
            "kb_chunk_count": kb_result.get("chunk_count", 0),
            "kb_latency_ms": kb_result.get("latency_ms", 0),
            "qa_success": qa_result.get("success", False),
            "qa_answer": qa_result.get("answer", "") if qa_result.get("success") else None,
            "qa_source_count": qa_result.get("source_count", 0),
            "qa_latency_ms": qa_result.get("latency_ms", 0),
            "qa_metadata": qa_result.get("metadata", {}),
        }

    async def run_all_tests(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Run tests for all queries.

        Args:
            queries: List of query strings

        Returns:
            List of test results
        """
        print(f"\n{'#' * 60}")
        print(f"# RAG Service QA Pipeline Test")
        print(f"{'#' * 60}")
        print(f"Date: {datetime.now().isoformat()}")
        print(f"RAG Service: {self.base_url}")
        print(f"External KB: {self.external_kb_url}")
        print(f"Company ID: {self.company_id}")
        print(f"File Type: {self.file_type}")
        print(f"Total Queries: {len(queries)}")

        results = []

        for i, query in enumerate(queries, 1):
            print(f"\n\n>>> Test {i}/{len(queries)}")
            result = await self.run_comparison_test(query)
            results.append(result)

            # Small delay between tests
            if i < len(queries):
                await asyncio.sleep(0.5)

        # Print summary
        self.print_summary(results)

        return results

    def print_summary(self, results: List[Dict[str, Any]]) -> None:
        """Print test summary.

        Args:
            results: List of test results
        """
        print(f"\n\n{'#' * 60}")
        print(f"# Test Summary")
        print(f"{'#' * 60}")

        kb_success = sum(1 for r in results if r["kb_success"])
        qa_success = sum(1 for r in results if r["qa_success"])

        avg_kb_latency = sum(r["kb_latency_ms"] for r in results if r["kb_success"]) / max(kb_success, 1)
        avg_qa_latency = sum(r["qa_latency_ms"] for r in results if r["qa_success"]) / max(qa_success, 1)

        print(f"\nExternal KB:")
        print(f"  Success: {kb_success}/{len(results)}")
        print(f"  Avg latency: {avg_kb_latency:.0f}ms")

        print(f"\nRAG Service QA:")
        print(f"  Success: {qa_success}/{len(results)}")
        print(f"  Avg latency: {avg_qa_latency:.0f}ms")

        # Detailed results table
        print(f"\n{'-' * 60}")
        print(f"{'Query':<40} {'KB':<6} {'QA':<6} {'QA Latency':<12}")
        print(f"{'-' * 60}")

        for r in results:
            query_short = r["query"][:37] + "..." if len(r["query"]) > 40 else r["query"]
            kb_status = "✓" if r["kb_success"] else "✗"
            qa_status = "✓" if r["qa_success"] else "✗"
            qa_latency = f"{r['qa_latency_ms']:.0f}ms" if r["qa_success"] else "N/A"
            print(f"{query_short:<40} {kb_status:<6} {qa_status:<6} {qa_latency:<12}")

        print(f"{'-' * 60}")

        # Save results to file
        output_file = "rag_service_qa_test_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "rag_service_url": self.base_url,
                    "external_kb_url": self.external_kb_url,
                    "company_id": self.company_id,
                    "file_type": self.file_type,
                },
                "summary": {
                    "total_tests": len(results),
                    "kb_success": kb_success,
                    "qa_success": qa_success,
                    "avg_kb_latency_ms": avg_kb_latency,
                    "avg_qa_latency_ms": avg_qa_latency,
                },
                "results": results,
            }, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Results saved to: {output_file}")


async def main():
    """Main entry point."""
    tester = RAGServiceTester()

    print("Starting RAG Service QA Pipeline Test...")
    print(f"Testing {len(TEST_QUERIES)} queries\n")

    await tester.run_all_tests(TEST_QUERIES)


if __name__ == "__main__":
    asyncio.run(main())
