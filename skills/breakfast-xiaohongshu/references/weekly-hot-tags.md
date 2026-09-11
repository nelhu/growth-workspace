# 本地最新 Top10 话题规则

来源固定为 `/Users/xuezi/dir/growth-workspace/dist/hot-topics/{YYYY-MM-DD}.md`，上游产出格式为 `## Top10` 表格和 `## 原始内容`。不要递归读取 demo、测试文件或把原始回答当作精选列表。

生成前执行：

```bash
python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py import-latest-topics --date YYYY-MM-DD
python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py context --date YYYY-MM-DD
```

- 按文件名中的合法日期选最新文件，而不是文件修改时间；不选晚于执行当天上海日期的文件。补生成旧早餐时仍取执行时最新来源，不按早餐目标日筛选。
- 只读 `## Top10` 中的表格：`序号 | 话题 | 入选类型 | 原始依据`。序号从 1 连续递增，取前 10 条，保留顺序、类型和依据，名称仅补齐前导 `#`。
- 上游可能保留超过 10 条，本 Skill 只取前 10 条；前 10 条重复、不足 10 条、最新文件损坏或缺少章节时明确报错，不静默改用旧日期，不随机补词。提示用户先产出/修复热门话题文件；不要自行联网启动上游查询。
- 在早餐目标目录生成 `weekly-hot-tags.json`，记录 `mode=local_top10`、`is_verified_trend=false`、`source_path`、`source_date`、`source_sha256`、完整 `source_markdown` 快照和 10 条 `candidates`。本地来源的入选依据照录，不将点点 AI 的推荐升级为已独立核实的官方热榜。
- `tag_strategy` 使用 `mode=local_top10`、`is_verified_trend=false`、`weekly_hot_tag_registry_path`；`tags` 与台账一致。README 链接台账并显示来源日期，避免把旧来源说成当日趋势。
- 导入时选择最新来源；校验/发布时使用冻结的来源快照，后续新榜单出现或原文件更新不应悄悄改变已有内容包。缺少话题的旧草稿需要显式重新导入并同步 README/JSON 后校验。
- 旧 `fetch-weekly-hot-tags` 命令兼容转为本地导入；不再使用 `generate-random-tags`、Just One API、千瓜或新榜采集。
