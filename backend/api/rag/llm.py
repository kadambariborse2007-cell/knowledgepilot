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
    )


RETRYABLE = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "404", "NOT_FOUND")


def _is_retryable(error: Exception) -> bool:
    text = str(error)
    return any(code in text for code in RETRYABLE)


def model_names() -> list[str]:
    """Primary model first, then fallbacks (used when a model is busy or retired)."""
    names = [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS]
    return list(dict.fromkeys(name for name in names if name))


def generate(prompt: str, system: str, rounds: int = 3) -> str:
    last_error = None
    for attempt in range(rounds):
        for model in model_names():
            try:
                response = _get_client().models.generate_content(
                    model=model, contents=prompt, config=_config(system)
                )
                return (response.text or "").strip()
            except LLMError:
                raise
            except Exception as error:  # noqa: BLE001
                if not _is_retryable(error):
                    raise LLMError(f"Gemini request failed: {error}") from error
                last_error = error
        if attempt < rounds - 1:
            time.sleep(min(60, 10 * (attempt + 1)))
    raise LLMError(f"Gemini request failed: {last_error}")


def stream(prompt: str, system: str, rounds: int = 2):
    """Yield text pieces as Gemini generates them."""
    last_error = None
    for attempt in range(rounds):
        for model in model_names():
            started = False
            try:
                for chunk in _get_client().models.generate_content_stream(
                    model=model, contents=prompt, config=_config(system)
                ):
                    if chunk.text:
                        started = True
                        yield chunk.text
                return
            except LLMError:
                raise
            except Exception as error:  # noqa: BLE001
                if started or not _is_retryable(error):
                    raise LLMError(f"Gemini request failed: {error}") from error
                last_error = error
        if attempt < rounds - 1:
            time.sleep(8)
    raise LLMError(f"Gemini request failed: {last_error}")
