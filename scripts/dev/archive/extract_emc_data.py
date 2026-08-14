import json
import os
import zipfile
from pathlib import Path

# Paths (adjusted for correct hierarchy)
BASE_PATH = Path(__file__).resolve().parents[1]  # points to the minecraft folder
CUSTOM_EMC_PATH = BASE_PATH / "config" / "ProjectE" / "custom_emc.json"
MAPPING_TOML_PATH = BASE_PATH / "config" / "ProjectE" / "mapping.toml"
PROCESSING_TOML_PATH = BASE_PATH / "config" / "ProjectE" / "processing.toml"
INTEGRATION_JAR_PATH = BASE_PATH / "mods" / "ProjectE_Integration-1.20.1-7.2.5.jar"

OUTPUT_CORRECTED = BASE_PATH / "config" / "ProjectE" / "custom_emc_corrected.json"
REPORT_PATH = BASE_PATH / "reports" / "emc_audit_report.md"
BASE_EMC_PATH = BASE_PATH / "data" / "base_emc.json"

# Threshold for "extremely high" EMC values (adjustable)
HIGH_EMC_THRESHOLD = 1_000_000_000  # values above this are likely auto‑generated defaults

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_toml(path):
    try:
        import toml
    except ImportError:
        raise RuntimeError("toml library not installed. Install with 'pip install toml'.")
    with open(path, "r", encoding="utf-8") as f:
        return toml.load(f)

def extract_jar_emc(jar_path):
    emc_data = {}
    if not jar_path.is_file():
        return emc_data
    with zipfile.ZipFile(jar_path, "r") as jar:
        for name in jar.namelist():
            if name.endswith(".json") and "emc" in name.lower():
                with jar.open(name) as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, dict):
                            emc_data.update(data)
                    except Exception:
                        continue
    return emc_data

def suggest_emc(item_name, default_emc=None):
    # Simple heuristic based on common suffixes
    if default_emc is not None:
        return default_emc
    if "dust" in item_name:
        return 256
    if "nugget" in item_name:
        return 16
    if "ingot" in item_name:
        return 256
    if "ore" in item_name:
        return 128
    # Fallback for unknown items
    return 1

def main(dry_run=False):
    # Load data
    custom = load_json(CUSTOM_EMC_PATH)
    entries = custom.get("entries", [])
    mapping = load_toml(MAPPING_TOML_PATH) if MAPPING_TOML_PATH.is_file() else {}
    processing = load_toml(PROCESSING_TOML_PATH) if PROCESSING_TOML_PATH.is_file() else {}
    jar_emc = extract_jar_emc(INTEGRATION_JAR_PATH)

    # Build lookup for existing EMC values
    emc_lookup = {e["item"]: e["emc"] for e in entries}

    # Identify suspicious entries
    suspicious = []
    high_auto = []  # entries that appear to be auto‑generated high values
    for e in entries:
        emc = e["emc"]
        if emc <= 0:
            suspicious.append((e["item"], emc, "non‑positive"))
        elif emc > HIGH_EMC_THRESHOLD:
            high_auto.append((e["item"], emc))
        # values within normal range are considered fine

    # Find items in integration JAR that are missing from custom EMC (potential missing base items)
    missing = []
    for item, val in jar_emc.items():
        if item not in emc_lookup:
            suggestion = suggest_emc(item, default_emc=val)
            missing.append((item, suggestion))

    # Build corrected entries list
    corrected_entries = []
    for e in entries:
        # Replace high auto‑generated values with a more realistic suggestion
        if e["emc"] > HIGH_EMC_THRESHOLD:
            new_val = suggest_emc(e["item"], default_emc=None)
            corrected_entries.append({"item": e["item"], "emc": new_val, "suggested": True, "original": e["emc"]})
        else:
            corrected_entries.append(e)
    # Append missing items detected from the JAR
    for item, sugg in missing:
        corrected_entries.append({"item": item, "emc": sugg, "suggested": True})

    corrected = {"entries": corrected_entries}

    if not dry_run:
        # Write corrected EMC file
        OUTPUT_CORRECTED.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_CORRECTED, "w", encoding="utf-8") as f:
            json.dump(corrected, f, indent=2)
        # Write report
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("# EMC Audit Report\n\n")
            f.write(f"Total entries processed: {len(entries)}\n\n")
            f.write("## Suspicious entries (non‑positive)\n\n")
            if suspicious:
                for item, emc, reason in suspicious:
                    f.write(f"- {item}: {emc} ({reason})\n")
            else:
                f.write("None detected.\n")
            f.write("\n## Auto‑generated high EMC values replaced\n\n")
            if high_auto:
                for item, old_val in high_auto:
                    new_val = suggest_emc(item)
                    f.write(f"- {item}: {old_val} → suggested {new_val}\n")
            else:
                f.write("None detected.\n")
            f.write("\n## Missing items added from integration JAR\n\n")
            for item, val in missing:
                f.write(f"- {item}: suggested EMC = {val}\n")
        # Write merged base EMC file for reference
        BASE_EMC_PATH.parent.mkdir(parents=True, exist_ok=True)
        base_emc = {**jar_emc, **emc_lookup}
        with open(BASE_EMC_PATH, "w", encoding="utf-8") as f:
            json.dump(base_emc, f, indent=2)
        print("Extraction and audit completed (high values handled).")
    else:
        print("Dry run completed – no files written.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract EMC data and generate audit report (with high‑value handling).")
    parser.add_argument("--dry-run", action="store_true", help="Do not write any files.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
