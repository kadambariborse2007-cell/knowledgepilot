"""Heuristic prompt-injection detector for document chunks.

Chunks that look like they are trying to give instructions to an AI model are
flagged at upload time. Flagged chunks are never sent to the LLM, and the UI
shows a warning when they match a question.
"""
import re

PATTERNS = [
    (r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|any|system|the)\b.{0,30}\b(instructions?|prompts?|rules?|context|guidelines?|directions?)\b",
     "Tries to override previous instructions"),
    (r"\b(you are now|from now on,? you|act as|pretend to be|roleplay as|you must now)\b", "Tries to change the AI's role"),
    (r"\b(system prompt|system message|developer message|hidden instructions?)\b", "Mentions system/developer prompts"),
    (r"\b(reveal|print|show|output|leak|repeat)\b.{0,30}\b(system prompt|instructions|api key|secret|password|credentials)\b",
     "Tries to extract secrets or instructions"),
    (r"\b(do not|don't|never)\b.{0,20}\b(tell|inform|mention|reveal)\b.{0,20}\b(the user|anyone|the reader)\b",
     "Tries to hide information from the user"),
    (r"\b(new|updated|real)\s+instructions?\s*:", "Contains injected 'new instructions'"),
    (r"(\[/?(inst|system)\]|<\|?(system|im_start|im_end)\|?>|###\s*(system|instruction))", "Contains chat-template control tokens"),
    (r"\b(respond|reply|answer)\s+(only\s+)?with\b.{0,40}\b(regardless|no matter|whatever)\b", "Tries to force a fixed answer"),
    (r"\bjailbreak|\bDAN mode\b|\bdeveloper mode\b", "Known jailbreak phrase"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE | re.DOTALL), reason) for p, reason in PATTERNS]


def scan(text: str) -> list[str]:
    """Return a list of reasons why the text looks suspicious (empty list = clean)."""
    return [reason for pattern, reason in _COMPILED if pattern.search(text)]
