#!/usr/bin/env python3
"""
pack_env.py -- shared pack auto-detection for the modpack dev tools.

Import this from any tool script so the tool works in ANY modpack instance with
zero hardcoded paths, mod versions, or pack names. Everything below is discovered
from the instance layout at runtime:

    from pack_env import (
        MINECRAFT_DIR, MODS_DIR, CONFIG_DIR, DOCS_DIR,
        pack_info, find_mod, has_mod, has_projecte, has_autoemc,
        autoemc_baselines, git,
    )

Layout assumed (standard Minecraft instance):
    <instance>/                 <- instance.cfg, mmc-pack.json, flame/  (PrismLauncher)
        minecraft/              <- MINECRAFT_DIR: mods/, config/, docs/, scripts/
            scripts/            <- this file lives here

Nothing here is specific to ATM9 or any single pack. Pure stdlib.
"""

import glob
import json
import os
import re
import subprocess

# --------------------------------------------------------------------------- #
# Directory anchors (relative to this file -- portable to any instance)
# --------------------------------------------------------------------------- #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_minecraft_dir(start):
    """Walk up from `start` to the Minecraft instance dir (the one containing
    both mods/ and config/). This makes the tools work no matter how deeply they
    are nested under it -- e.g. scripts/ or scripts/dev/."""
    d = start
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "mods")) and os.path.isdir(os.path.join(d, "config")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    # Fallback: assume we're one level under it (scripts/ layout).
    return os.path.abspath(os.path.join(start, ".."))


MINECRAFT_DIR = _find_minecraft_dir(SCRIPT_DIR)
INSTANCE_DIR = os.path.abspath(os.path.join(MINECRAFT_DIR, ".."))  # holds instance.cfg

MODS_DIR = os.path.join(MINECRAFT_DIR, "mods")
CONFIG_DIR = os.path.join(MINECRAFT_DIR, "config")
DOCS_DIR = os.path.join(MINECRAFT_DIR, "docs")

# Common EMC / ProjectE paths (only meaningful if the pack has those mods)
PROJECTE_DIR = os.path.join(CONFIG_DIR, "ProjectE")
AUTOEMC_DIR = os.path.join(CONFIG_DIR, "autoemc")
CUSTOM_EMC_PATH = os.path.join(PROJECTE_DIR, "custom_emc.json")
GENERATED_EMC_PATH = os.path.join(AUTOEMC_DIR, "generated_entries.json")
AUTOEMC_CONFIG_PATH = os.path.join(CONFIG_DIR, "autoemc-common.toml")

# MultiMC/Prism component uid -> friendly loader name
_LOADER_UIDS = {
    "net.minecraftforge": "forge",
    "net.neoforged": "neoforge",
    "net.fabricmc.fabric-loader": "fabric",
    "org.quiltmc.quilt-loader": "quilt",
}


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Pack metadata
# --------------------------------------------------------------------------- #
def pack_info():
    """Auto-detect {name, mc_version, loader, loader_version} from mmc-pack.json
    + instance.cfg. Any field that cannot be found is left as None (name falls
    back to the instance folder name)."""
    info = {"name": None, "mc_version": None, "loader": None, "loader_version": None}

    mmc = (_read_json(os.path.join(MINECRAFT_DIR, "mmc-pack.json"))
           or _read_json(os.path.join(INSTANCE_DIR, "mmc-pack.json")))
    if mmc:
        for c in mmc.get("components", []):
            uid = c.get("uid")
            if uid == "net.minecraft":
                info["mc_version"] = c.get("version") or c.get("cachedVersion")
            elif uid in _LOADER_UIDS:
                info["loader"] = _LOADER_UIDS[uid]
                info["loader_version"] = c.get("version") or c.get("cachedVersion")

    cfg = os.path.join(INSTANCE_DIR, "instance.cfg")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("name="):
                        info["name"] = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not info["name"]:
        info["name"] = os.path.basename(INSTANCE_DIR) or "modpack"
    return info


# --------------------------------------------------------------------------- #
# Mod discovery (version-agnostic -- never hardcode a jar filename)
# --------------------------------------------------------------------------- #
def list_jars(mods_dir=None):
    d = mods_dir or MODS_DIR
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".jar"))


