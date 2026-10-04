// ===== Vocab-Dailia PWA =====
const REPO = "Sinisteristic/Vocab-Dailia";
const BRANCH = "main";
const URLS = {
  roots: `https://raw.githubusercontent.com/${REPO}/${BRANCH}/roots_voc.json`,
  archaic: `https://raw.githubusercontent.com/${REPO}/${BRANCH}/archaic_voc.json`,
  general: `https://raw.githubusercontent.com/${REPO}/${BRANCH}/general_voc.json`,
};

let state = {
  roots: [], archaic: [], general: [],
  loaded: false,
  tab: "browse",
  browseTracks: new Set(["roots", "archaic", "general"]),
  browseQuery: "",
  quiz: { pool: [], idx: 0, score: 0, finished: false, currentAnswered: false },
  flash: { pool: [], idx: 0, flipped: false },
};

const viewEl = document.getElementById("view");

// ---------- โหลดข้อมูล ----------
async function loadAll() {
  viewEl.innerHTML = `<div class="loading">กำลังโหลดคลังคำศัพท์...</div>`;
  try {
    const [roots, archaic, general] = await Promise.all(
      Object.values(URLS).map((u) => fetch(u, { cache: "no-store" }).then((r) => r.json()))
    );
    state.roots = roots; state.archaic = archaic; state.general = general;
    state.loaded = true;
  } catch (e) {
    viewEl.innerHTML = `<div class="empty">โหลดข้อมูลไม่สำเร็จ ลองรีเฟรชอีกครั้ง<br><small>${e}</small></div>`;
    return;
  }
  render();
}

// ---------- ทำ pool กลาง (ใช้ร่วมกันทั้ง flashcard/quiz) ----------
// แต่ละ item: {track, headword, meaning, extra, sourceObj}
function buildPool(tracks) {
  const pool = [];
  if (tracks.has("roots")) {
    state.roots.forEach((w) => pool.push({
      track: "roots", headword: w.name, meaning: w.thai_meaning,
      extra: w.thai_transliteration || "", obj: w,
    }));
  }
  if (tracks.has("archaic")) {
    state.archaic.forEach((w) => pool.push({
      track: "archaic", headword: w.word, meaning: w.thai,
      extra: w.modern_replacement || "", obj: w,
    }));
  }
  if (tracks.has("general")) {
    state.general.forEach((c) => (c.levels || []).forEach((lvl) => pool.push({
      track: "general", headword: lvl.word, meaning: lvl.thai,
      extra: `${c.concept_thai || c.concept} · ${lvl.cefr}`, obj: lvl, concept: c,
    })));
  }
  return pool;
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------- Tab: Browse ----------
function renderBrowse() {
  const chips = ["roots", "archaic", "general"].map((t) => {
    const label = { roots: "ชื่อ/นิรุกติศาสตร์", archaic: "คำโบราณ", general: "ศัพท์ทั่วไป (CEFR)" }[t];
    const active = state.browseTracks.has(t) ? "active" : "";
    return `<button class="track-chip ${active}" data-track="${t}">${label}</button>`;
  }).join("");

  let items = [];
  if (state.browseTracks.has("roots")) items = items.concat(state.roots.map((w) => ({ track: "roots", w })));
  if (state.browseTracks.has("archaic")) items = items.concat(state.archaic.map((w) => ({ track: "archaic", w })));
  if (state.browseTracks.has("general")) items = items.concat(state.general.map((w) => ({ track: "general", w })));

  const q = state.browseQuery.trim().toLowerCase();
  if (q) {
    items = items.filter(({ track, w }) => {
      if (track === "roots") return (w.name + w.thai_meaning).toLowerCase().includes(q);
      if (track === "archaic") return (w.word + w.thai).toLowerCase().includes(q);
      return (w.concept + w.concept_thai + (w.levels || []).map((l) => l.word).join(" ")).toLowerCase().includes(q);
    });
  }

  const cardsHtml = items.slice(0, 100).map(({ track, w }) => {
    if (track === "roots") {
      const comps = (w.components || []).map((c) => `${c.part} (${c.language}) = ${c.meaning_thai}`).join(" · ");
      return `<div class="card">
        <div class="headword">${w.name}</div>
        <div class="meaning th">${w.thai_meaning || ""} ${w.thai_transliteration ? `<span class="meta">(${w.thai_transliteration})</span>` : ""}</div>
        <div class="meta">${comps}</div>
        <div class="expl th">${w.explanation_thai || ""}</div>
      </div>`;
    }
    if (track === "archaic") {
      return `<div class="card archaic">
        <div class="headword">${w.word} <span class="meta">(${w.pos || ""})</span></div>
        <div class="meaning th">${w.thai || ""}</div>
        <div class="meta">${w.is_from_source ? "📖 พบในต้นฉบับ" : "✍️ อังกฤษโบราณ (สำรอง)"} · แทนปัจจุบัน: ${w.modern_replacement || "-"}</div>
        <div class="expl th">${w.example || ""}${w.example_thai ? ` (${w.example_thai})` : ""}</div>
      </div>`;
    }
    const levelRows = (w.levels || []).map((lvl) => `
      <div class="level-row th"><span class="lvl-tag">${lvl.cefr}</span><b>${lvl.word}</b> (${lvl.pos || ""}) — ${lvl.thai || ""}
        <div class="meta">${lvl.example || ""}${lvl.example_thai ? ` (${lvl.example_thai})` : ""}</div>
      </div>`).join("");
    return `<div class="card general">
      <div class="headword th">${w.concept_thai || w.concept}</div>
      ${levelRows}
    </div>`;
  }).join("") || `<div class="empty">ไม่พบคำที่ตรงกับที่ค้นหา</div>`;

  viewEl.innerHTML = `
    <div class="track-filter">${chips}</div>
    <input type="text" id="search-box" placeholder="ค้นหาคำ / ชื่อ / ความหมาย..." value="${state.browseQuery}">
    ${cardsHtml}
  `;

  viewEl.querySelectorAll(".track-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const t = btn.dataset.track;
      if (state.browseTracks.has(t)) state.browseTracks.delete(t); else state.browseTracks.add(t);
      renderBrowse();
    });
  });
  document.getElementById("search-box").addEventListener("input", (e) => {
    state.browseQuery = e.target.value;
    renderBrowse();
  });
}

