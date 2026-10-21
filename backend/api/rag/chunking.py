"""Split page text into overlapping chunks. Each chunk keeps its page number."""
import re

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long(piece: str) -> list[str]:
    if len(piece) <= CHUNK_SIZE:
        return [piece]
    return [piece[i : i + CHUNK_SIZE] for i in range(0, len(piece), CHUNK_SIZE - CHUNK_OVERLAP)]


def chunk_page(text: str) -> list[str]:
    text = _clean(text)
    if not text:
        return []

    sentences = []
    for part in _SENTENCE_SPLIT.split(text):
        part = part.strip()
        if part:
            sentences.extend(_split_long(part))

    chunks, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > CHUNK_SIZE:
            chunks.append(current)
            overlap = current[-CHUNK_OVERLAP:]
            space = overlap.find(" ")
            current = (overlap[space + 1 :] if space != -1 else overlap) + " " + sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Return a list of {"page": int, "text": str, "index": int}."""
    result = []
    for page in pages:
        for text in chunk_page(page["text"]):
            result.append({"page": page["page"], "text": text, "index": len(result)})
    return result
