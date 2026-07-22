const config = window.DBL_GUIDE_CONFIG || { apiBase: "" };
const apiBase = config.apiBase.replace(/\/$/, "");

const questions = [
  { id: "country", kicker: "Your market", title: "Where will you buy and keep the boat?", help: "Country affects availability, prices and which sold-boat evidence is relevant.", options: [
    ["AU", "Australia", "Use Australian market evidence where available"], ["US", "United States", "Use United States market evidence"],
    ["GB", "United Kingdom", "Use UK market evidence"], ["NZ", "New Zealand", "Use New Zealand market evidence"],
    ["EU", "Europe", "We will ask for the exact country before emailing"], ["OTHER", "Somewhere else", "We will keep recommendations global until qualified"]
  ]},
  { id: "water", kicker: "Your boating", title: "What sort of water will you use most?", help: "Choose the hardest conditions you expect to use regularly, not a once-a-year ambition.", options: [
    ["sheltered", "Sheltered water", "Harbours, rivers and protected bays"], ["coastal", "Coastal", "Day runs along the coast with sensible weather windows"],
    ["offshore", "Offshore", "Open-water passages and more exposed conditions"]
  ]},
  { id: "overnight", kicker: "Time aboard", title: "Does the boat need to handle overnight trips?", help: "This is a meaningful fork. Proper sleeping capability removes many open day boats.", options: [
    ["none", "No, day use only", "Keep the layout focused on the day"], ["optional", "Nice to have", "An occasional night without building the whole decision around it"],
    ["required", "Yes, it is essential", "Practical accommodation is a hard requirement"]
  ]},
  { id: "people", kicker: "Your crew", title: "How many people are normally aboard?", help: "Use your typical group rather than the maximum number you might carry once.", options: [
    ["2", "One or two", "Mostly a couple or solo use"], ["4", "Three or four", "A couple, children or close friends"],
    ["6", "Five or six", "Regular family and friends"], ["8", "Seven or eight", "A larger regular group"]
  ]},
  { id: "helm", kicker: "Weather protection", title: "How protected should the helm be?", help: "This changes how and when the boat can be used more than many buyers expect.", options: [
    ["open", "Open", "Maximum connection to the day and weather"], ["protected", "Protected", "A windscreen, hardtop or substantial shelter"],
    ["enclosed", "Fully enclosed", "A proper cabin or wheelhouse around the helm"]
  ]},
  { id: "storage", kicker: "Ownership reality", title: "Where will the boat live?", help: "A brilliant boat is the wrong boat if its storage and handling do not fit your life.", options: [
    ["trailer", "On a trailer", "Trailerability is a hard requirement"], ["dry-stack", "Dry stack", "Crane and facility limits matter"],
    ["marina", "Marina berth", "No trailering requirement"], ["unsure", "Not sure yet", "Keep all storage options open"]
  ]},
  { id: "priority", kicker: "Main mission", title: "What should the boat do particularly well?", help: "Mixed use is fine, but one priority helps separate close alternatives.", options: [
    ["family", "Family time", "Comfort, access and flexible social space"], ["fishing", "Fishing", "Working space, access and practical movement"],
    ["watersports", "Watersports", "Swimming, toys and energetic day use"], ["exploring", "Exploring", "Weather range, independence and purposeful travel"],
    ["mixed-use", "A genuine mix", "Avoid over-specialising the recommendation"]
  ]},
  { id: "length", kicker: "Practical size", title: "What length range feels realistic?", help: "This is a starting range, not a sales filter. Your other answers may expose a nearby alternative.", options: [
    ["20-29", "20-29 feet", "Compact and easier to store"], ["30-34", "30-34 feet", "A useful middle ground"],
    ["35-39", "35-39 feet", "More space and capability"], ["40-50", "40-50 feet", "Larger systems and accommodation"]
  ]},
  { id: "budget", kicker: "Price qualification", title: "What budget band are you working within?", help: "Optional for now. We store the answer but only use it as a filter where regional sold-price evidence is reliable.", optional: true, options: [
    ["under-150", "Under 150k", "In your local currency"], ["150-300", "150k-300k", "In your local currency"],
    ["300-600", "300k-600k", "In your local currency"], ["600-plus", "600k+", "In your local currency"],
    ["unsure", "Not sure yet", "Do not price-filter my shortlist"]
  ]},
  { id: "condition", kicker: "Buying preference", title: "Are you considering new or used?", help: "This helps us make the sales evidence and later follow-up more relevant.", optional: true, options: [
    ["new", "New", "Current-model availability matters most"], ["used", "Used", "Sold-market depth matters most"],
    ["either", "Either", "Show the best fit regardless of age"]
  ]},
  { id: "timing", kicker: "Timing", title: "When are you realistically looking to buy?", help: "This does not change the boat fit. It helps make future information more useful.", optional: true, options: [
    ["now", "Right now", "Actively comparing"], ["3-months", "Within three months", "A near-term decision"],
    ["6-months", "Three to six months", "Still narrowing the field"], ["later", "More than six months", "Early research"]
  ]}
];

