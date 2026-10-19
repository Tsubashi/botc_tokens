import sys; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
import os
IN = "/Users/cscott/Projects/botc_tokens/.fuzz/in"
OUT = "/Users/cscott/Projects/botc_tokens/.fuzz/out"
os.makedirs(OUT, exist_ok=True)
# Top level
run([]); run(["--bogus"]); run(["nothing"]); run(["CREATE", "--help"]); run(["version", "extra"])
# create: script-source problems (offline-ish: these fail before network)
for f in sorted(os.listdir(IN)):
    run(["create", f"{IN}/{f}", "-o", OUT])
run(["create", "/nonexistent/path.json", "-o", OUT])
run(["create", "", "-o", OUT])
run(["create", "ftp://example.com/x.json", "-o", OUT])
run(["create", "data:application/json;base64,W10=", "-o", OUT])
run(["create", "http://[::1", "-o", OUT])            # malformed URL
run(["create", "http://", "-o", OUT])
run(["create", "https://nonexistent.invalid/x.json", "-o", OUT])
# output dir problems
run(["create", f"{IN}/emptylist.json", "-o", f"{IN}/notjson.json"])  # file as output dir
run(["create", f"{IN}/emptylist.json", "-o", "/dev/null/sub"])
run(["create", f"{IN}/emptylist.json", "-o", ""])
# numeric args
for a in (["--dpi", "0"], ["--dpi", "-1"], ["--dpi", "nan"], ["--dpi", "1e400"], ["--dpi", "99999999"],
          ["--dpi", "1"], ["--role-diameter", "inf"], ["--role-diameter", "1e308"], ["--role-diameter", "0.00001"],
          ["--paper-size", "1", "1"], ["--paper-size", "1e308", "1e308"], ["--margin-horizontal", "1e308"],
          ["--padding", "1e308"], ["--paper-type", "A4"], ["--paper-type", "tabloid"],
          ["--reminder-diameter", "1e9"], ["--dpi", "1", "--role-diameter", "25.3"]):
    run(["create", f"{IN}/emptylist.json", "-o", OUT, *a])
