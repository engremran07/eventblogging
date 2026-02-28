"""
Algorithmic comment moderation helpers.
"""

from __future__ import annotations

import re

URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
REPEATED_CHAR_RE = re.compile(r"(.)\1{4,}", re.IGNORECASE)
SUSPICIOUS_TERMS = {
    "buy now",
    "free money",
    "crypto giveaway",
    "casino",
    "telegram",
    "whatsapp",
    "seo service",
    "click here",
    "loan offer",
}


def evaluate_comment_risk(body: str) -> dict[str, object]:
    """
    Return a deterministic moderation score and reasons.
    Score is 0-100 where higher means more suspicious.
    """
    text = (body or "").strip()
    lowered = text.lower()
    reasons: list[str] = []
    score = 0

    url_hits = len(URL_RE.findall(lowered))
    if url_hits >= 1:
        delta = min(15 + (url_hits * 10), 40)
        score += delta
        reasons.append(f"contains_links:{url_hits}")

    matched_terms = [term for term in SUSPICIOUS_TERMS if term in lowered]
    if matched_terms:
        delta = min(10 + (len(matched_terms) * 10), 35)
        score += delta
        reasons.append(f"suspicious_terms:{','.join(sorted(matched_terms))}")

    if REPEATED_CHAR_RE.search(lowered):
        score += 12
        reasons.append("repeated_characters")

    exclamations = lowered.count("!")
    if exclamations >= 5:
        score += 8
        reasons.append(f"excessive_punctuation:{exclamations}")

    tokens = [token for token in re.split(r"\s+", lowered) if token]
    token_count = len(tokens)
    if token_count <= 2:
        score += 6
        reasons.append("very_short_message")

    alpha_chars = [ch for ch in text if ch.isalpha()]
    if alpha_chars:
        caps_ratio = sum(1 for ch in alpha_chars if ch.isupper()) / len(alpha_chars)
        if caps_ratio >= 0.7 and len(alpha_chars) >= 12:
            score += 10
            reasons.append("shouting_caps")

    unique_tokens = len(set(tokens))
    if token_count >= 8 and unique_tokens <= max(2, token_count // 4):
        score += 10
        reasons.append("token_repetition")

    score = max(0, min(int(score), 100))
    return {"score": score, "reasons": reasons}
