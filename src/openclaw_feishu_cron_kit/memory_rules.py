from __future__ import annotations

import os
import re
from pathlib import Path


START_MARKER = "<!-- openclaw-feishu-delivery:start -->"
END_MARKER = "<!-- openclaw-feishu-delivery:end -->"
LEGACY_SECTION_TITLE = "## 飞书消息项目铁律（强制）"

MANAGED_BLOCK_RE = re.compile(
    rf"{re.escape(START_MARKER)}\n.*?\n{re.escape(END_MARKER)}",
    flags=re.S,
)
LEGACY_SECTION_RE = re.compile(
    rf"(?ms)^{re.escape(LEGACY_SECTION_TITLE)}\n.*?(?=^## |\Z)"
)


def build_delivery_memory_rules_section(project_root: Path) -> str:
    root = project_root.expanduser().resolve()
    runtime_dir = root / "runtime"
    docs_dir = root / "docs"
    lines = [
        LEGACY_SECTION_TITLE,
        "",
        f"1. 所有结构化飞书消息统一使用：`{root / 'scripts' / 'send_message.py'}`",
        "2. 路由由模板配置决定，禁止手填 `--target-id / --target-type / --delivery-channel / --thread-*`",
        "3. 禁止硬编码消息 JSON 结构，模板样式与 route 都交给 runtime 配置",
        "4. runtime 配置入口：",
        f"   - `{runtime_dir / 'feishu-templates.local.json'}`",
        f"   - `{runtime_dir / 'accounts.local.json'}`",
        "5. 文档入口：",
        f"   - `{root / 'README.md'}`",
        f"   - `{docs_dir / 'openclaw-runtime-workflow.md'}`",
        f"   - `{docs_dir / 'template-contract.md'}`",
        f"   - `{docs_dir / 'agent-onboarding.md'}`",
        f"6. 新增模板或首个任务时，优先使用：`{root / 'scripts' / 'scaffold_agent_task.py'}`",
        "7. 发送失败必须记录重试过程",
    ]
    return "\n".join(lines).rstrip()


def build_managed_delivery_memory_block(project_root: Path) -> str:
    return "\n".join(
        [
            START_MARKER,
            build_delivery_memory_rules_section(project_root),
            END_MARKER,
        ]
    )


def infer_openclaw_state_dir(project_root: Path, explicit_state_dir: Path | None = None) -> Path:
    if explicit_state_dir is not None:
        return explicit_state_dir.expanduser().resolve()

    root = project_root.expanduser().resolve()
    if root.parent.name == "projects":
        return root.parent.parent.resolve()

    config_path = os.getenv("OPENCLAW_CONFIG_PATH")
    if config_path:
        return Path(config_path).expanduser().resolve().parent

    for env_name in ("OPENCLAW_STATE_DIR", "OPENCLAW_HOME"):
        value = os.getenv(env_name)
        if value:
            return Path(value).expanduser().resolve()

    return Path("~/.openclaw").expanduser().resolve()


def insert_managed_block(text: str, block: str) -> str:
    stripped = text.strip()
    if not stripped:
        return block

    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        insert_at = 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
        prefix = "\n".join(lines[:insert_at]).rstrip()
        suffix = "\n".join(lines[insert_at:]).lstrip("\n")
        if suffix:
            return f"{prefix}\n\n{block}\n\n{suffix}"
        return f"{prefix}\n\n{block}"

    return f"{block}\n\n{text.lstrip()}"


def inject_delivery_memory_rules(memory_text: str, project_root: Path) -> tuple[str, str]:
    normalized = memory_text.rstrip("\n")
    block = build_managed_delivery_memory_block(project_root)

    if MANAGED_BLOCK_RE.search(normalized):
        updated = MANAGED_BLOCK_RE.sub(block, normalized, count=1)
        return updated.rstrip() + "\n", "replaced"

    if LEGACY_SECTION_RE.search(normalized):
        updated = LEGACY_SECTION_RE.sub(block, normalized, count=1)
        return updated.rstrip() + "\n", "normalized"

    updated = insert_managed_block(normalized, block)
    return updated.rstrip() + "\n", "inserted"


def update_memory_file(
    memory_path: Path,
    project_root: Path,
    *,
    apply: bool = False,
    create_missing: bool = False,
) -> dict[str, object]:
    if not memory_path.exists() and not create_missing:
        return {
            "memoryPath": str(memory_path),
            "exists": False,
            "changed": False,
            "action": "missing",
        }

    if memory_path.exists():
        original = memory_path.read_text(encoding="utf-8")
    else:
        workspace_name = memory_path.parent.name
        original = f"# MEMORY.md - {workspace_name}\n"

    updated, action = inject_delivery_memory_rules(original, project_root)
    changed = updated != original

    if changed and apply:
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(updated, encoding="utf-8")

    return {
        "memoryPath": str(memory_path),
        "exists": memory_path.exists(),
        "changed": changed,
        "action": action if changed else "unchanged",
    }


def list_workspace_memory_paths(state_dir: Path, workspace_glob: str = "workspace-*") -> list[Path]:
    root = state_dir.expanduser().resolve()
    workspaces = [path for path in sorted(root.glob(workspace_glob)) if path.is_dir()]
    return [workspace / "MEMORY.md" for workspace in workspaces]
