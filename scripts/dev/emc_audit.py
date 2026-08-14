#!/usr/bin/env python3
"""
emc_audit.py -- Audit ProjectE / AutoEMC values for any modpack.

Portable across packs: all paths, mod versions, and AutoEMC baseline numbers are
auto-detected via pack_env (nothing is hardcoded to ATM9). If the pack has no
ProjectE, the script says so and exits cleanly.

What it does:
  * Flags items assigned AutoEMC's fallback ranks (common/uncommon/rare/epic base)
    -- read from the pack's own autoemc-common.toml, not hardcoded.
  * Flags cheap creative/debug items priced below the pack's OP floor.
  * Detects duplicate entries in custom_emc.json.
  * Scans the ProjectE Integration jar (found by glob, any version) for flat
    item->EMC data and reports items present there but missing locally.
  * Proposes overrides from scripts/emc_manual_overrides.json (pack-specific data)
    for items that actually exist in this pack.

Outputs (to docs/):
  emc_audit_report_YYYYMMDD_HHMMSS.md   timestamped report
  emc_rank_flagged.json                 fallback-rank items, for review
  emc_override_suggestions.json         consumed by emc_apply_overrides.py

Pure stdlib.
"""

import collections
import json
import os
import sys
import time
import zipfile

import pack_env as env


