import win32gui
import win32process
import win32api
import win32con
import time
import pyperclip

def force_focus_window(hwnd):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    try:
        cur_fg = win32gui.GetForegroundWindow()
        if cur_fg == hwnd:
            return True

        cur_thread = win32api.GetCurrentThreadId()
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        fg_thread, _ = win32process.GetWindowThreadProcessId(cur_fg)

        # Attach to foreground thread and target thread
        if fg_thread != cur_thread:
            win32process.AttachThreadInput(cur_thread, fg_thread, True)
        if target_thread != cur_thread and target_thread != fg_thread:
            win32process.AttachThreadInput(cur_thread, target_thread, True)

        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)

        if fg_thread != cur_thread:
            win32process.AttachThreadInput(cur_thread, fg_thread, False)
        if target_thread != cur_thread and target_thread != fg_thread:
            win32process.AttachThreadInput(cur_thread, target_thread, False)

        return True
    except Exception as e:
        print(f"Focus error: {e}")
        return False

print("Focus helper defined successfully.")
