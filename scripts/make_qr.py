#!/usr/bin/env python3
"""Generate a QR code and a printable "scan to open" card for a FINN share URL.

Pure-Python (segno); no cloud service, no account, no cost. Run it after you know the
deployed HTTPS URL:

    python scripts/make_qr.py https://your-finn-demo.pages.dev --out docs/share

Writes <out>/finn_qr.png, <out>/finn_qr.svg and <out>/finn_share_card.html (open the
HTML and print to PDF for a one-page phone-sharing handout).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import segno

CARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FINN — scan to open</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #faf8f4; color: #1a1a1a;
         display: flex; min-height: 100vh; align-items: center; justify-content: center; }}
  .card {{ background: #fff; border: 1px solid #e4ded3; border-radius: 16px; padding: 2.4rem; max-width: 420px;
          text-align: center; box-shadow: 0 8px 30px rgba(0,0,0,.06); }}
  h1 {{ font-size: 1.9rem; margin: 0 0 .2rem; letter-spacing: -.02em; }}
  .tag {{ color: #555; margin: 0 0 1.4rem; font-size: .95rem; }}
  img {{ width: 260px; height: 260px; image-rendering: pixelated; }}
  .url {{ margin-top: 1.2rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9rem;
         word-break: break-all; color: #2a4b8d; }}
  .fine {{ margin-top: 1rem; font-size: .78rem; color: #777; line-height: 1.5; }}
</style></head>
<body><div class="card">
  <h1>FINN</h1>
  <p class="tag">Mobile-first primary-source investor research</p>
  <img src="finn_qr.png" alt="QR code linking to the FINN demo">
  <p class="url">{url}</p>
  <p class="fine">Scan with your phone camera. No app install or login needed. Primary sources only:
  NSE records and company documents. Not investment advice.</p>
</div></body></html>
"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Make a QR code + share card for a FINN URL.")
    p.add_argument("url", help="the deployed HTTPS URL, e.g. https://finn-demo.pages.dev")
    p.add_argument("--out", default="docs/share", help="output directory (default: docs/share)")
    args = p.parse_args(argv)
    if not args.url.lower().startswith(("http://", "https://")):
        print("URL must start with http:// or https://", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qr = segno.make(args.url, error="m")
    qr.save(out / "finn_qr.png", scale=10, border=2)
    qr.save(out / "finn_qr.svg", scale=10, border=2)
    (out / "finn_share_card.html").write_text(CARD.format(url=args.url))
    print(f"Wrote {out/'finn_qr.png'}, {out/'finn_qr.svg'} and {out/'finn_share_card.html'} for {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
