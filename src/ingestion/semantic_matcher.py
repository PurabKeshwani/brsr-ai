"""
Semantic Context Matcher — generalizes family classification to wording
variants not seen before, without hand-writing a new regex every time.

Runs strictly as a FALLBACK, after both confirmed_aliases.json (exact,
human-reviewed) and regex context_patterns (exact, hand-verified) have
already been tried and found nothing — see field_mapper.py's map_row().
Never touches numeric values, only proposes which schema FAMILY a context
string belongs to.

Model: sentence-transformers 'all-MiniLM-L6-v2' — small (~80MB, one-time
download), runs fully locally on CPU, no API key, no per-call cost, no
rate limits.

Confidence thresholds (HIGH_CONFIDENCE, REVIEW_THRESHOLD below) are
starting points, NOT proven-correct values — calibrate them by running
against Glenmark/Aequs data and checking that known-good contexts score
above HIGH_CONFIDENCE for the right family, and genuine noise (letterhead
text, addresses) scores below REVIEW_THRESHOLD.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

REGISTRY_PATH = Path(__file__).parent / "schema_registry.json"

HIGH_CONFIDENCE = 0.80   # >= this: auto-accept, treated like a regex match
REVIEW_THRESHOLD = 0.55  # >= this (but below HIGH): queue for human review
                          # below this: plain unmapped, no candidate shown

_model = None
_family_embeddings: Optional[list] = None  # [(family_id, phrase, embedding), ...]


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _load_canonical_embeddings():
    global _family_embeddings
    if _family_embeddings is not None:
        return _family_embeddings

    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    pairs = []
    for family in data["families"]:
        for phrase in family.get("canonical_phrases", []):
            pairs.append((family["family_id"], phrase))

    if not pairs:
        _family_embeddings = []
        return _family_embeddings

    model = _get_model()
    phrases = [p[1] for p in pairs]
    embeddings = model.encode(phrases, convert_to_numpy=True, normalize_embeddings=True)
    _family_embeddings = [(pairs[i][0], pairs[i][1], embeddings[i]) for i in range(len(pairs))]
    return _family_embeddings


def match_context(context: str) -> tuple[Optional[str], float]:
    """Returns (best_matching_family_id, cosine_similarity_score).
    Returns (None, 0.0) for empty context or if the registry has no
    canonical phrases loaded yet (run add_canonical_phrases.py first).
    """
    if not context or not context.strip():
        return None, 0.0

    pairs = _load_canonical_embeddings()
    if not pairs:
        return None, 0.0

    import numpy as np

    model = _get_model()
    query_emb = model.encode([context], convert_to_numpy=True, normalize_embeddings=True)[0]

    best_family, best_score = None, -1.0
    for family_id, _phrase, emb in pairs:
        score = float(np.dot(query_emb, emb))  # cosine similarity (both normalized)
        if score > best_score:
            best_score = score
            best_family = family_id

    return best_family, best_score