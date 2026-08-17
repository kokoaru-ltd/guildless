"""Entry point for the bundled runtime executable.

Separate from the CLI on purpose. The packaged product must not depend on the
user having Python, a virtualenv, or a working shell, so this is the single
thing PyInstaller freezes and the desktop shell launches.

It also fixes the working directory. A frozen binary starts wherever the
shortcut points, and a company whose ledger location depends on where its icon
was clicked would keep two sets of books.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def data_home() -> Path:
    """Where the books live.

    Under the user's profile rather than beside the executable: Program Files
    is not writable, and a ledger that fails to save is worse than one that
    never existed.
    """
    # Resolved, because the write boundary resolves too. A path that reaches
    # the same directory by a different route -- a junction, a redirect, a
    # mapped drive -- fails the boundary check even though both sides mean the
    # same folder, and the runtime then refuses to start.
    override = os.getenv("GUILDLESS_HOME")
    if override:
        return Path(override).resolve()
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    return (Path(base) / "Guildless").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(prog="guildless-runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()

    home = data_home()
    (home / "runs").mkdir(parents=True, exist_ok=True)
    # Set rather than defaulted: an inherited value from the launching shell
    # would point somewhere the boundary does not allow.
    os.environ["GUILDLESS_HOME"] = str(home)
    os.environ["COUNCIL_OUTPUT_DIR"] = str(home / "runs")
    os.environ["COUNCIL_RUNTIME_DIR"] = str(home / ".runtime")
    os.chdir(home)

    # Imported after the environment is set, because settings are read at
    # import time and would otherwise bind to the wrong directory.
    import uvicorn

    from council.api import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
