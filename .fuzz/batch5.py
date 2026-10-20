import sys; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
import os
F = "/Users/cscott/Projects/botc_tokens/.fuzz"; IN = f"{F}/in2"; OUT = f"{F}/out5"; os.makedirs(OUT, exist_ok=True)
S = f"{IN}/reminder_empty.json"
run(["create", S, "-o", OUT, "--dpi", "1", "--role-diameter", "1", "--reminder-diameter", "1"], timeout=120)
run(["create", S, "-o", OUT, "--dpi", "1", "--role-diameter", "1", "--reminder-diameter", "1", "--margin-horizontal", "0", "--margin-vertical", "0"], timeout=120)
run(["create", S, "-o", OUT, "--dpi", "1", "--role-diameter", "30", "--reminder-diameter", "30", "--margin-horizontal", "0", "--margin-vertical", "0"], timeout=120)
run(["create", S, "-o", OUT, "--dpi", "3", "--role-diameter", "46", "--reminder-diameter", "26", "--margin-horizontal", "0", "--margin-vertical", "0", "--padding", "0.1"], timeout=120)
run(["create", S, "-o", OUT, "--dpi", "300", "--paper-size", "50", "50", "--role-diameter", "46", "--margin-horizontal", "0", "--margin-vertical", "0"], timeout=120)
run(["create", S, "-o", OUT, "--dpi", "300", "--paper-size", "50", "50", "--role-diameter", "46", "--margin-horizontal", "0", "--margin-vertical", "0", "--grid"], timeout=120)
run(["create", S, "-o", OUT, "--dpi", "4000"], timeout=300)
run(["create", S, "-o", OUT, "--dpi", "300", "--paper-size", "5000", "5000"], timeout=300)