// ---------- Tab: Flashcard ----------
function newFlashDeck() {
  state.flash.pool = shuffle(buildPool(new Set(["roots", "archaic", "general"])));
  state.flash.idx = 0;
  state.flash.flipped = false;
}

function renderFlashcard() {
  if (state.flash.pool.length === 0) newFlashDeck();
  if (state.flash.pool.length === 0) { viewEl.innerHTML = `<div class="empty">ยังไม่มีคำศัพท์ในคลัง</div>`; return; }
  const item = state.flash.pool[state.flash.idx];
  viewEl.innerHTML = `
    <div class="flash-wrap">
      <div class="meta">${item.track === "roots" ? "ชื่อ/นิรุกติศาสตร์" : item.track === "archaic" ? "คำโบราณ" : "ศัพท์ทั่วไป"} · ${state.flash.idx + 1}/${state.flash.pool.length}</div>
      <div class="flashcard ${state.flash.flipped ? "flipped" : ""}" id="flashcard">
        <div class="flashcard-inner">
          <div class="flashcard-face front"><div class="big">${item.headword}</div></div>
          <div class="flashcard-face back">
            <div class="big th">${item.meaning || ""}</div>
            <div class="meta th">${item.extra || ""}</div>
          </div>
        </div>
      </div>
      <div class="flash-controls">
        <button class="btn" id="flash-prev">◀ ก่อนหน้า</button>
        <button class="btn" id="flash-shuffle">🔀 สับใหม่</button>
        <button class="btn" id="flash-next">ถัดไป ▶</button>
      </div>
    </div>`;
  document.getElementById("flashcard").addEventListener("click", () => {
    state.flash.flipped = !state.flash.flipped;
    renderFlashcard();
  });
  document.getElementById("flash-next").addEventListener("click", (e) => {
    e.stopPropagation();
    state.flash.idx = (state.flash.idx + 1) % state.flash.pool.length;
    state.flash.flipped = false;
    renderFlashcard();
  });
  document.getElementById("flash-prev").addEventListener("click", (e) => {
    e.stopPropagation();
    state.flash.idx = (state.flash.idx - 1 + state.flash.pool.length) % state.flash.pool.length;
    state.flash.flipped = false;
    renderFlashcard();
  });
  document.getElementById("flash-shuffle").addEventListener("click", (e) => {
    e.stopPropagation();
    newFlashDeck();
    renderFlashcard();
  });
}

// ---------- Tab: Quiz ----------
function newQuiz() {
  const pool = shuffle(buildPool(new Set(["roots", "archaic", "general"])));
  const n = Math.min(10, pool.length);
  const questions = pool.slice(0, n).map((correct) => {
    const distractorsPool = pool.filter((p) => p !== correct && p.meaning && p.meaning !== correct.meaning);
    const distractors = shuffle(distractorsPool).slice(0, 3).map((p) => p.meaning);
    const options = shuffle([correct.meaning, ...distractors]);
    return { item: correct, options, correctAnswer: correct.meaning };
  });
  state.quiz = { pool: questions, idx: 0, score: 0, finished: false, currentAnswered: false };
}

