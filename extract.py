"""
Alboom Proof gallery extractor.

Logs into a gallery URL with your credentials, scrolls until every thumbnail is
loaded, then downloads each photo at full resolution into ./gallery/.

Usage:
    export PROOF_EMAIL="you@example.com"
    export PROOF_PASSWORD="your-password"
    python extract.py "https://silascoelho.com.br/proof/pt-BR/s/natalia-e-ricardo"

Optional:
    --output DIR     Output folder (default: ./gallery)
    --headed         Show the browser window (useful for debugging / captchas)
    --timeout SECS   Per-page navigation timeout (default: 60)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import Page, async_playwright


IMG_EXT_RE = re.compile(r"\.(jpe?g|png|webp|tiff?|heic)(\?|$)", re.IGNORECASE)


def sanitize_filename(url: str, index: int) -> str:
    path = urlparse(url).path
    name = Path(path).name or f"photo-{index:04d}.jpg"
    name = re.sub(r"[^\w.\-]", "_", name)
    if not IMG_EXT_RE.search(name):
        name += ".jpg"
    return f"{index:04d}_{name}"


async def login(page: Page, email: str, password: str) -> None:
    # Click the "client login" button if present
    for label in ("Entrar como cliente", "Login as client", "Entrar"):
        btn = page.get_by_role("button", name=re.compile(label, re.I))
        if await btn.count():
            await btn.first.click()
            break

    # Fill credentials. Selectors are intentionally loose so they survive small
    # UI tweaks from Alboom.
    email_field = page.locator(
        "input[type=email], input[name*=email i], input[placeholder*=email i]"
    ).first
    await email_field.wait_for(state="visible", timeout=15_000)
    await email_field.fill(email)

    password_field = page.locator("input[type=password]").first
    await password_field.fill(password)

    submit = page.locator(
        "button[type=submit], button:has-text('Entrar'), button:has-text('Login')"
    ).first
    await submit.click()

    # Wait for the gallery grid to appear.
    await page.wait_for_load_state("networkidle", timeout=30_000)


async def autoscroll(page: Page) -> None:
    """Scroll to the bottom repeatedly until image count stabilises."""
    previous = -1
    stable_rounds = 0
    while stable_rounds < 3:
        count = await page.evaluate("document.querySelectorAll('img').length")
        if count == previous:
            stable_rounds += 1
        else:
            stable_rounds = 0
            previous = count
        await page.mouse.wheel(0, 20_000)
        await page.wait_for_timeout(800)


async def collect_image_urls(page: Page) -> list[str]:
    """Pull the highest-resolution URL we can find for each <img>."""
    urls: list[str] = await page.evaluate(
        """
        () => {
          const out = new Set();
          const pickBest = (srcset) => {
            if (!srcset) return null;
            const parts = srcset.split(',').map(s => s.trim());
            // Each entry is "url 1200w" or "url 2x". Take the last (highest).
            const last = parts[parts.length - 1];
            return last ? last.split(/\\s+/)[0] : null;
          };
          document.querySelectorAll('img').forEach(img => {
            const best = pickBest(img.srcset) || img.currentSrc || img.src;
            if (best && /\\.(jpe?g|png|webp|tiff?|heic)(\\?|$)/i.test(best)) {
              out.add(best);
            }
          });
          // Also harvest CSS background-images
          document.querySelectorAll('*').forEach(el => {
            const bg = getComputedStyle(el).backgroundImage;
            const m = bg && bg.match(/url\\(["']?(.*?)["']?\\)/);
            if (m && /\\.(jpe?g|png|webp)(\\?|$)/i.test(m[1])) {
              out.add(m[1]);
            }
          });
          return [...out];
        }
        """
    )
    # Strip Alboom's size-restricting query params so we get originals when possible.
    cleaned = []
    for u in urls:
        # Common CDN resize params on Alboom: w=, h=, fit=, q=
        u = re.sub(r"([?&])(w|h|fit|q|dpr|auto)=[^&]*", r"\1", u)
        u = re.sub(r"[?&]+$", "", u).replace("?&", "?")
        cleaned.append(u)
    # Skip tiny UI assets (logos, flags, svg)
    return [
        u for u in dict.fromkeys(cleaned)
        if not u.endswith(".svg")
        and "logo" not in u.lower()
        and "flag-icons" not in u
    ]


async def download_all(urls: list[str], out_dir: Path, cookies: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jar = httpx.Cookies()
    for c in cookies:
        jar.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))

    async with httpx.AsyncClient(
        cookies=jar,
        follow_redirects=True,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0 (gallery-extractor)"},
    ) as client:
        sem = asyncio.Semaphore(6)

        async def fetch_one(i: int, url: str) -> None:
            dest = out_dir / sanitize_filename(url, i)
            if dest.exists() and dest.stat().st_size > 0:
                print(f"[skip] {dest.name}")
                return
            async with sem:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                    print(f"[ok]   {dest.name} ({len(r.content)//1024} KB)")
                except Exception as exc:
                    print(f"[fail] {url} -> {exc}")

        await asyncio.gather(*[fetch_one(i, u) for i, u in enumerate(urls, 1)])


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output", default="gallery")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Skip creating <output>.zip at the end",
    )
    args = parser.parse_args()

    email = os.environ.get("PROOF_EMAIL")
    password = os.environ.get("PROOF_PASSWORD")
    if not email or not password:
        print("Set PROOF_EMAIL and PROOF_PASSWORD in your environment.", file=sys.stderr)
        return 2

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(args.timeout * 1000)

        print(f"-> opening {args.url}")
        await page.goto(args.url, wait_until="domcontentloaded")

        print("-> logging in")
        await login(page, email, password)

        print("-> scrolling to load all photos")
        await autoscroll(page)

        print("-> collecting image URLs")
        urls = await collect_image_urls(page)
        print(f"-> found {len(urls)} images")

        cookies = await context.cookies()
        await browser.close()

    out_dir = Path(args.output)
    await download_all(urls, out_dir, cookies)
    print(f"done. files saved to {out_dir}/")

    if not args.no_zip:
        archive = shutil.make_archive(str(out_dir), "zip", root_dir=out_dir)
        size_mb = Path(archive).stat().st_size / (1024 * 1024)
        print(f"-> zipped -> {archive} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
