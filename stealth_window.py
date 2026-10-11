"""
Stealth HUD Window for EchoHUD.
Implements:
1. Frameless, translucent, always-on-top custom UI via CustomTkinter.
2. Win32 SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE) to hide from screen shares.
3. Live audio VU meter, streaming question & answer boxes.
4. Window dragging, collapsing, click-through toggle, and settings dialog.
"""

import sys
import ctypes
import tkinter as tk
import customtkinter as ctk
from PIL import Image

# Win32 Constants
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, config, on_save_callback):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.on_save_callback = on_save_callback

        self.title("EchoHUD Settings")
        self.geometry("480x560")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._build_ui()

    def _build_ui(self):
        pad = 12

        title_lbl = ctk.CTkLabel(self, text="⚙️ Configuration & AI Settings", font=ctk.CTkFont(size=16, weight="bold"))
        title_lbl.pack(pady=(16, 10))

        scroll = ctk.CTkScrollableFrame(self, width=440, height=430)
        scroll.pack(fill="both", expand=True, padx=pad, pady=(0, pad))

        # Audio Source
        ctk.CTkLabel(scroll, text="Audio Input Source:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 2))
        self.audio_mode_var = ctk.StringVar(value=self.config.get("audio_mode", "loopback"))
        audio_menu = ctk.CTkOptionMenu(scroll, values=["loopback", "microphone"], variable=self.audio_mode_var)
        audio_menu.pack(fill="x", pady=(0, 10))

        # AI Provider
        ctk.CTkLabel(scroll, text="AI Provider:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 2))
        self.provider_var = ctk.StringVar(value=self.config.get("ai_provider", "demo"))
        provider_menu = ctk.CTkOptionMenu(
            scroll,
            values=["demo", "gemini", "groq", "openai", "ollama"],
            variable=self.provider_var,
            command=self._on_provider_change
        )
        provider_menu.pack(fill="x", pady=(0, 10))

        # API Keys Frame
        self.keys_frame = ctk.CTkFrame(scroll)
        self.keys_frame.pack(fill="x", pady=6)

        ctk.CTkLabel(self.keys_frame, text="Gemini API Key:").pack(anchor="w", padx=8, pady=(4, 1))
        self.gemini_key_entry = ctk.CTkEntry(self.keys_frame, placeholder_text="AIzaSy...", show="*")
        self.gemini_key_entry.insert(0, self.config.get("gemini_api_key", ""))
        self.gemini_key_entry.pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkLabel(self.keys_frame, text="Groq API Key:").pack(anchor="w", padx=8, pady=(4, 1))
        self.groq_key_entry = ctk.CTkEntry(self.keys_frame, placeholder_text="gsk_...", show="*")
        self.groq_key_entry.insert(0, self.config.get("groq_api_key", ""))
        self.groq_key_entry.pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkLabel(self.keys_frame, text="OpenAI API Key:").pack(anchor="w", padx=8, pady=(4, 1))
        self.openai_key_entry = ctk.CTkEntry(self.keys_frame, placeholder_text="sk-...", show="*")
        self.openai_key_entry.insert(0, self.config.get("openai_api_key", ""))
        self.openai_key_entry.pack(fill="x", padx=8, pady=(0, 6))

        # Prompt Preset
        ctk.CTkLabel(scroll, text="System Prompt Preset:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 2))
        self.prompt_preset_var = ctk.StringVar(value=self.config.get("system_prompt_preset", "micro1_writer_editor"))
        prompt_menu = ctk.CTkOptionMenu(
            scroll,
            values=["micro1_graphic_design", "micro1_simulation_expert", "micro1_video_annotation", "micro1_writer_editor", "micro1_robotics", "kirklan_profile", "everyday_person", "software_engineer", "general_interview", "sales_call", "custom"],
            variable=self.prompt_preset_var
        )
        prompt_menu.pack(fill="x", pady=(0, 10))

        # Custom Prompt Box
        ctk.CTkLabel(scroll, text="Custom System Prompt:").pack(anchor="w", pady=(4, 2))
        self.custom_prompt_text = ctk.CTkTextbox(scroll, height=80, wrap="word")
        self.custom_prompt_text.insert("1.0", self.config.get("custom_system_prompt", ""))
        self.custom_prompt_text.pack(fill="x", pady=(0, 10))

        # Stealth Mode Checkbox
        self.stealth_var = ctk.BooleanVar(value=self.config.get("stealth_mode", True))
        self.stealth_cb = ctk.CTkCheckBox(scroll, text="Stealth Mode (Hide from Zoom/Teams/Screenshare)", variable=self.stealth_var)
        self.stealth_cb.pack(anchor="w", pady=6)

        # Save Button
        save_btn = ctk.CTkButton(self, text="Save & Apply Settings", command=self._save_and_close, fg_color="#10B981", hover_color="#059669")
        save_btn.pack(fill="x", padx=pad, pady=10)

    def _on_provider_change(self, choice):
        pass

    def _save_and_close(self):
        self.config["audio_mode"] = self.audio_mode_var.get()
        self.config["ai_provider"] = self.provider_var.get()
        self.config["gemini_api_key"] = self.gemini_key_entry.get().strip()
        self.config["groq_api_key"] = self.groq_key_entry.get().strip()
        self.config["openai_api_key"] = self.openai_key_entry.get().strip()
        self.config["system_prompt_preset"] = self.prompt_preset_var.get()
        self.config["custom_system_prompt"] = self.custom_prompt_text.get("1.0", "end-1c").strip()
        self.config["stealth_mode"] = self.stealth_var.get()
        if "selected_model" not in self.config:
            self.config["selected_model"] = {}
        self.config["selected_model"]["gemini"] = "gemini-3.8-flash"
        self.config["selected_model"]["groq"] = "openai/gpt-oss-20b"
        self.config["selected_model"]["openai"] = "gpt-4o-mini"

        if self.on_save_callback:
            self.on_save_callback(self.config)
        self.destroy()


class StealthHUDWindow(ctk.CTk):
    def __init__(self, config, on_request_demo=None, on_request_snip=None, on_settings_changed=None, on_toggle_listen=None, on_request_clipboard=None):
        super().__init__()
        self.config = config
        self.on_request_demo = on_request_demo
        self.on_request_snip = on_request_snip
        self.on_settings_changed = on_settings_changed
        self.on_toggle_listen = on_toggle_listen
        self.on_request_clipboard = on_request_clipboard
        self.is_listening = True

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Window properties - standard window with taskbar icon & focus
        self.title("⚡ EchoHUD | Stealth AI Copilot")
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.config.get("transparency", 0.92))

        # Size and position
        self.full_geometry = self.config.get("window_geometry", "520x620+150+150")
        self.geometry(self.full_geometry)
        self.is_collapsed = False
        self.is_click_through = False

        # Bring window immediately to front
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()

        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self.after(200, self._apply_stealth_mode)
        self.after(500, lambda: (self.lift(), self.focus_force()))

    def _build_ui(self):
        # Outer border frame for stylish dark HUD styling
        self.main_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#13141F", border_width=1, border_color="#2A2D40")
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # 1. Custom Title Bar
        self.title_bar = ctk.CTkFrame(self.main_frame, height=36, corner_radius=8, fg_color="#1B1C2A")
        self.title_bar.pack(fill="x", padx=6, pady=(6, 4))
        self.title_bar.bind("<Button-1>", self._start_move)
        self.title_bar.bind("<B1-Motion>", self._on_drag)

        # Title Label
        self.title_lbl = ctk.CTkLabel(
            self.title_bar,
            text="⚡ EchoHUD",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8"
        )
        self.title_lbl.pack(side="left", padx=10)
        self.title_lbl.bind("<Button-1>", self._start_move)
        self.title_lbl.bind("<B1-Motion>", self._on_drag)

        # Stealth Status Badge
        self.stealth_badge = ctk.CTkLabel(
            self.title_bar,
            text="[STEALTH: ON]" if self.config.get("stealth_mode", True) else "[STEALTH: OFF]",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#10B981" if self.config.get("stealth_mode", True) else "#EF4444"
        )
        self.stealth_badge.pack(side="left", padx=4)

        # Window Controls (Minimize, Settings, Close)
        close_btn = ctk.CTkButton(self.title_bar, text="✕", width=26, height=24, fg_color="transparent",
                                  hover_color="#EF4444", command=self.on_close)
        close_btn.pack(side="right", padx=(2, 6))

        collapse_btn = ctk.CTkButton(self.title_bar, text="—", width=26, height=24, fg_color="transparent",
                                     hover_color="#3B82F6", command=self.toggle_collapse)
        collapse_btn.pack(side="right", padx=2)

        settings_btn = ctk.CTkButton(self.title_bar, text="⚙", width=26, height=24, fg_color="transparent",
                                     hover_color="#3B82F6", command=self.open_settings)
        settings_btn.pack(side="right", padx=2)

        # 2. Audio & Status Bar
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=10, pady=(2, 6))

        self.status_lbl = ctk.CTkLabel(
            self.status_frame,
            text="🟢 Listening (System Loopback)...",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        )
        self.status_lbl.pack(side="left")

        # Audio VU meter bar
        self.audio_meter = ctk.CTkProgressBar(self.status_frame, width=120, height=8, corner_radius=4)
        self.audio_meter.set(0.0)
        self.audio_meter.configure(progress_color="#10B981", fg_color="#222538")
        self.audio_meter.pack(side="right", pady=4)

        # 3. Question Display Card
        q_header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        q_header_frame.pack(fill="x", padx=10, pady=(2, 0))

        ctk.CTkLabel(q_header_frame, text="🗣️ Detected Question:", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#E2E8F0").pack(side="left")

        self.question_box = ctk.CTkTextbox(self.main_frame, height=54, corner_radius=8, fg_color="#1A1B28",
                                           text_color="#F1F5F9", font=ctk.CTkFont(size=12), wrap="word")
        self.question_box.pack(fill="x", padx=10, pady=(2, 8))
        self.question_box.insert("1.0", "Waiting for question from audio...")

        # 4. Answer Display Card
        ans_header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ans_header_frame.pack(fill="x", padx=10, pady=(2, 0))

        ctk.CTkLabel(ans_header_frame, text="💡 AI Teleprompter Talking Points:", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#38BDF8").pack(side="left")

        self.answer_box = ctk.CTkTextbox(self.main_frame, corner_radius=8, fg_color="#181A26",
                                         text_color="#E2E8F0", font=ctk.CTkFont(size=13), wrap="word")
        self.answer_box.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        self.answer_box.insert("1.0", "Ready. Questions detected from meeting audio or screen snips will stream live answers here.")

        # 5. Bottom Controls Bar
        self.bottom_bar = ctk.CTkFrame(self.main_frame, height=36, corner_radius=8, fg_color="#1B1C2A")
        self.bottom_bar.pack(fill="x", padx=8, pady=(0, 6))

        # Start / Stop Listening Button
        self.listen_btn = ctk.CTkButton(
            self.bottom_bar,
            text="⏹ Stop",
            width=68,
            height=26,
            fg_color="#EF4444",
            hover_color="#DC2626",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_toggle_listen_click
        )
        self.listen_btn.pack(side="left", padx=(4, 2), pady=4)

        # Demo Test Button
        demo_btn = ctk.CTkButton(self.bottom_bar, text="⚡ Test", width=60, height=26,
                                 fg_color="#3B82F6", hover_color="#2563EB", command=self._on_demo_click)
        demo_btn.pack(side="left", padx=2, pady=4)

        # Screen Snip Button
        snip_btn = ctk.CTkButton(self.bottom_bar, text="📸 Snip", width=68, height=26,
                                 fg_color="#8B5CF6", hover_color="#7C3AED", command=self._on_snip_click)
        snip_btn.pack(side="left", padx=2, pady=4)

        # Analyze Copied Text Button (for browser exercise text)
        clip_btn = ctk.CTkButton(self.bottom_bar, text="📋 Text", width=62, height=26,
                                 fg_color="#6366F1", hover_color="#4F46E5", command=self._on_clipboard_click)
        clip_btn.pack(side="left", padx=2, pady=4)

        # Copy Button
        copy_btn = ctk.CTkButton(self.bottom_bar, text="Copy", width=48, height=26,
                                 fg_color="#334155", hover_color="#475569", command=self.copy_answer)
        copy_btn.pack(side="left", padx=2, pady=4)

        # Clear Button
        clear_btn = ctk.CTkButton(self.bottom_bar, text="🧹 Clear", width=52, height=26,
                                  fg_color="#334155", hover_color="#475569", command=self.clear_content)
        clear_btn.pack(side="left", padx=2, pady=4)

        # Opacity Slider
        opacity_lbl = ctk.CTkLabel(self.bottom_bar, text="Opacity:", font=ctk.CTkFont(size=10), text_color="#94A3B8")
        opacity_lbl.pack(side="left", padx=(8, 2))

        self.opacity_slider = ctk.CTkSlider(self.bottom_bar, from_=0.35, to=1.0, width=70, height=14,
                                            command=self._on_opacity_change)
        self.opacity_slider.set(self.config.get("transparency", 0.92))
        self.opacity_slider.pack(side="left", padx=2)

    def _start_move(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        x = self.winfo_x() - self._drag_start_x + event.x
        y = self.winfo_y() - self._drag_start_y + event.y
        self.geometry(f"+{x}+{y}")

    def _on_opacity_change(self, val):
        self.attributes("-alpha", float(val))
        self.config["transparency"] = float(val)

    def _apply_stealth_mode(self):
        """Applies Windows native SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)."""
        if sys.platform != "win32":
            return
        enabled = self.config.get("stealth_mode", True)
        affinity = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
        try:
            inner_hwnd = self.winfo_id()
            parent_hwnd = ctypes.windll.user32.GetParent(inner_hwnd) or inner_hwnd
            ctypes.windll.user32.SetWindowDisplayAffinity(inner_hwnd, affinity)
            res = ctypes.windll.user32.SetWindowDisplayAffinity(parent_hwnd, affinity)
            print(f"[Stealth] SetWindowDisplayAffinity({affinity}): {'Success' if res else 'Failed'}")
        except Exception as e:
            print(f"[Stealth] Error setting display affinity: {e}")

    def update_audio_level(self, level_0_to_100):
        """Thread-safe update of VU meter."""
        self.after(0, lambda: self.audio_meter.set(level_0_to_100 / 100.0))

    def update_status(self, text, color="#94A3B8"):
        """Thread-safe status text update."""
        self.after(0, lambda: self.status_lbl.configure(text=text, text_color=color))

    def set_question(self, text):
        """Thread-safe update of question text."""
        def _update():
            self.question_box.delete("1.0", "end")
            self.question_box.insert("1.0", text)
        self.after(0, _update)

    def clear_answer(self):
        """Thread-safe clear answer box."""
        def _clear():
            self.answer_box.delete("1.0", "end")
        self.after(0, _clear)

    def append_answer_token(self, token):
        """Thread-safe token streaming into answer box."""
        clean_token = token.replace("\u2011", "-")
        def _append():
            self.answer_box.insert("end", clean_token)
            self.answer_box.see("end")
        self.after(0, _append)

    def set_full_answer(self, text):
        """Thread-safe full answer replace."""
        clean_text = text.replace("\u2011", "-")
        def _set():
            self.answer_box.delete("1.0", "end")
            self.answer_box.insert("1.0", clean_text)
            self.answer_box.see("end")
        self.after(0, _set)

    def toggle_collapse(self):
        """Minimizes into a compact floating pill or restores."""
        if not self.is_collapsed:
            self.full_geometry = self.geometry()
            x = self.winfo_x()
            y = self.winfo_y()
            self.geometry(f"200x42+{x}+{y}")
            self.is_collapsed = True
        else:
            self.geometry(self.full_geometry)
            self.is_collapsed = False

    def clear_content(self):
        self.question_box.delete("1.0", "end")
        self.question_box.insert("1.0", "Listening for next question...")
        self.answer_box.delete("1.0", "end")
        self.update_status("🟢 Listening (System Loopback)...", "#94A3B8")

    def copy_answer(self):
        text = self.answer_box.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_status("📋 Copied answer to clipboard!", "#38BDF8")

    def open_settings(self):
        SettingsDialog(self, self.config, on_save_callback=self._on_settings_saved)

    def _on_settings_saved(self, new_cfg):
        self.config = new_cfg
        self._apply_stealth_mode()
        badge_text = "[STEALTH: ON]" if self.config.get("stealth_mode", True) else "[STEALTH: OFF]"
        badge_color = "#10B981" if self.config.get("stealth_mode", True) else "#EF4444"
        self.stealth_badge.configure(text=badge_text, text_color=badge_color)
        if self.on_settings_changed:
            self.on_settings_changed(new_cfg)

    def _on_demo_click(self):
        if self.on_request_demo:
            self.on_request_demo()

    def _on_snip_click(self):
        if self.on_request_snip:
            self.on_request_snip()

    def _on_clipboard_click(self):
        if self.on_request_clipboard:
            self.on_request_clipboard()

    def set_listening_state(self, is_listening: bool):
        """Thread-safe update of listening state UI."""
        self.is_listening = is_listening
        def _update():
            if self.is_listening:
                self.listen_btn.configure(text="⏹ Stop", fg_color="#EF4444", hover_color="#DC2626")
                mode = self.config.get("audio_mode", "loopback")
                self.update_status(f"🟢 Listening ({mode})...", "#10B981")
            else:
                self.listen_btn.configure(text="▶ Start", fg_color="#10B981", hover_color="#059669")
                self.update_status("🔴 Stopped (Not Listening)", "#EF4444")
                self.audio_meter.set(0.0)
        self.after(0, _update)

    def _on_toggle_listen_click(self):
        if self.on_toggle_listen:
            self.on_toggle_listen()

    def on_close(self):
        self.destroy()
