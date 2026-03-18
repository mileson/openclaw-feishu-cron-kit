from __future__ import annotations

import json
import re
from typing import Any


_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
_MISSING = object()


def _markdown_element(content: str) -> dict[str, Any]:
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": content,
        },
    }


def _note_element(content: str) -> dict[str, Any]:
    return {
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": content,
            }
        ],
    }


def _derive_context(value: Any) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if isinstance(value, dict):
        context.update(value)
        for key, item in value.items():
            if isinstance(item, list):
                context[f"{key}_count"] = len(item)
    elif isinstance(value, list):
        context["item_count"] = len(value)
    else:
        context["item"] = value
    return context


def _resolve_path(payload: Any, path: str) -> Any:
    current = payload
    for chunk in path.split("."):
        key = chunk.strip()
        if not key:
            return _MISSING
        if isinstance(current, dict):
            if key not in current:
                return _MISSING
            current = current[key]
            continue
        return _MISSING
    return current


def _stringify(value: Any) -> str:
    if value is _MISSING or value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        if not value:
            return ""
        if all(not isinstance(item, (dict, list)) for item in value):
            return "、".join(str(item).strip() for item in value if str(item).strip())
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _render_template(template: str, root: dict[str, Any], item: Any | None = None) -> str:
    if not template:
        return ""

    context: dict[str, Any] = {}
    context.update(_derive_context(root))
    if isinstance(root, dict):
        context.update(root)
    if item is not None:
        context.update(_derive_context(item))
        if isinstance(item, dict):
            context.update(item)
        else:
            context["item"] = item

    def replace(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        if not token:
            return ""
        value = _resolve_path(context, token)
        if value is _MISSING and isinstance(root, dict):
            value = _resolve_path(root, token)
        return _stringify(value)

    return _PLACEHOLDER_RE.sub(replace, template).strip()


def _render_fact_lines(items: list[dict[str, Any]], root: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in items:
        label = str(item.get("label") or "").strip()
        value_template = str(item.get("template") or "").strip()
        path = str(item.get("path") or "").strip()
        if value_template:
            value_text = _render_template(value_template, root)
        elif path:
            value_text = _stringify(_resolve_path(root, path))
        else:
            value_text = ""
        if not value_text:
            continue
        if label:
            lines.append(f"- **{label}**：{value_text}")
        else:
            lines.append(f"- {value_text}")
    return lines


def _render_record_lines(block: dict[str, Any], root: dict[str, Any], item: Any, index: int) -> list[str]:
    lines: list[str] = []
    title_template = str(block.get("title_template") or block.get("item_template") or "{item}").strip()
    title = _render_template(title_template, root, item)
    if not title:
        fallback = _stringify(item)
        title = f"{index}. {fallback}" if block.get("ordered") else fallback
    elif block.get("ordered"):
        title = f"{index}. {title}"
    lines.append(title)

    for template in block.get("lines") or []:
        rendered = _render_template(str(template), root, item)
        if rendered:
            lines.append(rendered)

    child_field = str(block.get("children_field") or "").strip()
    if child_field:
        children = []
        if isinstance(item, dict):
            raw_children = _resolve_path(item, child_field)
            if isinstance(raw_children, list):
                children = raw_children
        max_children = int(block.get("max_children") or 0) or len(children)
        for child in children[:max_children]:
            child_title_template = str(block.get("child_title_template") or block.get("child_item_template") or "{item}").strip()
            child_title = _render_template(child_title_template, root, child)
            child_lines = [f"  - {child_title or _stringify(child)}"]
            for template in block.get("child_lines") or []:
                rendered = _render_template(str(template), root, child)
                if rendered:
                    child_lines.append(f"    {rendered}")
            lines.extend(child_lines)
    return lines


def _render_collection_block(block: dict[str, Any], root: dict[str, Any]) -> list[dict[str, Any]]:
    path = str(block.get("path") or block.get("field") or "").strip()
    values = _resolve_path(root, path) if path else _MISSING
    if not isinstance(values, list):
        values = []

    empty_text = str(block.get("empty_text") or "").strip()
    if not values and not empty_text:
        return []

    elements: list[dict[str, Any]] = []
    section_title = _render_template(str(block.get("title") or block.get("title_template") or "").strip(), root)
    if section_title:
        elements.append(_markdown_element(f"**{section_title}**"))

    if not values and empty_text:
        elements.append(_markdown_element(empty_text))
        return elements

    max_items = int(block.get("max_items") or 0) or len(values)
    for index, item in enumerate(values[:max_items], start=1):
        lines = _render_record_lines(block, root, item, index)
        rendered = "\n".join(line for line in lines if line).strip()
        if rendered:
            elements.append(_markdown_element(rendered))
    return elements


def _render_block(block: dict[str, Any], root: dict[str, Any]) -> list[dict[str, Any]]:
    block_type = str(block.get("type") or "").strip()
    if block_type == "divider":
        return [{"tag": "hr"}]
    if block_type == "markdown":
        content = _render_template(str(block.get("template") or ""), root)
        return [_markdown_element(content)] if content else []
    if block_type == "facts":
        lines = _render_fact_lines(block.get("items") or [], root)
        if not lines:
            return []
        title = _render_template(str(block.get("title") or ""), root)
        if title:
            lines.insert(0, f"**{title}**")
        return [_markdown_element("\n".join(lines))]
    if block_type in {"list", "record_list"}:
        return _render_collection_block(block, root)
    if block_type == "note":
        content = _render_template(str(block.get("template") or ""), root)
        return [_note_element(content)] if content else []
    return []


def _build_blocks_card(template_name: str, template_config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any] | None:
    presentation = template_config.get("presentation") or {}
    blocks = presentation.get("blocks") or []
    if not isinstance(blocks, list) or not blocks:
        return None

    title_template = str(presentation.get("header_title_template") or "").strip()
    title = (
        _render_template(title_template, data)
        if title_template
        else str(data.get("title") or template_config.get("description") or template_name)
    )

    elements: list[dict[str, Any]] = []
    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue
        block_elements = _render_block(raw_block, data)
        if not block_elements:
            continue
        if elements and elements[-1] == {"tag": "hr"} and block_elements[0] == {"tag": "hr"}:
            continue
        elements.extend(block_elements)

    while elements and elements[-1] == {"tag": "hr"}:
        elements.pop()

    if not elements:
        return None

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template_config.get("header_template", "blue"),
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": elements,
    }


def _as_markdown_item(item: dict[str, Any]) -> str:
    parts: list[str] = []
    emoji = item.get("emoji") or "•"
    title = item.get("title") or "未命名项目"
    score = item.get("score")
    platform = item.get("platform")
    description = item.get("description") or ""
    first_line = f"{emoji} **{title}**"
    if score:
        first_line += f"（{score}）"
    parts.append(first_line)
    if description:
        parts.append(f"> {description}")
    if platform:
        parts.append(f"`平台`：{platform}")
    return "\n".join(parts)


def build_generic_card(template_name: str, template_config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    configured_card = _build_blocks_card(template_name, template_config, data)
    if configured_card:
        return configured_card

    presentation = template_config.get("presentation") or {}
    title = data.get("title") or presentation.get("header_title_template") or template_config.get("description") or template_name
    summary = data.get("summary") or f"已生成 1 条 `{template_name}` 报告。"
    timestamp = data.get("timestamp")
    archive_target_path = data.get("archive_target_path")
    items = data.get("items") or []
    sections = data.get("sections") or []

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"✅ **{title}**\n{summary}"},
        }
    ]

    if timestamp:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"📅 {timestamp}"},
            }
        )

    if items:
        elements.append({"tag": "hr"})
        for item in items:
            elements.append(
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": _as_markdown_item(item)},
                }
            )

    for section in sections:
        section_title = section.get("title") or "补充信息"
        lines = section.get("lines") or []
        if not lines:
            continue
        elements.append({"tag": "hr"})
        block = [f"**{section_title}**"]
        block.extend([f"- {line}" for line in lines])
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(block)}})

    if archive_target_path:
        elements.append({"tag": "hr"})
        elements.append(_note_element(f"归档文件：{archive_target_path}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template_config.get("header_template", "blue"),
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": elements,
    }


def build_summary_post(thread_title: str, summary_data: dict[str, Any]) -> dict[str, Any]:
    notice = summary_data["notice"]
    bullets = summary_data["bullets"]
    footer = summary_data.get("footer")
    mention_open_ids = summary_data.get("mention_open_ids") or []

    first_line: list[dict[str, Any]] = []
    for open_id in mention_open_ids:
        first_line.append({"tag": "at", "user_id": open_id})
        first_line.append({"tag": "text", "text": " "})
    first_line.append({"tag": "text", "text": notice})

    content = [
        first_line,
        [{"tag": "text", "text": "【摘要】"}],
    ]
    for bullet in bullets:
        content.append([{"tag": "text", "text": f"- {bullet}"}])
    if footer:
        content.append([{"tag": "text", "text": footer}])

    return {
        "post": {
            "zh_cn": {
                "title": f"{thread_title} · 最新摘要",
                "content": content,
            }
        }
    }


def build_summary_text(summary_data: dict[str, Any]) -> dict[str, Any]:
    notice = summary_data["notice"]
    bullets = summary_data["bullets"]
    footer = summary_data.get("footer")
    mention_open_ids = summary_data.get("mention_open_ids") or []

    lines: list[str] = []
    if mention_open_ids:
        lines.append(" ".join(f'<at user_id="{open_id}"></at>' for open_id in mention_open_ids))
    lines.append(notice)
    lines.append("【摘要】")
    lines.extend([f"- {bullet}" for bullet in bullets])
    if footer:
        lines.append(footer)
    return {"text": "\n".join(lines)}
