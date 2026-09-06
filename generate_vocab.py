import json
import os
import random
import re
import sys
import urllib.request

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
SOURCES_DIR = "sources"
CHUNK_CHARS = 4000
PENDING_FILE = "pending_new_items.json"  # ไฟล์ชั่วคราว เก็บเฉพาะคำใหม่ที่เพิ่งได้จาก Claude

PROMPTS = {
    "naming_roots": """จากข้อความอ้างอิงด้านล่างนี้ (มาจากไฟล์ "{filename}") ช่วยเลือกรากศัพท์ภาษาลาติน สูงสุด {count} คำที่น่าสนใจ ที่เชื่อมโยงได้กับเนื้อหานี้
(ควรเป็นรากที่ถูกนำไปใช้ตั้งชื่อคน/สถานที่/ตัวละคร/แบรนด์ในโลกจริงหรือในสื่อต่างๆ)

สำคัญ: ไม่จำเป็นต้องเป็นคำที่ปรากฏตรงตัวในข้อความ — ให้ใช้ธีม โทนเรื่อง ชื่อตัวละคร ชื่อสถานที่ หรือแนวคิดที่ปรากฏในข้อความนี้เป็นแรงบันดาลใจในการเลือกรากศัพท์ลาตินที่เกี่ยวข้องได้เลย (เช่น ถ้าข้อความพูดถึงแสงจันทร์ ก็เลือกรากศัพท์เกี่ยวกับแสง/จันทร์ได้ แม้คำละตินจะไม่ปรากฏตรงๆ) ตอบ [] เฉพาะกรณีที่ธีมของข้อความนี้ไม่เอื้อให้เชื่อมโยงกับอะไรได้เลยจริงๆ เท่านั้น

ห้ามเลือกคำที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"latin": "คำ+รูปพจนานุกรม", "pos": "ชนิดคำ", "root": "ราก", "thai": "คำแปลไทย", "naming_examples": ["ตัวอย่าง 1", "ตัวอย่าง 2"], "old_english": "คำอังกฤษโบราณที่เกี่ยวข้อง หรือ 'ไม่มี'", "source": "{filename} (เชื่อมโยงจากธีม/ชื่อในเนื้อหา)"}}]

ข้อความอ้างอิง:
---
{source}
---""",
    "old_english": """จากข้อความอ้างอิงด้านล่างนี้ (มาจากไฟล์ "{filename}") ช่วยสร้างคำศัพท์ภาษาอังกฤษโบราณ (Old English) สูงสุด {count} คำ ที่เข้ากับโทนของเนื้อหานี้

สำคัญ: ไม่จำเป็นต้องมีคำอังกฤษโบราณปรากฏในข้อความจริง — ให้ใช้ธีม โทนเรื่อง หรือบรรยากาศของข้อความนี้ (เช่น ยุคกลาง มหากาพย์ ตำนาน สงคราม ธรรมชาติ) เป็นแรงบันดาลใจแต่งคำ/ประโยคภาษาอังกฤษโบราณที่เข้ากันได้เลย ตอบ [] เฉพาะกรณีที่ธีมของข้อความนี้ไม่เอื้อให้แต่งอะไรได้เลยจริงๆ เท่านั้น

ห้ามเลือกคำที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"old_english": "คำ", "pos": "ชนิดคำ", "thai": "คำแปลไทย", "modern_descendant": "คำอังกฤษปัจจุบันที่สืบทอดมา", "example": "ประโยคภาษาอังกฤษโบราณ", "example_thai": "คำแปลประโยคนั้น", "source": "{filename} (แต่งจากธีมของเนื้อหา)"}}]

ข้อความอ้างอิง:
---
{source}
---""",
}

