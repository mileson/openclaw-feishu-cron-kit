from __future__ import annotations

from pathlib import Path

from openclaw_feishu_cron_kit.memory_rules import (
    END_MARKER,
    START_MARKER,
    inject_delivery_memory_rules,
    list_workspace_memory_paths,
    update_memory_file,
)


def test_inject_delivery_memory_rules_inserts_after_title(tmp_path: Path) -> None:
    project_root = tmp_path / "openclaw-feishu-delivery"
    project_root.mkdir()

    text = "# MEMORY.md - blogger\n\n## 工作记录\n\n- 初始化\n"
    updated, action = inject_delivery_memory_rules(text, project_root)

    assert action == "inserted"
    assert updated.startswith("# MEMORY.md - blogger\n\n" + START_MARKER)
    assert "`" + str(project_root / "scripts" / "send_message.py") + "`" in updated
    assert END_MARKER in updated


def test_inject_delivery_memory_rules_normalizes_legacy_section(tmp_path: Path) -> None:
    project_root = tmp_path / "openclaw-feishu-delivery"
    project_root.mkdir()

    text = """# MEMORY.md - product

## 飞书消息项目铁律（强制）

1. 所有结构化飞书消息统一使用：`/root/.openclaw/scripts/send_feishu_message.py`

## 工作记录

- 初始化
"""
    updated, action = inject_delivery_memory_rules(text, project_root)

    assert action == "normalized"
    assert "/root/.openclaw/scripts/send_feishu_message.py" not in updated
    assert START_MARKER in updated


def test_update_memory_file_supports_create_missing(tmp_path: Path) -> None:
    project_root = tmp_path / "openclaw-feishu-delivery"
    workspace_dir = tmp_path / "workspace-product"
    project_root.mkdir()

    result = update_memory_file(
        workspace_dir / "MEMORY.md",
        project_root,
        apply=True,
        create_missing=True,
    )

    assert result["changed"] is True
    memory_text = (workspace_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert START_MARKER in memory_text
    assert "# MEMORY.md - workspace-product" in memory_text


def test_list_workspace_memory_paths_returns_sorted_workspace_memory_files(tmp_path: Path) -> None:
    (tmp_path / "workspace-b").mkdir()
    (tmp_path / "workspace-a").mkdir()
    (tmp_path / "logs").mkdir()

    memory_paths = list_workspace_memory_paths(tmp_path)

    assert memory_paths == [
        tmp_path / "workspace-a" / "MEMORY.md",
        tmp_path / "workspace-b" / "MEMORY.md",
    ]
