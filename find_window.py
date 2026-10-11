import ctypes

user32 = ctypes.windll.user32

def enum_cb(hwnd, lparam):
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    title = buf.value
    vis = user32.IsWindowVisible(hwnd)
    if title:
        print(f"HWND: {hwnd}, PID: {pid.value}, Visible: {vis}, Title: '{title}'")
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