FILES = {"naming_roots": "naming_roots.json", "old_english": "old_english_vocab.json"}
KEY_FIELD = {"naming_roots": "latin", "old_english": "old_english"}


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_source_text(requested_file):
    if not os.path.isdir(SOURCES_DIR):
        print(f"ERROR: ไม่พบโฟลเดอร์ {SOURCES_DIR}/", file=sys.stderr)
        sys.exit(1)
    txt_files = [f for f in os.listdir(SOURCES_DIR) if f.endswith(".txt")]
    if not txt_files:
        print(f"ERROR: ไม่พบไฟล์ .txt ใน {SOURCES_DIR}/", file=sys.stderr)
        sys.exit(1)
    filename = requested_file if requested_file in txt_files else random.choice(txt_files)
    with open(os.path.join(SOURCES_DIR, filename), "r", encoding="utf-8") as f:
        content = f.read()
    if len(content) <= CHUNK_CHARS:
        chunk = content
    else:
        start = random.randint(0, len(content) - CHUNK_CHARS)
        chunk = content[start:start + CHUNK_CHARS]
    return filename, chunk


def call_claude(api_key, prompt, attempt=1, max_attempts=3):
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4000,
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

    stop_reason = data.get("stop_reason", "?")
    content_blocks = data.get("content", [])
    text = ""
    for block in content_blocks:
        if block.get("type") == "text":
            text += block.get("text", "")

    if not text.strip():
        print(f"[attempt {attempt}] Claude ตอบว่างเปล่า (stop_reason={stop_reason})", file=sys.stderr)
        print(f"raw response: {json.dumps(data, ensure_ascii=False)[:1500]}", file=sys.stderr)
        if attempt < max_attempts:
            print("ลองขอใหม่อีกครั้ง...", file=sys.stderr)
            return call_claude(api_key, prompt, attempt + 1, max_attempts)
        raise RuntimeError("Claude ตอบว่างเปล่าซ้ำหลายครั้ง ดู raw response ด้านบนเพื่อวินิจฉัย")

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # กันเผื่อ Claude แทรกข้อความอธิบายก่อน/หลัง JSON ทั้งที่สั่งห้ามแล้ว —
    # ดึงเฉพาะช่วงตั้งแต่ [ ตัวแรกถึง ] ตัวสุดท้ายมาลองแปลงใหม่
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            print(f"[attempt {attempt}] ต้องดึง JSON ออกจากข้อความที่มีคำอธิบายแทรก (แก้ไขอัตโนมัติสำเร็จ)", file=sys.stderr)
            return result
        except json.JSONDecodeError:
            pass

    print(f"[attempt {attempt}] parse JSON ไม่สำเร็จ ข้อความที่ได้จริง:", file=sys.stderr)
    print(text[:1500], file=sys.stderr)
    if attempt < max_attempts:
        print("ลองขอใหม่อีกครั้ง...", file=sys.stderr)
        return call_claude(api_key, prompt, attempt + 1, max_attempts)
    raise RuntimeError("parse JSON จากคำตอบ Claude ไม่สำเร็จหลังจากลองหลายครั้ง")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    target = os.environ.get("TARGET", "naming_roots")
    requested_file = os.environ.get("SOURCE_FILE", "").strip()
    count = os.environ.get("COUNT", "3" if target == "naming_roots" else "5")

    if not api_key:
        print("ERROR: ไม่พบ ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)
    if target not in FILES:
        print("ERROR: target ต้องเป็น naming_roots หรือ old_english", file=sys.stderr)
        sys.exit(1)

    filename, chunk = pick_source_text(requested_file)
    print(f"ใช้ไฟล์: {filename} (สุ่มตัดข้อความยาว {len(chunk)} ตัวอักษร)")

    path = FILES[target]
    key_field = KEY_FIELD[target]
    existing = load_json(path, [])
    existing_keys = ", ".join(item[key_field] for item in existing) or "(ยังไม่มี)"

    prompt = PROMPTS[target].format(count=count, existing=existing_keys, source=chunk, filename=filename)

    print(f"กำลังขอคำศัพท์ {count} คำ ({target}) จาก Claude...")
    new_items = call_claude(api_key, prompt)

    # เขียนแค่ "คำใหม่ที่ได้" ลงไฟล์ชั่วคราว ไม่แตะไฟล์หลัก
    # ให้ขั้นตอน merge (ใน workflow) เป็นคนรวมเข้าไฟล์หลักอย่างปลอดภัยทีหลัง
    save_json(PENDING_FILE, {"target": target, "items": new_items})
    print(f"ได้คำใหม่ {len(new_items)} คำ บันทึกไว้ที่ {PENDING_FILE} รอ merge")


if __name__ == "__main__":
    main()
