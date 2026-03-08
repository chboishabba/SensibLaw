"""Utilities for computing text similarity signatures."""
from __future__ import annotations

import hashlib
import re

TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    """Return a list of lowercase word tokens."""
    return TOKEN_RE.findall(text.lower())


def token_jaccard_similarity(left: str, right: str) -> float:
    """Return token-set Jaccard similarity for two texts."""
    left_tokens = set(_tokenize(left))
    right_tokens = set(_tokenize(right))
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    if not union:
        return 1.0
    return len(left_tokens & right_tokens) / len(union)


def simhash(text: str) -> str:
    """Compute a 64-bit SimHash fingerprint of the given text.

    The implementation uses token-level hashing via MD5 and aggregates bit
    weights to derive the fingerprint.
    """
    tokens = _tokenize(text)
    hashbits = 64
    v = [0] * hashbits
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(hashbits):
            bitmask = 1 << i
            if h & bitmask:
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(hashbits):
        if v[i] >= 0:
            fingerprint |= 1 << i
    return f"{fingerprint:016x}"


def simhash_hamming_distance(left_hex: str, right_hex: str) -> int:
    """Return the Hamming distance between two hex-encoded SimHash values."""
    try:
        left = int(left_hex, 16)
        right = int(right_hex, 16)
    except Exception:
        return 64
    return (left ^ right).bit_count()


def minhash(text: str, num_perm: int = 8) -> str:
    """Compute a MinHash signature for the text.

    A small number of permutations are used to produce a compact signature. The
    result is returned as a hex string.
    """
    tokens = set(_tokenize(text))
    if not tokens:
        return "0" * (num_perm * 16)
    mins: list[int] = []
    for i in range(num_perm):
        min_val: int | None = None
        for token in tokens:
            h = hashlib.sha1(f"{i}-{token}".encode("utf-8")).digest()
            val = int.from_bytes(h[:8], "big")
            if min_val is None or val < min_val:
                min_val = val
        assert min_val is not None
        mins.append(min_val)
    return "".join(f"{m:016x}" for m in mins)
