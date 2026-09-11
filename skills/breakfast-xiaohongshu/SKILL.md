---
name: breakfast-xiaohongshu
description: 为中国四口之家生成早餐图文内容包，并在用户明确要求发布时通过本地 Chrome Computer Use 发布小红书笔记。适用于早餐计划、信息图、文案标题、本地 Top10 话题导入、生成并发布或发布已有早餐内容包；仅要求生成时不发布。
---

# 小红书早餐 Skill

这个 Skill 覆盖“生成 + 浏览器发布”完整流程。仅生成、发布已有内容包、生成并发布三种模式按用户请求选择；不得把生成请求视为发布授权。内容必须真实适合中国家庭早晨操作，不做摆拍型早餐。

## 核心规则

- 发布只使用本地 Chrome 的 Computer Use，不启动 `xiaohongshu-mcp`，不调用 `scripts/breakfast_xhs.py publish` 或 MCP `publish_content`。
- 发布话题必须按台账逐个输入、逐个确认被编辑器识别为话题；禁止整段粘贴 10 个 `#话题`。全部绑定并核验名称、数量、顺序后才能提交。发布前还必须执行可交互检查、状态驱动等待、字段回读、有限退避和单次提交等可靠性规则；不得用伪装真人、随机乱点、指纹修改或验证码绕过来规避平台检测。操作细节见 `references/browser-publish.md`。
- 生成阶段输出至少 3 张小红书配图、标题、200 字以内文案、10 个话题标签、互动问题、置顶评论、明天预告、发布描述和内容包路径；发布阶段另交付实际提交结果。
- 每日全部产物必须写入当前工作区 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}/`：包含图片、`README.md`、`content-package.json`、`weekly-hot-tags.json` 和辅助预览图。不得只写入 `~/.breakfast-xiaohongshu/out/` 或其他本机私有目录。
- `README.md` 是每日唯一的人工交付入口，必须汇总标题、正文、10 个标签、互动问题、置顶评论、明天预告、发布状态、热词台账链接和所有图片预览/链接。用户只需阅读此文件，不应依赖 JSON。
- 每次生成完成后必须运行 `validate-manifest`，然后执行 `git add dist/breakfast-xiaohongshu/{YYYY-MM-DD}`、`git commit`、`git push origin main`。仅当推送成功后才可标记任务完成；校验或推送失败必须如实返回失败原因，状态不得写为完成。
- 用户明确要求“发布”或“生成并发布”时，阅读并执行 [浏览器发布流程](references/browser-publish.md)。本次升级 Skill 不更改已有定时任务的生成-only授权；持续自动发布需要用户另行明确授权并更新自动化。
- 生成前必须阅读 `references/content-strategy.md` 和 [本地 Top10 规则](references/weekly-hot-tags.md)，先导入话题，再运行上下文命令：

```bash
python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py context
```

使用脚本返回的 JSON 作为生成上下文，里面包含日期、星期、早餐轮换、最近 7 天避重、配色、蛋白质重点和输出路径。
- 运行 `python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py import-latest-topics --date YYYY-MM-DD`，从工作区 `dist/hot-topics` 最新日期的 Markdown 导入前 10 条话题，保留顺序和来源快照，不再随机生成。缺失或不足 10 条时暂停，不静默回退到旧文件或随机词。

## Tiny.C 账号的 AI 声明偏好

用户已说明个人账号会统一声明 AI 相关内容，后续按以下偏好生成文案和执行用户单独授权的发布任务：

- 正文不再添加“配图为 AI 辅助搭配示意”等 AI 配图声明文案；交付 Markdown 和内容包中的正文保持一致。
- 浏览器发布时不主动选择“笔记含 AI 合成内容”或“含 AI 生成内容”类型声明。
- 若平台自动添加该标识或明确强制要求声明，则保留并告知用户，不绕过平台要求；账号声明不视为平台豁免的证明。
- 此偏好不授权修改已发布笔记，也不改变每日自动化仅生成、不发布的边界。

## 内容生成

生成图片时必须优先使用 `GPT Image 2` 这类高保真图片生成模型，并套用 `references/content-strategy.md` 里的“固定图片风格 Prompt”。该风格是高信息密度的小红书早餐计划海报：日历卡片、大标题、顶部 5 个信息模块、4 个带真实食物图的早餐表格区块、底部营养/预算/快速方案总结。不要生成极简现代卡片图。

本地 SVG、手写 HTML 截图、纯矢量图只能作为结构草稿或排版沟通稿，不能作为最终成品图。最终图必须是高保真图片生成结果，食物照片、纸张质感、图标和整体逼真度要贴近用户提供的小红书样例。

最终图尺寸必须固定为 `853×1280 px`，即用户样例海报本体尺寸。不要使用手机截图尺寸，也不要生成 `864×1821` 这类过长比例。若图片生成模型输出其他尺寸，必须重新生成，或在不拉伸变形的前提下裁切/缩放为 `853×1280` 后再进入内容包。

每次必须生成以下最终产物：

1. 多张小红书配图，顺序固定：
   - 第 1 张：真实家庭餐桌早餐成品图，背景必须采用固定的家庭餐桌和餐厅元素，可以展示不同拍摄角度，给粉丝形成“主人家餐厅餐桌”的空间记忆；参考用户提供的真实餐桌风格图，不做拼贴宫格。
   - 第 2 张：最终版竖版早餐信息图，必须采用参考图确认过的暖色高信息密度版式：顶部日期/标题/5 个计划模块，中部 2×2 菜品卡片，底部营养亮点和小贴士。
   - 第 3 张及以后：菜品制作过程图，每张聚焦一个菜品，展示成品、食材准备、做法步骤和小贴士；不再展示购物清单或明天预告。
2. 小红书标题：采用 `references/content-strategy.md` 的吸引力标题模板，以早餐为主题，突出当天菜品或实用卖点；不再强制栏目名和天数前缀，控制在 20 个字符以内。
3. 200 字以内小红书精炼正文。
4. 从 `dist/hot-topics` 最新日期文件的 `## Top10` 导入前 10 条话题，按来源顺序使用，不随机补词；详细选择、快照与失败规则见 `references/weekly-hot-tags.md`（本参考文档内为同目录 `weekly-hot-tags.md`）。
5. 互动问题 A/B/C/D，其中 D 必须是“评论区留下你专属版”。
6. 置顶评论。
7. 明天预告。
8. 发布描述：说明至少 3 张图片路径、标题、正文、标签、互动问题、置顶评论、明天预告和建议发布时间/备注，供用户手动发布。
9. 结构化内容包 JSON，命名为 `content-package.json` 或 `manifest.json`，用于存档、校验及浏览器发布时读取；它本身不构成发布授权。
10. 每日交付 Markdown，固定命名为 `README.md`，作为 GitHub 目录的默认可读交付页。必须完整同步上述第 2-7 项和图片链接，并在内容包根字段 `delivery_markdown_path` 中登记其本地绝对路径。