def load_custom_emc(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("entries", [])


def load_generated_emc(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manual_overrides():
    """Pack-specific override candidates from scripts/emc_manual_overrides.json."""
    path = os.path.join(env.SCRIPT_DIR, "emc_manual_overrides.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("overrides", [])
    except Exception as e:
        print(f"  (warning: could not read emc_manual_overrides.json: {e})")
        return []


def scan_integration_jar(jar_path):
    """Best-effort scan of the ProjectE Integration jar for flat {item_id: emc}
    JSON maps. Returns {item_id: emc}. Integration mostly ships conversion recipes
    rather than flat maps, so this is a light heuristic, not authoritative."""
    found = {}
    if not jar_path or not os.path.isfile(jar_path):
        return found
    try:
        with zipfile.ZipFile(jar_path, "r") as jar:
            for name in jar.namelist():
                if not name.endswith(".json"):
                    continue
                if "emc" not in name.lower():
                    continue
                try:
                    with jar.open(name) as f:
                        data = json.load(f)
                except Exception:
                    continue
                if isinstance(data, dict):
                    for k, v in data.items():
                        # only keep entries that look like item_id -> number
                        if isinstance(v, (int, float)) and isinstance(k, str) and ":" in k:
                            found[k] = v
    except Exception:
        pass
    return found


def run_audit():
    if not env.has_projecte():
        print("No ProjectE detected in this pack (no config/ProjectE and no ProjectE jar).")
        print("Nothing to audit. Exiting.")
        return 0

    baselines = env.autoemc_baselines()
    fallback_ranks = {
        baselines["commonBase"]: f"Common Base ({baselines['commonBase']})",
        baselines["uncommonBase"]: f"Uncommon Base ({baselines['uncommonBase']})",
        baselines["rareBase"]: f"Rare Base ({baselines['rareBase']})",
        baselines["epicBase"]: f"Epic Base ({baselines['epicBase']})",
    }
    op_floor = baselines["opMinimumEmc"]

    custom_entries = load_custom_emc(env.CUSTOM_EMC_PATH)
    generated_map = load_generated_emc(env.GENERATED_EMC_PATH)

    item_counts = collections.Counter(e["item"] for e in custom_entries)
    duplicates = [item for item, cnt in item_counts.items() if cnt > 1]
    custom_map = {e["item"]: e["emc"] for e in custom_entries}
    known_items = set(custom_map) | set(generated_map)
    known_namespaces = {k.split(":", 1)[0] for k in known_items if ":" in k}

    # Items sitting exactly on an AutoEMC fallback rank -> base-item review candidates
    rank_flagged = []
    for item_id, emc in generated_map.items():
        if emc in fallback_ranks:
            rank_flagged.append({"item": item_id, "emc": emc, "rank": fallback_ranks[emc]})

    # Cheap creative/debug items below the OP floor
    cheap_creative = []
    creative_keywords = ["creative", "debug", "infinity", "infinite"]
    for source in (custom_map, generated_map):
        for item_id, emc in source.items():
            low = item_id.lower()
            if any(kw in low for kw in creative_keywords) and emc < op_floor:
                if not any(c["item"] == item_id for c in cheap_creative):
                    cheap_creative.append({"item": item_id, "emc": emc})

    # Integration jar scan (globbed -- version-agnostic)
    integ_jar = env.find_mod("ProjectE_Integration", "ProjectEIntegration", "projecteintegration")
    jar_emc = scan_integration_jar(integ_jar)
    jar_missing = [
        {"item": k, "emc": v} for k, v in sorted(jar_emc.items()) if k not in known_items
    ]

    # Suggestions
    suggestions = []
    for ov in load_manual_overrides():
        item = ov.get("item")
        target = ov.get("emc")
        if item is None or target is None:
            continue
        # Suggest only when the item's mod is actually loaded in this pack (its
        # item is priced, or any item in its namespace is) -- keeps the override
        # relevant in this pack while staying silent in packs without that mod.
        ns = item.split(":", 1)[0] if ":" in item else None
        present = item in known_items or (ns is not None and ns in known_namespaces)
        if present and custom_map.get(item) != target:
            suggestions.append({
                "item": item,
                "emc": target,
                "reason": ov.get("reason", "Manual override"),
            })
    for c in cheap_creative:
        suggestions.append({
            "item": c["item"],
            "emc": op_floor,
            "reason": f"Creative/debug item elevated to OP floor ({op_floor})",
        })

    # ---- write report -------------------------------------------------------
    os.makedirs(env.DOCS_DIR, exist_ok=True)
    info = env.pack_info()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(env.DOCS_DIR, f"emc_audit_report_{stamp}.md")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# EMC Audit & Rank Detection Report\n\n")
        f.write(f"*Pack: {info['name']} | Minecraft {info['mc_version']} / "
                f"{info['loader']} | generated {time.strftime('%Y-%m-%d %H:%M')}*\n\n")
        f.write(f"**AutoEMC baselines (from config):** common={baselines['commonBase']}, "
                f"uncommon={baselines['uncommonBase']}, rare={baselines['rareBase']}, "
                f"epic={baselines['epicBase']}, OP floor={op_floor}\n\n")
        f.write(f"**Custom entries (`custom_emc.json`)**: {len(custom_entries)}\n")
        f.write(f"**AutoEMC entries (`generated_entries.json`)**: {len(generated_map)}\n")
        f.write(f"**Duplicates in custom_emc.json**: {len(duplicates)}\n")
        f.write(f"**Items on AutoEMC fallback ranks**: {len(rank_flagged)}\n")
        f.write(f"**Cheap creative/debug items**: {len(cheap_creative)}\n")
        f.write(f"**Integration jar**: {os.path.basename(integ_jar) if integ_jar else '(not found)'}"
                f" | flat EMC entries found: {len(jar_emc)} | missing locally: {len(jar_missing)}\n\n")

        if duplicates:
            f.write("## Duplicate entries in custom_emc.json\n\n")
            for item in duplicates[:50]:
                f.write(f"- `{item}` (x{item_counts[item]})\n")
            f.write("\n")

        if rank_flagged:
            f.write("## Items on AutoEMC Fallback Ranks (base-item audit candidates)\n\n")
            f.write("| Item ID | EMC | Fallback Rank |\n|---|---|---|\n")
            for r in rank_flagged[:50]:
                f.write(f"| `{r['item']}` | {r['emc']} | {r['rank']} |\n")
            if len(rank_flagged) > 50:
                f.write(f"\n*... and {len(rank_flagged) - 50} more in `emc_rank_flagged.json`.*\n")
            f.write("\n")

        if cheap_creative:
            f.write("## Cheap Creative / Debug Items\n\n")
            for c in cheap_creative[:20]:
                f.write(f"- `{c['item']}`: current {c['emc']} -> suggested {op_floor}\n")
            f.write("\n")

        if jar_missing:
            f.write("## Integration-jar EMC entries missing locally\n\n")
            for m in jar_missing[:30]:
                f.write(f"- `{m['item']}`: jar EMC {m['emc']}\n")
            if len(jar_missing) > 30:
                f.write(f"\n*... and {len(jar_missing) - 30} more.*\n")
            f.write("\n")

    # ---- write machine-readable exports ------------------------------------
    with open(os.path.join(env.DOCS_DIR, "emc_rank_flagged.json"), "w", encoding="utf-8") as f:
        json.dump({"fallback_rank_items": rank_flagged}, f, indent=2)
    with open(os.path.join(env.DOCS_DIR, "emc_override_suggestions.json"), "w", encoding="utf-8") as f:
        json.dump({"suggestions": suggestions}, f, indent=2)

    rel = os.path.relpath(report_path, env.MINECRAFT_DIR)
    print(f"Audit complete for: {info['name']}")
    print(f"  duplicates={len(duplicates)} rank_flagged={len(rank_flagged)} "
          f"cheap_creative={len(cheap_creative)} suggestions={len(suggestions)}")
    print(f"  integration jar: {os.path.basename(integ_jar) if integ_jar else '(not found)'} "
          f"({len(jar_missing)} entries missing locally)")
    print(f"Report: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(run_audit())
