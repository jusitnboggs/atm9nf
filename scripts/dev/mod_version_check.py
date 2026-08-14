#!/usr/bin/env python3
"""
mod_version_check.py -- Cross-platform mod version reconciliation for ATM9-NF (FUG fork).

THE PROBLEM
-----------
Mod authors frequently push an update to CurseForge (or vice versa) without
backfilling the other platform. If you only ever look at one platform's version
list, you can silently sit on a stale build for weeks. This tool checks BOTH
platforms for every installed jar and flags where they disagree, or where a newer
compatible build exists on either one.

HOW IT IDENTIFIES MODS
----------------------
Filenames do not map reliably to project IDs, so identity is resolved by file
hash -- the only trustworthy cross-platform key:
  * Modrinth   : SHA-1            -> POST /v2/version_files      (no API key)
  * CurseForge : Murmur2 finger.  -> POST /v1/fingerprints       (needs API key)

TIERS
-----
  * Modrinth tier always runs (no key required; the repo already whitelists
    api.modrinth.com).
  * CurseForge tier runs only when an API key is present, read from either the
    CURSEFORGE_API_KEY environment variable or a scripts/.curseforge_api_key file
    (both gitignored). Without a key the CF tier is skipped with a clear notice and
    Modrinth-only results are still produced. See scripts/.curseforge_api_key.example.

OUTPUTS (mirrors emc_audit.py conventions -- written to docs/, which is gitignored)
  docs/mod_version_report_YYYYMMDD_HHMMSS.md   timestamped run report
  docs/MOD_VERSION_STATUS.md                   stable "latest" pointer
  docs/mod_version_status.json                 machine-readable per-mod status

USAGE
  python scripts/mod_version_check.py                 # full check (both tiers if key)
  python scripts/mod_version_check.py --modrinth-only # skip CurseForge
  python scripts/mod_version_check.py --refresh       # ignore identity cache
  python scripts/mod_version_check.py --fail-on-stale # exit 1 if anything is stale (CI)

Pure stdlib + requests. Python 3.10+.
"""

import argparse
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("This tool requires the 'requests' package.  Install it with:  pip install requests")

import hashlib

try:
    import pack_env as env   # shared pack auto-detection (same scripts/ dir)
except Exception:
    env = None

# --------------------------------------------------------------------------- #
# Paths (resolved relative to this script inside minecraft/scripts/)
# --------------------------------------------------------------------------- #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Anchor to the real minecraft dir via pack_env (works from scripts/ or scripts/dev/).
MINECRAFT_DIR = env.MINECRAFT_DIR if env else os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DEFAULT_MODS_DIR = env.MODS_DIR if env else os.path.join(MINECRAFT_DIR, "mods")
DOCS_DIR = env.DOCS_DIR if env else os.path.join(MINECRAFT_DIR, "docs")
CACHE_PATH = os.path.join(SCRIPT_DIR, ".mod_check_cache.json")   # dev-local (gitignored)
CF_KEY_FILE = os.path.join(SCRIPT_DIR, ".curseforge_api_key")    # dev-local (gitignored)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
# Defaults; auto-detected from the pack (mmc-pack.json) at startup, overridable
# with --mc / --loader.
MC_VERSION = "1.20.1"
LOADER = "forge"

MODRINTH_API = "https://api.modrinth.com/v2"
CURSEFORGE_API = "https://api.curseforge.com/v1"
CF_GAME_ID = 432                 # Minecraft
CF_MODLOADER_FORGE = 1           # CurseForge modLoaderType enum: 1 = Forge
CF_CLASS_MOD = 6                 # CurseForge classId for "Mc Mods" (used by search)
# loader name -> CurseForge modLoaderType enum
CF_MODLOADER_BY_LOADER = {"forge": 1, "cauldron": 2, "liteloader": 3, "fabric": 4, "quilt": 5, "neoforge": 6}
CF_MODLOADER_TYPE = CF_MODLOADER_FORGE   # set from the detected loader in main()

USER_AGENT = "atm9nf-devtools/1.0 (github.com/jusitnboggs/atm9nf; mod version reconciliation)"

MODRINTH_BULK_CHUNK = 100        # hashes per bulk request (smaller = fewer dropped matches)
THROTTLE_SECONDS = 0.21          # ~4.7 req/s, under Modrinth's 300/min per-IP limit
DRIFT_DAYS_DEFAULT = 3           # min gap between platforms' newest builds to call it drift
CACHE_VERSION = 2                # bump to invalidate on-disk identity cache format

# Prefer stable releases when picking "newest available". Set False (via
# --include-prereleases) to let beta/alpha builds count as the latest.
STABLE_ONLY = True

