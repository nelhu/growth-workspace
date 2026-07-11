#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import struct
import sys
import urllib.request
from urllib.parse import urlparse


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
TREND_SOURCE_TYPES = {"topic_rank", "rising_rank", "industry_rank", "trend_report"}
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


def validate_weekly_hot_tag_registry(registry, target):
    errors = []
    if not isinstance(registry, dict):
        return ["本周热词台账必须是 JSON 对象"]

    coverage_start, coverage_end = trend_window(target)
    if registry.get("target_date") != target.isoformat():
        errors.append(f"本周热词台账 target_date 必须是 {target.isoformat()}")
    if registry.get("coverage_start") != coverage_start.isoformat():
        errors.append(f"本周热词台账 coverage_start 必须是 {coverage_start.isoformat()}")
    if registry.get("coverage_end") != coverage_end.isoformat():
        errors.append(f"本周热词台账 coverage_end 必须是 {coverage_end.isoformat()}")

    try:
        collected_date = parse_observed_date(registry.get("collected_at"))
        if not coverage_start <= collected_date <= coverage_end:
            errors.append("本周热词台账 collected_at 必须落在目标日期最近 7 天内")
    except ValueError:
        errors.append("本周热词台账缺少合法的 collected_at")

    candidates = registry.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 5:
        errors.append("本周热词台账 candidates 至少包含 5 个候选标签")
        return errors

    seen_tags = set()
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            errors.append(f"本周热词台账第 {index} 项必须是对象")
            continue
        tag = candidate.get("tag")
        if not isinstance(tag, str) or not tag.startswith("#") or len(tag) <= 1:
            errors.append(f"本周热词台账第 {index} 项 tag 必须以 # 开头")
        elif tag in seen_tags:
            errors.append(f"本周热词台账存在重复标签: {tag}")
        else:
            seen_tags.add(tag)
        source_name = candidate.get("source_name")
        if source_name not in TREND_SOURCE_HOSTS:
            errors.append(f"本周热词台账第 {index} 项 source_name 必须是千瓜数据或新榜")
        elif not source_url_matches(source_name, candidate.get("source_url")):
            errors.append(f"本周热词台账第 {index} 项 source_url 必须属于 {source_name}")
        if candidate.get("source_type") not in TREND_SOURCE_TYPES:
            errors.append(f"本周热词台账第 {index} 项 source_type 必须是榜单或趋势报告类型")
        if not isinstance(candidate.get("rank"), int) or candidate["rank"] < 1:
            errors.append(f"本周热词台账第 {index} 项 rank 必须是正整数")
        if not isinstance(candidate.get("rank_context"), str) or not candidate["rank_context"].strip():
            errors.append(f"本周热词台账第 {index} 项缺少 rank_context")
        if not isinstance(candidate.get("relevance"), str) or not candidate["relevance"].strip():
            errors.append(f"本周热词台账第 {index} 项缺少 relevance")
        try:
            observed_date = parse_observed_date(candidate.get("observed_at"))
            if not coverage_start <= observed_date <= coverage_end:
                errors.append(f"本周热词台账第 {index} 项 observed_at 不在最近 7 天窗口内")
        except ValueError:
            errors.append(f"本周热词台账第 {index} 项缺少合法的 observed_at")
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
        if tags[:5] != FIXED_VERTICAL_TAGS:
            errors.append(f"tags 前 5 个必须固定为: {', '.join(FIXED_VERTICAL_TAGS)}")
        weekly_hot_tags = tags[5:]
        if any(not str(tag).strip() for tag in weekly_hot_tags):
            errors.append("tags 后 5 个本周热词不能为空")
        elif delivery_text:
            for tag in tags:
                if tag not in delivery_text:
                    errors.append(f"每日交付 Markdown 缺少标签: {tag}")

    tag_strategy = manifest.get("tag_strategy", {})
    if not isinstance(tag_strategy, dict):
        errors.append("tag_strategy 必须是对象")
    else:
        fixed_tags = tag_strategy.get("fixed_vertical_tags")
        weekly_hot_tags = tag_strategy.get("weekly_hot_tags")
        if fixed_tags != FIXED_VERTICAL_TAGS:
            errors.append("tag_strategy.fixed_vertical_tags 必须与 tags 前 5 个固定垂直标签一致")
        if weekly_hot_tags != tags[5:]:
            errors.append("tag_strategy.weekly_hot_tags 必须与 tags 后 5 个本周热词完全一致")

        try:
            target = dt.date.fromisoformat(manifest.get("date", ""))
        except ValueError:
            target = None
        registry_path = tag_strategy.get("weekly_hot_tag_registry_path")
        if not target:
            errors.append("无法校验本周热词台账：date 必须是合法日期")
        elif not isinstance(registry_path, str) or not pathlib.Path(registry_path).is_absolute():
            errors.append("tag_strategy.weekly_hot_tag_registry_path 必须是绝对路径")
        else:
            expected_registry_path = trend_registry_path(target)
            actual_registry_path = pathlib.Path(registry_path)
            if actual_registry_path != expected_registry_path:
                errors.append(f"本周热词台账必须使用目标日期路径: {expected_registry_path}")
            _, registry, registry_errors = load_weekly_hot_tag_registry(target)
            if registry_errors:
                errors.extend(registry_errors)
            else:
                evidence = tag_strategy.get("weekly_hot_tag_evidence")
                if not isinstance(evidence, list) or len(evidence) != 5:
                    errors.append("tag_strategy.weekly_hot_tag_evidence 必须包含 5 条来源证据")
                else:
                    candidate_keys = {
                        (
                            item.get("tag"),
                            item.get("source_name"),
                            item.get("source_url"),
                            item.get("source_type"),
                            item.get("rank_context"),
                            item.get("observed_at"),
                            item.get("rank"),
                        )
                        for item in registry["candidates"]
                    }
                    for index, item in enumerate(evidence):
                        if not isinstance(item, dict):
                            errors.append(f"本周热词第 {index + 1} 条来源证据必须是对象")
                            continue
                        if item.get("tag") != tags[index + 5]:
                            errors.append(f"本周热词第 {index + 1} 条来源证据必须与 tags 顺序一致")
                        key = (
                            item.get("tag"),
                            item.get("source_name"),
                            item.get("source_url"),
                            item.get("source_type"),
                            item.get("rank_context"),
                            item.get("observed_at"),
                            item.get("rank"),
                        )
                        if key not in candidate_keys:
                            errors.append(f"本周热词第 {index + 1} 条来源证据不在台账候选中")

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


def command_save_weekly_hot_tags(args):
    target = parse_date(args.date)
    try:
        registry = load_manifest(args.input)
    except (OSError, json.JSONDecodeError) as error:
        print(f"错误: 无法读取本周热词输入文件: {error}", file=sys.stderr)
        return 1

    coverage_start, coverage_end = trend_window(target)
    registry = dict(registry)
    registry["target_date"] = target.isoformat()
    registry["coverage_start"] = coverage_start.isoformat()
    registry["coverage_end"] = coverage_end.isoformat()
    errors = validate_weekly_hot_tag_registry(registry, target)
    if errors:
        for error in errors:
            print(f"错误: {error}", file=sys.stderr)
        return 1

    path = trend_registry_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
        f.write("\n")
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
