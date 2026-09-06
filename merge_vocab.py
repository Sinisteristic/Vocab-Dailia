import json
import os

FILES = {"naming_roots": "naming_roots.json", "old_english": "old_english_vocab.json"}
KEY_FIELD = {"naming_roots": "latin", "old_english": "old_english"}
PENDING_FILE = "pending_new_items.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    pending = load_json(PENDING_FILE, None)
    if pending is None:
        print("ไม่พบ pending_new_items.json ไม่มีอะไรต้อง merge")
        return

    target = pending["target"]
    new_items = pending["items"]
    path = FILES[target]
    key_field = KEY_FIELD[target]

    # โหลด "เนื้อหาล่าสุดของไฟล์หลัก" ใหม่ทุกครั้งที่ merge (สำคัญ: ต้องรันหลัง git reset ไป origin/main แล้วเท่านั้น)
    existing = load_json(path, [])
    existing_key_set = {e[key_field] for e in existing}

    added = 0
    for item in new_items:
        if item.get(key_field) not in existing_key_set:
            existing.append(item)
            existing_key_set.add(item.get(key_field))
            added += 1

    save_json(path, existing)
    print(f"merge แล้ว: เพิ่ม {added} รายการใหม่ (รวมทั้งหมด {len(existing)}) ในไฟล์ {path}")
    # หมายเหตุ: ไม่ลบ pending_new_items.json ที่นี่โดยตั้งใจ — ถ้า push ล้มเหลวและต้อง retry
    # workflow จะ reset ไฟล์หลักกลับไปที่ origin/main แล้วเรียก merge ใหม่ด้วย pending ไฟล์เดิมนี้อีกครั้ง
    # ไฟล์นี้เป็นไฟล์ที่ไม่ได้ commit เข้า git อยู่แล้ว จะหายไปเองเมื่อ job จบ (fresh checkout ทุกครั้ง)


if __name__ == "__main__":
    main()