function renderQuiz() {
  if (state.quiz.pool.length === 0) newQuiz();
  if (state.quiz.pool.length === 0) { viewEl.innerHTML = `<div class="empty">ยังไม่มีคำศัพท์พอทำควิซ</div>`; return; }

  if (state.quiz.finished) {
    incrementStreak();
    viewEl.innerHTML = `
      <div class="quiz-result">
        <div class="meta">คะแนนของคุณ</div>
        <div class="score">${state.quiz.score} / ${state.quiz.pool.length}</div>
        <button class="btn" id="quiz-restart">เล่นใหม่</button>
      </div>`;
    document.getElementById("quiz-restart").addEventListener("click", () => { newQuiz(); renderQuiz(); });
    return;
  }

  const q = state.quiz.pool[state.quiz.idx];
  const optsHtml = q.options.map((opt) => `<button class="quiz-option th" data-opt="${encodeURIComponent(opt)}">${opt}</button>`).join("");
  viewEl.innerHTML = `
    <div class="quiz-progress">ข้อ ${state.quiz.idx + 1} / ${state.quiz.pool.length} · คะแนน ${state.quiz.score}</div>
    <div class="quiz-q">คำว่า <b>${q.item.headword}</b> แปลว่าอะไร?</div>
    ${optsHtml}
  `;
  viewEl.querySelectorAll(".quiz-option").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (state.quiz.currentAnswered) return;
      state.quiz.currentAnswered = true;
      const chosen = decodeURIComponent(btn.dataset.opt);
      const correct = chosen === q.correctAnswer;
      if (correct) state.quiz.score++;
      viewEl.querySelectorAll(".quiz-option").forEach((b) => {
        const val = decodeURIComponent(b.dataset.opt);
        if (val === q.correctAnswer) b.classList.add("correct");
        else if (b === btn) b.classList.add("wrong");
      });
      setTimeout(() => {
        state.quiz.idx++;
        state.quiz.currentAnswered = false;
        if (state.quiz.idx >= state.quiz.pool.length) state.quiz.finished = true;
        renderQuiz();
      }, 900);
    });
  });
}

// ---------- Tab: Stats ----------
function getStreak() {
  try {
    const raw = localStorage.getItem("vocabdailia_streak");
    return raw ? JSON.parse(raw) : { streak: 0, lastDate: null };
  } catch (e) { return { streak: 0, lastDate: null }; }
}
function incrementStreak() {
  try {
    const today = new Date().toISOString().slice(0, 10);
    const data = getStreak();
    if (data.lastDate === today) return;
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    data.streak = data.lastDate === yesterday ? data.streak + 1 : 1;
    data.lastDate = today;
    localStorage.setItem("vocabdailia_streak", JSON.stringify(data));
  } catch (e) { /* localStorage ใช้ไม่ได้ก็ข้ามไป */ }
}
function generalWordCount() {
  return state.general.reduce((sum, c) => sum + (c.levels ? c.levels.length : 0), 0);
}
function renderStats() {
  const streak = getStreak();
  viewEl.innerHTML = `
    <div class="stat-grid">
      <div class="stat-box"><div class="num">${state.roots.length}</div><div class="label th">ชื่อ/นิรุกติศาสตร์</div></div>
      <div class="stat-box"><div class="num">${state.archaic.length}</div><div class="label th">คำโบราณ</div></div>
      <div class="stat-box"><div class="num">${state.general.length}</div><div class="label th">แนวคิด CEFR (${generalWordCount()} คำ)</div></div>
      <div class="stat-box"><div class="num">${state.roots.length + state.archaic.length + generalWordCount()}</div><div class="label th">รวมทั้งหมด</div></div>
    </div>
    <div class="stat-box" style="margin-bottom:0.8rem;">
      <div class="num">🔥 ${streak.streak}</div>
      <div class="label th">วันติดต่อกันที่เล่น Quiz</div>
    </div>
    <div class="meta th" style="text-align:center;">อัปเดตล่าสุด: ${new Date().toLocaleString("th-TH")}</div>
    <div style="text-align:center; margin-top:0.8rem;"><button class="btn" id="refresh-btn">🔄 รีเฟรชข้อมูล</button></div>
  `;
  document.getElementById("refresh-btn").addEventListener("click", loadAll);
}

// ---------- Router ----------
function render() {
  if (!state.loaded) return;
  document.querySelectorAll("nav.tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === state.tab));
  if (state.tab === "browse") renderBrowse();
  else if (state.tab === "flashcard") renderFlashcard();
  else if (state.tab === "quiz") renderQuiz();
  else if (state.tab === "stats") renderStats();
}

document.querySelectorAll("nav.tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.tab = btn.dataset.tab;
    render();
  });
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("service-worker.js").catch(() => {}));
}

loadAll();
