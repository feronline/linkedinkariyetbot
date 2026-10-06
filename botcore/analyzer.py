"""Yapay zekasiz, yerel CV analizi ve ilan puanlama (kural + anahtar kelime)."""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

from .taxonomy import SKILLS, ROLES, SENIORITY, GENERIC_TITLES, NON_SOFTWARE
from .textutil import fold, term_regex, split_sections

_SKILL_RE = {name: [term_regex(a) for a in aliases] for name, aliases in SKILLS.items()}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ── Metin cikarma ───────────────────────────────────────────
def extract_text(path: str | Path) -> str:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    if ext == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    return path.read_text(encoding="utf-8", errors="ignore")


# ── Yetenek bulma ───────────────────────────────────────────
def find_skills(text: str) -> dict[str, int]:
    t = fold(text)
    out = {}
    for name, regs in _SKILL_RE.items():
        n = sum(len(r.findall(t)) for r in regs)
        if n:
            out[name] = n
    return out


# ── Deneyim suresi ──────────────────────────────────────────
_DATE = r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?((?:19|20)\d{2})"
_RANGE = re.compile(rf"{_DATE}\s*[-–—to]+\s*(?:{_DATE}|(present|now|current|halen|devam))", re.I)


def estimate_years(text: str) -> float:
    """Egitim bolumu haric tarih araliklarinin birlesiminden yil hesaplar."""
    secs = split_sections(text)
    body = "\n".join(v for k, v in secs.items() if not k.startswith(("education", "egitim")))
    spans = []
    today = date.today()
    for m in _RANGE.finditer(body):
        m1, y1, m2, y2, cur = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        start = int(y1) + (MONTHS.get(fold(m1)[:3], 1) - 1) / 12 if m1 else int(y1)
        if cur:
            end = today.year + today.month / 12
        else:
            end = int(y2) + (MONTHS.get(fold(m2)[:3], 12) if m2 else 12) / 12
        if 0 < end - start < 15:
            spans.append((start, end))
    spans.sort()
    total, cur_end = 0.0, None
    for s, e in spans:
        if cur_end is None or s > cur_end:
            total += e - s
            cur_end = e
        elif e > cur_end:
            total += e - cur_end
            cur_end = e
    explicit = re.findall(r"(\d{1,2})\+?\s*(?:years|yil|yrs)", fold(text))
    if explicit:
        total = max(total, float(max(int(x) for x in explicit)))
    return round(total, 1)


def seniority_for(years: float):
    for max_y, label, exclude, levels in SENIORITY:
        if years <= max_y:
            return label, exclude, levels
    return SENIORITY[-1][1:]


# ── CV analizi ──────────────────────────────────────────────
@dataclass
class CVAnalysis:
    file: str
    skills: dict[str, float]
    years: float
    seniority: str
    exclude_words: list[str]
    experience_levels: list[str]
    roles: list[tuple[str, float]]          # (rol_id, skor)
    search_keywords: list[str] = field(default_factory=list)
    title_must: list[str] = field(default_factory=list)
    title_exclude: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def analyze_cv(path: str | Path) -> CVAnalysis:
    text = extract_text(path)
    secs = split_sections(text)
    skills_text = "\n".join(v for k, v in secs.items() if "skill" in k or "yetenek" in k or "beceri" in k)

    skills: dict[str, float] = {}
    for name, n in find_skills(text).items():
        skills[name] = float(min(n, 4))
    for name in find_skills(skills_text):          # yetenek bolumunde gecen = daha guvenilir
        skills[name] = skills.get(name, 0) + 3.0

    role_scores = {}
    for rid, role in ROLES.items():
        score = sum(w * min(skills.get(s, 0), 6) for s, w in role["skills"].items())
        headline = fold(" ".join(text.strip().splitlines()[:4]))
        if any(term_regex(t).search(headline) for t in role["title_must"] + [role["label"]]):
            score *= 2                                  # CV basligi (headline) en guclu sinyal
        if score > 0:
            role_scores[rid] = score
    ranked = sorted(role_scores.items(), key=lambda x: -x[1])
    top = ranked[0][1] if ranked else 0
    # en iyi rolun %60'indan fazlasini alanlar bu CV'nin rolleri; en fazla 2
    roles = [(r, round(s / top, 2)) for r, s in ranked if s >= 0.6 * top][:2]

    years = estimate_years(text)
    label, sen_excl, levels = seniority_for(years)

    kw, must, excl = [], [], []
    for rid, _ in roles[:1] if roles else []:
        kw += ROLES[rid]["search"]
        must += ROLES[rid]["title_must"]
        excl += ROLES[rid]["title_exclude"]
    for rid, _ in roles[1:]:
        kw += ROLES[rid]["search"][:1]
        must += ROLES[rid]["title_must"]
    excl = [e for e in excl if e not in must]

    return CVAnalysis(
        file=str(path), skills=skills, years=years, seniority=label,
        exclude_words=sen_excl, experience_levels=levels, roles=roles,
        search_keywords=list(dict.fromkeys(kw)), title_must=list(dict.fromkeys(must)),
        title_exclude=list(dict.fromkeys(excl + sen_excl)),
    )


# ── Ilan puanlama ───────────────────────────────────────────
@dataclass
class JobScore:
    score: int
    reason: str

    @property
    def ok(self):
        return self.score >= 50


def score_job(title: str, description: str, cv: CVAnalysis, broad: bool = False) -> JobScore:
    """0-100. Baslik uyumu (50) + aciklamadaki yetenek ortusmesi (50). Haric kelime = 0.

    broad=True: 'yazilimla alakali her sey' - rol bazli haric kelimeler (game, mobile...)
    yerine sadece kidem ve yazilim-disi kelimeler elenir; genel yazilim basliklari kabul edilir.
    """
    t = fold(title)
    excl = (cv.exclude_words + NON_SOFTWARE) if broad else cv.title_exclude
    for w in excl:
        if term_regex(w).search(t):
            return JobScore(0, f"baslikta haric kelime: {w!r}")
    musts = cv.title_must + (GENERIC_TITLES if broad else [])
    hit = [m for m in musts if term_regex(m).search(t)]
    title_pts = 50 if hit else 0

    job_sk = find_skills(title + chr(10) + description) if description else {}
    if job_sk:
        wsum = sum(1 + 0.2 * min(n, 5) for n in job_sk.values())
        wmatch = sum(1 + 0.2 * min(n, 5) for s, n in job_sk.items() if s in cv.skills)
        desc_pts = 50 * wmatch / wsum
        common = [s for s in job_sk if s in cv.skills]
    else:
        desc_pts, common = (0, [])
    if not hit and desc_pts < 35:
        return JobScore(int(desc_pts), "baslik uymuyor, yetenek ortusmesi dusuk")
    return JobScore(int(title_pts + desc_pts),
                    f"baslik={hit[:2]} ortak={common[:6]}")
