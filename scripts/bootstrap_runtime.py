#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openclaw_feishu_cron_kit.core import load_openclaw_account_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap private runtime config for openclaw-feishu-delivery")
    parser.add_argument("--runtime-dir", default=str(ROOT / "runtime"))
    parser.add_argument("--examples-dir", default=str(ROOT / "examples"))
    parser.add_argument("--templates-source")
    parser.add_argument("--accounts-source")
    parser.add_argument("--jobs-spec-source")
    parser.add_argument("--openclaw-config")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_file(target: Path, source: Path, force: bool) -> str:
    if target.exists() and not force:
        return f"skip {target}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return f"copy {source} -> {target}"


def bootstrap_accounts_from_openclaw(target: Path, openclaw_config: Path, force: bool) -> str:
    if target.exists() and not force:
        return f"skip {target}"
    accounts = load_openclaw_account_registry(openclaw_config)
    if not accounts:
        raise ValueError(f"未在 {openclaw_config} 中找到 channels.feishu.accounts")
    payload = {"accounts": {}}
    for key, account in accounts.items():
        app_id = str(account.get("appId") or account.get("app_id") or "").strip()
        app_secret = str(account.get("appSecret") or account.get("app_secret") or "").strip()
        if app_id and app_secret:
            payload["accounts"][key] = {"app_id": app_id, "app_secret": app_secret}
    if not payload["accounts"]:
        raise ValueError(f"{openclaw_config} 中没有可用的飞书凭证")
    write_json(target, payload)
    return f"generate {target} from {openclaw_config}"


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir)
    examples_dir = Path(args.examples_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    actions: list[str] = []
    templates_target = runtime_dir / "feishu-templates.local.json"
    accounts_target = runtime_dir / "accounts.local.json"
    jobs_spec_target = runtime_dir / "jobs-spec.local.json"

    templates_source = Path(args.templates_source) if args.templates_source else examples_dir / "feishu-templates.example.json"
    accounts_source = Path(args.accounts_source) if args.accounts_source else examples_dir / "accounts.example.json"
    jobs_spec_source = Path(args.jobs_spec_source) if args.jobs_spec_source else examples_dir / "jobs-spec.example.json"

    actions.append(ensure_file(templates_target, templates_source, args.force))

    openclaw_config = Path(args.openclaw_config) if args.openclaw_config else Path.home() / ".openclaw" / "openclaw.json"
    if args.accounts_source:
        actions.append(ensure_file(accounts_target, accounts_source, args.force))
    elif openclaw_config.exists():
        try:
            actions.append(bootstrap_accounts_from_openclaw(accounts_target, openclaw_config, args.force))
        except ValueError:
            actions.append(ensure_file(accounts_target, accounts_source, args.force))
    else:
        actions.append(ensure_file(accounts_target, accounts_source, args.force))

    actions.append(ensure_file(jobs_spec_target, jobs_spec_source, args.force))

    print("Runtime bootstrap complete")
    for item in actions:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
