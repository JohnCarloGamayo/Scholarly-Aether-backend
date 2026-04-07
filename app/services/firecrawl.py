import httpx
from typing import Any

from ..config import get_settings


settings = get_settings()


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.firecrawl_api_key
        self.base_url = base_url or settings.firecrawl_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def _scrape_options(self) -> dict[str, Any]:
        return {
            # Request comprehensive outputs including images
            "formats": ["markdown", "links", "html", "screenshot"],
            "onlyMainContent": False,
            # Give pages more time to render dynamic content
            "waitFor": 5000,
            "timeout": 90000,
        }

    async def crawl(self, url: str, max_pages: int = 5, depth: int = 5) -> dict[str, Any]:
        # Use the scrape endpoint for single page with all content
        scrape_endpoint = f"{self.base_url}/v1/scrape"

        scrape_options = self._scrape_options()
        payload = {"url": url, **scrape_options}

        async with httpx.AsyncClient(timeout=240) as client:
            resp = await client.post(scrape_endpoint, json=payload, headers=self.headers)
            resp.raise_for_status()
            result = resp.json()
            
            # Wrap single page result to match expected structure
            if result.get("success") and result.get("data"):
                data = result["data"]
                # Return in format expected by crawl_job.py
                return {
                    "success": True,
                    "data": [data]  # Wrap in array for consistent processing
                }
            return result

    async def scrape(self, url: str) -> dict[str, Any]:
        scrape_endpoint = f"{self.base_url}/v1/scrape"
        scrape_options = self._scrape_options()
        payload = {"url": url, **scrape_options}
        
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(scrape_endpoint, json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
