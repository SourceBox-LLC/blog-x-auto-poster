## SourceBox Articles Auto-Tweeter

This project automatically promotes SourceBox AI blog posts to X (Twitter).

On each run it:

1. Scrapes the SourceBox AI blog for articles.
2. Stores/updates articles in a local SQLite database.
3. Generates a tweet for any article missing a `post` using a text model.
4. Converts the tweet into a visual-only image description.
5. Generates an image from that description with an image model.
6. Uploads the image to X and posts the tweet.
7. Records the tweet ID so it never posts the same article twice.

You can run it once on demand with `uv run main.py`, or keep it running
on a schedule inside Docker (hourly loop in the container).

---

## Architecture

- **`main.py`**
  - Entry point.
  - On startup calls `helpers.get_articles.main()` to scrape the latest
    articles from `https://www.sourceboxai.com/blog` and upsert them into
    SQLite.
  - Loads all articles from the database (`helpers.db.get_all_articles`).
  - For each article:
    - If `post` is empty: generates a tweet with GPT‑5
      (`helpers.models.run_text_model`).
    - If `image_urls` is empty: generates an image prompt from the tweet
      (`helpers.models.tweet_to_image_description`) and then an image with
      the configured image model (`helpers.models.run_image_model`).
    - If `tweet_id` is empty and there is at least one image URL: appends
      the article URL to the tweet text (while staying under 280 chars),
      uploads the image to X, posts the tweet, and stores the `tweet_id`.
  - Tracks changed articles and persists them back to SQLite via
    `helpers.db.update_article`.

- **`helpers/get_articles.py`**
  - Scrapes the blog index and individual article pages using `requests`
    and `BeautifulSoup`.
  - Extracts `url`, `title`, and `content` for each article.
  - Calls `helpers.db.init_db()` and `helpers.db.upsert_article()` to
    insert or update rows in the `articles` table.
  - Can be run directly (`uv run helpers/get_articles.py`) but is also
    invoked automatically by `main.py` at the start of each run.

- **`helpers/models.py`**
  - Centralizes Replicate model IDs:
    - `TEXT_MODEL_ID = "openai/gpt-5"`
    - `IMAGE_MODEL_ID = "google/imagen-4-fast"`
    - `MARKER_MODEL_ID = "datalab-to/marker"`
  - Provides helpers:
    - `run_text_model(prompt)` – runs the text model via `replicate.run` and
      returns a string.
    - `run_image_model(input_payload, use_file_output=False)` – runs the
      image model via `replicate.run`. When `use_file_output=True`, it
      returns file objects whose `.url` attributes are normalized into
      HTTP URLs by `main.py`.
    - `tweet_to_image_description(tweet)` – uses the text model to turn a
      tweet into a short, visual-only image description (no overlaid text,
      no UI, no watermarks) that is then passed to the image model.
    - `extract_text_from_url` / `image_has_text` – call the `marker`
      model to inspect generated images. Currently used for logging only
      (it prints a snippet of detected text but does not block tweets).

- **`helpers/tweet.py`**
  - Handles X (Twitter) OAuth 1.0a signing using credentials from `.env`.
  - Uploads images via the media upload endpoint with retry logic around
    transient SSL errors.
  - Creates tweets (v2) with optional attached media IDs.
  - Exposes `post_tweet_with_image(status_text, image_url)` which:
    - Downloads the image from `image_url`.
    - Uploads it as media to X.
    - Posts a tweet with `status_text` and the uploaded media attached.
    - Returns the tweet ID.

- **`helpers/db.py`**
  - Manages a SQLite database `sourcebox_blog.db` in the project root.
  - Schema (table `articles`):
    - `id` – INTEGER PRIMARY KEY AUTOINCREMENT
    - `url` – TEXT UNIQUE, article URL
    - `title` – TEXT, article title
    - `content` – TEXT, article body
    - `post` – TEXT, generated tweet text
    - `image_urls` – TEXT, JSON-encoded list of image URLs
    - `tweet_id` – TEXT, ID of the tweet that promoted this article
  - Functions:
    - `init_db()` – creates the table if it does not exist.
    - `upsert_article(article)` – inserts or updates a row by `url`, used
      by the scraper.
    - `get_all_articles()` – returns a list of article dicts used by
      `main.py`.
    - `update_article(article)` – writes back `post`, `image_urls`, and
      `tweet_id` (plus title/content) for a given `url`.

