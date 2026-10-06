"""Yerel arayuz: python run.py ui  ->  http://127.0.0.1:8765
Yalnizca bu bilgisayardan erisilir (127.0.0.1). Ek paket gerekmez."""
import email.parser
import email.policy
import json
import secrets
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from botcore import profile as P
from botcore.analyzer import analyze_cv
from botcore.quota import Quota

ROOT = Path(__file__).resolve().parent
PORT = 8765
TOKEN = secrets.token_urlsafe(16)
PROC: dict[str, subprocess.Popen | None] = {"apply": None, "login": None}
LOG = ROOT / "data" / "ui_run.log"
_cache: dict[str, tuple[float, dict]] = {}


def running(name: str) -> bool:
    p = PROC[name]
    return p is not None and p.poll() is None


def spawn(name: str, args: list[str]) -> None:
    if running(name):
        return
    LOG.parent.mkdir(exist_ok=True)
    f = open(LOG, "a", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and name == "apply" else 0
    PROC[name] = subprocess.Popen([sys.executable, "-u", "run.py", *args], cwd=ROOT, stdout=f,
                                  stderr=subprocess.STDOUT, creationflags=flags)


def cv_info(path: Path) -> dict:
    m = path.stat().st_mtime
    if path.name not in _cache or _cache[path.name][0] != m:
        a = analyze_cv(path)
        top = sorted(a.skills.items(), key=lambda x: -x[1])[:14]
        _cache[path.name] = (m, {"name": path.name, "years": a.years, "seniority": a.seniority,
                                 "roles": [r for r, _ in a.roles], "search": a.search_keywords,
                                 "skills": [k for k, _ in top]})
    return _cache[path.name][1]


def state() -> dict:
    prof = P.load()
    q = Quota(prof["daily_limits"])
    rows = q.con.execute("SELECT ts,site,status,score,title,company,profile,note FROM jobs "
                         "WHERE status!='skipped' ORDER BY ts DESC LIMIT 60").fetchall()
    stats = dict(q.con.execute("SELECT status,COUNT(*) FROM jobs GROUP BY 1").fetchall())
    qs = {}
    for (note,) in q.con.execute("SELECT note FROM jobs WHERE status='needs_answer'"):
        for part in (note or "").split(";"):
            part = " ".join(part.split())
            low = part.lower()
            noise = ("hata:", "diyalog", "zorunlu", "lütfen", "lutfen", "please", "geçerli", "gecerli",
                     "decimal", "değerinden", "required", "must be", "select an option", "bir seçenek")
            if 3 < len(part) < 160 and not any(n in low for n in noise):
                qs[part] = qs.get(part, 0) + 1
    from botcore.textutil import fold
    answers = {fold(k): v for k, v in prof["answers"].items()}
    done = [(q, answers[fold(q)]) for q in qs if fold(q) in answers]
    qs = {q: n for q, n in qs.items() if fold(q) not in answers}
    log = LOG.read_text(encoding="utf-8", errors="replace")[-3000:] if LOG.exists() else ""
    return {
        "token": TOKEN, "profile": prof, "stats": stats,
        "quota": {s: [q.used_today(s), q.daily[s]] for s in q.daily},
        "running": running("apply"), "login_running": running("login"),
        "logged_in": (ROOT / "data/sessions/linkedin.json").exists(),
        "cvs": [cv_info(p) for p in P.cv_files()],
        "jobs": [dict(zip(("ts", "site", "status", "score", "title", "company", "cv", "note"), r)) for r in rows],
        "questions": sorted(qs.items(), key=lambda x: -x[1])[:15], "answered": done, "log": log,
    }


def parse_upload(headers, body: bytes) -> tuple[str, bytes] | None:
    msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        b"Content-Type: " + headers["Content-Type"].encode() + b"\r\n\r\n" + body)
    for part in msg.iter_parts():
        name = part.get_filename()
        if name:
            return Path(name).name, part.get_payload(decode=True)
    return None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code=200, body=b"", ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def local_ok(self) -> bool:
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self.local_ok():
            return self.send(403)
        path = urlparse(self.path).path
        if path == "/":
            return self.send(200, PAGE, "text/html")
        if path == "/api/state":
            return self.send(200, state())
        self.send(404)

    def do_POST(self):
        if not self.local_ok() or self.headers.get("X-Token") != TOKEN:
            return self.send(403, {"error": "yetkisiz"})
        url = urlparse(self.path)
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        try:
            if url.path == "/api/upload":
                got = parse_upload(self.headers, raw)
                if not got or Path(got[0]).suffix.lower() not in (".pdf", ".docx"):
                    return self.send(400, {"error": "PDF veya DOCX yukle"})
                P.CV_DIR.mkdir(parents=True, exist_ok=True)
                (P.CV_DIR / got[0]).write_bytes(got[1])
            elif url.path == "/api/delete_cv":
                name = Path(parse_qs(url.query)["name"][0]).name
                (P.CV_DIR / name).unlink(missing_ok=True)
            elif url.path == "/api/profile":
                P.save(json.loads(raw))
            elif url.path == "/api/answer":
                d = json.loads(raw)
                prof = P.load()
                prof["answers"][d["key"]] = d["value"]
                P.save(prof)
            elif url.path == "/api/start":
                spawn("apply", ["apply"])
            elif url.path == "/api/stop":
                if running("apply"):
                    PROC["apply"].terminate()
            elif url.path == "/api/login":
                spawn("login", ["login"])
            else:
                return self.send(404)
        except Exception as e:
            return self.send(500, {"error": str(e)})
        self.send(200, {"ok": True})


PAGE = (ROOT / "ui.html").read_text(encoding="utf-8") if (ROOT / "ui.html").exists() else "ui.html eksik"


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Arayuz: {url}  (kapatmak icin Ctrl+C)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
