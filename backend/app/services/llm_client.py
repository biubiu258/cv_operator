"""OpenAI 兼容协议的 LLM 客户端。"""
import httpx


def _base(base_url: str) -> str:
    return (base_url or "").rstrip("/")


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


async def list_models(base_url: str, api_key: str) -> list:
    """拉取该平台支持的模型列表（GET {base_url}/models）。"""
    url = f"{_base(base_url)}/models"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_headers(api_key))
        resp.raise_for_status()
        data = resp.json()

    items = data.get("data", []) if isinstance(data, dict) else data
    models = []
    for it in items:
        if isinstance(it, dict) and it.get("id"):
            models.append(it["id"])
        elif isinstance(it, str):
            models.append(it)
    return sorted(models)


async def test_connection(base_url: str, api_key: str) -> tuple:
    try:
        models = await list_models(base_url, api_key)
        return True, "连接成功", models
    except Exception as e:  # noqa: BLE001
        return False, f"连接失败：{e}", []


async def chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    temperature: float = 0.6,
    max_tokens: int = None,
    json_mode: bool = False,
) -> str:
    """调用 chat/completions，返回首个候选的文本内容。"""
    url = f"{_base(base_url)}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {**_headers(api_key), "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]