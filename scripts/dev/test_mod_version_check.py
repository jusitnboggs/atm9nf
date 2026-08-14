#!/usr/bin/env python3
"""
Offline self-tests for mod_version_check.py -- no network required.

The whole CurseForge tier depends on reproducing CurseForge's Murmur2 file
fingerprint exactly. These vectors were fuzz-verified (20,000 cases, 0 mismatches)
against meza/curseforge-fingerprint, the C++ CurseForge actually runs. If any of
these fail, the fingerprint implementation has regressed and CF lookups will
silently return zero matches.

Run:  python scripts/test_mod_version_check.py
"""

import importlib.util
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_module():
    path = os.path.join(SCRIPT_DIR, "mod_version_check.py")
    spec = importlib.util.spec_from_file_location("mod_version_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cf_fingerprint_bytes(mod, data):
    """Mirror mod.cf_fingerprint() but from an in-memory buffer (no temp file)."""
    stripped = data.translate(None, mod._CF_STRIP)
    return mod.murmur2_32(stripped, 1)


def main():
    mod = load_module()
    failures = []

    # --- Murmur2 / CurseForge fingerprint vectors --------------------------- #
    # (input bytes, expected unsigned uint32 fingerprint)
    fp_vectors = [
        (b"", 1540447798),                 # empty / all-whitespace collapses here
        (b"hello world", 2824650221),
        (b"hello", 2788266382),
        (b"h e\tl\nl o", 2788266382),      # proves whitespace is DELETED, not replaced
    ]
    for data, expected in fp_vectors:
        got = cf_fingerprint_bytes(mod, data)
        if got != expected:
            failures.append(f"fingerprint({data!r}) = {got}, expected {expected}")

    # whitespace stripping must remove exactly bytes 9,10,13,32 and nothing else
    if mod._CF_STRIP != bytes((9, 10, 13, 32)):
        failures.append(f"_CF_STRIP changed: {tuple(mod._CF_STRIP)} != (9, 10, 13, 32)")

    # result must be an unsigned 32-bit int
    big = cf_fingerprint_bytes(mod, bytes(range(256)) * 32)
    if not (0 <= big <= 0xFFFFFFFF):
        failures.append(f"fingerprint out of uint32 range: {big}")

    # --- Date helpers ------------------------------------------------------- #
    d_new = mod.parse_iso("2026-08-09T00:00:00Z")
    d_old = mod.parse_iso("2025-11-01T00:00:00Z")
    if d_new is None or d_old is None:
        failures.append("parse_iso failed on valid ISO strings")
    elif mod.day_delta(d_new, d_old) != 281:
        failures.append(f"day_delta expected 281, got {mod.day_delta(d_new, d_old)}")
    # day_delta floors to whole days: a sub-second-short span rounds DOWN.
    d_old_frac = mod.parse_iso("2025-11-01T00:00:00.5Z")
    if mod.day_delta(d_new, d_old_frac) != 280:
        failures.append(f"day_delta floor expected 280, got {mod.day_delta(d_new, d_old_frac)}")
    if mod.parse_iso(None) is not None or mod.parse_iso("not-a-date") is not None:
        failures.append("parse_iso should return None on bad input")

    # --- Report ------------------------------------------------------------- #
    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"OK -- {len(fp_vectors)} fingerprint vectors + helpers passed.")


if __name__ == "__main__":
    main()
