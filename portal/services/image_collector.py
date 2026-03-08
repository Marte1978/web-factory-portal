"""Downloads logo, OG images, and site photos for a company."""
import re
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from io import BytesIO
from PIL import Image as PILImage
from bs4 import BeautifulSoup
from portal.config import HTTP_HEADERS, HTTP_TIMEOUT



def download_and_save(url: str, dest: Path, max_size=(800, 800)) -> bool:
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS)
        if r.status_code != 200 or len(r.content) < 500:
            return False
        img = PILImage.open(BytesIO(r.content)).convert("RGBA")
        img.thumbnail(max_size, PILImage.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(dest), "PNG")
        return True
    except Exception:
        return False


def get_logo(base_url: str, soup: BeautifulSoup, dest: Path) -> bool:
    if not soup or not base_url:
        return False

    candidates = []

    # 1. og:image
    og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
    if og and og.get("content"):
        candidates.append(urljoin(base_url, og["content"]))

    # 2. apple-touch-icon
    apple = soup.find("link", rel=lambda r: r and "apple-touch-icon" in " ".join(r))
    if apple and apple.get("href"):
        candidates.append(urljoin(base_url, apple["href"]))

    # 3. link[rel~=icon]
    icon = soup.find("link", rel=lambda r: r and "icon" in " ".join(r or []).lower())
    if icon and icon.get("href"):
        candidates.append(urljoin(base_url, icon["href"]))

    # 4. /favicon.ico fallback
    parsed = urlparse(base_url)
    candidates.append(f"{parsed.scheme}://{parsed.netloc}/favicon.ico")

    for url in candidates:
        if download_and_save(url, dest, max_size=(512, 512)):
            return True
    return False


def get_og_image(base_url: str, soup: BeautifulSoup, dest: Path) -> bool:
    if not soup:
        return False
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        url = urljoin(base_url, og["content"])
        return download_and_save(url, dest)
    return False


def get_site_photos(base_url: str, soup: BeautifulSoup, dest_dir: Path, max_photos=12) -> list[str]:
    """Scrapes meaningful images from the homepage and inner pages."""
    if not soup or not base_url:
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    seen_urls = set()

    SKIP_KW = [
        "icon", "pixel", "track", "1x1", "spinner", "loading",
        "arrow", "btn", "social", "facebook", "twitter", "whatsapp",
        "instagram", "linkedin", "youtube", "tiktok", "badge", "seal",
        "payment", "visa", "mastercard", "flag", "map-pin", "bullet",
    ]

    def _try_save(src: str) -> bool:
        if not src or src in seen_urls:
            return False
        if any(kw in src.lower() for kw in SKIP_KW):
            return False
        seen_urls.add(src)
        url = urljoin(base_url, src)
        ext = Path(urlparse(url).path).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ""):
            return False
        fname = f"photo_{len(saved)+1}.png"
        if download_and_save(url, dest_dir / fname, max_size=(1200, 900)):
            saved.append(fname)
            return True
        return False

    # Priority 1: background images in style attributes
    for tag in soup.find_all(style=re.compile(r"url\(", re.I)):
        style = tag.get("style", "")
        for m in re.finditer(r'url\(["\']?([^"\')\s]+)["\']?\)', style, re.I):
            _try_save(m.group(1))
            if len(saved) >= max_photos:
                return saved

    # Priority 2: img tags with meaningful src
    for img in soup.find_all("img", src=True):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src", "")
        _try_save(src)
        if len(saved) >= max_photos:
            return saved

    # Priority 3: data-src lazy loading
    for img in soup.find_all("img"):
        for attr in ["data-src", "data-lazy", "data-original", "data-lazy-src"]:
            src = img.get(attr, "")
            if src:
                _try_save(src)
                break
        if len(saved) >= max_photos:
            return saved

    return saved
