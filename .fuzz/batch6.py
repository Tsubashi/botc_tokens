import sys, time; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
F = "/Users/cscott/Projects/botc_tokens/.fuzz"; IN = f"{F}/in2"; OUT = f"{F}/out6"
for f in ("ability_word20", "ability_word30", "ability_word45", "ability_word80", "ability_url", "reminder_word60", "name_word80"):
    run(["create", f"{IN}/{f}.json", "-o", OUT], timeout=120)
for f in ("ability_words60", "ability_words120", "ability_words200"):
    t = time.time(); run(["create", f"{IN}/{f}.json", "-o", OUT], timeout=240); print(f"    took {time.time()-t:.0f}s")
