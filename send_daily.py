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


def pick_words(vocab, key_field, cursor, priority_cursor, per_day):
    """
    เลือกคำของวันนี้ โดยให้สิทธิ์ "คำใหม่ที่ยังไม่เคยถูกส่งเลยสักครั้ง" ก่อนเสมอ
    (priority_cursor ชี้ตำแหน่งคำถัดไปที่ยังไม่เคยถูกจัดลำดับความสำคัญ)
    ถ้าคำใหม่ไม่พอเติมโควต้าต่อวัน จะเติมส่วนที่เหลือด้วยการวนคิวปกติ (round-robin)
    จากคำทั้งหมดในคลัง (รวมคำเก่าที่เคยส่งไปแล้ว)

    คืนค่า: (คำที่เลือกวันนี้, cursor ใหม่, priority_cursor ใหม่, เลขรอบสำหรับแสดงผล)
    """
    total = len(vocab)
    if total == 0:
        return [], cursor, priority_cursor, 1

    picked = []
    picked_keys = set()

    # 1) คำใหม่ก่อนเสมอ
    new_available = max(0, total - priority_cursor)
    take_new = min(new_available, per_day)
    for i in range(take_new):
        item = vocab[priority_cursor + i]
        picked.append(item)
        picked_keys.add(item[key_field])
    priority_cursor += take_new

    # 2) เติมที่เหลือด้วยคิวปกติ ข้ามคำที่เพิ่งถูกเลือกไปแล้วในข้อ 1 (กันคำซ้ำในแจ้งเตือนเดียวกัน)
    remaining = per_day - take_new
    attempts = 0
    while remaining > 0 and attempts < total * 2:
        item = vocab[cursor % total]
        cursor += 1
        attempts += 1
        if item[key_field] in picked_keys:
            continue
        picked.append(item)
        picked_keys.add(item[key_field])
        remaining -= 1

    round_number = (cursor // total) + 1
    return picked, cursor, priority_cursor, round_number


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

    progress = load_json(PROGRESS_FILE, {})

    # โครงสร้างใหม่: cursor (วนคิวปกติ) + priority_cursor (ชี้คำใหม่ที่ยังไม่เคยถูกจัดสรร)
    # รองรับการอัปเกรดจากไฟล์ progress.json แบบเก่า (naming_index/oe_index) ให้อัตโนมัติ
    naming_cursor = progress.get("naming_cursor", progress.get("naming_index", 0))
    naming_priority_cursor = progress.get("naming_priority_cursor", len(naming_vocab))
    oe_cursor = progress.get("oe_cursor", progress.get("oe_index", 0))
    oe_priority_cursor = progress.get("oe_priority_cursor", len(oe_vocab))

    naming_today, naming_cursor, naming_priority_cursor, naming_round = pick_words(
        naming_vocab, "latin", naming_cursor, naming_priority_cursor, NAMING_PER_DAY
    )
    oe_today, oe_cursor, oe_priority_cursor, oe_round = pick_words(
        oe_vocab, "old_english", oe_cursor, oe_priority_cursor, OE_PER_DAY
    )

    new_progress = {
        "naming_cursor": naming_cursor,
        "naming_priority_cursor": naming_priority_cursor,
        "oe_cursor": oe_cursor,
        "oe_priority_cursor": oe_priority_cursor,
    }

    naming_section = "📛 รากศัพท์ลาตินในการตั้งชื่อ\n\n" + "\n\n".join(
        format_naming(w) for w in naming_today
    )
    oe_section = "📜 คำอังกฤษโบราณ (Old English)\n\n" + "\n\n".join(
        format_oe(w) for w in oe_today
    )
    message = naming_section + "\n\n" + ("─" * 20) + "\n\n" + oe_section
    title = f"ลาติน x อังกฤษโบราณ (รอบ {naming_round}/{oe_round})"

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

    save_json(PROGRESS_FILE, new_progress)


if __name__ == "__main__":
    main()
