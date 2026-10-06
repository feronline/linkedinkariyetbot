"""Zamanlanmis gunluk calistirma (Windows Gorev Zamanlayici bunu sik araliklarla cagirir).

Her gun 10:00-16:30 arasinda RASTGELE bir saat secer; bilgisayar o saatten sonra
acik/uyanik oldugunda bir kez calisir, gun icinde tekrar calismaz. Gun icin basvuru
sayisi da 12-20 arasi rastgeledir (ust sinir profile.json'daki daily_limits).
"""
import json
import random
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "data" / "schedule.json"
LOG = ROOT / "data" / "scheduled.log"
WINDOW_START, WINDOW_END, LATEST = time(10, 0), time(16, 30), time(18, 0)


def pick_target() -> str:
    lo = WINDOW_START.hour * 60 + WINDOW_START.minute
    hi = WINDOW_END.hour * 60 + WINDOW_END.minute
    m = random.randint(lo, hi)
    return f"{m // 60:02d}:{m % 60:02d}"


def main() -> None:
    today = date.today().isoformat()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if st.get("day") != today:
        st = {"day": today, "target": pick_target(), "started": False, "limit": random.randint(12, 20)}
        STATE.write_text(json.dumps(st))
    if st["started"]:
        return
    now = datetime.now().time()
    hh, mm = map(int, st["target"].split(":"))
    if now < time(hh, mm) or now > LATEST:
        return                                   # henuz vakit gelmedi / gun icinde kacirildi
    st["started"] = True                          # cift calismayi onle
    STATE.write_text(json.dumps(st))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M} (hedef {st['target']}, limit {st['limit']}) ===\n")
        f.flush()
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run([sys.executable.replace("pythonw", "python"), "-u", "run.py", "apply", "--limit", str(st["limit"])],
                       cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, creationflags=flags)


if __name__ == "__main__":
    main()
