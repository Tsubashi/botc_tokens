import sys; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
import os
F = "/Users/cscott/Projects/botc_tokens/.fuzz"; IN = f"{F}/in2"; OUT = f"{F}/out2"
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
