from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import time

mic = AudioUtilities.GetMicrophone()
iface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
vol = cast(iface, POINTER(IAudioEndpointVolume))

print("Читаю мут каждую секунду. Ctrl+C для выхода.")
while True:
    print("muted =", vol.GetMute())
    time.sleep(1)
