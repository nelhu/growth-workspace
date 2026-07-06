#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import struct
import sys
import urllib.request


STATE_DIR = pathlib.Path.home() / ".breakfast-xiaohongshu"
HISTORY_FILE = STATE_DIR / "history.json"
OUTPUT_DIR = STATE_DIR / "out"
DEFAULT_MCP_URL = "http://127.0.0.1:18060/mcp"
TARGET_IMAGE_WIDTH = 853
TARGET_IMAGE_HEIGHT = 1280
FIXED_VERTICAL_TAGS = ["#早餐", "#儿童早餐", "#家庭早餐", "#长高早餐", "#四口之家早餐"]
IMAGE_PLAN_TYPES = [
    "real_breakfast_grid",
    "final_infographic",
    "shopping_and_prep",
    "tomorrow_preview",
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
        "manifest_path": str(out_dir / "manifest.json"),
        "history_file": str(HISTORY_FILE),
        "mcp_url": args.mcp_url,
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
        "images",
        "real_image_sources",
        "tags",
        "interaction_question",
        "pinned_comment",
        "tomorrow_preview",
        "strategy",
    ]
    for key in required:
        if key not in manifest:
            errors.append(f"缺少必填字段: {key}")

    title = manifest.get("title", "")
    if not title or chinese_len(title) > 60:
        errors.append("title 必须非空，且压缩空白后不超过 60 个字符")

    content = manifest.get("content", "")
    if not content or chinese_len(content) > 200:
        errors.append("content 必须非空，且压缩空白后不超过 200 个中文字符")
    if "#" in content:
        errors.append("content 不应包含 #话题；请使用 tags 字段")

    images = manifest.get("images", [])
    if not isinstance(images, list) or len(images) != 4:
        errors.append("images 必须是 4 张图片，顺序为真实成品宫格、最终信息图、购物备餐图、明天预告图")
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

    image_plan = manifest.get("image_plan", [])
    if image_plan:
        plan_types = [item.get("type") for item in image_plan if isinstance(item, dict)]
        if plan_types != IMAGE_PLAN_TYPES:
            errors.append(f"image_plan.type 顺序必须为: {', '.join(IMAGE_PLAN_TYPES)}")

    real_image_sources = manifest.get("real_image_sources", [])
    if (
        not isinstance(real_image_sources, list)
        or not real_image_sources
        or any(not str(source).startswith(("http://", "https://")) for source in real_image_sources)
    ):
        errors.append("real_image_sources 必须至少包含 1 个网上真实图片来源 URL")

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

    tag_strategy = manifest.get("tag_strategy", {})
    if tag_strategy:
        fixed_tags = tag_strategy.get("fixed_vertical_tags")
        weekly_hot_tags = tag_strategy.get("weekly_hot_tags")
        if fixed_tags != FIXED_VERTICAL_TAGS:
            errors.append("tag_strategy.fixed_vertical_tags 必须与 tags 前 5 个固定垂直标签一致")
        if not isinstance(weekly_hot_tags, list) or len(weekly_hot_tags) != 5:
            errors.append("tag_strategy.weekly_hot_tags 必须包含 5 个本周热词")

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
    <integer>20</integer>
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

    publish = sub.add_parser("publish", help="通过 xiaohongshu-mcp 发布 manifest")
    publish.add_argument("manifest")
    publish.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    publish.set_defaults(func=command_publish)

    launchd = sub.add_parser("launchd-template", help="输出每天 20:00 的 LaunchAgent 模板")
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
