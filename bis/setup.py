"""Store the Anthropic API key for the test bench, typed in hidden, never shown.

  python -m bis.setup

The key goes to ~/.config/build-it-small/anthropic.env (mode 600), outside every repository.
Use a key made for this bench, with a monthly spend limit set in the Anthropic Console.
"""
import getpass
import os
from pathlib import Path

KEY_FILE = Path.home() / ".config" / "build-it-small" / "anthropic.env"


def load_key():
    if not KEY_FILE.exists():
        return None
    if KEY_FILE.stat().st_mode & 0o077:
        raise SystemExit(f"{KEY_FILE} is readable by others. Run: chmod 600 {KEY_FILE}")
    for line in KEY_FILE.read_text().splitlines():
        if line.startswith("BIS_ANTHROPIC_KEY="):
            return line.split("=", 1)[1].strip()
    return None


def main():
    key = getpass.getpass("Anthropic API key for the test bench (hidden): ").strip()
    if not key.startswith("sk-ant-"):
        raise SystemExit("That doesn't look like an Anthropic API key. Nothing saved.")
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(f"BIS_ANTHROPIC_KEY={key}\n")
    print(f"Saved to {KEY_FILE} (only you can read it).")


if __name__ == "__main__":
    main()
