from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


def _get_mic_volume_interface() -> IAudioEndpointVolume:
    # Re-activated on every call rather than cached: the default recording
    # device can change (unplugged headset, etc.) between polls.
    mic = AudioUtilities.GetMicrophone()
    interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_mic_muted() -> bool:
    return bool(_get_mic_volume_interface().GetMute())


def set_mic_muted(muted: bool) -> None:
    _get_mic_volume_interface().SetMute(muted, None)


def handle_audio_mute_toggle(params: dict) -> dict:
    try:
        set_mic_muted(not get_mic_muted())
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
