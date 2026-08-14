#!/usr/bin/env python3
"""
generate_mod_downloads.py -- Build scripts/mod_downloads.json FROM the installed pack.

download_mods.ps1 downloads any missing jars from a {filename: url} map. Maintaining
that map by hand is the opposite of "minimal configuration", so this tool generates it
by identifying every installed jar and recording a direct download URL:

  * Modrinth  : SHA-1 -> the exact file's CDN url (no API key needed).
  * CurseForge: Murmur2 fingerprint -> file downloadUrl (needs a free key; falls back
                to the forgecdn CDN pattern, then to "SEARCH_CURSEFORGE").
  * Anything unidentified -> "SEARCH_CURSEFORGE" (present in the launcher base pack /
    manual install), which download_mods.ps1 already understands.

Reuses the identification engine in mod_version_check.py, so the two tools stay in sync.
Portable across packs via pack_env. Pure stdlib + requests.

Usage:
  python scripts/generate_mod_downloads.py           # write scripts/mod_downloads.json
  python scripts/generate_mod_downloads.py --dry-run # print summary only
  python scripts/generate_mod_downloads.py --modrinth-only
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import quote

import pack_env as env

# Reuse the tested identification engine.
try:
    import mod_version_check as mvc
except Exception as e:  # pragma: no cover
    sys.exit(f"Could not import mod_version_check.py (must sit next to this script): {e}")

# Always write next to download_mods.ps1 (the user-facing scripts/ dir), even when
# this generator lives in scripts/dev/.
OUT_PATH = os.path.join(env.MINECRAFT_DIR, "scripts", "mod_downloads.json")
SEARCH = "SEARCH_CURSEFORGE"


def modrinth_url_for(version_obj, sha1):
    """Direct CDN url of the file in this Modrinth version whose sha1 matches the
    installed jar (falls back to the primary/first file)."""
    files = version_obj.get("files") or []
    for f in files:
        if (f.get("hashes") or {}).get("sha1") == sha1:
            return f.get("url")
    for f in files:
        if f.get("primary"):
            return f.get("url")
    return files[0].get("url") if files else None


def load_existing_urls():
    """Existing real URLs from mod_downloads.json (filename -> url), skipping
    metadata keys and SEARCH_CURSEFORGE placeholders. These may be hand-curated
    (custom GitHub-release jars, direct CDN links) and must never be lost."""
    if not os.path.exists(OUT_PATH):
        return {}
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {}
    return {
        k: v for k, v in d.items()
        if not k.startswith("_") and isinstance(v, str) and v and v != SEARCH
    }


def forgecdn_url(file_id, filename):
    """Construct the public forgecdn URL for a CurseForge file id + name."""
    try:
        a = file_id // 1000
        b = file_id % 1000
        return f"https://edge.forgecdn.net/files/{a}/{b}/{quote(filename)}"
    except Exception:
        return None


def curseforge_urls(cf_http, fingerprints):
    """fingerprint -> best download url, via /v1/fingerprints (full file objects)."""
    out = {}
    for i in range(0, len(fingerprints), 100):
        chunk = fingerprints[i:i + 100]
        resp = cf_http.post(f"{mvc.CURSEFORGE_API}/fingerprints/{mvc.CF_GAME_ID}",
                            json={"fingerprints": chunk})
        if resp.status_code != 200:
            print(f"  (CurseForge fingerprint HTTP {resp.status_code} at {i})")
            time.sleep(mvc.THROTTLE_SECONDS)
            continue
        for match in resp.json().get("data", {}).get("exactMatches", []):
            fobj = match.get("file", {})
            fp = fobj.get("fileFingerprint")
            if fp is None:
                continue
            url = fobj.get("downloadUrl")
            if not url and fobj.get("id") and fobj.get("fileName"):
                url = forgecdn_url(fobj["id"], fobj["fileName"])
            out[fp] = url
        time.sleep(mvc.THROTTLE_SECONDS)
    return out


def generate(args):
    jars = env.list_jars()
    if not jars:
        sys.exit(f"No jars found in {env.MODS_DIR}")

    cf_key = None if args.modrinth_only else mvc.load_cf_key(None)
    cf_active = cf_key is not None
    info = env.pack_info()

    print(f"Generating mod_downloads.json for: {info['name']}")
    print(f"  {len(jars)} jars | Modrinth: ON | CurseForge: {'ON' if cf_active else 'OFF (no key)'}")

    # hash everything
    sha1_by_file, fp_by_file = {}, {}
    for jar in jars:
        path = os.path.join(env.MODS_DIR, jar)
        sha1_by_file[jar] = mvc.sha1_of(path)
        if cf_active:
            fp_by_file[jar] = mvc.cf_fingerprint(path)

    # Modrinth identify (reuses bulk + single-hash backfill)
    mr_http = mvc.Http()
    print("Identifying on Modrinth ...")
    mr_by_hash = mvc.modrinth_identify(mr_http, list(set(sha1_by_file.values())))

    # CurseForge identify (only if key)
    cf_by_fp = {}
    if cf_active:
        print("Identifying on CurseForge ...")
        cf_http = mvc.Http({"x-api-key": cf_key})
        cf_by_fp = curseforge_urls(cf_http, list(set(fp_by_file.values())))

    # Existing curated/previously-resolved URLs. Preserved by default so custom
    # jars (e.g. your own GitHub-release builds) are never downgraded to SEARCH.
    existing = load_existing_urls()

    result = {}
    counts = {"modrinth": 0, "curseforge": 0, "preserved": 0, "search": 0}
    for jar in jars:
        sha1 = sha1_by_file[jar]
        fresh, kind = None, None
        ver = mr_by_hash.get(sha1)
        if ver:
            u = modrinth_url_for(ver, sha1)
            if u:
                fresh, kind = u, "modrinth"
        if not fresh and cf_active:
            u = cf_by_fp.get(fp_by_file.get(jar))
            if u:
                fresh, kind = u, "curseforge"
        keep = existing.get(jar)

        if args.refresh_urls and fresh:
            url, src = fresh, kind                 # --refresh-urls: prefer fresh
        elif keep:
            url, src = keep, "preserved"           # default: keep curated/existing
        elif fresh:
            url, src = fresh, kind
        else:
            url, src = SEARCH, "search"
        counts[src] += 1
        result[jar] = url

    print(f"  Modrinth: {counts['modrinth']} | CurseForge: {counts['curseforge']} | "
          f"preserved: {counts['preserved']} | {SEARCH}: {counts['search']}")
    n_search = counts["search"]

    if args.dry_run:
        print("(dry run -- nothing written)")
        return 0

    header = {
        "_comment": (
            "AUTO-GENERATED by generate_mod_downloads.py from the installed pack. "
            "Maps jar filename -> direct download URL (or SEARCH_CURSEFORGE for jars "
            "that must come from the launcher base pack / manual install). "
            "Regenerate after adding or updating mods; do not hand-edit."
        ),
        "_generated": time.strftime("%Y-%m-%d %H:%M"),
        "_pack": info["name"],
    }
    payload = {**header, **{k: result[k] for k in sorted(result)}}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {os.path.relpath(OUT_PATH, env.MINECRAFT_DIR)} ({len(result)} entries).")
    if n_search and not cf_active:
        print("Tip: add a CurseForge API key to resolve direct URLs for the "
              f"{n_search} '{SEARCH}' jars (see scripts/.curseforge_api_key.example).")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Generate scripts/mod_downloads.json from the installed pack.")
    ap.add_argument("--dry-run", action="store_true", help="Print the summary but do not write the file.")
    ap.add_argument("--modrinth-only", action="store_true", help="Skip CurseForge even if a key is present.")
    ap.add_argument("--refresh-urls", action="store_true", help="Prefer freshly-resolved URLs over existing ones (existing entries are still preserved where nothing fresh resolves).")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return generate(args)


if __name__ == "__main__":
    sys.exit(main())
