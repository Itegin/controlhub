import io

import mss
from PIL import Image

try:
    import win32clipboard
except ImportError:
    # Only real absence case is pywin32 not being installed -- handled at
    # call time below rather than at import time, so the rest of the agent
    # still starts up and every other handler keeps working.
    win32clipboard = None


def _capture_primary_monitor_image() -> Image.Image:
    with mss.MSS() as sct:
        # monitors[0] is the combined virtual screen across every display,
        # not a single monitor. is_primary isn't guaranteed to land on
        # monitors[1] -- Windows lets any monitor be set as primary, and
        # mss lists them in OS enumeration order, not primary-first -- so
        # search for the flagged one; fall back to index 1 only if a given
        # mss/platform combination ever doesn't populate the flag.
        monitor = next((m for m in sct.monitors[1:] if m.get("is_primary")), sct.monitors[1])
        shot = sct.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.rgb)


def _image_to_dib(image: Image.Image) -> bytes:
    # Windows' CF_DIB clipboard format wants a BITMAPINFOHEADER + color
    # table + pixel data (a "device-independent bitmap"), NOT a full .bmp
    # file -- a full BMP file is that same DIB data with an extra 14-byte
    # BITMAPFILEHEADER glued on the front (signature, file size, reserved
    # fields, pixel-data offset). Pillow only knows how to emit the full
    # file form, so the fix is: save as BMP into memory, then slice off
    # exactly those first 14 bytes. Do not "simplify" this away -- passing
    # the full BMP (with header) to SetClipboardData(CF_DIB, ...) produces
    # a clipboard entry that looks fine in memory but pastes as garbage or
    # nothing in every real app, because CF_DIB readers expect DIB data to
    # start at byte 0, not after a file header that shouldn't be there.
    buffer = io.BytesIO()
    image.save(buffer, "BMP")
    return buffer.getvalue()[14:]


def handle_screenshot(params: dict) -> dict:
    if win32clipboard is None:
        return {"status": "error", "message": "pywin32 is not installed"}

    try:
        image = _capture_primary_monitor_image()
        dib = _image_to_dib(image)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # backend/app/api/screenshot.py (POST /api/screenshot) is intentionally
    # left in place and unused from here -- this handler used to upload the
    # PNG there for remote viewing from the phone; that use case is gone
    # now that this copies straight to the local clipboard instead (see
    # CLAUDE.md/commit notes for the trade-off), but the endpoint is kept
    # in case a future remote-viewable-screenshot feature wants it back.
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
        finally:
            # Runs even if EmptyClipboard/SetClipboardData raises above --
            # an open clipboard that never gets closed blocks every other
            # app's copy/paste on this PC until the lock clears.
            win32clipboard.CloseClipboard()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "ok"}
