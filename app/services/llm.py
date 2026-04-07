import httpx
from ..config import get_settings

settings = get_settings()


class LLMClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model

    async def _resolve_model(self) -> str:
        """Resolve a usable model id. If a concrete model is configured, use it; otherwise fetch the first available."""
        if self.model and self.model != "local-model":
            return self.model

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{self.base_url}/models", headers=headers)
                resp.raise_for_status()
                data = resp.json()
                models = data.get("data") or []
                if not models:
                    raise ValueError("No models returned by LLM server")
                model_id = models[0].get("id")
                if not model_id:
                    raise ValueError("LLM server returned empty model id")
                return model_id
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to resolve model from LLM server: {exc}")
            return self.model or "local-model"

    async def summarize(self, content: str, source_url: str, page_title: str = "") -> str:
        model_to_use = await self._resolve_model()
        prompt = (
            "You are an academic summarizer. Summarize the following crawled content into clear, concise bullet points. "
            "Preserve key findings, methodologies, and notable data. Provide a short title. Keep output under 400 words."
            f"\nSource: {source_url}\nContent:\n{content}"
        )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": "You write academic-ready summaries."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
            # Fallback: If LLM is not available, return the markdown content as summary
            print(f"LLM not available ({e}), using markdown as summary")
            
            # Use page title from metadata if available
            title = page_title
            
            if not title:
                # Extract title from markdown (first H1 or H2)
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip image lines
                    if line.startswith('!['):
                        continue
                    if line.startswith('# '):
                        title = line[2:].strip()
                        break
                    elif line.startswith('## ') and not title:
                        title = line[3:].strip()
                        break
            
            if not title:
                # Try to extract from URL
                from urllib.parse import urlparse
                parsed = urlparse(source_url)
                domain = parsed.netloc.replace('www.', '')
                title = f"Content from {domain}"
            
            # Truncate to first 10000 characters to keep it reasonable but comprehensive
            summary = f"# {title}\n\n{content[:10000]}"
            if len(content) > 10000:
                summary += "\n\n... (content truncated)"
            return summary

    async def answer(self, question: str, context: str) -> str:
        prompt = (
            "You are Scholarly Aether, an AI research assistant. Answer the question using ONLY the provided context. "
            "Write a detailed and structured response with these sections when applicable: "
            "Direct Answer, Key Evidence, and Practical Takeaways. "
            "Cite URLs inline when relevant. If the answer is not in context, say you don't have that information. "
            "Do not invent citations or facts. "
            "Formatting rules: plain text only, no markdown, no asterisks, no bullet symbols."\
            f"\n\nQuestion: {question}\n\nContext:\n{context}"
        )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise academic assistant that gives rich, well-explained answers grounded in provided sources."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "max_tokens": 1200,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
