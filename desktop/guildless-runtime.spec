# PyInstaller spec for the runtime the desktop app ships.
#
# A directory rather than one file. The onefile bootloader unpacks itself and
# then verifies that its parent process is the same executable, which is false
# when the desktop shell launches it -- it refuses to start with "parent process
# has different executable". A sidecar is launched by another program by
# definition, so onefile is the wrong shape here. It also avoids re-extracting
# seventy megabytes on every start.

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("council")
    + [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "fastapi",
        "pydantic",
        "httpx",
        "dotenv",
    ]
)

a = Analysis(
    ["runtime_entry.py"],
    pathex=[".."],
    binaries=[],
    # The built UI travels with the runtime, so the desktop shell can serve the
    # real screen without a separate web build step on the user's machine.
    datas=[("../frontend/dist", "frontend/dist")],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    # Heavy optional dependencies that the packaged runtime never touches.
    excludes=["faster_whisper", "torch", "playwright", "browser_use", "tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="guildless-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="guildless-runtime",
)
