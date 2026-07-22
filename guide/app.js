const config = window.DBL_GUIDE_CONFIG || {};
const productionApi = location.hostname === "arav1oli.github.io" ? "https://dans-boat-life-guide-api.onrender.com" : "";
const apiBase = (config.apiBase || productionApi).replace(/\/$/, "");

const missionDetailOptions = {
  family: [
    ["protected-family-days", "Protected family days", "Shelter and comfort when the weather changes"],
    ["easy-water-access", "Easy water access", "Swimming and getting on and off should be simple"],
    ["family-weekends", "Weekends together", "Sleeping aboard is part of the family plan"],
    ["room-for-friends", "Room for friends", "A larger regular day group matters"]
  ],
  fishing: [
    ["offshore-fishing", "Serious offshore fishing", "Open-water capability and a fishing-led layout"],
    ["coastal-fishing", "Coastal fishing", "Practical fishing with broader family use"],
    ["walkaround-fishing", "Space to move around", "Safe, useful circulation around the deck"],
    ["short-handed-fishing", "Short-handed control", "Docking and position control with fewer people"]
  ],
  watersports: [
    ["water-access", "Easy water access", "Platforms, terraces or doors close to the water"],
    ["social-anchor", "Social days at anchor", "Room for people matters as much as performance"],
    ["all-weather-active", "More weather protection", "Keep active days possible when conditions change"],
    ["fast-day-runs", "Fast day runs", "Cover distance quickly and make the most of the day"]
  ],
  exploring: [
    ["all-weather-exploring", "All-weather passages", "Protection and open-water capability come first"],
    ["range-autonomy", "Range and autonomy", "Longer trips with greater independence"],
    ["short-handed-exploring", "Short-handed exploring", "Confident handling with a small crew"],
    ["weekend-exploring", "Weekend adventures", "Practical overnight capability without a large yacht"]
  ],
  "mixed-use": [
    ["protection-balance", "Protection and day use", "A useful balance rather than an open-only layout"],
    ["mixed-water-access", "Easy water access", "Swimming and active use remain important"],
    ["overnight-option", "Keep overnighting open", "A berth matters even if it is not used every trip"],
    ["social-space", "More social space", "A larger group and flexible seating matter most"]
  ]
};

