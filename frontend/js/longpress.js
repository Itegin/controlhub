const LONG_PRESS_MS = 500;
const MOVE_CANCEL_PX = 10;

// A stationary pointerdown held past LONG_PRESS_MS fires onLongPress instead
// of onTap. Movement past MOVE_CANCEL_PX before then cancels the timer --
// without this, a drag gesture starting on the tile would be misread as a
// stationary hold instead of a drag.
export function attachLongPress(element, onLongPress, onTap) {
  let timer = null;
  let startX = 0;
  let startY = 0;
  let firedLongPress = false;

  function clearTimer() {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  }

  element.addEventListener("pointerdown", (event) => {
    firedLongPress = false;
    startX = event.clientX;
    startY = event.clientY;
    clearTimer();
    timer = setTimeout(() => {
      firedLongPress = true;
      timer = null;
      onLongPress();
    }, LONG_PRESS_MS);
  });

  element.addEventListener("pointermove", (event) => {
    if (timer === null) {
      return;
    }
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    if (Math.hypot(dx, dy) > MOVE_CANCEL_PX) {
      clearTimer();
    }
  });

  element.addEventListener("pointerup", () => {
    const wasLongPress = firedLongPress;
    clearTimer();
    if (!wasLongPress) {
      onTap();
    }
  });

  element.addEventListener("pointercancel", clearTimer);
  element.addEventListener("pointerleave", clearTimer);
}
