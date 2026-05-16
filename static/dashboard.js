const $ = (sel) => document.querySelector(sel);

async function fetchJSON(url, options) {
  const r = await fetch(url, options);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

function setBadge(el, on, label) {
  el.textContent = label;
  el.classList.toggle("badge--on", !!on);
  el.classList.toggle("badge--off", !on);
}

function renderEvents(list) {
  const ul = $("#events");
  ul.innerHTML = "";
  if (!list.length) {
    const li = document.createElement("li");
    li.textContent = "Sem eventos ainda.";
    li.style.color = "#8a93a3";
    ul.appendChild(li);
    return;
  }
  for (const e of list) {
    const li = document.createElement("li");
    if (e.image_path) {
      const img = document.createElement("img");
      img.src = e.image_path;
      img.alt = e.label;
      li.appendChild(img);
    }
    const meta = document.createElement("div");
    meta.className = "e-meta";
    const label = document.createElement("div");
    label.className = "e-label";
    label.textContent = e.label;
    const time = document.createElement("div");
    time.className = "e-time";
    time.textContent = e.event_time;
    const conf = document.createElement("div");
    conf.className = "e-conf";
    conf.textContent = `conf ${Number(e.confidence).toFixed(2)}`;
    meta.append(label, time, conf);
    li.appendChild(meta);
    ul.appendChild(li);
  }
}

async function refreshCamera() {
  try {
    const s = await fetchJSON("/camera/status");
    setBadge($("#badge-camera"), s.connected, `câmera: ${s.connected ? "online" : "offline"}`);
    $("#m-frames").textContent = s.frames_read;
    $("#m-events").textContent = s.events_saved;
    $("#m-source").textContent = s.source_type;
  } catch {
    setBadge($("#badge-camera"), false, "câmera: erro");
  }
}

async function refreshAgent() {
  try {
    const s = await fetchJSON("/agent/status");
    setBadge($("#badge-ollama"), s.ollama_online, `ollama: ${s.ollama_online ? "online" : "offline"}`);
    $("#badge-model").textContent = `modelo: ${s.model}`;
    renderEvents(s.recent_events || []);
  } catch {
    setBadge($("#badge-ollama"), false, "ollama: erro");
  }
}

async function refreshWeather() {
  const box = $("#weather");
  if (!box) return;
  const main = box.querySelector(".weather-main");
  const meta = box.querySelector(".weather-meta");
  try {
    const data = await fetchJSON("/external/weather");
    if (!data.available || !data.snapshot) {
      main.textContent = "--";
      meta.textContent = data.reason || "sem snapshot disponivel";
      return;
    }
    const w = data.snapshot;
    main.textContent = `${Number(w.temperature_c).toFixed(1)}°C · ${w.condition}`;
    meta.textContent = `umidade ${w.humidity_percent}% · vento ${Number(w.wind_speed_kmh).toFixed(1)} km/h · ${w.source}`;
  } catch {
    main.textContent = "--";
    meta.textContent = "falha ao consultar clima";
  }
}

function appendMsg(text, kind) {
  const log = $("#chat-log");
  const div = document.createElement("div");
  div.className = `chat-msg chat-msg--${kind}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

$("#chat-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const input = $("#chat-input");
  const button = ev.target.querySelector("button");
  const message = input.value.trim();
  if (!message) return;
  appendMsg(message, "user");
  input.value = "";
  button.disabled = true;
  try {
    const r = await fetchJSON("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    appendMsg(r.reply, "bot");
  } catch (e) {
    appendMsg(`Erro ao falar com o agente: ${e.message}`, "err");
  } finally {
    button.disabled = false;
    input.focus();
  }
});

refreshCamera();
refreshAgent();
refreshWeather();
setInterval(refreshCamera, 2000);
setInterval(refreshAgent, 5000);
setInterval(refreshWeather, 10 * 60 * 1000);
