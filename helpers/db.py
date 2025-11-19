import json
import sqlite3


DB_PATH = "sourcebox_blog.db"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                post TEXT,
                image_urls TEXT,
                tweet_id TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_article(article: dict) -> str:
    url = article.get("url")
    title = article.get("title", "")
    content = article.get("content", "")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("SELECT id FROM articles WHERE url = ?", (url,))
        row = cur.fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO articles (url, title, content, post, image_urls, tweet_id) VALUES (?, ?, ?, ?, ?, ?)",
                (url, title, content, article.get("post", ""), None, None),
            )
            conn.commit()
            return "inserted"
        else:
            conn.execute(
                "UPDATE articles SET title = ?, content = ? WHERE url = ?",
                (title, content, url),
            )
            conn.commit()
            return "updated"
    finally:
        conn.close()


def get_all_articles() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT url, title, content, post, image_urls, tweet_id FROM articles ORDER BY id"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    articles: list[dict] = []
    for row in rows:
        image_urls_raw = row["image_urls"]
        image_urls: list[str]
        if image_urls_raw:
            try:
                image_urls = json.loads(image_urls_raw)
            except Exception:
                image_urls = []
        else:
            image_urls = []

        articles.append(
            {
                "url": row["url"],
                "title": row["title"],
                "content": row["content"],
                "post": row["post"] or "",
                "image_urls": image_urls,
                "tweet_id": row["tweet_id"],
            }
        )

    return articles


def update_article(article: dict) -> None:
    url = article.get("url")
    if not url:
        return

    image_urls = article.get("image_urls") or []
    image_urls_json = json.dumps(image_urls)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE articles SET title = ?, content = ?, post = ?, image_urls = ?, tweet_id = ? WHERE url = ?",
            (
                article.get("title", ""),
                article.get("content", ""),
                article.get("post", ""),
                image_urls_json,
                article.get("tweet_id"),
                url,
            ),
        )
        conn.commit()
    finally:
        conn.close()
