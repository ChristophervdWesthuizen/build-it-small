"""Read a document with a Claude model and return JSON that matches a schema.

Text documents are sent as text (pulled out of the PDF for free first). Images are sent as images.
Every call reports its tokens and cost, so the bench can price the whole run.
"""
import base64
import json
import time
from pathlib import Path

import anthropic

from .prices import cost

_client = None


def client():
    global _client
    if _client is None:
        from .setup import load_key
        key = load_key()  # the bench's own key file first (python -m bis.setup)
        _client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return _client


def read(model, system, schema, text=None, image_path=None, effort="low", max_tokens=4000):
    """Returns (data or None, info). info has tokens, cost, seconds, stop_reason, error."""
    content = []
    if image_path:
        data = base64.standard_b64encode(Path(image_path).read_bytes()).decode()
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
        content.append({"type": "text", "text": "Read this invoice."})
    else:
        content.append({"type": "text", "text": "Read this invoice. Its text, pulled from the PDF:\n\n" + text})
    t0 = time.time()
    info = {"model": model, "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "error": None}
    try:
        resp = client().messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.RateLimitError as e:
        info["error"] = f"rate limited: {e}"
        return None, info | {"seconds": time.time() - t0}
    except anthropic.APIStatusError as e:
        info["error"] = f"API {e.status_code}: {e.message}"
        return None, info | {"seconds": time.time() - t0}
    except anthropic.APIConnectionError as e:
        info["error"] = f"connection: {e}"
        return None, info | {"seconds": time.time() - t0}
    u = resp.usage
    info.update(input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                cost=cost(model, u.input_tokens, u.output_tokens), seconds=time.time() - t0,
                stop_reason=resp.stop_reason)
    if resp.stop_reason != "end_turn":
        info["error"] = f"stopped: {resp.stop_reason}"
        return None, info
    text_out = next((b.text for b in resp.content if b.type == "text"), None)
    try:
        return json.loads(text_out), info
    except (TypeError, json.JSONDecodeError):
        info["error"] = "output was not valid JSON"
        return None, info
