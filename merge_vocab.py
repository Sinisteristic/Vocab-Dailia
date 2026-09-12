import json
import os
from datetime import datetime, timezone

FILES = {"roots_voc": "roots_voc.json", "archaic_voc": "archaic_voc.json"}
KEY_FIELD = {"roots_voc": "name", "archaic_voc": "word"}
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    existing = load_json(path, [])
    existing_key_set = {e[key_field] for e in existing}

    added = 0
    for item in new_items:
        if item.get(key_field) not in existing_key_set:
            item["date_added"] = today  # เพิ่มวันที่ ไว้ใช้กรองใน Google Sheet
            existing.append(item)
            existing_key_set.add(item.get(key_field))
            added += 1

    save_json(path, existing)
    print(f"merge แล้ว: เพิ่ม {added} รายการใหม่ (รวมทั้งหมด {len(existing)}) ในไฟล์ {path}")


if __name__ == "__main__":
    main()