# Status codes
ST_UP_TO_DATE = "UP_TO_DATE"
ST_UPDATE = "UPDATE_AVAILABLE"
ST_DRIFT = "PLATFORM_DRIFT"
ST_SINGLE = "SINGLE_PLATFORM"
ST_UNIDENTIFIED = "UNIDENTIFIED"
ST_PARTIAL = "PARTIAL"           # only one tier ran; cross-platform view incomplete


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def murmur2_32(data, seed):
    """MurmurHash2 (32-bit, x86) -- the variant CurseForge uses for fingerprints."""
    m = 0x5BD1E995
    r = 24
    length = len(data)
    h = (seed ^ length) & 0xFFFFFFFF
    i = 0
    while length >= 4:
        k = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)
        k = (k * m) & 0xFFFFFFFF
        k ^= k >> r
        k = (k * m) & 0xFFFFFFFF
        h = (h * m) & 0xFFFFFFFF
        h ^= k
        i += 4
        length -= 4
    if length == 3:
        h ^= data[i + 2] << 16
        h ^= data[i + 1] << 8
        h ^= data[i]
        h = (h * m) & 0xFFFFFFFF
    elif length == 2:
        h ^= data[i + 1] << 8
        h ^= data[i]
        h = (h * m) & 0xFFFFFFFF
    elif length == 1:
        h ^= data[i]
        h = (h * m) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * m) & 0xFFFFFFFF
    h ^= h >> 15
    return h & 0xFFFFFFFF


# CurseForge strips these whitespace bytes from the file BEFORE hashing.
_CF_STRIP = bytes((9, 10, 13, 32))
_CF_STRIP_TABLE = bytes(b for b in range(256) if b not in _CF_STRIP)


def cf_fingerprint(path):
    """CurseForge file fingerprint: murmur2(seed=1) over the file with whitespace
    bytes (tab, LF, CR, space) removed."""
    with open(path, "rb") as f:
        raw = f.read()
    normalized = raw.translate(None, _CF_STRIP)
    return murmur2_32(normalized, 1)


def read_modinfo(path):
    """Best-effort extraction of (modid, display_name) from a Forge/NeoForge jar's
    META-INF/mods.toml. Used for nicer display names and slug-based cross-linking."""
    modid, name = None, None
    try:
        with zipfile.ZipFile(path) as z:
            toml = None
            for candidate in ("META-INF/mods.toml", "META-INF/neoforge.mods.toml"):
                if candidate in z.namelist():
                    toml = z.read(candidate).decode("utf-8", "replace")
                    break
            if toml:
                # first [[mods]] block wins
                block = toml.split("[[mods]]", 1)[-1]
                m = re.search(r'modId\s*=\s*"([^"]+)"', block)
                if m:
                    modid = m.group(1)
                n = re.search(r'displayName\s*=\s*"([^"]+)"', block)
                if n:
                    name = n.group(1)
    except Exception:
        pass
    return modid, name


# --------------------------------------------------------------------------- #
# Cache (maps a file signature -> its stable identity so reruns skip re-hashing
# and re-fingerprinting; "latest available" is always fetched live).
# --------------------------------------------------------------------------- #
def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {"version": CACHE_VERSION, "files": {}}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CACHE_VERSION:
            return {"version": CACHE_VERSION, "files": {}}
        return data
    except Exception:
        return {"version": CACHE_VERSION, "files": {}}


def save_cache(cache):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"  (warning: could not write cache: {e})")


def file_sig(path):
    st = os.stat(path)
    return f"{int(st.st_mtime)}:{st.st_size}"


