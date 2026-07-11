---
name: breakfast-xiaohongshu
description: 为中国四口之家生成每日小红书早餐内容包。适用于用户要求自动生成早餐小红书、明日早餐计划、竖版早餐信息图、200字内小红书文案、流量标签、每天上海时间18点生成早餐内容、家庭营养早餐轮换的场景。本 Skill 只产出图文和发布描述，不直接发布到小红书。
---

# 小红书早餐 Skill

这个 Skill 用来建立可长期执行的“明天早餐”小红书内容生成工作流：只生成待人工确认/发布的图文内容包，不直接发布到小红书。内容必须真实适合中国家庭早晨操作，不做摆拍型早餐。

## 核心规则

- 禁止自动发布：默认和定时任务都不得启动 `xiaohongshu-mcp`，不得调用 `scripts/breakfast_xhs.py publish`，不得调用 MCP `publish_content`。
- 只产出内容：最终只输出至少 3 张小红书配图、小红书标题、200 字以内文案、10 个话题标签、互动问题、置顶评论、明天预告、发布描述和内容包路径。
- 每日全部产物必须写入当前工作区 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}/`：包含图片、`content-package.json`、`weekly-hot-tags.json` 和辅助预览图。不得只写入 `~/.breakfast-xiaohongshu/out/` 或其他本机私有目录。
- 每次生成完成后必须运行 `validate-manifest`，然后执行 `git add dist/breakfast-xiaohongshu/{YYYY-MM-DD}`、`git commit`、`git push origin main`。仅当推送成功后才可标记任务完成；校验或推送失败必须如实返回失败原因，状态不得写为完成。
- 如果用户后续单独要求发布，必须把“发布”视为新的显式任务；本 Skill 的每日自动化仍然只生成内容。
- 生成前必须阅读 `references/content-strategy.md`，并运行：

```bash
python3 scripts/breakfast_xhs.py context
```

使用脚本返回的 JSON 作为生成上下文，里面包含日期、星期、早餐轮换、最近 7 天避重、配色、蛋白质重点和输出路径。
- 生成前必须从千瓜或新榜采集最近 7 天的候选热词，并写入台账。千瓜/新榜是“本周最热”的唯一来源；小红书关键词搜索页不得作为热词证据。仅当 `weekly_hot_tag_status` 为 `ready` 时，才能生成 `ready_for_review` 内容包；每个目标日期的最终内容包必须通过校验，且固定为 `status=ready_for_review`、`should_publish=false`、`is_original=true`。

```bash
python3 scripts/breakfast_xhs.py save-weekly-hot-tags --date YYYY-MM-DD --input /path/to/weekly-hot-tags.json
```

台账输入必须包含 `collected_at` 及至少 5 个 `candidates`；每个候选必须有 `tag`、`source_name`（千瓜数据或新榜）、`source_url`、`source_type`、`rank_context`、`observed_at`、`rank`、`relevance`。来源 URL 必须属于对应网站，无法取得可验证来源时不得用泛标签补位。

## 内容生成

生成图片时必须优先使用 `GPT Image 2` 这类高保真图片生成模型，并套用 `references/content-strategy.md` 里的“固定图片风格 Prompt”。该风格是高信息密度的小红书早餐计划海报：日历卡片、大标题、顶部 5 个信息模块、4 个带真实食物图的早餐表格区块、底部营养/预算/快速方案总结。不要生成极简现代卡片图。

本地 SVG、手写 HTML 截图、纯矢量图只能作为结构草稿或排版沟通稿，不能作为最终成品图。最终图必须是高保真图片生成结果，食物照片、纸张质感、图标和整体逼真度要贴近用户提供的小红书样例。

最终图尺寸必须固定为 `853×1280 px`，即用户样例海报本体尺寸。不要使用手机截图尺寸，也不要生成 `864×1821` 这类过长比例。若图片生成模型输出其他尺寸，必须重新生成，或在不拉伸变形的前提下裁切/缩放为 `853×1280` 后再进入内容包。

每次必须生成以下最终产物：

1. 多张小红书配图，顺序固定：
   - 第 1 张：真实家庭餐桌早餐成品图，背景必须采用固定的家庭餐桌和餐厅元素，可以展示不同拍摄角度，给粉丝形成“主人家餐厅餐桌”的空间记忆；参考用户提供的真实餐桌风格图，不做拼贴宫格。
   - 第 2 张：最终版竖版早餐信息图，必须采用参考图确认过的暖色高信息密度版式：顶部日期/标题/5 个计划模块，中部 2×2 菜品卡片，底部营养亮点和小贴士。
   - 第 3 张及以后：菜品制作过程图，每张聚焦一个菜品，展示成品、食材准备、做法步骤和小贴士；不再展示购物清单或明天预告。
2. 小红书标题，使用连续栏目格式，例如：`跟着 Tiny.C 吃30天早餐｜第08天｜四口之家20分钟中式早餐`。
3. 200 字以内小红书精炼正文。
4. 10 个话题标签：前 5 个为固定垂直标签，后 5 个为本周小红书热词筛选；每个标签必须带 `#`，方便直接复制到小红书。
5. 互动问题 A/B/C/D，其中 D 必须是“评论区留下你专属版”。
6. 置顶评论。
7. 明天预告。
8. 发布描述：说明至少 3 张图片路径、标题、正文、标签、互动问题、置顶评论、明天预告和建议发布时间/备注，供用户手动发布。
9. 结构化内容包 JSON，命名为 `content-package.json` 或沿用脚本返回目录下的 `manifest.json`，但它只用于存档/校验/人工复制，不用于自动发布。

