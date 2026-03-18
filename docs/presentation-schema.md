# Presentation Schema

这个文档定义模板配置里的展示层 DSL。

核心目标只有一个：把“卡片长什么样”从脚本里抽出来，沉淀到配置。

```ascii
presentation
├─ schema
├─ structure
├─ styles
└─ blocks
```

## 1. `schema`

当前推荐：

- `1.0`
  - 兼容旧模板，适合线性结构
- `2.0`
  - 推荐新模板，适合 panel、折叠块、按记录动态展开

## 2. `structure`

`structure` 是功能型结构族，不按业务场景命名。

推荐结构族：

- `generic`
  - 普通线性报告
- `collapsible-list`
  - 适合知识整理、日报、执行步骤这类“多段折叠”
- `grouped-panels`
  - 适合按 agent / 分类动态展开多个 panel
- `panel-report`
  - 适合巡检、诊断、问题发现这类报告
- `items-report`
  - 适合热点清单、候选项列表
- `sections-report`
  - 适合标准多 section 简报

## 3. `styles`

`styles` 描述的是视觉样式，而不是业务含义。

例如：

```json
{
  "panels": {
    "default": {
      "title_color": "#333333",
      "header_background_color": "grey",
      "border_color": "grey"
    }
  }
}
```

适合沉淀的内容：

- 面板颜色
- header 背景
- 边框颜色
- 图标或 emoji 约定

## 4. `blocks`

`blocks` 决定卡片内容怎么拼。

常用 block：

- `plain_text`
- `markdown`
- `facts`
- `list`
- `record_list`
- `collapsible_panel`
- `collapsible_record_panels`
- `divider`
- `note`

## 5. 推荐分层

```ascii
业务 payload
  -> title / summary / stats / jobs / insights / ...

presentation.structure
  -> 选择整体布局族

presentation.blocks
  -> 决定每块怎么渲染

styles
  -> 决定视觉细节
```

## 6. 推荐实践

- 优先先选 `structure`，不要先想“我要不要新建一个 renderer”
- 相同结构、不同业务，只换 `required_fields` 和 payload
- 样式变化优先动 `styles`，不要动业务脚本
- 折叠、列表、panel 这类交互结构统一沉淀在配置，不继续写死在 Python 里

## 7. 例子

```ascii
daily-knowledge
  -> structure = collapsible-list
  -> blocks = summary + timestamp + 执行步骤折叠 + 洞察折叠 + 教训折叠

openclaw-best-practices
  -> structure = grouped-panels
  -> blocks = summary + 每个 agent 的推荐 panel

cron-diagnosis-report
  -> structure = panel-report
  -> blocks = summary + stats + findings + jobs
```

## 8. 不推荐继续做的事

- 用模板名绑定 renderer 名称
- 在脚本里判断“如果是 daily_knowledge 就手拼折叠面板”
- 在业务脚本里直接构造 Feishu card JSON
- 在 prompt 里描述卡片布局细节
