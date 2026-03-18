from openclaw_feishu_cron_kit.presentation_presets import TEMPLATE_PRESENTATIONS, materialize_template_registry
from openclaw_feishu_cron_kit.renderer import build_generic_card, build_summary_post, build_summary_text


def test_build_summary_post_wraps_post_payload_for_feishu_reply_api() -> None:
    payload = build_summary_post(
        "固定话题",
        {
            "notice": "本轮已完成",
            "bullets": ["第一条", "第二条"],
            "footer": "详情见上一条完整卡片。",
            "mention_open_ids": ["ou_demo"],
        },
    )

    assert "post" in payload
    assert "zh_cn" in payload["post"]
    assert payload["post"]["zh_cn"]["title"] == "固定话题 · 最新摘要"

    content = payload["post"]["zh_cn"]["content"]
    assert content[0][0] == {"tag": "at", "user_id": "ou_demo"}
    assert content[0][-1] == {"tag": "text", "text": "本轮已完成"}
    assert content[1] == [{"tag": "text", "text": "【摘要】"}]
    assert content[2] == [{"tag": "text", "text": "- 第一条"}]
    assert content[3] == [{"tag": "text", "text": "- 第二条"}]
    assert content[4] == [{"tag": "text", "text": "详情见上一条完整卡片。"}]


def test_build_summary_text_formats_fallback_reply() -> None:
    payload = build_summary_text(
        {
            "notice": "本轮已完成",
            "bullets": ["第一条", "第二条"],
            "footer": "详情见上一条完整卡片。",
            "mention_open_ids": ["ou_demo"],
        }
    )

    assert payload == {
        "text": '<at user_id="ou_demo"></at>\n本轮已完成\n【摘要】\n- 第一条\n- 第二条\n详情见上一条完整卡片。'
    }


def test_build_generic_card_renders_presentation_blocks_for_daily_knowledge() -> None:
    template_config = {
        "description": "每日知识整理",
        "header_template": "blue",
        "presentation": TEMPLATE_PRESENTATIONS["daily-knowledge"],
    }
    data = {
        "title": "每日知识整理任务完成",
        "summary": "✅ 完成！已整理昨天工作记录。",
        "report_date": "2026-03-17",
        "organized_at": "2026-03-18 02:00",
        "timestamp": "2026-03-18 02:00",
        "important_events": ["事件 A", "事件 B"],
        "execution_steps": [
            {"name": "读取昨天记忆", "status": "ok", "file": "memory/2026-03-17.md", "detail": "提炼关键洞察"}
        ],
        "completed_tasks": ["完成任务 A"],
        "new_topics": ["新主题 A（SCORE 23/25）"],
        "insights": ["洞察 A"],
        "lessons": ["教训 A"],
        "updated_files": [{"path": "/tmp/demo.md", "note": "补充整理结果"}],
    }

    card = build_generic_card("daily-knowledge", template_config, data)

    assert card["header"]["title"]["content"] == "每日知识整理任务完成"
    rendered_blocks = [
        element["text"]["content"]
        for element in card["elements"]
        if element.get("tag") == "div"
    ]
    assert any("**执行步骤**" in content for content in rendered_blocks)
    assert any("读取昨天记忆" in content for content in rendered_blocks)
    assert any("**关键洞察**" in content for content in rendered_blocks)
    assert any("洞察 A" in content for content in rendered_blocks)


def test_materialize_template_registry_replaces_renderer_with_blocks() -> None:
    registry = {
        "templates": {
            "daily-knowledge": {
                "description": "每日知识整理",
                "renderer": "daily_knowledge",
                "presentation": {"header_title_template": "📚 每日知识整理 · {report_date}"},
            }
        }
    }

    updated, changes = materialize_template_registry(registry, drop_renderer=True)

    template = updated["templates"]["daily-knowledge"]
    assert changes == [{"template": "daily-knowledge", "blocks": "updated", "renderer": "removed"}]
    assert "renderer" not in template
    assert template["presentation"]["header_title_template"] == "📚 每日知识整理 · {report_date}"
    assert template["presentation"]["blocks"][0]["type"] == "markdown"