---

## Prerequisites

- Python tooling: this project uses **uv** and `pyproject.toml`/`uv.lock`.
  - Install uv from https://docs.astral.sh/uv/ (e.g. via their install
    script) if you have not already.
- A Replicate account and API token.
- X (Twitter) API credentials with permission to post tweets and upload
  media.
- Docker (optional) if you want the hourly scheduler in a container.

---

## Environment variables (`.env`)

Create a `.env` file in the project root (already in `.gitignore`) with:

- **Replicate**
  - `REPLICATE_API_TOKEN` – your Replicate API token.

- **Twitter / X OAuth 1.0a** (used by `helpers/tweet.py`):
  - `CONSUMER_KEY`
  - `CONSUMER_SECRET`
  - `ACCESS_TOKEN`
  - `ACCESS_TOKEN_SECRET`

- **Optional / future use** (depending on your X setup):
  - `BEARER_TOKEN`
  - `CLIENT_ID`
  - `CLIENT_SECRET`

These are loaded via `python-dotenv` (`load_dotenv()` in `main.py` and
`helpers/models.py`).

---

## Local development with uv

From the project root (`/home/sbussiso/Projects/etc/SourceBox Articles`):

1. **Sync dependencies** (if needed):

   ```bash
   uv sync
   ```

2. **Populate / refresh the SQLite database (optional)**:

   ```bash
   uv run helpers/get_articles.py
   ```

   This step is optional because `main.py` also calls
   `helpers.get_articles.main()` on startup, but running it manually is
   useful if you only want to scrape and inspect the DB.

3. **Run the full pipeline once**:

   ```bash
   uv run main.py
   ```

   On each run this will:

   - Scrape the latest articles and upsert them into SQLite.
   - Load all articles from the DB.
   - Generate missing tweets and images.
   - Append the article URL to the tweet text (without asking the model).
   - Post tweets with media to X for any article without a `tweet_id`.
   - Persist changes (`post`, `image_urls`, `tweet_id`) back to SQLite.

4. **Inspect the database (optional)**:

   ```bash
   sqlite3 sourcebox_blog.db
   .tables
   SELECT url, title, post, tweet_id FROM articles;
   ```

---

## Docker: hourly scheduler inside the container

The included `Dockerfile` builds an image that:

1. Uses `ghcr.io/astral-sh/uv:python3.10-bookworm-slim` as the base.
2. Copies `pyproject.toml`, `uv.lock`, `main.py`, and `helpers/`.
3. Runs `uv sync --frozen --no-dev` to install dependencies.
4. Runs `uv run main.py` in an infinite loop with a 1‑hour sleep between
   runs.

### Build the image

From the project root:

```bash
docker build -t sourcebox-articles .
``

### Run the scheduler container

```bash
docker run -d \
  --name sourcebox-scheduler \
  --env-file .env \
  -v "$(pwd)/sourcebox_blog.db:/app/sourcebox_blog.db" \
  sourcebox-articles
``

Notes:

- The bind mount ensures your SQLite DB lives on the host; container
  restarts wont lose state.
- The container will:
  - Immediately run `uv run main.py` once.
  - Then sleep 3600 seconds and run it again, repeating forever.

### View logs

```bash
docker logs -f sourcebox-scheduler
```

Youll see output from both the scraper and the main pipeline: article
counts, generated posts, image URLs, tweet IDs, and DB save summaries.

---

## Idempotency and re-running

The pipeline is designed to be idempotent:

- Articles are uniquely keyed by `url` in the database.
- A tweet is only generated if `post` is empty.
- Images are only generated if `image_urls` is empty.
- A tweet is only sent if `tweet_id` is empty.

Re-running `uv run main.py` or letting the Docker scheduler run hourly
will therefore only act on new or incomplete articles.

If you want to re-post for testing, you can clear specific fields in the
DB (e.g. set `tweet_id` to `NULL` for a row) and run again.

---

## Safety and limits

- Be cautious with your X API keys: `.env` is ignored by Git; do not
  commit it.
- The tweet text is trimmed to 280 characters before appending the
  article URL; if necessary the text is shortened with `...` to fit.
- Image generation and posting rely on external services (Replicate and
  X); network errors or rate limits may cause occasional failures, which
  will surface in the logs.