const questions = [
  { id: "country", kicker: "Your market", title: "Where will you buy and keep the boat?", help: "Country affects availability, prices and which sold-boat evidence is relevant.", options: [
    ["AU", "Australia", "Use Australian market evidence where available"], ["US", "United States", "Use United States market evidence"],
    ["GB", "United Kingdom", "Use UK market evidence"], ["NZ", "New Zealand", "Use New Zealand market evidence"],
    ["EU", "Europe", "We will ask for the exact country before emailing"], ["OTHER", "Somewhere else", "Keep recommendations global until qualified"]
  ]},
  { id: "water", kicker: "Your boating", title: "What sort of water will you use most?", help: "Choose the hardest conditions you expect to use regularly, not a once-a-year ambition.", options: [
    ["sheltered", "Sheltered water", "Harbours, rivers and protected bays"], ["coastal", "Coastal", "Day runs along the coast with sensible weather windows"],
    ["offshore", "Offshore", "Open-water passages and more exposed conditions"]
  ]},
  { id: "priority", kicker: "Main mission", title: "What should the boat do particularly well?", help: "A boat can do several things, but one primary mission makes the shortlist more honest.", options: [
    ["family", "Family time", "Comfort, access and flexible social space"], ["fishing", "Fishing", "Working space, access and practical movement"],
    ["watersports", "Watersports", "Swimming, toys and energetic day use"], ["exploring", "Exploring", "Weather range, independence and purposeful travel"],
    ["mixed-use", "A genuine mix", "Avoid over-specialising the recommendation"]
  ]},
  { id: "mission_detail", kicker: "The job to be done", title: "Within that mission, what matters most?", help: "This answer is used as a real qualification, not a marketing preference.", when: (answers) => Boolean(answerValue(answers, "priority")), options: (answers) => missionDetailOptions[answerValue(answers, "priority")] || [] },
  { id: "people", kicker: "Day capacity", title: "How many people are normally aboard during the day?", help: "This is your usual day group. Sleeping capacity is asked separately if you need it.", options: [
    ["2", "One or two", "Mostly a couple or solo use"], ["4", "Three or four", "A couple, children or close friends"],
    ["6", "Five or six", "Regular family and friends"], ["8", "Seven or eight", "A larger regular day group"]
  ]},
  { id: "overnight", kicker: "Time aboard", title: "Does the boat need to handle overnight trips?", help: "This is a meaningful fork. Day use and sleeping aboard are different requirements.", options: [
    ["none", "No, day use only", "Keep the layout focused on the day"], ["optional", "Nice to have", "An occasional night without building the whole decision around it"],
    ["required", "Yes, it is essential", "Practical accommodation is a hard requirement"]
  ]},
  { id: "sleeping_people", kicker: "Overnight party", title: "How many people need a proper place to sleep?", help: "Use the usual overnight party, not the number carried during the day.", when: (answers) => ["optional", "required"].includes(answerValue(answers, "overnight")), options: [
    ["2", "One or two", "A proper berth for a couple"], ["4", "Three or four", "Family or two couples"],
    ["6", "Five or six", "A larger overnight party"]
  ]},
  { id: "overnight_duration", kicker: "Trip length", title: "How long will a normal overnight trip be?", help: "Longer stays need more autonomy than a single night close to home.", when: (answers) => ["optional", "required"].includes(answerValue(answers, "overnight")), options: [
    ["occasional", "One night", "An occasional overnight close to home"], ["weekend", "A weekend", "Two or three nights aboard"],
    ["extended", "Four nights or more", "Range and onboard autonomy become important"]
  ]},
  { id: "overnight_facilities", kicker: "Onboard comfort", title: "What must be confirmed for overnight use?", help: "A missing transcript tag is treated as unknown, not quietly assumed.", when: (answers) => ["optional", "required"].includes(answerValue(answers, "overnight")), options: [
    ["basic", "A practical berth", "Keep systems and expectations simple"], ["galley", "A proper galley", "Cooking aboard must be confirmed"],
    ["shower", "A separate shower", "Bathroom privacy and comfort are essential"]
  ]},
  { id: "helm", kicker: "Weather protection", title: "How protected should the helm be?", help: "This now removes incompatible layouts rather than adding a small score.", options: [
    ["open", "Open", "Maximum connection to the day and weather"], ["protected", "Protected", "A windscreen, hardtop or substantial shelter"],
    ["enclosed", "Fully enclosed", "A proper cabin or wheelhouse around the helm"]
  ]},
  { id: "storage", kicker: "Ownership reality", title: "Where will the boat live?", help: "A brilliant boat is the wrong boat if its storage and handling do not fit your life.", options: [
    ["trailer", "On a trailer", "Trailerability is a hard requirement"], ["dry-stack", "Dry stack", "Crane and facility limits matter"],
    ["marina", "Marina berth", "No trailering requirement"], ["unsure", "Not sure yet", "Keep storage options open"]
  ]},
  { id: "length", kicker: "Practical size", title: "What length range feels realistic?", help: "Boats more than four feet outside this range will not be shown.", options: [
    ["20-29", "20-29 feet", "Compact and easier to store"], ["30-34", "30-34 feet", "A useful middle ground"],
    ["35-39", "35-39 feet", "More space and capability"], ["40-50", "40-50 feet", "Larger systems and accommodation"]
  ]},
  { id: "budget", kicker: "Price qualification", title: "What budget band are you working within?", help: "Stored for later regional price filtering. It does not yet overrule boat fit where sales evidence is thin.", optional: true, options: [
    ["under-150", "Under 150k", "In your local currency"], ["150-300", "150k-300k", "In your local currency"],
    ["300-600", "300k-600k", "In your local currency"], ["600-plus", "600k+", "In your local currency"],
    ["unsure", "Not sure yet", "Do not price-filter my shortlist"]
  ]},
  { id: "condition", kicker: "Buying preference", title: "Are you considering new or used?", help: "This makes sales evidence and later follow-up more relevant.", optional: true, options: [
    ["new", "New", "Current-model availability matters most"], ["used", "Used", "Sold-market depth matters most"],
    ["either", "Either", "Show the best fit regardless of age"]
  ]},
  { id: "timing", kicker: "Timing", title: "When are you realistically looking to buy?", help: "This does not change boat fit. It makes future information more useful.", optional: true, options: [
    ["now", "Right now", "Actively comparing"], ["3-months", "Within three months", "A near-term decision"],
    ["6-months", "Three to six months", "Still narrowing the field"], ["later", "More than six months", "Early research"]
  ]}
];

