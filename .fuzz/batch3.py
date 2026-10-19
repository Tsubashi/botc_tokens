import sys; sys.path.insert(0, "/Users/cscott/Projects/botc_tokens/.fuzz")
from harness import run
import os
F = "/Users/cscott/Projects/botc_tokens/.fuzz"
# dump
run(["dump"]); run(["dump", "bogus"]); run(["dump", "all", f"{F}/dump_out"]); run(["dump", "components", f"{F}/dump_out"])
run(["dump", "all", f"{F}/in/notjson.json"])              # output dir is a file
run(["dump", "duplicates", f"{F}/in/notjson.json"])
run(["dump", "icon-lookup", f"{F}/in/notjson.json/sub"])
run(["dump", "all", ""])
ro = f"{F}/ro2"; os.makedirs(ro, exist_ok=True); os.chmod(ro, 0o500)
run(["dump", "all", ro]); run(["dump", "duplicates", f"{ro}/sub"]); os.chmod(ro, 0o700)
# migrate
run(["migrate"]); run(["migrate", "-i", "/nonexistent"]); run(["migrate", "-i", f"{F}/in/notjson.json"])
run(["migrate", "-i", f"{F}/mig/empty", f"{F}/mig_out"])
run(["migrate", "-i", f"{F}/mig/one", f"{F}/mig_out"])
run(["migrate", "-i", f"{F}/mig", f"{F}/mig_out"])
run(["migrate", "-i", f"{F}/mig/direct", f"{F}/mig_out"])
run(["migrate", "-i", f"{F}/mig/dirjson", f"{F}/mig_out"])
run(["migrate", "-i", f"{F}/mig/two", f"{F}/mig_out"])
run(["migrate", "-i", f"{F}/mig/direct", f"{F}/in/notjson.json"])  # output is a file
run(["migrate", "-i", f"{F}/mig/one", f"{F}/in/notjson.json"])
run(["migrate", "-i", f"{F}/mig/direct", ""])
os.chmod(ro, 0o500); run(["migrate", "-i", f"{F}/mig/one", ro]); run(["migrate", "-i", f"{F}/mig/direct", ro]); os.chmod(ro, 0o700)
unr = f"{F}/mig/unreadable"; os.makedirs(unr, exist_ok=True); os.chmod(unr, 0)
run(["migrate", "-i", unr, f"{F}/mig_out"]); os.chmod(unr, 0o700)
# pad-icons
run(["pad-icons"]); run(["pad-icons", "/nonexistent"]); run(["pad-icons", f"{F}/in/notjson.json"])
run(["pad-icons", f"{F}/pad/empty"]); run(["pad-icons", f"{F}/pad"]); run(["pad-icons", f"{F}/pad", "-i"])
os.chmod(ro, 0o500); run(["pad-icons", ro]); os.chmod(ro, 0o700)
import shutil; rop = f"{F}/ro_pad"; os.makedirs(rop, exist_ok=True); shutil.copy(f"{F}/pad/corner.png", rop); os.chmod(rop, 0o500)
run(["pad-icons", rop]); os.chmod(rop, 0o700)
