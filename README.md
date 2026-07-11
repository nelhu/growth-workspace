# growth-workspace

小红书内容 Skill、参考附件与每日内容包的仓库归档。

- [早餐内容生成 Skill](skills/breakfast-xiaohongshu/SKILL.md)
- [浏览器发帖 Skill](skills/xiaohongshu-chrome-post/SKILL.md)
- [参考图片与问答附件索引](assets/README.md)
- [小红书草稿](drafts/)
- [每日早餐内容包](dist/breakfast-xiaohongshu/)
- [历史早餐样例](xhs/)

每日生成产物固定存放在 `dist/breakfast-xiaohongshu/{YYYY-MM-DD}/`。每个日期目录的 `README.md` 是唯一人工交付入口，包含可直接发布的全部文案和图片预览；`content-package.json` 和 `weekly-hot-tags.json` 仅用于校验与追溯。内容校验通过并成功推送到 `origin/main` 后才算交付完成。
