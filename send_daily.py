import json
import os
import sys
import urllib.request

WORDS_PER_DAY = 15  # ปรับได้ 10-20
VOCAB_FILE = "latin_vocab.json"
PROGRESS_FILE = "progress.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    ntfy_topic = os.environ.get("NTFY_TOPIC")
    if not ntfy_topic:
        print("ERROR: ไม่พบ NTFY_TOPIC ใน environment variable", file=sys.stderr)
        sys.exit(1)

    vocab = load_json(VOCAB_FILE, [])
    if not vocab:
        print("ERROR: ไม่พบคำศัพท์ใน latin_vocab.json", file=sys.stderr)
        sys.exit(1)

    progress = load_json(PROGRESS_FILE, {"index": 0, "round": 1})
    idx = progress["index"]
    total = len(vocab)

    todays_words = []
    for _ in range(WORDS_PER_DAY):
        todays_words.append(vocab[idx % total])
        idx += 1

    new_round = progress["round"] + (1 if idx // total > (progress["index"] // total) else 0)
    progress["index"] = idx % total
    progress["round"] = new_round if idx >= total else progress["round"]

    lines = [f"{w['latin']} ({w['pos']}) — {w['thai']}" for w in todays_words]
    message = "\n".join(lines)
    title = f"คำศัพท์ลาตินวันนี้ ({len(todays_words)} คำ) — รอบที่ {progress['round']}"

    url = f"https://ntfy.sh/{ntfy_topic}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Tags": "books",
            "Priority": "default",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print("ส่งแจ้งเตือนสำเร็จ, status:", resp.status)

    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()
