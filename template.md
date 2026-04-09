'''
class CloudCompletionService:
    """云端文本补全服务类 - 调用远程补全API"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 60,
        auth_token: Optional[str] = None
    ):
        """初始化云端文本补全服务

        Args:
            api_url: 补全API地址
            model_name: 模型名称
            timeout: 请求超时时间(秒)
            auth_token: 认证令牌
        """
        self.api_url = api_url or settings.cloud_completion_url
        self.model_name = model_name or settings.cloud_completion_model
        self.timeout = timeout
        self.auth_token = auth_token or settings.cloud_auth_token

        if not self.api_url:
            raise ValueError("cloud_completion_url is not configured")

        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Basic {self.auth_token}"

        self._client = httpx.Client(timeout=self.timeout, headers=headers)

    def complete(
        self,
        prompt: str,
        max_tokens: int = 320,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stream: bool = False
    ) -> CompletionResult:
        """执行文本补全

        Args:
            prompt: 提示文本
            max_tokens: 最大生成token数
            temperature: 温度参数(0-2)
            top_p: 核采样参数(0-1)
            stream: 是否流式输出

        Returns:
            补全结果

        Raises:
            httpx.HTTPError: API请求失败
            ValueError: 响应格式错误
        """
        if stream:
            raise NotImplementedError("Streaming not implemented yet")

        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
            "model": self.model_name
        }

        response = self._client.post(self.api_url, json=payload)
        response.raise_for_status()
        return self._parse_completion_response(response.json())

    def _parse_completion_response(self, response: dict) -> CompletionResult:
        """解析API响应，提取补全结果

        Args:
            response: API响应JSON数据

        Returns:
            补全结果

        Raises:
            ValueError: 响应格式错误
        """
        # 支持多种响应格式
        if "choices" in response:
            # OpenAI 风格: {"choices": [{"text": "...", "finish_reason": "stop"}], "usage": {...}}
            choice = response["choices"][0]
            text = choice.get("text", choice.get("message", {}).get("content", ""))
            finish_reason = choice.get("finish_reason")
            usage = response.get("usage")
        elif "output" in response:
            # 简单格式: {"output": "文本", "finish_reason": "stop"}
            text = response["output"]
            finish_reason = response.get("finish_reason")
            usage = response.get("usage")
        elif "text" in response:
            # 最简格式: {"text": "文本"}
            text = response["text"]
            finish_reason = response.get("finish_reason")
            usage = response.get("usage")
        elif "result" in response:
            # 结果格式: {"result": "文本"}
            text = response["result"]
            finish_reason = response.get("finish_reason")
            usage = response.get("usage")
        else:
            raise ValueError(f"Unexpected response format: {response}")

        return {
            "text": text,
            "finish_reason": finish_reason,
            "usage": usage
        }

    def complete_with_retry(
        self,
        prompt: str,
        max_tokens: int = 320,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stream: bool = False,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> CompletionResult:
        """带重试机制的文本补全

        Args:
            prompt: 提示文本
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: 核采样参数
            stream: 是否流式输出
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)

        Returns:
            补全结果
        """
        import time

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self.complete(prompt, max_tokens, temperature, top_p, stream)
            except httpx.HTTPError as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(retry_delay * (2 ** attempt))
                continue
            except Exception as e:
                raise e

        raise last_error if last_error else RuntimeError("Failed to complete text")

    def complete_stream(
        self,
        prompt: str,
        max_tokens: int = 320,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Iterator[str]:
        """流式文本补全

        Args:
            prompt: 提示文本
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: 核采样参数

        Yields:
            生成的文本片段
        """
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "model": self.model_name
        }

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", self.api_url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                            yield self._parse_stream_chunk(chunk)
                        except Exception:
                            continue

    def _parse_stream_chunk(self, chunk: dict) -> str:
        """解析流式响应的数据块

        Args:
            chunk: 数据块

        Returns:
            文本片段
        """
        if "choices" in chunk:
            choice = chunk["choices"][0]
            return choice.get("text", choice.get("delta", {}).get("content", ""))
        elif "text" in chunk:
            return chunk["text"]
        return ""

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 320,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stream: bool = False
    ) -> CompletionResult:
        """对话式补全

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: 核采样参数
            stream: 是否流式输出

        Returns:
            补全结果
        """
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
            "model": self.model_name
        }

        response = self._client.post(self.api_url, json=payload)
        response.raise_for_status()
        return self._parse_completion_response(response.json())

    def close(self) -> None:
        """关闭HTTP客户端"""
        self._client.close()

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        self.close()
'''


# Cloud Services Common Configuration
CLOUD_AUTH_TOKEN=T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo

# Cloud Embedding Service Configuration
CLOUD_EMBEDDING_URL=http://128.23.74.3:9091/llm/embed-bge/v1/embeddings
CLOUD_EMBEDDING_MODEL=bge-m3
CLOUD_EMBEDDING_TIMEOUT=30

# Cloud Rerank Service Configuration
CLOUD_RERANK_URL=http://128.23.74.3:9091/llm/embed-reranker/rerank
CLOUD_RERANK_MODEL=embed_rerank
CLOUD_RERANK_TIMEOUT=30

# Cloud Completion Service Configuration
CLOUD_COMPLETION_URL=http://128.23.74.3:9091/llm/Qwen3-32B-Instruct/v1/completions
CLOUD_COMPLETION_MODEL=Qwen3-32B
CLOUD_COMPLETION_TIMEOUT=60


GLM_AUTH_TOKEN=your_basic_auth_token_here
GLM_COMPLETION_URL=https://open.bigmodel.cn/api/coding/paas/v4/chat/completions
GLM_COMPLETION_MODEL=glm-4-7
GLM_COMPLETION_TIMEOUT=60