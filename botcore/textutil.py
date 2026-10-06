"""Metin yardimcilari: Turkce karakter katlama, bolum bulma."""
import re

_FOLD = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigGuUsSoOcC")


def fold(text: str) -> str:
    """Kucuk harf + Turkce karakterleri ASCII'ye indirger (eslestirme icin)."""
    return " ".join(text.translate(_FOLD).lower().split())   #   vb. bosluklari da tek bosluk yapar


def term_regex(term: str) -> re.Pattern:
    """'c#', 'node.js', 'react native' gibi terimler icin sinir kontrollu regex."""
    t = re.escape(fold(term)).replace(r"\ ", r"[\s\-_/]+")
    return re.compile(rf"(?<![a-z0-9]){t}(?![a-z0-9])")


_UNUSED = (
    "technical skills", "skills", "yetenekler", "teknik beceriler",
    "experience", "work experience", "deneyim", "is deneyimi",
    "projects", "projeler", "education", "egitim", "profile", "summary",
    "shipped", "certificat", "languages", "additional",
)


def split_sections(text: str) -> dict[str, str]:
    """Buyuk harfli kisa satirlari baslik sayip {baslik: icerik} dondurur."""
    sections: dict[str, list[str]] = {"": []}
    cur = ""
    for line in text.splitlines():
        raw = line.strip()
        if raw and len(raw) <= 40 and raw == raw.upper() and any(c.isalpha() for c in raw):
            cur = fold(raw).strip(" :")
            sections.setdefault(cur, [])
            continue
        sections.setdefault(cur, []).append(line)
    return {k: chr(10).join(v) for k, v in sections.items()}
