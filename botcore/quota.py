"""Kalici kota ve 'daha once denendi' kaydi (SQLite, data/state.db)."""
import json
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
        self.con.execute("""CREATE TABLE IF NOT EXISTS questions(
            label TEXT PRIMARY KEY, kind TEXT, options TEXT, n INTEGER, ts TEXT)""")
        try:
            self.con.execute("ALTER TABLE jobs ADD COLUMN location TEXT")
        except sqlite3.OperationalError:
            pass                                  # sutun zaten var
        self.con.commit()

    def add_questions(self, missing: dict):
        now = datetime.now().isoformat(timespec="seconds")
        for label, info in missing.items():
            self.con.execute(
                "INSERT INTO questions VALUES(?,?,?,1,?) ON CONFLICT(label) DO UPDATE SET "
                "n=n+1, kind=excluded.kind, options=excluded.options, ts=excluded.ts",
                (label, info["kind"], json.dumps(info["options"], ensure_ascii=False), now))
        self.con.commit()

    def used_today(self, site: str, location: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM jobs WHERE site=? AND day=? AND status='applied'"
        args = [site, date.today().isoformat()]
        if location is not None:
            sql += " AND location=?"
            args.append(location)
        return self.con.execute(sql, args).fetchone()[0]

    def remaining(self, site: str) -> int:
        return max(0, self.daily.get(site, 20) - self.used_today(site))

    def seen(self, site: str, job_id: str, retry_after: float = 0.0) -> bool:
        """retry_after: 'cevap gerekli' kayitlar bu zamandan (epoch) eskiyse tekrar denenir."""
        r = self.con.execute("SELECT status, ts FROM jobs WHERE site=? AND job_id=?", (site, job_id)).fetchone()
        if r is None:
            return False
        if r[0] == "needs_answer" and retry_after and datetime.fromisoformat(r[1]).timestamp() < retry_after:
            return False
        return True

    def record(self, site, job_id, title, company, profile, score, status, note="", location=""):
        now = datetime.now()
        self.con.execute("INSERT OR REPLACE INTO jobs(site,job_id,title,company,profile,score,status,note,ts,day,location) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (site, job_id, title, company, profile, score, status, note,
                          now.isoformat(timespec="seconds"), now.date().isoformat(), location))
        self.con.commit()

    def lock_today(self, site: str):
        """Site 'limit doldu' dediginde bugunu kapat."""
        self.daily[site] = self.used_today(site)
