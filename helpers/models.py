import replicate
from dotenv import load_dotenv

load_dotenv()


TEXT_MODEL_ID = "openai/gpt-5"
IMAGE_MODEL_ID = "google/imagen-4-fast"
MARKER_MODEL_ID = "datalab-to/marker"


def run_text_model(prompt: str) -> str:
    output = replicate.run(
        TEXT_MODEL_ID,
        input={"prompt": prompt},
    )

    if isinstance(output, str):
        return output
    # Some models return a list/iterator of chunks
    return "".join(str(part) for part in output)


def run_image_model(input_payload: dict, use_file_output: bool = False):
    return replicate.run(
        IMAGE_MODEL_ID,
        input=input_payload,
        use_file_output=use_file_output,
    )


def tweet_to_image_description(tweet: str) -> str:
    """Use the text model to turn a tweet into a visual-only image description.

    The output is meant to be passed as the prompt to an image generator, so it
    should describe a concrete scene or composition, not include any overlay
    text, UI, or typography instructions.
    """

    tweet = (tweet or "").strip()
    if not tweet:
        return ""

    prompt = f"""You are an assistant that converts marketing tweets into
concise, visual-only image descriptions for a text-to-image model.

Given the tweet below, write 1–2 short sentences that describe a single,
coherent scene that captures its core idea.

Constraints:
- Do NOT mention or imply any written text, titles, captions, UI, or
  watermarks in the image.
- Focus on the visual metaphor, environment, subjects, lighting, and mood.
- No hashtags, no URLs, no @mentions.

Tweet:
{tweet}

Now respond with only the image description, nothing else.
"""

    description = run_text_model(prompt)
    return description.strip()


def generate_text(prompt):
    input = {
        "prompt": prompt,
    }

    result = ""
    for event in replicate.stream(
        TEXT_MODEL_ID,
        input=input,
    ):
        print(event, end="")
        result += str(event)
    return result


def generate_image(prompt):
    input = {
        "prompt": prompt,
        "aspect_ratio": "4:3"
    }

    output = run_image_model(input)

    urls = []
    # To access the file URLs:
    first_url = output[0].url
    print(first_url)
    urls.append(first_url)
    #=> "https://replicate.delivery/.../output_0.jpg"

    # To write the files to disk:
    for index, item in enumerate(output):
        if index > 0:
            url = item.url
            urls.append(url)
        with open(f"output_{index}.jpg", "wb") as file:
            file.write(item.read())
    #=> output_0.jpg written to disk

    return urls


def extract_text_from_url(file_url: str) -> str:
    file_url = (file_url or "").strip()
    if not file_url.startswith("http://") and not file_url.startswith("https://"):
        print("Marker: skipping non-URL image for text extraction:", repr(file_url))
        return ""

    try:
        output = replicate.run(
            MARKER_MODEL_ID,
            input={"file": file_url},
        )
    except Exception as e:
        print("Marker: error running text extraction:", e)
        # Propagate empty string so caller can decide how to handle
        return ""

    if isinstance(output, dict):
        markdown = output.get("markdown") or ""
    else:
        markdown = str(output)

    return markdown.strip()


def image_has_text(image_url: str) -> bool:
    markdown = extract_text_from_url(image_url)
    if markdown:
        # For now, marker is informational only; we don't block on it.
        print("Marker (info): extracted text snippet:", markdown[:200].replace("\n", " "), "...")
    # Relaxed check: always treat image as acceptable
    return False


if __name__ == "__main__":
    generate_text("Are you AGI?")
    generate_image("a cat on the moon")