结构化内容包建议包含：

```json
{
  "date": "YYYY-MM-DD",
  "weekday": "星期X",
  "title": "跟着 Tiny.C 吃30天早餐｜第08天｜四口之家20分钟中式早餐",
  "content": "200字以内正文，不把#话题写进正文",
  "images": [
    "/absolute/path/to/01-real-family-table.png",
    "/absolute/path/to/02-final-infographic.png",
    "/absolute/path/to/03-shrimp-noodle-process.png"
  ],
  "image_plan": [
    {"order": 1, "type": "real_family_table", "description": "固定家庭餐桌和餐厅背景的真实早餐成品图"},
    {"order": 2, "type": "final_infographic", "description": "暖色高信息密度总览信息图：顶部5个计划模块，中部2×2菜品卡，底部营养亮点和小贴士"},
    {"order": 3, "type": "dish_process", "dish": "虾仁毛豆青菜汤面", "description": "菜品制作过程图"}
  ],
  "first_image_references": [
    "/absolute/path/to/reference-family-table-photo.jpg"
  ],
  "tags": ["#早餐", "#儿童早餐", "#家庭早餐", "#长高早餐", "#四口之家早餐", "#本周热词1", "#本周热词2", "#本周热词3", "#本周热词4", "#本周热词5"],
  "tag_strategy": {
    "fixed_vertical_tags": ["#早餐", "#儿童早餐", "#家庭早餐", "#长高早餐", "#四口之家早餐"],
    "weekly_hot_tags": ["#本周热词1", "#本周热词2", "#本周热词3", "#本周热词4", "#本周热词5"],
    "weekly_hot_tag_registry_path": "/absolute/path/to/workspace/dist/breakfast-xiaohongshu/YYYY-MM-DD/weekly-hot-tags.json",
    "weekly_hot_tag_evidence": [
      {"tag": "#本周热词1", "source_name": "千瓜数据", "source_url": "https://www.qian-gua.com/...", "source_type": "topic_rank", "rank_context": "美食饮品周榜", "observed_at": "YYYY-MM-DDTHH:MM:SS+08:00", "rank": 1}
    ]
  },
  "interaction_question": "明天我做 4 个版本：A. 小学生长高版 B. 老人好消化版 C. 上班族快手版 D. 评论区留下你专属版。你家更需要哪个？评论 A/B/C/D，我按票数发。",
  "pinned_comment": "想要「7天不重样早餐表」的，评论“7天”。选 D 的留下年龄、家庭人数、忌口和早上可用时间，我会挑典型家庭做专属版。",
  "tomorrow_preview": "明天预告：不喝牛奶也高钙版四口之家早餐。",
  "status": "ready_for_review",
  "should_publish": false,
  "is_original": true,
  "strategy": {
    "structure": "粥类",
    "soup_type": "小米粥",
    "dry_main": "牛肉鸡蛋饼",
    "color_palette": "春日绿色",
    "protein_focus": ["牛肉", "鸡蛋", "豆浆"]
  }
}
```

