(function () {
  "use strict";

  const API_BASE = "";

  const store = {
    session_id: null,
    status: {
      turn_current: 0,
      turn_max: 10,
      current_speaker: "",
      player_can_write: false,
      game_finished: false,
      result: null,
      messages: [],
    },
    context: {
      player_mission: "",
      characters: [],
      narrativa_inicial: "",
    },
    messages: [],
    error: null,
    streamingMessage: null,
    streamingNode: null,
  };

  const $ = (id) => document.getElementById(id);

  function safeGetItem(key, defaultValue) {
    try {
      const v = localStorage.getItem(key);
      return v !== null ? v : defaultValue;
    } catch (_) {
      return defaultValue;
    }
  }
  function safeSetItem(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_) {}
  }

  const $chat = () => $("chat");
  const $errorBanner = () => $("error-banner");
  const $intro = () => $("intro-text");
  const $mission = () => $("mission-text");
  const $characters = () => $("characters-list");
  const $gameState = () => $("game-state");
  const $playerInput = () => $("player-input");
  const $btnSend = () => $("btn-send");
  const $btnNew = () => $("btn-new-game");
  const $btnReset = () => $("btn-reset");
  const $loadingOverlay = () => $("loading-overlay");
  const $loadingMessage = () => $("loading-message");
  const $newGameModal = () => $("new-game-modal");
  const $btnCreateGame = () => $("btn-create-game");
  const $btnCancelNewGame = () => $("btn-cancel-new-game");
  const $seedEra = () => $("seed-era");
  const $seedTopic = () => $("seed-topic");
  const $seedStyle = () => $("seed-style");
  const $seedNumActors = () => $("seed-num-actors");

  function showLoading(message) {
    const msg = message || "Procesando…";
    const el = $loadingMessage();
    if (el) el.textContent = msg;
    const overlay = $loadingOverlay();
    if (overlay) overlay.classList.remove("hidden");
  }

  function hideLoading() {
    const overlay = $loadingOverlay();
    if (overlay) overlay.classList.add("hidden");
  }

  function showError(msg) {
    store.error = msg;
    const el = $errorBanner();
    if (el) {
      el.textContent = msg;
      el.classList.remove("hidden");
    }
  }

  function clearError() {
    store.error = null;
    const el = $errorBanner();
    if (el) el.classList.add("hidden");
  }

  function apiUrl(path, params) {
    const url = new URL(path, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }
    return url.pathname + url.search;
  }

  async function apiGet(path, params) {
    const url = API_BASE + apiUrl(path, params);
    const res = await fetch(url);
    if (res.status === 404) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Sesión no encontrada");
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Error ${res.status}`);
    }
    return res.json();
  }

  function openNewGameModal() {
    const modal = $newGameModal();
    if (!modal) return;
    modal.classList.remove("hidden");
    const era = $seedEra();
    if (era) era.focus();
  }

  function closeNewGameModal() {
    const modal = $newGameModal();
    if (!modal) return;
    modal.classList.add("hidden");
  }

  function buildSeedPayloadFromForm() {
    const era = (($seedEra() && $seedEra().value) || "").trim();
    const topic = (($seedTopic() && $seedTopic().value) || "").trim();
    const style = (($seedStyle() && $seedStyle().value) || "").trim();
    const numActorsRaw = (($seedNumActors() && $seedNumActors().value) || "").trim();

    if (era.length > 200 || topic.length > 200 || style.length > 200) {
      return { error: "Cada campo de texto permite como máximo 200 caracteres." };
    }

    const hasTextSeed = !!(era || topic || style);
    const hasNumActors = numActorsRaw !== "";
    const payload = {};

    if (hasTextSeed) {
      const parts = [];
      if (era) parts.push(`Época/contexto: ${era}`);
      if (topic) parts.push(`Tema: ${topic}`);
      if (style) parts.push(`Estilo: ${style}`);
      payload.theme = parts.join(" | ");
    }

    if (hasNumActors) {
      const parsed = Number(numActorsRaw);
      if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5) {
        return { error: "El número de personajes debe ser un entero entre 1 y 5." };
      }
      payload.num_actors = parsed;
    }

    return { payload };
  }

  async function postNewGame(payload = {}) {
    clearError();
    showLoading("Creando partida…");
    try {
      const url = API_BASE + "/game/new";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Error ${res.status}`);
      }
      const data = await res.json();
      store.session_id = data.session_id;
      store.context.narrativa_inicial = data.narrativa_inicial || "";
      store.context.player_mission = data.player_mission || "";
      store.context.characters = data.characters || [];
      store.status.turn_current = data.turn_current ?? 0;
      store.status.turn_max = data.turn_max ?? 10;
      store.status.player_can_write = data.player_can_write ?? false;
      store.status.game_finished = false;
      store.status.result = null;
      store.messages = [];
      await fetchContext();
      await fetchStatus();
      renderAll();
      return true;
    } catch (e) {
      showError(e.message || "Error al crear partida");
      return false;
    } finally {
      hideLoading();
    }
  }

  async function submitNewGameFromForm() {
    const built = buildSeedPayloadFromForm();
    if (built.error) {
      showError(built.error);
      return;
    }
    const ok = await postNewGame(built.payload || {});
    if (!ok) return;
    closeNewGameModal();
  }

  async function fetchContext() {
    if (!store.session_id) return;
    try {
      const data = await apiGet("/game/context", { session_id: store.session_id });
      store.context.player_mission = data.player_mission || "";
      store.context.characters = data.characters || [];
      store.context.narrativa_inicial = data.narrativa_inicial || "";
    } catch (e) {
      showError(e.message || "Error al cargar contexto");
    }
  }

  async function fetchStatus() {
    if (!store.session_id) return;
    try {
      const data = await apiGet("/game/status", { session_id: store.session_id });
      store.status.turn_current = data.turn_current ?? 0;
      store.status.turn_max = data.turn_max ?? 10;
      store.status.current_speaker = data.current_speaker || "";
      store.status.player_can_write = data.player_can_write ?? false;
      store.status.game_finished = data.game_finished ?? false;
      store.status.result = data.result ?? null;
      store.status.messages = data.messages || [];
      store.messages = store.status.messages.map((m) => ({
        author: m.author,
        content: m.content,
        isSystem: m.author === "Sistema" || m.author === "system",
        isPlayer: m.author === "Usuario",
      }));
      renderAll();
    } catch (e) {
      showError(e.message || "Sesión no encontrada");
      store.session_id = null;
      renderAll();
    }
  }

  function renderSidebar() {
    const intro = $intro();
    const mission = $mission();
    const charactersEl = $characters();
    const gameStateEl = $gameState();
    if (intro) intro.textContent = store.context.narrativa_inicial || "—";
    if (mission) mission.textContent = store.context.player_mission || "—";
    const chars = store.context.characters || [];
    if (charactersEl) charactersEl.innerHTML = chars.length
      ? chars
          .map(
            (c) =>
              `<div class="char-item"><strong>${escapeHtml(c.name)}</strong>${c.personality ? "<br>" + escapeHtml(c.personality) : ""}</div>`
          )
          .join("")
      : "—";

    const s = store.status;
    let stateHtml = "";
    if (store.session_id) {
      stateHtml = `
        <dl>
          <dt>Turno</dt><dd>${s.turn_current} / ${s.turn_max}</dd>
          <dt>Habla</dt><dd>${escapeHtml(s.current_speaker) || "—"}</dd>
          <dt>Puedes escribir</dt><dd>${s.player_can_write ? "Sí" : "No"}</dd>
          <dt>Partida terminada</dt><dd>${s.game_finished ? "Sí" : "No"}</dd>
        </dl>
      `;
      if (s.result) {
        stateHtml += `<p><strong>Resultado:</strong> ${escapeHtml(s.result.reason || "")}</p>`;
        if (s.result.mission_evaluation) {
          stateHtml += `<pre>${escapeHtml(JSON.stringify(s.result.mission_evaluation, null, 2))}</pre>`;
        }
      }
    } else {
      stateHtml = "<p>Sin partida activa.</p>";
    }
    $gameState().innerHTML = stateHtml;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function msgClass(msg) {
    if (msg.isSystem) return "msg msg-system";
    if (msg.isPlayer) return "msg msg-player";
    return "msg msg-agent";
  }

  function renderChat() {
    const chat = $chat();
    if (!chat) return;
    chat.innerHTML = "";

    const list = store.streamingMessage
      ? [...store.messages, { ...store.streamingMessage, streaming: true }]
      : store.messages;

    list.forEach((msg, i) => {
      const div = document.createElement("div");
      div.className = msgClass(msg) + (msg.streaming ? " msg-streaming" : "");
      div.dataset.index = String(i);
      div.innerHTML = `
        <div class="msg-author">${escapeHtml(msg.author)}</div>
        <div class="msg-content">${escapeHtml(msg.content)}</div>
      `;
      chat.appendChild(div);
      if (msg.streaming) store.streamingNode = div.querySelector(".msg-content");
    });

    if (!store.streamingMessage) store.streamingNode = null;
    if (store.streamingNode) store.streamingNode.scrollIntoView({ behavior: "smooth" });
  }

  function updateStreamingContent(text) {
    if (store.streamingNode) {
      store.streamingNode.textContent = text;
      store.streamingNode.scrollIntoView({ behavior: "smooth" });
    }
  }

  function updateInputState() {
    const s = store.status;
    const canWrite = store.session_id && s.player_can_write && !s.game_finished;
    $playerInput().disabled = !canWrite;
    $btnSend().disabled = !canWrite;
  }

  function renderAll() {
    renderSidebar();
    renderChat();
    updateInputState();
  }

  function resetPartida() {
    clearError();
    store.session_id = null;
    store.status = {
      turn_current: 0,
      turn_max: 10,
      current_speaker: "",
      player_can_write: false,
      game_finished: false,
      result: null,
      messages: [],
    };
    store.context = { player_mission: "", characters: [], narrativa_inicial: "" };
    store.messages = [];
    store.streamingMessage = null;
    store.streamingNode = null;
    renderAll();
  }

  async function sendTurn() {
    const inputEl = $playerInput();
    const text = (inputEl && inputEl.value ? inputEl.value : "").trim();
    if (!store.session_id) {
      showError("No hay partida activa. Crea una nueva partida.");
      return;
    }
    if (!text) return;

    const userMsg = {
      author: "Usuario",
      content: text,
      isPlayer: true,
      isSystem: false,
    };
    store.messages.push(userMsg);
    if (inputEl) inputEl.value = "";
    renderChat();
    updateInputState();

    store.streamingMessage = { author: "", content: "", isSystem: false, isPlayer: false };
    renderChat();

    const url = API_BASE + "/game/turn";
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ session_id: store.session_id, text }),
      });

      if (res.status === 404) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Sesión no encontrada");
      }
      if (!res.ok) throw new Error(`Error ${res.status}`);

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buffer = "";
      let currentContent = "";

      function processEventBlock(block) {
        let eventType = "";
        let dataLine = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLine = line.slice(5).trim();
        }
        if (!dataLine || !eventType) return;
        try {
          const data = JSON.parse(dataLine);
          if (eventType === "message_delta" && data.delta != null) {
            currentContent += data.delta;
            if (store.streamingMessage) store.streamingMessage.content = currentContent;
            updateStreamingContent(currentContent);
          } else if (eventType === "message" && data.message) {
            const m = data.message;
            store.messages.push({
              author: m.author || "",
              content: m.content || "",
              isSystem: m.author === "Sistema" || m.author === "system",
              isPlayer: m.author === "Usuario",
            });
            store.streamingMessage = null;
            currentContent = "";
          } else if (eventType === "game_ended") {
            store.status.game_finished = true;
            store.status.result = {
              reason: data.reason,
              mission_evaluation: data.mission_evaluation,
            };
            store.streamingMessage = null;
          } else if (eventType === "error") {
            showError(data.message || "Error en el turno");
            store.streamingMessage = null;
          }
        } catch (_) {}
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += dec.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        parts.forEach(processEventBlock);
      }
      if (buffer.trim()) processEventBlock(buffer);

      store.streamingMessage = null;
      await fetchStatus();
    } catch (e) {
      showError(e.message || "Error al enviar");
      store.streamingMessage = null;
      await fetchStatus();
    }
    renderAll();
  }

  function initTheme() {
    const theme = safeGetItem("agora-ui-theme", "light");
    const dark = theme === "dark";
    const checkbox = $("theme-checkbox");
    if (checkbox) checkbox.checked = dark;
    document.body.classList.toggle("theme-dark", dark);
    document.body.classList.toggle("theme-light", !dark);
  }

  function toggleTheme() {
    const checkbox = $("theme-checkbox");
    const dark = checkbox ? checkbox.checked : false;
    safeSetItem("agora-ui-theme", dark ? "dark" : "light");
    document.body.classList.toggle("theme-dark", dark);
    document.body.classList.toggle("theme-light", !dark);
  }

  const btnNew = $btnNew();
  const btnReset = $btnReset();
  const btnSend = $btnSend();
  const btnCreateGame = $btnCreateGame();
  const btnCancelNewGame = $btnCancelNewGame();
  const playerInput = $playerInput();
  const themeCheckbox = $("theme-checkbox");
  if (btnNew) btnNew.addEventListener("click", openNewGameModal);
  if (btnReset) btnReset.addEventListener("click", resetPartida);
  if (btnSend) btnSend.addEventListener("click", sendTurn);
  if (btnCreateGame) btnCreateGame.addEventListener("click", submitNewGameFromForm);
  if (btnCancelNewGame) btnCancelNewGame.addEventListener("click", closeNewGameModal);
  if (playerInput) playerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendTurn();
  });
  if (themeCheckbox) themeCheckbox.addEventListener("change", toggleTheme);

  initTheme();
  renderAll();
})();
