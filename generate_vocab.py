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
CHUNK_CHARS = 4000          # สำหรับไฟล์ .txt (ข้อความดิบ)
JSON_SAMPLE_SIZE = 30       # สำหรับไฟล์ .json (คู่ EN/TH ทางการ) — จำนวนแถวที่สุ่มมาต่อรอบ
PENDING_FILE = "pending_new_items.json"  # ไฟล์ชั่วคราว เก็บเฉพาะคำใหม่ที่เพิ่งได้จาก Claude

THAI_PERIOD_NOTE = (
    "ข้อสำคัญเรื่องการแปลไทย: เลือกใช้คำศัพท์ไทยที่เหมาะกับ \"ยุคสมัย\" ของคำ/ชื่อนั้นๆ "
    "ถ้าคำต้นทางเป็นคำโบราณ/ล้าสมัย ให้แปลด้วยคำไทยโบราณ ราชาศัพท์ หรือคำที่พบในวรรณคดีไทย "
    "(เช่น ใช้ \"เยาวมาลย์\" แทน \"หญิงสาว\", \"พิโรธ\" แทน \"โกรธ\", \"เสด็จ\" แทน \"ไป\" ในบริบทที่เหมาะสม) "
    "ไม่ใช่แปลด้วยภาษาไทยสมัยใหม่ทื่อๆ — ให้ความรู้สึกของยุคสมัยตรงกับต้นฉบับ"
)

# แทรกเฉพาะตอนแหล่งอ้างอิงเป็นไฟล์ .json ที่มีคำแปลไทยทางการมาให้แล้ว (ห้าม AI แปลเอง)
TRANSLATION_GROUNDING_NOTE_ARCHAIC = (
    "ข้อสำคัญที่สุด — เรื่องคำแปลไทย: ข้อความอ้างอิงด้านล่างมาพร้อม \"คำแปลไทยทางการ\" จากต้นฉบับอยู่แล้ว "
    "(ไม่ใช่คำแปลที่ AI สร้างขึ้นเอง) ห้ามแปลคำหรือประโยคขึ้นใหม่เองเด็ดขาด ให้ทำตามนี้:\n"
    "1. เลือกคำโบราณจากฝั่ง EN ของรายการใดรายการหนึ่งที่ให้มา\n"
    "2. ดูคำแปลไทยทางการ (TH) ของ \"รายการเดียวกันนั้น\" แล้วดึง/สรุปคำหรือวลีในคำแปลนั้นที่ตรงกับคำที่เลือก มาใส่ในฟิลด์ \"thai\" "
    "— ถ้าคำแปลทางการใช้คำอื่นที่ความหมายตรงกัน ให้ยึดตามคำแปลทางการนั้น ไม่ใช่แปลเอง\n"
    "3. ฟิลด์ \"example\" ให้ใช้ข้อความ EN ของรายการนั้นเป๊ะๆ (หรือประโยคย่อยในนั้นที่มีคำนี้อยู่จริง) และฟิลด์ \"example_thai\" "
    "ให้ใช้คำแปลไทยทางการของรายการเดียวกันเป๊ะๆ (หรือส่วนที่สอดคล้องกัน) ห้ามแต่งขึ้นใหม่เอง"
)

TRANSLATION_GROUNDING_NOTE_ROOTS = (
    "ข้อสังเกตเพิ่มเติม: ข้อความอ้างอิงมีคำแปลไทยทางการกำกับอยู่ด้วย ถ้าชื่อนี้มีทับศัพท์ภาษาไทยทางการปรากฏอยู่ในคำแปล "
    "ให้ใส่ทับศัพท์นั้นในฟิลด์ \"thai_transliteration\" ด้วย (ถ้าไม่พบให้ใส่เป็นค่าว่าง \"\") "
    "ส่วนฟิลด์ \"thai_meaning\" และ \"explanation_thai\" ยังคงเป็นการวิเคราะห์นิรุกติศาสตร์ของคุณเองตามปกติ ไม่ต้องอิงจากคำแปล"
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

{translation_note}

ห้ามเลือกชื่อที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"name": "ชื่อที่ปรากฏในข้อความ", "thai_meaning": "ความหมายรวมของชื่อเป็นภาษาไทย (ใช้คำไทยตามยุคสมัยของชื่อนั้น)", "thai_transliteration": "ทับศัพท์ไทยทางการถ้ามี ไม่มีใส่ค่าว่าง", "components": [{{"part": "ส่วนย่อยของชื่อ", "language": "ภาษาที่มาของส่วนนี้", "meaning_thai": "ความหมายของส่วนนี้เป็นภาษาไทย"}}], "explanation_thai": "อธิบายว่าส่วนต่างๆ ผนวกกันเป็นชื่อนี้ได้อย่างไร และเชื่อมโยงกับตัวละคร/สถานที่นี้อย่างไร", "source": "{filename}"}}]

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

{translation_note}

