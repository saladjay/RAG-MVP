"""
HTTP API 测试脚本

支持两种模式：
1. 基础模式：直接测试单个 completions 请求
2. Prompt 评估模式：从本地 txt 文件读取 system prompt，
   从 queries.txt 读取测试 query，批量测试 prompt 有效程度。

使用方式：
  # 基础测试
  uv run python tests/test_http_api.py

  # Prompt 评估（指定 prompt 文件）
  uv run python tests/test_http_api.py --prompt prompts/query_judge.txt

  # 指定 prompt 文件 + query 文件 + 输出文件
  uv run python tests/test_http_api.py --prompt prompts/query_judge.txt --queries queries.txt --output results/prompt_eval.json

  # 指定最大测试条数和并发数
  uv run python tests/test_http_api.py --prompt prompts/query_judge.txt --limit 50 --concurrency 5
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# ============================================================================
# 配置
# ============================================================================

BASE_URL = "http://128.23.74.3:9091"
COMPLETIONS_PATH = "/llm/Qwen3-32B-Instruct/v1/completions"
CHAT_COMPLETIONS_PATH = "/llm/Qwen3-32B-Instruct/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Basic T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo",
}
MODEL = "Qwen3-32B"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.1
DEFAULT_CONCURRENCY = 3


# ============================================================================
# 基础测试
# ============================================================================

async def test_http_api():
    """基础 HTTP API 测试"""
    url = f"{BASE_URL}{COMPLETIONS_PATH}"
    payload = {
        "prompt": "你好，请问今天天气怎么样？",
        "max_tokens": 100,
        "temperature": 0.7,
        "model": MODEL,
    }

    print(f"Testing HTTP API with httpx...")
    print(f"URL: {url}")
    print(f"Headers: {HEADERS}")
    print(f"Payload: {payload}")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=HEADERS)
            print(f"\nResponse status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            response.raise_for_status()
            data = response.json()
            print(f"\nResponse data:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            if "choices" in data:
                text = data["choices"][0].get("text", "")
                print(f"\nGenerated text: {text}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# Prompt 评估
# ============================================================================

def load_prompt_file(path: Path) -> str:
    """从 txt 文件加载 system prompt 内容"""
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    content = path.read_text(encoding="utf-8").strip()
    print(f"[加载] System prompt: {path} ({len(content)} 字符)")
    return content


def load_queries(path: Path, limit: Optional[int] = None) -> List[str]:
    """从 txt 文件加载 query 列表，每行一条"""
    if not path.exists():
        raise FileNotFoundError(f"Query 文件不存在: {path}")
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit:
        lines = lines[:limit]
    print(f"[加载] Query 文件: {path} ({len(lines)} 条)")
    return lines


def build_chat_payload(
    system_prompt: str,
    user_query: str,
    context: str = "",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    """
    构建 Dify 风格的 chat completions payload。

    参照 Dify LLM 节点结构，使用 messages 数组（非 prompts）。
    user 消息中包含当前 query 和可选的历史 context 占位符。
    """
    user_text = f"# 当前的query\n{user_query}"
    if context:
        user_text += f"\n# 历史query\n{context}"

    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def build_dify_style_payload(
    system_prompt: str,
    user_query: str,
    context: str = "",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    """
    构建 Dify 内部 LLM 节点风格的 payload（prompts 数组格式）。

    此格式完全对应 Dify 工作流中 LLM 节点的输出结构，
    适合直接模拟 Dify 节点行为进行测试。
    """
    user_text = f"# 当前的query\n{user_query}"
    if context:
        user_text += f"\n# 历史query\n{context}"

    return {
        "model_mode": "chat",
        "prompts": [
            {"role": "system", "text": system_prompt, "files": []},
            {"role": "user", "text": user_text, "files": []},
        ],
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


async def call_llm(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_query: str,
    *,
    context: str = "",
    use_dify_format: bool = False,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    """调用 LLM API 并返回结构化结果"""
    if use_dify_format:
        # Dify prompts 格式需要转换为标准 messages 格式发送给 API
        user_text = f"# 当前的query\n{user_query}"
        if context:
            user_text += f"\n# 历史query\n{context}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    else:
        payload = build_chat_payload(system_prompt, user_query, context, max_tokens, temperature)
        messages = payload["messages"]

    api_payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    url = f"{BASE_URL}{CHAT_COMPLETIONS_PATH}"
    start_time = time.time()

    try:
        response = await client.post(url, json=api_payload, headers=HEADERS)
        latency = time.time() - start_time

        response.raise_for_status()
        data = response.json()

        # 提取回复文本
        reply = ""
        if "choices" in data and data["choices"]:
            message = data["choices"][0].get("message", {})
            reply = message.get("content", "")

        # 提取 token 用量
        usage = data.get("usage", {})

        return {
            "query": user_query,
            "reply": reply,
            "status": "success",
            "latency_s": round(latency, 3),
            "usage": usage,
        }

    except httpx.HTTPStatusError as e:
        latency = time.time() - start_time
        return {
            "query": user_query,
            "reply": "",
            "status": f"http_error_{e.response.status_code}",
            "latency_s": round(latency, 3),
            "error": str(e),
        }
    except Exception as e:
        latency = time.time() - start_time
        return {
            "query": user_query,
            "reply": "",
            "status": "error",
            "latency_s": round(latency, 3),
            "error": str(e),
        }


async def run_prompt_evaluation(
    prompt_file: str,
    queries_file: str = "queries.txt",
    output_file: Optional[str] = None,
    limit: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    use_dify_format: bool = False,
    context: str = "",
):
    """
    执行 Prompt 评估流程。

    Args:
        prompt_file: System prompt 所在的 txt 文件路径
        queries_file: 测试 query 列表文件路径
        output_file: 评估结果输出 JSON 文件路径
        limit: 最大测试条数
        concurrency: 并发请求数
        max_tokens: 最大生成 token 数
        temperature: 生成温度
        use_dify_format: 是否使用 Dify 风格 payload 格式
        context: 可选的历史 context 内容（替换 {{#context#}}）
    """
    # 加载文件
    project_root = Path(__file__).parent.parent
    prompt_path = Path(prompt_file)
    if not prompt_path.is_absolute():
        prompt_path = project_root / prompt_path
    queries_path = Path(queries_file)
    if not queries_path.is_absolute():
        queries_path = project_root / queries_path

    system_prompt = load_prompt_file(prompt_path)
    queries = load_queries(queries_path, limit)

    print(f"\n{'=' * 80}")
    print("Prompt 评估模式")
    print(f"{'=' * 80}")
    print(f"  Prompt 文件:  {prompt_path}")
    print(f"  Query 文件:   {queries_path}")
    print(f"  Query 数量:   {len(queries)}")
    print(f"  并发数:       {concurrency}")
    print(f"  Max tokens:   {max_tokens}")
    print(f"  Temperature:  {temperature}")
    print(f"  Dify 格式:    {'是' if use_dify_format else '否'}")
    print(f"{'=' * 80}\n")

    # 使用信号量控制并发
    semaphore = asyncio.Semaphore(concurrency)
    results: List[Dict[str, Any]] = []
    success_count = 0
    error_count = 0
    total_latency = 0.0

    async def evaluate_one(idx: int, query: str) -> Dict[str, Any]:
        nonlocal success_count, error_count, total_latency
        async with semaphore:
            result = await call_llm(
                client,
                system_prompt,
                query,
                context=context,
                use_dify_format=use_dify_format,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            result["index"] = idx

            if result["status"] == "success":
                success_count += 1
            else:
                error_count += 1
            total_latency += result["latency_s"]

            # 实时输出进度
            status_icon = "OK" if result["status"] == "success" else "FAIL"
            latency_str = f"{result['latency_s']:.2f}s"
            reply_preview = result["reply"][:80].replace("\n", " ")
            print(f"  [{idx}/{len(queries)}] [{status_icon}] {latency_str} | {query[:40]}... -> {reply_preview}...")

            return result

    # 执行评估
    start_time = time.time()
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        tasks = [evaluate_one(i + 1, q) for i, q in enumerate(queries)]
        results = await asyncio.gather(*tasks)

    total_time = time.time() - start_time

    # 统计
    print(f"\n{'=' * 80}")
    print("评估结果汇总")
    print(f"{'=' * 80}")
    print(f"  总数:         {len(queries)}")
    print(f"  成功:         {success_count}")
    print(f"  失败:         {error_count}")
    print(f"  总耗时:       {total_time:.2f}s")
    print(f"  平均延迟:     {total_latency / len(queries):.3f}s" if queries else "")
    print(f"  QPS:          {len(queries) / total_time:.2f}" if total_time > 0 else "")

    # 构建输出
    output_data = {
        "meta": {
            "prompt_file": str(prompt_path),
            "queries_file": str(queries_path),
            "system_prompt_length": len(system_prompt),
            "total_queries": len(queries),
            "limit": limit,
            "concurrency": concurrency,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "use_dify_format": use_dify_format,
        },
        "statistics": {
            "success": success_count,
            "error": error_count,
            "total_time_s": round(total_time, 3),
            "avg_latency_s": round(total_latency / len(queries), 3) if queries else 0,
            "qps": round(len(queries) / total_time, 2) if total_time > 0 else 0,
        },
        "results": results,
    }

    # 保存结果
    if output_file:
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  结果已保存: {output_path}")
    else:
        # 默认保存到 results/ 目录
        default_dir = project_root / "results"
        default_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_path = default_dir / f"prompt_eval_{timestamp}.json"
        default_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  结果已保存: {default_path}")

    # 打印部分详细结果
    print(f"\n--- 详细结果（前 5 条）---")
    for r in results[:5]:
        print(f"\n  Query: {r['query']}")
        print(f"  状态: {r['status']} | 延迟: {r['latency_s']}s")
        if r.get("reply"):
            print(f"  回复:\n    {r['reply'][:300]}")
        if r.get("error"):
            print(f"  错误: {r['error']}")

    return output_data


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="HTTP API 测试 / Prompt 评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础测试
  python tests/test_http_api.py

  # Prompt 评估（指定 prompt 文件）
  python tests/test_http_api.py --prompt prompts/query_judge.txt

  # 完整参数
  python tests/test_http_api.py --prompt prompts/query_judge.txt --queries queries.txt --limit 50 --concurrency 5
        """,
    )

    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="System prompt 文件路径（txt 格式）。指定后进入 Prompt 评估模式。",
    )
    parser.add_argument(
        "--queries",
        type=str,
        default="queries.txt",
        help="测试 query 文件路径，每行一条（默认: queries.txt）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="评估结果输出 JSON 文件路径",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最大测试 query 条数",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"并发请求数（默认: {DEFAULT_CONCURRENCY}）",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"最大生成 token 数（默认: {DEFAULT_MAX_TOKENS}）",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"生成温度（默认: {DEFAULT_TEMPERATURE}）",
    )
    parser.add_argument(
        "--dify-format",
        action="store_true",
        help="使用 Dify 风格 payload 格式（prompts 数组）",
    )
    parser.add_argument(
        "--context",
        type=str,
        default="",
        help="附加的历史 context 内容",
    )

    args = parser.parse_args()

    if args.prompt:
        asyncio.run(
            run_prompt_evaluation(
                prompt_file=args.prompt,
                queries_file=args.queries,
                output_file=args.output,
                limit=args.limit,
                concurrency=args.concurrency,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                use_dify_format=args.dify_format,
                context=args.context,
            )
        )
    else:
        asyncio.run(test_http_api())


if __name__ == "__main__":
    main()
