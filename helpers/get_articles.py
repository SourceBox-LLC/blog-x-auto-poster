import os
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from helpers.db import init_db, upsert_article
else:
    from .db import init_db, upsert_article

BASE_URL = "https://www.sourceboxai.com"
BLOG_INDEX = f"{BASE_URL}/blog"


def get_article_links():
    """Collect all article URLs from the blog index page."""
    resp = requests.get(BLOG_INDEX, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # pick only /blog/... links, skip the index itself
        if href.startswith("/blog/") and href != "/blog":
            # strip anchors like #section
            href = href.split("#", 1)[0]
            links.add(urljoin(BASE_URL, href))

    return sorted(links)


def scrape_article(url: str) -> dict:
    """Fetch a single article page and extract title + text content."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title: usually the main h1
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else url

    # Main content: try <article>, then <main>, then fall back to <body>
    article_el = soup.find("article")
    if not article_el:
        article_el = soup.find("main")
    if not article_el:
        article_el = soup.body

    # Collect paragraphs and list items as text
    parts = []
    for tag in article_el.find_all(["p", "li"]):
        text = tag.get_text(" ", strip=True)
        if text:
            parts.append(text)

    content = "\n\n".join(parts)

    return {
        "url": url,
        "title": title,
        "content": content,
        "post": ""
    }


def main():
    init_db()
    article_links = get_article_links()
    print(f"Found {len(article_links)} article URLs")

    inserted = 0
    updated = 0
    for i, url in enumerate(article_links, 1):
        try:
            print(f"[{i}/{len(article_links)}] scraping {url}")
            article = scrape_article(url)
            print(f"  -> {article['title']}")
            result = upsert_article(article)
            if result == "inserted":
                inserted += 1
                print("  (inserted into database)")
            else:
                updated += 1
                print("  (updated existing record in database)")
            time.sleep(0.5)  # be polite
        except Exception as e:
            print(f"Error scraping {url}: {e}")

    print(f"Finished. Inserted: {inserted}, Updated: {updated}.")


if __name__ == "__main__":
    main()