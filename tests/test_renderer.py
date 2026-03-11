from openclaw_feishu_cron_kit.renderer import build_summary_post


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
