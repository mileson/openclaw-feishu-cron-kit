from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


TEMP_JOB_ID_PLACEHOLDER = "__OPENCLAW_PENDING_JOB_ID__"


def load_jobs_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("jobs spec 顶层必须是对象")
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("jobs spec 必须包含 jobs 数组")
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_job_defaults(defaults: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    return deep_merge(defaults, job)


def render_job_text(value: str, job_id: str) -> str:
    return value.replace("{{job_id}}", job_id)


def normalize_job_spec(job: dict[str, Any]) -> dict[str, Any]:
    name = str(job.get("name") or "").strip()
    if not name:
        raise ValueError("job.name 不能为空")

    payload = job.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError(f"job {name} 的 payload 必须是对象")
    payload_kind = str(payload.get("kind") or "").strip()
    if payload_kind not in {"agentTurn", "systemEvent"}:
        raise ValueError(f"job {name} 的 payload.kind 仅支持 agentTurn / systemEvent")

    schedule = job.get("schedule") or {}
    if not isinstance(schedule, dict):
        raise ValueError(f"job {name} 的 schedule 必须是对象")
    schedule_kind = str(schedule.get("kind") or "").strip()
    if schedule_kind not in {"cron", "every", "at"}:
        raise ValueError(f"job {name} 的 schedule.kind 仅支持 cron / every / at")

    return {
        "match": job.get("match") or {},
        "name": name,
        "description": str(job.get("description") or "").strip(),
        "enabled": bool(job.get("enabled", True)),
        "agent": str(job.get("agent") or job.get("agentId") or "").strip(),
        "session": str(job.get("session") or job.get("sessionTarget") or "").strip(),
        "wake": str(job.get("wake") or job.get("wakeMode") or "").strip(),
        "timeout_seconds": job.get("timeout_seconds") or job.get("timeoutSeconds"),
        "timeout_ms": job.get("timeout_ms") or job.get("timeout"),
        "light_context": job.get("light_context"),
        "expect_final": job.get("expect_final"),
        "announce": job.get("announce"),
        "best_effort_deliver": job.get("best_effort_deliver"),
        "account": str(job.get("account") or "").strip(),
        "channel": str(job.get("channel") or "").strip(),
        "to": str(job.get("to") or "").strip(),
        "model": str(job.get("model") or "").strip(),
        "thinking": str(job.get("thinking") or "").strip(),
        "session_key": str(job.get("session_key") or job.get("sessionKey") or "").strip(),
        "schedule": schedule,
        "payload": payload,
    }


def format_openclaw_duration(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text.isdigit():
            value = int(text)
        else:
            return text
    if not isinstance(value, (int, float)):
        raise ValueError(f"无法识别的 duration 值: {value}")

    milliseconds = int(value)
    if milliseconds <= 0:
        raise ValueError(f"duration 必须大于 0: {value}")

    units = (
        ("d", 24 * 60 * 60 * 1000),
        ("h", 60 * 60 * 1000),
        ("m", 60 * 1000),
        ("s", 1000),
    )
    for suffix, base in units:
        if milliseconds % base == 0:
            return f"{milliseconds // base}{suffix}"
    return f"{milliseconds}ms"


def build_schedule_flags(job: dict[str, Any]) -> list[str]:
    schedule = job["schedule"]
    flags: list[str] = []
    kind = schedule["kind"]
    if kind == "cron":
        expr = str(schedule.get("expr") or "").strip()
        if not expr:
            raise ValueError(f"job {job['name']} 缺少 schedule.expr")
        flags.extend(["--cron", expr])
        if schedule.get("tz"):
            flags.extend(["--tz", str(schedule["tz"])])
    elif kind == "every":
        every = format_openclaw_duration(schedule.get("every") or schedule.get("everyMs"))
        if not every:
            raise ValueError(f"job {job['name']} 缺少 schedule.every")
        flags.extend(["--every", every])
    else:
        at = str(schedule.get("at") or "").strip()
        if not at:
            raise ValueError(f"job {job['name']} 缺少 schedule.at")
        flags.extend(["--at", at])

    if schedule.get("exact"):
        flags.append("--exact")
    stagger = schedule.get("stagger")
    if stagger is None:
        stagger = schedule.get("staggerMs")
    if stagger:
        flags.extend(["--stagger", format_openclaw_duration(stagger)])
    return flags


def build_payload_flags(job: dict[str, Any], job_id: str) -> list[str]:
    payload = job["payload"]
    kind = payload["kind"]
    if kind == "agentTurn":
        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError(f"job {job['name']} 缺少 payload.message")
        return ["--message", render_job_text(message, job_id)]

    text = str(payload.get("text") or payload.get("system_event") or "").strip()
    if not text:
        raise ValueError(f"job {job['name']} 缺少 payload.text")
    return ["--system-event", render_job_text(text, job_id)]


def build_common_flags(job: dict[str, Any], job_id: str) -> list[str]:
    flags = ["--name", job["name"]]
    if job["description"]:
        flags.extend(["--description", job["description"]])
    if job["agent"]:
        flags.extend(["--agent", job["agent"]])
    if job["session"]:
        flags.extend(["--session", job["session"]])
    if job["wake"]:
        flags.extend(["--wake", job["wake"]])
    if job["timeout_seconds"] is not None:
        flags.extend(["--timeout-seconds", str(job["timeout_seconds"])])
    if job["timeout_ms"] is not None:
        flags.extend(["--timeout", str(job["timeout_ms"])])
    if job["light_context"] is True:
        flags.append("--light-context")
    if job["expect_final"] is True:
        flags.append("--expect-final")
    if job["announce"] is True:
        flags.append("--announce")
    if job["best_effort_deliver"] is True:
        flags.append("--best-effort-deliver")
    if job["account"]:
        flags.extend(["--account", job["account"]])
    if job["channel"]:
        flags.extend(["--channel", job["channel"]])
    if job["to"]:
        flags.extend(["--to", job["to"]])
    if job["model"]:
        flags.extend(["--model", job["model"]])
    if job["thinking"]:
        flags.extend(["--thinking", job["thinking"]])
    if job["session_key"]:
        flags.extend(["--session-key", job["session_key"]])
    flags.extend(build_schedule_flags(job))
    flags.extend(build_payload_flags(job, job_id))
    return flags


def build_add_command(openclaw_bin: str, job: dict[str, Any]) -> list[str]:
    command = [openclaw_bin, "cron", "add"]
    if not job["enabled"]:
        command.append("--disabled")
    command.extend(build_common_flags(job, TEMP_JOB_ID_PLACEHOLDER))
    return command


def build_edit_command(openclaw_bin: str, job: dict[str, Any], job_id: str, openclaw_job_id: str) -> list[str]:
    command = [openclaw_bin, "cron", "edit", openclaw_job_id]
    command.extend(build_common_flags(job, job_id))
    command.append("--enable" if job["enabled"] else "--disable")
    return command


def run_openclaw(openclaw_bin: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [openclaw_bin, *args],
        check=False,
        capture_output=True,
        text=True,
    )


def parse_openclaw_json_output(raw: str) -> dict[str, Any]:
    lines = raw.splitlines()
    candidates: list[str] = []

    stripped = raw.lstrip()
    if stripped:
        candidates.append(stripped)

    for index, line in enumerate(lines):
        if line.lstrip().startswith(("{", "[")) and not line.lstrip().startswith("[plugins]"):
            candidates.append("\n".join(lines[index:]).strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    preview = raw.strip().splitlines()[:8]
    raise ValueError(f"无法从 openclaw 输出中解析 JSON: {' | '.join(preview)}")


def list_jobs(openclaw_bin: str) -> list[dict[str, Any]]:
    proc = run_openclaw(openclaw_bin, ["cron", "list", "--all", "--json"])
    if proc.returncode != 0:
        raise RuntimeError(f"openclaw cron list 失败: {(proc.stderr or proc.stdout).strip()}")
    payload = parse_openclaw_json_output(proc.stdout)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("openclaw cron list --json 返回中缺少 jobs 数组")
    return jobs


def find_existing_job(existing_jobs: list[dict[str, Any]], job: dict[str, Any]) -> dict[str, Any] | None:
    match = job.get("match") or {}
    explicit_id = str(match.get("id") or "").strip()
    if explicit_id:
        for item in existing_jobs:
            if str(item.get("id")) == explicit_id:
                return item
        return None

    target_name = str(match.get("name") or job["name"]).strip()
    target_agent = job["agent"]
    candidates = [
        item
        for item in existing_jobs
        if str(item.get("name") or "").strip() == target_name
        and (not target_agent or str(item.get("agentId") or "").strip() == target_agent)
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        raise ValueError(f"job {job['name']} 命中多个现有任务，请在 spec.match.id 显式指定目标 job id")
    return candidates[0]


def sync_jobs(spec_path: Path, openclaw_bin: str, apply: bool) -> list[dict[str, Any]]:
    spec = load_jobs_spec(spec_path)
    defaults = spec.get("defaults") or {}
    if defaults and not isinstance(defaults, dict):
        raise ValueError("jobs spec.defaults 必须是对象")

    existing_jobs = list_jobs(openclaw_bin)
    results: list[dict[str, Any]] = []
    for raw_job in spec["jobs"]:
        if not isinstance(raw_job, dict):
            raise ValueError("jobs spec.jobs[] 每项都必须是对象")
        job = normalize_job_spec(merge_job_defaults(defaults, raw_job))
        existing = find_existing_job(existing_jobs, job)
        action = "update" if existing else "create"
        openclaw_job_id = str((existing or {}).get("id") or "")
        command_preview = (
            build_edit_command(openclaw_bin, job, openclaw_job_id or "{{job_id}}", openclaw_job_id)
            if existing
            else build_add_command(openclaw_bin, job)
        )
        result = {
            "action": action,
            "name": job["name"],
            "job_id": openclaw_job_id or None,
            "command": command_preview,
        }
        results.append(result)
        if not apply:
            continue

        if existing:
            proc = run_openclaw(openclaw_bin, build_edit_command(openclaw_bin, job, openclaw_job_id, openclaw_job_id)[1:])
            if proc.returncode != 0:
                raise RuntimeError(f"更新任务失败: {job['name']} => {(proc.stderr or proc.stdout).strip()}")
            continue

        proc = run_openclaw(openclaw_bin, build_add_command(openclaw_bin, job)[1:])
        if proc.returncode != 0:
            raise RuntimeError(f"创建任务失败: {job['name']} => {(proc.stderr or proc.stdout).strip()}")

        refreshed_jobs = list_jobs(openclaw_bin)
        created = find_existing_job(refreshed_jobs, job)
        if not created:
            raise RuntimeError(f"任务已创建但无法回读 job id: {job['name']}")
        openclaw_job_id = str(created["id"])
        proc = run_openclaw(openclaw_bin, build_edit_command(openclaw_bin, job, openclaw_job_id, openclaw_job_id)[1:])
        if proc.returncode != 0:
            raise RuntimeError(f"创建后回填 job_id 失败: {job['name']} => {(proc.stderr or proc.stdout).strip()}")
        result["job_id"] = openclaw_job_id
        result["command"] = build_edit_command(openclaw_bin, job, openclaw_job_id, openclaw_job_id)
        existing_jobs = refreshed_jobs

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync local jobs spec into OpenClaw cron jobs")
    parser.add_argument("--spec-file", default="runtime/jobs-spec.local.json")
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--apply", action="store_true", help="实际执行 openclaw cron add/edit")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    results = sync_jobs(Path(args.spec_file), openclaw_bin=args.openclaw_bin, apply=args.apply)
    if args.json:
        print(json.dumps({"apply": args.apply, "results": results}, ensure_ascii=False, indent=2))
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] OpenClaw jobs sync")
    for item in results:
        print(f"- {item['action']}: {item['name']} job_id={item['job_id'] or 'new'}")
    return 0
