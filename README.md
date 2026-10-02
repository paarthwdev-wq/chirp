# Chirp — Instant AI Voice-to-Text for Windows

<p align="center">
  <img src="chirp_logo.png" width="80" alt="Chirp Logo"/>
</p>

<p align="center">
  <b>Ultra-fast floating voice dictation capsule for Windows.</b><br/>
  Speak anywhere → text appears instantly in any app.
</p>

---

## ✨ Features

- 🎙️ **Instant Dictation** — press F8, speak, text types itself automatically in any active app
- ⚡ **Sub-1 second** ultra-low latency with intelligent dynamic noise-floor calibration
- 🧠 **OpenAI GPT-4o Audio** — state-of-the-art transcription, natural phrasing, and smart search query formatting
- 🌐 **Multilingual Native Support** — Hindi, Hinglish, English (India/US) auto-detected
- 🤖 **3 Selectable Engines** — OpenAI GPT-4o, Google Gemini Flash, and Zero-Config Fast Web Speech
- 🔴 **Live Reactive VU Meter** — real-time animated soundwave reacting to mic input
- 💎 **Luxury Glassmorphic Capsule** — non-intrusive floating pill that never steals window focus
- 🔁 **Auto-Restart Watchdog** — 100% resilient background thread monitoring
- ⌨️ **Universal Compatibility** — seamlessly types into Word, Notepad, VS Code, Slack, WhatsApp, Chrome, etc.

---

## 🚀 Quick Start

### 1. Download & Install (Windows)
1. Run `Install_Chirp.bat` on your Desktop to install Chirp into `%LOCALAPPDATA%\Chirp`.
2. Or simply double-click `Chirp.exe`.

### 2. Run from Source
```bash
pip install pyaudio SpeechRecognition pyperclip pywin32 keyboard requests openai
python chirp_app.py
```

---

## 🎮 Usage

| Action | How |
|--------|-----|
| **Start / Pause listening** | Click the capsule or press `F8` |
| **Switch AI engine** | Click the badge on the right (`GPT-4o` / `Gemini` / `Web`) |
| **Configure API Keys** | Right-click capsule → 🔑 API Keys Settings |
| **Smart Search Mode** | Right-click capsule → ✓ Smart Search Optimizer Mode |
| **Change Language** | Right-click capsule → 🌐 Language |
| **Move Capsule** | Drag anywhere on screen |

---

## ⚙️ AI Engines

| Engine | Speed | Capabilities | Requires |
|--------|-------|--------------|----------|
| **OpenAI GPT-4o** | Fast (~700ms) | Next-gen audio comprehension, auto-punctuation, smart search intent | OpenAI API Key |
| **Fast Web Speech** | Ultra-Fast (~480ms) | Instant real-time transcription, Hindi/Hinglish/English auto-detect | Free (Zero Config) |
| **Google Gemini** | Fast (~1.2s) | Google AI Studio Flash model | Gemini API Key |

> **Pro Tip:** When using **GPT-4o**, enable **Smart Search Optimizer Mode** to turn spoken thoughts directly into high-intent search queries!

---

## 🛠️ Build from Source

```bash
pip install pyinstaller
python -m PyInstaller --clean Chirp.spec
python deploy_chirp.py
```

---

## 📁 Project Structure

```
Chirp/
├── chirp_app.py       # Main application
├── Chirp.spec         # PyInstaller build config
├── deploy_chirp.py    # Desktop deployment script
├── make_chirp_icon.py # Icon generator
├── chirp.ico          # App icon
└── chirp_logo.png     # Logo
```

---

## 📄 License

MIT License — free to use, modify, and distribute.
