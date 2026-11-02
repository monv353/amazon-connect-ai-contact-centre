#!/usr/bin/env python3
"""Inline the contact flow JSON into the CloudFormation template.

The flow lives in connect/flows/inbound-flow.json so it is easy to read, diff and
re-import into the Connect flow designer. CloudFormation needs it as a string in
AWS::Connect::ContactFlow.Content, so this script swaps the "__INBOUND_FLOW_JSON__"
placeholder in infra/template.yaml for a YAML literal block holding the JSON.
${LexBotAliasArn} and ${SupportQueueArn} inside the JSON are resolved by Fn::Sub.

Usage: python3 scripts/render_template.py [output_path]   (default: build/template.yaml)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "infra" / "template.yaml"
FLOW = ROOT / "connect" / "flows" / "inbound-flow.json"
PLACEHOLDER = '"__INBOUND_FLOW_JSON__"'


def render(source: str, flow_json: str) -> str:
    # Validate and compact the flow so the template stays small (Content max is 256,000 chars).
    compact = json.dumps(json.loads(flow_json), separators=(",", ":"), ensure_ascii=False)
    lines = source.splitlines()
    matches = [i for i, line in enumerate(lines) if PLACEHOLDER in line]
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {PLACEHOLDER} placeholder, found {len(matches)}")
    i = matches[0]
    line = lines[i]
    indent = len(line) - len(line.lstrip())
    # "- "__INBOUND_FLOW_JSON__"" -> "- |" followed by the JSON indented one level deeper.
    lines[i] = line.replace(PLACEHOLDER, "|")
    lines.insert(i + 1, " " * (indent + 4) + compact)
    return "\n".join(lines) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "template.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(SOURCE.read_text(encoding="utf-8"), FLOW.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"rendered {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
