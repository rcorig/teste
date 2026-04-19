# Alboom Proof gallery extractor

Downloads every photo from an Alboom Proof gallery (e.g. `silascoelho.com.br/proof/...`)
using your own client credentials.

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
export PROOF_EMAIL="you@example.com"
export PROOF_PASSWORD="your-password"

python extract.py "https://silascoelho.com.br/proof/pt-BR/s/natalia-e-ricardo"
```

Photos land in `./gallery/` named `0001_<original>.jpg`, `0002_…`, etc.

## Flags

| Flag | Purpose |
|---|---|
| `--output DIR` | Change output folder (default `./gallery`) |
| `--headed` | Show the Chromium window — useful if the site throws a captcha or the login selectors drift |
| `--timeout SECS` | Per-page navigation timeout (default 60) |
| `--no-zip` | Skip creating `<output>.zip` at the end |

When the run finishes you'll get both `gallery/` and `gallery.zip` — the zip is
what you want to right-click → **Download** from a Codespace on iPad.

## How it works

1. Opens the gallery URL in headless Chromium.
2. Clicks **Entrar como cliente** and fills the email/password form.
3. Scrolls the gallery until no new `<img>` elements appear (handles lazy loading).
4. Pulls the best candidate from each image's `srcset` (falling back to `src`),
   strips CDN resize params, and downloads everything in parallel reusing the
   authenticated cookies.

## If something breaks

Alboom can change their markup at any time. Run with `--headed` to watch the
flow, and if the login step fails, adjust the selectors in `extract.py::login`
(look for inputs / buttons with different labels).
