#!/usr/bin/env python3
"""
emc_apply_overrides.py -- Apply audit suggestions to custom_emc.json, safely.

Portable across packs via pack_env (no hardcoded paths). Backs up custom_emc.json,
applies every suggestion from docs/emc_override_suggestions.json, then validates the
result -- restoring the backup if the write produced invalid JSON.

Run emc_audit.py first to generate the suggestions. Pure stdlib.
"""

import json
import os
import shutil
import sys
import time

import pack_env as env

SUGGESTIONS_PATH = os.path.join(env.DOCS_DIR, "emc_override_suggestions.json")


def apply_overrides():
    if not env.has_projecte():
        print("No ProjectE detected in this pack. Nothing to apply. Exiting.")
        return 0

    if not os.path.exists(env.CUSTOM_EMC_PATH):
        print(f"custom_emc.json not found at {env.CUSTOM_EMC_PATH}.")
        print("Nothing to apply. Exiting.")
        return 0

    if not os.path.exists(SUGGESTIONS_PATH):
        print(f"Suggestions file not found at {SUGGESTIONS_PATH}. Run emc_audit.py first.")
        return 1

    with open(SUGGESTIONS_PATH, "r", encoding="utf-8") as f:
        suggestions = json.load(f).get("suggestions", [])
    if not suggestions:
        print("No suggestions to apply.")
        return 0

    # Safety 1: back up custom_emc.json
    backup_path = f"{env.CUSTOM_EMC_PATH}.bak_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copyfile(env.CUSTOM_EMC_PATH, backup_path)
    print(f"Backup created: {os.path.relpath(backup_path, env.MINECRAFT_DIR)}")

    with open(env.CUSTOM_EMC_PATH, "r", encoding="utf-8") as f:
        custom_data = json.load(f)

    entries = custom_data.get("entries", [])
    entries_map = {e["item"]: e for e in entries}

    modified = added = 0
    for s in suggestions:
        item_id, target = s["item"], s["emc"]
        if item_id in entries_map:
            if entries_map[item_id]["emc"] != target:
                entries_map[item_id]["emc"] = target
                modified += 1
        else:
            new_entry = {"item": item_id, "emc": target}
            entries.append(new_entry)
            entries_map[item_id] = new_entry
            added += 1

    custom_data["entries"] = entries
    with open(env.CUSTOM_EMC_PATH, "w", encoding="utf-8") as f:
        json.dump(custom_data, f, indent=2)

    # Safety 2: validate, restore backup on failure
    try:
        with open(env.CUSTOM_EMC_PATH, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        print(f"CRITICAL: post-write JSON invalid ({e}). Restoring backup.")
        shutil.copyfile(backup_path, env.CUSTOM_EMC_PATH)
        return 1

    print(f"Applied overrides. Added: {added}, Modified: {modified}. JSON valid.")
    return 0


if __name__ == "__main__":
    sys.exit(apply_overrides())
