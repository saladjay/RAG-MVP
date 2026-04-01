"""
Complete external KB test script for fianl_version_qa.jsonl.

This script reads questions from fianl_version_qa.jsonl,
queries the external KB service, and saves results.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def main():
    """Main function to run external KB test."""
    from rag_service.clients.external_kb_client import ExternalKBClient, ExternalKBClientConfig

    # Configuration
    questions_file = Path("questions/fianl_version_qa.jsonl")
    output_file = Path("external_kb_results.json")

    base_url = "http://128.23.77.226:6719"
    endpoint = "/cloudoa-ai/ai/file-knowledge/queryKnowledge"
    comp_id = "N000131"
    file_type = "PublicDocDispatch"
    search_type = 1
    topk = 10
    limit = 5  # Run first 5 tests for demonstration

    print(f"External KB Test Runner")
    print(f"=" * 50)
    print(f"Questions file: {questions_file}")
    print(f"Output file: {output_file}")
    print(f"Service: {base_url}{endpoint}")
    print(f"Limit: First {limit} questions")
    print("-" * 50)

    # Create client
    config = ExternalKBClientConfig(
        base_url=base_url,
        endpoint=endpoint,
        timeout=30,
        max_retries=3,
    )
    client = ExternalKBClient(config)

    # Parse questions from JSONL
    inputs = []
    with open(questions_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                title_question = data.get("title_question", "")
                answer_list = data.get("answear_list", [])

                # Split by ###
                if "###" in title_question:
                    parts = title_question.split("###", 1)
                    title = parts[0].strip()
                    query = parts[1].strip()
                else:
                    title = title_question
                    query = title_question

                inputs.append({
                    "line": line_num,
                    "title": title,
                    "query": query,
                    "expected_answers": answer_list,
                })

            except json.JSONDecodeError as e:
                print(f"[WARN] Invalid JSON on line {line_num}: {e}")

    # Limit tests
    inputs = inputs[:limit]

    print(f"Parsed {len(inputs)} test questions")

    # Run queries
    results = []
    for idx, input_data in enumerate(inputs, 1):
        print(f"\n[{idx}/{len(inputs)}] {input_data['query'][:50]}...")

        try:
            chunks = await client.query(
                query=input_data["query"],
                comp_id=comp_id,
                file_type=file_type,
                search_type=search_type,
                topk=topk,
            )

            print(f"  [OK] {len(chunks)} chunks retrieved")

            results.append({
                "title": input_data["title"],
                "query": input_data["query"],
                "expected_answers": input_data["expected_answers"],
                "chunk_count": len(chunks),
                "chunks": chunks,
                "success": True,
            })

        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append({
                "title": input_data["title"],
                "query": input_data["query"],
                "expected_answers": input_data["expected_answers"],
                "chunk_count": 0,
                "chunks": [],
                "success": False,
                "error": str(e),
            })

    # Save results
    output_data = {
        "config": {
            "base_url": base_url,
            "endpoint": endpoint,
            "comp_id": comp_id,
            "file_type": file_type,
            "search_type": search_type,
            "topk": topk,
        },
        "total_tests": len(results),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Total: {len(results)}")
    print(f"  Successful: {output_data['successful']}")
    print(f"  Failed: {output_data['failed']}")
    print(f"  Results: {output_file}")

    await client.close()

    return 1 if output_data["failed"] > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