ห้ามเลือกคำที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"word": "คำโบราณที่มีอยู่จริง", "pos": "ชนิดคำ", "is_from_source": true, "thai": "คำแปลไทย (ใช้คำไทยโบราณ/ราชาศัพท์/คำวรรณคดีให้เข้ากับยุคของคำนี้)", "modern_replacement": "คำที่ใช้แทนกันในภาษาอังกฤษปัจจุบัน", "example": "ตัวอย่างประโยคที่ใช้คำนี้", "example_thai": "คำแปลประโยคนั้น (ใช้สำนวนไทยให้เข้ากับยุค)", "source": "{filename}"}}]

(หมายเหตุ: "is_from_source" ใส่ true ถ้าคำนี้ปรากฏจริงในข้อความอ้างอิง หรือ false ถ้าเป็นคำที่เลือกมาจากเป้าหมายรอง)

ข้อความอ้างอิง:
---
{source}
---""",
    "general_voc": """ช่วยคิดคำศัพท์ภาษาอังกฤษทั่วไป (ไม่ต้องอิงจากข้อความอ้างอิงใดๆ) สูงสุด {count} "ชุดคำ" โดยแต่ละชุดคือ 1 แนวคิด/ความหมาย (concept) ที่มีคำศัพท์แตกต่างกันไปตามระดับความยากง่าย CEFR ตั้งแต่ A1 ถึง C2

สำหรับแต่ละแนวคิด:
1. ตั้งชื่อแนวคิดนั้นสั้นๆ เป็นภาษาไทย (เช่น "ความสุข", "การพูดคุย", "ความเหนื่อยล้า")
2. ไล่ระดับคำศัพท์ภาษาอังกฤษที่สื่อความหมายใกล้เคียงแนวคิดนี้ ตั้งแต่ระดับ A1 ไปจนถึง C2 (เรียงลำดับความยากขึ้นเรื่อยๆ) — คำในแต่ละระดับไม่จำเป็นต้องเป็นคำเดียวกัน แต่ต้องสื่อถึงแนวคิดเดียวกัน
3. ถ้าแนวคิดนี้ไม่มีคำศัพท์ที่เหมาะสมตามธรรมชาติในบางระดับ ให้ "ข้ามระดับนั้นไปเลย" ห้ามยัดคำที่ไม่เข้ากับระดับนั้นจริงๆ เข้ามา (แต่ควรมีอย่างน้อย 3 ระดับต่อ 1 แนวคิด)
4. สำหรับคำในแต่ละระดับ ให้ระบุ: ชนิดคำ (pos), คำแปลไทย, ตัวอย่างประโยคภาษาอังกฤษ, คำแปลประโยคนั้นเป็นไทย, คำอธิบายละเอียดว่าคำนี้ใช้ในบริบทไหน ต่างจากคำในระดับอื่นของแนวคิดเดียวกันอย่างไร, synonym ภาษาอังกฤษของคำนี้ (อย่างน้อย 1-2 คำ), synonym ภาษาไทยของคำแปล (อย่างน้อย 1-2 คำ)

ห้ามเลือกแนวคิดที่ซ้ำกับรายการนี้: {existing}

