from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from openclaw_feishu_cron_kit.core import build_settings_from_args, load_account_credentials
from openclaw_feishu_cron_kit.jobs_sync import (
    TEMP_JOB_ID_PLACEHOLDER,
    build_add_command,
    build_edit_command,
    build_schedule_flags,
    format_openclaw_duration,
    merge_job_defaults,
    normalize_job_spec,
    parse_openclaw_json_output,
    render_job_text,
)


def test_build_settings_prefers_runtime_local_files(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    scripts_dir = project_root / "scripts"
    runtime_dir = project_root / "runtime"
    examples_dir = project_root / "examples"
    scripts_dir.mkdir(parents=True)
    runtime_dir.mkdir()
    examples_dir.mkdir()

    entry_script = scripts_dir / "send_message.py"
    entry_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (runtime_dir / "feishu-templates.local.json").write_text("{}", encoding="utf-8")
    (runtime_dir / "accounts.local.json").write_text("{}", encoding="utf-8")
    (examples_dir / "feishu-templates.example.json").write_text("{}", encoding="utf-8")
    (examples_dir / "accounts.example.json").write_text("{}", encoding="utf-8")
    (examples_dir / "jobs.example.json").write_text('{"jobs":[]}', encoding="utf-8")

    args = Namespace(
        templates_file=None,
        jobs_file=None,
        accounts_file=None,
        openclaw_config_file=None,
        state_dir=None,
        logs_dir=None,
    )
    settings = build_settings_from_args(args, entry_script=entry_script)

    assert settings.runtime_dir == runtime_dir
    assert settings.templates_file == runtime_dir / "feishu-templates.local.json"
    assert settings.accounts_file == runtime_dir / "accounts.local.json"
    assert settings.jobs_file == examples_dir / "jobs.example.json"


def test_load_account_credentials_accepts_openclaw_json_shape(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    examples_dir = project_root / "examples"
    examples_dir.mkdir()
    (examples_dir / "feishu-templates.example.json").write_text("{}", encoding="utf-8")
    (examples_dir / "jobs.example.json").write_text('{"jobs":[]}', encoding="utf-8")
    openclaw_config = tmp_path / "openclaw.json"
    openclaw_config.write_text(
        """
        {
          "channels": {
            "feishu": {
              "accounts": {
                "main": {"appId": "cli_main", "appSecret": "sec_main"},
                "blogger": {"appId": "cli_blogger", "appSecret": "sec_blogger"}
              }
            }
          }
        }
        """.strip(),
        encoding="utf-8",
    )

    settings = Namespace(
        project_root=project_root,
        runtime_dir=project_root / "runtime",
        templates_file=examples_dir / "feishu-templates.example.json",
        jobs_file=examples_dir / "jobs.example.json",
        accounts_file=project_root / "runtime" / "accounts.local.json",
        openclaw_config_file=openclaw_config,
        state_dir=project_root / "state",
        logs_dir=project_root / "logs",
        entry_script=project_root / "scripts" / "send_message.py",
    )

    assert load_account_credentials(settings, "blogger") == ("cli_blogger", "sec_blogger")
    assert load_account_credentials(settings, "unknown") == ("cli_main", "sec_main")


def test_jobs_sync_builds_commands_with_real_job_id_placeholders() -> None:
    defaults = {
        "session": "isolated",
        "wake": "next-heartbeat",
        "timeout_seconds": 300,
    }
    raw_job = {
        "name": "深度选题研究",
        "agent": "blogger",
        "schedule": {"kind": "cron", "expr": "0 6 * * *", "tz": "Asia/Shanghai"},
        "payload": {
            "kind": "agentTurn",
            "message": "python3 scripts/send_message.py --job-id \"{{job_id}}\"",
        },
    }
    job = normalize_job_spec(merge_job_defaults(defaults, raw_job))

    assert render_job_text(raw_job["payload"]["message"], "job-123") == 'python3 scripts/send_message.py --job-id "job-123"'

    add_command = build_add_command("openclaw", job)
    assert TEMP_JOB_ID_PLACEHOLDER in add_command[-1]
    assert "--cron" in add_command
    assert "--agent" in add_command

    edit_command = build_edit_command("openclaw", job, "job-123", "job-123")
    assert 'python3 scripts/send_message.py --job-id "job-123"' in edit_command
    assert "--enable" in edit_command


def test_parse_openclaw_json_output_skips_plugin_banner() -> None:
    raw = """
    [plugins] feishu_chat: Registered feishu_chat
    [plugins] feishu_doc: Registered feishu_fetch_doc
    {
      "jobs": [
        {"id": "job-1", "name": "demo"}
      ]
    }
    """.strip()

    payload = parse_openclaw_json_output(raw)

    assert payload["jobs"][0]["id"] == "job-1"


def test_format_openclaw_duration_supports_ms_fields() -> None:
    assert format_openclaw_duration(10800000) == "3h"
    assert format_openclaw_duration("300000") == "5m"


def test_build_schedule_flags_supports_every_ms_and_stagger_ms() -> None:
    job = normalize_job_spec(
        {
            "name": "每3小时任务",
            "agent": "blogger",
            "schedule": {"kind": "every", "everyMs": 10800000, "staggerMs": 300000},
            "payload": {"kind": "agentTurn", "message": "echo ok"},
        }
    )

    flags = build_schedule_flags(job)

    assert flags == ["--every", "3h", "--stagger", "5m"]
