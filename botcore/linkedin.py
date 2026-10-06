"""LinkedIn Easy Apply adaptoru. Dil bagimsiz: data-* ozellikleri + katlanmis metin.

Arayuz Turkce de olsa Ingilizce de olsa calismasi icin hicbir yerde tek dilli
aria-label'a guvenilmez. Secici/anahtar kelimeler dosyanin basinda toplanmistir.
"""
from __future__ import annotations

import asyncio
import difflib
import random
import re
from pathlib import Path

from .analyzer import CVAnalysis, score_job
from .quota import Quota
from .textutil import fold

SITE = "linkedin"
SESSION = Path("data/sessions/linkedin.json")

# -- Secici / anahtar kelime merkezi (LinkedIn degisince SADECE burasi) --
MODAL = ":is(.jobs-easy-apply-modal, [role=dialog].artdeco-modal)"   # :is() -> sonraki secicilere dogru uygulanir
APPLY_BTN = "button.jobs-apply-button"
CARD = "[data-occludable-job-id]"
CLOSE_BTN = "[data-test-modal-close-btn]"
DESC = "#job-details, .jobs-description__content, .jobs-box__html-content"
KW_SUBMIT = ("gonder", "submit", "send application")
KW_EASY = ("kolay basvuru", "easy apply")
KW_SENT = ("basvurunuz gonderildi", "application sent", "application was sent", "basvuru gonderildi")
NUM_HINTS = ("how many", "kac", "years", "yil", "number of", "sayi", "salary", "maas", "ucret", "notice", "ihbar")
YES, NO = ("yes", "evet"), ("no", "hayir")
EXP_CODES = {"Internship": 1, "Entry level": 2, "Associate": 3, "Mid-Senior level": 4, "Director": 5}

FORM_JS = r"""(sel) => {
 const m=document.querySelector(sel); if(!m) return [];
 const out=[]; let i=0;
 const esc=(s)=>CSS.escape(s);
 const lab=(e)=>{ let t='';
   const fs=e.closest('fieldset'); if(e.type==='radio'&&fs){const lg=fs.querySelector('legend'); if(lg) t=lg.innerText;}
   if(!t&&e.id){const l=m.querySelector('label[for="'+esc(e.id)+'"]'); if(l) t=l.innerText;}
   if(!t) t=e.getAttribute('aria-label')||'';
   if(!t){const g=e.closest('[data-test-form-element],.fb-dash-form-element,.jobs-easy-apply-form-element'); if(g){const l=g.querySelector('label,legend'); if(l) t=l.innerText;}}
   return t.trim().replace(/\s+/g,' ');};
 for(const e of m.querySelectorAll('input,select,textarea')){
   if(['file','hidden','submit','button'].includes(e.type)) continue;
   if(e.id.startsWith('jobsDocumentCardToggle')) continue;
   if(e.offsetParent===null) continue;
   e.setAttribute('data-bot-i', i);
   let opt='';
   if(e.type==='radio'||e.type==='checkbox'){const l=e.id&&m.querySelector('label[for="'+esc(e.id)+'"]'); opt=l?l.innerText.trim():'';}
   out.push({i,tag:e.tagName.toLowerCase(),type:e.type,label:lab(e),value:e.value,checked:e.checked,opt,
     options:e.tagName==='SELECT'?[...e.options].map(o=>({v:o.value,t:o.text.trim()})):null});
   i++;}
 return out;}"""


