"""Yetenek ve rol sozlugu. Herkes buraya yeni yetenek/rol ekleyebilir.

SKILLS : kanonik_ad -> [takma adlar]
ROLES  : rol_id -> etiket, arama kelimeleri, baslik ifadeleri, haric ifadeler, yetenek agirliklari
"""

SKILLS: dict[str, list[str]] = {
    # diller
    "python": ["python"], "c#": ["c#", "csharp", "c sharp"], "c++": ["c++", "cpp"],
    "java": ["java"], "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript"], "go": ["golang"], "rust": ["rust"],
    "kotlin": ["kotlin"], "swift": ["swift", "swiftui"], "php": ["php"], "sql": ["sql"],
    # web
    "react": ["react", "react.js", "reactjs"], "next.js": ["next.js", "nextjs"],
    "node.js": ["node.js", "nodejs"], "vue": ["vue", "vue.js"],
    "angular": ["angular"], "tailwind": ["tailwind"], "html/css": ["html", "css"],
    "django": ["django"], "flask": ["flask"], "fastapi": ["fastapi"],
    "spring": ["spring", "spring boot"], ".net": [".net", "asp.net", "dotnet"],
    "rest api": ["rest api", "restful"], "graphql": ["graphql"],
    # mobil
    "react native": ["react native", "react-native"], "expo": ["expo"],
    "flutter": ["flutter", "dart"], "android": ["android"], "ios": ["ios"],
    # oyun
    "unity": ["unity", "unity3d"], "unreal": ["unreal", "unreal engine", "ue4", "ue5"],
    "godot": ["godot"], "hdrp": ["hdrp"], "cinemachine": ["cinemachine"],
    "gameplay": ["gameplay", "game development", "game dev"], "game design": ["game design"],
    # ml / ai
    "pytorch": ["pytorch"], "tensorflow": ["tensorflow"], "keras": ["keras"],
    "opencv": ["opencv"], "computer vision": ["computer vision", "goruntu isleme", "image processing"],
    "machine learning": ["machine learning", "ml", "makine ogrenmesi"],
    "deep learning": ["deep learning", "derin ogrenme", "cnn", "fcnn"],
    "nlp": ["nlp", "natural language processing"], "llm": ["llm", "large language model", "genai", "generative ai"],
    "yolo": ["yolo", "yolov8", "yolov11"], "ocr": ["ocr", "tesseract", "easyocr"],
    "whisper": ["whisper"], "onnx": ["onnx"], "scikit-learn": ["scikit-learn", "sklearn"],
    "pandas": ["pandas"], "numpy": ["numpy"], "data science": ["data science", "veri bilimi"],
    "n8n": ["n8n"], "automation": ["automation", "otomasyon"], "rag": ["rag"],
    # altyapi
    "docker": ["docker"], "kubernetes": ["kubernetes", "k8s"], "aws": ["aws"],
    "gcp": ["gcp", "google cloud"], "azure": ["azure"], "ci/cd": ["ci/cd", "github actions", "gitlab ci"],
    "postgresql": ["postgresql", "postgres"], "mysql": ["mysql"], "mongodb": ["mongodb"],
    "redis": ["redis"], "celery": ["celery"], "supabase": ["supabase"], "sqlite": ["sqlite"],
    "git": ["git", "github"], "linux": ["linux"],
}

