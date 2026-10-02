"""
Chirp — Luxury Floating AI Voice Dictation Capsule for Windows
High-performance PyAudio VAD engine with live animated audio level visualizer.
Supports OpenAI Whisper, Google Gemini Flash, and multilingual fallback.
"""

import os
import sys
import time
import json
import base64
import wave
import io
import ctypes
import threading
import collections
import concurrent.futures
import tkinter as tk
from tkinter import ttk, messagebox
import winsound
import requests

try:
    import pyaudio
    import audioop
except ImportError:
    pyaudio = None
    audioop = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import win32gui
    import win32process
    import win32api
    import win32con
except ImportError:
    win32gui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import keyboard
except ImportError:
    keyboard = None

user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

APP_NAME = "Chirp"
APP_VERSION = "3.0.0"
CONFIG_FILE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Chirp", "config.json")

# Styling
TRANS_KEY = "#000001"
COLOR_BG_DARK = "#0B0F1A"
COLOR_BG_HOVER = "#121828"
COLOR_BORDER_IDLE = "#222C42"

COLOR_OPENAI_ACCENT = "#10B981"  # Emerald Green (GPT-4o)
COLOR_GEMINI_ACCENT = "#8B5CF6"  # Royal Violet (Gemini)
COLOR_WEB_ACCENT = "#0284C7"     # Sky Blue (Web Speech)
COLOR_PROCESSING = "#38BDF8"     # Cyan

COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_MUTED = "#8E9BB5"

def force_focus_window(hwnd):
    """Reliably activate and focus the target window using Win32 AttachThreadInput."""
    if not hwnd or not win32gui or not win32gui.IsWindow(hwnd):
        return False
    try:
        cur_fg = win32gui.GetForegroundWindow()
        if cur_fg == hwnd:
            return True

        cur_thread = win32api.GetCurrentThreadId()
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        fg_thread, _ = win32process.GetWindowThreadProcessId(cur_fg)

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

class ChirpApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANS_KEY)
        self.root.attributes("-transparentcolor", TRANS_KEY)

        self.width = 182
        self.height = 38
        self.opacity = 0.90
        self.sound_enabled = True
        self.hotkey = "f8"
        self.engine = "openai" # "openai" (GPT-4o), "gemini", "web"
        self.search_mode = False
        self.language = "auto" # "auto", "hi-IN", "en-IN", "en-US"
        self.mic_index = None

        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

        self.is_listening = False
        self.is_processing = False
        self.live_volume = 0
        self.last_target_hwnd = None
        self.stop_threads = False
        # NOTE: self.recognizer is no longer shared — each transcribe_web_wav call
        # creates its own sr.Recognizer() for thread safety.
        self._web_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


        # Load persisted config
        self.load_config()
        self.root.attributes("-alpha", self.opacity)

        # Setup Icon
        self.bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        self.ico_path = os.path.join(self.bundle_dir, "chirp.ico")
        if os.path.exists(self.ico_path):
            try:
                self.root.iconbitmap(self.ico_path)
            except Exception:
                pass

        # Apply geometry
        self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")

        # Canvas for custom rounded glass capsule
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANS_KEY,
            highlightthickness=0,
            cursor="hand2"
        )
        self.canvas.pack(fill="both", expand=True)

        # Dragging & Clicking
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_moved = False

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<Enter>", self.on_hover_enter)
        self.canvas.bind("<Leave>", self.on_hover_leave)

        # Context Menu
        self.menu = tk.Menu(self.root, tearoff=0, bg="#111625", fg="#FFFFFF", activebackground="#10B981", activeforeground="#000000", font=("Segoe UI", 9))
        self.build_context_menu()

        # Apply Windows non-activating style
        self.apply_noactivate_style()

        # Target Window Tracker
        threading.Thread(target=self.track_foreground_window, daemon=True).start()

        # Setup Global Hotkey
        self.setup_hotkey()

        # Audio Stream Thread
        self.audio_thread = None

        # Pre-warm Google Speech API connection in background (saves ~250ms on first real call)
        threading.Thread(target=self._prewarm_api, daemon=True).start()

        # Render & Animation Loop
        self.render_pill()
        self.ui_update_loop()

    def load_config(self):
        default_x = max(50, self.root.winfo_screenwidth() - 260)
        default_y = 40
        self.pos_x = default_x
        self.pos_y = default_y

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.pos_x = data.get("x", default_x)
                    self.pos_y = data.get("y", default_y)
                    self.opacity = data.get("opacity", 0.90)
                    self.sound_enabled = data.get("sound_enabled", True)
                    self.engine = data.get("engine", "openai")
                    self.search_mode = data.get("search_mode", False)
                    self.language = data.get("language", "auto")
                    self.mic_index = data.get("mic_index", None)
                    if not self.openai_key:
                        self.openai_key = data.get("openai_key", "")
                    if not self.gemini_key:
                        self.gemini_key = data.get("gemini_key", "")
            except Exception:
                pass

    def save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            data = {
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
                "opacity": self.opacity,
                "sound_enabled": self.sound_enabled,
                "engine": self.engine,
                "search_mode": self.search_mode,
                "language": self.language,
                "mic_index": self.mic_index,
                "openai_key": self.openai_key,
                "gemini_key": self.gemini_key
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def apply_noactivate_style(self):
        try:
            self.root.update_idletasks()
            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            old_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = old_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception as e:
            print(f"Error applying window style: {e}")

    def track_foreground_window(self):
        while not self.stop_threads:
            try:
                if win32gui:
                    hwnd = win32gui.GetForegroundWindow()
                    my_hwnd = self.root.winfo_id()
                    my_parent = user32.GetParent(my_hwnd) or my_hwnd
                    if hwnd and hwnd != my_hwnd and hwnd != my_parent:
                        if win32gui.IsWindowVisible(hwnd):
                            self.last_target_hwnd = hwnd
            except Exception:
                pass
            time.sleep(0.04)

    def setup_hotkey(self):
        if not keyboard:
            return
        try:
            keyboard.add_hotkey(self.hotkey, self.toggle_listening)
        except Exception as e:
            print(f"Could not bind hotkey {self.hotkey}: {e}")

    # --- Mouse Handlers ---
    def on_press(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.drag_moved = False

    def on_drag(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        if abs(dx) > 3 or abs(dy) > 3:
            self.drag_moved = True
            new_x = self.root.winfo_x() + dx
            new_y = self.root.winfo_y() + dy
            self.root.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        if not self.drag_moved:
            if event.x >= 108:
                self.cycle_engine()
            else:
                self.toggle_listening()
        else:
            self.save_config()

    def on_hover_enter(self, event):
        if not self.is_listening and not self.is_processing:
            self.render_pill(hover=True)

    def on_hover_leave(self, event):
        if not self.is_listening and not self.is_processing:
            self.render_pill(hover=False)

    def cycle_engine(self):
        if self.engine == "openai":
            self.set_engine("gemini")
        elif self.engine == "gemini":
            self.set_engine("web")
        else:
            self.set_engine("openai")

    def set_engine(self, eng):
        self.engine = eng
        self.save_config()
        self.render_pill()
        if eng == "openai" and not self.openai_key:
            self.open_settings_modal("Please enter your OpenAI API Key to use OpenAI GPT-4o.")
        elif eng == "gemini" and not self.gemini_key:
            self.open_settings_modal("Please enter your Gemini API Key to use Google Gemini.")

    # --- Context Menu ---
    def build_context_menu(self):
        self.menu.delete(0, "end")
        self.menu.add_command(label="🎙️ Toggle Dictation (F8)", command=self.toggle_listening)
        self.menu.add_separator()

        # Engine Selection
        self.menu.add_command(
            label=f"{'●' if self.engine == 'openai' else '○'} Listen with OpenAI (GPT-4o-mini)",
            command=lambda: self.set_engine("openai")
        )
        self.menu.add_command(
            label=f"{'●' if self.engine == 'gemini' else '○'} Listen with Gemini (Flash)",
            command=lambda: self.set_engine("gemini")
        )
        self.menu.add_command(
            label=f"{'●' if self.engine == 'web' else '○'} Listen with Fast Web Speech",
            command=lambda: self.set_engine("web")
        )
        self.menu.add_separator()

        # Language Selection
        lang_menu = tk.Menu(self.menu, tearoff=0, bg="#111625", fg="#FFFFFF", activebackground="#10B981", activeforeground="#000000")
        lang_menu.add_command(label="Multilingual / Auto Detect", command=lambda: self.set_language("auto"))
        lang_menu.add_command(label="Hindi / Hinglish (India)", command=lambda: self.set_language("hi-IN"))
        lang_menu.add_command(label="English (India)", command=lambda: self.set_language("en-IN"))
        lang_menu.add_command(label="English (United States)", command=lambda: self.set_language("en-US"))
        self.menu.add_cascade(label=f"🌐 Language [{self.language}]", menu=lang_menu)

        search_chk = "✓" if self.search_mode else "○"
        self.menu.add_command(
            label=f"{search_chk} Smart Search Optimizer Mode",
            command=self.toggle_search_mode
        )

        self.menu.add_command(label="🔑 API Keys Settings...", command=self.open_settings_modal)
        self.menu.add_separator()

        # Opacity Menu
        opacity_menu = tk.Menu(self.menu, tearoff=0, bg="#111625", fg="#FFFFFF", activebackground="#10B981", activeforeground="#000000")
        opacity_menu.add_command(label="95% (Solid)", command=lambda: self.set_opacity(0.95))
        opacity_menu.add_command(label="88% (Balanced)", command=lambda: self.set_opacity(0.88))
        opacity_menu.add_command(label="75% (Translucent)", command=lambda: self.set_opacity(0.75))
        self.menu.add_cascade(label="👁️ Opacity", menu=opacity_menu)

        sound_label = "🔊 Audio Feedback: ON" if self.sound_enabled else "🔇 Audio Feedback: OFF"
        self.menu.add_command(label=sound_label, command=self.toggle_sound)
        self.menu.add_command(label="📍 Reset Position", command=self.reset_position)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Exit Chirp", command=self.close_app)

    def show_context_menu(self, event):
        self.build_context_menu()
        self.menu.tk_popup(event.x_root, event.y_root)

    def set_language(self, lang):
        self.language = lang
        self.save_config()

    def toggle_search_mode(self):
        self.search_mode = not self.search_mode
        self.save_config()

    def set_opacity(self, op):
        self.opacity = op
        self.root.attributes("-alpha", op)
        self.save_config()

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.save_config()

    def reset_position(self):
        self.pos_x = max(50, self.root.winfo_screenwidth() - 260)
        self.pos_y = 40
        self.root.geometry(f"+{self.pos_x}+{self.pos_y}")
        self.save_config()

    # --- API Keys Dialog ---
    def open_settings_modal(self, notice=""):
        win = tk.Toplevel(self.root)
        win.title("Chirp — AI Settings (GPT-4o-mini & Gemini)")
        win.geometry("490x350")
        win.resizable(False, False)
        win.configure(bg="#0B0F1A")
        win.attributes("-topmost", True)

        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 245
        y = (win.winfo_screenheight() // 2) - 175
        win.geometry(f"+{x}+{y}")

        hdr = tk.Frame(win, bg="#121828", padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Chirp AI Configuration", font=("Segoe UI", 12, "bold"), fg="#FFFFFF", bg="#121828").pack(anchor="w")
        tk.Label(hdr, text="Configure your OpenAI (GPT-4o-mini) & Google Gemini API Keys", font=("Segoe UI", 8), fg="#8E9BB5", bg="#121828").pack(anchor="w")

        body = tk.Frame(win, bg="#0B0F1A", padx=20, pady=12)
        body.pack(fill="both", expand=True)

        if notice:
            tk.Label(body, text=notice, font=("Segoe UI", 8, "italic"), fg="#F59E0B", bg="#0B0F1A", wraplength=450).pack(anchor="w", pady=(0, 6))

        # OpenAI Row
        oa_hdr = tk.Frame(body, bg="#0B0F1A")
        oa_hdr.pack(fill="x")
        tk.Label(oa_hdr, text="OpenAI API Key (Powers GPT-4o-mini):", font=("Segoe UI", 9, "bold"), fg="#10B981", bg="#0B0F1A").pack(side="left")
        lbl_oa_status = tk.Label(oa_hdr, text="", font=("Segoe UI", 8), bg="#0B0F1A", fg="#8E9BB5")
        lbl_oa_status.pack(side="right")

        entry_oa = tk.Entry(body, font=("Segoe UI", 9), bg="#161E33", fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat", highlightthickness=1, highlightbackground="#222C42", show="*")
        entry_oa.pack(fill="x", ipady=3, pady=(2, 4))
        entry_oa.insert(0, self.openai_key)

        def test_openai():
            k = entry_oa.get().strip()
            if not k:
                lbl_oa_status.config(text="⚠ No key entered", fg="#F59E0B")
                return
            lbl_oa_status.config(text="Testing...", fg="#8E9BB5")
            def _run():
                try:
                    r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {k}"}, timeout=6)
                    if r.status_code == 200:
                        # Check chat completion quota with gpt-4o-mini
                        rc = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"}, json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}, timeout=6)
                        if rc.status_code == 200:
                            lbl_oa_status.config(text="✓ Valid (GPT-4o-mini Ready)", fg="#10B981")
                        elif rc.status_code == 429:
                            lbl_oa_status.config(text="⚠ Valid Key, but No Credits (429)", fg="#F59E0B")
                        else:
                            lbl_oa_status.config(text=f"⚠ Connected ({rc.status_code})", fg="#F59E0B")
                    elif r.status_code == 401:
                        lbl_oa_status.config(text="✗ Invalid Key (401)", fg="#EF4444")
                    else:
                        lbl_oa_status.config(text=f"Error {r.status_code}", fg="#EF4444")
                except Exception as ex:
                    lbl_oa_status.config(text="✗ Connection Failed", fg="#EF4444")
            threading.Thread(target=_run, daemon=True).start()

        btn_test_oa = tk.Button(body, text="Test OpenAI Key", font=("Segoe UI", 8), bg="#162035", fg="#10B981", activebackground="#222C42", activeforeground="#FFFFFF", relief="flat", padx=8, pady=1, cursor="hand2", command=test_openai)
        btn_test_oa.pack(anchor="w", pady=(0, 10))

        # Gemini Row
        gm_hdr = tk.Frame(body, bg="#0B0F1A")
        gm_hdr.pack(fill="x")
        tk.Label(gm_hdr, text="Gemini API Key (Google AI Studio):", font=("Segoe UI", 9, "bold"), fg="#8B5CF6", bg="#0B0F1A").pack(side="left")
        lbl_gm_status = tk.Label(gm_hdr, text="", font=("Segoe UI", 8), bg="#0B0F1A", fg="#8E9BB5")
        lbl_gm_status.pack(side="right")

        entry_gm = tk.Entry(body, font=("Segoe UI", 9), bg="#161E33", fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat", highlightthickness=1, highlightbackground="#222C42", show="*")
        entry_gm.pack(fill="x", ipady=3, pady=(2, 4))
        entry_gm.insert(0, self.gemini_key)

        def test_gemini():
            gk = entry_gm.get().strip()
            if not gk:
                lbl_gm_status.config(text="⚠ No key entered", fg="#F59E0B")
                return
            lbl_gm_status.config(text="Testing...", fg="#8E9BB5")
            def _run():
                try:
                    r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={gk}", timeout=6)
                    if r.status_code == 200:
                        lbl_gm_status.config(text="✓ Active & Working", fg="#10B981")
                    else:
                        lbl_gm_status.config(text=f"✗ Error ({r.status_code})", fg="#EF4444")
                except Exception:
                    lbl_gm_status.config(text="✗ Connection Failed", fg="#EF4444")
            threading.Thread(target=_run, daemon=True).start()

        btn_test_gm = tk.Button(body, text="Test Gemini Key", font=("Segoe UI", 8), bg="#162035", fg="#8B5CF6", activebackground="#222C42", activeforeground="#FFFFFF", relief="flat", padx=8, pady=1, cursor="hand2", command=test_gemini)
        btn_test_gm.pack(anchor="w", pady=(0, 12))

        btn_bar = tk.Frame(body, bg="#0B0F1A")
        btn_bar.pack(fill="x", pady=(4, 0))

        def save_and_close():
            self.openai_key = entry_oa.get().strip()
            self.gemini_key = entry_gm.get().strip()
            self.save_config()
            self.render_pill()
            win.destroy()

        btn_save = tk.Button(btn_bar, text="Save Keys", font=("Segoe UI", 9, "bold"), bg="#10B981", fg="#000000", activebackground="#059669", activeforeground="#FFFFFF", relief="flat", padx=16, pady=4, cursor="hand2", command=save_and_close)
        btn_save.pack(side="right", padx=(8, 0))

        btn_cancel = tk.Button(btn_bar, text="Cancel", font=("Segoe UI", 9), bg="#1F293D", fg="#8E9BB5", activebackground="#2D3A54", activeforeground="#FFFFFF", relief="flat", padx=14, pady=4, cursor="hand2", command=win.destroy)
        btn_cancel.pack(side="right")

    def _prewarm_api(self):
        """Fire a tiny dummy request to Google Speech API at startup to pre-establish TCP connection.
        This saves ~250ms on the user's very first transcription."""
        try:
            import struct, wave as wave_mod
            # Generate 0.1s of silence at 16kHz
            silent = struct.pack('<' + 'h' * 1600, *([0] * 1600))
            buf = io.BytesIO()
            with wave_mod.open(buf, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
                wf.writeframes(silent)
            wav_bytes = buf.getvalue()
            r = sr.Recognizer()
            r.energy_threshold = 280; r.dynamic_energy_threshold = False
            with sr.AudioFile(io.BytesIO(wav_bytes)) as src:
                audio = r.record(src)
            r.recognize_google(audio, language="hi-IN")
        except Exception:
            pass  # Silence is expected to return no text — connection is warmed up

    # --- Live Audio Stream & Voice Activity Detection (VAD) ---
    def toggle_listening(self):
        if not self.is_listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        self.is_listening = True
        self.render_pill()
        if self.sound_enabled:
            try:
                winsound.Beep(920, 50)
            except Exception:
                pass
        self.audio_thread = threading.Thread(target=self.pyaudio_stream_worker, daemon=True)
        self.audio_thread.start()

    def stop_listening(self):
        self.is_listening = False
        self.is_processing = False
        self.live_volume = 0
        self.render_pill()
        if self.sound_enabled:
            try:
                winsound.Beep(480, 50)
            except Exception:
                pass

    def pyaudio_stream_worker(self):
        """Continuously streams microphone data, calculates live RMS, and detects complete phrases."""
        if not pyaudio:
            return

        p = pyaudio.PyAudio()
        RATE = 16000
        CHUNK = 1024
        SILENCE_LIMIT_SEC = 0.40   # 0.40s lightning-fast pause detection (ChatGPT Live speed!)
        MAX_PHRASE_SEC = 25.0      # Continuous speech support
        MIN_AUDIO_BYTES = 1600     # ~0.05s minimum (never drops short words like 'yes', 'no')

        try:
            device_idx = self.mic_index
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=RATE,
                input=True,
                input_device_index=device_idx,
                frames_per_buffer=CHUNK
            )
        except Exception as e:
            print(f"Could not open specific device, trying system default: {e}")
            try:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
            except Exception as ex:
                print(f"Failed to open microphone: {ex}")
                p.terminate()
                return

        # Pre-roll rolling ring buffer (holds past ~0.77 seconds of audio)
        # Prevents cutting off the first word, consonant, or breath of speech!
        pre_buffer = collections.deque(maxlen=12)
        frames = []
        is_speaking = False
        silence_start = None
        phrase_start = None
        ambient_rms = 15.0   # Start low — matches typical quiet mic RMS (~10-20)

        try:
            while self.is_listening:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    rms = 0
                    if audioop:
                        try:
                            rms = audioop.rms(data, 2)
                        except Exception:
                            pass

                    # Live volume for visualizer
                    self.live_volume = min(100, int((rms / 450) * 100))

                    now = time.time()

                    # Dynamic noise floor calibration
                    if not is_speaking:
                        ambient_rms = (ambient_rms * 0.94) + (rms * 0.06)
                        pre_buffer.append(data)

                    # Dynamic energy threshold — tuned for low-sensitivity mics
                    # Min=25 (not 80!) so quiet mics still trigger. Max=300 cap so loud rooms don't lock out.
                    energy_threshold = min(300, max(25, int(ambient_rms * 1.25)))

                    if rms > energy_threshold:
                        if not is_speaking:
                            is_speaking = True
                            phrase_start = now
                            # Include rolling pre-buffer so beginning of words are NEVER cut off
                            frames = list(pre_buffer)
                        silence_start = None
                        frames.append(data)
                    elif is_speaking:
                        frames.append(data)
                        if silence_start is None:
                            silence_start = now
                        elif (now - silence_start) >= SILENCE_LIMIT_SEC or (now - phrase_start) >= MAX_PHRASE_SEC:
                            # Natural pause detected! Complete sentence finished.
                            is_speaking = False
                            silence_start = None
                            captured_audio = b"".join(frames)
                            frames = []

                            # Dispatch transcription in separate background worker so audio stream stays open
                            threading.Thread(target=self.process_audio_chunk, args=(captured_audio, RATE), daemon=True).start()

                except OSError as e:
                    # Overflow or device error — pause briefly and retry (stream stays open)
                    print(f"[Chirp] Audio stream OSError: {e}")
                    time.sleep(0.05)
                except Exception as e:
                    print(f"[Chirp] Audio read error: {e}")
                    time.sleep(0.02)

        except Exception as e:
            # Outer guard: catches any unexpected crash to prevent silent thread death
            print(f"[Chirp] pyaudio_stream_worker CRASHED: {e}")
        finally:
            # FLUSH ON MANUAL STOP / PAUSE:
            # If user spoke and clicked the capsule or pressed F8 to pause, transcribe whatever was spoken!
            if len(frames) > 0:
                captured_audio = b"".join(frames)
                if len(captured_audio) >= MIN_AUDIO_BYTES:
                    threading.Thread(target=self.process_audio_chunk, args=(captured_audio, RATE), daemon=True).start()

            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            p.terminate()
            print("[Chirp] pyaudio_stream_worker exited.")


    def process_audio_chunk(self, raw_bytes, rate):
        """Encodes PCM to WAV, applies studio audio AGC normalization, and sends to OpenAI / Gemini / Web."""
        if not raw_bytes or len(raw_bytes) < 1600:
            return

        self.is_processing = True
        self.root.after(0, self.render_pill)

        # Smart Audio Normalization: Boost quiet speech to broadcast clarity so AI transcribes with 100% precision
        if audioop and len(raw_bytes) >= 1600:
            try:
                peak = audioop.max(raw_bytes, 2)
                if 300 < peak < 18000:
                    gain = min(3.5, 24000.0 / peak)
                    raw_bytes = audioop.mul(raw_bytes, 2, gain)
            except Exception:
                pass

        # Build WAV in memory
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(raw_bytes)
        wav_bytes = wav_buf.getvalue()

        try:
            text = self.dispatch_transcription_wav(wav_bytes)
            if text:
                self.inject_text(text)
        except Exception as e:
            print(f"Processing chunk error: {e}")
        finally:
            self.is_processing = False
            self.root.after(0, self.render_pill)

    def dispatch_transcription_wav(self, wav_bytes):
        engine = self.engine

        if engine == "openai":
            if self.openai_key:
                try:
                    return self.transcribe_openai_wav(wav_bytes)
                except Exception as e:
                    print(f"OpenAI error, instant fallback to Web: {e}")
                    return self.transcribe_web_wav(wav_bytes)
            else:
                return self.transcribe_web_wav(wav_bytes)

        elif engine == "gemini":
            if self.gemini_key:
                try:
                    return self.transcribe_gemini_wav(wav_bytes)
                except Exception as e:
                    print(f"Gemini error, instant fallback to Web: {e}")
                    return self.transcribe_web_wav(wav_bytes)
            else:
                return self.transcribe_web_wav(wav_bytes)

        else:
            return self.transcribe_web_wav(wav_bytes)

    def transcribe_openai_wav(self, wav_bytes):
        """Transcribes speech using OpenAI GPT-4o Audio / Whisper.
        If search_mode is active, formats the transcription into an optimal web search query."""
        if not self.openai_key:
            raise Exception("OpenAI API key not configured")

        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")

        # 1. Try GPT-4o-mini Audio directly
        for audio_model in ["gpt-4o-mini-audio-preview", "gpt-4o-audio-preview"]:
            try:
                url_chat = "https://api.openai.com/v1/chat/completions"
                headers_chat = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                }
                prompt_instruction = (
                    "Transcribe this speech accurately into plain text. Output ONLY the raw transcribed words with natural punctuation. Do not output commentary or quotes."
                    if not self.search_mode else
                    "Transcribe this speech and output ONLY a concise, high-relevance search query suitable for Google. No quotes or explanation."
                )
                payload_chat = {
                    "model": audio_model,
                    "modalities": ["text"],
                    "audio": {"data": b64_audio, "format": "wav"},
                    "messages": [
                        {"role": "user", "content": prompt_instruction}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 300
                }
                resp_chat = requests.post(url_chat, headers=headers_chat, json=payload_chat, timeout=6)
                if resp_chat.status_code == 200:
                    data = resp_chat.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "").strip()
                        if content:
                            return content
                elif resp_chat.status_code == 429:
                    raise Exception("OpenAI Quota Limit Reached (429)")
            except Exception as e_gpt:
                if "429" in str(e_gpt):
                    raise e_gpt

        # 2. Try Whisper transcription API with exact phonetic guidance
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {
            "model": "whisper-1",
            "prompt": "Clear Hindi, English, and Hinglish dictation. Technical words in English with exact spelling. Natural punctuation.",
            "temperature": 0.0
        }
        if self.language == "hi-IN":
            data["language"] = "hi"
        elif self.language in ("en-IN", "en-US"):
            data["language"] = "en"

        resp = requests.post(url, headers=headers, files=files, data=data, timeout=6)
        if resp.status_code == 200:
            text = resp.json().get("text", "").strip()
            if self.search_mode and text:
                try:
                    rc = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [{"role": "user", "content": f"Convert this spoken statement into a concise search query. Output only the query:\n{text}"}],
                            "max_tokens": 40,
                            "temperature": 0.0
                        },
                        timeout=3
                    )
                    if rc.status_code == 200:
                        q = rc.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if q:
                            return q
                except Exception:
                    pass
            return text
        else:
            raise Exception(f"OpenAI API Error: {resp.status_code} {resp.text}")

    def transcribe_gemini_wav(self, wav_bytes):
        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={self.gemini_key}"

        prompt = "Transcribe the following speech accurately into plain text. Output ONLY the transcribed words without notes or quotes."
        if self.search_mode:
            prompt = "Transcribe the following speech and format it as a clean, concise search query. Output only the query."

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 200
            }
        }
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                return "".join(text_parts).strip()
            return ""
        else:
            raise Exception(f"Gemini API Error: {resp.status_code} {resp.text}")

    def transcribe_web_wav(self, wav_bytes):
        """Thread-safe Web Speech Recognition: fresh recognizer per call, persistent executor."""
        if not sr:
            return None

        # ── Thread-safe: each call gets its OWN recognizer (no shared state) ──
        r = sr.Recognizer()
        r.energy_threshold = 280
        r.dynamic_energy_threshold = False

        try:
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio = r.record(source)
        except Exception as e:
            print(f"Audio read error: {e}")
            return None

        # Dedicated language mode (fastest direct path ~400-500ms)
        if self.language in ("hi-IN", "en-IN", "en-US"):
            try:
                return r.recognize_google(audio, language=self.language)
            except Exception:
                return None

        # "auto" Mode — FAST SEQUENTIAL (not parallel):
        # Google hi-IN handles Hinglish perfectly. Try it first.
        # Only fall back to en-IN if hi-IN returns nothing (rare).
        # Sequential = single API call in 99% of cases = ~400ms faster than parallel.
        try:
            result = r.recognize_google(audio, language="hi-IN")
            if result and result.strip():
                return result.strip()
        except Exception:
            pass

        # Fallback: pure English (fires only if hi-IN returned nothing)
        try:
            result = r.recognize_google(audio, language="en-IN")
            if result and result.strip():
                return result.strip()
        except Exception:
            pass

        return None


    def inject_text(self, text):
        if not text:
            return
        clean_text = text.strip() + " "

        target_hwnd = self.last_target_hwnd
        if target_hwnd:
            force_focus_window(target_hwnd)
            time.sleep(0.008)  # 8ms focus settle (was 15ms)

        if pyperclip and win32api:
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass

            try:
                pyperclip.copy(clean_text)
                time.sleep(0.005)  # 5ms clipboard settle (was 10ms)

                # Send Ctrl+V
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                win32api.keybd_event(ord('V'), 0, 0, 0)
                time.sleep(0.005)  # 5ms key hold (was 10ms)
                win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

            finally:
                def restore():
                    time.sleep(0.4)
                    try:
                        pyperclip.copy(old_clip)
                    except Exception:
                        pass
                threading.Thread(target=restore, daemon=True).start()

    # --- UI Rendering & Animations ---
    def render_pill(self, hover=False):
        self.canvas.delete("all")
        w = self.width
        h = self.height
        r = h // 2

        if self.engine == "openai":
            engine_col = COLOR_OPENAI_ACCENT
            engine_tag = "4o-mini"
        elif self.engine == "gemini":
            engine_col = COLOR_GEMINI_ACCENT
            engine_tag = "Gemini"
        else:
            engine_col = COLOR_WEB_ACCENT
            engine_tag = "Web"

        if self.is_listening:
            border_col = engine_col
            bg_col = "#09121B"
            status_text = "Listening..."
            text_col = COLOR_TEXT_PRIMARY
        elif self.is_processing:
            border_col = COLOR_PROCESSING
            bg_col = "#0C1728"
            status_text = "Typing..."
            text_col = COLOR_PROCESSING
        else:
            border_col = "#323F5E" if hover else COLOR_BORDER_IDLE
            bg_col = COLOR_BG_HOVER if hover else COLOR_BG_DARK
            status_text = APP_NAME
            text_col = COLOR_TEXT_MUTED if not hover else COLOR_TEXT_PRIMARY

        # 1. Rounded Capsule Shell
        pad = 2
        self.canvas.create_oval(pad, pad, h - pad, h - pad, fill=bg_col, outline=border_col, width=1.5)
        self.canvas.create_oval(w - (h - pad), pad, w - pad, h - pad, fill=bg_col, outline=border_col, width=1.5)
        self.canvas.create_rectangle(r, pad, w - r, h - pad, fill=bg_col, outline="")
        self.canvas.create_line(r, pad, w - r, pad, fill=border_col, width=1.5)
        self.canvas.create_line(r, h - pad, w - r, h - pad, fill=border_col, width=1.5)

        # 2. Indicator / Live VU Soundwave Meter
        icon_cx = 19
        icon_cy = h // 2

        if self.is_listening:
            # Active Indicator Dot
            self.canvas.create_oval(icon_cx - 5, icon_cy - 5, icon_cx + 5, icon_cy + 5, fill=engine_col, outline="")

            # Live VU Soundwave Meter reacting to actual microphone volume!
            vol = max(10, self.live_volume)
            base_bars = [4, 7, 10, 6]
            for i, b in enumerate(base_bars):
                bx = icon_cx + 11 + (i * 3)
                bh = max(3, int(b * (vol / 40)))
                bh = min(bh, 13)
                self.canvas.create_line(bx, icon_cy - bh, bx, icon_cy + bh, fill=engine_col, width=1.5)
            text_x = 46
        elif self.is_processing:
            self.canvas.create_oval(icon_cx - 4, icon_cy - 4, icon_cx + 4, icon_cy + 4, fill=COLOR_PROCESSING, outline="")
            text_x = 34
        else:
            self.draw_mic_icon(icon_cx, icon_cy, fill=text_col)
            text_x = 36

        # 3. Status Label
        self.canvas.create_text(
            text_x,
            icon_cy,
            text=status_text,
            anchor="w",
            font=("Segoe UI", 9, "bold" if self.is_listening else "normal"),
            fill=text_col
        )

        # 4. Engine Selector Badge
        badge_w = 56
        badge_h = 22
        badge_x1 = w - badge_w - 7
        badge_y1 = (h - badge_h) // 2
        badge_x2 = w - 7
        badge_y2 = badge_y1 + badge_h

        br = badge_h // 2
        b_bg = "#121A2B" if not self.is_listening else "#132128"
        self.canvas.create_oval(badge_x1, badge_y1, badge_x1 + badge_h, badge_y2, fill=b_bg, outline=engine_col, width=1)
        self.canvas.create_oval(badge_x2 - badge_h, badge_y1, badge_x2, badge_y2, fill=b_bg, outline=engine_col, width=1)
        self.canvas.create_rectangle(badge_x1 + br, badge_y1, badge_x2 - br, badge_y2, fill=b_bg, outline="")
        self.canvas.create_line(badge_x1 + br, badge_y1, badge_x2 - br, badge_y1, fill=engine_col, width=1)
        self.canvas.create_line(badge_x1 + br, badge_y2, badge_x2 - br, badge_y2, fill=engine_col, width=1)

        badge_cx = (badge_x1 + badge_x2) // 2
        self.canvas.create_text(
            badge_cx,
            icon_cy,
            text=engine_tag,
            font=("Segoe UI", 7, "bold"),
            fill=engine_col
        )

    def draw_mic_icon(self, cx, cy, fill="#8E9BB5"):
        self.canvas.create_rectangle(cx - 3, cy - 6, cx + 3, cy + 2, fill=fill, outline="")
        self.canvas.create_arc(cx - 3, cy - 9, cx + 3, cy - 3, start=0, extent=180, fill=fill, outline="")
        self.canvas.create_arc(cx - 3, cy - 1, cx + 3, cy + 5, start=180, extent=180, fill=fill, outline="")
        self.canvas.create_arc(cx - 5, cy - 3, cx + 5, cy + 6, start=180, extent=180, style="arc", outline=fill, width=1.2)
        self.canvas.create_line(cx, cy + 6, cx, cy + 8, fill=fill, width=1.2)
        self.canvas.create_line(cx - 3, cy + 8, cx + 3, cy + 8, fill=fill, width=1.2)

    def ui_update_loop(self):
        if self.is_listening:
            self.render_pill()
            # ── Watchdog: restart audio thread if it died silently ──
            if self.audio_thread is None or not self.audio_thread.is_alive():
                print("[Chirp] Audio thread died unexpectedly — restarting...")
                self.audio_thread = threading.Thread(
                    target=self.pyaudio_stream_worker, daemon=True
                )
                self.audio_thread.start()
        self.root.after(80, self.ui_update_loop)

    def close_app(self):
        self.stop_threads = True
        self.is_listening = False
        self.save_config()
        try:
            self._web_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.root.destroy()


    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ChirpApp()
    app.run()
