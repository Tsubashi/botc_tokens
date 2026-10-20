import sys; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
import os, json
F = "/Users/cscott/Projects/botc_tokens/.fuzz"
IN = f"{F}/in2"
C = "/Users/cscott/Projects/botc_tokens/.fuzz/comp"
OUT = "/Users/cscott/Projects/botc_tokens/.fuzz/out2"
os.makedirs(OUT, exist_ok=True)
skip = {"many_roles.json", "image_junk.json"}  # slow/network ones run separately
for f in sorted(os.listdir(IN)):
    if f.endswith(".json") and f not in skip:
        run(["create", f"{IN}/{f}", "-o", OUT])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "--skip-ability-text"])
run(["create", f"{IN}/image_tiny.json", "-o", OUT, "--skip-ability-text", "--dpi", "10"])
# component packages
for c in ("badfont", "badimg", "tinybg", "dirs.zip", "empty.zip", "notzip.zip", "/nonexistent", ""):
    run(["create", f"{IN}/name_empty.json", "-o", OUT, "-c", f"{C}/{c}" if not c.startswith("/") and c else c])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-c", f"{IN}/notjson.json"])
# override files
ov = f"{F}/ov"; os.makedirs(ov, exist_ok=True)
cases = {
 "dup_notjson.json": "x", "dup_list.json": "[]", "dup_badkey.json": '{"A B": 1}', "dup_str.json": '{"a": "1"}',
 "dup_neg.json": '{"a": -1}', "dup_zero.json": '{"a": 0}', "dup_float.json": '{"a": 1.0}',
 "dup_huge.json": '{"a": 100000}',
 "il_notjson.json": "x", "il_list.json": "[]", "il_int.json": '{"a": 1}', "il_empty.json": '{"a": ""}',
 "il_null.json": '{"a": "\\u0000"}', "il_dir.json": '{"a": "."}',
}
for n, body in cases.items():
    open(f"{ov}/{n}", "w").write(body)
    flag = "--duplicates" if n.startswith("dup") else "--icon-lookup"
    run(["create", f"{IN}/name_empty.json", "-o", OUT, flag, f"{ov}/{n}"])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "--duplicates", "/nonexistent.json"])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "--duplicates", ov])  # a directory
run(["create", f"{IN}/name_empty.json", "-o", OUT, "--icon-lookup", ov])
# intermediate dir
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-m", f"{IN}/notjson.json"])  # a file
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-m", f"{IN}/notjson.json/sub"])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-m", ""])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-m", f"{F}/inter", "--incremental"])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-m", f"{F}/inter", "--incremental"])
# read-only dirs
ro = f"{F}/ro"; os.makedirs(ro, exist_ok=True); os.chmod(ro, 0o500)
run(["create", f"{IN}/name_empty.json", "-o", ro])
run(["create", f"{IN}/name_empty.json", "-o", f"{ro}/sub"])
run(["create", f"{IN}/name_empty.json", "-o", OUT, "-m", ro])
os.chmod(ro, 0o700)
# unreadable script
ur = f"{F}/unreadable.json"; open(ur, "w").write("[]"); os.chmod(ur, 0)
run(["create", ur, "-o", OUT]); os.chmod(ur, 0o600)
