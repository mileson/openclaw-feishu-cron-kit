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

from openclaw_feishu_cron_kit.core import build_settings
from openclaw_feishu_cron_kit.cron_wrapper import deliver_configured_jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deliver structured cron payloads via openclaw-feishu-delivery wrapper.")
    parser.add_argument("--config-file", default=str(ROOT / "runtime" / "cron-delivery.local.json"))
    parser.add_argument("--job-id")
    parser.add_argument("--runs-dir")
    parser.add_argument("--templates-file")
    parser.add_argument("--jobs-file")
    parser.add_argument("--accounts-file")
    parser.add_argument("--openclaw-config-file")
    parser.add_argument("--state-dir")
    parser.add_argument("--logs-dir")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = build_settings(
        project_root=ROOT,
        entry_script=Path(__file__).resolve(),
        templates_file=args.templates_file,
        jobs_file=args.jobs_file,
        accounts_file=args.accounts_file,
        openclaw_config_file=args.openclaw_config_file,
        state_dir=args.state_dir,
        logs_dir=args.logs_dir,
    )
    results = deliver_configured_jobs(
        settings,
        config_path=Path(args.config_file),
        only_job_id=args.job_id,
        default_runs_dir=Path(args.runs_dir) if args.runs_dir else None,
    )
    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(json.dumps(item, ensure_ascii=False))
    failed = any(item["status"] in {"missing-run", "missing-payload", "send-failed"} for item in results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
