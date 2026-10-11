"""
Screen Capture Engine for EchoHUD.
Captures screenshots for vision analysis (e.g. LeetCode questions, slides, diagrams).
Includes safe fallbacks if running in restricted environments.
"""

import io
from PIL import Image, ImageGrab


class ScreenEngine:
    @staticmethod
    def capture_fullscreen():
        """
        Captures the primary screen and returns PNG bytes.
        Returns None if desktop surface is inaccessible.
        """
        # Try PIL ImageGrab first
        try:
            img = ImageGrab.grab(all_screens=False)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            print(f"[Screen] ImageGrab failed ({e}), trying mss...")

        # Fallback to mss
        try:
            import mss
            with mss.MSS() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        except Exception as e:
            print(f"[Screen] Screen capture unavailable in this session: {e}")
            return None
