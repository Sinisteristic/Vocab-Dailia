import json
import os
import re
import sys
import urllib.request

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

PROMPTS = {
    "naming_roots": """จากข้อความอ้างอิงด้านล่างนี้ ช่วยดึงคำ/รากศัพท์ภาษาลาติน {count} คำที่น่าสนใจ
(ควรเป็นรากที่ถูกนำไปใช้ตั้งชื่อคน/สถานที่/ตัวละคร/แบรนด์ในโลกจริงหรือในสื่อต่างๆ)
ห้ามเลือกคำที่ซ้ำกับรายการนี้: {existing}

ตอบเป็น JSON array เท่านั้น ไม่ต้องมีคำอธิบายอื่น ไม่ต้องมี ```json ครอบ ตามฟอร์แมตนี้เป๊ะๆ:
[{{"latin": "คำ+รูปพจนานุกรม", "pos": "ชนิดคำ", "root": "ราก", "thai": "คำแปลไทย", "naming_examples": ["ตัวอย่าง 1 พร้อมอธิบายสั้นๆ", "ตัวอย่าง 2"], "old_english": "คำอังกฤษโบราณที่เกี่ยวข้องพร้อมอธิบาย หรือ 'ไม่มี' ถ้าไม่เกี่ยวข้องจริงๆ"}}]

ข้อความอ้างอิง:
---
{source}
---""",
    "old_english": """จากข้อความอ้างอิงด้านล่างนี้ (หรือถ้าไม่มีคำอังกฤษโบราณปรากฏตรงๆ ให้แต่งคำ/ประโยคอังกฤษโบราณที่เกี่ยวข้องกับธีมของข้อความ)
ช่วยสร้างคำศัพท์ภาษาอังกฤษโบราณ (Old English) {count} คำ
ห้ามเลือกคำที่ซ้ำกับรายการนี้: {existing}

ตอบเป็น JSON array เท่านั้น ไม่ต้องมีคำอธิบายอื่น ไม่ต้องมี ```json ครอบ ตามฟอร์แมตนี้เป๊ะๆ:
[{{"old_english": "คำ", "pos": "ชนิดคำ", "thai": "คำแปลไทย", "modern_descendant": "คำอังกฤษปัจจุบันที่สืบทอดมา พร้อมอธิบายสั้นๆ", "example": "ประโยคภาษาอังกฤษโบราณ", "example_thai": "คำแปลประโยคนั้น"}}]

ข้อความอ้างอิง:
---
{source}
---""",
}

FILES = {
    "naming_roots": "naming_roots.json",
    "old_english": "old_english_vocab.json",
}

KEY_FIELD = {
    "naming_roots": "latin",
    "old_english": "old_english",
}


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def call_claude(api_key, prompt):
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = data["content"][0]["text"]
    # กันเผื่อ Claude ตอบมาพร้อม ```json ครอบ
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    target = os.environ.get("TARGET", "naming_roots")
    source = os.environ.get("SOURCE_TEXT", "")
    count = os.environ.get("COUNT", "3" if target == "naming_roots" else "5")

    if not api_key:
        print("ERROR: ไม่พบ ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)
    if target not in FILES:
        print("ERROR: target ต้องเป็น naming_roots หรือ old_english", file=sys.stderr)
        sys.exit(1)
    if not source.strip():
        print("ERROR: ไม่ได้ใส่ SOURCE_TEXT", file=sys.stderr)
        sys.exit(1)

    path = FILES[target]
    key_field = KEY_FIELD[target]
    existing = load_json(path, [])
    existing_keys = ", ".join(item[key_field] for item in existing) or "(ยังไม่มี)"

    prompt = PROMPTS[target].format(count=count, existing=existing_keys, source=source)

    print(f"กำลังขอคำศัพท์ {count} คำ ({target}) จาก Claude...")
    new_items = call_claude(api_key, prompt)

    added = 0
    for item in new_items:
        if item.get(key_field) not in {e[key_field] for e in existing}:
            existing.append(item)
            added += 1

    save_json(path, existing)
    print(f"เพิ่มคำศัพท์ใหม่ {added} รายการ (รวมทั้งหมด {len(existing)} รายการ) ในไฟล์ {path}")


if __name__ == "__main__":
    main()