const state = { index: 0, answers: {}, sessionId: null, token: null, resumeUrl: null, boats: [], apiReady: false, pending: new Set(), editing: false };
const $ = (selector) => document.querySelector(selector);
const screens = [$("#intro-screen"), $("#question-screen"), $("#results-screen")];

function answerValue(answers, key) { const answer = answers[key]; return answer && typeof answer === "object" ? String(answer.value) : (answer == null ? null : String(answer)); }
function activeQuestions() { return questions.filter((question) => !question.when || question.when(state.answers)); }
function questionOptions(question) { return typeof question.options === "function" ? question.options(state.answers) : question.options; }
function showScreen(target) { screens.forEach((screen) => { screen.hidden = screen !== target; }); window.scrollTo({ top: 0, behavior: "smooth" }); }
function setSaveState(kind, text) { const el = $("#save-state"); el.className = `save-state ${kind}`; el.querySelector("span:last-child").textContent = text; }
function sessionHeaders() { return { "Content-Type": "application/json", "X-Resume-Token": state.token }; }
function allActiveAnswered() { return activeQuestions().every((question) => state.answers[question.id]); }

function pruneInactiveAnswers() {
  const activeIds = new Set(activeQuestions().map((question) => question.id));
  questions.forEach((question) => {
    if (!activeIds.has(question.id)) { delete state.answers[question.id]; state.pending.delete(question.id); return; }
    const selected = answerValue(state.answers, question.id);
    if (selected && selected !== "unspecified" && !questionOptions(question).some(([value]) => value === selected)) {
      delete state.answers[question.id]; state.pending.delete(question.id);
    }
  });
}

function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
async function api(path, options = {}, attempts = 3) {
  if (!apiBase) throw new Error("The secure guide service has not been configured.");
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 70000);
    try {
      const response = await fetch(`${apiBase}${path}`, { ...options, signal: controller.signal });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Request failed");
      return payload;
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) await delay(1200 * (attempt + 1));
    } finally { clearTimeout(timeout); }
  }
  throw lastError;
}

async function syncPendingAnswers() {
  for (const question of activeQuestions()) {
    if (!state.pending.has(question.id) || !state.answers[question.id]) continue;
    const answer = state.answers[question.id];
    await api(`/api/sessions/${state.sessionId}/decisions`, {
      method: "POST", headers: sessionHeaders(),
      body: JSON.stringify({ question_id: question.id, answer_value: answer.value, answer_label: answer.label })
    });
    state.pending.delete(question.id);
  }
}

