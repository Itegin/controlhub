import os
import subprocess
from ctypes import POINTER, cast
from pathlib import Path

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, EDataFlow, ERole, IAudioEndpointVolume

_DATA_FLOWS = {
    "microphone": EDataFlow.eCapture.value,
    "speaker": EDataFlow.eRender.value,
}

# Bundled next to the agent (see agents/windows/tools/), resolved from this
# file's own location rather than a relative path so it doesn't depend on
# the process's cwd when the agent is launched (e.g. as a scheduled task).
_SOUND_VOLUME_VIEW = Path(__file__).resolve().parent.parent / "tools" / "SoundVolumeView.exe"


def _get_volume_interface(device: str) -> IAudioEndpointVolume:
    # Re-activated on every call rather than cached: the default device for
    # a given role can change (unplugged headset, etc.) between polls.
    #
    # Goes through the raw device enumerator rather than pycaw's
    # AudioUtilities.GetMicrophone() / GetSpeakers() convenience methods --
    # those two are NOT symmetric: GetMicrophone() returns a raw IMMDevice
    # (which has .Activate()), but GetSpeakers() wraps that same kind of
    # result in pycaw's higher-level AudioDevice helper, which has no
    # .Activate() at all (confirmed by hand: calling .Activate() on it
    # raises AttributeError). Enumerating directly gives the same raw
    # IMMDevice type for both roles, so one code path works for both.
    enumerator = AudioUtilities.GetDeviceEnumerator()
    endpoint = enumerator.GetDefaultAudioEndpoint(_DATA_FLOWS[device], ERole.eMultimedia.value)
    interface = endpoint.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_muted(device: str) -> bool:
    return bool(_get_volume_interface(device).GetMute())


def set_muted(device: str, muted: bool) -> None:
    _get_volume_interface(device).SetMute(muted, None)


def get_volume(device: str) -> int:
    return round(_get_volume_interface(device).GetMasterVolumeLevelScalar() * 100)


def set_volume(device: str, value: int) -> None:
    _get_volume_interface(device).SetMasterVolumeLevelScalar(value / 100, None)


def handle_audio_mute_toggle(params: dict) -> dict:
    try:
        device = params["device"]
        set_muted(device, not get_muted(device))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_audio_volume_set(params: dict) -> dict:
    try:
        set_volume(params["device"], params["value"])
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_audio_switch(params: dict) -> dict:
    try:
        # OUTPUT_DEVICE_PRIMARY/SECONDARY hold SoundVolumeView's full
        # "Command-Line Friendly ID" (DriverName\Device\Name\Direction), not
        # a bare device Name -- a bare Name isn't a safe identifier here.
        # E.g. "Динамики" is both the actual Realtek render device AND a
        # capture-side subunit name that shows up under an unrelated fifine
        # Microphone device in the same SoundVolumeView listing; passing
        # just "Динамики" would be ambiguous. Passed through to subprocess
        # exactly as read from the environment -- do not shorten, split, or
        # otherwise parse these strings, the full ID is what disambiguates.
        primary = os.getenv("OUTPUT_DEVICE_PRIMARY")
        secondary = os.getenv("OUTPUT_DEVICE_SECONDARY")
        if not primary or not secondary:
            return {"status": "error", "message": "OUTPUT_DEVICE_PRIMARY/SECONDARY not set"}

        # /SwitchDefault toggles: whichever of the two isn't currently the
        # default becomes it. Trailing 0 = render/multimedia role.
        #
        # timeout=4 is deliberate, not decorative: this runs synchronously
        # inside the agent's single receive loop (see _receive_loop in
        # agent.py), so an unbounded subprocess call here would stall the
        # entire agent -- not just this command, but poll_loop's ticks and
        # every other message too -- if SoundVolumeView.exe ever wedges (a
        # device name that no longer matches anything popping a GUI dialog
        # instead of exiting is the likely way that happens). Kept under
        # the backend's own 5s execute timeout (see CLAUDE.md) rather than
        # equal to it, so on a real hang this handler's own "error" result
        # has a chance to win the race and reach the client before the
        # backend's synthetic "timeout" result does; if both fire, the
        # client just sees the same req_id resolve twice, which is harmless
        # today but worth knowing about.
        subprocess.run(
            [str(_SOUND_VOLUME_VIEW), "/SwitchDefault", primary, secondary, "0"],
            check=True,
            timeout=4,
        )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
