
from __future__ import annotations
import os, time

DEFAULT_MODEL = "llama-3.3-70b-versatile"   


def groq_json(system_prompt: str, user_prompt: str,
              temperature: float = 0.1, model: str = DEFAULT_MODEL,
              max_retries: int = 3) -> str:
    from groq import Groq, RateLimitError

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    system = system_prompt + "\n\nRespond with a single valid JSON object and nothing else."
    delay = 8  
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content
        except RateLimitError:
            if attempt < max_retries:
                print(f"  (rate limited, waiting {delay}s and retrying...)")
                time.sleep(delay)
                delay *= 2
                continue
            raise

def groq_text(system_prompt: str, user_prompt: str,
              temperature: float = 0.2, model: str = DEFAULT_MODEL,
              max_retries: int = 3) -> str:
    from groq import Groq, RateLimitError

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    delay = 8
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            return resp.choices[0].message.content
        except RateLimitError:
            if attempt < max_retries:
                print(f"  (rate limited, waiting {delay}s and retrying...)")
                time.sleep(delay)
                delay *= 2
                continue
            raise


VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def groq_vision(image_b64: str, prompt: str, media_type: str = "image/jpeg",
                model: str = VISION_MODEL, max_retries: int = 3) -> str:
    """Send one image + prompt to a Groq vision model; return plain text (used for OCR)."""
    from groq import Groq, RateLimitError

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    delay = 8
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                ]}],
                temperature=0,
            )
            return resp.choices[0].message.content
        except RateLimitError:
            if attempt < max_retries:
                print(f"  (rate limited, waiting {delay}s and retrying...)")
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:
            msg = str(e).lower()
            if any(s in msg for s in ("decommission", "not found", "does not exist", "no longer")):
                raise RuntimeError(
                    f"Vision model '{model}' looks unavailable on your account. "
                    "List your live models with:  curl https://api.groq.com/openai/v1/models "
                    "-H \"Authorization: Bearer $GROQ_API_KEY\"  and update VISION_MODEL in "
                    "app/groq_client.py to a current vision model."
                ) from e
            raise