# agirliklar: rol icin yetenegin ne kadar belirleyici oldugu (1-5)
ROLES: dict[str, dict] = {
    "ai_ml": {
        "label": "AI / ML / Computer Vision",
        "search": ["Machine Learning Engineer", "AI Engineer", "Computer Vision Engineer", "Python AI Developer"],
        "title_must": ["machine learning", "ml engineer", "ai engineer", "artificial intelligence",
                       "deep learning", "computer vision", "nlp", "llm", "data scientist",
                       "ai developer", "ai automation", "genai", "mlops", "applied scientist"],
        "title_exclude": ["game", "unity", "ios", "android", "mobile", "sales", "marketing", "recruiter"],
        "skills": {"pytorch": 5, "tensorflow": 5, "keras": 4, "opencv": 5, "computer vision": 5,
                   "machine learning": 5, "deep learning": 5, "nlp": 4, "llm": 4, "yolo": 4, "ocr": 3,
                   "onnx": 3, "scikit-learn": 4, "pandas": 3, "numpy": 3, "data science": 4,
                   "whisper": 2, "n8n": 2, "rag": 3, "python": 2},
    },
    "backend": {
        "label": "Backend / Python",
        "search": ["Python Developer", "Backend Developer", "FastAPI Developer"],
        "title_must": ["python developer", "python engineer", "backend developer", "backend engineer",
                       "back-end", "fastapi", "django", "flask", "software engineer python"],
        "title_exclude": ["game", "unity", "ios", "android", "frontend", "front-end", "devops"],
        "skills": {"python": 4, "fastapi": 5, "django": 5, "flask": 4, "celery": 3, "postgresql": 3,
                   "redis": 3, "rest api": 3, "docker": 2, "sql": 2, "node.js": 3, "mongodb": 2},
    },
    "game": {
        "label": "Oyun Gelistirme",
        "search": ["Unity Developer", "Game Developer", "Gameplay Programmer"],
        "title_must": ["unity", "game developer", "game programmer", "gameplay programmer",
                       "gameplay engineer", "unreal", "game engineer", "godot", "game dev"],
        "title_exclude": ["game designer", "level designer", "artist", "animator", "producer",
                          "community", "qa ", "tester", "creative lead", "narrative"],
        "skills": {"unity": 5, "c#": 4, "unreal": 5, "godot": 4, "hdrp": 3, "cinemachine": 3,
                   "gameplay": 4, "c++": 2},
    },
    "mobile": {
        "label": "Mobil Gelistirme",
        "search": ["React Native Developer", "Mobile Developer", "Flutter Developer"],
        "title_must": ["react native", "mobile developer", "mobile engineer", "ios developer",
                       "android developer", "flutter", "expo", "cross-platform", "mobile app"],
        "title_exclude": ["unity", "game", "web only"],
        "skills": {"react native": 5, "expo": 5, "flutter": 5, "android": 4, "ios": 4, "kotlin": 4,
                   "swift": 4, "typescript": 2, "sqlite": 2, "supabase": 2},
    },
    "frontend": {
        "label": "Frontend / Web",
        "search": ["Frontend Developer", "React Developer"],
        "title_must": ["frontend", "front-end", "react developer", "web developer", "next.js", "vue developer"],
        "title_exclude": ["game", "unity", "backend", "native"],
        "skills": {"react": 5, "next.js": 4, "vue": 5, "angular": 5, "typescript": 3, "javascript": 3,
                   "tailwind": 3, "html/css": 3},
    },
}

# (maks yil, etiket, basliklarda dislanacak kelimeler, aranacak LinkedIn deneyim kodlari)
SENIORITY = [
    (1.0, "entry", ["senior", "lead", "principal", "staff", "head", "manager", "director", "architect", "sr.", "kidemli", "yonetici", "mudur", "takim lideri", "uzman yardimcisi"], ["Internship", "Entry level"]),
    (3.0, "junior", ["senior", "lead", "principal", "staff", "head", "manager", "director", "architect", "sr.", "kidemli", "yonetici", "mudur", "takim lideri", "uzman yardimcisi"], ["Entry level", "Associate"]),
    (6.0, "mid", ["principal", "staff", "head", "manager", "director", "architect", "yonetici", "mudur"], ["Associate", "Mid-Senior level"]),
    (99.0, "senior", ["intern", "junior", "trainee", "entry"], ["Mid-Senior level", "Director"]),
]

# "Yazilimla alakali her sey" modu: bu basliklar herhangi bir CV icin uygundur
GENERIC_TITLES = [
    "software", "developer", "programmer", "yazilim", "gelistirici", "full-stack", "sdk",
    "full stack", "fullstack", "backend", "back-end", "frontend", "front-end", "web",
    "mobile", "ios", "android", "game", "unity", "data engineer", "data scientist",
    "data analyst", "machine learning", "ai ", " ai", "devops", "qa automation", "sdet",
    "cloud", "python", "react", "node", "java", ".net", "flutter",
]
NON_SOFTWARE = ["data center", "operations engineer", "field engineer", "maintenance", "technician", "hr ", "payroll", "warehouse", "logistics", "sales", "marketing", "recruiter", "accountant", "nurse", "driver", "teacher",
                "mechanical", "civil", "electrical", "chemical", "hardware", "network engineer",
                "security guard", "support specialist", "destek uzmani", "help desk", "technical support", "satis", "muhasebe", "pazarlama", "musteri", "insan kaynaklari", "operasyon", "temsilcisi", "customer", "designer", "artist",
                "animator", "producer", "trainer", "tutor", "auditor", "analyst - finance"]
