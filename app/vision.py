
from __future__ import annotations
import base64
import io

TRANSCRIBE_PROMPT = (
    "Transcribe the handwritten meeting notes in this image into plain text, verbatim. "
    "Preserve names, dates, numbers and the bullet/line structure. Do not summarise or add "
    "commentary — output only the transcribed text."
)


def _prep_base64(path: str, max_dim: int = 1568, max_bytes: int = 3_000_000) -> str:
    """Open any image, downscale/compress to stay well under Groq's 4MB base64 limit."""
    from PIL import Image  # ships with gradio

    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
    quality = 85
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        if len(data) <= max_bytes or quality <= 40:
            return base64.b64encode(data).decode("utf-8")
        quality -= 10


def transcribe_image(path: str, llm=None) -> str:
    """Photo path -> transcribed text. `llm(b64, prompt)` is injectable for testing."""
    b64 = _prep_base64(path)
    if llm is None:
        from .groq_client import groq_vision
        return groq_vision(b64, TRANSCRIBE_PROMPT).strip()
    return llm(b64, TRANSCRIBE_PROMPT).strip()
