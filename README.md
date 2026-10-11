# ⚡ EchoHUD: Stealth Real-Time AI Meeting & Interview Teleprompter

**EchoHUD** is an open-source, lightweight implementation of the core technology behind tools like Cluely. It listens to incoming meeting audio in real time, monitors live speech, and projects discreet, streaming talking points on a translucent desktop HUD that is excluded from screen capture.

---

## 🚀 Key Features

* **🎧 Direct Audio Loopback (WASAPI):** Listens to meeting audio (Zoom, Google Meet, Microsoft Teams) directly through Windows WASAPI loopback without needing an external bot to join the call. Also supports microphone input.
* **👻 Screen-Share Invisibility (Stealth Mode):** Uses native Windows API (`SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE`) so the HUD overlay is visible on your monitor but completely omitted from screen sharing and recording software (Zoom, Teams, Discord, OBS).
* **⚡ Real-Time Streaming Teleprompter:** Generates concise, bulleted talking points and code snippets rather than long scripts, making it effortless to glance and speak naturally.
* **🌐 Multiple AI Providers Supported:**
  * **Demo Mode:** Zero-configuration instant simulation with realistic technical answers.
  * **Google Gemini:** `gemini-2.0-flash` / `gemini-1.5-flash` with vision support.
  * **Groq Cloud:** Ultra-low latency Llama-3.3-70B inference (~150ms).
  * **OpenAI:** `gpt-4o-mini` / `gpt-4o`.
  * **Ollama:** 100% local and private offline LLMs (e.g. Llama 3.2).
* **📸 Screen Snip (Vision Solver):** Instantly captures on-screen code problems or quiz questions and streams solutions.
* **⌨️ Global Hotkeys:**
  * `Ctrl + Alt + H`: Minimize to floating pill / restore HUD.
  * `Ctrl + Alt + S`: Trigger instant Screen Snip & Vision solver.
  * `Ctrl + Alt + C`: Clear question and answer boxes.

---

## 🛠️ Architecture

```
[System Audio / Speakers] 
          │ 
          ▼ (WASAPI Loopback Capture via PyAudioWPatch)
 [Energy VAD & 16kHz Resampler]
          │
          ▼ (Audio Utterance Buffer)
    [Speech-to-Text] ──► (Google STT / Groq Whisper)
          │
          ▼ (Transcribed Question)
  [Streaming LLM]   ──► (Gemini / Groq / OpenAI / Ollama)
          │
          ▼ (Token Stream)
[Translucent HUD Overlay] ──► (Win32: WDA_EXCLUDEFROMCAPTURE)
```

---

## 📦 Installation & Setup

1. **Clone or navigate to the directory:**
   ```powershell
   cd c:\Users\Kirklan\Documents\antigravity\jolly-salk
   ```

2. **Install dependencies:**
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. **Verify all subsystems:**
   ```powershell
   python main.py --test
   ```

---

## 🎯 How to Run

Launch the HUD:
```powershell
python main.py
```

### Quick Usage Tips
1. **Click `⚡ Quick Test`:** Verifies the visual HUD and token streaming immediately without waiting for voice input.
2. **Audio Mode:** By default, it captures system audio (the interviewer). In **Settings (⚙)**, you can toggle between `loopback` (system speakers) and `microphone` (your voice).
3. **Configure API Keys:** Click **⚙** in the title bar to insert your Gemini, Groq, or OpenAI API key. Or select **Demo** mode to use without an API key.
4. **Adjust Opacity:** Use the opacity slider at the bottom to adjust how subtle the overlay looks on your screen.

---

## 🔒 How the Invisibility Mechanism Works

On Windows 10 (version 2004+) and Windows 11, the OS Desktop Window Manager (DWM) provides the function:
```c
SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE); // 0x00000011
```
When this flag is active on the window handle, Windows renders the window to the physical display but strips it out from any capture APIs (such as `BitBlt`, `DirectX Desktop Duplication`, and `Windows.Graphics.Capture`). Consequently, screen sharing over Zoom, Google Meet, or Microsoft Teams displays whatever is *behind* the window instead of the HUD.
