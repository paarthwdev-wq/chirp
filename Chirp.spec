# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['chirp_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('chirp.ico', '.'),
        ('chirp_logo.png', '.')
    ],
    hiddenimports=[
        'speech_recognition',
        'win32gui',
        'win32con',
        'win32api',
        'win32process',
        'pyperclip',
        'keyboard',
        'pyaudio',
        'audioop',
        'wave',
        'winsound',
        'requests'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'scipy',
        'pandas',
        'numpy.testing',
        'boto3',
        'botocore',
        'tensorflow',
        'playwright',
        'matplotlib',
        'IPython',
        'jupyter',
        'cv2',
        'PIL.SpiderImagePlugin'
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Chirp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='chirp.ico',
)
