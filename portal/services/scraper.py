"""
Scraper robusto con dos niveles:
  Nivel 1 — requests + BeautifulSoup (rápido, funciona en ~60% de sitios)
  Nivel 2 — Playwright headless (para sitios JS/React/Vue/Angular)
Detecta automáticamente cuándo escalar al nivel 2.
"""
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import Tuple, Optional
from portal.services.search_engine import get_headers, random_delay


# ─── Nivel 1: requests ────────────────────────────────────────────────────────

def scrape_requests(url: str, timeout: int = 12) -> Tuple[Optional[BeautifulSoup], str, str]:
    if not url:
        return None, "", url
    if not url.startswith("http"):
        url = "https://" + url

    for scheme in ["https://", "http://"]:
        try:
            u = scheme + url.split("://", 1)[-1]
            r = requests.get(u, timeout=timeout, headers=get_headers(), allow_redirects=True)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "lxml")
            return soup, r.text, r.url
        except Exception:
            continue
    return None, "", url


def _is_js_rendered(soup: Optional[BeautifulSoup], html: str) -> bool:
    """Detecta si la página necesita JS para mostrar contenido."""
    if not soup:
        return True
    text = soup.get_text(strip=True)
    # Si hay muy poco texto o señales de SPA
    if len(text) < 200:
        return True
    title = soup.find("title")
    if not title or len(title.get_text(strip=True)) < 3:
        return True
    # Frameworks SPA
    spa_signals = [
        'id="root"', 'id="app"', 'id="__next"',
        "window.__INITIAL_STATE__", "window.__NUXT__",
        "<noscript>You need to enable JavaScript",
        "ng-version", "data-reactroot",
    ]
    return any(s in html for s in spa_signals)


# ─── Nivel 2: Playwright headless ────────────────────────────────────────────

def scrape_playwright(url: str, timeout: int = 20000) -> Tuple[Optional[BeautifulSoup], str, str]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-blink-features=AutomationControlled"]
            )
            ctx = browser.new_context(
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                ]),
                viewport={"width": 1366, "height": 768},
                locale="es-419",
            )
            page = ctx.new_page()

            # Bloquear recursos pesados que no aportan datos
            page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3}", lambda r: r.abort())
            page.route("**/{gtm,analytics,ads,doubleclick}**", lambda r: r.abort())

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except Exception:
                # Si timeout, intentar con networkidle más corto
                try:
                    page.goto(url, wait_until="load", timeout=timeout // 2)
                except Exception:
                    pass

            # Esperar a que aparezca contenido real
            try:
                page.wait_for_selector("body", timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

            html = page.content()
            final_url = page.url
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        return soup, html, final_url
    except Exception as e:
        return None, "", url


# ─── Scraper unificado ────────────────────────────────────────────────────────

def scrape_smart(url: str) -> Tuple[Optional[BeautifulSoup], str, str]:
    """
    Intenta requests primero. Si detecta SPA/JS o falla,
    escala automáticamente a Playwright.
    """
    if not url:
        return None, "", ""

    # Nivel 1
    soup, html, final_url = scrape_requests(url)

    # ¿Necesita JS?
    if _is_js_rendered(soup, html):
        soup2, html2, final_url2 = scrape_playwright(url)
        # Usar Playwright solo si devuelve más contenido
        if soup2 and len(html2) > len(html):
            return soup2, html2, final_url2

    return soup, html, final_url
