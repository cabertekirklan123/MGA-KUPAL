"""
Audio Capture Engine for EchoHUD.
Captures system audio loopback (WASAPI) and/or microphone audio on Windows.
Performs real-time energy-based VAD (Voice Activity Detection), buffers speech,
and triggers transcription when a pause is detected.
"""

import io
import time
import wave
import threading
import numpy as np
import pyaudiowpatch as pyaudio

CHUNK_SIZE = 1024
TARGET_SAMPLE_RATE = 16000


class AudioCaptureEngine:
    def __init__(self, mode="loopback", energy_threshold=400, silence_seconds=1.2,
                 on_speech_captured=None, on_level_update=None):
        """
        :param mode: 'loopback', 'microphone', or 'both'
        :param energy_threshold: RMS amplitude threshold for speech detection
        :param silence_seconds: consecutive seconds of silence to trigger end-of-speech
        :param on_speech_captured: callback(wav_bytes) called when speech segment is ready
        :param on_level_update: callback(level_0_to_100) for UI audio meter
        """
        self.mode = mode
        self.energy_threshold = energy_threshold
        self.silence_seconds = silence_seconds
        self.on_speech_captured = on_speech_captured
        self.on_level_update = on_level_update

        self.p = None
        self.stream = None
        self.is_running = False
        self.is_paused = False
        self._thread = None

        # Speech buffering state
        self._is_speaking = False
        self._speech_buffer = []  # list of numpy arrays
        self._pre_buffer = []     # rolling buffer of ~0.3s before speech to catch initial syllables
        self._last_speech_time = 0
        self._sample_rate = 48000
        self._channels = 2

    def pause(self):
        """Pauses audio listening and clears active speech buffers."""
        self.is_paused = True
        self._is_speaking = False
        self._speech_buffer = []
        if self.on_level_update:
            self.on_level_update(0)

    def resume(self):
        """Resumes audio listening."""
        self.is_paused = False
        self._is_speaking = False
        self._speech_buffer = []

    def toggle(self):
        """Toggles between listening and paused states. Returns True if now listening."""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
        return not self.is_paused

    def get_devices_info(self):
        """Returns diagnostic info about available loopback and microphone devices."""
        p = pyaudio.PyAudio()
        info = {"loopback": None, "microphone": None}
        try:
            try:
                loopback = p.get_default_wasapi_loopback()
                info["loopback"] = {
                    "index": loopback["index"],
                    "name": loopback["name"],
                    "channels": loopback["maxInputChannels"],
                    "rate": int(loopback["defaultSampleRate"])
                }
            except Exception:
                pass

            try:
                mic = p.get_default_input_device_info()
                info["microphone"] = {
                    "index": mic["index"],
                    "name": mic["name"],
                    "channels": mic["maxInputChannels"],
                    "rate": int(mic["defaultSampleRate"])
                }
            except Exception:
                pass
        finally:
            p.terminate()
        return info

    def start(self):
        """Start audio capture in a background thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_capture, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop audio capture cleanly."""
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    def _get_target_device(self, p):
        """Find the selected device according to self.mode."""
        if self.mode == "microphone":
            try:
                return p.get_default_input_device_info()
            except Exception as e:
                print(f"[Audio] Error getting default mic: {e}")
                return None
        else:
            # Default to loopback
            try:
                return p.get_default_wasapi_loopback()
            except Exception as e:
                print(f"[Audio] Warning: Loopback not available ({e}), falling back to mic")
                try:
                    return p.get_default_input_device_info()
                except Exception:
                    return None

    def _run_capture(self):
        """Main audio worker loop."""
        self.p = pyaudio.PyAudio()
        dev_info = self._get_target_device(self.p)
        if not dev_info:
            print("[Audio] No audio device available.")
            self.is_running = False
            return

        self._channels = max(1, dev_info["maxInputChannels"])
        self._sample_rate = int(dev_info["defaultSampleRate"])
        dev_index = dev_info["index"]

        print(f"[Audio] Opened '{dev_info['name']}' at {self._sample_rate}Hz, {self._channels}ch")

        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                input_device_index=dev_index,
                frames_per_buffer=CHUNK_SIZE
            )
        except Exception as e:
            print(f"[Audio] Failed to open stream: {e}")
            self.is_running = False
            return

        # Pre-buffer size: ~0.3s of chunks
        max_pre_chunks = max(3, int((self._sample_rate * 0.3) / CHUNK_SIZE))

        while self.is_running:
            try:
                # Read raw PCM chunk
                raw_data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if not raw_data:
                    continue

                if self.is_paused:
                    if self.on_level_update:
                        self.on_level_update(0)
                    time.sleep(0.02)
                    continue

                # Convert to numpy int16
                samples = np.frombuffer(raw_data, dtype=np.int16)
                if len(samples) == 0:
                    continue

                # Convert to mono if multichannel
                if self._channels > 1:
                    mono = samples.reshape(-1, self._channels).mean(axis=1).astype(np.int16)
                else:
                    mono = samples

                # Calculate RMS Energy
                rms = float(np.sqrt(np.mean(mono.astype(np.float32) ** 2)))

                # Update UI volume level callback (scaled 0-100)
                if self.on_level_update:
                    normalized = min(100, int((rms / 2500.0) * 100))
                    self.on_level_update(normalized)

                now = time.time()
                is_above_threshold = rms >= self.energy_threshold

                if is_above_threshold:
                    if not self._is_speaking:
                        # Speech started! Include pre-buffer to preserve start of word
                        self._is_speaking = True
                        self._speech_buffer = list(self._pre_buffer)
                    self._speech_buffer.append(mono)
                    self._last_speech_time = now
                else:
                    if self._is_speaking:
                        self._speech_buffer.append(mono)
                        # Check if silence timeout exceeded
                        if now - self._last_speech_time > self.silence_seconds:
                            self._is_speaking = False
                            # Package speech if long enough (> 0.6s)
                            total_samples = sum(len(c) for c in self._speech_buffer)
                            min_samples = int(self._sample_rate * 0.6)
                            if total_samples >= min_samples:
                                self._dispatch_speech(self._speech_buffer)
                            self._speech_buffer = []
                    else:
                        # Keep rolling pre-buffer while idle
                        self._pre_buffer.append(mono)
                        if len(self._pre_buffer) > max_pre_chunks:
                            self._pre_buffer.pop(0)

            except Exception as e:
                if self.is_running:
                    print(f"[Audio] Stream error: {e}")
                    time.sleep(0.05)

    def _dispatch_speech(self, chunks):
        """Resamples captured speech to 16kHz mono and outputs in WAV bytes."""
        if not chunks:
            return
        full_audio = np.concatenate(chunks)

        # Resample to TARGET_SAMPLE_RATE (16kHz)
        if self._sample_rate != TARGET_SAMPLE_RATE:
            target_len = int(len(full_audio) * TARGET_SAMPLE_RATE / self._sample_rate)
            indices = np.linspace(0, len(full_audio) - 1, target_len)
            resampled = np.interp(indices, np.arange(len(full_audio)), full_audio).astype(np.int16)
        else:
            resampled = full_audio

        # Create in-memory WAV container
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(TARGET_SAMPLE_RATE)
            wf.writeframes(resampled.tobytes())
        wav_bytes = wav_buf.getvalue()

        # Fire speech captured callback asynchronously
        if self.on_speech_captured:
            threading.Thread(target=self.on_speech_captured, args=(wav_bytes,), daemon=True).start()
