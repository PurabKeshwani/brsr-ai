"""
Dumps raw node structure across ALL the different child-key conventions
OpenDataLoader uses: "kids" (general), "list items" (list nodes), and
"rows" -> "cells" -> "kids" (table nodes). Earlier versions of this script
only checked "kids", which meant list-node content was completely invisible
— this version fixes that so we can see the real structure once, correctly.

Usage:
    python scripts/dump_tree_structure.py data/extracted/glenmark.json 19 20
"""
import json
import sys
from pathlib import Path


def dump(node, depth, page_lo, page_hi, path="root"):
    if isinstance(node, dict):
        page = node.get("page number")
        node_type = node.get("type")
        content = node.get("content", "")
        node_id = node.get("id")
        next_id = node.get("next list id")
        prev_id = node.get("previous list id")

        if page is None or (page_lo <= page <= page_hi):
            preview = (content[:80] + "...") if len(content) > 80 else content
            extra = ""
            if next_id is not None:
                extra += f" [next_list_id={next_id}]"
            if prev_id is not None:
                extra += f" [prev_list_id={prev_id}]"
            indent = "  " * depth
            print(f"{indent}[{path}] type={node_type!r} page={page} id={node_id}{extra}")
            if content:
                print(f"{indent}    content={preview!r}")

        # "kids" — general parent-child (headings, paragraphs, most nodes)
        for i, child in enumerate(node.get("kids", [])):
            dump(child, depth + 1, page_lo, page_hi, path=f"{path}.kids[{i}]")

        # "list items" — list-type nodes' real children (DIFFERENT key)
        for i, item in enumerate(node.get("list items", [])):
            dump(item, depth + 1, page_lo, page_hi, path=f"{path}.list_items[{i}]")

        # "rows" -> "cells" -> "kids" — table-type nodes (THIRD different pattern)
        for ri, row in enumerate(node.get("rows", [])):
            for ci, cell in enumerate(row.get("cells", [])):
                for ki, kid in enumerate(cell.get("kids", [])):
                    dump(kid, depth + 1, page_lo, page_hi,
                         path=f"{path}.rows[{ri}].cells[{ci}].kids[{ki}]")

    elif isinstance(node, list):
        for i, item in enumerate(node):
            dump(item, depth, page_lo, page_hi, path=f"{path}[{i}]")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python dump_tree_structure.py path/to/extracted.json page_lo page_hi")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    page_lo, page_hi = int(sys.argv[2]), int(sys.argv[3])
    dump(data, depth=0, page_lo=page_lo, page_hi=page_hi)