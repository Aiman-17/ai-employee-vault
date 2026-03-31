"""
setup_vault.py — Initialize your AI_Employee_Vault for Obsidian.

Usage:
    1. Copy .env.example to .env and set VAULT_PATH to your desired vault location
       e.g. VAULT_PATH=C:/Users/YourName/Documents/AI_Employee_Vault
    2. Run: uv run python scripts/setup_vault.py

What this does:
    - Creates the VAULT_PATH directory (and all subdirectories)
    - Copies vault_template/ contents into VAULT_PATH
    - Skips .gitkeep placeholder files
    - Prints instructions to open the vault in Obsidian

Obsidian requirement:
    Install Obsidian v1.10.6+ from https://obsidian.md/download
    Then open VAULT_PATH as a vault: File → Open vault → Open folder as vault
"""

import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = os.getenv("VAULT_PATH")
TEMPLATE_DIR = Path(__file__).parent.parent / "vault_template"


def setup_vault():
    if not VAULT_PATH:
        print("ERROR: VAULT_PATH is not set in .env")
        print("Copy .env.example to .env and set VAULT_PATH to your desired vault directory.")
        print("Example: VAULT_PATH=C:/Users/YourName/Documents/AI_Employee_Vault")
        raise SystemExit(1)

    vault = Path(VAULT_PATH)

    if not TEMPLATE_DIR.exists():
        print(f"ERROR: vault_template/ not found at {TEMPLATE_DIR}")
        raise SystemExit(1)

    print(f"Setting up vault at: {vault}")

    # Copy all contents from vault_template/ into the vault directory
    copied = 0
    skipped = 0

    for src_path in TEMPLATE_DIR.rglob("*"):
        if src_path.name == ".gitkeep":
            skipped += 1
            continue

        relative = src_path.relative_to(TEMPLATE_DIR)
        dst_path = vault / relative

        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if dst_path.exists():
                print(f"  SKIP (exists): {relative}")
                skipped += 1
            else:
                shutil.copy2(src_path, dst_path)
                print(f"  COPY: {relative}")
                copied += 1

    # Also create directories from .gitkeep entries
    for gitkeep in TEMPLATE_DIR.rglob(".gitkeep"):
        relative_dir = gitkeep.parent.relative_to(TEMPLATE_DIR)
        target_dir = vault / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)

    print()
    print(f"Done. Copied {copied} files, skipped {skipped}.")
    print()
    print("=" * 60)
    print("NEXT STEPS — Open your vault in Obsidian:")
    print("=" * 60)
    print(f"  1. Install Obsidian v1.10.6+ from https://obsidian.md/download")
    print(f"  2. Open Obsidian -> File -> Open vault -> Open folder as vault")
    print(f"  3. Select this folder: {vault}")
    print(f"  4. Pin Dashboard.md to the sidebar for your daily overview")
    print()
    print("Your AI Employee vault is ready.")


if __name__ == "__main__":
    setup_vault()
