import asyncio
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from urllib.parse import urljoin

from ..db import SessionLocal
from .. import models
from ..services.firecrawl import FirecrawlClient
from ..services.pdf import summary_to_pdf


def process_crawl_job(job_id: str, user_id: str, url: str):
    db: Session = SessionLocal()
    firecrawl = FirecrawlClient()
    user_uuid = uuid.UUID(user_id)
    job_uuid = uuid.UUID(job_id)

    try:
        job = (
            db.query(models.CrawlJob)
            .filter(models.CrawlJob.id == job_uuid, models.CrawlJob.owner_id == user_uuid)
            .first()
        )
        if not job:
            print(f"Job {job_id} not found")
            return

        job.status = models.CrawlStatus.crawling
        db.commit()
        print(f"Starting crawl for {url}")

        crawl_response = asyncio.run(firecrawl.crawl(url, max_pages=5, depth=5))
        print(f"Crawl response keys: {crawl_response.keys()}")
        
        # Firecrawl v1 API returns: {"success": true, "data": {"markdown": "...", "metadata": {...}, "screenshot": "...", "links": [...], "html": "..."}}
        if not crawl_response.get("success"):
            raise ValueError(f"Firecrawl API returned success=false. Response: {crawl_response}")
        
        data = crawl_response.get("data", {})
        
        # Handle both single page and multi-page responses
        documents = []
        if isinstance(data, list):
            # Multi-page crawl returns array directly
            documents = data
        elif isinstance(data, dict):
            # Single page response
            documents = [data]
        
        print(f"Found {len(documents)} documents")
        
        markdown = ""
        screenshot = None
        metadata = {}
        html = ""
        links = []
        
        # Process all documents
        if documents:
            markdown_parts = []
            all_links = []
            
            for idx, doc in enumerate(documents, start=1):
                doc_md = doc.get("markdown", "")
                doc_html = doc.get("html", "")
                doc_links = doc.get("links", [])
                doc_metadata = doc.get("metadata", {})
                doc_screenshot = doc.get("screenshot")
                
                # Collect first screenshot
                if not screenshot and doc_screenshot:
                    screenshot = doc_screenshot
                
                # Collect metadata from first page
                if idx == 1:
                    metadata = doc_metadata
                
                # Collect all links
                all_links.extend(doc_links)
                
                # Add markdown content
                if doc_md:
                    source_url = doc_metadata.get("sourceURL") or doc_metadata.get("url") or url
                    if len(documents) > 1:
                        markdown_parts.append(f"# Source: {source_url}\n\n{doc_md}\n")
                    else:
                        markdown_parts.append(doc_md)
                    print(f"Document {idx}: {len(doc_md)} chars of markdown, {len(doc_html)} chars of HTML")
                
                # Collect HTML for fallback
                if doc_html:
                    html += doc_html + "\n\n"
            
            # Combine all markdown
            if markdown_parts:
                markdown = "\n\n---\n\n".join(markdown_parts)
            
            links = list(set(all_links))  # Deduplicate links



        # If we want to crawl additional pages, we can scrape linked pages
        # For now, focus on getting complete data from the main page
        if not markdown or len(markdown) < 200:
            print("Warning: Very little markdown content extracted")
        
        print(f"Final markdown length: {len(markdown) if markdown else 0}")
        print(f"Screenshot available: {bool(screenshot)}")
        print(f"HTML length: {len(html) if html else 0}")
        print(f"Metadata: {metadata}")
        print(f"Markdown preview (first 500 chars): {(markdown or '')[:500]}")
        
        # Count images in markdown
        import re
        image_count = len(re.findall(r'!\[.*?\]\(.*?\)', markdown)) if markdown else 0
        print(f"Images found in markdown: {image_count}")
        
        # Count headings
        heading_count = len(re.findall(r'^#+\s+.+$', markdown, re.MULTILINE)) if markdown else 0
        print(f"Headings found: {heading_count}")
        
        # Fallback: if markdown is missing or too short, try extracting readable text from HTML
        if (not markdown or len(markdown) < 500) and html:
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                text = soup.get_text("\n")
                text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                if text:
                    markdown = f"# {metadata.get('title') or url}\n\n{text}"
                    print(f"Used HTML->text fallback, new markdown length: {len(markdown)}")
            except Exception as html_exc:  # noqa: BLE001
                print(f"HTML fallback failed: {html_exc}")

        if not markdown:
            raise ValueError(f"No markdown returned from Firecrawl. Response: {crawl_response}")

        job.status = models.CrawlStatus.summarizing
        db.commit()
        print(f"Generating PDF from raw markdown with {image_count} images")

        # Use metadata title or first line as title
        page_title = metadata.get('title') or url
        first_line = next((ln.strip() for ln in (markdown or '').split('\n') if ln.strip()), '')
        title_line = (page_title or first_line or "AI Crawl").strip()[:120]

        pdf_path = summary_to_pdf(title_line or "AI Crawl", markdown, url, screenshot)
        print(f"PDF created at {pdf_path}")

        document = models.Document(
            title=title_line or "AI Crawl",
            source_url=url,
            summary=markdown,
            pdf_path=pdf_path,
            crawl_job_id=job.id,
        )
        job.status = models.CrawlStatus.completed
        job.summary = markdown
        job.pdf_path = pdf_path
        job.finished_at = datetime.utcnow()
        db.add(document)
        db.commit()
        print(f"Job {job_id} completed successfully")
    except Exception as exc:  # noqa: BLE001
        print(f"Error processing job {job_id}: {exc}")
        import traceback
        traceback.print_exc()
        
        job = (
            db.query(models.CrawlJob)
            .filter(models.CrawlJob.id == job_uuid, models.CrawlJob.owner_id == user_uuid)
            .first()
        )
        if job:
            job.status = models.CrawlStatus.failed
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