const state = { index: 0, answers: {}, sessionId: null, token: null, resumeUrl: null, boats: [], apiReady: false };
const $ = (selector) => document.querySelector(selector);
const screens = [$("#intro-screen"), $("#question-screen"), $("#results-screen")];

function showScreen(target) { screens.forEach((screen) => { screen.hidden = screen !== target; }); window.scrollTo({ top: 0, behavior: "smooth" }); }
function setSaveState(kind, text) { const el = $("#save-state"); el.className = `save-state ${kind}`; el.querySelector("span:last-child").textContent = text; }
function sessionHeaders() { return { "Content-Type": "application/json", "X-Resume-Token": state.token }; }

async function api(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, options);
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Request failed");
  return response.json();
}

async function startSession() {
  const params = new URLSearchParams(location.search);
  const fragment = new URLSearchParams(location.hash.replace(/^#/, ""));
  const existingId = params.get("session"); const existingToken = fragment.get("token");
  try {
    if (existingId && existingToken) {
      state.sessionId = existingId; state.token = existingToken;
      const saved = await api(`/api/sessions/${existingId}`, { headers: { "X-Resume-Token": existingToken } });
      state.answers = saved.answers || {}; state.apiReady = true;
      setSaveState("saved", "Saved guide restored"); renderDecisionTrail();
      if (questions.every((question) => state.answers[question.id])) { showResults(); }
      else if (Object.keys(state.answers).length) { state.index = Math.min(Object.keys(state.answers).length, questions.length - 1); showQuestion(); }
      return;
    }
    const created = await api("/api/sessions", { method: "POST" });
    state.sessionId = created.public_id; state.token = created.resume_token; state.resumeUrl = created.resume_url; state.apiReady = true;
    history.replaceState({}, "", `${location.pathname}?session=${created.public_id}#token=${created.resume_token}`);
    setSaveState("saved", "Progress saves automatically");
  } catch (error) {
    state.apiReady = false;
    setSaveState("error", "Preview mode: connect the guide database to save progress");
  }
}

function updateProgress() {
  const answered = Object.keys(state.answers).length;
  $("#progress-count").textContent = `${Math.min(answered, questions.length)} of ${questions.length}`;
  $("#progress-label").textContent = answered ? "Building your brief" : "Getting started";
  $("#progress-bar").style.width = `${(answered / questions.length) * 100}%`;
}

function renderDecisionTrail() {
  const list = $("#decision-list"); list.innerHTML = "";
  questions.forEach((question, index) => {
    const answer = state.answers[question.id]; if (!answer) return;
    const row = $("#decision-template").content.cloneNode(true);
    row.querySelector(".decision-number").textContent = index + 1;
    row.querySelector(".decision-question").textContent = question.title;
    row.querySelector(".decision-answer").textContent = answer.label;
    row.querySelector("button").addEventListener("click", () => { state.index = index; showQuestion(); });
    list.appendChild(row);
  });
  updateProgress();
}

function showQuestion() {
  const question = questions[state.index]; showScreen($("#question-screen"));
  $("#question-kicker").textContent = question.kicker; $("#question-title").textContent = question.title; $("#question-help").textContent = question.help;
  const options = $("#answer-options"); options.innerHTML = "";
  question.options.forEach(([value, label, description]) => {
    const button = document.createElement("button"); button.className = "answer-option"; button.type = "button";
    button.innerHTML = `<strong>${label}</strong><span>${description}</span>`;
    button.addEventListener("click", () => chooseAnswer(question, value, label)); options.appendChild(button);
  });
  $("#back-button").hidden = state.index === 0;
  $("#skip-button").hidden = !question.optional;
  updateProgress();
}

async function chooseAnswer(question, value, label) {
  state.answers[question.id] = { value, label }; renderDecisionTrail(); setSaveState("", "Saving this decision…");
  if (state.apiReady) {
    try {
      await api(`/api/sessions/${state.sessionId}/decisions`, { method: "POST", headers: sessionHeaders(), body: JSON.stringify({ question_id: question.id, answer_value: value, answer_label: label }) });
      setSaveState("saved", "All decisions saved");
    } catch (error) { setSaveState("error", "Could not save. Your on-screen answers are still here"); }
  } else {
    setSaveState("error", "Preview mode: connect the guide database to save progress");
  }
  if (questions.every((item) => state.answers[item.id])) { showResults(); }
  else if (state.index < questions.length - 1) { state.index += 1; showQuestion(); }
  else { showResults(); }
}

function scoreBoats() {
  const a = Object.fromEntries(Object.entries(state.answers).map(([key, answer]) => [key, answer.value]));
  return state.boats.map((boat) => {
    const f = boat.features; const excluded = [];
    if (a.overnight === "required" && f.berths < 2) excluded.push("overnight");
    if (Number(a.people || 4) > f.day_capacity) excluded.push("capacity");
    if (a.storage === "trailer" && !f.trailerable) excluded.push("trailer");
    if (a.helm === "enclosed" && f.helm !== "enclosed") excluded.push("helm");
    if (a.water === "offshore" && !f.use.includes("offshore")) excluded.push("water");
    if (excluded.length) return null;
    let fit = 0; const reasons = [];
    if (a.overnight === "required" && f.berths >= 2) { fit += 20; reasons.push(`Provides practical overnight capability for ${f.berths}`); }
    else if (a.overnight === "optional" && f.berths) { fit += 12; reasons.push("Keeps occasional overnighting open"); }
    else if (a.overnight === "none" && f.berths === 0) { fit += 12; reasons.push("Purposeful day-boat layout"); }
    if (a.helm === f.helm) { fit += 14; reasons.push(`Matches your ${f.helm.replace("-", " ")} helm preference`); }
    if (a.water && f.use.includes(a.water)) { fit += 18; reasons.push(`Supported for the ${a.water} use you selected`); }
    if (a.priority && f.priorities.includes(a.priority)) { fit += 18; reasons.push(`Strong fit for ${a.priority.replace("-", " ")} use`); }
    if (a.storage === "trailer" && f.trailerable) { fit += 12; reasons.push("Fits the trailering requirement"); }
    if (a.length) { const [low, high] = a.length.split("-").map(Number); if (boat.length_feet >= low && boat.length_feet <= high) { fit += 10; reasons.push("Inside your preferred length range"); } }
    const total = Math.min(fit / 92, 1) * .55 + boat.evidence_confidence * .20 + boat.audience_percentile * .15 + boat.market_percentile * .10;
    return { ...boat, score: total, reasons: reasons.slice(0, 3) };
  }).filter(Boolean).sort((x, y) => y.score - x.score).slice(0, 5);
}

function showResults() {
  showScreen($("#results-screen")); updateProgress(); const cards = $("#result-cards"); cards.innerHTML = "";
  const results = scoreBoats();
  results.forEach((boat, index) => {
    const card = $("#result-template").content.cloneNode(true); card.querySelector(".rank-badge").textContent = index + 1;
    const image = card.querySelector(".result-image"); image.src = boat.thumbnail; image.alt = `${boat.full_name} video thumbnail`;
    card.querySelector(".result-make").textContent = boat.make; card.querySelector(".result-name").textContent = boat.full_name;
    card.querySelector(".match-score").textContent = `${Math.round(boat.score * 100)}% fit`;
    const reasons = card.querySelector(".match-reasons"); boat.reasons.forEach((reason) => { const li = document.createElement("li"); li.textContent = reason; reasons.appendChild(li); });
    card.querySelector(".watch-out p").textContent = boat.watch_out;
    const transcriptEvidence = card.querySelector(".transcript-evidence");
    const evidenceList = transcriptEvidence.querySelector("ul");
    (boat.evidence || []).forEach((claim) => {
      const li = document.createElement("li"); const link = document.createElement("a");
      link.href = claim.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = `${claim.topic.replaceAll("_", " ")} · ${Math.floor(claim.start_seconds / 60)}:${String(claim.start_seconds % 60).padStart(2, "0")}`;
      const quote = document.createElement("span"); quote.textContent = `“${claim.excerpt}”`;
      li.append(link, quote); evidenceList.appendChild(li);
    });
    transcriptEvidence.hidden = !evidenceList.children.length;
    const links = card.querySelector(".evidence-links"); boat.videos.forEach((video) => { const a = document.createElement("a"); a.href = `https://www.youtube.com/watch?v=${video.id}`; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = `Watch ${video.type.toLowerCase()}`; links.appendChild(a); });
    cards.appendChild(card);
  });
  if (!results.length) cards.innerHTML = '<div class="email-panel"><div><h2>Not enough reliable matches yet.</h2><p>Your brief is specific. That is useful, not a reason to force an unsuitable recommendation. Save it and Dan can use it to expand the evidence.</p></div></div>';
}

$("#start-button").addEventListener("click", showQuestion);
$("#back-button").addEventListener("click", () => { if (state.index > 0) { state.index -= 1; showQuestion(); } });
$("#skip-button").addEventListener("click", () => chooseAnswer(questions[state.index], "unspecified", "Prefer not to say"));
$("#restart-button").addEventListener("click", async () => { if (!confirm("Start a new guide? Your existing emailed resume link will still work.")) return; history.replaceState({}, "", location.pathname); state.answers = {}; state.index = 0; state.sessionId = null; state.token = null; renderDecisionTrail(); showScreen($("#intro-screen")); await startSession(); });

$("#completion-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget; const button = form.querySelector("button[type=submit]"); const message = $("#completion-message");
  message.className = "completion-message"; button.disabled = true; button.textContent = "Saving and preparing…";
  if (!state.apiReady) { message.className += " error"; message.textContent = "The guide database is not connected in this preview, so your private resume email cannot be sent yet."; button.disabled = false; button.textContent = "Email my full guide"; return; }
  const data = Object.fromEntries(new FormData(form)); data.marketing_consent = form.elements.marketing_consent.checked;
  try {
    const completed = await api(`/api/sessions/${state.sessionId}/complete`, { method: "POST", headers: sessionHeaders(), body: JSON.stringify(data) });
    message.className += " success"; message.innerHTML = completed.email_status === "sent" ? "Your guide is on its way." : `Your guide is saved. Email delivery is queued. <a href="${completed.resume_url}">Copy your private resume link now</a>.`;
    button.textContent = "Guide saved";
  } catch (error) { message.className += " error"; message.textContent = "We could not save the final guide. Please try again."; button.disabled = false; button.textContent = "Email my full guide"; }
});

async function init() {
  state.boats = await fetch("data/boats.json").then((response) => response.json());
  await startSession(); renderDecisionTrail();
}

init();
