from pathlib import Path
import hashlib
import json
import secrets
import shutil

root = Path(__file__).resolve().parent
registry = json.loads((root / 'weekly-hot-tags.json').read_text())
checks = json.loads((root / 'watermark-verification.json').read_text())
assert len(registry['candidates']) == 10
for check in checks:
    assert check['size'] == [853, 1280]
    assert check['identify_code'] == 0
    assert 'AI metadata stripped' in check['all_stdout']
    assert 'Skipped (no visible watermark detected)' in check['all_stdout']
    assert not json.loads(check['identify_stdout'])['watermarks']
    assert not json.loads(check['identify_stdout'])['signals']

names = {
    'real_family_table': 'family-table',
    'final_infographic': 'breakfast-overview',
    'dish_process': 'shrimp-edamame-bun-process',
}
descs = {
    'real_family_table': '四人份紫薯燕麦羹、虾仁毛豆豆腐小包、清炒小白菜和柑橘家庭餐桌',
    'final_infographic': '奶油米白与清新绿高密度早餐总览',
    'dish_process': '虾仁毛豆豆腐小包食材与四步制作过程',
}
by_role = {x['role']: x for x in checks}
order = list(by_role)
secrets.SystemRandom().shuffle(order)
images, plan = [], []
for number, role in enumerate(order, 1):
    clean = Path(by_role[role]['clean'])
    final = root / f'{number:02d}-{names[role]}.png'
    shutil.copy2(clean, final)
    assert hashlib.sha256(final.read_bytes()).digest() == hashlib.sha256(clean.read_bytes()).digest()
    images.append(str(final))
    item = {'order': number, 'type': role, 'description': descs[role]}
    if role == 'dish_process':
        item['dish'] = '虾仁毛豆豆腐小包'
    plan.append(item)

