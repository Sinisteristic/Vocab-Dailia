import json
import os
import sys
import urllib.request

ROOTS_PER_DAY = int(os.environ.get("ROOTS_PER_DAY", os.environ.get("NAMING_PER_DAY", "2")))
ARCHAIC_PER_DAY = int(os.environ.get("ARCHAIC_PER_DAY", os.environ.get("OE_PER_DAY", "4")))
ROOTS_FILE = "roots_voc.json"
ARCHAIC_FILE = "archaic_voc.json"
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
    ถ้าคำใหม่ไม่พอเติมโควต้าต่อวัน จะเติมส่วนที่เหลือด้วยการวนคิวปกติ (round-robin)
    """
    total = len(vocab)
    if total == 0:
        return [], cursor, priority_cursor, 1

    picked = []
    picked_keys = set()

    new_available = max(0, total - priority_cursor)
    take_new = min(new_available, per_day)
    for i in range(take_new):
        item = vocab[priority_cursor + i]
        picked.append(item)
        picked_keys.add(item[key_field])
    priority_cursor += take_new

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


def format_roots(w):
    # รองรับ schema ใหม่ (name/components/explanation_thai) เป็นหลัก
    # และยังรองรับ schema เก่าที่สุด (latin/root/naming_examples) เผื่อมีของเดิมหลงเหลืออยู่
    if "name" in w:
        lines = [f"🔸 {w['name']} — {w.get('thai_meaning', '')}"]
        for comp in w.get("components", []):
            lines.append(f"   • {comp.get('part', '')} ({comp.get('language', '')}) = {comp.get('meaning_thai', '')}")
        if w.get("explanation_thai"):
            lines.append(f"   💡 {w['explanation_thai']}")
        return "\n".join(lines)
    else:
        lines = [f"🔸 {w.get('latin', '')} ({w.get('pos', '')}) — {w.get('thai', '')}"]
        if w.get("root"):
            lines.append(f"   ราก: {w['root']}")
        if w.get("naming_examples"):
            lines.append("   ตั้งชื่อ/พบใน:")
            for ex in w["naming_examples"]:
                lines.append(f"     • {ex}")
        return "\n".join(lines)


def format_archaic(w):
    # รองรับ schema ใหม่ (word/is_from_source/modern_replacement) เป็นหลัก
    # และยังรองรับ schema เก่า (old_english/modern_descendant) เผื่อมีของเดิมหลงเหลืออยู่
    if "word" in w:
        tag = "📖 พบในเนื้อหาจริง" if w.get("is_from_source") else "✍️ อังกฤษโบราณ (สำรอง)"
        lines = [f"🔹 {w['word']} ({w.get('pos', '')}) — {w.get('thai', '')}  [{tag}]"]
        if w.get("modern_replacement"):
            lines.append(f"   ใช้แทนปัจจุบันด้วย: {w['modern_replacement']}")
        if w.get("example"):
            ex_line = f"   {w['example']}"
            if w.get("example_thai"):
                ex_line += f" ({w['example_thai']})"
            lines.append(ex_line)
        return "\n".join(lines)
    else:
        lines = [f"🔹 {w.get('old_english', '')} ({w.get('pos', '')}) — {w.get('thai', '')}"]
        if w.get("modern_descendant"):
            lines.append(f"   ลูกหลานในปัจจุบัน: {w['modern_descendant']}")
        if w.get("example"):
            ex_line = f"   {w['example']}"
            if w.get("example_thai"):
                ex_line += f" ({w['example_thai']})"
            lines.append(ex_line)
        return "\n".join(lines)


def main():
    ntfy_topic = os.environ.get("NTFY_TOPIC")
    if not ntfy_topic:
        print("ERROR: ไม่พบ NTFY_TOPIC ใน environment variable", file=sys.stderr)
        sys.exit(1)

    roots_vocab = load_json(ROOTS_FILE, [])
    archaic_vocab = load_json(ARCHAIC_FILE, [])
    if not roots_vocab or not archaic_vocab:
        print("ERROR: ไม่พบคำศัพท์ในไฟล์ roots_voc.json หรือ archaic_voc.json", file=sys.stderr)
        sys.exit(1)

    progress = load_json(PROGRESS_FILE, {})

    # รองรับการอัปเกรดจาก progress.json รูปแบบเก่า (naming_*/oe_*) ให้อัตโนมัติ
    roots_cursor = progress.get("roots_cursor", progress.get("naming_cursor", progress.get("naming_index", 0)))
    roots_priority_cursor = progress.get(
        "roots_priority_cursor", progress.get("naming_priority_cursor", len(roots_vocab))
    )
    archaic_cursor = progress.get("archaic_cursor", progress.get("oe_cursor", progress.get("oe_index", 0)))
    archaic_priority_cursor = progress.get(
        "archaic_priority_cursor", progress.get("oe_priority_cursor", len(archaic_vocab))
    )

    # key field ของคำแต่ละรายการ: schema ใหม่ใช้ "name"/"word", เผื่อของเก่าหลงเหลือใช้ "latin"/"old_english"
    roots_key = "name" if (roots_vocab and "name" in roots_vocab[0]) else "latin"
    archaic_key = "word" if (archaic_vocab and "word" in archaic_vocab[0]) else "old_english"

    roots_today, roots_cursor, roots_priority_cursor, roots_round = pick_words(
        roots_vocab, roots_key, roots_cursor, roots_priority_cursor, ROOTS_PER_DAY
    )
    archaic_today, archaic_cursor, archaic_priority_cursor, archaic_round = pick_words(
        archaic_vocab, archaic_key, archaic_cursor, archaic_priority_cursor, ARCHAIC_PER_DAY
    )

    new_progress = {
        "roots_cursor": roots_cursor,
        "roots_priority_cursor": roots_priority_cursor,
        "archaic_cursor": archaic_cursor,
        "archaic_priority_cursor": archaic_priority_cursor,
    }

    roots_section = "📛 ที่มาของชื่อ (นิรุกติศาสตร์)\n\n" + "\n\n".join(
        format_roots(w) for w in roots_today
    )
    archaic_section = "📜 คำโบราณ (Archaic Words)\n\n" + "\n\n".join(
        format_archaic(w) for w in archaic_today
    )
    message = roots_section + "\n\n" + ("─" * 20) + "\n\n" + archaic_section
    title = f"ที่มาชื่อ x คำโบราณ (รอบ {roots_round}/{archaic_round})"

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