话题字段格式：`tag_strategy={"mode":"local_top10","is_verified_trend":false,"weekly_hot_tag_registry_path":"目标日期目录的绝对路径/weekly-hot-tags.json"}`。`tags` 完整复制台账前 10 条候选的 tag；本地精选结果不等于已独立验证的官方热榜。

生成后可以运行校验，确认至少 3 张图片、标题、正文、10 个标签、互动问题、置顶评论、明天预告和策略字段完整：

```bash
python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py validate-manifest /path/to/content-package-or-manifest.json
```

生成成功后记录本次早餐方案，避免一周内重复。此时不要带 `--published`；只有浏览器确认发布成功后，才按发布参考流程记录已发布历史：

```bash
python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py record /path/to/content-package-or-manifest.json
```

## 定时任务规则

目标时间：每天 18:00，时区 Asia/Shanghai，为运行日的“明天”生成小红书早餐内容包。

自动化策略：

- 18:00 生成内容、多张图片、标题、文案、10 个标签、互动问题、置顶评论、明天预告、发布描述和结构化内容包。
- 所有当日产物输出到 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}/`；交付页固定命名为 `README.md`，热词台账固定命名为 `weekly-hot-tags.json`，内容包固定命名为 `content-package.json`。
- 校验标题长度、200 字以内文案、图片路径、图片尺寸、10 个标签、互动问题、置顶评论、明天预告、交付 Markdown 和必填策略字段。
- 最终图必须是 `853×1280 px`。
- 只记录生成历史，不记录为已发布。
- 不检查小红书登录态。
- 不启动 `xiaohongshu-mcp`。
- 不自动公开发布。
- 不使用 `AUTO_PUBLISH`。
- 校验通过后，必须将当日 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}` 产物与所需的 Skill/参考附件变更提交并推送至 `origin/main`；`git push origin main` 成功才是任务完成条件。

输出 macOS LaunchAgent 模板：

```bash
python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py launchd-template --command "/path/to/daily-breakfast-command"
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
- 从 `dist/hot-topics` 最新日期文件的 `## Top10` 导入前 10 条话题，按来源顺序使用，不随机补词；详细选择、快照与失败规则见 `references/weekly-hot-tags.md`（本参考文档内为同目录 `weekly-hot-tags.md`）。
- 每篇必须包含互动问题 A/B/C/D，D 是“评论区留下你专属版”。
- 每篇必须包含置顶评论和明天预告，用来把收藏用户转化为追更关注。
- 每日 `README.md` 必须是内容包的完整、可直接阅读版本，包含全部图片预览/链接和可复制的文案字段；缺失或与内容包不一致时，校验必须失败。

## 最终回复格式

每次生成完成后回复以下字段；发布模式另报告 `publication.json` 路径、提交证据、置顶评论状态，不能把生成完成当成发布成功：

- 目标日期
- 标题
- 图片路径
- 内容包路径
- 每日交付 Markdown 路径
- 小红书文案
- 流量标签
- 互动问题
- 置顶评论
- 明天预告
- 发布状态：按实际阶段报告未发布、发布成功、结果待核实或阻塞
- 失败原因，如有
- Git 推送结果
