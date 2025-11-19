from dotenv import load_dotenv
from helpers.tweet import post_tweet_with_image
from helpers.models import (
    image_has_text,
    run_text_model,
    run_image_model,
    tweet_to_image_description,
)
from helpers.db import init_db, get_all_articles, update_article
from helpers.get_articles import main as refresh_articles_from_web


load_dotenv()


def generate_post_for_article(article):
    title = article.get("title", "").strip()
    content = article.get("content", "").strip()
    url = article.get("url", "").strip()

    prompt = f"""You are a marketing copywriter for SourceBox AI.

Write a single X (Twitter) post promoting the blog article below.

Constraints:
- One tweet only (no thread)
- Maximum 280 characters
- Strong hook, concise value
- Up to 2 emojis
- No hashtags, no @mentions
- Do NOT include any URLs or links of any kind.

Title: {title}

Article content:
{content}

Now write just the tweet text, nothing else.
"""

    text = run_text_model(prompt)

    # Normalize whitespace and hard-limit to 280 chars
    text = " ".join(text.split())
    if len(text) > 280:
        text = text[:277] + "..."

    return text


def generate_image_for_post(post_text):
    # First, convert the tweet into a dedicated image description so the
    # image model gets a clean visual prompt instead of the full tweet.
    image_description = tweet_to_image_description(post_text) or post_text

    prompt = (
        f"""
        No text, no words just a visual representation of:
        {image_description}\n\n
        """
    )

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        input_payload = {
            "prompt": prompt,
            "aspect_ratio": "4:3",
        }

        # Ask Replicate to give us file outputs so we can get stable URLs
        output = run_image_model(input_payload, use_file_output=True)

        urls = []
        # Normalize different possible output shapes into a list of HTTP URLs
        items = output if isinstance(output, (list, tuple)) else [output]
        for item in items:
            url = getattr(item, "url", None)
            if url is None:
                # Fall back to string if needed
                url = str(item)
            if isinstance(url, bytes):
                try:
                    url = url.decode("utf-8", errors="ignore")
                except Exception:
                    continue
            url = url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                urls.append(url)

        if not urls:
            print("No image URLs returned from image model.")
        else:
            first_url = urls[0]
            if not image_has_text(first_url):
                return urls
            print(f"Image attempt {attempt} appears to contain text, regenerating...")

    print("Warning: Could not obtain a text-free image after multiple attempts.")
    return []


def main():
    print("Refreshing articles from web (helpers.get_articles)...")
    refresh_articles_from_web()

    init_db()
    print("Loading articles from SQLite database...")
    articles = get_all_articles()
    print(f"Loaded {len(articles)} article(s) from database.")

    updated_posts = 0
    updated_images = 0
    posted_tweets = 0
    changed_urls = set()
    changed_articles = []

    for article in articles:
        if not article.get("post"):
            post_text = generate_post_for_article(article)
            article["post"] = post_text
            updated_posts += 1
            url_key = article.get("url")
            if url_key and url_key not in changed_urls:
                changed_urls.add(url_key)
                changed_articles.append(article)
            print("Generated post for:", article.get("title"))
            print(post_text)
            print("-" * 80)

        if article.get("post") and not article.get("image_urls"):
            image_urls = generate_image_for_post(article["post"])
            if image_urls:
                article["image_urls"] = image_urls
                updated_images += 1
                url_key = article.get("url")
                if url_key and url_key not in changed_urls:
                    changed_urls.add(url_key)
                    changed_articles.append(article)
                print("Generated image(s) for:", article.get("title"))
                print("First image URL:", image_urls[0])
            else:
                print("Skipping images for article (could not get text-free image):", article.get("title"))
            print("-" * 80)

        if article.get("post") and article.get("image_urls") and not article.get("tweet_id"):
            url = (article.get("url") or "").strip()
            tweet_text = article["post"]

            if url:
                max_len = 280
                sep = " "
                # If adding the URL would exceed the limit, trim the text portion.
                if len(tweet_text) + len(sep) + len(url) > max_len:
                    allowed = max_len - len(sep) - len(url)
                    if allowed > 3:
                        tweet_text = tweet_text[: allowed - 3] + "..."
                    elif allowed > 0:
                        tweet_text = tweet_text[:allowed]
                    else:
                        tweet_text = ""

                if tweet_text:
                    tweet_text = f"{tweet_text}{sep}{url}"
                else:
                    tweet_text = url

            tweet_id = post_tweet_with_image(tweet_text, article["image_urls"][0])
            article["tweet_id"] = tweet_id
            posted_tweets += 1
            url_key = article.get("url")
            if url_key and url_key not in changed_urls:
                changed_urls.add(url_key)
                changed_articles.append(article)
            print("Tweeted article:", article.get("title"))
            if tweet_id:
                print("Tweet ID:", tweet_id)
            print("-" * 80)

    if changed_articles:
        print(f"Saving {len(changed_articles)} modified article(s) to database...")
        for article in changed_articles:
            update_article(article)
        print("Database save complete.")
    else:
        print("No article changes to save.")

    print(f"Articles with new posts: {updated_posts}")
    print(f"Articles with new images: {updated_images}")
    print(f"Articles tweeted: {posted_tweets}")


if __name__ == "__main__":
    main()