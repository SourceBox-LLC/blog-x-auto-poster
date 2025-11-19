import base64
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()


def get_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required.")
    return value


CONSUMER_KEY = get_env("CONSUMER_KEY")
CONSUMER_SECRET = get_env("CONSUMER_SECRET")
ACCESS_TOKEN = get_env("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = get_env("ACCESS_TOKEN_SECRET")


def percent_encode(value):
    return quote(str(value), safe="~-._")


def build_oauth_header(method, url, consumer_key, consumer_secret, access_token, access_token_secret, extra_params=None):
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    all_params = {**oauth_params}
    if extra_params:
        all_params.update(extra_params)

    encoded_items = [(percent_encode(k), percent_encode(v)) for k, v in all_params.items()]
    encoded_items.sort()
    param_string = "&".join(f"{k}={v}" for k, v in encoded_items)

    base_string = "&".join(
        [method.upper(), percent_encode(url), percent_encode(param_string)]
    )
    signing_key = "&".join(
        [percent_encode(consumer_secret), percent_encode(access_token_secret)]
    )

    signature = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    oauth_signature = base64.b64encode(signature).decode("utf-8")

    oauth_params["oauth_signature"] = oauth_signature
    header_params = ", ".join(
        f'{k}="{percent_encode(v)}"' for k, v in oauth_params.items()
    )
    return f"OAuth {header_params}"


def upload_media(image_bytes):
    url = "https://upload.twitter.com/1.1/media/upload.json"
    method = "POST"

    media_b64 = base64.b64encode(image_bytes).decode("utf-8")
    params = {"media_data": media_b64}

    max_retries = 3
    backoff_seconds = 2

    for attempt in range(1, max_retries + 1):
        headers = {
            "Authorization": build_oauth_header(
                method=method,
                url=url,
                consumer_key=CONSUMER_KEY,
                consumer_secret=CONSUMER_SECRET,
                access_token=ACCESS_TOKEN,
                access_token_secret=ACCESS_TOKEN_SECRET,
                extra_params=params,
            ),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = requests.post(url, headers=headers, data=params, timeout=30)
            print("Media upload status:", response.status_code)
            print("Media upload body:", response.text)
            response.raise_for_status()
            data = response.json()
            return data.get("media_id_string")
        except requests.exceptions.SSLError as e:
            print(f"Media upload SSL error (attempt {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                raise
            time.sleep(backoff_seconds)


def create_tweet(status_text, media_ids=None):
    url = "https://api.twitter.com/2/tweets"
    method = "POST"

    payload = {"text": status_text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    headers = {
        "Authorization": build_oauth_header(
            method=method,
            url=url,
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
            extra_params=None,
        ),
        "Content-Type": "application/json",
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )
    print("Tweet status:", response.status_code)
    print("Tweet body:", response.text)
    response.raise_for_status()
    data = response.json()
    tweet_id = data.get("data", {}).get("id")
    return tweet_id


def post_simple_tweet():
    status_text = f"Posting a simple tweet from my Python script at {int(time.time())}."
    tweet_id = create_tweet(status_text)
    print("Tweet posted:", status_text)
    print("Tweet id:", tweet_id)


def post_tweet_with_image(status_text, image_url):
    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()
    image_bytes = resp.content
    media_id = upload_media(image_bytes)
    tweet_id = create_tweet(status_text, media_ids=[media_id])
    return tweet_id


if __name__ == "__main__":
    post_simple_tweet()