def find_mod(*patterns, mods_dir=None):
    """Return the path to the first jar whose filename contains ANY of the given
    case-insensitive substrings, ignoring version. e.g. find_mod('ProjectE_Integration',
    'ProjectEIntegration'). None if nothing matches."""
    jars = list_jars(mods_dir)
    for pat in patterns:
        p = pat.lower()
        for j in jars:
            if p in j.lower():
                return os.path.join(mods_dir or MODS_DIR, j)
    return None


def find_mods(*patterns, mods_dir=None):
    """All jars matching any pattern (case-insensitive substring)."""
    jars = list_jars(mods_dir)
    pats = [p.lower() for p in patterns]
    out = []
    for j in jars:
        low = j.lower()
        if any(p in low for p in pats):
            out.append(os.path.join(mods_dir or MODS_DIR, j))
    return out


def has_mod(*patterns, mods_dir=None):
    return find_mod(*patterns, mods_dir=mods_dir) is not None


# --------------------------------------------------------------------------- #
# Feature detection -- lets a tool skip cleanly in packs without the feature
# --------------------------------------------------------------------------- #
def has_projecte():
    return os.path.isdir(PROJECTE_DIR) or has_mod("ProjectE", "projecte")


def has_autoemc():
    return os.path.exists(AUTOEMC_CONFIG_PATH) or has_mod("autoemc")


def autoemc_baselines():
    """Read AutoEMC's fallback-rank baselines and OP floor from the pack's own
    autoemc-common.toml so the tools track the pack's real config instead of
    hardcoded numbers. Falls back to AutoEMC's documented defaults."""
    vals = {
        "commonBase": 8,
        "uncommonBase": 64,
        "rareBase": 512,
        "epicBase": 4096,
        "opMinimumEmc": 1_000_000_000_000,
        "highEmcWarningThreshold": 1_000_000_000_000,
    }
    if os.path.exists(AUTOEMC_CONFIG_PATH):
        try:
            with open(AUTOEMC_CONFIG_PATH, "r", encoding="utf-8") as f:
                text = f.read()
            for key in list(vals):
                m = re.search(rf"^\s*{re.escape(key)}\s*=\s*(\d+)", text, re.MULTILINE)
                if m:
                    vals[key] = int(m.group(1))
        except Exception:
            pass
    return vals


# --------------------------------------------------------------------------- #
# Git helpers (for the sync tooling / config generators)
# --------------------------------------------------------------------------- #
def git(*args, cwd=None):
    """Run a git command in MINECRAFT_DIR (or cwd). Returns stdout stripped, or
    None on any failure."""
    try:
        out = subprocess.run(
            ["git", "-C", cwd or MINECRAFT_DIR, *args],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def git_remote_url(remote="origin"):
    return git("remote", "get-url", remote)


def git_current_branch():
    b = git("rev-parse", "--abbrev-ref", "HEAD")
    return b if b and b != "HEAD" else None


# --------------------------------------------------------------------------- #
# Self-report when run directly -- handy sanity check in a new pack
# --------------------------------------------------------------------------- #
def summary():
    info = pack_info()
    lines = [
        "pack_env auto-detection:",
        f"  instance dir : {INSTANCE_DIR}",
        f"  minecraft dir: {MINECRAFT_DIR}",
        f"  pack name    : {info['name']}",
        f"  minecraft    : {info['mc_version']}",
        f"  loader       : {info['loader']} {info['loader_version'] or ''}".rstrip(),
        f"  jars in mods : {len(list_jars())}",
        f"  ProjectE     : {'yes' if has_projecte() else 'no'}",
        f"  AutoEMC      : {'yes' if has_autoemc() else 'no'}",
        f"  git remote   : {git_remote_url() or '(none)'}",
        f"  git branch   : {git_current_branch() or '(none/detached)'}",
    ]
    if has_autoemc():
        b = autoemc_baselines()
        lines.append(f"  emc baselines: common={b['commonBase']} uncommon={b['uncommonBase']} "
                     f"rare={b['rareBase']} epic={b['epicBase']} op_floor={b['opMinimumEmc']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
