import json
import os
import sys
import urllib.request

NAMING_PER_DAY = 3
OE_PER_DAY = 5
NAMING_FILE = "naming_roots.json"
OE_FILE = "old_english_vocab.json"
PROGRESS_FILE = "progress.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_next(items, start_idx, count):
    total = len(items)
    picked = []
    idx = start_idx
    for _ in range(count):
        picked.append(items[idx % total])
        idx += 1
    return picked, idx % total, idx // total > start_idx // total


def format_naming(w):
    lines = [f"🔸 {w['latin']} ({w['pos']}) — {w['thai']}"]
    if w.get("root"):
        lines.append(f"   ราก: {w['root']}")
    if w.get("naming_examples"):
        lines.append("   ตั้งชื่อ/พบใน:")
        for ex in w["naming_examples"]:
            lines.append(f"     • {ex}")
    if w.get("old_english"):
        lines.append(f"   อังกฤษโบราณ: {w['old_english']}")
    return "\n".join(lines)


def format_oe(w):
    lines = [f"🔹 {w['old_english']} ({w['pos']}) — {w['thai']}"]
    if w.get("modern_descendant"):
        lines.append(f"   ลูกหลานในปัจจุบัน: {w['modern_descendant']}")
    if w.get("example"):
        ex_line = f"   📖 {w['example']}"
        if w.get("example_thai"):
            ex_line += f" ({w['example_thai']})"
        lines.append(ex_line)
    return "\n".join(lines)


def main():
    ntfy_topic = os.environ.get("NTFY_TOPIC")
    if not ntfy_topic:
        print("ERROR: ไม่พบ NTFY_TOPIC ใน environment variable", file=sys.stderr)
        sys.exit(1)

    naming_vocab = load_json(NAMING_FILE, [])
    oe_vocab = load_json(OE_FILE, [])
    if not naming_vocab or not oe_vocab:
        print("ERROR: ไม่พบคำศัพท์ในไฟล์ naming_roots.json หรือ old_english_vocab.json", file=sys.stderr)
        sys.exit(1)

    progress = load_json(
        PROGRESS_FILE,
        {"naming_index": 0, "naming_round": 1, "oe_index": 0, "oe_round": 1},
    )

    naming_today, new_naming_idx, naming_wrapped = pick_next(
        naming_vocab, progress["naming_index"], NAMING_PER_DAY
    )
    oe_today, new_oe_idx, oe_wrapped = pick_next(
        oe_vocab, progress["oe_index"], OE_PER_DAY
    )

    progress["naming_index"] = new_naming_idx
    if naming_wrapped:
        progress["naming_round"] += 1
    progress["oe_index"] = new_oe_idx
    if oe_wrapped:
        progress["oe_round"] += 1

    naming_section = "📛 รากศัพท์ลาตินในการตั้งชื่อ\n\n" + "\n\n".join(
        format_naming(w) for w in naming_today
    )
    oe_section = "📜 คำอังกฤษโบราณ (Old English)\n\n" + "\n\n".join(
        format_oe(w) for w in oe_today
    )
    message = naming_section + "\n\n" + ("─" * 20) + "\n\n" + oe_section
    title = f"ลาติน x อังกฤษโบราณ (รอบ {progress['naming_round']}/{progress['oe_round']})"

    url = f"https://ntfy.sh/{ntfy_topic}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Tags": "scroll",
            "Priority": "default",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print("ส่งแจ้งเตือนสำเร็จ, status:", resp.status)

    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()
