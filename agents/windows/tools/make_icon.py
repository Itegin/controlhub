"""
Converts frontend/icons/icon-180.png into agents/windows/icon.ico for use
as the Desktop shortcut icon created by start_agent.bat.

Requires Pillow (already listed in agents/windows/requirements.txt).

Idempotent: skips conversion if icon.ico already exists and is newer than
icon-180.png, so start_agent.bat can call this on every run for free.
"""

from pathlib import Path

from PIL import Image

AGENT_DIR = Path(__file__).resolve().parent.parent
SOURCE_PNG = AGENT_DIR.parent.parent / "frontend" / "icons" / "icon-180.png"
DEST_ICO = AGENT_DIR / "icon.ico"

ICON_SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]


def main() -> None:
    if not SOURCE_PNG.exists():
        raise FileNotFoundError(f"source icon not found: {SOURCE_PNG}")

    if DEST_ICO.exists() and DEST_ICO.stat().st_mtime >= SOURCE_PNG.stat().st_mtime:
        print(f"{DEST_ICO.name} is up to date, skipping conversion.")
        return

    image = Image.open(SOURCE_PNG)
    image.save(DEST_ICO, format="ICO", sizes=ICON_SIZES)
    print(f"Wrote {DEST_ICO} ({', '.join(f'{w}x{h}' for w, h in ICON_SIZES)}).")


if __name__ == "__main__":
    main()
