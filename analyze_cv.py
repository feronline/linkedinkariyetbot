"""Kullanim: python analyze_cv.py cv1.pdf [cv2.pdf ...]"""
import io, sys
from botcore.analyzer import analyze_cv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for f in sys.argv[1:]:
    a = analyze_cv(f)
    print("=" * 60)
    print(f)
    print(f"  Deneyim: ~{a.years} yil -> {a.seniority}  | LinkedIn seviyeleri: {a.experience_levels}")
    print(f"  Roller : {a.roles}")
    print(f"  Arama  : {a.search_keywords}")
    print(f"  Haric  : {a.title_exclude}")
    top = sorted(a.skills.items(), key=lambda x: -x[1])[:15]
    print("  Yetenek:", ", ".join(f"{k}({v:g})" for k, v in top))
