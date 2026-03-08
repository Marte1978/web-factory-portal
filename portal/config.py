import os
from pathlib import Path

BASE_DIR      = Path(r"C:\Users\Willy\sistema de egocios")
PACKAGES_DIR  = BASE_DIR / "packages"
RESEARCH_DIR  = BASE_DIR / "research"
LOGOS_DIR     = RESEARCH_DIR / "logos"
PROGRESS_FILE = RESEARCH_DIR / "progress_100.json"
EXCEL_DEFAULT = Path(r"C:\Users\Willy\OneDrive\Escritorio\INVESTIGACION_100_EMPRESAS.xlsx")

PACKAGES_DIR.mkdir(exist_ok=True)
LOGOS_DIR.mkdir(exist_ok=True)

MAX_CONCURRENT_JOBS = 3
REQUEST_DELAY       = 1.2  # seconds between DDG queries
HTTP_TIMEOUT        = 12

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
