"""Benchmark raw/compressed text against compact dictionary token streams."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import sys
import time
import zlib


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans  # noqa: E402
from src.storage.postgres.token_codec import (  # noqa: E402
    CorpusCodec,
    encode_delta_sequence,
)


def _files(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.rglob("*"), key=lambda value: value.as_posix())
        if path.is_file() and path.suffix.casefold() in {".txt", ".md", ".markdown"}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    raw = bytearray()
    token_surfaces: list[str] = []
    offsets: list[int] = []
    for path in _files(args.input_dir):
        payload = path.read_bytes()
        text = payload.decode("utf-8")
        base = len(raw)
        raw.extend(payload)
        for surface, start, end in tokenize_canonical_with_spans(text):
            token_surfaces.append(surface.casefold())
            offsets.extend((base + start, base + end))
    dictionary = {surface: index for index, surface in enumerate(sorted(set(token_surfaces)))}
    logical_ids = tuple(dictionary[surface] for surface in token_surfaces)
    codec = CorpusCodec.from_lexeme_ids(logical_ids)
    encoded_symbols = codec.encode(logical_ids)
    encoded_offsets = encode_delta_sequence(offsets)
    dictionary_bytes = sum(len(value.encode("utf-8")) + 4 for value in dictionary)
    # A conservative PostgreSQL heap estimate demonstrates why row-per-token is
    # an index/projection rather than a compression format. It is not claimed as
    # an exact pg_column_size measurement.
    row_projection_estimate = len(logical_ids) * (24 + 4 + 4 + 4 + 4)
    print(f"documents={len(_files(args.input_dir))}")
    print(f"tokens={len(logical_ids)}")
    print(f"unique_lexemes={len(dictionary)}")
    print(f"raw_utf8_bytes={len(raw)}")
    print(f"zlib_text_bytes={len(zlib.compress(bytes(raw), level=9))}")
    print(f"dictionary_bytes={dictionary_bytes}")
    print(f"encoded_symbol_bytes={len(encoded_symbols)}")
    print(f"encoded_offset_bytes={len(encoded_offsets)}")
    print(f"compact_total_bytes={dictionary_bytes + len(encoded_symbols) + len(encoded_offsets)}")
    print(f"row_projection_estimate_bytes={row_projection_estimate}")
    print(f"reconstruction_token_hash={hashlib.sha256(chr(0).join(token_surfaces).encode()).hexdigest()}")
    print(f"elapsed_seconds={time.perf_counter() - started:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
