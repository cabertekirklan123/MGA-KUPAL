"""
Speech-to-Text Engine for EchoHUD.
Transcribes WAV audio buffers into text using:
1. Google Speech Recognition (free, built-in, zero API key required)
2. Groq Whisper API (whisper-large-v3-turbo, ultra-fast cloud STT)
3. OpenAI Whisper API (whisper-1)
"""

import io
import requests
import speech_recognition as sr


class SpeechEngine:
    def __init__(self, config=None):
        self.config = config or {}
        self.recognizer = sr.Recognizer()
        # Tune recognizer settings
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = False

    def transcribe(self, wav_bytes):
        """
        Transcribe raw WAV bytes to text.
        Returns transcribed string or None if unparseable/silent.
        """
        if not wav_bytes or len(wav_bytes) < 1000:
            return None

        # Check if Groq API key is configured for ultra-fast whisper
        groq_key = self.config.get("groq_api_key")
        if groq_key:
            try:
                text = self._transcribe_groq(wav_bytes, groq_key)
                if text:
                    return text
            except Exception as e:
                print(f"[STT] Groq Whisper failed ({e}), falling back to Google STT")

        # Default fallback: Free built-in Google Speech Recognition
        return self._transcribe_google(wav_bytes)

    def _transcribe_google(self, wav_bytes):
        """Transcribe using Google Speech Recognition (Free built-in API)."""
        try:
            with io.BytesIO(wav_bytes) as audio_file:
                with sr.AudioFile(audio_file) as source:
                    audio_data = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio_data)
                    return text.strip() if text else None
        except sr.UnknownValueError:
            # Normal: audio was inaudible, noise, or silence
            return None
        except sr.RequestError as e:
            print(f"[STT] Google Speech API network error: {e}")
            return None
        except Exception as e:
            print(f"[STT] Error during transcription: {e}")
            return None

    def _transcribe_groq(self, wav_bytes, api_key):
        """Transcribe using Groq Whisper API (~150ms latency)."""
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {
            "file": ("speech.wav", wav_bytes, "audio/wav")
        }
        data = {
            "model": "whisper-large-v3-turbo",
            "response_format": "json"
        }
        response = requests.post(url, headers=headers, files=files, data=data, timeout=8)
        if response.status_code == 200:
            result = response.json()
            return result.get("text", "").strip()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
