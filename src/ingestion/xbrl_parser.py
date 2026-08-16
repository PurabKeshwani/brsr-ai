"""
BRSR XBRL Parser

SEBI-mandated BRSR filings are published on NSE in TWO formats: a PDF
(human-readable) and an XBRL XML (machine-readable, officially tagged).
This module parses the XBRL — which makes PDF text extraction unnecessary.

Why this replaces the PDF pipeline entirely:
- Every value is an officially tagged fact, not text we have to segment,
  classify, and map. No regex, no table detection, no LLM, no guessing.
- Dimensional context (gender, employee category, benefit type, financial
  year) is explicit in each fact's contextRef — the exact "merged header"
  problem that no PDF table tool could solve reliably.
- Same SEBI taxonomy across all filers, so per-company wording variation
  (the thing that kept breaking the PDF pipeline) doesn't exist here.

XBRL structure (relevant parts):
  <xbrli:context id="D_Male_PermanentEmployees_TableA">
    <xbrli:period><startDate>..</startDate><endDate>..</endDate></xbrli:period>
    <xbrli:scenario>
      <xbrldi:explicitMember dimension="in-capmkt:GenderAxis">MaleMember</...>
      <xbrldi:explicitMember dimension="...Axis">PermanentEmployeesMember</...>
    </xbrli:scenario>
  </xbrli:context>
  <in-capmkt:NumberOfEmployees contextRef="D_Male_..." unitRef="pure">1282</...>

So: parse all contexts into dimension dicts, then join every fact to its
context. Result is a tidy table: concept | value | unit | dimensions | period.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
}


def _local(tag: str) -> str:
    """Strips the namespace from a tag name."""
    return tag.split("}")[-1] if "}" in tag else tag


@dataclass
class XbrlContext:
    context_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instant: Optional[str] = None
    dimensions: dict = field(default_factory=dict)  # axis_name -> member_name

    @property
    def period_label(self) -> str:
        if self.instant:
            return f"instant:{self.instant}"
        return f"{self.start_date}..{self.end_date}"


@dataclass
class XbrlFact:
    concept: str          # e.g. "NumberOfEmployeesOrWorkersIncludingDifferentlyAbled"
    value: str            # raw string exactly as filed — never reformatted
    unit: Optional[str]   # e.g. "pure", "Gigajoule", "INR", "MtCO2e"
    decimals: Optional[str]
    context: XbrlContext

    @property
    def dimensions(self) -> dict:
        return self.context.dimensions

    @property
    def period(self) -> str:
        return self.context.period_label

    def as_row(self) -> dict:
        row = {
            "concept": self.concept,
            "value": self.value,
            "unit": self.unit,
            "period": self.period,
        }
        row.update(self.dimensions)
        return row


def _parse_contexts(root: ET.Element) -> dict[str, XbrlContext]:
    contexts: dict[str, XbrlContext] = {}
    for ctx_el in root.findall("xbrli:context", NS):
        ctx = XbrlContext(context_id=ctx_el.get("id", ""))

        period = ctx_el.find("xbrli:period", NS)
        if period is not None:
            start = period.find("xbrli:startDate", NS)
            end = period.find("xbrli:endDate", NS)
            instant = period.find("xbrli:instant", NS)
            ctx.start_date = start.text if start is not None else None
            ctx.end_date = end.text if end is not None else None
            ctx.instant = instant.text if instant is not None else None

        # Dimensions live under scenario (or segment in some filings)
        for container_tag in ("xbrli:scenario", "xbrli:segment"):
            container = ctx_el.find(f".//{container_tag}", NS)
            if container is None:
                continue
            for member in container.findall("xbrldi:explicitMember", NS):
                axis = (member.get("dimension") or "").split(":")[-1]
                value = (member.text or "").split(":")[-1]
                ctx.dimensions[axis] = value
            for member in container.findall("xbrldi:typedMember", NS):
                axis = (member.get("dimension") or "").split(":")[-1]
                child = list(member)
                value = (child[0].text or "") if child else ""
                ctx.dimensions[axis] = value

        contexts[ctx.context_id] = ctx
    return contexts


def parse_xbrl(path: str | Path) -> list[XbrlFact]:
    """Parses a BRSR XBRL instance into a flat list of facts, each carrying
    its full dimensional context. Values are returned as the exact strings
    filed — no rounding, no reformatting, no interpretation.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    contexts = _parse_contexts(root)

    facts: list[XbrlFact] = []
    for el in root:
        ctx_ref = el.get("contextRef")
        if not ctx_ref or ctx_ref not in contexts:
            continue  # not a fact (schemaRef, context, unit definitions)
        if el.text is None or not el.text.strip():
            continue
        facts.append(
            XbrlFact(
                concept=_local(el.tag),
                value=el.text.strip(),
                unit=el.get("unitRef"),
                decimals=el.get("decimals"),
                context=contexts[ctx_ref],
            )
        )
    return facts


def facts_to_dataframe(facts: list[XbrlFact]):
    """Returns a pandas DataFrame — one row per fact, dimensions as columns."""
    import pandas as pd
    return pd.DataFrame([f.as_row() for f in facts])


if __name__ == "__main__":
    import io
    import sys
    from collections import Counter

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) != 2:
        print("Usage: python xbrl_parser.py path/to/brsr.xml")
        sys.exit(1)

    facts = parse_xbrl(sys.argv[1])
    numeric = [f for f in facts if f.unit is not None]

    print(f"Total facts parsed: {len(facts)}")
    print(f"Numeric facts (have a unit): {len(numeric)}")
    print(f"Unique concepts: {len(set(f.concept for f in facts))}\n")

    print("=== Sample: employee headcount facts with full context ===")
    for f in facts:
        if "EmployeesOrWorkersIncludingDifferentlyAbled" in f.concept:
            print(f"  {f.concept}")
            print(f"    value={f.value} unit={f.unit} dims={f.dimensions}")

    print("\n=== Units used in this filing ===")
    for unit, count in Counter(f.unit for f in numeric).most_common():
        print(f"  {count:4d}x  {unit}")