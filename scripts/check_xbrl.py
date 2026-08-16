"""
Checks whether NSE's BRSR XBRL filings contain the same numeric disclosures
we've been extracting from PDFs — but already structured and officially
tagged, which would remove the need for PDF extraction entirely.

Downloads one XBRL file and reports: total tagged facts, how many are
numeric, and whether known BRSR values (employee counts, energy, GHG,
water) appear as tagged elements.

Usage:
    python scripts/check_xbrl.py <xbrl_url>
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter

import requests


def main(url: str):
    headers = {
        # NSE blocks requests without a browser-like User-Agent.
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/xml,text/xml,*/*",
    }
    print(f"Downloading {url} ...")
    resp = requests.get(url, headers=headers, timeout=60)
    print(f"HTTP {resp.status_code}, {len(resp.content):,} bytes")

    if resp.status_code != 200:
        print("Download failed. Try opening the URL in a browser first (NSE sometimes requires a session cookie).")
        return

    out_path = "sample_brsr.xml"
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"Saved to {out_path}\n")

    root = ET.fromstring(resp.content)

    all_elements = list(root.iter())
    print(f"Total XML elements: {len(all_elements):,}")

    # Facts with actual text content (i.e. tagged data values)
    facts = [el for el in all_elements if el.text and el.text.strip()]
    print(f"Elements with values: {len(facts):,}")

    numeric_facts = []
    for el in facts:
        txt = el.text.strip().replace(",", "")
        try:
            float(txt)
            numeric_facts.append(el)
        except ValueError:
            pass
    print(f"Numeric-valued elements: {len(numeric_facts):,}\n")

    # Namespace-stripped tag names, most common first
    def local_name(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    tag_counts = Counter(local_name(el.tag) for el in facts)
    print("=== 40 most common tagged elements ===")
    for name, count in tag_counts.most_common(40):
        print(f"  {count:4d}x  {name}")

    # Look for tags matching the BRSR disclosures we care about
    print("\n=== Searching for known BRSR concepts ===")
    keywords = ["employee", "worker", "energy", "water", "waste", "emission",
                 "ghg", "scope", "wage", "training", "female", "male", "turnover"]
    for kw in keywords:
        matches = [n for n in tag_counts if kw in n.lower()]
        if matches:
            print(f"\n  '{kw}' -> {len(matches)} matching tag(s), e.g.:")
            for m in matches[:5]:
                sample = next((el.text.strip()[:60] for el in facts if local_name(el.tag) == m), "")
                print(f"      {m} = {sample!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_xbrl.py <xbrl_url>")
        sys.exit(1)
    main(sys.argv[1])