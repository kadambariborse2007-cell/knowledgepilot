"""Google Gemini (free tier) client."""
import time

from django.conf import settings


class LLMError(Exception):
    pass


_client = None


def _get_client():
    global _client
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set on the server.")
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _config(system: str):
    from google.genai import types

    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.1,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def _is_rate_limit(error: Exception) -> bool:
    text = str(error)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "503" in text or "UNAVAILABLE" in text


def generate(prompt: str, system: str, retries: int = 4) -> str:
    for attempt in range(retries + 1):
        try:
            response = _get_client().models.generate_content(
                model=settings.GEMINI_MODEL, contents=prompt, config=_config(system)
            )
            return (response.text or "").strip()
        except LLMError:
            raise
        except Exception as error:  # noqa: BLE001
            if _is_rate_limit(error) and attempt < retries:
                time.sleep(min(60, 8 * (attempt + 1)))
                continue
            raise LLMError(f"Gemini request failed: {error}") from error
    return ""


def stream(prompt: str, system: str):
    """Yield text pieces as Gemini generates them."""
    for attempt in range(3):
        try:
            started = False
            for chunk in _get_client().models.generate_content_stream(
                model=settings.GEMINI_MODEL, contents=prompt, config=_config(system)
            ):
                if chunk.text:
                    started = True
                    yield chunk.text
            return
        except LLMError:
            raise
        except Exception as error:  # noqa: BLE001
            if _is_rate_limit(error) and not started and attempt < 2:
                time.sleep(8 * (attempt + 1))
                continue
            raise LLMError(f"Gemini request failed: {error}") from error
