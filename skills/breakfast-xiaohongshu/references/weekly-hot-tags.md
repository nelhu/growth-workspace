# 随机话题规则

每次运行 `python3 skills/breakfast-xiaohongshu/scripts/breakfast_xhs.py generate-random-tags --date YYYY-MM-DD`，离线随机生成恰好 10 个不重复话题，覆盖早餐、美食、穿搭、显瘦、美妆、旅行六类。全部 10 个 tags 按台账顺序使用，不再固定前 5 个标签。无需 Token、联网采集、榜单证据或最近 7 天热词；随机话题不得称为已验证热词。为兼容目录结构，台账仍叫 weekly-hot-tags.json。tag_strategy 必须包含 mode=random_topics、is_verified_trend=false 和 weekly_hot_tag_registry_path。

每个候选记录 tag 和 category。校验器检查日期、去重、六类覆盖、主题池归属和内容包与台账一致性。台账不记录虚构来源 URL、排名或曝光指标。