class LinkedIn:
    def __init__(self, page, profile: dict, cvs: list[CVAnalysis], quota: Quota, log):
        self.page, self.prof, self.cvs, self.q, self.log = page, profile, cvs, quota, log
        self.limit_hit = False
        self.dry_seen: set[str] = set()

    # -- yardimcilar --
    async def pause(self):
        a, b = self.prof["delay_seconds"]
        await asyncio.sleep(random.uniform(a, b))

    def answer_for(self, label: str) -> str | None:
        f = fold(label)
        in_tr = "turkey" in f or "turkiye" in f
        if in_tr and any(k in f for k in ("authoriz", "calisma izni", "work permit", "right to work", "eligible")):
            return "yes"                      # Turkiye'de calisma izni sorulursa: evet
        if in_tr and any(k in f for k in ("sponsor", "vize", "visa")):
            return "no"
        for key in sorted(self.prof["answers"], key=len, reverse=True):
            val = self.prof["answers"][key]
            if isinstance(val, list):         # liste ise rastgele biri (ornegin maas araligi)
                val = random.choice(val) if val else ""
            if val != "" and fold(key) in f:
                return str(val)
        # "How many years of ... experience with X?" gibi sorular: genel deneyim yili
        if any(k in f for k in ("how many years", "years of", "kac yil", "yillik", "yil deneyim")):
            v = self.prof["answers"].get("years of experience", "")
            return str(v) if v != "" else None
        return None

    # -- giris --
    async def ensure_login(self) -> bool:
        await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        return "/feed" in self.page.url

    # -- arama --
    def search_url(self, keywords: str, cv: CVAnalysis, start: int = 0) -> str:
        p = ["f_AL=true", f"keywords={keywords.replace(' ', '%20')}", "sortBy=DD"]
        if self.prof["location"]:
            p.append(f"location={self.prof['location'].replace(' ', '%20')}")
        wt = {"Remote": 2, "On-site": 1, "Hybrid": 3}.get(self.prof["work_type"])
        if wt:
            p.append(f"f_WT={wt}")
        codes = [str(EXP_CODES[l]) for l in cv.experience_levels if l in EXP_CODES]
        if codes:
            p.append("f_E=" + "%2C".join(codes))
        if start:
            p.append(f"start={start}")
        return "https://www.linkedin.com/jobs/search/?" + "&".join(p)

    async def list_job_ids(self, url: str) -> list[str]:
        await self.page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        for _ in range(4):  # sanal liste: kaydirarak kartlari yukle
            await self.page.mouse.wheel(0, 1200)
            await asyncio.sleep(0.8)
        return await self.page.eval_on_selector_all(
            CARD, "els=>els.map(e=>e.getAttribute('data-occludable-job-id'))")

    # -- ilan ayrintisi (kart her seferinde id ile yeniden bulunur: 'stale' hatasi olmaz) --
    async def open_job(self, job_id: str) -> dict | None:
        card = self.page.locator(f"{CARD}[data-occludable-job-id='{job_id}']")
        try:
            await card.scroll_into_view_if_needed(timeout=5000)
            await card.locator("a[href*='/jobs/view/']").first.click(timeout=5000)
        except Exception:
            return None
        await asyncio.sleep(2.5)
        title = ""
        if await self.page.locator("h1").count():
            title = (await self.page.locator("h1").first.inner_text()).strip()
        company = ""
        for sel in ("[class*='unified-top-card__company-name']", "a[href*='/company/']:not(:has(img))"):
            c = self.page.locator(sel).first
            if await c.count():
                company = " ".join((await c.inner_text()).split())
                if company and "logo" not in company.lower():
                    break
        desc = ""
        d = self.page.locator(DESC).first
        if await d.count():
            desc = await d.inner_text()
        return {"id": job_id, "title": title, "company": company, "desc": desc}

    def best_cv(self, job: dict):
        scored = [(score_job(job["title"], job["desc"], cv, self.prof.get("any_software", True)), cv) for cv in self.cvs]
        return max(scored, key=lambda x: x[0].score)

    # -- Easy Apply --
    async def easy_apply_button(self):
        """Metne gore bulur (sinif adina bagli degil); ust filtre hapini (pill) haric tutar."""
        cand = self.page.locator("button:not(.artdeco-pill)", has_text=re.compile(r"kolay\s+ba.vuru|easy\s+apply", re.I))
        for _ in range(8):  # buton gec render edilebilir: 4 sn'ye kadar bekle
            for b in await cand.all():
                try:
                    if await b.is_visible():
                        txt = fold(await b.inner_text())
                        if any(k in txt for k in KW_EASY):
                            return b
                except Exception:
                    pass
            await asyncio.sleep(0.5)
        return None

    async def close_modal(self):
        try:
            btn = self.page.locator(CLOSE_BTN).first
            if await btn.count():
                await btn.click(timeout=3000)
                await asyncio.sleep(1)
                dlg = self.page.locator("[role=alertdialog]")
                if await dlg.count():
                    for b in await dlg.locator("button").all():  # 'kaydet' olmayan = at/discard
                        t = fold(await b.inner_text())
                        if t and not any(k in t for k in ("kaydet", "save")) and "dismiss" not in t:
                            await b.click(timeout=3000)
                            break
        except Exception:
            pass
        await asyncio.sleep(1)

    async def tick(self, el):
        """Ozel radio/checkbox: gizli input yerine etikete tiklar (check() durumu degismiyor diye hata veriyordu)."""
        _id = await el.get_attribute("id")
        lbl = self.page.locator(f"label[for='{_id}']") if _id else None
        if lbl is not None and await lbl.count():
            await lbl.first.click(timeout=3000)
        else:
            await el.click(force=True, timeout=3000)

    async def pick_resume(self, cv: CVAnalysis):
        """Ozgecmis adimi varsa: ada en cok benzeyen kayitli CV'yi sec, yoksa dosyayi yukle."""
        modal = self.page.locator(MODAL)
        radios = modal.locator("input[id^='jobsDocumentCardToggle']")
        has_file = await modal.locator("input[type=file]").count()
        if not await radios.count() and not has_file:
            return
        more = modal.locator("button:has-text('daha göster'), button:has-text('more resume')")
        if await more.count():
            try:
                await more.first.click(timeout=2000)
                await asyncio.sleep(0.5)
            except Exception:
                pass
        stem = fold(Path(cv.file).stem)
        best, best_r, best_txt = None, 0.0, ""
        for r in await radios.all():
            lbl = modal.locator(f"label[for='{await r.get_attribute('id')}']")
            txt = fold(await lbl.inner_text()) if await lbl.count() else ""
            m = re.search(r"resume\s+(.+?)\s+(?:ogesini|belgesini|is )", txt) or re.search(r"resume\s+(\S+)", txt)
            name = fold(Path(m.group(1)).stem) if m else txt
            ratio = difflib.SequenceMatcher(None, stem, name).ratio()
            if name and (stem in name or name in stem):
                ratio = max(ratio, 0.9)
            if ratio > best_r:
                best, best_r, best_txt = r, ratio, txt
        if best is not None and best_r >= 0.6:
            if not any(k in best_txt for k in ("secimini kaldir", "deselect", "unselect")):
                await self.tick(best)
            return
        if has_file:
            await modal.locator("input[type=file]").first.set_input_files(cv.file)
            await asyncio.sleep(2)

    async def fill_step(self) -> list[str]:
        """Gorunen alanlari doldurur; cevaplanamayan etiketleri dondurur."""
        unresolved = []
        fields = await self.page.evaluate(FORM_JS, MODAL)
        radios: dict[str, list] = {}

        def loc(i):
            return self.page.locator(f"[data-bot-i='{i}']")

        for f in fields:
            lab, t = f["label"], f["type"]
            fl = fold(lab)
            try:
                if t == "radio":
                    radios.setdefault(lab, []).append(f)
                elif t == "checkbox":
                    if any(k in fl for k in ("follow", "takip")) and f["checked"]:
                        await self.tick(loc(f["i"]))
                    elif any(k in fold(f["opt"] + fl) for k in ("agree", "kabul", "consent", "onay", "terms")) and not f["checked"]:
                        await self.tick(loc(f["i"]))
                elif f["tag"] == "select":
                    opts = f["options"]
                    cur = next((o for o in opts if o["v"] == f["value"]), None)
                    if f["value"] and cur and not fold(cur["t"]).startswith(("select", "bir secenek")):
                        continue
                    ans = fold(self.answer_for(lab) or "")
                    pick = None
                    if ans:
                        pick = next((o for o in opts if o["v"] and (
                            ans in fold(o["t"])
                            or (ans in YES and fold(o["t"]) in YES)
                            or (ans in NO and fold(o["t"]) in NO))), None)
                    if pick:
                        await loc(f["i"]).select_option(value=pick["v"])
                    else:
                        unresolved.append(lab)
                elif f["tag"] == "textarea" or t in ("text", "number", "tel", "email", "url"):
                    if f["value"].strip():
                        continue
                    ans = self.answer_for(lab)
                    if ans is None and f["tag"] == "textarea" and any(k in fl for k in ("cover", "on yazi", "motivasyon")):
                        ans = self.prof["cover_letter"] or None
                    if ans is not None and (t == "number" or any(k in fl for k in NUM_HINTS)):
                        m = re.search(r"\d+(?:[.,]\d+)?", ans)       # "2 yil" -> "2"; sayi yoksa cevaplanamaz
                        ans = m.group(0).replace(",", ".") if m else None
                    if ans is None:
                        unresolved.append(lab)
                    else:
                        await loc(f["i"]).fill(ans)
            except Exception as e:
                self.log.debug(f"alan hatasi {lab!r}: {e}")
        for lab, opts in radios.items():
            if any(o["checked"] for o in opts):
                continue
            ans = fold(self.answer_for(lab) or "")
            want = YES if ans in YES else NO if ans in NO else None
            pick = next((o for o in opts if (want and fold(o["opt"]) in want) or (ans and ans == fold(o["opt"]))), None)
            if pick:
                await self.tick(loc(pick["i"]))
            else:
                unresolved.append(lab)
        return [u for u in unresolved if u]

    async def form_errors(self) -> list[str]:
        els = self.page.locator(f"{MODAL} .artdeco-inline-feedback--error")
        return [(await e.inner_text()).strip() for e in await els.all() if await e.is_visible()]

    async def apply(self, cv: CVAnalysis) -> tuple[str, str]:
        """-> (status, note). status: applied | needs_answer | failed | skipped"""
        btn = await self.easy_apply_button()
        if not btn:
            vis = await self.page.evaluate("()=>[...document.querySelectorAll('.jobs-search__job-details--container button, .job-details-jobs-unified-top-card__container--two-pane button')].filter(b=>b.offsetParent).map(b=>b.innerText.trim()).filter(Boolean).slice(0,8)")
            self.log.info(f"     buton bulunamadi, gorunenler: {vis}")
            return "retry", "easy apply butonu bulunamadi"
        await btn.click()
        try:
            await self.page.wait_for_selector(MODAL, timeout=8000)
        except Exception:
            return "failed", "modal acilmadi"
        await asyncio.sleep(1.5)
        try:
            for _ in range(10):
                await self.pick_resume(cv)
                unresolved = await self.fill_step()
                primary = self.page.locator(f"{MODAL} footer button.artdeco-button--primary").first
                if not await primary.count():
                    return "failed", "ilerleme butonu yok"
                ptxt = fold(await primary.inner_text())
                attrs = await primary.evaluate("e=>e.getAttributeNames().join(' ')")
                is_submit = "submit-button" in attrs or any(k in ptxt for k in KW_SUBMIT)
                await primary.click()
                await asyncio.sleep(2)
                errs = await self.form_errors()
                if errs:
                    # not: once cevaplanamayan sorular, sonra LinkedIn'in dogrulama hatalari ("HATA:" on ekiyle)
                    parts = list(dict.fromkeys(unresolved)) + ["HATA: " + " ".join(e.split()) for e in dict.fromkeys(errs)]
                    return "needs_answer", "; ".join(parts)[:300]
                if is_submit:
                    body = fold(await self.page.locator("body").inner_text())
                    if "limit" in body and "basvuru" in body and ("gunluk" in body or "daily" in body):
                        self.limit_hit = True
                    ok = any(k in body for k in KW_SENT)
                    return ("applied", "") if ok else ("failed", "gonderim dogrulanamadi")
            return "failed", "adim siniri asildi"
        finally:
            await self.close_modal()

    # -- ana dongu --
    async def run(self, dry: bool = False):
        for cv in self.cvs:
            for kw in cv.search_keywords[:3]:
                for pg in range(self.prof["pages_per_query"]):
                    if self.q.remaining(SITE) <= 0 or self.limit_hit:
                        self.log.info("Gunluk limit doldu, duruyorum.")
                        return
                    self.log.info(f"[{Path(cv.file).stem}] '{kw}' sayfa {pg + 1}")
                    ids = await self.list_job_ids(self.search_url(kw, cv, start=25 * pg))
                    self.log.info(f"   {len(ids)} ilan")
                    for jid in ids:
                        if self.q.remaining(SITE) <= 0 or self.limit_hit:
                            return
                        if self.q.seen(SITE, jid) or jid in self.dry_seen:
                            continue
                        self.dry_seen.add(jid)
                        job = await self.open_job(jid)
                        if not job or not job["title"]:
                            continue
                        sc, best = self.best_cv(job)
                        tag = f"{job['title']} @ {job['company']}"
                        if sc.score < self.prof["min_score"]:
                            if not dry:
                                self.q.record(SITE, jid, job["title"], job["company"], "", sc.score, "skipped", sc.reason)
                            self.log.info(f"   - {tag}  puan={sc.score} atlandi ({sc.reason})")
                            continue
                        cvname = Path(best.file).stem
                        if dry:
                            self.log.info(f"   + {tag}  puan={sc.score} -> {cvname} [DRY]  {sc.reason}")
                            continue
                        self.log.info(f"   > {tag}  puan={sc.score} -> {cvname}")
                        try:
                            status, note = await self.apply(best)
                        except Exception as e:      # tek ilan hatasi tum calismayi durdurmasin
                            status, note = "failed", f"hata: {str(e)[:120]}"
                            await self.close_modal()
                        if status != "retry":   # gecici hata: bir sonraki calistirmada tekrar dene
                            self.q.record(SITE, jid, job["title"], job["company"], cvname, sc.score, status, note)
                        self.log.info(f"     sonuc: {status} {note}")
                        await self.pause()
