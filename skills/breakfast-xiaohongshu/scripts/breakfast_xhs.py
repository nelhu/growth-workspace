#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import random
import struct
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse


WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parents[3]
STATE_DIR = pathlib.Path.home() / ".breakfast-xiaohongshu"
HISTORY_FILE = STATE_DIR / "history.json"
OUTPUT_DIR = WORKSPACE_ROOT / "dist" / "breakfast-xiaohongshu"
DEFAULT_MCP_URL = "http://127.0.0.1:18060/mcp"
TARGET_IMAGE_WIDTH = 853
TARGET_IMAGE_HEIGHT = 1280
FIXED_VERTICAL_TAGS = ["#早餐", "#儿童早餐", "#家庭早餐", "#长高早餐", "#四口之家早餐"]
TITLE_PATTERN = re.compile(r"跟着 Tiny\.C 吃30天早餐｜第\d{2}天｜四口之家20分钟.+早餐")
TREND_SOURCE_HOSTS = {
    "千瓜数据": ("qian-gua.com",),
    "新榜": ("newrank.cn",),
}
TREND_SOURCE_TYPES = {"hot_search", "topic_rank", "rising_rank", "industry_rank", "trend_report"}
IMAGE_PLAN_TYPES = [
    "real_family_table",
    "final_infographic",
]

STRUCTURES = [
    "粥类",
    "汤面类",
    "馄饨类",
    "豆浆类",
    "杂粮糊类",
    "牛肉面类",
    "蒸制类",
    "煎饼类",
    "包子类",
    "玉米红薯类",
    "贝果类",
    "手抓饼类",
    "杂粮饭团类",
]

PALETTES = [
    "春日绿色",
    "奶油橙",
    "豆沙粉",
    "浅蓝",
    "秋日暖棕",
    "日式木色",
    "清新绿色",
    "莫兰迪色系",
]

PROTEINS = [
    "牛肉",
    "牛腩",
    "牛肉末",
    "牛肉饼",
    "豆浆",
    "黄豆",
    "黑豆",
    "毛豆",
    "豆腐",
    "鸡蛋",
    "虾仁",
    "鱼类",
]

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def load_history():
    if not HISTORY_FILE.exists():
        return []
    with HISTORY_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_history(history):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history[-120:], f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_date(value):
    if value:
        return dt.date.fromisoformat(value)
    return dt.datetime.now().date() + dt.timedelta(days=1)


def trend_window(target):
    return target - dt.timedelta(days=6), target


def trend_registry_path(target):
    return OUTPUT_DIR / target.isoformat() / "weekly-hot-tags.json"


def delivery_markdown_path(target):
    return OUTPUT_DIR / target.isoformat() / "README.md"


