"""Kullanici profili: data/profile.json (git'e girmez)."""
import json
from pathlib import Path

DATA = Path("data")
PROFILE = DATA / "profile.json"
CV_DIR = DATA / "cvs"
SESSIONS = DATA / "sessions"

DEFAULT = {
    "daily_limits": {"linkedin": 20, "kariyernet": 20},
    "phone": "",                    # ulke kodsuz, ornek 5XXXXXXXXX (doluysa LinkedIn'deki kayitli numaranin YERINE yazilir)
    "min_score": 50,
    "any_software": True,           # yazilimla alakali her ilana basvur (CV rolu zorunlu degil)
    "work_type": ["Remote", "On-site", "Hybrid"],   # liste: istedigini birakabilirsin
    "locations": [],                # ornek: ["Istanbul, Turkiye", "Germany"]; bos = dunya geneli
    "pages_per_query": 2,
    "delay_seconds": [6, 14],
    "cover_letter": "",
    # Form sorulari: anahtar -> cevap. Etiket anahtari ICERIYORSA cevap yazilir.
    # Cevabi olmayan zorunlu soru = ilan atlanir (tahmin yok).
    "answers": {
        "years of experience": "2", "yillik deneyim": "2", "deneyim yili": "2", "yil deneyim": "2",
        "phone": "", "telefon": "",
        "website": "", "github": "", "linkedin": "", "portfolio": "",
        "expected salary": "", "maas": "", "notice period": "",
        "sponsorship": "no", "vize": "no", "authorized to work": "yes", "calisma izni": "yes",
        "english": "", "ingilizce": ""
    },
}


def load() -> dict:
    prof = dict(DEFAULT)
    if PROFILE.exists():
        user = json.loads(PROFILE.read_text(encoding="utf-8"))
        prof.update({k: v for k, v in user.items() if k != "answers"})
        prof["answers"] = {**DEFAULT["answers"], **user.get("answers", {})}
        if "locations" not in user and user.get("location"):      # eski tek konumlu profil
            prof["locations"] = [user["location"]]
        prof.pop("location", None)
    return prof


def save(prof: dict) -> None:
    DATA.mkdir(exist_ok=True)
    PROFILE.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")


def cv_files() -> list[Path]:
    CV_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in CV_DIR.iterdir() if p.suffix.lower() in (".pdf", ".docx"))
