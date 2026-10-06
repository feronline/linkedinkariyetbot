"""Kalici kota ve 'daha once denendi' kaydi (SQLite, data/state.db)."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB = Path("data/state.db")

# Muhafazakar varsayilanlar. Siteler resmi limit yayinlamaz; kendi hesabina gore ayarla.
DEFAULT_DAILY = {"linkedin": 20, "kariyernet": 20}


class Quota:
    def __init__(self, daily: dict | None = None, db: Path = DB):
        db.parent.mkdir(parents=True, exist_ok=True)
        self.daily = {**DEFAULT_DAILY, **(daily or {})}
        self.con = sqlite3.connect(db)
        self.con.execute("""CREATE TABLE IF NOT EXISTS jobs(
            site TEXT, job_id TEXT, title TEXT, company TEXT, profile TEXT,
            score INTEGER, status TEXT, note TEXT, ts TEXT, day TEXT,
            PRIMARY KEY(site, job_id))""")
        self.con.commit()

    def used_today(self, site: str) -> int:
        r = self.con.execute("SELECT COUNT(*) FROM jobs WHERE site=? AND day=? AND status='applied'",
                             (site, date.today().isoformat())).fetchone()
        return r[0]

    def remaining(self, site: str) -> int:
        return max(0, self.daily.get(site, 20) - self.used_today(site))

    def seen(self, site: str, job_id: str) -> bool:
        return self.con.execute("SELECT 1 FROM jobs WHERE site=? AND job_id=?", (site, job_id)).fetchone() is not None

    def record(self, site, job_id, title, company, profile, score, status, note=""):
        now = datetime.now()
        self.con.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (site, job_id, title, company, profile, score, status, note,
                          now.isoformat(timespec="seconds"), now.date().isoformat()))
        self.con.commit()

    def lock_today(self, site: str):
        """Site 'limit doldu' dediginde bugunu kapat."""
        self.daily[site] = self.used_today(site)
