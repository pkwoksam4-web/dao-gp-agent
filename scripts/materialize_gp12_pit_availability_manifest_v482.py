from __future__ import annotations

import base64
import gzip
import hashlib
import json
import pathlib


EXPECTED_B64_SHA256 = 'ff82d254f00f7875a284040b538107ddb5b4b334cbd60bfbe46f8d8f61d6773c'
EXPECTED_JSON_SHA256 = '0e56d465039c2d374b1cd50e8aea6a7cc69d829485efe19d2020b3d8ae436125'
EXPECTED_CHUNK_N = 11
EXPECTED_COUNTS = {'nominal_events': 2732, 'standard_overrides': 270, 'special_overrides': 11}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def materialize(root: pathlib.Path) -> pathlib.Path:
    chunk_dir = root / 'data' / 'gp12_pit_event_availability_v482_chunks'
    chunks = sorted(chunk_dir.glob('part*.b64'))
    if len(chunks) != EXPECTED_CHUNK_N:
        raise ValueError(f'expected {EXPECTED_CHUNK_N} manifest chunks; found={len(chunks)}')
    encoded = b''.join(p.read_bytes() for p in chunks)
    if sha256(encoded) != EXPECTED_B64_SHA256:
        raise ValueError('PIT availability base64 payload SHA256 mismatch')
    try:
        raw = gzip.decompress(base64.b64decode(encoded, validate=True))
    except Exception as exc:
        raise ValueError('PIT availability payload decode failed') from exc
    if sha256(raw) != EXPECTED_JSON_SHA256:
        raise ValueError('PIT availability JSON SHA256 mismatch')
    x = json.loads(raw.decode('utf-8'))
    for key, expected in EXPECTED_COUNTS.items():
        if len(x.get(key) or []) != expected:
            raise ValueError(f'{key} count mismatch')
    out = root / 'data' / 'GP12_PIT_EVENT_AVAILABILITY_V482.json'
    out.write_bytes(raw)
    print(json.dumps({
        'output': str(out),
        'json_sha256': EXPECTED_JSON_SHA256,
        'counts': EXPECTED_COUNTS,
    }, ensure_ascii=False))
    return out


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    materialize(root)


if __name__ == '__main__':
    main()
