"""
External KB Query Test Script.

This script reads questions from fianl_version_qa.jsonl,
queries the external knowledge base, and saves results.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def main() -> None:
    """Main function to run external KB test."""
    from e2e_test.runners.external_kb_test import ExternalKBTestRunner

    # File paths
    questions_file = Path(__file__).parent.parent / "questions" / "fianl_version_qa.jsonl"
    output_file = Path(__file__).parent.parent / "external_kb_results.json"

    # External KB configuration
    base_url = os.getenv(
        "EXTERNAL_KB_BASE_URL",
        "http://localhost:8001"
    )

    print(f"Reading questions from: {questions_file}")
    print(f"External KB URL: {base_url}")
    print(f"Output file: {output_file}")
    print("-" * 50)

    # Create runner
    runner = ExternalKBTestRunner(
        base_url=base_url,
        comp_id="N000131",
        file_type="PublicDocDispatch",
        search_type=1,  # fulltext
        topk=10,
    )

    try:
        # Run tests
        results = await runner.run_test_file(questions_file)

        # Save results
        runner.save_results(results, output_file)

        # Print summary
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful

        print("-" * 50)
        print(f"Test Summary:")
        print(f"  Total tests: {total}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Results saved to: {output_file}")

        # Show some sample results
        if results:
            print("\nSample results:")
            for i, result in enumerate(results[:3]):
                print(f"\n{i + 1}. {result.title[:50]}...")
                print(f"   Query: {result.query}")
                print(f"   Chunks: {len(result.chunks)}")
                if result.chunks:
                    print(f"   Top chunk: {result.chunks[0].get('content', '')[:100]}...")

        sys.exit(1 if failed > 0 else 0)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