def parse_observed_date(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("时间不能为空")
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def is_http_url(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def source_url_matches(source_name, source_url):
    if not is_http_url(source_url):
        return False
    hostname = (urlparse(source_url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in TREND_SOURCE_HOSTS[source_name])


class TrendProviderError(RuntimeError):
    pass


def now_shanghai():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).replace(microsecond=0)


def normalize_tag(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lstrip("#").strip()
    return f"#{value}" if value else None


def write_weekly_hot_tag_registry(registry, target):
    path = trend_registry_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as f:
            temp_path = pathlib.Path(f.name)
            json.dump(registry, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
    return path


TOPIC_POOLS = {
    "早餐": ["#早餐", "#家庭早餐", "#早餐不重样", "#快手早餐", "#中式早餐", "#早餐日常"],
    "美食": ["#美食", "#家常菜", "#美食分享", "#今天吃什么", "#在家做饭", "#简单美食"],
    "穿搭": ["#穿搭", "#日常穿搭", "#通勤穿搭", "#穿搭灵感", "#休闲穿搭"],
    "显瘦": ["#显瘦穿搭", "#显瘦搭配", "#微胖穿搭", "#显高显瘦", "#梨形身材穿搭"],
    "美妆": ["#美妆", "#日常妆容", "#新手化妆", "#自然妆容", "#美妆分享"],
    "旅行": ["#旅行", "#周末去哪儿", "#旅行日记", "#亲子旅行", "#城市漫步"],
}


def validate_weekly_hot_tag_registry(registry, target):
    if not isinstance(registry, dict):
        return ["话题台账必须是对象"]
    errors = []
    if registry.get("target_date") != target.isoformat():
        errors.append("话题台账目标日期不一致")
    if registry.get("mode") != "random_topics" or registry.get("is_verified_trend") is not False:
        errors.append("话题台账必须标记随机话题，非已验证热词")
    candidates = registry.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 10:
        return errors + ["随机话题必须恰好 10 个"]
    seen, categories = set(), set()
    for item in candidates:
        if not isinstance(item, dict):
            errors.append("话题候选必须是对象")
            continue
        tag, category = item.get("tag"), item.get("category")
        if category not in TOPIC_POOLS or tag not in TOPIC_POOLS.get(category, []):
            errors.append("话题必须来自指定六类主题池")
        if tag in seen:
            errors.append("随机话题不能重复")
        seen.add(tag)
        categories.add(category)
    if categories != set(TOPIC_POOLS):
        errors.append("随机话题必须覆盖早餐、美食、穿搭、显瘦、美妆、旅行")
    return errors


def load_weekly_hot_tag_registry(target):
    path = trend_registry_path(target)
    if not path.exists():
        return path, None, [f"缺少本周热词台账: {path}"]
    try:
        registry = load_manifest(path)
    except (OSError, json.JSONDecodeError) as error:
        return path, None, [f"无法读取本周热词台账: {error}"]
    return path, registry, validate_weekly_hot_tag_registry(registry, target)


def recent(history, days=7):
    today = dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=days)
    items = []
    for item in history:
        try:
            item_date = dt.date.fromisoformat(item.get("date", ""))
        except ValueError:
            continue
        if item_date >= cutoff:
            items.append(item)
    return items


def first_available(options, used, offset=0):
    for index in range(len(options)):
        candidate = options[(index + offset) % len(options)]
        if candidate not in used:
            return candidate
    return options[offset % len(options)]


def command_context(args):
    target = parse_date(args.date)
    history = load_history()
    recent_items = recent(history, 7)
    used_structures = {x.get("strategy", {}).get("structure") for x in recent_items}
    used_palettes = {x.get("strategy", {}).get("color_palette") for x in recent_items}
    day_offset = target.toordinal()
    protein_focus = [
        PROTEINS[(day_offset + i * 3) % len(PROTEINS)]
        for i in range(3)
    ]
    weekly_hot_tag_path, weekly_hot_tag_registry, weekly_hot_tag_errors = load_weekly_hot_tag_registry(target)
    out_dir = OUTPUT_DIR / target.isoformat()
    context = {
        "date": target.isoformat(),
        "weekday": WEEKDAYS[target.weekday()],
        "family": ["我（家庭主力）", "6岁女儿", "哺乳期老婆", "60岁母亲"],
        "budget_rmb": 40,
        "must_pair": "稀 + 干",
        "weekday_time_limit_minutes": 20,
        "emergency_plan_minutes": 5,
        "recommended_structure": first_available(STRUCTURES, used_structures, day_offset),
        "recommended_color_palette": first_available(PALETTES, used_palettes, day_offset),
        "protein_focus": protein_focus,
        "avoid_recent": [
            {
                "date": x.get("date"),
                "structure": x.get("strategy", {}).get("structure"),
                "soup_type": x.get("strategy", {}).get("soup_type"),
                "dry_main": x.get("strategy", {}).get("dry_main"),
                "color_palette": x.get("strategy", {}).get("color_palette"),
            }
            for x in recent_items
        ],
        "output_dir": str(out_dir),
        "manifest_path": str(out_dir / "content-package.json"),
        "delivery_markdown_path": str(delivery_markdown_path(target)),
        "history_file": str(HISTORY_FILE),
        "mcp_url": args.mcp_url,
        "weekly_hot_tag_registry_path": str(weekly_hot_tag_path),
        "weekly_hot_tag_status": "ready" if not weekly_hot_tag_errors else "missing_or_invalid",
        "weekly_hot_tag_errors": weekly_hot_tag_errors,
        "weekly_hot_tag_candidates": (
            weekly_hot_tag_registry.get("candidates", []) if weekly_hot_tag_registry and not weekly_hot_tag_errors else []
        ),
    }
    print(json.dumps(context, ensure_ascii=False, indent=2))


def chinese_len(text):
    return len("".join(str(text).split()))


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def image_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
        if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
            return struct.unpack(">II", head[16:24])
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                marker_start = f.read(1)
                if not marker_start:
                    break
                if marker_start != b"\xff":
                    continue
                marker = f.read(1)
                while marker == b"\xff":
                    marker = f.read(1)
                if marker in [b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"]:
                    f.read(3)
                    height, width = struct.unpack(">HH", f.read(4))
                    return width, height
                length_bytes = f.read(2)
                if len(length_bytes) != 2:
                    break
                length = struct.unpack(">H", length_bytes)[0]
                f.seek(length - 2, os.SEEK_CUR)
    return None


def validate_manifest_data(manifest):
    errors = []
    required = [
        "date",
        "weekday",
        "title",
        "content",
        "delivery_markdown_path",
        "images",
        "first_image_references",
        "tags",
        "tag_strategy",
        "interaction_question",
        "pinned_comment",
        "tomorrow_preview",
        "status",
        "should_publish",
        "is_original",
        "strategy",
    ]
    for key in required:
        if key not in manifest:
            errors.append(f"缺少必填字段: {key}")

    title = manifest.get("title", "")
    if not title or chinese_len(title) > 60:
        errors.append("title 必须非空，且压缩空白后不超过 60 个字符")
    elif not TITLE_PATTERN.fullmatch(title):
        errors.append("title 必须使用“跟着 Tiny.C 吃30天早餐｜第XX天｜四口之家20分钟…早餐”栏目格式")

    content = manifest.get("content", "")
    if not content or chinese_len(content) > 200:
        errors.append("content 必须非空，且压缩空白后不超过 200 个中文字符")
    if "#" in content:
        errors.append("content 不应包含 #话题；请使用 tags 字段")

    try:
        delivery_target = dt.date.fromisoformat(manifest.get("date", ""))
    except ValueError:
        delivery_target = None
    delivery_path = manifest.get("delivery_markdown_path")
    delivery_text = ""
    if not delivery_target:
        errors.append("无法校验交付 Markdown：date 必须是合法日期")
    elif not isinstance(delivery_path, str) or not pathlib.Path(delivery_path).is_absolute():
        errors.append("delivery_markdown_path 必须是绝对路径")
    else:
        expected_delivery_path = delivery_markdown_path(delivery_target)
        actual_delivery_path = pathlib.Path(delivery_path)
        if actual_delivery_path != expected_delivery_path:
            errors.append(f"交付 Markdown 必须使用目标日期路径: {expected_delivery_path}")
        elif not actual_delivery_path.exists():
            errors.append(f"缺少每日交付 Markdown: {actual_delivery_path}")
        else:
            delivery_text = actual_delivery_path.read_text(encoding="utf-8")
            for marker in ["## 小红书标题", "## 小红书正文", "## 流量标签", "## 互动问题", "## 置顶评论", "## 明天预告", "## 配图"]:
                if marker not in delivery_text:
                    errors.append(f"每日交付 Markdown 缺少章节: {marker}")
            for value in [title, content, manifest.get("interaction_question", ""), manifest.get("pinned_comment", ""), manifest.get("tomorrow_preview", "")]:
                if value and value not in delivery_text:
                    errors.append("每日交付 Markdown 未完整同步内容包字段")

    images = manifest.get("images", [])
    if not isinstance(images, list) or len(images) < 3:
        errors.append("images 必须至少 3 张，顺序为真实家庭餐桌首图、最终信息图、菜品制作过程图...")
    else:
        for image in images:
            if not str(image).startswith(("http://", "https://")):
                path = pathlib.Path(image)
                if not path.is_absolute():
                    errors.append(f"图片路径必须是绝对路径: {image}")
                elif not path.exists():
                    errors.append(f"图片路径不存在: {image}")
                else:
                    size = image_size(path)
                    expected = (TARGET_IMAGE_WIDTH, TARGET_IMAGE_HEIGHT)
                    if size and size != expected:
                        errors.append(f"图片尺寸必须为 {expected[0]}x{expected[1]}，当前为 {size[0]}x{size[1]}: {image}")
                    elif not size:
                        errors.append(f"无法识别图片尺寸，请确认是 PNG/JPEG: {image}")
                    if delivery_text and path.name not in delivery_text:
                        errors.append(f"每日交付 Markdown 缺少图片链接: {path.name}")

    image_plan = manifest.get("image_plan", [])
    if image_plan:
        plan_types = [item.get("type") for item in image_plan if isinstance(item, dict)]
        if plan_types[:2] != IMAGE_PLAN_TYPES:
            errors.append(f"image_plan 前 2 张 type 顺序必须为: {', '.join(IMAGE_PLAN_TYPES)}")
        if len(plan_types) < 3 or any(plan_type != "dish_process" for plan_type in plan_types[2:]):
            errors.append("image_plan 第 3 张及以后 type 必须全部为 dish_process")

    first_image_references = manifest.get("first_image_references", [])
    if (
        not isinstance(first_image_references, list)
        or not first_image_references
        or any(
            not (
                str(source).startswith(("http://", "https://"))
                or pathlib.Path(str(source)).is_absolute()
            )
            for source in first_image_references
        )
    ):
        errors.append("first_image_references 必须至少包含 1 个参考来源 URL 或本地绝对路径")

    tags = manifest.get("tags", [])
    if not isinstance(tags, list) or len(tags) != 10:
        errors.append("tags 必须恰好 10 个")
    else:
        if any(not str(tag).startswith("#") for tag in tags):
            errors.append("tags 中每个话题都必须以 # 开头，方便直接复制到小红书")
        if len(set(tags)) != 10:
            errors.append("tags 不得重复")
        if delivery_text:
            for tag in tags:
                if tag not in delivery_text:
                    errors.append(f"每日交付 Markdown 缺少标签: {tag}")

    tag_strategy = manifest.get("tag_strategy", {})
    if not isinstance(tag_strategy, dict):
        errors.append("tag_strategy 必须是对象")
    else:
        if tag_strategy.get("mode") != "random_topics" or tag_strategy.get("is_verified_trend") is not False:
            errors.append("tag_strategy 必须声明 random_topics 和 is_verified_trend=false")
        if delivery_target:
            path, registry, registry_errors = load_weekly_hot_tag_registry(delivery_target)
            errors.extend(registry_errors)
            if tag_strategy.get("weekly_hot_tag_registry_path") != str(path):
                errors.append("tag_strategy 台账路径必须对应目标日期")
            if not registry_errors and tags != [item["tag"] for item in registry["candidates"]]:
                errors.append("tags 必须与台账的 10 个随机话题及顺序一致")

    interaction_question = manifest.get("interaction_question", "")
    for option in ["A.", "B.", "C.", "D."]:
        if option not in interaction_question:
            errors.append(f"interaction_question 必须包含选项 {option}")
    if "评论区留下你专属版" not in interaction_question:
        errors.append("interaction_question 的 D 选项必须是“评论区留下你专属版”")

    if not str(manifest.get("pinned_comment", "")).strip():
        errors.append("pinned_comment 必须非空")

    if not str(manifest.get("tomorrow_preview", "")).strip():
        errors.append("tomorrow_preview 必须非空")

    if manifest.get("status") != "ready_for_review":
        errors.append("status 必须是 ready_for_review")
    if manifest.get("should_publish") is not False:
        errors.append("should_publish 必须是 false，内容包仅供人工确认")
    if manifest.get("is_original") is not True:
        errors.append("is_original 必须是 true")

    strategy = manifest.get("strategy", {})
    for key in ["structure", "soup_type", "dry_main", "color_palette", "protein_focus"]:
        if not strategy.get(key):
            errors.append(f"strategy.{key} 是必填项")

    return errors


def command_validate(args):
    manifest = load_manifest(args.manifest)
    errors = validate_manifest_data(manifest)
    if errors:
        for error in errors:
            print(f"错误: {error}", file=sys.stderr)
        return 1
    print("通过: manifest 校验成功")
    return 0


def command_record(args):
    manifest = load_manifest(args.manifest)
    errors = validate_manifest_data(manifest)
    if errors:
        for error in errors:
            print(f"错误: {error}", file=sys.stderr)
        return 1

    history = load_history()
    history = [x for x in history if x.get("date") != manifest.get("date")]
    history.append(
        {
            "date": manifest.get("date"),
            "weekday": manifest.get("weekday"),
            "title": manifest.get("title"),
            "tags": manifest.get("tags"),
            "images": manifest.get("images"),
            "visibility": manifest.get("visibility", "仅自己可见"),
            "published": bool(args.published),
            "strategy": manifest.get("strategy", {}),
            "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_history(history)
    print(f"通过: 已记录 {manifest.get('date')} 到 {HISTORY_FILE}")
    return 0


def prepare_registry_input(path, target):
    registry = load_manifest(path)
    coverage_start, coverage_end = trend_window(target)
    registry = dict(registry)
    registry["target_date"] = target.isoformat()
    registry["coverage_start"] = coverage_start.isoformat()
    registry["coverage_end"] = coverage_end.isoformat()
    registry["evidence_schema_version"] = 2
    return registry


def command_fetch_weekly_hot_tags(args):
    target = parse_date(args.date)
    rng = random.SystemRandom()
    candidates = [{"tag": rng.choice(tags), "category": category} for category, tags in TOPIC_POOLS.items()]
    selected = {item["tag"] for item in candidates}
    remaining = [{"tag": tag, "category": category} for category, tags in TOPIC_POOLS.items() for tag in tags if tag not in selected]
    candidates.extend(rng.sample(remaining, 4))
    rng.shuffle(candidates)
    registry = {
        "target_date": target.isoformat(),
        "collected_at": now_shanghai().isoformat(),
        "mode": "random_topics",
        "is_verified_trend": False,
        "candidates": candidates,
    }
    errors = validate_weekly_hot_tag_registry(registry, target)
    if errors:
        print("错误: " + "; ".join(errors), file=sys.stderr)
        return 1
    path = write_weekly_hot_tag_registry(registry, target)
    print(f"通过: 已保存 10 个随机话题到 {path}（非已验证热词）")
    return 0


def command_save_weekly_hot_tags(args):
    target = parse_date(args.date)
    try:
        registry = prepare_registry_input(args.input, target)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"错误: 无法读取本周热词输入文件: {error}", file=sys.stderr)
        return 1

    errors = validate_weekly_hot_tag_registry(registry, target)
    if errors:
        for error in errors:
            print(f"错误: {error}", file=sys.stderr)
        return 1

    path = write_weekly_hot_tag_registry(registry, target)
    print(f"通过: 已保存 {target.isoformat()} 本周热词台账到 {path}")
    return 0


def rpc(url, payload, session_id=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body), resp.headers.get("Mcp-Session-Id")


def command_publish(args):
    manifest = load_manifest(args.manifest)
    errors = validate_manifest_data(manifest)
    if errors:
        for error in errors:
            print(f"错误: {error}", file=sys.stderr)
        return 1

    init_payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "breakfast-xiaohongshu", "version": "1.0.0"},
        },
        "id": 1,
    }
    init_result, session_id = rpc(args.mcp_url, init_payload)
    if "error" in init_result:
        print(json.dumps(init_result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    arguments = {
        "title": manifest["title"],
        "content": manifest["content"],
        "images": manifest["images"],
        "tags": manifest.get("tags", []),
        "visibility": manifest.get("visibility", "仅自己可见"),
        "is_original": bool(manifest.get("is_original", True)),
    }
    if manifest.get("schedule_at"):
        arguments["schedule_at"] = manifest["schedule_at"]
    if manifest.get("products"):
        arguments["products"] = manifest["products"]

    publish_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "publish_content", "arguments": arguments},
        "id": 2,
    }
    result, _ = rpc(args.mcp_url, publish_payload, session_id=session_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if "error" not in result else 1


def command_launchd_template(args):
    command = args.command
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.codex.breakfast-xiaohongshu</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>{command}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>18</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{STATE_DIR}/daily.log</string>
  <key>StandardErrorPath</key>
  <string>{STATE_DIR}/daily.err</string>
</dict>
</plist>"""
    print(plist)


def build_parser():
    parser = argparse.ArgumentParser(description="小红书早餐 Skill 辅助脚本")
    sub = parser.add_subparsers(dest="command", required=True)

    context = sub.add_parser("context", help="输出明日内容生成上下文")
    context.add_argument("--date", help="目标日期，默认明天")
    context.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    context.set_defaults(func=command_context)

    validate = sub.add_parser("validate-manifest", help="发布前校验 manifest")
    validate.add_argument("manifest")
    validate.set_defaults(func=command_validate)

    record = sub.add_parser("record", help="把已生成或已发布的 manifest 记录到历史")
    record.add_argument("manifest")
    record.add_argument("--published", action="store_true")
    record.set_defaults(func=command_record)

    fetch_weekly_hot_tags = sub.add_parser("generate-random-tags", aliases=["fetch-weekly-hot-tags"], help="离线随机生成六类主题的 10 个话题")
    fetch_weekly_hot_tags.add_argument("--date", required=True, help="内容包目标日期")
    fetch_weekly_hot_tags.set_defaults(func=command_fetch_weekly_hot_tags)

    save_weekly_hot_tags = sub.add_parser("save-weekly-hot-tags", help="保存带来源证据的本周热词台账")
    save_weekly_hot_tags.add_argument("--date", required=True, help="内容包目标日期")
    save_weekly_hot_tags.add_argument("--input", required=True, help="热词台账输入 JSON 路径")
    save_weekly_hot_tags.set_defaults(func=command_save_weekly_hot_tags)

    publish = sub.add_parser("publish", help="通过 xiaohongshu-mcp 发布 manifest")
    publish.add_argument("manifest")
    publish.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    publish.set_defaults(func=command_publish)

    launchd = sub.add_parser("launchd-template", help="输出每天 18:00 的 LaunchAgent 模板")
    launchd.add_argument("--command", required=True)
    launchd.set_defaults(func=command_launchd_template)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