กติกาการตอบที่สำคัญที่สุด: ตอบเป็น JSON array เพียวๆ เท่านั้น ห้ามมีข้อความอธิบาย คำนำ หรือสรุปใดๆ ทั้งก่อนและหลัง JSON แม้แต่ประโยคเดียว ไม่ต้องมี ```json ครอบ คำตอบทั้งหมดต้องเริ่มด้วย [ และจบด้วย ] เท่านั้น ตามฟอร์แมตนี้เป๊ะๆ:
[{{"concept": "ชื่อแนวคิดสั้นๆ เป็นภาษาอังกฤษ (ใช้เป็น key ห้ามซ้ำ)", "concept_thai": "ชื่อแนวคิดเป็นภาษาไทย", "levels": [{{"cefr": "A1", "word": "คำศัพท์", "pos": "ชนิดคำ", "thai": "คำแปลไทย", "example": "ตัวอย่างประโยค", "example_thai": "คำแปลประโยค", "explanation_thai": "คำอธิบายละเอียดการใช้และความต่างจากระดับอื่น", "synonyms_en": ["..."], "synonyms_thai": ["..."]}}]}}]""",
}

FILES = {"roots_voc": "roots_voc.json", "archaic_voc": "archaic_voc.json", "general_voc": "general_voc.json"}
KEY_FIELD = {"roots_voc": "name", "archaic_voc": "word", "general_voc": "concept"}
NEEDS_SOURCE = {"roots_voc": True, "archaic_voc": True, "general_voc": False}


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_source_text(requested_file):
    """
    คืนค่า (filename, source_block_text, has_official_translation)
    รองรับ 2 แบบ:
    - ไฟล์ .txt : ข้อความดิบ สุ่มตัดช่วงตามเดิม (has_official_translation=False)
    - ไฟล์ .json : array ของ {"en":..., "th":...} ที่มีคำแปลไทยทางการมาให้แล้ว
                   สุ่มหยิบมาหลายแถว จัดฟอร์แมตเป็นรายการมีเลขกำกับ (has_official_translation=True)
    """
    if not os.path.isdir(SOURCES_DIR):
        print(f"ERROR: ไม่พบโฟลเดอร์ {SOURCES_DIR}/", file=sys.stderr)
        sys.exit(1)
    raw_candidates = [f for f in os.listdir(SOURCES_DIR) if f.endswith(".txt") or f.endswith(".json")]
    candidates = []
    for f in raw_candidates:
        if f.endswith(".json"):
            # กันไฟล์ .json ที่ว่างเปล่าหรือพัง ไม่ให้ถูกสุ่มไปใช้เป็นแหล่งอ้างอิง (จะได้คำ 0 คำแบบเงียบๆ)
            try:
                with open(os.path.join(SOURCES_DIR, f), "r", encoding="utf-8") as fh:
                    parsed = json.load(fh)
                if not parsed:
                    print(f"ข้าม {f}: เป็น .json ว่างเปล่า ไม่เหมาะเป็นแหล่งอ้างอิง (เช็คว่าไฟล์นี้ควรอยู่ที่ root ไม่ใช่ sources/ หรือเปล่า)", file=sys.stderr)
                    continue
            except (json.JSONDecodeError, OSError) as e:
                print(f"ข้าม {f}: เปิด/อ่านไฟล์ไม่ได้ ({e})", file=sys.stderr)
                continue
        candidates.append(f)
    if not candidates:
        print(f"ERROR: ไม่พบไฟล์ .txt หรือ .json ที่ใช้งานได้จริงใน {SOURCES_DIR}/", file=sys.stderr)
        sys.exit(1)
    filename = requested_file if requested_file in candidates else random.choice(candidates)
    full_path = os.path.join(SOURCES_DIR, filename)

    if filename.endswith(".json"):
        with open(full_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        sample_size = min(JSON_SAMPLE_SIZE, len(entries))
        sample = random.sample(entries, sample_size)
        lines = []
        for i, e in enumerate(sample, 1):
            lines.append(f"[{i}]\nEN: {e['en']}\nTH (คำแปลทางการ): {e['th']}")
        chunk = "\n\n".join(lines)
        return filename, chunk, True
    else:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) <= CHUNK_CHARS:
            chunk = content
        else:
            start = random.randint(0, len(content) - CHUNK_CHARS)
            chunk = content[start:start + CHUNK_CHARS]
        return filename, chunk, False


def call_claude(api_key, prompt, attempt=1, max_attempts=3):
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Sonnet 5 / Opus 5.x เปิด adaptive thinking เป็นค่าเริ่มต้นเสมอ (กิน token ร่วมกับ max_tokens)
    # ส่วน Haiku 4.5 ไม่รองรับพารามิเตอร์นี้ (จะ error ถ้าส่งไป) — เช็คก่อนว่าเป็นรุ่นไหน
    if "haiku-4-5" not in ANTHROPIC_MODEL:
        payload["thinking"] = {"type": "adaptive"}
        payload["output_config"] = {"effort": "low"}  # งานนี้แค่ดึง/จัดฟอร์แมตคำศัพท์ ไม่ต้องคิดหนัก
    body = json.dumps(payload).encode("utf-8")
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
        print(f"ERROR: target ต้องเป็นหนึ่งใน {list(FILES.keys())}", file=sys.stderr)
        sys.exit(1)

    path = FILES[target]
    key_field = KEY_FIELD[target]
    existing = load_json(path, [])
    existing_keys = ", ".join(item[key_field] for item in existing) or "(ยังไม่มี)"

    if NEEDS_SOURCE[target]:
        filename, chunk, has_translation = pick_source_text(requested_file)
        print(f"ใช้ไฟล์: {filename} (โหมด {'JSON คู่แปลทางการ' if has_translation else 'ข้อความดิบ .txt'}, ยาว {len(chunk)} ตัวอักษร)")
        if target == "archaic_voc":
            note = TRANSLATION_GROUNDING_NOTE_ARCHAIC if has_translation else ""
        else:  # roots_voc
            note = TRANSLATION_GROUNDING_NOTE_ROOTS if has_translation else ""
        prompt = PROMPTS[target].format(
            count=count, existing=existing_keys, source=chunk, filename=filename, translation_note=note
        )
    else:  # general_voc — ไม่ใช้ source ไฟล์ใดๆ
        print("target=general_voc ไม่ใช้ไฟล์ source (คิดคำศัพท์เอง)")
        prompt = PROMPTS[target].format(count=count, existing=existing_keys)

    print(f"กำลังขอคำศัพท์ {count} ชุด ({target}) จาก Claude...")
    new_items = call_claude(api_key, prompt)

    save_json(PENDING_FILE, {"target": target, "items": new_items})
    print(f"ได้ของใหม่ {len(new_items)} ชุด บันทึกไว้ที่ {PENDING_FILE} รอ merge")


if __name__ == "__main__":
    main()
