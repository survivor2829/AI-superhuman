from __future__ import annotations

import re


def clean_outbound_message(content: str, *, prefix: str) -> str:
    text = " ".join(str(content or "").split())
    if prefix:
        while text.startswith(prefix):
            text = text[len(prefix) :].lstrip()
        text = text.lstrip("：:，,。 .")
    text = _collapse_punctuation(text)
    text = text.lstrip("：:，,。 .")
    return f"{prefix}{text}" if prefix else text


def _collapse_punctuation(text: str) -> str:
    replacements = [
        (r"[，,]{2,}", "，"),
        (r"[。\.]{2,}", "。"),
        (r"[：:]{2,}", "："),
        (r"[？?]{2,}", "？"),
        (r"[！!]{2,}", "！"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s*([，。！？：])\s*", r"\1", text)
    text = text.replace("：，", "：").replace("：。", "：")
    return text
