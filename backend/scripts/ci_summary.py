"""Publish only test names/outcomes, never raw pytest captures or failure locals."""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def summarize(source: Path) -> dict:
    root = ET.parse(source).getroot()
    cases = []
    for case in root.iter("testcase"):
        name = case.attrib.get("name", "unknown")
        # Parametrized values may contain private input. Keep only the test name.
        name = name.split("[", 1)[0]
        name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)[:150]
        outcome = next(
            (key for key in ("failure", "error", "skipped") if case.find(key) is not None), "passed"
        )
        cases.append({"name": name, "outcome": outcome})
    return {
        "tests": len(cases),
        "passed": bool(cases) and all(case["outcome"] == "passed" for case in cases),
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = summarize(args.source)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    raise SystemExit(0 if result["passed"] else 1)
