import sys, glob; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
F = "/Users/cscott/Projects/botc_tokens/.fuzz"
for f in sorted(glob.glob(f"{F}/in2/word_*.json")):
    run(["create", f, "-o", f"{F}/out7"], timeout=120)
