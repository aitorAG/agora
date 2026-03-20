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
      player_public_mission: "",
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
      activeStoryTab: "context",
      storyEntryMode: "new",
      contextRevealChars: 0,
      contextRevealDone: false,
      contextRevealSessionId: null,
    },
    newGame: {
      step: "mode",
      standardCatalog: [],
      standardLoading: false,
      standardError: null,
      standardSubmitting: false,
    },
  };

  const INPUT_LIMITS = {
    player: { maxSentences: 5, maxWords: 120, maxChars: 600 },
    custom: {
      era: { maxSentences: 2, maxWords: 30, maxChars: 160, label: "Época/contexto" },
      topic: { maxSentences: 2, maxWords: 30, maxChars: 160, label: "Tema" },
      style: { maxSentences: 1, maxWords: 18, maxChars: 100, label: "Estilo" },
      total: { maxSentences: 5, maxWords: 70, maxChars: 400, label: "La descripción custom" },
    },
  };
  const LANDING_GAMES_LIMIT = 4;
  const STORY_TAB_ORDER = ["context", "characters", "chat"];
  let contextRevealTimer = null;
  let storyPagerScrollTimer = null;

  const $ = (id) => document.getElementById(id);

  function normalizeText(value) {
    return String(value || "").trim();
  }

  function countWords(text) {
    const matches = normalizeText(text).match(/\S+/g);
    return matches ? matches.length : 0;
  }

  function countSentences(text) {
    const cleaned = normalizeText(text);
    if (!cleaned) return 0;
    const parts = cleaned.split(/[.!?…]+/).map((part) => part.trim()).filter(Boolean);
    return parts.length || 1;
  }

  function validateTextLimits(text, limits) {
    const cleaned = normalizeText(text);
    if (!cleaned) return "";
    if (cleaned.length > limits.maxChars) {
      return `${limits.label} no puede superar ${limits.maxChars} caracteres.`;
    }
    if (countWords(cleaned) > limits.maxWords) {
      return `${limits.label} no puede superar ${limits.maxWords} palabras.`;
    }
    if (countSentences(cleaned) > limits.maxSentences) {
      return `${limits.label} no puede superar ${limits.maxSentences} frases.`;
    }
    return "";
  }

  function validatePlayerMessage(text) {
    return validateTextLimits(text, {
      ...INPUT_LIMITS.player,
      label: "El mensaje del usuario",
    });
  }

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
  const $playerInput = () => $("player-input");
  const $btnSend = () => $("btn-send");
  const $btnNew = () => $("btn-new-game");
  const $btnHome = () => $("btn-home");
  const $btnThemeToggle = () => $("btn-theme-toggle");
  const $themeToggleIcon = () => $("theme-toggle-icon");
  const $topbarTitleBlock = () => $("topbar-title-block");
  const $topbarStoryTitle = () => $("topbar-story-title");
  const $topbarStatus = () => $("topbar-status");
  const $topbarTurn = () => $("topbar-turn");
  const $topbarGame = () => $("topbar-game");
  const $workspace = () => $("workspace");
  const $landingView = () => $("landing-view");
  const $landingGamesList = () => $("landing-games-list");
  const $storyShell = () => $("story-shell");
  const $storyTabs = () => document.querySelectorAll("[data-story-tab]");
  const $storyStages = () => document.querySelectorAll("[data-story-stage]");
  const $storyPager = () => $("story-pager");
  const $storyTrack = () => $("story-track");
  const $contextStream = () => $("context-stream");
  const $storyMissionPrimary = () => $("story-mission-primary");
  const $storyMissionPublicWrap = () => $("story-mission-public-wrap");
  const $storyMissionPublic = () => $("story-mission-public");
  const $storyMissionInline = () => $("story-mission-inline");
  const $storyCharactersGrid = () => $("story-characters-grid");
  const $btnLandingCustom = () => $("btn-landing-custom");
  const $btnLandingStandard = () => $("btn-landing-standard");
  const $btnLandingAllGames = () => $("btn-landing-all-games");
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
  const $inputArea = () => $("input-area");
  const $rightRail = () => $("right-rail");

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
    resetStoryExperience();
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

  function isStandardTemplateActive(template) {
    if (!template || typeof template !== "object" || !Object.prototype.hasOwnProperty.call(template, "active")) {
      return true;
    }
    const value = template.active;
    if (typeof value === "boolean") return value;
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      if (["false", "0", "no", "off"].includes(normalized)) return false;
      if (["true", "1", "yes", "on"].includes(normalized)) return true;
    }
    return Boolean(value);
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
    const templates = Array.isArray(store.newGame.standardCatalog)
      ? store.newGame.standardCatalog.filter((template) => isStandardTemplateActive(template))
      : [];
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
      if (step === "custom") title.textContent = "Historia custom";
      else if (step === "standard") title.textContent = "Historia desde la librería";
      else title.textContent = "Nueva historia";
    }
    if (help) {
      if (step === "custom") help.textContent = "Define el contexto, el tema y el tono para construir una historia nueva.";
      else if (step === "standard") help.textContent = "Elige una historia ya preparada de la librería y entra directo en la investigación.";
      else help.textContent = "Elige cómo quieres iniciar la historia.";
    }
    if (step === "standard") renderStandardTemplates();
  }

  function openNewGameModal(step) {
    const modal = $newGameModal();
    if (!modal) return;
    resetNewGameWizard();
    showNewGameStep(step || "mode");
    modal.classList.remove("hidden");
  }

  function openCustomNewGameModal() {
    openNewGameModal("custom");
    const era = $seedEra();
    if (era) era.focus();
  }

  async function openStandardNewGameModal() {
    openNewGameModal("standard");
    await fetchStandardCatalog();
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
    const eraError = validateTextLimits(era, INPUT_LIMITS.custom.era);
    if (eraError) return { error: eraError };
    const topicError = validateTextLimits(topic, INPUT_LIMITS.custom.topic);
    if (topicError) return { error: topicError };
    const styleError = validateTextLimits(style, INPUT_LIMITS.custom.style);
    if (styleError) return { error: styleError };

    const hasTextSeed = !!(era || topic || style);
    const hasNumActors = numActorsRaw !== "";
    const payload = {};

    if (hasTextSeed) {
      const totalError = validateTextLimits(
        [era, topic, style].filter(Boolean).join(" "),
        INPUT_LIMITS.custom.total
      );
      if (totalError) return { error: totalError };
      if (era) payload.era = era;
      if (topic) payload.topic = topic;
      if (style) payload.style = style;
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
    showLoading("Creando historia…");
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
      store.context.player_public_mission = data.player_public_mission || "";
      store.context.characters = data.characters || [];
      store.status.turn_current = data.turn_current ?? 0;
      store.status.turn_max = data.turn_max ?? 10;
      store.status.player_can_write = data.player_can_write ?? false;
      store.status.game_finished = false;
      store.status.result = null;
      store.messages = [];
      prepareStoryExperience("new");
      await fetchContext();
      await fetchStatus();
      prepareStoryExperience("new");
      ensureContextReveal(true);
      if (hasFirstActorMessage()) {
        emitClientInitMetric(store.session_id, initStartedAtMs);
      }
      await fetchGamesList();
      forceStoryTab("context");
      renderAll();
      return true;
    } catch (e) {
      showError(e.message || "Error al crear la historia");
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
    showLoading("Abriendo historia desde la librería…");
    try {
      const data = await apiPost("/game/standard/start", { template_id: templateId });
      store.session_id = data.session_id;
      store.context.narrativa_inicial = data.narrativa_inicial || "";
      store.context.player_mission = data.player_mission || "";
      store.context.player_public_mission = data.player_public_mission || "";
      store.context.characters = data.characters || [];
      store.status.turn_current = data.turn_current ?? 0;
      store.status.turn_max = data.turn_max ?? 10;
      store.status.player_can_write = data.player_can_write ?? false;
      store.status.game_finished = false;
      store.status.result = null;
      store.messages = [];
      prepareStoryExperience("new");
      await fetchContext();
      await fetchStatus();
      prepareStoryExperience("new");
      ensureContextReveal(true);
      if (hasFirstActorMessage()) {
        emitClientInitMetric(store.session_id, initStartedAtMs);
      }
      await fetchGamesList();
      closeNewGameModal();
      forceStoryTab("context");
      renderAll();
    } catch (e) {
      showError(e.message || "No se pudo iniciar la historia desde la librería");
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
      store.context.player_public_mission = data.player_public_mission || "";
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
      renderLandingGames();
      return;
    }
    store.games_loading = true;
    store.games_error = null;
    renderGamesDrawer();
    renderLandingGames();
    try {
      const data = await apiGet("/game/list");
      store.games_list = Array.isArray(data.games) ? data.games : [];
    } catch (e) {
      store.games_list = [];
      store.games_error = e.message || "Error al cargar historias";
    } finally {
      store.games_loading = false;
      renderGamesDrawer();
      renderLandingGames();
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

  function truncateText(text, maxChars) {
    const clean = normalizeText(text);
    if (!clean) return "";
    if (clean.length <= maxChars) return clean;
    return `${clean.slice(0, Math.max(0, maxChars - 1)).trim()}…`;
  }

  function currentGameTitle() {
    const activeId = String(store.session_id || "");
    const games = Array.isArray(store.games_list) ? store.games_list : [];
    const currentGame = games.find((game) => String(game && game.id ? game.id : "") === activeId);
    const explicitTitle = normalizeText(currentGame && currentGame.title ? currentGame.title : "");
    if (explicitTitle && !/^partida sin t[ií]tulo$/i.test(explicitTitle) && !/^historia sin t[ií]tulo$/i.test(explicitTitle)) {
      return explicitTitle;
    }
    const firstSentence = normalizeText(store.context.narrativa_inicial).split(/[.!?]/)[0] || "";
    return truncateText(firstSentence, 54) || "Historia en curso";
  }

  function currentStoryTabIndex() {
    const idx = STORY_TAB_ORDER.indexOf(store.ui.activeStoryTab);
    return idx >= 0 ? idx : 0;
  }

  function storyStageForTab(tab) {
    const stages = Array.from($storyStages());
    return stages.find((stage) => (stage.getAttribute("data-story-stage") || "") === tab) || null;
  }

  function syncStoryPagerPosition(animate) {
    const pager = $storyPager();
    const stage = storyStageForTab(store.ui.activeStoryTab);
    if (!pager || !stage) return;
    const targetLeft = stage.offsetLeft;
    const currentLeft = pager.scrollLeft;
    if (Math.abs(currentLeft - targetLeft) < 2) return;
    pager.scrollTo({ left: targetLeft, behavior: animate ? "smooth" : "auto" });
  }

  function syncStoryTabFromPager() {
    const pager = $storyPager();
    if (!pager) return;
    const pagerLeft = pager.scrollLeft;
    const stages = STORY_TAB_ORDER
      .map((tab) => ({ tab, stage: storyStageForTab(tab) }))
      .filter((item) => item.stage);
    if (!stages.length) return;
    let closest = stages[0];
    let closestDistance = Math.abs(pagerLeft - closest.stage.offsetLeft);
    stages.slice(1).forEach((item) => {
      const distance = Math.abs(pagerLeft - item.stage.offsetLeft);
      if (distance < closestDistance) {
        closest = item;
        closestDistance = distance;
      }
    });
    const nextTab = closest.tab;
    if (store.ui.activeStoryTab === nextTab) return;
    if (store.ui.activeStoryTab === "context" && nextTab !== "context" && !store.ui.contextRevealDone) {
      completeContextReveal();
    }
    store.ui.activeStoryTab = nextTab;
    renderStoryShell();
    updateInputState();
  }

  function clearContextRevealTimer() {
    if (contextRevealTimer) {
      window.clearInterval(contextRevealTimer);
      contextRevealTimer = null;
    }
  }

  function completeContextReveal() {
    clearContextRevealTimer();
    const fullText = normalizeText(store.context.narrativa_inicial);
    store.ui.contextRevealSessionId = store.session_id;
    store.ui.contextRevealChars = fullText.length;
    store.ui.contextRevealDone = true;
  }

  function resetStoryExperience() {
    clearContextRevealTimer();
    store.ui.activeStoryTab = "context";
    store.ui.storyEntryMode = "new";
    store.ui.contextRevealChars = 0;
    store.ui.contextRevealDone = false;
    store.ui.contextRevealSessionId = null;
  }

  function prepareStoryExperience(mode) {
    clearContextRevealTimer();
    store.ui.storyEntryMode = mode === "resume" ? "resume" : "new";
    store.ui.activeStoryTab = mode === "resume" ? "chat" : "context";
    store.ui.contextRevealSessionId = store.session_id;
    if (mode === "resume") {
      const text = normalizeText(store.context.narrativa_inicial);
      store.ui.contextRevealChars = text.length;
      store.ui.contextRevealDone = true;
      return;
    }
    store.ui.contextRevealChars = 0;
    store.ui.contextRevealDone = false;
  }

  function ensureContextReveal(forceRestart) {
    const fullText = normalizeText(store.context.narrativa_inicial);
    if (!store.session_id || !fullText) {
      clearContextRevealTimer();
      return;
    }
    if (store.ui.storyEntryMode === "resume") {
      completeContextReveal();
      return;
    }
    if (forceRestart) {
      clearContextRevealTimer();
      store.ui.contextRevealChars = 0;
      store.ui.contextRevealDone = false;
      store.ui.contextRevealSessionId = store.session_id;
    }
    if (store.ui.contextRevealDone || contextRevealTimer) return;
    contextRevealTimer = window.setInterval(() => {
      const currentText = normalizeText(store.context.narrativa_inicial);
      const increment = Math.max(1, Math.ceil(currentText.length / 120));
      if (store.ui.contextRevealChars >= currentText.length) {
        completeContextReveal();
        renderStoryShell();
        return;
      }
      store.ui.contextRevealChars = Math.min(currentText.length, store.ui.contextRevealChars + increment);
      renderStoryShell();
    }, 28);
  }

  function setActiveStoryTab(tab) {
    const nextTab = STORY_TAB_ORDER.includes(tab) ? tab : "context";
    if (store.ui.activeStoryTab === nextTab) return;
    if (store.ui.activeStoryTab === "context" && nextTab !== "context" && !store.ui.contextRevealDone) {
      completeContextReveal();
    }
    store.ui.activeStoryTab = nextTab;
    renderStoryShell();
    syncStoryPagerPosition(true);
    updateInputState();
  }

  function forceStoryTab(tab) {
    const nextTab = STORY_TAB_ORDER.includes(tab) ? tab : "context";
    store.ui.activeStoryTab = nextTab;
    renderStoryShell();
    syncStoryPagerPosition(false);
    updateInputState();
  }

  function renderStoryCharactersMarkup() {
    const characters = Array.isArray(store.context.characters) ? store.context.characters : [];
    if (!characters.length) {
      return '<p class="story-empty-state">Todavía no hay personajes definidos para esta historia.</p>';
    }
    return characters
      .map((character, index) => {
        const name = normalizeText(character && character.name ? character.name : "") || `Personaje ${index + 1}`;
        const note = normalizeText(character && character.personality ? character.personality : "") || "Presencia clave en esta escena.";
        const publicMission = normalizeText(character && character.public_mission ? character.public_mission : "");
        return `
          <article class="character-sheet-card">
            <div class="character-sheet-meta">
              <span class="character-sheet-index">${String(index + 1).padStart(2, "0")}</span>
              <span class="character-sheet-role">Personaje</span>
            </div>
            <h3>${escapeHtml(name)}</h3>
            <p class="character-sheet-personality">${escapeHtml(note)}</p>
            ${publicMission ? `<p class="character-sheet-public-mission">${escapeHtml(publicMission)}</p>` : ""}
          </article>
        `;
      })
      .join("");
  }

  function renderStoryShell() {
    const shell = $storyShell();
    if (!shell) return;
    const hasSession = !!store.session_id;
    shell.classList.toggle("hidden", !hasSession);
    if (!hasSession) {
      clearContextRevealTimer();
      return;
    }

    const activeTab = store.ui.activeStoryTab;
    const fullContext = normalizeText(store.context.narrativa_inicial);
    const revealLength = store.ui.contextRevealDone
      ? fullContext.length
      : Math.min(fullContext.length, Math.max(0, store.ui.contextRevealChars));
    const contextPreview = fullContext.slice(0, revealLength);
    const mission = normalizeText(store.context.player_mission) || "Descubre la situación y decide cómo avanzar.";
    const publicMission = normalizeText(store.context.player_public_mission);

    $storyTabs().forEach((button) => {
      const tab = button.getAttribute("data-story-tab") || "";
      const selected = tab === activeTab;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-selected", selected ? "true" : "false");
      button.setAttribute("tabindex", selected ? "0" : "-1");
    });

    $storyStages().forEach((stage) => {
      const stageName = stage.getAttribute("data-story-stage") || "";
      const selected = stageName === activeTab;
      stage.setAttribute("aria-hidden", selected ? "false" : "true");
    });

    const contextStream = $contextStream();
    if (contextStream) {
      const text = contextPreview || "El guionista está preparando el contexto.";
      contextStream.innerHTML = `${escapeHtml(text)}${store.ui.contextRevealDone ? "" : '<span class="context-cursor">▍</span>'}`;
    }
    const missionPrimary = $storyMissionPrimary();
    if (missionPrimary) missionPrimary.textContent = mission;
    const missionPublicWrap = $storyMissionPublicWrap();
    if (missionPublicWrap) missionPublicWrap.classList.toggle("hidden", !publicMission);
    const missionPublicNode = $storyMissionPublic();
    if (missionPublicNode) missionPublicNode.textContent = publicMission || "—";
    const missionInline = $storyMissionInline();
    if (missionInline) missionInline.textContent = mission;
    const charactersGrid = $storyCharactersGrid();
    if (charactersGrid) charactersGrid.innerHTML = renderStoryCharactersMarkup();

    syncStoryPagerPosition(false);

    if (!store.ui.contextRevealDone && activeTab === "context") {
      ensureContextReveal(false);
    }
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
      showError("No hay historia activa para adjuntar el feedback.");
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
      showError("No hay historia activa para adjuntar el feedback.");
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
    showLoading("Reanudando historia…");
    try {
      const data = await apiPost("/game/resume", { session_id: sessionId });
      store.session_id = data.session_id || sessionId;
      prepareStoryExperience("resume");
      await fetchContext();
      await fetchStatus();
      prepareStoryExperience("resume");
      await fetchGamesList();
      closeGamesPanel();
      forceStoryTab("chat");
      renderAll();
    } catch (e) {
      showError(e.message || "No se pudo reanudar la historia");
    } finally {
      hideLoading();
    }
  }

  function buildGamesMarkup(games, options) {
    const settings = options || {};
    const itemClass = settings.itemClass || "game-item";
    const emptyMessage = settings.emptyMessage || "No hay historias disponibles.";
    const limit = Number.isInteger(settings.limit) ? settings.limit : games.length;
    const visibleGames = games.slice(0, Math.max(0, limit));
    if (!visibleGames.length) {
      return `<p class="games-list-state">${escapeHtml(emptyMessage)}</p>`;
    }
    return visibleGames
      .map((g) => {
        const gameId = String(g.id || "");
        const title = String(g.title || "Historia sin título");
        const updatedLabel = formatRelativeDate(g.updated_at);
        const activeClass = gameId === store.session_id ? " is-active" : "";
        const statusLabel = gameId === store.session_id ? "Activa" : "Continuar";
        return `
          <button type="button" class="${itemClass}${activeClass}" data-game-id="${escapeHtml(gameId)}">
            <span class="game-item-title">${escapeHtml(title)}</span>
            <span class="game-item-meta">
              <span class="game-item-status">${escapeHtml(statusLabel)}</span>
              <span class="game-item-date">${escapeHtml(updatedLabel)}</span>
            </span>
          </button>
        `;
      })
      .join("");
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
    const sTurn = $statusTurn();
    const sSpeaker = $statusSpeaker();
    const sInput = $statusInput();
    const sEnded = $statusEnded();
    const topbarTitleBlock = $topbarTitleBlock();
    const topbarStoryTitle = $topbarStoryTitle();
    const topbarStatus = $topbarStatus();
    const topbarTurn = $topbarTurn();
    const topbarGame = $topbarGame();
    if (sTurn) sTurn.textContent = store.session_id ? `${s.turn_current} / ${s.turn_max}` : "—";
    if (sSpeaker) sSpeaker.textContent = store.session_id ? (s.current_speaker || "Jugador") : "—";
    if (sInput) sInput.textContent = store.session_id ? (s.player_can_write ? "Abierta" : "Bloqueada") : "—";
    if (sEnded) sEnded.textContent = store.session_id ? (s.game_finished ? "Finalizada" : "En curso") : "—";
    if (topbarTitleBlock) topbarTitleBlock.classList.toggle("hidden", !store.session_id);
    if (topbarStoryTitle) topbarStoryTitle.textContent = store.session_id ? currentGameTitle() : "";
    if (topbarStatus) topbarStatus.classList.toggle("hidden", !store.session_id);
    if (topbarTurn) topbarTurn.textContent = store.session_id ? `Turno ${s.turn_current}/${s.turn_max}` : "—";
    if (topbarGame) {
      const hasVictory = isPlayerVictory();
      const hasEnded = !!(store.session_id && s.game_finished);
      topbarGame.classList.toggle("hidden", !hasEnded);
      topbarGame.textContent = hasVictory ? "🏆 Victoria" : "Historia finalizada";
    }
  }

  function renderLandingGames() {
    const list = $landingGamesList();
    if (!list) return;
    if (store.games_loading) {
      list.innerHTML = '<p class="games-list-state">Cargando historias…</p>';
      return;
    }
    if (store.games_error) {
      list.innerHTML = `<p class="games-list-state games-list-error">${escapeHtml(store.games_error)}</p>`;
      return;
    }
    const games = Array.isArray(store.games_list) ? store.games_list : [];
    list.innerHTML = buildGamesMarkup(games, {
      limit: LANDING_GAMES_LIMIT,
      itemClass: "game-item landing-game-item",
      emptyMessage: "Todavía no tienes historias. Crea una y entra en tu primera historia.",
    });
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
      list.innerHTML = '<p class="games-list-state">Cargando historias…</p>';
      return;
    }
    if (store.games_error) {
      list.innerHTML = `<p class="games-list-state games-list-error">${escapeHtml(store.games_error)}</p>`;
      return;
    }
    const games = Array.isArray(store.games_list) ? store.games_list : [];
    list.innerHTML = buildGamesMarkup(games, {
      emptyMessage: "Aún no tienes historias guardadas.",
    });
  }

  function renderLanding() {
    const hasSession = !!store.session_id;
    const workspace = $workspace();
    const landing = $landingView();
    const storyShell = $storyShell();
    const topbarTitleBlock = $topbarTitleBlock();
    const rightRail = $rightRail();
    if (workspace) workspace.classList.toggle("workspace-landing", !hasSession);
    if (workspace) workspace.classList.toggle("workspace-story", hasSession);
    if (landing) landing.classList.toggle("hidden", hasSession);
    if (storyShell) storyShell.classList.toggle("hidden", !hasSession);
    if (topbarTitleBlock) topbarTitleBlock.classList.toggle("hidden", !hasSession);
    if (rightRail) rightRail.classList.add("hidden");
    renderLandingGames();
    renderStoryShell();
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
        <div class="victory-kicker">Historia finalizada</div>
        <h2 class="victory-title">Victoria del jugador</h2>
        <p class="victory-subtitle">${escapeHtml(detail)}</p>
        <p class="victory-note">El chat queda bloqueado. Puedes usar el menú superior para feedback, usuario o una nueva historia.</p>
      </section>
    `;
  }

  function updateInputState() {
    const s = store.status;
    const blockedByVictory = isPlayerVictory();
    const canWrite = store.session_id
      && store.ui.activeStoryTab === "chat"
      && s.player_can_write
      && !s.game_finished
      && !blockedByVictory;
    const playerInput = $playerInput();
    const sendBtn = $btnSend();
    if (playerInput) {
      playerInput.disabled = !canWrite;
      playerInput.placeholder = blockedByVictory
        ? "Historia ganada. Ya no puedes escribir en este chat."
        : store.ui.activeStoryTab !== "chat"
          ? "Entra en la pestaña Chat para escribir."
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
    if (!store.session_id) {
      store.ui.storyPanelOpen = false;
      store.ui.briefingOpen = false;
      store.ui.feedbackOpen = false;
      store.ui.feedbackSubmitting = false;
      store.ui.feedbackError = null;
    }
    renderUserMenu();
    renderSidebar();
    renderLanding();
    renderGamesDrawer();
    renderOverlayPanels();
    renderVictoryOverlay();
    renderChat();
    updateInputState();
  }

  function resetPartida() {
    resetStoryExperience();
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
      showError("No hay historia activa. Crea una nueva historia.");
      return;
    }
    if (!text) return;
    const inputError = validatePlayerMessage(text);
    if (inputError) {
      showError(inputError);
      return;
    }
    clearError();

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
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${res.status}`);
      }

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
      const lastMessage = store.messages[store.messages.length - 1];
      if (lastMessage === userMsg) store.messages.pop();
      showError(e.message || "Error al enviar");
      clearStreamingState();
      await fetchStatus();
      await fetchGamesList();
    }
    renderAll();
  }

  function initTheme() {
    const storedTheme = safeGetItem("agora-ui-theme", "light");
    applyTheme(storedTheme === "dark" ? "dark" : "light");
  }

  function toggleTheme() {
    const dark = document.body.classList.contains("theme-dark");
    applyTheme(dark ? "light" : "dark");
  }

  function applyTheme(theme) {
    const nextTheme = theme === "dark" ? "dark" : "light";
    const dark = nextTheme === "dark";
    safeSetItem("agora-ui-theme", nextTheme);
    document.body.classList.toggle("theme-dark", dark);
    document.body.classList.toggle("theme-light", !dark);
    const toggle = $btnThemeToggle();
    const icon = $themeToggleIcon();
    if (toggle) {
      toggle.setAttribute("aria-label", dark ? "Activar modo claro" : "Activar modo oscuro");
      toggle.setAttribute("title", dark ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
    }
    if (icon) icon.textContent = dark ? "☾" : "☀";
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
  const btnLandingCustom = $btnLandingCustom();
  const btnLandingStandard = $btnLandingStandard();
  const btnLandingAllGames = $btnLandingAllGames();
  const landingGamesList = $landingGamesList();
  const storyPager = $storyPager();
  const btnHome = $btnHome();
  const btnThemeToggle = $btnThemeToggle();
  const playerInput = $playerInput();
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
  if (btnHome) {
    btnHome.addEventListener("click", () => {
      toggleUserMenu(false);
      closeGamesPanel();
      closeStoryPanel();
      closeBriefingModal();
      closeFeedbackModal();
      resetPartida();
    });
  }
  if (btnNew) btnNew.addEventListener("click", () => openNewGameModal("mode"));
  if (btnThemeToggle) btnThemeToggle.addEventListener("click", toggleTheme);
  if (btnSend) btnSend.addEventListener("click", sendTurn);
  if (btnCreateGame) btnCreateGame.addEventListener("click", submitNewGameFromForm);
  if (btnCancelNewGame) btnCancelNewGame.addEventListener("click", closeNewGameModal);
  if (btnLandingCustom) {
    btnLandingCustom.addEventListener("click", () => openCustomNewGameModal());
  }
  if (btnLandingStandard) {
    btnLandingStandard.addEventListener("click", async () => {
      await openStandardNewGameModal();
    });
  }
  if (btnLandingAllGames) {
    btnLandingAllGames.addEventListener("click", async () => {
      await fetchGamesList();
      openGamesPanel();
    });
  }
  $storyTabs().forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.getAttribute("data-story-tab");
      if (!tab) return;
      setActiveStoryTab(tab);
    });
  });
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
  if (landingGamesList) {
    landingGamesList.addEventListener("click", (e) => {
      const target = e.target && e.target.closest ? e.target.closest("[data-game-id]") : null;
      if (!target) return;
      const gameId = target.getAttribute("data-game-id");
      if (!gameId || gameId === store.session_id) return;
      resumeGame(gameId);
    });
  }
  if (storyPager) {
    storyPager.addEventListener("scroll", () => {
      if (storyPagerScrollTimer) window.clearTimeout(storyPagerScrollTimer);
      storyPagerScrollTimer = window.setTimeout(() => {
        storyPagerScrollTimer = null;
        syncStoryTabFromPager();
      }, 90);
    }, { passive: true });
  }
  window.addEventListener("resize", () => {
    syncStoryPagerPosition(false);
  });

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
      window.location.assign("/admin/panel-control/");
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