copy = json.loads((root / 'content-text.json').read_text())
title, body = copy['title'], copy['content']
assert len(title) <= 20 and len(body) <= 200
tags = [item['tag'] for item in registry['candidates']]
interaction = '明天我做 4 个版本：A. 小学生长高版 B. 老人好消化版 C. 上班族快手版 D. 评论区留下你专属版。你家更需要哪个？评论 A/B/C/D，我按票数发；选 D 的直接留下年龄、家庭人数、忌口和早上可用时间。关注我，明早直接抄作业。'
pinned = '想要「7天不重样早餐表」的，评论“7天”。选 D 的留下年龄、家庭人数、忌口和早上可用时间，我会挑典型家庭做专属版，后面每天更新。'
preview = '明天预告：不喝牛奶也高钙版，芝麻豆腐玉米卷配热梨羹。'
prep = '前晚虾仁切丁、毛豆焯熟，拌碎豆腐后包成小包并冷冻；紫薯蒸熟冷藏；小白菜洗净沥干。'
timeline = [
    '0–5分钟冷冻小包入蒸锅，紫薯与燕麦加水入小锅加热',
    '5–10分钟搅拌紫薯燕麦羹，同时切好小白菜',
    '10–15分钟快炒小白菜，检查蒸锅水量',
    '15–20分钟确认虾仁小包彻底蒸熟，分装羹、小包、青菜和柑橘',
]
emergency = '即饮无糖豆浆、全麦面包、即食熟鸡蛋和香蕉，5分钟。'
watermark = '3 张最终图片均由 remove-ai-watermarks all 从独立 853×1280 源文件生成；identify --json 未检测到可识别水印或 metadata 信号。不可见水印阶段因缺少 GPU 依赖跳过，按 Skill 规则不拦截。详见 watermark-verification.json。'
manifest = {
    'date': '2026-09-29', 'weekday': '星期二', 'title': title, 'content': body,
    'tags': tags, 'interaction_question': interaction, 'pinned_comment': pinned,
    'tomorrow_preview': preview, 'status': 'ready_for_review', 'is_original': True,
    'should_publish': False, 'delivery_markdown_path': str(root / 'README.md'),
    'images': images, 'image_plan': plan,
    'first_image_references': [
        '/Users/xuezi/dir/growth-workspace/dist/breakfast-xiaohongshu/2026-09-25/03-family-table.png',
        '/Users/xuezi/dir/growth-workspace/assets/image1_example/image_44641b65.jpg',
    ],
    'strategy': {'structure': '蒸制类', 'soup_type': '紫薯燕麦羹',
                 'dry_main': '虾仁毛豆豆腐小包', 'color_palette': '清新绿色',
                 'protein_focus': ['虾仁', '毛豆', '豆腐']},
    'tag_strategy': {'mode': 'local_top10', 'is_verified_trend': False,
                     'weekly_hot_tag_registry_path': str(root / 'weekly-hot-tags.json')},
    'publishing_notes': '草稿保存已按用户后续要求暂停，未发布。图片顺序：' +
                        '、'.join(f'图{i+1}{descs[role]}' for i, role in enumerate(order)) + '。',
    'watermark_verification': watermark, 'budget_rmb': 40, 'prep': prep,
    'timeline': timeline, 'emergency_plan': emergency,
    'menu': [
        {'name': '紫薯燕麦羹', 'ingredients': '熟紫薯约300g、燕麦片100g、水约900ml',
         'method': '紫薯前晚蒸熟冷藏；早晨压碎，与燕麦和水同煮约8分钟，搅拌至软糯。'},
        {'name': '虾仁毛豆豆腐小包', 'ingredients': '虾仁200g、毛豆100g、北豆腐150g、饺子皮约20张',
         'method': '前晚虾仁切丁，毛豆焯熟，与压碎的豆腐拌馅，包入饺子皮后冷冻；早晨从冷冻直接蒸15分钟左右，确认虾仁彻底熟透。'},
        {'name': '清炒小白菜', 'ingredients': '小白菜约400g、蒜末少许、植物油少许',
         'method': '洗净切段，热锅少油快炒至熟，老人份切细并少盐。'},
        {'name': '柑橘', 'ingredients': '柑橘4个', 'method': '洗净后剥皮分瓣；孩子份检查去籽。'},
    ],
}
(root / 'content-package.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
lines = [
    '# 2026-09-29 早餐内容包', '', '## 小红书标题', '', title, '',
    '## 小红书正文', '', body, '', '## 流量标签', '', ' '.join(tags), '',
    '## 互动问题', '', interaction, '', '## 置顶评论', '', pinned, '',
    '## 明天预告', '', preview, '', '## 发布状态', '',
    '草稿保存已按用户后续要求暂停，未发布；ready_for_review；should_publish=false。', '',
    '## 菜单与20分钟流程', '',
    '- 紫薯燕麦羹 + 虾仁毛豆豆腐小包 + 清炒小白菜 + 柑橘。',
    '- 前晚准备：' + prep, '- 早晨流程：' + '；'.join(timeline) + '。',
    '- 极忙5分钟：' + emergency, '- 预算：约40元/四人。', '',
    '## 话题来源', '',
    '来源日期：' + registry['source_date'] + '。[话题台账](weekly-hot-tags.json)。本地精选，不是独立核实官方热榜。', '',
    '## 配图', '',
]
for i, (role, path) in enumerate(zip(order, images), 1):
    name = Path(path).name
    lines += [f'![图{i}：{descs[role]}]({name})', '', f'[图{i}文件]({name})', '']
lines += [
    '## 内容包与发布描述', '',
    '[content-package.json](content-package.json)。图片按上述随机顺序排列；标题、正文、标签、互动问题、置顶评论和明天预告已同步。建议上海时间早间手动审阅；草稿保存当前暂停，未执行发布。', '',
    '## 图片核验', '',
    '3 张最终图片均为 853×1280 px，由独立源图经 `remove-ai-watermarks all` 生成新文件；`identify --json` 未检测到可识别水印或 metadata 信号。不可见水印阶段因缺少 GPU 依赖跳过，按 Skill 规则不拦截，也不据此宣称图片绝对无水印。详见 [watermark-verification.json](watermark-verification.json)。', '',
]
(root / 'README.md').write_text('\n'.join(lines))
print(json.dumps({'order': order, 'title': title, 'content_length': len(body), 'images': images}, ensure_ascii=False, indent=2))
