#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openclaw_feishu_cron_kit.presentation_presets import materialize_template_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize config-driven presentation blocks into template registry")
    parser.add_argument("--templates-file", default=str(ROOT / "runtime" / "feishu-templates.local.json"))
    parser.add_argument("--write", action="store_true", help="Write updated registry back to disk")
    parser.add_argument("--overwrite-blocks", action="store_true", help="Replace existing presentation.blocks")
    parser.add_argument("--drop-renderer", action="store_true", help="Remove legacy renderer field after materialization")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    templates_file = Path(args.templates_file)
    registry = json.loads(templates_file.read_text(encoding="utf-8"))
    updated, changes = materialize_template_registry(
        registry,
        overwrite_blocks=args.overwrite_blocks,
        drop_renderer=args.drop_renderer,
    )

    if args.write and changes:
        templates_file.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "templates_file": str(templates_file),
                "write": args.write,
                "overwrite_blocks": args.overwrite_blocks,
                "drop_renderer": args.drop_renderer,
                "changed_templates": changes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
