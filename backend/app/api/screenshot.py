import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.db import DB_PATH

logger = logging.getLogger("controlhub.api")

router = APIRouter()

# Same base directory as the SQLite file (DB_PATH's parent), not a second
# hardcoded copy of "/app/data" -- one source of truth for where this
# container's persistent data volume is mounted.
SCREENSHOT_DIR = DB_PATH.parent / "screenshots"


@router.post("/api/screenshot")
async def upload_screenshot(file: UploadFile = File(...)) -> dict:
    # Client-declared content-type only, not a magic-bytes check -- good
    # enough to reject an obviously-wrong upload, not a substitute for
    # treating this as a trusted-network, single-user endpoint (see the
    # summary note on this route having no auth at all).
    if file.content_type != "image/png":
        raise HTTPException(status_code=400, detail="expected a PNG file (image/png)")

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # Server-side clock, not file.filename -- the client's claimed name is
    # never trusted for the save path.
    filename = f"{datetime.now():%Y%m%d_%H%M%S}.png"
    contents = await file.read()
    (SCREENSHOT_DIR / filename).write_bytes(contents)

    logger.info("Screenshot saved: %s", filename)
    return {"status": "ok", "filename": filename}
