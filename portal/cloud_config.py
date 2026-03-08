"""Cloud-aware config — overrides local paths when running on Render/Railway."""
import os
from pathlib import Path

IS_CLOUD = os.getenv("RENDER") == "true" or os.getenv("RAILWAY_ENVIRONMENT") is not None

# Base dir: use /tmp on cloud, local path in dev
if IS_CLOUD:
    BASE_DIR     = Path("/tmp/webfactory")
    PACKAGES_DIR = BASE_DIR / "packages"
    LOGOS_DIR    = BASE_DIR / "logos"
else:
    BASE_DIR     = Path(os.getenv("BUSINESS_DIR", r"C:\Users\Willy\sistema de egocios"))
    PACKAGES_DIR = BASE_DIR / "packages"
    LOGOS_DIR    = BASE_DIR / "research" / "logos"

DATA_JSON    = Path(__file__).parent / "data" / "companies.json"
PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

HTTP_TIMEOUT = 12
MAX_CONCURRENT_JOBS = 2

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
