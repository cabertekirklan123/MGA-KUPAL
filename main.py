"""
EchoHUD: Stealth AI Meeting & Interview Teleprompter.
Main application runner and pipeline coordinator.
"""

import sys
import time
import argparse
import threading

# Ensure safe console printing on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pynput import keyboard

import config
from audio_capture import AudioCaptureEngine
from speech_engine import SpeechEngine
from ai_engine import AIEngine
from screen_engine import ScreenEngine
from stealth_window import StealthHUDWindow

DEMO_QUESTIONS = [
    "Explain how the React Virtual DOM works and what reconciliation is.",
    "Why do relational databases use B+ Trees instead of regular Binary Search Trees for indexes?",
    "Explain the CAP theorem and the difference between CP and AP distributed databases.",
    "How would you solve Two Sum in optimal time complexity?"
]
demo_idx = 0


class EchoHUDApp:
    def __init__(self):
        self.cfg = config.load_config()

        self.speech_engine = SpeechEngine(self.cfg)
        self.ai_engine = AIEngine(self.cfg)
        self.audio_engine = None
        self.window = None
        self.hotkey_listener = None

    def start(self):
        print("=" * 60)
        print("⚡ EchoHUD: Stealth Real-Time AI Teleprompter Starting...")
        print(f"• Audio Mode: {self.cfg.get('audio_mode', 'loopback')}")
        print(f"• AI Provider: {self.cfg.get('ai_provider', 'demo')}")
        print(f"• Stealth Exclude From Capture: {self.cfg.get('stealth_mode', True)}")
        print("=" * 60)

        # 1. Initialize GUI
        self.window = StealthHUDWindow(
            self.cfg,
            on_request_demo=self.trigger_demo_test,
            on_request_snip=self.trigger_screen_snip,
            on_request_clipboard=self.trigger_clipboard_analysis,
            on_settings_changed=self.on_settings_reloaded,
            on_toggle_listen=self.toggle_listening
        )

        # 2. Initialize Audio Capture Engine
        self.audio_engine = AudioCaptureEngine(
            mode=self.cfg.get("audio_mode", "loopback"),
            energy_threshold=self.cfg.get("energy_threshold", 400),
            silence_seconds=self.cfg.get("silence_seconds", 1.2),
            on_speech_captured=self.on_speech_captured,
            on_level_update=self.window.update_audio_level
        )
        self.audio_engine.start()

        # 3. Setup Global Hotkeys
        self._setup_hotkeys()

        # 4. Handle Window Close
        self.window.protocol("WM_DELETE_WINDOW", self.shutdown)

        # 5. Run GUI Mainloop
        try:
            self.window.mainloop()
        except KeyboardInterrupt:
            self.shutdown()

    def _setup_hotkeys(self):
        """Registers system-wide hotkeys for stealth control."""
        try:
            hotkeys = {
                '<ctrl>+<alt>+h': self._on_hotkey_toggle_hud,
                '<ctrl>+<alt>+s': self.trigger_screen_snip,
                '<ctrl>+<alt>+v': self.trigger_clipboard_analysis,
                '<ctrl>+<alt>+c': self._on_hotkey_clear,
                '<ctrl>+<alt>+<space>': self.toggle_listening,
                '<ctrl>+<alt>+p': self.toggle_listening
            }
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            print("[Hotkeys] Registered: Ctrl+Alt+H (Toggle), Ctrl+Alt+Space/P (Listen), Ctrl+Alt+S (Snip), Ctrl+Alt+V (Clipboard), Ctrl+Alt+C (Clear)")
        except Exception as e:
            print(f"[Hotkeys] Could not register global hotkeys: {e}")

    def toggle_listening(self):
        """Toggles between listening and stopped states."""
        if self.audio_engine:
            is_listening = self.audio_engine.toggle()
            if self.window:
                self.window.set_listening_state(is_listening)
            print(f"[Audio] Listening state: {'RESUMED' if is_listening else 'STOPPED'}")

    def _on_hotkey_toggle_hud(self):
        if self.window:
            self.window.toggle_collapse()

    def _on_hotkey_clear(self):
        if self.window:
            self.window.clear_content()

    def on_speech_captured(self, wav_bytes):
        """Called when audio engine finishes capturing a speech utterance."""
        if not self.window:
            return

        self.window.update_status("🟡 Transcribing interviewer voice...", "#F59E0B")
        text = self.speech_engine.transcribe(wav_bytes)

        if text and len(text.strip()) > 3:
            print(f"[Speech Detected]: {text}")
            self.window.set_question(text)
            self.window.update_status("🟡 AI Generating talking points...", "#F59E0B")
            self.window.clear_answer()

            def _query_ai():
                self.ai_engine.ask(text, on_token=self.window.append_answer_token)
                self.window.update_status("🟢 Ready (Listening)...", "#10B981")

            threading.Thread(target=_query_ai, daemon=True).start()
        else:
            self.window.update_status("🟢 Listening (System Loopback)...", "#94A3B8")

    def trigger_demo_test(self):
        """Simulates an incoming question to test the full pipeline and UI."""
        global demo_idx
        question = DEMO_QUESTIONS[demo_idx % len(DEMO_QUESTIONS)]
        demo_idx += 1

        print(f"[Demo] Simulating question: '{question}'")
        self.window.set_question(question)
        self.window.update_status("🟡 AI Generating talking points...", "#F59E0B")
        self.window.clear_answer()

        def _query_demo():
            self.ai_engine.ask(question, on_token=self.window.append_answer_token)
            self.window.update_status("🟢 Ready (Listening)...", "#10B981")

        threading.Thread(target=_query_demo, daemon=True).start()

    def trigger_screen_snip(self):
        """Captures active screen and queries the AI model with vision/context."""
        self.window.update_status("📸 Capturing screen...", "#8B5CF6")
        img_bytes = ScreenEngine.capture_fullscreen()

        preset = self.cfg.get("system_prompt_preset", "")
        if "graphic" in preset or "design" in preset:
            prompt = (
                "Analyze the graphic design, layout, visual asset, or assessment on screen.\n"
                "Evaluate the visual hierarchy, typography, color harmony, composition, and alignment.\n"
                "CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        elif "sim" in preset:
            prompt = (
                "Analyze the 3D simulation task, physics question, or asset diagram on screen.\n"
                "State the technical solution, platform considerations (Isaac Sim, MuJoCo, Gazebo), and physics parameters.\n"
                "CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        elif "video" in preset or "annotation" in preset:
            prompt = (
                "Analyze the video/data annotation task, assessment question, or guidelines on screen.\n"
                "State the correct annotation decision, explain any edge cases, and give a clear rationale.\n"
                "CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        elif "writer" in preset or "editor" in preset:
            prompt = (
                "Analyze the text exercise on screen.\n"
                "Spot any artificial filler, assess clarity and grammar, and provide the polished rewrite.\n"
                "CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        else:
            prompt = (
                "Analyze the question or task on screen and provide the optimal answer.\n"
                "CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        self.window.set_question(f"[Screen Exercise]: {prompt[:60]}...")
        self.window.update_status("🟡 AI Analyzing screenshot...", "#F59E0B")
        self.window.clear_answer()

        def _query_screen():
            self.ai_engine.ask(prompt, image_bytes=img_bytes, on_token=self.window.append_answer_token)
            self.window.update_status("🟢 Ready (Listening)...", "#10B981")

        threading.Thread(target=_query_screen, daemon=True).start()

    def trigger_clipboard_analysis(self):
        """Analyzes text copied to the clipboard (e.g. from an on-screen writing/editing test)."""
        try:
            copied_text = self.window.clipboard_get().strip()
        except Exception:
            copied_text = ""

        if not copied_text:
            self.window.update_status("⚠️ Clipboard is empty! Copy test text first (Ctrl+C).", "#EF4444")
            return

        print(f"[Clipboard] Analyzing {len(copied_text)} chars from clipboard...")
        self.window.set_question(f"[Exercise Text]: {copied_text[:85]}...")
        self.window.update_status("🟡 AI Analyzing test passage...", "#F59E0B")
        self.window.clear_answer()

        preset = self.cfg.get("system_prompt_preset", "")
        if "graphic" in preset or "design" in preset:
            prompt = (
                f"Evaluate this design question, critique prompt, or creative brief for the Graphic Design role:\n\n"
                f"\"\"\"\n{copied_text}\n\"\"\"\n\n"
                f"Provide the exact design critique, rationale, or visual recommendation.\n"
                f"CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        elif "sim" in preset:
            prompt = (
                f"Evaluate this simulation or technical question for the Simulation Expert role:\n\n"
                f"\"\"\"\n{copied_text}\n\"\"\"\n\n"
                f"State the exact technical answer, physics parameter tuning, or troubleshooting approach.\n"
                f"CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        elif "video" in preset or "annotation" in preset:
            prompt = (
                f"Evaluate this question, guideline, or text for the Video Data Annotation Specialist role (or English assessment):\n\n"
                f"\"\"\"\n{copied_text}\n\"\"\"\n\n"
                f"State the correct decision and rationale.\n"
                f"CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )
        else:
            prompt = (
                f"Carefully evaluate this text for the interview/exercise:\n\n"
                f"\"\"\"\n{copied_text}\n\"\"\"\n\n"
                f"Provide a clear critique and polished rewrite.\n"
                f"CRITICAL FORMAT: Answer in one continuous, natural paragraph ready to read aloud directly. Absolutely no bullet points, dashes, numbers, or markdown formatting."
            )

        def _query_clipboard():
            self.ai_engine.ask(prompt, on_token=self.window.append_answer_token)
            self.window.update_status("🟢 Ready (Listening)...", "#10B981")

        threading.Thread(target=_query_clipboard, daemon=True).start()

    def on_settings_reloaded(self, new_cfg):
        """Restart audio engine or update engines when settings change."""
        self.cfg = new_cfg
        config.save_config(new_cfg)
        self.speech_engine.config = new_cfg
        self.ai_engine.config = new_cfg

        # Restart audio capture with new mode if changed
        if self.audio_engine:
            self.audio_engine.stop()
            self.audio_engine = AudioCaptureEngine(
                mode=self.cfg.get("audio_mode", "loopback"),
                energy_threshold=self.cfg.get("energy_threshold", 400),
                silence_seconds=self.cfg.get("silence_seconds", 1.2),
                on_speech_captured=self.on_speech_captured,
                on_level_update=self.window.update_audio_level
            )
            self.audio_engine.start()
            print("[Settings] Audio capture restarted with new settings.")

    def shutdown(self):
        """Clean shutdown saving config."""
        print("[EchoHUD] Shutting down...")
        if self.audio_engine:
            self.audio_engine.stop()
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        if self.window:
            self.cfg["window_geometry"] = self.window.geometry()
            config.save_config(self.cfg)
            self.window.destroy()
        sys.exit(0)


def run_cli_test():
    """Automated headless test verifying all engine components."""
    print("=" * 60)
    print("⚡ Running EchoHUD Automated Subsystem Verification")
    print("=" * 60)

    # 1. Config Test
    cfg = config.load_config()
    print("✓ Config loaded successfully.")

    # 2. AI Engine Test
    ai = AIEngine(cfg)
    test_q = "Explain the CAP theorem"
    tokens = []
    resp = ai.ask(test_q, on_token=lambda t: tokens.append(t))
    print(f"✓ AI Engine generated {len(tokens)} streaming tokens successfully.")
    assert len(resp) > 0

    # 3. Audio Diagnostics
    audio_eng = AudioCaptureEngine()
    devs = audio_eng.get_devices_info()
    print(f"✓ Detected Loopback Device: {devs['loopback']}")
    print(f"✓ Detected Microphone Device: {devs['microphone']}")

    # 4. Speech Recognition Test
    speech_eng = SpeechEngine(cfg)
    print("✓ Speech recognition initialized.")

    print("\n[SUCCESS] All subsystems verified and operating normally!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EchoHUD: Stealth AI Teleprompter")
    parser.add_argument("--test", action="store_true", help="Run automated subsystem verification")
    args = parser.parse_args()

    if args.test:
        run_cli_test()
    else:
        app = EchoHUDApp()
        app.start()