async function startSession({ syncLocal = false } = {}) {
  const localAnswers = { ...state.answers };
  const params = new URLSearchParams(location.search);
  const fragment = new URLSearchParams(location.hash.replace(/^#/, ""));
  const existingId = state.sessionId || params.get("session");
  const existingToken = state.token || fragment.get("token");
  setSaveState("", "Connecting secure save…");
  if (existingId && existingToken) {
    state.sessionId = existingId; state.token = existingToken;
    const saved = await api(`/api/sessions/${existingId}`, { headers: { "X-Resume-Token": existingToken } });
    state.answers = { ...(saved.answers || {}), ...localAnswers };
    Object.keys(localAnswers).forEach((key) => state.pending.add(key));
    state.apiReady = true;
    pruneInactiveAnswers();
    if (syncLocal) await syncPendingAnswers();
    setSaveState("saved", localAnswers && Object.keys(localAnswers).length ? "All decisions saved" : "Saved guide restored");
    renderDecisionTrail();
    return;
  }
  const created = await api("/api/sessions", { method: "POST" });
  state.sessionId = created.public_id; state.token = created.resume_token; state.resumeUrl = created.resume_url; state.apiReady = true;
  history.replaceState({}, "", `${location.pathname}?session=${created.public_id}#token=${created.resume_token}`);
  Object.keys(localAnswers).forEach((key) => state.pending.add(key));
  if (syncLocal) await syncPendingAnswers();
  setSaveState("saved", "Progress saves automatically");
}

async function ensureConnected() {
  if (!state.apiReady) await startSession({ syncLocal: true });
  else await syncPendingAnswers();
}

function updateProgress() {
  const active = activeQuestions();
  const answered = active.filter((question) => state.answers[question.id]).length;
  $("#progress-count").textContent = `${answered} of ${active.length}`;
  $("#progress-label").textContent = answered ? "Building your brief" : "Getting started";
  $("#progress-bar").style.width = `${active.length ? (answered / active.length) * 100 : 0}%`;
}

function renderDecisionTrail() {
  pruneInactiveAnswers();
  const list = $("#decision-list"); list.innerHTML = "";
  activeQuestions().forEach((question, index) => {
    const answer = state.answers[question.id]; if (!answer) return;
    const row = $("#decision-template").content.cloneNode(true);
    row.querySelector(".decision-number").textContent = index + 1;
    row.querySelector(".decision-question").textContent = question.title;
    row.querySelector(".decision-answer").textContent = answer.label;
    row.querySelector("button").addEventListener("click", () => { state.index = activeQuestions().findIndex((item) => item.id === question.id); state.editing = true; showQuestion(); });
    list.appendChild(row);
  });
  updateProgress();
}

function showQuestion() {
  pruneInactiveAnswers();
  const active = activeQuestions();
  state.index = Math.max(0, Math.min(state.index, active.length - 1));
  const question = active[state.index]; showScreen($("#question-screen"));
  $("#question-kicker").textContent = question.kicker; $("#question-title").textContent = question.title; $("#question-help").textContent = question.help;
  const options = $("#answer-options"); options.innerHTML = "";
  questionOptions(question).forEach(([value, label, description]) => {
    const button = document.createElement("button"); button.className = "answer-option"; button.type = "button";
    button.innerHTML = `<strong>${label}</strong><span>${description}</span>`;
    button.addEventListener("click", () => chooseAnswer(question, value, label)); options.appendChild(button);
  });
  $("#back-button").hidden = state.index === 0;
  $("#skip-button").hidden = !question.optional;
  updateProgress();
}

async function chooseAnswer(question, value, label) {
  state.answers[question.id] = { value, label };
  state.pending.add(question.id);
  pruneInactiveAnswers(); renderDecisionTrail(); setSaveState("", "Saving this decision…");
  if (state.apiReady) {
    try { await syncPendingAnswers(); setSaveState("saved", "All decisions saved"); }
    catch (error) { state.apiReady = false; setSaveState("error", "Working locally. Secure save will retry before email."); }
  } else setSaveState("error", "Working locally. Secure save will retry before email.");

  const active = activeQuestions();
  const currentIndex = active.findIndex((item) => item.id === question.id);
  const firstMissing = active.findIndex((item) => !state.answers[item.id]);
  if (state.editing && firstMissing === -1) { state.editing = false; showResults(); return; }
  if (firstMissing === -1) { showResults(); return; }
  state.index = currentIndex >= 0 && currentIndex + 1 < active.length && !state.answers[active[currentIndex + 1].id] ? currentIndex + 1 : firstMissing;
  showQuestion();
}

function transcriptTag(boat, key, valueKey = "primary") { return (boat.transcript_attributes || []).find((item) => item.key === key && (item.value_key || "primary") === valueKey); }
function positiveTranscriptTag(boat, key, confidence = .82) { const tag = transcriptTag(boat, key); return Boolean(tag && tag.value_boolean === true && Number(tag.confidence || 0) >= confidence); }
function numericTranscriptTag(boat, key, confidence = .88) { const tag = transcriptTag(boat, key); return tag?.value_number != null && Number(tag.confidence || 0) >= confidence ? Number(tag.value_number) : null; }
function category(boat, key, confidence = .90) { return (boat.candidate_categories || []).some((item) => item.key === key && Number(item.confidence || 0) >= confidence); }
function accessSignal(boat) { return ["hydraulic_swim_platform", "folding_balconies", "beach_club", "side_boarding_door"].some((key) => positiveTranscriptTag(boat, key, .90)) || category(boat, "luxury-med-day-boat"); }
function controlSignal(boat) { return ["joystick_control", "dynamic_positioning", "bow_thruster", "stern_thruster"].some((key) => positiveTranscriptTag(boat, key, .90)); }
function rangeSignal(boat) { return positiveTranscriptTag(boat, "long_range_suitable", .88) || (positiveTranscriptTag(boat, "generator", .90) && positiveTranscriptTag(boat, "galley", .88)); }
function speedSignal(boat) { const speed = numericTranscriptTag(boat, "max_observed_speed_knots") || numericTranscriptTag(boat, "top_speed_knots"); return Boolean(speed && speed >= 28 && speed <= 80); }

function missionDetailMatch(boat, detail) {
  const f = boat.features; const protectedHelm = ["protected", "enclosed"].includes(f.helm); const offshore = f.use.includes("offshore");
  const rules = {
    "protected-family-days": [protectedHelm, "Protection for regular family days"], "easy-water-access": [accessSignal(boat), "Transcript-backed access to the water"],
    "family-weekends": [f.berths >= 2, "Practical family weekending capability"], "room-for-friends": [f.day_capacity >= 8, "Capacity for a larger regular group"],
    "offshore-fishing": [offshore && f.priorities.includes("fishing"), "Offshore capability with a fishing mission"], "coastal-fishing": [f.priorities.includes("fishing"), "A practical coastal fishing mission"],
    "walkaround-fishing": [positiveTranscriptTag(boat, "walkaround_decks", .88) || category(boat, "centre-console"), "Dan discusses practical walkaround movement"], "short-handed-fishing": [controlSignal(boat), "Controls suited to short-handed manoeuvring"],
    "water-access": [accessSignal(boat), "Transcript-backed water access"], "social-anchor": [f.day_capacity >= 9 || positiveTranscriptTag(boat, "folding_balconies", .90), "Room for social days at anchor"],
    "all-weather-active": [protectedHelm, "Weather protection without giving up active use"], "fast-day-runs": [speedSignal(boat), "Dan's test evidence supports fast day runs"],
    "all-weather-exploring": [protectedHelm && offshore, "Protected helm and open-water capability"], "range-autonomy": [rangeSignal(boat), "Transcript evidence supports greater range or autonomy"],
    "short-handed-exploring": [controlSignal(boat), "Controls support short-handed exploring"], "weekend-exploring": [f.berths >= 2, "Overnight capability for weekend exploring"],
    "protection-balance": [protectedHelm, "A useful balance of protection and day use"], "mixed-water-access": [accessSignal(boat), "Good water access for mixed use"],
    "overnight-option": [f.berths >= 2, "Keeps overnight trips available"], "social-space": [f.day_capacity >= 9 || positiveTranscriptTag(boat, "folding_balconies", .90), "A stronger social-space fit"]
  };
  return rules[detail] || [true, "Matches the way you described the mission"];
}

function evidenceProfileChips(boat) {
  const f = boat.features;
  const chips = [`${boat.length_feet} ft`, `${f.day_capacity} day capacity`, f.berths ? `${f.berths} sleeping` : "Day use", `${f.helm.replace("-", " ")} helm`];
  [["galley", "Galley confirmed"], ["separate_shower", "Separate shower"], ["folding_balconies", "Folding terraces"], ["walkaround_decks", "Walkaround decks"], ["joystick_control", "Joystick control"], ["long_range_suitable", "Long-range discussed"]]
    .forEach(([key, label]) => { if (positiveTranscriptTag(boat, key, .88)) chips.push(label); });
  return [...new Set(chips)].slice(0, 7);
}

function scoreBoats() {
  const a = Object.fromEntries(Object.entries(state.answers).map(([key, answer]) => [key, answer.value]));
  if (a.overnight === "none") { delete a.sleeping_people; delete a.overnight_duration; delete a.overnight_facilities; }
  return state.boats.map((boat) => {
    const f = boat.features; const excluded = []; const people = Number(a.people || 0); const sleeping = Number(a.sleeping_people || 0);
    if (people && people > f.day_capacity) excluded.push("capacity");
    if (a.overnight === "required" && f.berths < 2) excluded.push("overnight");
    if (sleeping && f.berths < sleeping) excluded.push("sleeping");
    if (a.overnight_duration === "extended" && !rangeSignal(boat)) excluded.push("autonomy");
    if (a.overnight_facilities === "galley" && !positiveTranscriptTag(boat, "galley", .88)) excluded.push("galley");
    if (a.overnight_facilities === "shower" && !positiveTranscriptTag(boat, "separate_shower", .90)) excluded.push("shower");
    if (a.storage === "trailer" && !f.trailerable) excluded.push("trailer");
    if (a.helm === "enclosed" && f.helm !== "enclosed") excluded.push("helm");
    if (a.helm === "protected" && f.helm === "open") excluded.push("helm");
    if (a.helm === "open" && f.helm === "enclosed") excluded.push("helm");
    if (a.water === "offshore" && !f.use.includes("offshore")) excluded.push("water");
    if (a.water === "coastal" && !["coastal", "offshore"].some((value) => f.use.includes(value))) excluded.push("water");
    if (a.priority && a.priority !== "mixed-use" && !f.priorities.includes(a.priority)) excluded.push("mission");
    if (a.priority === "mixed-use" && f.priorities.length < 2) excluded.push("mission");
    const [detailFits, detailReason] = missionDetailMatch(boat, a.mission_detail); if (a.mission_detail && !detailFits) excluded.push("mission detail");
    let low; let high;
    if (a.length && a.length !== "unspecified") { [low, high] = a.length.split("-").map(Number); if (boat.length_feet < low - 4 || boat.length_feet > high + 4) excluded.push("length"); }
    if (excluded.length) return null;

    let earned = 0; let possible = 0; const reasons = [];
    const award = (points, fraction, reason) => { possible += points; earned += points * Math.max(0, Math.min(fraction, 1)); if (reason && fraction >= .72) reasons.push(reason); };
    if (people) award(8, 1, `Carries your usual day party of ${people}`);
    if (a.overnight === "none") award(12, f.berths === 0 ? 1 : .38, f.berths === 0 ? "A purposeful day-boat layout" : null);
    else if (a.overnight === "optional") award(12, f.berths >= Math.max(sleeping, 2) ? 1 : .25, "Keeps occasional overnighting open");
    else if (a.overnight === "required") award(12, 1, "Provides the overnight capability you require");
    if (sleeping) award(16, 1, `Provides sleeping capacity for ${sleeping}`);
    if (a.overnight_duration) award(9, a.overnight_duration !== "extended" || rangeSignal(boat) ? 1 : 0, a.overnight_duration === "extended" ? "Transcript evidence supports longer stays" : "Suits the trip length you selected");
    if (a.overnight_facilities) { const fit = a.overnight_facilities === "basic" ? f.berths >= 2 : a.overnight_facilities === "galley" ? positiveTranscriptTag(boat, "galley", .88) : positiveTranscriptTag(boat, "separate_shower", .90); const reason = { basic: "A practical berth without unnecessary systems", galley: "Dan confirms a galley aboard", shower: "Dan confirms a separate shower" }[a.overnight_facilities]; award(10, fit ? 1 : 0, reason); }
    if (a.helm) award(13, f.helm === a.helm ? 1 : (a.helm === "protected" && f.helm === "enclosed" ? .82 : .68), `Matches your ${a.helm.replace("-", " ")} helm requirement`);
    if (a.water) award(14, f.use.includes(a.water) ? 1 : (a.water === "sheltered" ? .78 : 0), `Evidence supports the ${a.water} use you selected`);
    if (a.priority) award(15, f.priorities.includes(a.priority) ? 1 : (a.priority === "mixed-use" ? .88 : 0), `Editorial mission profile supports ${a.priority.replace("-", " ")}`);
    if (a.mission_detail) award(13, detailFits ? 1 : 0, detailReason);
    if (a.storage) award(8, a.storage !== "trailer" || f.trailerable ? 1 : 0, a.storage === "trailer" ? "Fits the trailering requirement" : "Compatible with the storage plan you selected");
    if (a.length && a.length !== "unspecified") { const exact = boat.length_feet >= low && boat.length_feet <= high; award(11, exact ? 1 : .55, exact ? "Falls inside your preferred length range" : "A nearby size worth comparing"); }
    const fit = possible ? earned / possible : .5;
    const total = fit * .82 + boat.evidence_confidence * .10 + boat.audience_percentile * .04 + boat.market_percentile * .04;
    const preferred = [];
    if (a.mission_detail) preferred.push(detailReason);
    if (sleeping) preferred.push(`Provides sleeping capacity for ${sleeping}`);
    if (a.overnight_facilities) preferred.push({ basic: "A practical berth without unnecessary systems", galley: "Dan confirms a galley aboard", shower: "Dan confirms a separate shower" }[a.overnight_facilities]);
    if (a.water) preferred.push(`Evidence supports the ${a.water} use you selected`);
    return { ...boat, score: total, reasons: [...new Set([...preferred, ...reasons])].slice(0, 4) };
  }).filter(Boolean).sort((x, y) => y.score - x.score).slice(0, 5);
}

function showResults() {
  showScreen($("#results-screen")); updateProgress(); const cards = $("#result-cards"); cards.innerHTML = "";
  const results = scoreBoats();
  results.forEach((boat, index) => {
    const card = $("#result-template").content.cloneNode(true); card.querySelector(".rank-badge").textContent = index + 1;
    const image = card.querySelector(".result-image"); image.src = boat.thumbnail; image.alt = `${boat.full_name} video thumbnail`; image.loading = "lazy";
    card.querySelector(".result-make").textContent = boat.make; card.querySelector(".result-name").textContent = boat.full_name;
    card.querySelector(".match-score").textContent = `${Math.round(boat.score * 100)}% fit`;
    const reasons = card.querySelector(".match-reasons"); boat.reasons.forEach((reason) => { const li = document.createElement("li"); li.textContent = reason; reasons.appendChild(li); });
    const profile = card.querySelector(".boat-tags"); const profileList = profile.querySelector("ul");
    evidenceProfileChips(boat).forEach((tag) => { const li = document.createElement("li"); li.textContent = tag; profileList.appendChild(li); });
    profile.hidden = !profileList.children.length;
    card.querySelector(".watch-out p").textContent = boat.watch_out;
    const transcriptEvidence = card.querySelector(".transcript-evidence"); const evidenceList = transcriptEvidence.querySelector("ul");
    (boat.evidence || []).forEach((claim) => {
      const li = document.createElement("li"); const link = document.createElement("a");
      link.href = claim.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = `${claim.topic.replaceAll("_", " ")} · ${Math.floor(claim.start_seconds / 60)}:${String(claim.start_seconds % 60).padStart(2, "0")}`;
      const quote = document.createElement("span"); quote.textContent = `“${claim.excerpt}”`; li.append(link, quote); evidenceList.appendChild(li);
    });
    transcriptEvidence.hidden = !evidenceList.children.length;
    const links = card.querySelector(".evidence-links"); boat.videos.forEach((video) => { const link = document.createElement("a"); link.href = `https://www.youtube.com/watch?v=${video.id}`; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = `Watch ${video.type.toLowerCase()}`; links.appendChild(link); });
    cards.appendChild(card);
  });
  if (!results.length) cards.innerHTML = '<div class="no-match"><h2>No reliable match for every hard requirement yet.</h2><p>That is more useful than forcing the same popular boat into every search. Edit one of your decisions or save the brief so the catalogue can be expanded against it.</p></div>';
}

$("#start-button").addEventListener("click", () => { state.editing = false; showQuestion(); });
$("#back-button").addEventListener("click", () => { if (state.index > 0) { state.index -= 1; showQuestion(); } });
$("#skip-button").addEventListener("click", () => chooseAnswer(activeQuestions()[state.index], "unspecified", "Prefer not to say"));
$("#restart-button").addEventListener("click", async () => {
  if (!confirm("Start a new guide? Your existing emailed resume link will still work.")) return;
  history.replaceState({}, "", location.pathname); state.answers = {}; state.pending.clear(); state.index = 0; state.sessionId = null; state.token = null; state.apiReady = false;
  renderDecisionTrail(); showScreen($("#intro-screen"));
  try { await startSession(); } catch (error) { setSaveState("error", "Working locally. Secure save will retry before email."); }
});

$("#completion-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget; const button = form.querySelector("button[type=submit]"); const message = $("#completion-message");
  message.className = "completion-message"; message.textContent = "Connecting secure save and preparing your guide…"; button.disabled = true; button.textContent = "Connecting and saving…";
  const data = Object.fromEntries(new FormData(form)); data.marketing_consent = form.elements.marketing_consent.checked;
  try {
    await ensureConnected();
    const completed = await api(`/api/sessions/${state.sessionId}/complete`, { method: "POST", headers: sessionHeaders(), body: JSON.stringify(data) });
    message.className += " success";
    if (completed.email_status === "sent") message.textContent = "Your guide is on its way.";
    else { message.textContent = "Your guide is saved. Email delivery is queued. "; const link = document.createElement("a"); link.href = completed.resume_url; link.textContent = "Open your private resume link"; message.appendChild(link); }
    button.textContent = "Guide saved";
  } catch (error) {
    state.apiReady = false; message.className += " error"; message.textContent = "The secure guide service did not reconnect. Your answers are still on this screen. Please click the button to retry.";
    button.disabled = false; button.textContent = "Retry email and save";
  }
});

async function init() {
  state.boats = await fetch("data/boats.json").then((response) => response.json());
  try {
    await startSession(); pruneInactiveAnswers(); renderDecisionTrail();
    const active = activeQuestions(); const firstMissing = active.findIndex((question) => !state.answers[question.id]);
    if (firstMissing === -1 && Object.keys(state.answers).length) showResults();
    else if (Object.keys(state.answers).length) { state.index = Math.max(firstMissing, 0); showQuestion(); }
  } catch (error) { state.apiReady = false; setSaveState("error", "Working locally. Secure save will retry before email."); renderDecisionTrail(); }
}

init();
