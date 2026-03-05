(function () {
  "use strict";

  const API_BASE = "";

  const store = {
    screen: "login",
    auth: {
      user: null,
      isAuthenticated: false,
      loading: false,
      error: null,
    },
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
    observerThinking: false,
    games_list: [],
    games_loading: false,
    games_error: null,
    ui: {
      userMenuOpen: false,
      gamesPanelOpen: false,
      storyPanelOpen: false,
      briefingOpen: false,
      logoutLoading: false,
      feedbackOpen: false,
      feedbackSubmitting: false,
      feedbackError: null,
    },
    newGame: {
      step: "mode",
      standardCatalog: [],
      standardLoading: false,
      standardError: null,
      standardSubmitting: false,
    },
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
  const $victoryOverlay = () => $("victory-overlay");
  const $intro = () => $("intro-text");
  const $mission = () => $("mission-text");
  const $characters = () => $("characters-list");
  const $gameState = () => $("game-state");
  const $playerInput = () => $("player-input");
  const $btnSend = () => $("btn-send");
  const $btnNew = () => $("btn-new-game");
  const $loadingOverlay = () => $("loading-overlay");
  const $loadingMessage = () => $("loading-message");
  const $newGameModal = () => $("new-game-modal");
  const $newGameTitle = () => $("new-game-title");
  const $newGameHelp = () => $("new-game-help");
  const $newGameStepMode = () => $("new-game-step-mode");
  const $newGameStepCustom = () => $("new-game-step-custom");
  const $newGameStepStandard = () => $("new-game-step-standard");
  const $btnCreateGame = () => $("btn-create-game");
  const $btnCancelNewGame = () => $("btn-cancel-new-game");
  const $btnModeCustom = () => $("btn-mode-custom");
  const $btnModeStandard = () => $("btn-mode-standard");
  const $btnBackFromCustom = () => $("btn-back-from-custom");
  const $btnBackFromStandard = () => $("btn-back-from-standard");
  const $standardTemplatesList = () => $("standard-templates-list");
  const $seedEra = () => $("seed-era");
  const $seedTopic = () => $("seed-topic");
  const $seedStyle = () => $("seed-style");
  const $seedNumActors = () => $("seed-num-actors");
  const $app = () => $("app");
  const $loginScreen = () => $("login-screen");
  const $loginForm = () => $("login-form");
  const $loginUsername = () => $("login-username");
  const $loginPassword = () => $("login-password");
  const $btnLogin = () => $("btn-login");
  const $btnOpenRegister = () => $("btn-open-register");
  const $loginError = () => $("login-error");
  const $registerForm = () => $("register-form");
  const $registerUsername = () => $("register-username");
  const $registerPassword = () => $("register-password");
  const $btnRegister = () => $("btn-register");
  const $btnBackLogin = () => $("btn-back-login");
  const $registerError = () => $("register-error");
  const $userChip = () => $("user-chip");
  const $userAvatar = () => $("user-avatar");
  const $userName = () => $("user-name");
  const $userMenu = () => $("user-menu");
  const $menuGames = () => $("menu-games");
  const $menuFeedbackAdmin = () => $("menu-feedback-admin");
  const $menuObservability = () => $("menu-observability");
  const $menuLogout = () => $("menu-logout");
  const $gamesDrawer = () => $("games-drawer");
  const $gamesDrawerOverlay = () => $("games-drawer-overlay");
  const $gamesDrawerList = () => $("games-drawer-list");
  const $btnCloseGamesDrawer = () => $("btn-close-games-drawer");
  const $btnDrawerNewGame = () => $("btn-drawer-new-game");
  const $btnHistoryToggle = () => $("btn-history-toggle");
  const $storyPanel = () => $("story-panel");
  const $storyPanelOverlay = () => $("story-panel-overlay");
  const $btnCloseStoryPanel = () => $("btn-close-story-panel");
  const $btnOpenBriefing = () => $("btn-open-briefing");
  const $briefingModal = () => $("briefing-modal");
  const $btnCloseBriefing = () => $("btn-close-briefing");
  const $btnOpenFeedback = () => $("btn-open-feedback");
  const $feedbackModal = () => $("feedback-modal");
  const $feedbackText = () => $("feedback-text");
  const $feedbackError = () => $("feedback-error");
  const $btnCancelFeedback = () => $("btn-cancel-feedback");
  const $btnSendFeedback = () => $("btn-send-feedback");
  const $statusTurn = () => $("status-turn");
  const $statusSpeaker = () => $("status-speaker");
  const $statusInput = () => $("status-input");
  const $statusEnded = () => $("status-ended");

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

  function setAuthError(msg) {
    store.auth.error = msg || null;
    const el = $loginError();
    if (el) {
      if (msg) {
        el.textContent = msg;
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    }
  }

  function setRegisterError(msg) {
    const el = $registerError();
    if (el) {
      if (msg) {
        el.textContent = msg;
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    }
  }

  function currentUsername() {
    const user = store.auth.user || {};
    return String(user.username || "").trim() || "Usuario";
  }

  function setFeedbackError(msg) {
    store.ui.feedbackError = msg || null;
    const el = $feedbackError();
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      el.classList.remove("hidden");
    } else {
      el.textContent = "";
      el.classList.add("hidden");
    }
  }

  function isCurrentUserAdmin() {
    const user = store.auth.user || {};
    return String(user.role || "").trim().toLowerCase() === "admin";
  }

  function formatUserInitials(username) {
    const clean = String(username || "").trim();
    if (!clean) return "?";
    const parts = clean.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return clean.slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
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
    const res = await fetch(url, { credentials: "include" });
    if (res.status === 401) {
      await handleAuthExpired();
      throw new Error("Necesitas iniciar sesión.");
    }
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

  async function apiPost(path, payload) {
    const url = API_BASE + path;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload || {}),
    });
    if (res.status === 401) {
      await handleAuthExpired();
      throw new Error("Necesitas iniciar sesión.");
    }
    if (res.status === 404) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Sesión no encontrada");
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Error ${res.status}`);
    }
    return res.json();
  }

  async function handleAuthExpired() {
    store.auth.user = null;
    store.auth.isAuthenticated = false;
    store.screen = "login";
    store.session_id = null;
    store.games_list = [];
    store.ui.userMenuOpen = false;
    store.ui.gamesPanelOpen = false;
    store.ui.storyPanelOpen = false;
    store.ui.briefingOpen = false;
    store.ui.feedbackOpen = false;
    store.ui.feedbackSubmitting = false;
    store.ui.feedbackError = null;
    renderAll();
  }

  async function checkAuth() {
    store.auth.loading = true;
    try {
      const user = await apiGet("/auth/me");
      store.auth.user = user;
      store.auth.isAuthenticated = true;
      store.auth.error = null;
      store.screen = "app";
      return true;
    } catch (_) {
      store.auth.user = null;
      store.auth.isAuthenticated = false;
      store.screen = "login";
      return false;
    } finally {
      store.auth.loading = false;
    }
  }

  async function login(username, password) {
    setAuthError(null);
    setRegisterError(null);
    store.auth.loading = true;
    try {
      const data = await apiPost("/auth/login", { username, password });
      store.auth.user = data.user || { username };
      store.auth.isAuthenticated = true;
      store.auth.error = null;
      store.screen = "app";
      await fetchGamesList();
      renderAll();
      return true;
    } catch (e) {
      setAuthError(e.message || "No se pudo iniciar sesión");
      return false;
    } finally {
      store.auth.loading = false;
    }
  }

  async function register(username, password) {
    setAuthError(null);
    setRegisterError(null);
    store.auth.loading = true;
    try {
      const data = await apiPost("/auth/register", { username, password });
      store.auth.user = data.user || { username };
      store.auth.isAuthenticated = true;
      store.auth.error = null;
      store.screen = "app";
      await fetchGamesList();
      renderAll();
      return true;
    } catch (e) {
      setRegisterError(e.message || "No se pudo crear el usuario");
      return false;
    } finally {
      store.auth.loading = false;
    }
  }

  async function logout() {
    store.ui.logoutLoading = true;
    try {
      await apiPost("/auth/logout", {});
    } catch (_) {}
    store.auth.user = null;
    store.auth.isAuthenticated = false;
    store.screen = "login";
    store.ui.userMenuOpen = false;
    store.ui.gamesPanelOpen = false;
    store.ui.storyPanelOpen = false;
    store.ui.briefingOpen = false;
    store.ui.feedbackOpen = false;
    store.ui.feedbackSubmitting = false;
    store.ui.feedbackError = null;
    resetPartida();
    renderAll();
    store.ui.logoutLoading = false;
  }

  function resetNewGameWizard() {
    store.newGame.step = "mode";
    store.newGame.standardCatalog = [];
    store.newGame.standardLoading = false;
    store.newGame.standardError = null;
    store.newGame.standardSubmitting = false;
  }

  function renderTemplateCards(listElement, templates, emptyMessage, options) {
    if (!listElement) return;
    const {
      selectedTemplateId = "",
      buttonLabel = "Seleccionar",
      buttonClass = "btn-select-custom-template",
      disableButtons = false,
    } = options || {};
    if (!templates.length) {
      listElement.innerHTML = `<p class="games-list-state">${escapeHtml(emptyMessage)}</p>`;
      return;
    }
    listElement.innerHTML = templates
      .map((t) => {
        const templateId = String(t.id || "");
        const title = String(t.titulo || "Plantilla sin título");
        const description = String(t.descripcion_breve || "");
        const version = String(t.version || "1.0.0");
        const num = Number(t.num_personajes || 0);
        const selected = selectedTemplateId === templateId;
        return `
          <div class="standard-template-card${selected ? " is-selected" : ""}">
            <h4>${escapeHtml(title)}</h4>
            <p>${escapeHtml(description)}</p>
            <div class="standard-template-meta">
              <span>v${escapeHtml(version)}</span>
              <span>${num > 0 ? `${num} personajes` : "Personajes variables"}</span>
            </div>
            <button
              type="button"
              class="${buttonClass}"
              data-template-id="${escapeHtml(templateId)}"
              ${disableButtons ? "disabled" : ""}
            >
              ${escapeHtml(selected ? "Seleccionada" : buttonLabel)}
            </button>
          </div>
        `;
      })
      .join("");
  }

  function renderStandardTemplates() {
    const list = $standardTemplatesList();
    if (!list) return;
    if (store.newGame.standardLoading) {
      list.innerHTML = '<p class="games-list-state">Cargando plantillas…</p>';
      return;
    }
    if (store.newGame.standardError) {
      list.innerHTML = `<p class="games-list-state games-list-error">${escapeHtml(store.newGame.standardError)}</p>`;
      return;
    }
    const templates = Array.isArray(store.newGame.standardCatalog) ? store.newGame.standardCatalog : [];
    renderTemplateCards(
      list,
      templates,
      "No hay plantillas disponibles todavía.",
      {
        buttonLabel: store.newGame.standardSubmitting ? "Iniciando..." : "Jugar plantilla",
        buttonClass: "btn-start-standard",
        disableButtons: store.newGame.standardSubmitting,
      }
    );
  }

  function showNewGameStep(step) {
    store.newGame.step = step;
    const stepMode = $newGameStepMode();
    const stepCustom = $newGameStepCustom();
    const stepStandard = $newGameStepStandard();
    const title = $newGameTitle();
    const help = $newGameHelp();
    if (stepMode) stepMode.classList.toggle("hidden", step !== "mode");
    if (stepCustom) stepCustom.classList.toggle("hidden", step !== "custom");
    if (stepStandard) stepStandard.classList.toggle("hidden", step !== "standard");
    if (title) {
      if (step === "custom") title.textContent = "Nueva partida personalizada";
      else if (step === "standard") title.textContent = "Plantillas";
      else title.textContent = "Nueva partida";
    }
    if (help) {
      if (step === "custom") help.textContent = "Describe la partida y genera una historia nueva.";
      else if (step === "standard") help.textContent = "Elige una plantilla ya preparada para iniciar la partida al instante.";
      else help.textContent = "Elige cómo quieres iniciar la historia.";
    }
    if (step === "standard") renderStandardTemplates();
  }

  function openNewGameModal() {
    const modal = $newGameModal();
    if (!modal) return;
    resetNewGameWizard();
    showNewGameStep("mode");
    modal.classList.remove("hidden");
  }

  function closeNewGameModal() {
    const modal = $newGameModal();
    if (!modal) return;
    modal.classList.add("hidden");
    resetNewGameWizard();
    showNewGameStep("mode");
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

  function hasFirstActorMessage() {
    const messages = Array.isArray(store.status.messages) ? store.status.messages : [];
    const username = currentUsername();
    return messages.some((message) => {
      const author = String(message && message.author ? message.author : "").trim();
      const content = String(message && message.content ? message.content : "").trim();
      if (!author || !content) return false;
      if (author === "Sistema" || author === "system") return false;
      if (author === "Usuario" || author === username) return false;
      return true;
    });
  }

  async function emitClientInitMetric(sessionId, startedAtMs) {
    if (!sessionId) return;
    const elapsed = Math.max(0, Math.round(performance.now() - Number(startedAtMs || 0)));
    try {
      await apiPost("/game/init-metric", {
        session_id: String(sessionId),
        ttfa_client_ms: elapsed,
      });
    } catch (_) {}
  }

  async function postNewGame(payload = {}) {
    if (!store.auth.isAuthenticated) {
      await handleAuthExpired();
      return false;
    }
    const initStartedAtMs = performance.now();
    clearError();
    showLoading("Creando partida…");
    try {
      const url = API_BASE + "/game/new";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        await handleAuthExpired();
        throw new Error("Necesitas iniciar sesión.");
      }
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
      if (hasFirstActorMessage()) {
        emitClientInitMetric(store.session_id, initStartedAtMs);
      }
      await fetchGamesList();
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

  async function fetchStandardCatalog() {
    store.newGame.standardLoading = true;
    store.newGame.standardError = null;
    renderStandardTemplates();
    try {
      const data = await apiGet("/game/standard/list");
      store.newGame.standardCatalog = Array.isArray(data.templates) ? data.templates : [];
    } catch (e) {
      store.newGame.standardCatalog = [];
      store.newGame.standardError = e.message || "No se pudo cargar el catálogo de plantillas";
    } finally {
      store.newGame.standardLoading = false;
      renderStandardTemplates();
    }
  }

  async function startStandardGame(templateId) {
    if (!templateId) return;
    if (!store.auth.isAuthenticated) {
      await handleAuthExpired();
      return;
    }
    const initStartedAtMs = performance.now();
    store.newGame.standardSubmitting = true;
    renderStandardTemplates();
    clearError();
    showLoading("Cargando plantilla e iniciando partida…");
    try {
      const data = await apiPost("/game/standard/start", { template_id: templateId });
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
      if (hasFirstActorMessage()) {
        emitClientInitMetric(store.session_id, initStartedAtMs);
      }
      await fetchGamesList();
      closeNewGameModal();
      renderAll();
    } catch (e) {
      showError(e.message || "No se pudo iniciar la plantilla");
    } finally {
      store.newGame.standardSubmitting = false;
      hideLoading();
      renderStandardTemplates();
    }
  }

  async function fetchContext() {
    if (!store.auth.isAuthenticated) return;
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
    if (!store.auth.isAuthenticated) return;
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
        isPlayer: m.author === "Usuario" || m.author === currentUsername(),
      }));
      renderAll();
    } catch (e) {
      showError(e.message || "Sesión no encontrada");
      store.session_id = null;
      renderAll();
    }
  }

  async function fetchGamesList() {
    if (!store.auth.isAuthenticated) {
      store.games_list = [];
      store.games_loading = false;
      renderGamesDrawer();
      return;
    }
    store.games_loading = true;
    store.games_error = null;
    renderGamesDrawer();
    try {
      const data = await apiGet("/game/list");
      store.games_list = Array.isArray(data.games) ? data.games : [];
    } catch (e) {
      store.games_list = [];
      store.games_error = e.message || "Error al cargar partidas";
    } finally {
      store.games_loading = false;
      renderGamesDrawer();
    }
  }

  function formatShortDate(value) {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString("es-ES", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatRelativeDate(value) {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "";
    const diffMs = Date.now() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "justo ahora";
    if (mins < 60) return `hace ${mins} min`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `hace ${hours} h`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `hace ${days} d`;
    return formatShortDate(value);
  }

  function toggleUserMenu(forceOpen) {
    const next = typeof forceOpen === "boolean" ? forceOpen : !store.ui.userMenuOpen;
    store.ui.userMenuOpen = next;
    const chip = $userChip();
    if (chip) chip.setAttribute("aria-expanded", next ? "true" : "false");
    const menu = $userMenu();
    if (menu) menu.classList.toggle("hidden", !next);
    if (next) {
      const first = $menuGames();
      if (first) first.focus();
    }
  }

  function openGamesPanel() {
    store.ui.gamesPanelOpen = true;
    toggleUserMenu(false);
    const drawer = $gamesDrawer();
    const overlay = $gamesDrawerOverlay();
    if (drawer) {
      drawer.classList.remove("hidden");
      drawer.setAttribute("aria-hidden", "false");
    }
    if (overlay) {
      overlay.classList.remove("hidden");
      overlay.setAttribute("aria-hidden", "false");
    }
    renderGamesDrawer();
  }

  function closeGamesPanel() {
    store.ui.gamesPanelOpen = false;
    const drawer = $gamesDrawer();
    const overlay = $gamesDrawerOverlay();
    if (drawer) {
      drawer.classList.add("hidden");
      drawer.setAttribute("aria-hidden", "true");
    }
    if (overlay) {
      overlay.classList.add("hidden");
      overlay.setAttribute("aria-hidden", "true");
    }
  }

  function openStoryPanel() {
    store.ui.storyPanelOpen = true;
    const panel = $storyPanel();
    const overlay = $storyPanelOverlay();
    if (panel) {
      panel.classList.remove("hidden");
      panel.setAttribute("aria-hidden", "false");
    }
    if (overlay) {
      overlay.classList.remove("hidden");
      overlay.setAttribute("aria-hidden", "false");
    }
  }

  function closeStoryPanel() {
    store.ui.storyPanelOpen = false;
    const panel = $storyPanel();
    const overlay = $storyPanelOverlay();
    if (panel) {
      panel.classList.add("hidden");
      panel.setAttribute("aria-hidden", "true");
    }
    if (overlay) {
      overlay.classList.add("hidden");
      overlay.setAttribute("aria-hidden", "true");
    }
  }

  function openBriefingModal() {
    store.ui.briefingOpen = true;
    const modal = $briefingModal();
    if (modal) modal.classList.remove("hidden");
  }

  function closeBriefingModal() {
    store.ui.briefingOpen = false;
    const modal = $briefingModal();
    if (modal) modal.classList.add("hidden");
  }

  function openFeedbackModal() {
    if (!store.session_id) {
      showError("No hay partida activa para adjuntar el feedback.");
      return;
    }
    clearError();
    store.ui.feedbackOpen = true;
    store.ui.feedbackSubmitting = false;
    setFeedbackError(null);
    const modal = $feedbackModal();
    const text = $feedbackText();
    if (modal) modal.classList.remove("hidden");
    if (text) {
      text.value = "";
      text.focus();
    }
  }

  function closeFeedbackModal() {
    store.ui.feedbackOpen = false;
    store.ui.feedbackSubmitting = false;
    setFeedbackError(null);
    const modal = $feedbackModal();
    const text = $feedbackText();
    if (modal) modal.classList.add("hidden");
    if (text) text.value = "";
    renderOverlayPanels();
  }

  async function submitFeedback() {
    if (!store.auth.isAuthenticated) {
      await handleAuthExpired();
      return;
    }
    if (!store.session_id) {
      showError("No hay partida activa para adjuntar el feedback.");
      closeFeedbackModal();
      return;
    }
    const textEl = $feedbackText();
    const text = ((textEl && textEl.value) || "").trim();
    if (!text) {
      setFeedbackError("Escribe feedback antes de enviar.");
      return;
    }
    store.ui.feedbackSubmitting = true;
    setFeedbackError(null);
    const sendBtn = $btnSendFeedback();
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.textContent = "Enviando...";
    }
    try {
      await apiPost("/game/feedback", { session_id: store.session_id, text });
      closeFeedbackModal();
    } catch (e) {
      setFeedbackError(e.message || "No se pudo enviar el feedback.");
    } finally {
      store.ui.feedbackSubmitting = false;
      const btn = $btnSendFeedback();
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Enviar";
      }
    }
  }

  function closeOnOutsideClick(e) {
    const menu = $userMenu();
    const chip = $userChip();
    if (store.ui.userMenuOpen && menu && chip) {
      const inMenu = menu.contains(e.target);
      const inChip = chip.contains(e.target);
      if (!inMenu && !inChip) toggleUserMenu(false);
    }
  }

  async function resumeGame(sessionId) {
    if (!store.auth.isAuthenticated) {
      await handleAuthExpired();
      return;
    }
    if (!sessionId) return;
    clearError();
    showLoading("Reanudando partida…");
    try {
      const data = await apiPost("/game/resume", { session_id: sessionId });
      store.session_id = data.session_id || sessionId;
      await fetchContext();
      await fetchStatus();
      await fetchGamesList();
      closeGamesPanel();
      renderAll();
    } catch (e) {
      showError(e.message || "No se pudo reanudar la partida");
    } finally {
      hideLoading();
    }
  }

  function renderSidebar() {
    const intro = $intro();
    const mission = $mission();
    const charactersEl = $characters();
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
    const gameStateEl = $gameState();
    if (gameStateEl) gameStateEl.innerHTML = stateHtml;

    const sTurn = $statusTurn();
    const sSpeaker = $statusSpeaker();
    const sInput = $statusInput();
    const sEnded = $statusEnded();
    if (sTurn) sTurn.textContent = store.session_id ? `${s.turn_current} / ${s.turn_max}` : "—";
    if (sSpeaker) sSpeaker.textContent = store.session_id ? (s.current_speaker || "Jugador") : "—";
    if (sInput) sInput.textContent = store.session_id ? (s.player_can_write ? "Abierta" : "Bloqueada") : "—";
    if (sEnded) sEnded.textContent = store.session_id ? (s.game_finished ? "Finalizada" : "En curso") : "—";
  }

  function renderUserMenu() {
    const chip = $userChip();
    const avatar = $userAvatar();
    const name = $userName();
    const menu = $userMenu();
    if (!chip || !avatar || !name || !menu) return;
    const username = currentUsername();
    avatar.textContent = formatUserInitials(username);
    name.textContent = username;
    chip.setAttribute("aria-expanded", store.ui.userMenuOpen ? "true" : "false");
    menu.classList.toggle("hidden", !store.ui.userMenuOpen);
    const feedbackAdminBtn = $menuFeedbackAdmin();
    if (feedbackAdminBtn) feedbackAdminBtn.classList.toggle("hidden", !isCurrentUserAdmin());
    const observabilityBtn = $menuObservability();
    if (observabilityBtn) observabilityBtn.classList.toggle("hidden", !isCurrentUserAdmin());
    const logoutBtn = $menuLogout();
    if (logoutBtn) {
      logoutBtn.disabled = !!store.ui.logoutLoading;
      logoutBtn.textContent = store.ui.logoutLoading ? "Cerrando sesión..." : "Cerrar sesión";
    }
  }

  function renderGamesDrawer() {
    const list = $gamesDrawerList();
    if (!list) return;
    if (!store.ui.gamesPanelOpen) return;
    if (store.games_loading) {
      list.innerHTML = '<p class="games-list-state">Cargando partidas…</p>';
      return;
    }
    if (store.games_error) {
      list.innerHTML = `<p class="games-list-state games-list-error">${escapeHtml(store.games_error)}</p>`;
      return;
    }
    const games = Array.isArray(store.games_list) ? store.games_list : [];
    if (!games.length) {
      list.innerHTML = '<p class="games-list-state">Aún no tienes partidas guardadas.</p>';
      return;
    }
    list.innerHTML = games
      .map((g) => {
        const gameId = String(g.id || "");
        const title = String(g.title || "Partida sin título");
        const updatedLabel = formatRelativeDate(g.updated_at);
        const activeClass = gameId === store.session_id ? " is-active" : "";
        return `
          <button type="button" class="game-item${activeClass}" data-game-id="${escapeHtml(gameId)}">
            <span class="game-item-title">${escapeHtml(title)}</span>
            <span class="game-item-meta">
              <span class="game-item-status">${gameId === store.session_id ? "Activa" : "Continuar"}</span>
              <span class="game-item-date">${escapeHtml(updatedLabel)}</span>
            </span>
          </button>
        `;
      })
      .join("");
  }

  function renderOverlayPanels() {
    const storyPanel = $storyPanel();
    const storyOverlay = $storyPanelOverlay();
    if (storyPanel) {
      storyPanel.classList.toggle("hidden", !store.ui.storyPanelOpen);
      storyPanel.setAttribute("aria-hidden", store.ui.storyPanelOpen ? "false" : "true");
    }
    if (storyOverlay) {
      storyOverlay.classList.toggle("hidden", !store.ui.storyPanelOpen);
      storyOverlay.setAttribute("aria-hidden", store.ui.storyPanelOpen ? "false" : "true");
    }
    const briefing = $briefingModal();
    if (briefing) briefing.classList.toggle("hidden", !store.ui.briefingOpen);
    const feedback = $feedbackModal();
    if (feedback) feedback.classList.toggle("hidden", !store.ui.feedbackOpen);
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

  function clearStreamingState() {
    store.streamingMessage = null;
    store.streamingNode = null;
    store.observerThinking = false;
  }

  function appendChatMessage(chat, msg, isStreaming) {
    const div = document.createElement("div");
    div.className = msgClass(msg) + (isStreaming ? " msg-streaming" : "");
    div.innerHTML = `
      <div class="msg-author">${escapeHtml(msg.author)}</div>
      <div class="msg-content">${escapeHtml(msg.content)}</div>
    `;
    chat.appendChild(div);
    if (isStreaming) store.streamingNode = div.querySelector(".msg-content");
  }

  function appendObserverThinking(chat) {
    const div = document.createElement("div");
    div.className = "chat-thinking";
    div.innerHTML = `
      <div class="chat-thinking-spinner" role="status" aria-label="Pensando"></div>
    `;
    chat.appendChild(div);
  }

  function renderChat() {
    const chat = $chat();
    if (!chat) return;
    chat.innerHTML = "";
    store.streamingNode = null;

    store.messages.forEach((msg) => appendChatMessage(chat, msg, false));

    if (store.observerThinking && !store.streamingMessage) {
      appendObserverThinking(chat);
    }

    if (store.streamingMessage) {
      appendChatMessage(chat, store.streamingMessage, true);
    }

    const lastNode = store.streamingNode || chat.lastElementChild;
    if (lastNode) lastNode.scrollIntoView({ behavior: "smooth" });
  }

  function updateStreamingContent(text) {
    if (store.streamingNode) {
      store.streamingNode.textContent = text;
      store.streamingNode.scrollIntoView({ behavior: "smooth" });
    }
  }

  function isPlayerVictory() {
    if (!store.session_id || !store.status.game_finished) return false;
    const result = store.status.result;
    if (!result || typeof result !== "object") return false;
    const missionEvaluation = result.mission_evaluation;
    if (!missionEvaluation || typeof missionEvaluation !== "object") return false;
    return missionEvaluation.player_mission_achieved === true;
  }

  function renderVictoryOverlay() {
    const overlay = $victoryOverlay();
    if (!overlay) return;
    const hasVictory = isPlayerVictory();
    overlay.classList.toggle("hidden", !hasVictory);
    overlay.setAttribute("aria-hidden", hasVictory ? "false" : "true");
    if (!hasVictory) {
      overlay.innerHTML = "";
      return;
    }
    const reason = String((store.status.result && store.status.result.reason) || "").trim();
    const detail = reason || "Has cumplido la misión principal.";
    overlay.innerHTML = `
      <section class="victory-overlay-panel">
        <div class="victory-kicker">Partida finalizada</div>
        <h2 class="victory-title">Victoria del jugador</h2>
        <p class="victory-subtitle">${escapeHtml(detail)}</p>
        <p class="victory-note">El chat queda bloqueado. Puedes usar el menu superior para feedback, usuario o nueva partida.</p>
      </section>
    `;
  }

  function updateInputState() {
    const s = store.status;
    const blockedByVictory = isPlayerVictory();
    const canWrite = store.session_id && s.player_can_write && !s.game_finished && !blockedByVictory;
    const playerInput = $playerInput();
    const sendBtn = $btnSend();
    if (playerInput) {
      playerInput.disabled = !canWrite;
      playerInput.placeholder = blockedByVictory
        ? "Partida ganada. Ya no puedes escribir en este chat."
        : "Escribe tu mensaje...";
    }
    if (sendBtn) sendBtn.disabled = !canWrite;
  }

  function renderAll() {
    const loginScreen = $loginScreen();
    const app = $app();
    const loginForm = $loginForm();
    const registerForm = $registerForm();
    if (store.screen === "login" || store.screen === "register") {
      store.ui.storyPanelOpen = false;
      store.ui.briefingOpen = false;
      store.ui.feedbackOpen = false;
      store.ui.feedbackSubmitting = false;
      store.ui.feedbackError = null;
      if (loginScreen) loginScreen.classList.remove("hidden");
      if (app) app.classList.add("hidden");
      if (loginForm) loginForm.classList.toggle("hidden", store.screen !== "login");
      if (registerForm) registerForm.classList.toggle("hidden", store.screen !== "register");
      renderOverlayPanels();
      setAuthError(store.screen === "login" ? store.auth.error : null);
      setRegisterError(store.screen === "register" ? store.auth.error : null);
      return;
    }
    if (loginScreen) loginScreen.classList.add("hidden");
    if (app) app.classList.remove("hidden");
    renderUserMenu();
    renderSidebar();
    renderGamesDrawer();
    renderOverlayPanels();
    renderVictoryOverlay();
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
    clearStreamingState();
    renderAll();
  }

  async function sendTurn() {
    if (!store.auth.isAuthenticated) {
      await handleAuthExpired();
      return;
    }
    const inputEl = $playerInput();
    const text = (inputEl && inputEl.value ? inputEl.value : "").trim();
    if (!store.session_id) {
      showError("No hay partida activa. Crea una nueva partida.");
      return;
    }
    if (!text) return;

    const userMsg = {
      author: currentUsername(),
      content: text,
      isPlayer: true,
      isSystem: false,
    };
    store.messages.push(userMsg);
    if (inputEl) inputEl.value = "";
    clearStreamingState();
    store.observerThinking = true;
    renderChat();
    updateInputState();

    const url = API_BASE + "/game/turn";
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        credentials: "include",
        body: JSON.stringify({ session_id: store.session_id, text }),
      });

      if (res.status === 401) {
        await handleAuthExpired();
        throw new Error("Necesitas iniciar sesión.");
      }
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
          if (eventType === "observer_thinking") {
            store.observerThinking = true;
            renderChat();
          } else if (eventType === "message_start") {
            currentContent = "";
            store.observerThinking = false;
            store.streamingMessage = {
              author: data.author || "",
              content: "",
              isSystem: false,
              isPlayer: false,
            };
            renderChat();
          } else if (eventType === "message_delta" && data.delta != null) {
            if (!store.streamingMessage) {
              store.observerThinking = false;
              store.streamingMessage = {
                author: store.status.current_speaker || "",
                content: "",
                isSystem: false,
                isPlayer: false,
              };
              renderChat();
            }
            currentContent += data.delta;
            if (store.streamingMessage) store.streamingMessage.content = currentContent;
            updateStreamingContent(currentContent);
          } else if (eventType === "message" && data.message) {
            const m = data.message;
            store.messages.push({
              author: m.author || "",
              content: m.content || "",
              isSystem: m.author === "Sistema" || m.author === "system",
              isPlayer: m.author === "Usuario" || m.author === currentUsername(),
            });
            store.streamingMessage = null;
            store.streamingNode = null;
            currentContent = "";
            renderChat();
          } else if (eventType === "game_ended") {
            store.status.game_finished = true;
            store.status.result = {
              reason: data.reason,
              mission_evaluation: data.mission_evaluation,
            };
            clearStreamingState();
          } else if (eventType === "error") {
            showError(data.message || "Error en el turno");
            clearStreamingState();
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

      clearStreamingState();
      await fetchStatus();
      await fetchGamesList();
    } catch (e) {
      showError(e.message || "Error al enviar");
      clearStreamingState();
      await fetchStatus();
      await fetchGamesList();
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
  const btnSend = $btnSend();
  const btnCreateGame = $btnCreateGame();
  const btnCancelNewGame = $btnCancelNewGame();
  const btnModeCustom = $btnModeCustom();
  const btnModeStandard = $btnModeStandard();
  const btnBackFromCustom = $btnBackFromCustom();
  const btnBackFromStandard = $btnBackFromStandard();
  const standardTemplatesList = $standardTemplatesList();
  const playerInput = $playerInput();
  const themeCheckbox = $("theme-checkbox");
  const loginForm = $loginForm();
  const btnLogin = $btnLogin();
  const registerForm = $registerForm();
  const btnRegister = $btnRegister();
  const btnOpenRegister = $btnOpenRegister();
  const btnBackLogin = $btnBackLogin();
  const userChip = $userChip();
  const menuGames = $menuGames();
  const menuFeedbackAdmin = $menuFeedbackAdmin();
  const menuObservability = $menuObservability();
  const menuLogout = $menuLogout();
  const gamesDrawer = $gamesDrawer();
  const gamesDrawerOverlay = $gamesDrawerOverlay();
  const btnCloseGamesDrawer = $btnCloseGamesDrawer();
  const btnDrawerNewGame = $btnDrawerNewGame();
  const btnHistoryToggle = $btnHistoryToggle();
  const storyPanelOverlay = $storyPanelOverlay();
  const btnCloseStoryPanel = $btnCloseStoryPanel();
  const btnOpenBriefing = $btnOpenBriefing();
  const btnCloseBriefing = $btnCloseBriefing();
  const briefingModal = $briefingModal();
  const btnOpenFeedback = $btnOpenFeedback();
  const btnCancelFeedback = $btnCancelFeedback();
  const btnSendFeedback = $btnSendFeedback();
  const feedbackModal = $feedbackModal();
  if (btnNew) btnNew.addEventListener("click", openNewGameModal);
  if (btnSend) btnSend.addEventListener("click", sendTurn);
  if (btnCreateGame) btnCreateGame.addEventListener("click", submitNewGameFromForm);
  if (btnCancelNewGame) btnCancelNewGame.addEventListener("click", closeNewGameModal);
  if (btnModeCustom) {
    btnModeCustom.addEventListener("click", () => {
      showNewGameStep("custom");
      const era = $seedEra();
      if (era) era.focus();
    });
  }
  if (btnModeStandard) {
    btnModeStandard.addEventListener("click", async () => {
      showNewGameStep("standard");
      await fetchStandardCatalog();
    });
  }
  if (btnBackFromCustom) {
    btnBackFromCustom.addEventListener("click", () => showNewGameStep("mode"));
  }
  if (btnBackFromStandard) {
    btnBackFromStandard.addEventListener("click", () => showNewGameStep("mode"));
  }
  if (standardTemplatesList) {
    standardTemplatesList.addEventListener("click", async (e) => {
      const target = e.target && e.target.closest ? e.target.closest("[data-template-id]") : null;
      if (!target) return;
      const templateId = target.getAttribute("data-template-id");
      if (!templateId || store.newGame.standardSubmitting) return;
      await startStandardGame(templateId);
    });
  }
  if (playerInput) playerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendTurn();
  });
  if (themeCheckbox) themeCheckbox.addEventListener("change", toggleTheme);
  if (gamesDrawer) {
    gamesDrawer.addEventListener("click", (e) => {
      const target = e.target && e.target.closest ? e.target.closest("[data-game-id]") : null;
      if (!target) return;
      const gameId = target.getAttribute("data-game-id");
      if (!gameId) return;
      if (gameId === store.session_id) {
        closeGamesPanel();
        return;
      }
      resumeGame(gameId);
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const username = (($loginUsername() && $loginUsername().value) || "").trim();
      const password = (($loginPassword() && $loginPassword().value) || "").trim();
      if (!username || !password) {
        setAuthError("Usuario y contraseña son obligatorios.");
        return;
      }
      if (btnLogin) btnLogin.disabled = true;
      const ok = await login(username, password);
      if (!ok && btnLogin) btnLogin.disabled = false;
      if (ok && btnLogin) btnLogin.disabled = false;
    });
  }

  if (btnOpenRegister) {
    btnOpenRegister.addEventListener("click", () => {
      setAuthError(null);
      setRegisterError(null);
      store.screen = "register";
      renderAll();
    });
  }

  if (btnBackLogin) {
    btnBackLogin.addEventListener("click", () => {
      setAuthError(null);
      setRegisterError(null);
      store.screen = "login";
      renderAll();
    });
  }

  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const username = (($registerUsername() && $registerUsername().value) || "").trim();
      const password = (($registerPassword() && $registerPassword().value) || "").trim();
      if (!username || !password) {
        setRegisterError("Usuario y contraseña son obligatorios.");
        return;
      }
      if (password.length < 6) {
        setRegisterError("La contraseña debe tener al menos 6 caracteres.");
        return;
      }
      if (btnRegister) btnRegister.disabled = true;
      const ok = await register(username, password);
      if (!ok && btnRegister) btnRegister.disabled = false;
      if (ok && btnRegister) btnRegister.disabled = false;
    });
  }

  if (userChip) {
    userChip.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleUserMenu();
    });
  }
  if (menuGames) {
    menuGames.addEventListener("click", async () => {
      await fetchGamesList();
      openGamesPanel();
    });
  }
  if (menuLogout) {
    menuLogout.addEventListener("click", async () => {
      toggleUserMenu(false);
      await logout();
    });
  }
  if (menuFeedbackAdmin) {
    menuFeedbackAdmin.addEventListener("click", () => {
      toggleUserMenu(false);
      window.location.assign("/admin/feedback/");
    });
  }
  if (menuObservability) {
    menuObservability.addEventListener("click", () => {
      toggleUserMenu(false);
      window.location.assign("/admin/observability/");
    });
  }
  if (gamesDrawerOverlay) {
    gamesDrawerOverlay.addEventListener("click", () => closeGamesPanel());
  }
  if (btnCloseGamesDrawer) {
    btnCloseGamesDrawer.addEventListener("click", () => closeGamesPanel());
  }
  if (btnDrawerNewGame) {
    btnDrawerNewGame.addEventListener("click", () => {
      closeGamesPanel();
      openNewGameModal();
    });
  }
  if (btnHistoryToggle) {
    btnHistoryToggle.addEventListener("click", () => {
      if (store.ui.storyPanelOpen) closeStoryPanel();
      else openStoryPanel();
    });
  }
  if (storyPanelOverlay) {
    storyPanelOverlay.addEventListener("click", () => closeStoryPanel());
  }
  if (btnCloseStoryPanel) {
    btnCloseStoryPanel.addEventListener("click", () => closeStoryPanel());
  }
  if (btnOpenBriefing) {
    btnOpenBriefing.addEventListener("click", () => openBriefingModal());
  }
  if (btnCloseBriefing) {
    btnCloseBriefing.addEventListener("click", () => closeBriefingModal());
  }
  if (btnOpenFeedback) {
    btnOpenFeedback.addEventListener("click", () => openFeedbackModal());
  }
  if (btnCancelFeedback) {
    btnCancelFeedback.addEventListener("click", () => closeFeedbackModal());
  }
  if (btnSendFeedback) {
    btnSendFeedback.addEventListener("click", () => submitFeedback());
  }
  if (briefingModal) {
    briefingModal.addEventListener("click", (e) => {
      if (e.target === briefingModal) closeBriefingModal();
    });
  }
  if (feedbackModal) {
    feedbackModal.addEventListener("click", (e) => {
      if (e.target === feedbackModal) closeFeedbackModal();
    });
  }
  document.addEventListener("click", closeOnOutsideClick);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      toggleUserMenu(false);
      closeGamesPanel();
      closeStoryPanel();
      closeBriefingModal();
      closeFeedbackModal();
    }
  });

  async function init() {
    initTheme();
    await checkAuth();
    if (store.auth.isAuthenticated) {
      await fetchGamesList();
    }
    renderAll();
  }

  init();
})();
