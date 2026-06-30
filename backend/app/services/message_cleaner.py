from __future__ import annotations

import re


def clean_outbound_message(content: str, *, prefix: str) -> str:
    text = " ".join(str(content or "").split())
    if prefix:
        text = _strip_existing_prefix(text, prefix)
        text = text.lstrip("：:，,。 .")
    text = _collapse_punctuation(text)
    text = text.lstrip("：:，,。 .")
    return f"{prefix}{text}" if prefix else text


def _strip_existing_prefix(text: str, prefix: str) -> str:
    normalized = text.lstrip()
    prefix_variants = {prefix}
    if prefix.endswith(("：", ":")):
        base = prefix[:-1].rstrip()
        prefix_variants.update({f"{base}：", f"{base}:"})

    stripped = True
    while stripped:
        stripped = False
        for candidate in sorted(prefix_variants, key=len, reverse=True):
            if normalized.startswith(candidate):
                normalized = normalized[len(candidate) :].lstrip()
                stripped = True
                break
    return normalized


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