# --------------------------------------------------------------------------- #
# HTTP helper with basic retry/backoff and 429 handling
# --------------------------------------------------------------------------- #
class Http:
    def __init__(self, extra_headers=None):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        if extra_headers:
            self.s.headers.update(extra_headers)

    def _request(self, method, url, **kw):
        kw.setdefault("timeout", 30)
        for attempt in range(5):
            try:
                resp = self.s.request(method, url, **kw)
            except requests.RequestException as e:
                if attempt == 4:
                    raise
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 5))
                time.sleep(min(wait, 30) + 0.5)
                continue
            if 500 <= resp.status_code < 600:
                if attempt == 4:
                    return resp
                time.sleep(1.5 * (attempt + 1))
                continue
            return resp
        return resp

    def get(self, url, **kw):
        return self._request("GET", url, **kw)

    def post(self, url, **kw):
        return self._request("POST", url, **kw)


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #
def parse_iso(s):
    """Tolerant ISO-8601 parser. Python 3.10's datetime.fromisoformat only accepts
    exactly 3 or 6 fractional-second digits, but the platforms return varying
    precision (and a trailing 'Z'), so normalize the fractional part to 6 digits
    first. The only '.' in an ISO timestamp is the fractional seconds."""
    if not s:
        return None
    try:
        s = s.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        m = re.search(r"\.(\d+)", s)
        if m:
            frac = (m.group(1) + "000000")[:6]
            s = s[:m.start()] + "." + frac + s[m.end():]
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def day_delta(newer, older):
    if not newer or not older:
        return None
    return int((newer - older).total_seconds() // 86400)


def fmt_date(dt):
    return dt.strftime("%Y-%m-%d") if dt else "?"


# --------------------------------------------------------------------------- #
# Modrinth tier
# --------------------------------------------------------------------------- #
def modrinth_identify(http, sha1_list):
    """Identify installed files on Modrinth by SHA-1.

    The bulk POST /v2/version_files is fast but has been observed to silently omit
    some matches on large batches (undocumented partial responses). Every hash the
    bulk pass does not return is therefore re-checked with the reliable single-hash
    GET /v2/version_file/{hash}. A 404 there is authoritative: the file is genuinely
    not on Modrinth -- i.e. a real single-platform / staleness risk, not a fluke.
    """
    out = {}
    for i in range(0, len(sha1_list), MODRINTH_BULK_CHUNK):
        chunk = sha1_list[i:i + MODRINTH_BULK_CHUNK]
        resp = http.post(
            f"{MODRINTH_API}/version_files",
            json={"hashes": chunk, "algorithm": "sha1"},
        )
        if resp.status_code == 200:
            out.update(resp.json())
        else:
            print(f"  (Modrinth bulk lookup HTTP {resp.status_code} for chunk at {i})")
        time.sleep(THROTTLE_SECONDS)

    missing = [h for h in sha1_list if h not in out]
    if missing:
        print(f"  Backfilling {len(missing)} bulk-missed hashes via single-hash lookup ...")
        for h in missing:
            resp = http.get(f"{MODRINTH_API}/version_file/{h}", params={"algorithm": "sha1"})
            if resp.status_code == 200:
                out[h] = resp.json()   # bare version object, same schema as bulk entries
            time.sleep(THROTTLE_SECONDS)
    return out


def modrinth_latest(http, project_id, memo):
    """Newest forge / MC_VERSION version for a project (newest-first from the API)."""
    if project_id in memo:
        return memo[project_id]
    params = {
        "loaders": json.dumps([LOADER]),
        "game_versions": json.dumps([MC_VERSION]),
    }
    resp = http.get(f"{MODRINTH_API}/project/{project_id}/version", params=params)
    time.sleep(THROTTLE_SECONDS)
    result = None
    if resp.status_code == 200:
        versions = resp.json()
        # API returns newest-first, but sort defensively by date_published.
        versions = [v for v in versions if v.get("date_published")]
        versions.sort(key=lambda v: v["date_published"], reverse=True)
        if STABLE_ONLY:
            rels = [v for v in versions if v.get("version_type") == "release"]
            versions = rels or versions  # fall back to any type if no release exists
        if versions:
            v = versions[0]
            result = {
                "version": v.get("version_number"),
                "version_id": v.get("id"),
                "date": v.get("date_published"),
                "type": v.get("version_type"),
                "url": f"https://modrinth.com/mod/{project_id}/version/{v.get('id')}",
            }
    memo[project_id] = result
    return result


def modrinth_project_by_slug(http, slug, memo):
    """Exact-slug project lookup (used to bridge jars installed from CurseForge whose
    exact file is not on Modrinth). Returns project_id or None. No fuzzy search."""
    key = f"slug:{slug}"
    if key in memo:
        return memo[key]
    pid = None
    if slug:
        resp = http.get(f"{MODRINTH_API}/project/{slug}")
        time.sleep(THROTTLE_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            gv = data.get("game_versions") or []
            lo = data.get("loaders") or []
            if MC_VERSION in gv and LOADER in lo:
                pid = data.get("id")
    memo[key] = pid
    return pid


# --------------------------------------------------------------------------- #
# CurseForge tier
# --------------------------------------------------------------------------- #
def load_cf_key(cli_key):
    if cli_key:
        return cli_key.strip()
    env = os.environ.get("CURSEFORGE_API_KEY")
    if env:
        return env.strip()
    if os.path.exists(CF_KEY_FILE):
        try:
            with open(CF_KEY_FILE, "r", encoding="utf-8") as f:
                k = f.read().strip()
            if k:
                return k
        except Exception:
            pass
    return None


def cf_fingerprint_identify(http, fingerprints):
    """POST /v1/fingerprints -> {fingerprint: {modId, fileId, version, date}}."""
    out = {}
    for i in range(0, len(fingerprints), 100):
        chunk = fingerprints[i:i + 100]
        # Game-scoped endpoint narrows matching to Minecraft (gameId 432), avoiding
        # rare cross-game murmur2 collisions.
        resp = http.post(f"{CURSEFORGE_API}/fingerprints/{CF_GAME_ID}", json={"fingerprints": chunk})
        if resp.status_code != 200:
            print(f"  (CurseForge fingerprint lookup HTTP {resp.status_code} for chunk {i})")
            time.sleep(THROTTLE_SECONDS)
            continue
        data = resp.json().get("data", {})
        for match in data.get("exactMatches", []):
            fobj = match.get("file", {})
            fp = fobj.get("fileFingerprint")
            if fp is not None:
                out[fp] = {
                    "mod_id": fobj.get("modId"),
                    "file_id": fobj.get("id"),
                    "version": fobj.get("displayName"),
                    "date": fobj.get("fileDate"),
                }
        time.sleep(THROTTLE_SECONDS)
    return out


def cf_latest(http, mod_id, memo):
    """Newest available Forge / MC_VERSION file for a CurseForge project."""
    if mod_id in memo:
        return memo[mod_id]
    params = {
        "gameVersion": MC_VERSION,
        "modLoaderType": CF_MODLOADER_TYPE,
        "pageSize": 50,
    }
    resp = http.get(f"{CURSEFORGE_API}/mods/{mod_id}/files", params=params)
    time.sleep(THROTTLE_SECONDS)
    result = None
    if resp.status_code == 200:
        files = resp.json().get("data", [])
        files = [f for f in files if f.get("isAvailable", True) and f.get("fileDate")]
        files.sort(key=lambda f: f["fileDate"], reverse=True)
        if STABLE_ONLY:
            rels = [f for f in files if f.get("releaseType") == 1]  # 1=release,2=beta,3=alpha
            files = rels or files
        if files:
            f = files[0]
            result = {
                "version": f.get("displayName"),
                "file_id": f.get("id"),
                "date": f.get("fileDate"),
                "url": f.get("downloadUrl"),
            }
    memo[mod_id] = result
    return result


def cf_meta(http, mod_ids):
    """POST /v1/mods -> {modId: {name, slug, website}} for display + linking."""
    out = {}
    ids = [m for m in mod_ids if m is not None]
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        resp = http.post(f"{CURSEFORGE_API}/mods", json={"modIds": chunk})
        time.sleep(THROTTLE_SECONDS)
        if resp.status_code != 200:
            continue
        for mod in resp.json().get("data", []):
            out[mod.get("id")] = {
                "name": mod.get("name"),
                "slug": mod.get("slug"),
                "website": (mod.get("links") or {}).get("websiteUrl"),
            }
    return out


def cf_search_slug(http, slug, memo):
    """Exact-slug CurseForge search (bridges jars installed from Modrinth whose exact
    file is not on CurseForge). Returns modId or None."""
    key = f"cfslug:{slug}"
    if key in memo:
        return memo[key]
    mod_id = None
    if slug:
        params = {"gameId": CF_GAME_ID, "classId": CF_CLASS_MOD, "slug": slug}
        resp = http.get(f"{CURSEFORGE_API}/mods/search", params=params)
        time.sleep(THROTTLE_SECONDS)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                mod_id = data[0].get("id")
    memo[key] = mod_id
    return mod_id


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #
def classify(rec, cf_active, drift_days):
    """Decide a status code for one mod record."""
    mr, cf = rec["modrinth"], rec["curseforge"]
    mr_on = mr.get("project_id") is not None
    cf_on = cf.get("mod_id") is not None

    if not mr_on and not cf_on:
        return ST_UNIDENTIFIED

    # per-platform "behind" (a newer compatible build exists on that platform)
    mr_behind = None
    if mr_on and mr.get("latest_date") and mr.get("installed_date"):
        mr_behind = day_delta(parse_iso(mr["latest_date"]), parse_iso(mr["installed_date"]))
        mr["behind_days"] = mr_behind if mr_behind and mr_behind > 0 else 0
    cf_behind = None
    if cf_on and cf.get("latest_date") and cf.get("installed_date"):
        cf_behind = day_delta(parse_iso(cf["latest_date"]), parse_iso(cf["installed_date"]))
        cf["behind_days"] = cf_behind if cf_behind and cf_behind > 0 else 0

    behind_anywhere = (mr_behind and mr_behind > 0) or (cf_behind and cf_behind > 0)

    if mr_on and cf_on:
        # Compare the NEWEST build available on each platform -> the drift signal.
        mr_latest = parse_iso(mr.get("latest_date"))
        cf_latest = parse_iso(cf.get("latest_date"))
        if mr_latest and cf_latest:
            gap = abs(day_delta(mr_latest, cf_latest))
            if gap is not None and gap > drift_days:
                rec["drift_days"] = gap
                rec["drift_ahead"] = "modrinth" if mr_latest > cf_latest else "curseforge"
                return ST_DRIFT
        return ST_UPDATE if behind_anywhere else ST_UP_TO_DATE

    # identified on exactly one platform
    if cf_active:
        # both tiers ran and cross-slug bridging was attempted -> genuinely single-platform
        return ST_UPDATE if behind_anywhere else ST_SINGLE
    # CF tier did not run -> we only have half the picture
    return ST_UPDATE if behind_anywhere else ST_PARTIAL


def reconcile(mods_dir, args):
    global STABLE_ONLY
    STABLE_ONLY = not args.include_prereleases

    jars = sorted(f for f in os.listdir(mods_dir) if f.lower().endswith(".jar"))
    if not jars:
        sys.exit(f"No .jar files found in {mods_dir}")

    cache = load_cache() if not args.refresh else {"version": CACHE_VERSION, "files": {}}
    cache_files = cache.setdefault("files", {})

    cf_key = None if args.modrinth_only else load_cf_key(args.cf_key)
    cf_active = cf_key is not None

    print(f"Scanning {len(jars)} jars in {os.path.relpath(mods_dir, MINECRAFT_DIR)}/ ...")
    print(f"  Modrinth tier : ON")
    print(f"  CurseForge tier: {'ON' if cf_active else 'OFF (no API key -- see notice below)'}")

    # ---- hash / fingerprint every jar (cached by mtime:size) -----------------
    # NOTE: hash -> LIST of records. Two differently-named jars can be byte-identical
    # (a mislabeled/duplicated jar), and both must receive the platform match.
    records = []
    sha1_to_files, fp_to_files = {}, {}
    for jar in jars:
        path = os.path.join(mods_dir, jar)
        sig = file_sig(path)
        ce = cache_files.get(jar)
        if not ce or ce.get("sig") != sig:
            sha1 = sha1_of(path)
            fp = cf_fingerprint(path) if not args.modrinth_only else None
            modid, name = read_modinfo(path)
            ce = {"sig": sig, "sha1": sha1, "fp": fp, "modid": modid, "name": name}
            cache_files[jar] = ce
        elif not args.modrinth_only and ce.get("fp") is None:
            ce["fp"] = cf_fingerprint(path)  # backfill fp if cached before CF tier used
        rec = {
            "file": jar,
            "sha1": ce["sha1"],
            "fingerprint": ce.get("fp"),
            "modid": ce.get("modid"),
            "name": ce.get("name") or jar,
            "modrinth": {},
            "curseforge": {},
        }
        records.append(rec)
        sha1_to_files.setdefault(ce["sha1"], []).append(rec)
        if ce.get("fp") is not None:
            fp_to_files.setdefault(ce["fp"], []).append(rec)
    save_cache(cache)

    mr_http = Http()
    cf_http = Http({"x-api-key": cf_key}) if cf_active else None

    # ---- Modrinth identify (bulk by hash) -----------------------------------
    print("Identifying on Modrinth (bulk hash lookup + single-hash backfill) ...")
    mr_matches = modrinth_identify(mr_http, list(sha1_to_files.keys()))
    for sha1, ver in mr_matches.items():
        for rec in sha1_to_files.get(sha1, []):
            rec["modrinth"] = {
                "project_id": ver.get("project_id"),
                "installed_version": ver.get("version_number"),
                "installed_date": ver.get("date_published"),
                "link": "hash",
            }

    # ---- CurseForge identify (bulk by fingerprint) --------------------------
    cf_matches = {}
    if cf_active:
        print("Identifying on CurseForge (bulk fingerprint lookup) ...")
        cf_matches = cf_fingerprint_identify(cf_http, list(fp_to_files.keys()))
        for fp, m in cf_matches.items():
            for rec in fp_to_files.get(fp, []):
                rec["curseforge"] = {
                    "mod_id": m.get("mod_id"),
                    "installed_file_id": m.get("file_id"),
                    "installed_version": m.get("version"),
                    "installed_date": m.get("date"),
                    "link": "fingerprint",
                }

    # ---- fetch "latest available" per platform ------------------------------
    mr_memo, cf_memo, slug_memo = {}, {}, {}
    n_mr = sum(1 for r in records if r["modrinth"].get("project_id"))
    print(f"Fetching newest Modrinth builds for {n_mr} identified projects ...")
    for rec in records:
        pid = rec["modrinth"].get("project_id")
        if pid:
            latest = modrinth_latest(mr_http, pid, mr_memo)
            if latest:
                rec["modrinth"]["latest_version"] = latest["version"]
                rec["modrinth"]["latest_date"] = latest["date"]
                rec["modrinth"]["latest_type"] = latest.get("type")
                rec["modrinth"]["latest_url"] = latest["url"]

    if cf_active:
        n_cf = sum(1 for r in records if r["curseforge"].get("mod_id"))
        print(f"Fetching newest CurseForge builds for {n_cf} identified projects ...")
        for rec in records:
            mid = rec["curseforge"].get("mod_id")
            if mid:
                latest = cf_latest(cf_http, mid, cf_memo)
                if latest:
                    rec["curseforge"]["latest_version"] = latest["version"]
                    rec["curseforge"]["latest_date"] = latest["date"]
                    rec["curseforge"]["latest_url"] = latest["url"]

    # ---- cross-link bridges (installed-from-the-other-platform case) --------
    # A jar downloaded from CF won't hash-match on Modrinth even if the mod IS on
    # Modrinth. Try an exact-slug resolution using the jar's modId so we can still
    # surface drift. Matches found this way are labelled "linked", not "exact".
    if not args.no_bridge:
        for rec in records:
            slug = rec.get("modid")
            if not slug:
                continue
            if not rec["modrinth"].get("project_id") and (rec["curseforge"].get("mod_id") or not cf_active):
                pid = modrinth_project_by_slug(mr_http, slug, slug_memo)
                if pid:
                    rec["modrinth"]["project_id"] = pid
                    rec["modrinth"]["link"] = "slug"
                    latest = modrinth_latest(mr_http, pid, mr_memo)
                    if latest:
                        rec["modrinth"]["latest_version"] = latest["version"]
                        rec["modrinth"]["latest_date"] = latest["date"]
                        rec["modrinth"]["latest_url"] = latest["url"]
            if cf_active and not rec["curseforge"].get("mod_id") and rec["modrinth"].get("project_id"):
                mid = cf_search_slug(cf_http, slug, slug_memo)
                if mid:
                    rec["curseforge"]["mod_id"] = mid
                    rec["curseforge"]["link"] = "slug"
                    latest = cf_latest(cf_http, mid, cf_memo)
                    if latest:
                        rec["curseforge"]["latest_version"] = latest["version"]
                        rec["curseforge"]["latest_date"] = latest["date"]
                        rec["curseforge"]["latest_url"] = latest["url"]

    # ---- enrich CF display names --------------------------------------------
    if cf_active:
        cf_ids = {r["curseforge"].get("mod_id") for r in records if r["curseforge"].get("mod_id")}
        meta = cf_meta(cf_http, list(cf_ids))
        for rec in records:
            mid = rec["curseforge"].get("mod_id")
            if mid and mid in meta:
                rec["curseforge"]["project_name"] = meta[mid]["name"]
                rec["curseforge"]["project_url"] = meta[mid]["website"]

    # ---- classify -----------------------------------------------------------
    for rec in records:
        rec["status"] = classify(rec, cf_active, args.drift_days)

    return records, cf_active


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def summarize(records):
    buckets = {}
    for r in records:
        buckets.setdefault(r["status"], []).append(r)
    return buckets


def detect_conflicts(records):
    """Find jars that will collide at load time:
      * byte-identical jars (same sha1 under two names -- one is mislabeled), and
      * different jars declaring the same Forge modId (two builds of one mod).
    Both make Forge refuse to load or silently drop a mod."""
    by_sha, by_modid = {}, {}
    for r in records:
        by_sha.setdefault(r["sha1"], []).append(r)
        if r.get("modid"):
            by_modid.setdefault(r["modid"], []).append(r)
    identical = [(h, rs) for h, rs in by_sha.items() if len(rs) > 1]
    # same modId across jars that are NOT all byte-identical -> distinct conflicting builds
    modid_conf = [
        (mid, rs) for mid, rs in by_modid.items()
        if len(rs) > 1 and len({r["sha1"] for r in rs}) > 1
    ]
    identical.sort(key=lambda t: (t[1][0].get("modid") or "", t[0]))
    modid_conf.sort(key=lambda t: t[0])
    return identical, modid_conf


def _mr_cell(r):
    mr = r["modrinth"]
    if not mr.get("project_id"):
        return "-"
    tag = "" if mr.get("link") in (None, "hash") else " *(linked)*"
    latest = mr.get("latest_version") or "?"
    ld = fmt_date(parse_iso(mr.get("latest_date")))
    return f"{latest} ({ld}){tag}"


def _cf_cell(r):
    cf = r["curseforge"]
    if not cf.get("mod_id"):
        return "-"
    tag = "" if cf.get("link") in (None, "fingerprint") else " *(linked)*"
    latest = cf.get("latest_version") or "?"
    ld = fmt_date(parse_iso(cf.get("latest_date")))
    return f"{latest} ({ld}){tag}"


def write_reports(records, cf_active, args):
    os.makedirs(DOCS_DIR, exist_ok=True)
    buckets = summarize(records)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d_%H%M%S")

    def order(bucket):
        return sorted(bucket, key=lambda r: r["file"].lower())

    lines = []
    A = lines.append
    A("# Cross-Platform Mod Version Report")
    A("")
    A(f"*Generated {now.strftime('%Y-%m-%d %H:%M UTC')} — target: Minecraft {MC_VERSION} / {LOADER.title()}*")
    A("")
    A("This report reconciles every installed jar against **both** CurseForge and "
      "Modrinth so a mod that was updated on one platform but not the other cannot "
      "silently leave the pack on a stale build.")
    A("")
    if not cf_active:
        A("> [!WARNING]")
        A("> **CurseForge tier was SKIPPED — no API key found.** Only Modrinth was "
          "checked, so genuine cross-platform drift cannot be detected this run. "
          "Add a free key (env `CURSEFORGE_API_KEY` or `scripts/.curseforge_api_key`) "
          "to enable full reconciliation. See `docs/mod_update_tooling.md`.")
        A("")

    # ---- Duplicate / conflicting jars (pack-integrity, surfaced first) ------
    identical, modid_conf = detect_conflicts(records)
    if identical or modid_conf:
        A("## ⚠️ Duplicate / Conflicting Jars — fix before launch")
        A("")
        A("Multiple jars resolve to the same mod. Forge registers a mod id once, so "
          "two jars sharing an id crash on launch or silently drop one. Delete the "
          "stray jar in each group (and re-download the mod that was *supposed* to be "
          "under the wrong name).")
        A("")
        if identical:
            A("**Byte-identical duplicates** — same file content under two names, so one "
              "filename is mislabeled and its intended mod is effectively missing:")
            A("")
            for h, rs in identical:
                mid = next((r["modid"] for r in rs if r.get("modid")), "?")
                files = ", ".join(f"`{r['file']}`" for r in rs)
                A(f"- modId `{mid}` (sha1 `{h[:12]}`): {files}")
            A("")
        if modid_conf:
            A("**Same mod id, different files** — two distinct builds of one mod loaded "
              "together; keep only one:")
            A("")
            for mid, rs in modid_conf:
                files = ", ".join(f"`{r['file']}`" for r in rs)
                A(f"- modId `{mid}`: {files}")
            A("")

    total = len(records)
    A("## Summary")
    A("")
    A("| Status | Count | Meaning |")
    A("|---|---:|---|")
    A(f"| 🔴 Platform drift | {len(buckets.get(ST_DRIFT, []))} | One platform has a newer build than the other |")
    A(f"| 🟠 Update available | {len(buckets.get(ST_UPDATE, []))} | A newer compatible build exists |")
    A(f"| 🟣 Single-platform | {len(buckets.get(ST_SINGLE, []))} | Mod found on only one platform |")
    A(f"| 🔵 Partial (CF unchecked) | {len(buckets.get(ST_PARTIAL, []))} | Only Modrinth checked this run |")
    A(f"| ⚪ Unidentified | {len(buckets.get(ST_UNIDENTIFIED, []))} | Not matched on either platform |")
    A(f"| 🟢 Up to date | {len(buckets.get(ST_UP_TO_DATE, []))} | Newest everywhere it was found |")
    A(f"| **Total** | **{total}** | |")
    A("")

    # ---- Platform drift (headline) ------------------------------------------
    drift = order(buckets.get(ST_DRIFT, []))
    A("## 🔴 Platform Drift — one platform is ahead of the other")
    A("")
    if drift:
        A("These are the exact staleness traps: the two platforms disagree on the "
          "newest build. Update from the platform marked **ahead**.")
        A("")
        A("| Mod | Installed | Modrinth latest | CurseForge latest | Ahead | Gap |")
        A("|---|---|---|---|---|---:|")
        for r in drift:
            inst = r["modrinth"].get("installed_version") or r["curseforge"].get("installed_version") or "?"
            ahead = r.get("drift_ahead", "?")
            A(f"| {r['name']} <br>`{r['file']}` | {inst} | {_mr_cell(r)} | {_cf_cell(r)} "
              f"| **{ahead}** | {r.get('drift_days', '?')}d |")
    else:
        A("*None detected.*" + ("" if cf_active else " (CurseForge tier was off — drift cannot be seen.)"))
    A("")

    # ---- Updates available --------------------------------------------------
    upd = order(buckets.get(ST_UPDATE, []))
    A("## 🟠 Updates Available")
    A("")
    if upd:
        A("| Mod | Installed | Modrinth latest | CurseForge latest | Behind |")
        A("|---|---|---|---|---:|")
        for r in upd:
            inst = r["modrinth"].get("installed_version") or r["curseforge"].get("installed_version") or "?"
            behind = max(r["modrinth"].get("behind_days", 0), r["curseforge"].get("behind_days", 0))
            A(f"| {r['name']} <br>`{r['file']}` | {inst} | {_mr_cell(r)} | {_cf_cell(r)} | {behind}d |")
    else:
        A("*None.*")
    A("")

    # ---- Single-platform ----------------------------------------------------
    single = order(buckets.get(ST_SINGLE, []))
    if single:
        A("## 🟣 Single-Platform Mods")
        A("")
        A("Found on only one platform. Track updates on that platform — the other "
          "will never show a new version for these.")
        A("")
        A("| Mod | Platform | Installed | Latest |")
        A("|---|---|---|---|")
        for r in single:
            if r["modrinth"].get("project_id"):
                plat, inst, latest = "Modrinth", r["modrinth"].get("installed_version"), _mr_cell(r)
            else:
                plat, inst, latest = "CurseForge", r["curseforge"].get("installed_version"), _cf_cell(r)
            A(f"| {r['name']} <br>`{r['file']}` | {plat} | {inst or '?'} | {latest} |")
        A("")

    # ---- Partial (only when CF off) -----------------------------------------
    partial = order(buckets.get(ST_PARTIAL, []))
    if partial and not cf_active:
        A(f"## 🔵 Modrinth-only view (CurseForge unchecked) — {len(partial)} mods")
        A("")
        A("<details><summary>Matched on Modrinth and up to date there, but CurseForge "
          "was not checked this run.</summary>")
        A("")
        A("| Mod | Modrinth installed | Modrinth latest |")
        A("|---|---|---|")
        for r in partial:
            A(f"| `{r['file']}` | {r['modrinth'].get('installed_version','?')} | {_mr_cell(r)} |")
        A("")
        A("</details>")
        A("")

    # ---- Unidentified -------------------------------------------------------
    unid = order(buckets.get(ST_UNIDENTIFIED, []))
    if unid:
        A(f"## ⚪ Unidentified — {len(unid)} jars")
        A("")
        A("Not matched by hash on either platform (custom builds, renamed/repackaged "
          "jars, or removed projects). Review manually.")
        A("")
        for r in unid:
            hint = f" — modId `{r['modid']}`" if r.get("modid") else ""
            A(f"- `{r['file']}`{hint}")
        A("")

    # ---- Up to date (collapsed) ---------------------------------------------
    utd = order(buckets.get(ST_UP_TO_DATE, []))
    A(f"## 🟢 Up to Date — {len(utd)} mods")
    A("")
    A("<details><summary>Show up-to-date mods</summary>")
    A("")
    for r in utd:
        A(f"- `{r['file']}`")
    A("")
    A("</details>")
    A("")

    report_md = "\n".join(lines)
    report_path = os.path.join(DOCS_DIR, f"mod_version_report_{stamp}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    stable_path = os.path.join(DOCS_DIR, "MOD_VERSION_STATUS.md")
    with open(stable_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    json_path = os.path.join(DOCS_DIR, "mod_version_status.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated": now.isoformat(),
            "mc_version": MC_VERSION,
            "loader": LOADER,
            "curseforge_tier": cf_active,
            "counts": {k: len(v) for k, v in buckets.items()},
            "conflicts": {
                "byte_identical": [
                    {"sha1": h, "modid": next((r["modid"] for r in rs if r.get("modid")), None),
                     "files": [r["file"] for r in rs]}
                    for h, rs in identical
                ],
                "same_modid": [
                    {"modid": mid, "files": [r["file"] for r in rs]}
                    for mid, rs in modid_conf
                ],
            },
            "mods": records,
        }, f, indent=2)

    return report_path, stable_path, json_path, buckets, (len(identical) + len(modid_conf))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Cross-platform (CurseForge + Modrinth) mod version reconciliation.")
    ap.add_argument("--mods-dir", default=DEFAULT_MODS_DIR, help="Directory of installed jars (default: minecraft/mods).")
    ap.add_argument("--mc", default=None, help="Minecraft version to target (default: auto-detected from the pack).")
    ap.add_argument("--loader", default=None, help="Mod loader to target: forge/neoforge/fabric/quilt (default: auto-detected).")
    ap.add_argument("--modrinth-only", action="store_true", help="Skip the CurseForge tier entirely.")
    ap.add_argument("--cf-key", default=None, help="CurseForge API key (overrides env / key file).")
    ap.add_argument("--refresh", action="store_true", help="Ignore the on-disk identity cache and re-hash all jars.")
    ap.add_argument("--no-bridge", action="store_true", help="Disable slug-based cross-platform bridging.")
    ap.add_argument("--include-prereleases", action="store_true", help="Let beta/alpha builds count as the newest available (default: releases only).")
    ap.add_argument("--drift-days", type=int, default=DRIFT_DAYS_DEFAULT, help="Min day gap between platforms' newest builds to flag drift.")
    ap.add_argument("--fail-on-stale", action="store_true", help="Exit 1 if any drift/update is found (for CI).")
    args = ap.parse_args()

    # Windows consoles default to cp1252, which can't encode the emoji/dashes we
    # print. Switch console streams to UTF-8 (best-effort) so nothing crashes.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Auto-detect the pack's Minecraft version + loader (override with --mc/--loader).
    global MC_VERSION, LOADER, CF_MODLOADER_TYPE
    info = env.pack_info() if env else {}
    MC_VERSION = args.mc or info.get("mc_version") or MC_VERSION
    LOADER = (args.loader or info.get("loader") or LOADER).lower()
    CF_MODLOADER_TYPE = CF_MODLOADER_BY_LOADER.get(LOADER, CF_MODLOADER_FORGE)
    print(f"Target: Minecraft {MC_VERSION} / {LOADER}")

    if not os.path.isdir(args.mods_dir):
        sys.exit(f"Mods dir not found: {args.mods_dir}")

    t0 = time.time()
    records, cf_active = reconcile(args.mods_dir, args)
    report_path, stable_path, json_path, buckets, n_conflicts = write_reports(records, cf_active, args)

    n_drift = len(buckets.get(ST_DRIFT, []))
    n_update = len(buckets.get(ST_UPDATE, []))
    n_single = len(buckets.get(ST_SINGLE, []))
    n_unid = len(buckets.get(ST_UNIDENTIFIED, []))

    print("")
    print("=" * 60)
    if n_conflicts:
        print(f"  [!] Duplicate/conflicting jars: {n_conflicts} group(s) - see report")
    print(f"  Platform drift    : {n_drift}")
    print(f"  Updates available : {n_update}")
    print(f"  Single-platform   : {n_single}")
    print(f"  Unidentified      : {n_unid}")
    print(f"  Up to date        : {len(buckets.get(ST_UP_TO_DATE, []))}")
    if not cf_active:
        print(f"  (Modrinth-only    : {len(buckets.get(ST_PARTIAL, []))} - CurseForge tier OFF)")
    print("=" * 60)
    print(f"Report : {os.path.relpath(report_path, MINECRAFT_DIR)}")
    print(f"Latest : {os.path.relpath(stable_path, MINECRAFT_DIR)}")
    print(f"JSON   : {os.path.relpath(json_path, MINECRAFT_DIR)}")
    print(f"Done in {time.time() - t0:.1f}s.")

    if args.fail_on_stale and (n_drift or n_update):
        sys.exit(1)


if __name__ == "__main__":
    main()
