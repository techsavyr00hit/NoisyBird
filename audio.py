from typing import Optional, List
import numpy as np
import sounddevice as sd

class MicReader:
    _last_volume: float = 0.0

    @staticmethod
    def _audio_cb(indata, frames, time_info, status):
        if status:
            print("Audio status:", status)
        try:
            rms = float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))
        except Exception as e:
            print("audio_cb error:", e)
            rms = 0.0
        MicReader._last_volume = rms

    def __init__(self):
        self.stream: Optional[sd.InputStream] = None

    def start(self):
        try:
            try:
                dev_info = sd.query_devices(kind='input')
                samplerate = int(dev_info['default_samplerate'])
            except Exception:
                samplerate = 44100
            self.stream = sd.InputStream(callback=MicReader._audio_cb,
                                         channels=1,
                                         samplerate=samplerate,
                                         blocksize=1024,
                                         dtype='float32')
            self.stream.start()
            print("Microphone stream started (samplerate:", samplerate, ")")
        except Exception as e:
            print("Failed to start microphone stream:", e)
            self.stream = None

    def stop(self):
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
        except Exception as e:
            print("Error stopping microphone:", e)
            self.stream = None

    def get_volume(self) -> float:
        return MicReader._last_volume

class VolumeSmoother:
    def __init__(self, window: int = 6):
        self.window = max(1, int(window))
        self.history: List[float] = []

    def add(self, v: float):
        self.history.append(float(v))
        if len(self.history) > self.window:
            self.history.pop(0)

    def smooth(self) -> float:
        if not self.history:
            return 0.0
        return sum(self.history) / len(self.history)
#bbr