生成后可以运行校验，确认至少 3 张图片、标题、正文、10 个标签、互动问题、置顶评论、明天预告和策略字段完整：

```bash
python3 scripts/breakfast_xhs.py validate-manifest /path/to/content-package-or-manifest.json
```

生成成功后记录本次早餐方案，避免一周内重复。不要带 `--published`：

```bash
python3 scripts/breakfast_xhs.py record /path/to/content-package-or-manifest.json
```

## 定时任务规则

目标时间：每天 18:00，时区 Asia/Shanghai，为运行日的“明天”生成小红书早餐内容包。

自动化策略：

- 18:00 生成内容、多张图片、标题、文案、10 个标签、互动问题、置顶评论、明天预告、发布描述和结构化内容包。
- 所有当日产物输出到 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}/`；热词台账固定命名为 `weekly-hot-tags.json`，内容包固定命名为 `content-package.json`。
- 校验标题长度、200 字以内文案、图片路径、图片尺寸、10 个标签、互动问题、置顶评论、明天预告和必填策略字段。
- 最终图必须是 `853×1280 px`。
- 只记录生成历史，不记录为已发布。
- 不检查小红书登录态。
- 不启动 `xiaohongshu-mcp`。
- 不自动公开发布。
- 不使用 `AUTO_PUBLISH`。
- 校验通过后，必须将当日 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}` 产物与所需的 Skill/参考附件变更提交并推送至 `origin/main`；`git push origin main` 成功才是任务完成条件。

输出 macOS LaunchAgent 模板：

```bash
python3 scripts/breakfast_xhs.py launchd-template --command "/path/to/daily-breakfast-command"
```

除非用户明确要求，不要安装或覆盖系统定时任务。

## 质量门槛

- 7 天内早餐结构不重复。
- 不连续使用鸡蛋汤、紫菜汤、豆腐汤、蒸蛋、鸡肉饼，或相同“稀 + 干”结构。
- 必须包含“稀 + 干”、工作日 20 分钟流程、5 分钟极忙快速方案。
- 优先保证 6 岁女儿长高营养，同时兼顾哺乳期补蛋白/补钙/补铁、老人清淡易消化、上班族顶饱稳定。
- 预算约 40 元/天，口味为普通中式家常。
- 图片风格必须贴近参考图：浅米白底、主题色边框、日历卡片、真实食物小图、紧凑表格、高信息密度；避免明显 AI 感、大块留白和低保真矢量感。
- 图片尺寸必须通过校验：本地最终图片应为 `853×1280 px`。
- 每日推送至少 3 张图：图 1 为真实家庭餐桌首图，图 2 为总览信息图，图 3 及以后为菜品制作过程图。图 3-N 不再展示购物清单和明天预告。
- 第 1 张真实家庭餐桌早餐成品图必须记录 `first_image_references`，至少包含 1 个参考来源 URL 或本地绝对路径。画面必须有固定餐桌、餐厅背景、木椅/窗帘/绿植等可持续复用的空间识别元素，不再使用拼贴宫格。
- 用户提供的参考附件必须保存在仓库 `assets/`，并在内容包或对应说明中保留仓库相对路径或 GitHub 链接；不得只引用聊天临时文件或本机路径。
- 话题标签必须恰好 10 个，且每个都必须带 `#`：前 5 个固定为 `#早餐`、`#儿童早餐`、`#家庭早餐`、`#长高早餐`、`#四口之家早餐`；后 5 个必须从当次写入的最近 7 天热词台账中筛选。`tag_strategy.weekly_hot_tags` 必须和 `tags` 后 5 个完全一致，且每个标签都必须有千瓜/新榜的来源 URL、采集时间、榜单类型、榜单说明和位置。没有台账或来源过期时，校验必须失败。
- 每篇必须包含互动问题 A/B/C/D，D 是“评论区留下你专属版”。
- 每篇必须包含置顶评论和明天预告，用来把收藏用户转化为追更关注。

## 最终回复格式

每次生成完成后，只回复：

- 目标日期
- 标题
- 图片路径
- 内容包路径
- 小红书文案
- 流量标签
- 互动问题
- 置顶评论
- 明天预告
- 发布状态：未发布，仅生成待人工确认内容
- 失败原因，如有
- Git 推送结果
