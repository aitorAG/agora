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
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function clearError() {
    store.error = null;
    $errorBanner().classList.add("hidden");
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

  async function postNewGame() {
    clearError();
    showLoading("Creando partida…");
    try {
      const url = API_BASE + "/game/new";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
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
    } catch (e) {
      showError(e.message || "Error al crear partida");
    } finally {
      hideLoading();
    }
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
    $intro().textContent = store.context.narrativa_inicial || "—";
    $mission().textContent = store.context.player_mission || "—";
    const chars = store.context.characters || [];
    $characters().innerHTML = chars.length
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
    const hadStreaming = store.streamingNode != null;
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
    const text = ($playerInput().value || "").trim();
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
    $playerInput().value = "";
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
      showError(e.message || "Error al enviar turno");
      store.streamingMessage = null;
      await fetchStatus();
    }
    renderAll();
  }

  function initTheme() {
    const dark = localStorage.getItem("agora-ui-theme") === "dark";
    const checkbox = $("theme-checkbox");
    checkbox.checked = dark;
    document.body.classList.toggle("theme-dark", dark);
    document.body.classList.toggle("theme-light", !dark);
  }

  function toggleTheme() {
    const dark = $("theme-checkbox").checked;
    localStorage.setItem("agora-ui-theme", dark ? "dark" : "light");
    document.body.classList.toggle("theme-dark", dark);
    document.body.classList.toggle("theme-light", !dark);
  }

  $btnNew().addEventListener("click", postNewGame);
  $btnReset().addEventListener("click", resetPartida);
  $btnSend().addEventListener("click", sendTurn);
  $playerInput().addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendTurn();
  });
  $("theme-checkbox").addEventListener("change", toggleTheme);

  initTheme();
  renderAll();
})();
