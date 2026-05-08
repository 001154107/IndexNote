"""Smoke test — Web Scraper & URL Extraction."""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from indexnote.config import get_settings
from indexnote.scraper.url_extractor import URLExtractor
from indexnote.scraper.web_scraper import WebScraper

print("=== URL Extractor Test ===")
text = '''
Here is a report.
References:
- Google AI: https://ai.google.dev
- Wikipedia: http://en.wikipedia.org/wiki/RAG.
- Some email@test.com
- A broken link htp://bad.com
'''

urls = URLExtractor.extract_urls(text)
print(f"Extracted {len(urls)} URLs:")
for u in urls:
    print(f"  - {u}")


print("\n=== Web Scraper Test ===")
scraper = WebScraper()
test_url = "https://example.com/"
print(f"Downloading {test_url}...")
path = scraper.download_url(test_url)
if path and path.exists():
    print(f"[OK] Downloaded to: {path}")
    print(f"     Size: {path.stat().st_size} bytes")
else:
    print("[FAIL] Failed to download.")

print("\nAll Scraper tests complete!")
