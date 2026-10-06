"""Kullanim:
    python run.py setup            data/cvs icindeki CV'leri analiz et, data/profile.json olustur
    python run.py login            tarayicida LinkedIn'e elle giris yap, oturumu kaydet
    python run.py apply --dry      basvurmadan, hangi ilanlara basvurulacagini goster
    python run.py apply            basvur (gunluk kotaya kadar)
    python run.py ui               yerel arayuzu ac (http://127.0.0.1:8765)
    python run.py status           bugunku kota ve son kayitlar
"""
import argparse
import asyncio
import io
import logging
import sys

from botcore import profile as P
from botcore.analyzer import analyze_cv
from botcore.quota import Quota

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("bot")


def cmd_setup(_):
    files = P.cv_files()
    if not files:
        sys.exit(f"{P.CV_DIR} icine CV'ni (PDF/DOCX) koy, sonra tekrar calistir.")
    for f in files:
        a = analyze_cv(f)
        print(f"\n{f.name}: ~{a.years} yil ({a.seniority}) roller={a.roles}\n  arama={a.search_keywords}")
    if not P.PROFILE.exists():
        P.save(P.load())
        print(f"\n{P.PROFILE} olusturuldu. Telefon, maas, website gibi cevaplari 'answers' altina yaz.")


SITES = {"linkedin": "https://www.linkedin.com/login"}


async def cmd_login(args):
    """Tarayici acar; dogrulama (captcha/basili tut) ve girisi SEN yaparsin. Pencereyi kapatinca oturum kaydedilir."""
    from playwright.async_api import async_playwright
    site = getattr(args, "site", "linkedin")
    P.SESSIONS.mkdir(parents=True, exist_ok=True)
    out = P.SESSIONS / f"{site}.json"
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=False)
        c = await b.new_context(viewport=None, locale="tr-TR")
        pg = await c.new_page()
        await pg.goto(SITES[site])
        print(f"{site}: acilan pencerede dogrulamayi coz ve giris yap. Bitince pencereyi KAPAT; oturum kaydedilir.")
        try:
            while not pg.is_closed():
                await asyncio.sleep(3)
                try:
                    await c.storage_state(path=str(out))     # surekli kaydet: pencere kapaninca son hali kalir
                except Exception:
                    break
        finally:
            await b.close()
        print(f"Oturum kaydedildi: {out}")


async def cmd_apply(args):
    from playwright.async_api import async_playwright
    from botcore.linkedin import LinkedIn, SESSION
    prof = P.load()
    cvs = [analyze_cv(f) for f in P.cv_files()]
    if not cvs:
        sys.exit("data/cvs icinde CV yok.")
    if not SESSION.exists():
        sys.exit("Once: python run.py login")
    if args.min_score:
        prof["min_score"] = args.min_score
    q = Quota(prof["daily_limits"])
    if args.limit:
        q.daily["linkedin"] = min(q.daily["linkedin"], q.used_today("linkedin") + args.limit)
    log.info(f"Bugun kalan LinkedIn kotasi: {q.remaining('linkedin')}")
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=False)
        c = await b.new_context(storage_state=str(SESSION), viewport={"width": 1400, "height": 900})
        bot = LinkedIn(await c.new_page(), prof, cvs, q, log)
        if not await bot.ensure_login():
            sys.exit("Oturum gecersiz. python run.py login")
        await bot.run(dry=args.dry)
        await b.close()


def cmd_ui(_):
    import ui
    ui.main()


def cmd_status(_):
    prof = P.load()
    q = Quota(prof["daily_limits"])
    for site in q.daily:
        print(f"{site}: bugun {q.used_today(site)}/{q.daily[site]}")
    for r in q.con.execute("SELECT ts,site,status,score,title,company,note FROM jobs ORDER BY ts DESC LIMIT 15"):
        print(r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("setup")
    lg = sp.add_parser("login")
    lg.add_argument("site", nargs="?", default="linkedin", choices=list(SITES))
    sp.add_parser("status")
    sp.add_parser("ui")
    a = sp.add_parser("apply")
    a.add_argument("--dry", action="store_true")
    a.add_argument("--limit", type=int, help="bu calistirmada en fazla N basvuru")
    a.add_argument("--min-score", type=int, help="en az puan (varsayilan 50)")
    ns = ap.parse_args()
    res = {"setup": cmd_setup, "login": cmd_login, "apply": cmd_apply, "status": cmd_status, "ui": cmd_ui}[ns.cmd](ns)
    if asyncio.iscoroutine(res):
        asyncio.run(res)
