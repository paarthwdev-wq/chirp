import os
import shutil
import sys

base_dir = r"c:\Users\mishr\Downloads\SEO Facebook\Chirp"
exe_src = os.path.join(base_dir, "dist", "Chirp.exe")
ico_path = os.path.join(base_dir, "chirp.ico")

if not os.path.exists(exe_src):
    print("dist/Chirp.exe does not exist yet.")
    sys.exit(1)

file_size = os.path.getsize(exe_src)
print(f"Found dist/Chirp.exe ({file_size} bytes)")

desktops = [
    os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
]

for d in desktops:
    if os.path.exists(d):
        dest_exe = os.path.join(d, "Chirp.exe")
        try:
            shutil.copy2(exe_src, dest_exe)
            print(f"Copied Chirp.exe to {dest_exe}")
        except Exception as e:
            print(f"Error copying Chirp.exe: {e}")

        # Remove old Apper if present to keep desktop clean
        for old_file in ["Apper.exe", "Apper.lnk"]:
            old_p = os.path.join(d, old_file)
            if os.path.exists(old_p):
                try:
                    os.remove(old_p)
                    print(f"Removed legacy {old_file}")
                except Exception:
                    pass

        # Create shortcut .lnk with custom luxury icon
        lnk_path = os.path.join(d, "Chirp.lnk")
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            shortcut.TargetPath = dest_exe
            shortcut.WorkingDirectory = d
            shortcut.Description = "Chirp - AI Voice Dictation Capsule (OpenAI & Gemini)"
            if os.path.exists(ico_path):
                shortcut.IconLocation = f"{ico_path},0"
            else:
                shortcut.IconLocation = f"{dest_exe},0"
            shortcut.save()
            print(f"Created shortcut at {lnk_path}")
        except Exception as e:
            print(f"Error creating shortcut: {e}")

        # Also place the setup installer script on the desktop
        setup_bat = os.path.join(d, "Install_Chirp.bat")
        bat_content = f"""@echo off
title Chirp AI - Voice Dictation Setup
color 0A
echo ========================================================
echo        Chirp AI - Voice Dictation Setup (GPT-4o)
echo ========================================================
echo.
echo Installing Chirp to LocalAppData...
set "TARGET_DIR=%LOCALAPPDATA%\\Chirp"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

copy /Y "{dest_exe}" "%TARGET_DIR%\\Chirp.exe" >nul
if exist "{ico_path}" copy /Y "{ico_path}" "%TARGET_DIR%\\chirp.ico" >nul

echo.
echo [SUCCESS] Chirp AI setup is complete!
echo Launching Chirp...
start "" "%TARGET_DIR%\\Chirp.exe"
exit
"""
        try:
            with open(setup_bat, "w", encoding="utf-8") as f:
                f.write(bat_content)
            print(f"Created setup installer at {setup_bat}")
        except Exception as e:
            print(f"Error creating setup bat: {e}")

# Start Menu Shortcut
start_dir = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Chirp")
os.makedirs(start_dir, exist_ok=True)
lnk_start = os.path.join(start_dir, "Chirp.lnk")
try:
    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_start)
    shortcut.TargetPath = os.path.join(desktops[0] if os.path.exists(desktops[0]) else desktops[1], "Chirp.exe")
    shortcut.WorkingDirectory = os.path.dirname(shortcut.TargetPath)
    shortcut.Description = "Chirp - AI Voice Dictation Capsule (OpenAI GPT-4o & Gemini)"
    if os.path.exists(ico_path):
        shortcut.IconLocation = f"{ico_path},0"
    shortcut.save()
    print(f"Created Start Menu shortcut at {lnk_start}")
except Exception as e:
    print(f"Error creating Start Menu shortcut: {e}")

print("Chirp deployment complete!")
