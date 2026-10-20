"""Run botc_tokens in a subprocess with given argv; report uncaught exceptions and hangs."""
import os, subprocess, sys
PY = "/Users/cscott/Projects/botc_tokens/.venv/bin/python"
ENV = {**os.environ, "MAGICK_HOME": "/opt/homebrew/", "PYTHONPATH": "/Users/cscott/Projects/botc_tokens/src",
       "TERM": "dumb", "NO_COLOR": "1", "COLUMNS": "200"}
def run(argv, label=None, timeout=90):
    label = label or " ".join(argv)
    try:
        p = subprocess.run([PY, "-m", "botc_tokens", *argv], capture_output=True, text=True, timeout=timeout, env=ENV,
                           cwd="/Users/cscott/Projects/botc_tokens")
    except subprocess.TimeoutExpired:
        print(f"[HANG >{timeout}s] {label}", flush=True); return "hang"
    out = p.stdout + p.stderr
    if "Traceback (most recent call last)" in out:
        lines = out.strip().splitlines()
        print(f"[TRACEBACK] {label}\n    " + "\n    ".join(lines[-7:]), flush=True); return "tb"
    print(f"[ok exit={p.returncode}] {label}", flush=True)
    return None
