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

THAI_PERIOD_NOTE = (
    "ข้อสำคัญเรื่องการแปลไทย: เลือกใช้คำศัพท์ไทยที่เหมาะกับ \"ยุคสมัย\" ของคำ/ชื่อนั้นๆ "
    "ถ้าคำต้นทางเป็นคำโบราณ/ล้าสมัย ให้แปลด้วยคำไทยโบราณ ราชาศัพท์ หรือคำที่พบในวรรณคดีไทย "
    "(เช่น ใช้ \"เยาวมาลย์\" แทน \"หญิงสาว\", \"พิโรธ\" แทน \"โกรธ\", \"เสด็จ\" แทน \"ไป\" ในบริบทที่เหมาะสม) "
    "ไม่ใช่แปลด้วยภาษาไทยสมัยใหม่ทื่อๆ — ให้ความรู้สึกของยุคสมัยตรงกับต้นฉบับ"
)

PROMPTS = {
    "roots_voc": """จากข้อความอ้างอิงด้านล่างนี้ (มาจากไฟล์ "{filename}") ช่วยหาชื่อคน/สถานที่/ตัวละคร/สิ่งของ ที่ปรากฏจริงในข้อความนี้ สูงสุด {count} ชื่อ ที่มีที่มาทางภาษาศาสตร์ที่น่าสนใจ

สำหรับแต่ละชื่อ ให้วิเคราะห์:
1. ชื่อนั้นประกอบขึ้นจากส่วนย่อย (root/morpheme) อะไรบ้าง
2. แต่ละส่วนมาจากภาษาอะไร (เช่น ละติน, กรีกโบราณ, อังกฤษโบราณ, เยอรมัน/เจอร์แมนิก, ฝรั่งเศสโบราณ, หรือภาษาอื่นๆ — ไม่จำเป็นต้องเป็นละตินเสมอไป ให้ระบุตามความจริงทางนิรุกติศาสตร์)
3. แต่ละส่วนแปลว่าอะไร
4. เมื่อผนวกส่วนต่างๆ เข้าด้วยกันแล้ว ได้ความหมายรวมว่าอะไร และทำไมถึงถูกเลือกมาตั้งเป็นชื่อนี้ (ถ้าเป็นชื่อสมมติในนิยาย/เกม ให้วิเคราะห์ตามหลักนิรุกติศาสตร์ที่ผู้แต่งน่าจะใช้เป็นแรงบันดาลใจ)

ถ้าชื่อนั้นเป็นชื่อที่ประดิษฐ์ขึ้นและไม่มีที่มาทางภาษาศาสตร์จริงที่วิเคราะห์ได้เลย ให้ข้ามชื่อนั้นไป เลือกชื่ออื่นแทน

""" + THAI_PERIOD_NOTE + """

ห้ามเลือกชื่อที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"name": "ชื่อที่ปรากฏในข้อความ", "thai_meaning": "ความหมายรวมของชื่อเป็นภาษาไทย (ใช้คำไทยตามยุคสมัยของชื่อนั้น)", "components": [{{"part": "ส่วนย่อยของชื่อ", "language": "ภาษาที่มาของส่วนนี้", "meaning_thai": "ความหมายของส่วนนี้เป็นภาษาไทย"}}], "explanation_thai": "อธิบายว่าส่วนต่างๆ ผนวกกันเป็นชื่อนี้ได้อย่างไร และเชื่อมโยงกับตัวละคร/สถานที่นี้อย่างไร", "source": "{filename}"}}]

ข้อความอ้างอิง:
---
{source}
---""",
    "archaic_voc": """จากข้อความอ้างอิงด้านล่างนี้ (มาจากไฟล์ "{filename}") ช่วยหาคำโบราณ/คำล้าสมัย (archaic word) สูงสุด {count} คำ ที่เข้ากับโทนของเนื้อหานี้

ลำดับความสำคัญ (สำคัญมาก):
1. เป้าหมายหลัก: หาคำโบราณ/คำล้าสมัยที่ "ปรากฏตรงตัวจริงในข้อความนี้" ก่อนเสมอ — ไม่ว่าจะเป็นคำโบราณของภาษาอังกฤษยุคไหนก็ตาม (ไม่จำกัดแค่ Old English เท่านั้น อาจเป็น Middle English หรือคำล้าสมัยทั่วไปที่ไม่ใช้กันแล้วในปัจจุบันก็ได้)
2. เป้าหมายรอง: ถ้าหาคำที่ปรากฏจริงในข้อความไม่ได้เลย ให้เลือกคำโบราณ/คำอังกฤษโบราณ (Old English) ที่มีอยู่จริง มีบันทึกในพจนานุกรมหรือวรรณกรรมจริง (เช่น thee, thou, wherefore, betwixt, forsooth, verily, ere, hither, methinks, yonder, alas และคำ Old English แท้ๆ) ที่เข้ากับธีม/บรรยากาศของข้อความนี้มากที่สุด ห้ามประดิษฐ์คำขึ้นมาเองเด็ดขาด

สำหรับแต่ละคำ อธิบาย:
- ความหมายของคำ
- ตัวอย่างประโยคที่ใช้คำนั้น (ถ้าเป็นเป้าหมายหลัก ให้ดึงประโยคจากข้อความอ้างอิงนี้จริงๆ ถ้าเป็นเป้าหมายรอง แต่งประโยคสไตล์เดียวกันได้)
- คำที่ใช้แทนกันในภาษาอังกฤษปัจจุบัน (modern replacement)

""" + THAI_PERIOD_NOTE + """

ห้ามเลือกคำที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"word": "คำโบราณที่มีอยู่จริง", "pos": "ชนิดคำ", "is_from_source": true, "thai": "คำแปลไทย (ใช้คำไทยโบราณ/ราชาศัพท์/คำวรรณคดีให้เข้ากับยุคของคำนี้)", "modern_replacement": "คำที่ใช้แทนกันในภาษาอังกฤษปัจจุบัน", "example": "ตัวอย่างประโยคที่ใช้คำนี้", "example_thai": "คำแปลประโยคนั้น (ใช้สำนวนไทยให้เข้ากับยุค)", "source": "{filename}"}}]

(หมายเหตุ: "is_from_source" ใส่ true ถ้าคำนี้ปรากฏจริงในข้อความอ้างอิง หรือ false ถ้าเป็นคำที่เลือกมาจากเป้าหมายรอง)

ข้อความอ้างอิง:
---
{source}
---""",
}

FILES = {"roots_voc": "roots_voc.json", "archaic_voc": "archaic_voc.json"}
KEY_FIELD = {"roots_voc": "name", "archaic_voc": "word"}


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
    target = os.environ.get("TARGET", "roots_voc")
    requested_file = os.environ.get("SOURCE_FILE", "").strip()
    count = os.environ.get("COUNT", "3" if target == "roots_voc" else "5")

    if not api_key:
        print("ERROR: ไม่พบ ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)
    if target not in FILES:
        print("ERROR: target ต้องเป็น roots_voc หรือ archaic_voc", file=sys.stderr)
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

    save_json(PENDING_FILE, {"target": target, "items": new_items})
    print(f"ได้คำใหม่ {len(new_items)} คำ บันทึกไว้ที่ {PENDING_FILE} รอ merge")


if __name__ == "__main__":
    main()
