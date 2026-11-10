/**
 * Podcast Buddy - Frontend Client Logic
 * Vanilla JavaScript (Phase 3: SerpAPI News Discovery)
 *
 * NOTE: All external API credentials (SERPAPI_API_KEY) remain strictly server-side.
 * The frontend communicates exclusively with the local Flask backend endpoint:
 * GET /api/news/search?q=<query>
 */

document.addEventListener("DOMContentLoaded", () => {
  // Determine API base URL (works for Flask-hosted and local development)
  const isHttp = window.location.protocol.startsWith("http");
  const API_BASE = isHttp ? window.location.origin : "http://127.0.0.1:5000";

  // Elements: Search & Input
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const searchClearBtn = document.getElementById("search-clear-btn");
  const searchBtn = document.getElementById("search-btn");
  const topicChips = document.querySelectorAll(".topic-chip");

  // Elements: Informational Banner
  const infoBanner = document.getElementById("search-info-banner");
  const infoBannerTitle = document.getElementById("info-banner-title");
  const infoBannerMessage = document.getElementById("info-banner-message");
  const infoBannerClose = document.getElementById("info-banner-close");
  let bannerTimeout = null;

  // Elements: News Section Views
  const newsLoadingState = document.getElementById("news-loading-state");
  const newsErrorState = document.getElementById("news-error-state");
  const newsErrorTitle = document.getElementById("news-error-title");
  const newsErrorMessage = document.getElementById("news-error-message");
  const newsErrorRetryBtn = document.getElementById("news-error-retry-btn");
  const newsEmptyState = document.getElementById("news-empty-state");
  const newsResultsGrid = document.getElementById("news-results-grid");
  const feedStatusLabel = document.getElementById("feed-status-label");

  // Elements: Article Selection & Creation (Phase 4)
  const selectionCounterBadge = document.getElementById("selection-counter-badge");
  const selectionCounterText = document.getElementById("selection-counter-text");
  const btnCreatePodcast = document.getElementById("btn-create-podcast");
  const btnCreatePodcastText = document.getElementById("btn-create-podcast-text");

  // Elements: Episode Creation Panel (Phase 4)
  const episodeCreationPanel = document.getElementById("episode-creation-panel");
  const btnCloseCreationPanel = document.getElementById("btn-close-creation-panel");
  const episodeTitleInput = document.getElementById("episode-title-input");
  const episodeDescInput = document.getElementById("episode-desc-input");
  const sourcesCountBadge = document.getElementById("sources-count-badge");
  const episodeCreationStatus = document.getElementById("episode-creation-status");
  const episodeCreationStatusText = document.getElementById("episode-creation-status-text");
  const btnSubmitEpisode = document.getElementById("btn-submit-episode");
  const btnCancelEpisode = document.getElementById("btn-cancel-episode");

  // Elements: Episodes Library (Phase 4 & Phase 2 Enhancement)
  const episodesListContainer = document.getElementById("episodes-list-container");
  const episodesEmptyState = document.getElementById("episodes-empty-state");
  const btnRefreshEpisodes = document.getElementById("btn-refresh-episodes");
  const episodesSearchInput = document.getElementById("episodes-search-input");
  const btnClearSearchText = document.getElementById("btn-clear-search-text");
  const episodesFilterLanguage = document.getElementById("episodes-filter-language");
  const episodesFilterStatus = document.getElementById("episodes-filter-status");
  const btnClearFilters = document.getElementById("btn-clear-filters");
  const episodesFilterSummary = document.getElementById("episodes-filter-summary");
  const episodesFilterCountText = document.getElementById("episodes-filter-count-text");
  const playerSpeedSelector = document.getElementById("player-speed-selector");

  // Elements: AI Intelligence Viewer (Phase 5)
  const aiIntelligenceViewer = document.getElementById("ai-intelligence-viewer");
  const btnCloseAiViewer = document.getElementById("btn-close-ai-viewer");
  const aiViewerTitle = document.getElementById("ai-viewer-title");
  const aiViewerMeta = document.getElementById("ai-viewer-meta");
  const aiOverviewText = document.getElementById("ai-overview-text");
  const aiKeyPointsList = document.getElementById("ai-key-points-list");
  const aiFactsList = document.getElementById("ai-facts-list");
  const aiTopicsChips = document.getElementById("ai-topics-chips");
  const aiEntitiesChips = document.getElementById("ai-entities-chips");
  const aiSourcesInsightsContainer = document.getElementById("ai-sources-insights-container");
  const aiConfidencePill = document.getElementById("ai-confidence-pill");
  const aiLimitationsList = document.getElementById("ai-limitations-list");

  // Elements: Podcast Studio & Audio (Phase 6 & 7)
  const podcastStudioViewer = document.getElementById("podcast-studio-viewer");
  const btnCloseStudioViewer = document.getElementById("btn-close-studio-viewer");
  const studioViewerTitle = document.getElementById("studio-viewer-title");
  const studioViewerMeta = document.getElementById("studio-viewer-meta");
  const studioActiveTrackPill = document.getElementById("studio-active-track-pill");
  const audioLanguageSelect = document.getElementById("audio-language-select");
  const btnGenerateAudio = document.getElementById("btn-generate-audio");
  const btnGenerateAudioText = document.getElementById("btn-generate-audio-text");
  const btnGenerateScriptInStudio = document.getElementById("btn-generate-script-in-studio");
  const btnGenerateScriptText = document.getElementById("btn-generate-script-text");
  const audioStatusBanner = document.getElementById("audio-status-banner");
  const audioStatusIcon = document.getElementById("audio-status-icon");
  const audioStatusTitle = document.getElementById("audio-status-title");
  const audioStatusMsg = document.getElementById("audio-status-msg");
  const audioPlayerContainer = document.getElementById("audio-player-container");
  const audioPlayerLanguage = document.getElementById("audio-player-language");
  const audioPlayerTimestamp = document.getElementById("audio-player-timestamp");
  const audioPlayerDuration = document.getElementById("audio-player-duration");
  const htmlPodcastAudio = document.getElementById("html-podcast-audio");
  const scriptDialogueContainer = document.getElementById("script-dialogue-container");
  const btnDownloadAudio = document.getElementById("btn-download-audio");
  const btnCopyScript = document.getElementById("btn-copy-script");
  const btnCopyScriptText = document.getElementById("btn-copy-script-text");

  // Elements: Main Podcast Player Card
  const mainProgressBar = document.getElementById("main-progress-bar");
  const mainProgressFill = document.getElementById("main-progress-fill");
  const mainTimeCurrent = document.getElementById("main-time-current");
  const mainTimeDuration = document.getElementById("main-time-duration");
  const mainRewindBtn = document.getElementById("main-rewind-btn");
  const mainPlayBtn = document.getElementById("main-play-btn");
  const mainPlayIcon = document.getElementById("main-play-icon");
  const mainPauseIcon = document.getElementById("main-pause-icon");
  const mainForwardBtn = document.getElementById("main-forward-btn");
  const mainSpeedBtn = document.getElementById("main-speed-btn");
  const mainPlayerNote = document.getElementById("main-player-note");
  const playerHeading = document.getElementById("player-heading");
  const playerSubheading = document.getElementById("player-subheading");
  const playerPhaseBadge = document.getElementById("player-phase-badge");
  const waveformBars = document.querySelector(".waveform-bars");
  const studioLangPills = document.querySelectorAll(".lang-pill-btn");
  const mainVolumeSlider = document.getElementById("main-volume-slider");
  const mainVolumeBtn = document.getElementById("main-volume-btn");
  const volumeIconHigh = document.getElementById("volume-icon-high");
  const volumeIconMuted = document.getElementById("volume-icon-muted");
  let lastNonZeroVolume = 1.0;
  let allLoadedEpisodes = [];
  let currentPlayingEpisode = null;

  // Elements: Backend Diagnostics
  const statusIndicator = document.getElementById("backend-status-indicator");
  const statusText = document.getElementById("backend-status-text");
  const outputBox = document.getElementById("api-output-box");
  const timestampEl = document.getElementById("api-timestamp");
  const btnCheckHealth = document.getElementById("btn-check-health");
  const btnCheckRoot = document.getElementById("btn-check-root");

  // Application State
  const selectedArticleIds = new Set();
  let currentArticles = [];
  let currentStudioEpisode = null;

  let lastSearchedQuery = "";
  let currentSearchController = null;
  let activeSearchSeq = 0;
  let isSubmittingEpisode = false;

  // =========================================================================
  // 1. Search Box & Clear Button Logic
  // =========================================================================
  function updateClearButtonVisibility() {
    if (!searchInput || !searchClearBtn) return;
    searchClearBtn.hidden = searchInput.value.trim().length === 0;
  }

  if (searchInput) {
    searchInput.addEventListener("input", updateClearButtonVisibility);

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        triggerSearch();
      }
    });
  }

  if (searchClearBtn) {
    searchClearBtn.addEventListener("click", () => {
      if (searchInput) {
        searchInput.value = "";
        searchInput.focus();
      }
      updateClearButtonVisibility();
      topicChips.forEach(chip => chip.classList.remove("active"));
    });
  }

  // =========================================================================
  // 2. Banner Notification Helper
  // =========================================================================
  function showInfoBanner(title, message) {
    if (!infoBanner) return;
    if (infoBannerTitle) infoBannerTitle.textContent = title;
    if (infoBannerMessage) infoBannerMessage.textContent = message;

    infoBanner.hidden = false;

    if (bannerTimeout) clearTimeout(bannerTimeout);
    bannerTimeout = setTimeout(() => {
      hideInfoBanner();
    }, 6000);
  }

  function hideInfoBanner() {
    if (!infoBanner) return;
    infoBanner.hidden = true;
    if (bannerTimeout) clearTimeout(bannerTimeout);
  }

  if (infoBannerClose) {
    infoBannerClose.addEventListener("click", hideInfoBanner);
  }

  // =========================================================================
  // 3. Selection Counter Management (Step 10)
  // =========================================================================
  function updateSelectionCounter() {
    const count = selectedArticleIds.size;
    if (selectionCounterBadge && selectionCounterText) {
      if (count > 0) {
        selectionCounterBadge.hidden = false;
        selectionCounterText.textContent = `${count} stor${count === 1 ? 'y' : 'ies'} selected`;
      } else {
        selectionCounterBadge.hidden = true;
        selectionCounterText.textContent = "0 stories selected";
      }
    }

    // Phase 4: Update Create Podcast button state
    if (btnCreatePodcast) {
      btnCreatePodcast.disabled = count === 0;
      if (btnCreatePodcastText) {
        btnCreatePodcastText.textContent = count > 0 ? `Create Podcast (${count})` : "Create Podcast";
      }
    }

    if (sourcesCountBadge) {
      sourcesCountBadge.textContent = `${count} article${count === 1 ? '' : 's'}`;
    }
  }

  function toggleArticleSelection(articleId, cardElement, selectBtn) {
    if (selectedArticleIds.has(articleId)) {
      selectedArticleIds.delete(articleId);
      cardElement.classList.remove("selected");
      selectBtn.innerHTML = `<span>+</span> Select`;
      selectBtn.setAttribute("aria-pressed", "false");
    } else {
      selectedArticleIds.add(articleId);
      cardElement.classList.add("selected");
      selectBtn.innerHTML = `<span>✓</span> Selected`;
      selectBtn.setAttribute("aria-pressed", "true");
    }
    updateSelectionCounter();
  }

  // =========================================================================
  // 4. News State Management (Loading, Error, Results, Empty)
  // =========================================================================
  function setNewsView(view, errorData = null) {
    // Hide all dynamic states explicitly with hidden, display: none, and active class removal
    if (newsLoadingState) {
      newsLoadingState.hidden = true;
      newsLoadingState.style.display = "none";
      newsLoadingState.classList.remove("active");
    }
    if (newsErrorState) {
      newsErrorState.hidden = true;
      newsErrorState.style.display = "none";
      newsErrorState.classList.remove("active");
    }
    if (newsEmptyState) {
      newsEmptyState.hidden = true;
      newsEmptyState.style.display = "none";
      newsEmptyState.classList.remove("active");
    }
    if (newsResultsGrid) {
      newsResultsGrid.hidden = true;
      newsResultsGrid.style.display = "none";
      newsResultsGrid.classList.remove("active");
    }

    if (view === "loading") {
      if (newsLoadingState) {
        newsLoadingState.hidden = false;
        newsLoadingState.style.display = "flex";
        newsLoadingState.classList.add("active");
      }
    } else if (view === "error") {
      if (newsErrorState) {
        newsErrorState.hidden = false;
        newsErrorState.style.display = "flex";
        newsErrorState.classList.add("active");
        if (newsErrorTitle) newsErrorTitle.textContent = errorData?.title || "Search Failed";
        if (newsErrorMessage) newsErrorMessage.textContent = errorData?.message || "An unexpected error occurred.";
        if (newsErrorRetryBtn) newsErrorRetryBtn.hidden = !errorData?.retryable;
      }
    } else if (view === "results") {
      if (newsResultsGrid) {
        newsResultsGrid.hidden = false;
        newsResultsGrid.style.display = "grid";
        newsResultsGrid.classList.add("active");
      }
    } else if (view === "empty") {
      if (newsEmptyState) {
        newsEmptyState.hidden = false;
        newsEmptyState.style.display = "flex";
        newsEmptyState.classList.add("active");
        const emptyTitle = newsEmptyState.querySelector(".empty-title");
        const emptyDesc = newsEmptyState.querySelector(".empty-desc");
        if (emptyTitle) {
          emptyTitle.textContent = errorData?.message || "Search for a topic to discover the latest news.";
        }
        if (emptyDesc && errorData?.subtext) {
          emptyDesc.textContent = errorData.subtext;
        }
      }
    }
  }

  // =========================================================================
  // 5. Render Normalized News Results (Step 6)
  // =========================================================================
  function renderNewsCards(articles) {
    if (!newsResultsGrid) return;
    newsResultsGrid.innerHTML = "";

    if (!articles || articles.length === 0) {
      setNewsView("empty", {
        message: `No news found for "${lastSearchedQuery}".`,
        subtext: "Try a broader keyword or choose one of the Quick Topics above."
      });
      return;
    }

    articles.forEach((item) => {
      const isSelected = selectedArticleIds.has(item.id);

      const card = document.createElement("article");
      card.className = `news-card ${isSelected ? "selected" : ""}`;
      card.dataset.id = item.id;

      // Safe field values
      const title = escapeHtml(item.title || "Untitled Article");
      const publisher = escapeHtml(item.publisher || "Unknown Publisher");
      const date = item.date ? escapeHtml(item.date) : "";
      const rawSnippet = item.snippet && item.snippet.trim();
      const snippet = escapeHtml(rawSnippet || `Coverage from ${publisher}. Click Read Source for full reporting.`);
      const url = item.url ? encodeURI(item.url) : "#";

      card.innerHTML = `
        <div class="news-card-body">
          <div class="news-card-header">
            <span class="publisher-badge" title="${publisher}">${publisher}</span>
            <span class="source-verified-badge" title="Original publisher source article"><span class="badge-dot green"></span> Verified Source</span>
            ${date ? `<span class="news-date">${date}</span>` : ""}
          </div>
          <h3 class="news-card-title">${title}</h3>
          <p class="news-card-snippet">${snippet}</p>
        </div>
        <div class="news-card-footer">
          ${item.url ? `
            <a href="${url}" target="_blank" rel="noopener noreferrer" class="read-source-link" title="Open verified publisher article">
              <span>Read Source</span>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
            </a>
          ` : `<span class="news-date">Direct link unavailable</span>`}
          <button type="button" class="select-story-btn" aria-pressed="${isSelected}">
            ${isSelected ? "<span>✓</span> Selected" : "<span>+</span> Select"}
          </button>
        </div>
      `;

      // Wire select button
      const selectBtn = card.querySelector(".select-story-btn");
      if (selectBtn) {
        selectBtn.addEventListener("click", () => {
          toggleArticleSelection(item.id, card, selectBtn);
        });
      }

      newsResultsGrid.appendChild(card);
    });

    setNewsView("results");
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // =========================================================================
  // 6. Search Execution (Step 6, 7, 8)
  // =========================================================================
  async function searchNews(query) {
    const cleanQuery = (query || "").trim();

    if (!cleanQuery) {
      showInfoBanner("Search Notice", "Please enter a topic to search news.");
      if (searchInput) searchInput.focus();
      return;
    }

    if (currentSearchController) {
      currentSearchController.abort();
    }
    currentSearchController = new AbortController();
    const thisSeq = ++activeSearchSeq;

    lastSearchedQuery = cleanQuery;
    hideInfoBanner();

    // Disable search button & show loading state (Step 7)
    if (searchBtn) {
      searchBtn.disabled = true;
      searchBtn.classList.add("loading");
    }

    // Immediately reset previous search indicators and results so stale data never persists
    if (feedStatusLabel) {
      feedStatusLabel.textContent = "SerpAPI: Searching...";
    }
    if (newsResultsGrid) {
      newsResultsGrid.innerHTML = "";
    }
    currentArticles = [];
    selectedArticleIds.clear();
    updateSelectionCounter();

    setNewsView("loading");

    try {
      const endpoint = `${API_BASE}/api/news/search?q=${encodeURIComponent(cleanQuery)}`;
      const response = await fetch(endpoint, {
        signal: currentSearchController.signal,
        headers: { "Accept": "application/json" }
      });
      const data = await response.json();

      if (thisSeq !== activeSearchSeq) return;

      if (response.ok && data.success) {
        currentArticles = data.results || [];
        renderNewsCards(currentArticles);
        if (feedStatusLabel) {
          feedStatusLabel.textContent = `SerpAPI: ${currentArticles.length} stories`;
        }
      } else {
        // Step 8: Error handling
        currentArticles = [];
        selectedArticleIds.clear();
        updateSelectionCounter();
        if (newsResultsGrid) newsResultsGrid.innerHTML = "";
        if (feedStatusLabel) feedStatusLabel.textContent = "SerpAPI: Search Unavailable";

        const errorMessage = data.error || "Unable to fetch news from discovery service.";
        const isTimeout = response.status === 504;
        const isConfig = response.status === 503;
        setNewsView("error", {
          title: isConfig ? "API Key Configuration Required" : (isTimeout ? "News Search Timed Out" : "News Search Unavailable"),
          message: errorMessage,
          retryable: !isConfig
        });
        showInfoBanner("Search Notice", errorMessage);
      }
    } catch (err) {
      if (err.name === "AbortError") {
        return;
      }
      if (thisSeq !== activeSearchSeq) return;

      currentArticles = [];
      selectedArticleIds.clear();
      updateSelectionCounter();
      if (newsResultsGrid) newsResultsGrid.innerHTML = "";
      if (feedStatusLabel) feedStatusLabel.textContent = "SerpAPI: Connection Error";

      setNewsView("error", {
        title: "Connection Error",
        message: "Failed to communicate with the local backend server. Please verify Flask is running.",
        retryable: true
      });
      showInfoBanner("Connection Error", "Could not connect to Flask backend.");
    } finally {
      if (thisSeq === activeSearchSeq && searchBtn) {
        searchBtn.disabled = false;
        searchBtn.classList.remove("loading");
      }
    }
  }

  function triggerSearch() {
    const query = (searchInput && searchInput.value.trim()) || lastSearchedQuery || "";
    searchNews(query);
  }

  if (searchBtn) {
    searchBtn.addEventListener("click", (e) => {
      e.preventDefault();
      triggerSearch();
    });
  }

  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      triggerSearch();
    });
  }

  if (newsErrorRetryBtn) {
    newsErrorRetryBtn.addEventListener("click", () => {
      triggerSearch();
    });
  }

  // =========================================================================
  // 7. Quick Topics (Step 9: Real Search on Click)
  // =========================================================================
  topicChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const topic = chip.getAttribute("data-topic");
      if (!topic || !searchInput) return;

      // Populate input
      searchInput.value = topic;
      updateClearButtonVisibility();

      // Highlight active topic chip
      topicChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");

      // Scroll smoothly to news results if needed
      const resultsSection = document.getElementById("news-results");
      if (resultsSection) {
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      // Immediately execute search (Step 9)
      searchNews(topic);
    });
  });

  // =========================================================================
  // 8. Backend Diagnostics & Health Monitoring (Preserved Phase 1)
  // =========================================================================
  function setBackendStatus(state, message) {
    if (statusIndicator) {
      statusIndicator.classList.remove("status-pending", "status-connected", "status-disconnected");
      if (state === "connected") {
        statusIndicator.classList.add("status-connected");
        statusIndicator.setAttribute("title", `Backend: ${message || "Online"}`);
        statusIndicator.setAttribute("aria-label", `Backend: ${message || "Online"}`);
      } else if (state === "disconnected") {
        statusIndicator.classList.add("status-disconnected");
        statusIndicator.setAttribute("title", "Backend: Offline");
        statusIndicator.setAttribute("aria-label", "Backend: Offline");
      } else {
        statusIndicator.classList.add("status-pending");
        statusIndicator.setAttribute("title", message || "Backend: Checking...");
        statusIndicator.setAttribute("aria-label", message || "Backend: Checking...");
      }
    }

    const diagBadge = document.getElementById("diag-backend-status-badge");
    if (diagBadge) {
      diagBadge.className = `diag-status-pill ${state === "connected" ? "connected" : state === "disconnected" ? "disconnected" : "pending"}`;
      diagBadge.textContent = state === "connected" ? (message || "Online") : state === "disconnected" ? "Offline" : "Checking...";
    }

    if (statusText) {
      statusText.textContent = state === "connected" ? `Backend: ${message || "Online"}` : state === "disconnected" ? "Backend: Offline" : (message || "Backend: Checking...");
    }
  }

  function displayConsoleOutput(data, endpoint) {
    if (!outputBox || !timestampEl) return;
    const now = new Date().toLocaleTimeString();
    timestampEl.textContent = `${endpoint} at ${now}`;
    outputBox.innerHTML = `<code>${JSON.stringify(data, null, 2)}</code>`;
  }

  async function fetchEndpoint(endpoint) {
    const url = `${API_BASE}${endpoint}`;
    try {
      const response = await fetch(url, {
        headers: { "Accept": "application/json" }
      });
      const data = await response.json();
      return { success: response.ok, status: response.status, data };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: {
          error: "Failed to connect to Flask backend",
          details: error.message,
          hint: "Ensure 'python backend/app.py' is running on port 5000."
        }
      };
    }
  }

  async function checkHealth() {
    setBackendStatus("pending", "Checking...");
    const result = await fetchEndpoint("/health");
    if (result.success && result.data.status === "healthy") {
      setBackendStatus("connected", "Online (Healthy)");
    } else {
      setBackendStatus("disconnected");
    }
    displayConsoleOutput(result.data, "GET /health");
  }

  async function checkRoot() {
    const result = await fetchEndpoint("/");
    if (result.success) {
      setBackendStatus("connected", result.data.status || "Running");
    } else {
      setBackendStatus("disconnected");
    }
    displayConsoleOutput(result.data, "GET /");
  }

  if (btnCheckHealth) {
    btnCheckHealth.addEventListener("click", checkHealth);
  }

  if (btnCheckRoot) {
    btnCheckRoot.addEventListener("click", checkRoot);
  }

  // =========================================================================
  // 9. Episode Creation & Stored Library (Phase 4)
  // =========================================================================
  function openCreationPanel() {
    if (selectedArticleIds.size === 0) {
      showInfoBanner("Selection Required", "Please select at least one news article to create a podcast episode.");
      return;
    }

    if (!episodeCreationPanel) return;

    // Reset status
    setCreationStatus(null);

    // Pre-populate sensible title if empty
    if (episodeTitleInput && !episodeTitleInput.value.trim()) {
      const topic = lastSearchedQuery ? `${lastSearchedQuery} Digest` : "Curated News Roundup";
      const today = new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
      episodeTitleInput.value = `${topic} – ${today}`;
    }

    updateSelectionCounter();
    episodeCreationPanel.hidden = false;
    episodeCreationPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });

    if (episodeTitleInput) {
      episodeTitleInput.focus();
    }
  }

  function closeCreationPanel() {
    if (!episodeCreationPanel) return;
    episodeCreationPanel.hidden = true;
    setCreationStatus(null);
  }

  function setCreationStatus(state, message = "") {
    if (!episodeCreationStatus || !episodeCreationStatusText) return;

    if (!state) {
      episodeCreationStatus.hidden = true;
      episodeCreationStatus.className = "creation-status-box";
      episodeCreationStatusText.textContent = "";
      return;
    }

    episodeCreationStatus.hidden = false;
    episodeCreationStatus.className = `creation-status-box ${state}`;
    episodeCreationStatusText.textContent = message;
  }

  async function submitEpisodeCreation() {
    if (isSubmittingEpisode) return;

    const count = selectedArticleIds.size;
    if (count === 0) {
      setCreationStatus("error", "At least one article must be selected.");
      return;
    }

    const title = episodeTitleInput ? episodeTitleInput.value.trim() : "";
    if (!title) {
      setCreationStatus("error", "Episode title is required.");
      if (episodeTitleInput) episodeTitleInput.focus();
      return;
    }

    const description = episodeDescInput ? episodeDescInput.value.trim() : "";

    // Collect full article objects for selected IDs
    const selectedArticles = currentArticles.filter(a => selectedArticleIds.has(a.id));
    if (selectedArticles.length === 0) {
      setCreationStatus("error", "Selected articles not found in memory. Please refresh and select again.");
      return;
    }

    // Set loading state (Requirement 14: "Creating podcast...")
    isSubmittingEpisode = true;
    setCreationStatus("loading", "Creating podcast...");
    if (btnSubmitEpisode) {
      btnSubmitEpisode.disabled = true;
    }

    try {
      const response = await fetch(`${API_BASE}/api/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          title: title,
          description: description,
          articles: selectedArticles
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        const createdEp = data.episode;
        // Requirement 14: "Podcast episode created successfully."
        setCreationStatus("success", `Podcast episode created successfully. (Episode #${createdEp.id}: "${createdEp.title}" – Status: ${createdEp.status})`);
        showInfoBanner("Episode Created", `Podcast episode created successfully. (ID: #${createdEp.id})`);

        // Update player preview heading to reflect created episode
        const playerHeading = document.querySelector(".player-heading");
        const playerSubheading = document.querySelector(".player-subheading");
        if (playerHeading) playerHeading.textContent = createdEp.title;
        if (playerSubheading) playerSubheading.textContent = `Status: ${createdEp.status.toUpperCase()} • ${createdEp.sources.length} sources bundled`;

        // Clear article selections
        selectedArticleIds.clear();
        document.querySelectorAll(".news-card.selected").forEach(card => card.classList.remove("selected"));
        document.querySelectorAll(".select-story-btn").forEach(btn => {
          btn.innerHTML = `<span>+</span> Select`;
          btn.setAttribute("aria-pressed", "false");
        });
        updateSelectionCounter();

        // Refresh stored episodes library
        fetchEpisodes();

        // Auto-close creation panel after 3 seconds
        setTimeout(() => {
          closeCreationPanel();
        }, 3000);
      } else {
        // Requirement 14: "Unable to create podcast. Please try again."
        const errorMsg = data.error || "Unable to create podcast. Please try again.";
        setCreationStatus("error", errorMsg);
      }
    } catch (err) {
      setCreationStatus("error", "Unable to create podcast. Please try again.");
    } finally {
      isSubmittingEpisode = false;
      if (btnSubmitEpisode) {
        btnSubmitEpisode.disabled = false;
      }
    }
  }

  // =========================================================================
  // Phase 2 Enhancement: Saved Episodes Search, Filter & Clear Controllers
  // =========================================================================
  let currentEpisodesSearchTerm = "";
  let currentEpisodesLanguageFilter = "all";
  let currentEpisodesStatusFilter = "all";

  function filterAndRenderEpisodes() {
    if (!Array.isArray(allLoadedEpisodes)) {
      renderEpisodesList([]);
      return;
    }

    const query = (currentEpisodesSearchTerm || "").trim().toLowerCase();
    const langFilter = (currentEpisodesLanguageFilter || "all").toLowerCase();
    const statusFilter = (currentEpisodesStatusFilter || "all").toLowerCase();

    const isFilteringActive = Boolean(query || langFilter !== "all" || statusFilter !== "all");

    const filtered = allLoadedEpisodes.filter(ep => {
      // 1. Search term match (title and description)
      if (query) {
        const titleMatch = (ep.title || "").toLowerCase().includes(query);
        const descMatch = (ep.description || "").toLowerCase().includes(query);
        if (!titleMatch && !descMatch) return false;
      }

      // 2. Language filter
      if (langFilter !== "all") {
        const avail = Array.isArray(ep.available_audio_languages)
          ? ep.available_audio_languages.map(l => l.toLowerCase())
          : [];
        const primaryLang = (ep.audio_language || "").toLowerCase();
        if (!avail.includes(langFilter) && primaryLang !== langFilter) {
          return false;
        }
      }

      // 3. Readiness Status filter
      if (statusFilter !== "all") {
        if (statusFilter === "audio_ready" && !ep.audio_ready) return false;
        if (statusFilter === "ai_ready" && !ep.ai_ready) return false;
        if (statusFilter === "script_ready" && !ep.script_ready) return false;
      }

      return true;
    });

    if (btnClearSearchText) {
      btnClearSearchText.style.display = query ? "inline-flex" : "none";
    }

    if (episodesFilterSummary && episodesFilterCountText) {
      if (isFilteringActive) {
        episodesFilterSummary.style.display = "flex";
        episodesFilterCountText.textContent = `Showing ${filtered.length} of ${allLoadedEpisodes.length} saved episode${allLoadedEpisodes.length === 1 ? '' : 's'}${query ? ` matching "${escapeHtml(query)}"` : ''}`;
      } else {
        episodesFilterSummary.style.display = "none";
      }
    }

    if (filtered.length === 0 && allLoadedEpisodes.length > 0) {
      if (!episodesListContainer) return;
      episodesListContainer.innerHTML = `
        <div class="episodes-empty-state" id="episodes-no-results">
          <div class="empty-icon">🔍</div>
          <p class="empty-msg">No episodes found matching your filter criteria.</p>
          <span class="empty-hint">Try adjusting your search terms or clearing active filters to view all saved episodes.</span>
          <div style="margin-top: 0.85rem;">
            <button type="button" class="btn btn-secondary btn-sm" id="btn-empty-clear-filters">Clear All Filters</button>
          </div>
        </div>
      `;
      const btnEmptyClear = document.getElementById("btn-empty-clear-filters");
      if (btnEmptyClear) {
        btnEmptyClear.addEventListener("click", clearEpisodesFilters);
      }
      return;
    }

    renderEpisodesList(filtered);
  }

  function clearEpisodesFilters() {
    currentEpisodesSearchTerm = "";
    currentEpisodesLanguageFilter = "all";
    currentEpisodesStatusFilter = "all";

    if (episodesSearchInput) episodesSearchInput.value = "";
    if (episodesFilterLanguage) episodesFilterLanguage.value = "all";
    if (episodesFilterStatus) episodesFilterStatus.value = "all";

    filterAndRenderEpisodes();
  }

  async function fetchEpisodes() {
    try {
      const response = await fetch(`${API_BASE}/api/episodes`, {
        headers: { "Accept": "application/json" }
      });
      const data = await response.json();

      if (response.ok && data.success) {
        allLoadedEpisodes = data.episodes || [];
        filterAndRenderEpisodes();

        // Auto-select initial episode into unified studio on first load
        if (!currentStudioEpisode && allLoadedEpisodes.length > 0) {
          const epWithAudio = allLoadedEpisodes.find(e => e.audio_ready === true || (Array.isArray(e.available_audio_languages) && e.available_audio_languages.length > 0));
          const initialEp = epWithAudio || allLoadedEpisodes[0];
          selectEpisodeInStudio(initialEp, false, true);
        } else if (currentStudioEpisode) {
          const fresh = allLoadedEpisodes.find(e => e.id === currentStudioEpisode.id);
          if (fresh) {
            currentStudioEpisode = fresh;
            currentPlayingEpisode = fresh;
          }
        }
      }
    } catch (err) {
      console.warn("Could not fetch episodes list:", err);
    }
  }

  function formatAiBadge(ep) {
    if (ep.ai_ready || (ep.ai_status === "completed" && ep.intelligence)) {
      return `<span class="ai-status-pill completed">AI Insights Ready</span>`;
    }
    if (ep.ai_status === "processing") {
      return `<span class="ai-status-pill processing">AI Analyzing...</span>`;
    }
    if (ep.ai_status === "failed") {
      return `<span class="ai-status-pill failed">AI Insights Failed</span>`;
    }
    return `<span class="ai-status-pill pending">AI Not Started</span>`;
  }

  function formatScriptBadge(ep) {
    if (ep.script_ready || (ep.script_status === "completed" && ep.podcast_script)) {
      return `<span class="script-status-pill completed">Script Ready</span>`;
    }
    if (ep.script_status === "processing") {
      return `<span class="script-status-pill processing">Script Drafting...</span>`;
    }
    if (ep.script_status === "failed") {
      return `<span class="script-status-pill failed">Script Failed</span>`;
    }
    return `<span class="script-status-pill pending">Script Not Started</span>`;
  }

  function formatAudioBadge(ep) {
    const rawLangs = Array.isArray(ep.available_audio_languages) ? ep.available_audio_languages : [];
    const langs = rawLangs.map(l => {
      const lower = l.toLowerCase();
      if (lower === "hinglish") return "Hinglish";
      if (lower === "hindi") return "HI";
      if (lower === "english") return "EN";
      return l.toUpperCase().slice(0, 3);
    });

    if (ep.audio_ready || langs.length > 0) {
      const langStr = langs.length > 0 ? ` (${langs.join(', ')})` : "";
      return `<span class="audio-status-pill completed">Audio Ready${langStr}</span>`;
    }
    if (ep.audio_status === "processing") {
      return `<span class="audio-status-pill processing">Audio Generating...</span>`;
    }
    if (ep.audio_status === "failed") {
      return `<span class="audio-status-pill failed">Audio Failed</span>`;
    }
    return `<span class="audio-status-pill pending">Audio Not Started</span>`;
  }

  function renderEpisodesList(episodes) {
    if (!episodesListContainer) return;
    episodesListContainer.innerHTML = "";

    if (!episodes || episodes.length === 0) {
      if (episodesEmptyState) {
        episodesListContainer.appendChild(episodesEmptyState);
        episodesEmptyState.hidden = false;
      } else {
        episodesListContainer.innerHTML = `<div class="episodes-empty-state"><p class="empty-msg">No podcast episodes created yet.</p></div>`;
      }
      return;
    }

    episodes.forEach(ep => {
      const isThisEpActive = currentPlayingEpisode && currentPlayingEpisode.id === ep.id;
      const isAudioCurrentlyPlaying = isThisEpActive && htmlPodcastAudio && !htmlPodcastAudio.paused;

      const card = document.createElement("div");
      card.className = `episode-item-card ${isThisEpActive ? "now-playing" : ""}`;
      card.dataset.id = ep.id;

      const title = escapeHtml(ep.title || "Untitled Episode");
      const desc = ep.description ? escapeHtml(ep.description) : "";
      const status = escapeHtml(ep.status || "draft");
      const sourcesCount = ep.sources ? ep.sources.length : 0;
      
      let dateFormatted = "";
      if (ep.created_at) {
        try {
          const d = new Date(ep.created_at);
          dateFormatted = d.toLocaleString(undefined, {
            month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
          });
        } catch {
          dateFormatted = ep.created_at;
        }
      }

      // Check genuine audio availability on disk
      const hasAudio = ep.audio_ready === true || (Array.isArray(ep.available_audio_languages) && ep.available_audio_languages.length > 0);
      const listenBtn = hasAudio ? `
        <button type="button" class="btn-play-ep ${isAudioCurrentlyPlaying ? 'btn-playing' : ''}" data-id="${ep.id}" title="${isAudioCurrentlyPlaying ? 'Pause audio playback' : 'Listen to generated podcast audio'}">
          <span>${isAudioCurrentlyPlaying ? '⏸' : '▶'}</span> ${isAudioCurrentlyPlaying ? 'Pause' : 'Listen'}
        </button>
      ` : "";

      const studioBtn = `
        <button type="button" class="btn-studio" data-id="${ep.id}" title="Open Multi-Speaker Podcast Studio & Audio">
          <span>🎙️</span> Audio Studio
        </button>
      `;

      // Action buttons depending on AI state
      let aiActionBtns = "";
      if (ep.intelligence && (ep.ai_ready || ep.ai_status === "completed")) {
        aiActionBtns = `
          <button type="button" class="btn-view-ai" data-id="${ep.id}" title="View generated AI insights">
            <span>✨</span> Insights
          </button>
          <button type="button" class="btn-generate-ai" data-id="${ep.id}" title="Re-generate intelligence with Gemini">
            <span>🔄</span> Regen AI
          </button>
        `;
      } else if (ep.ai_status === "processing") {
        aiActionBtns = `
          <button type="button" class="btn-generate-ai" data-id="${ep.id}" disabled title="AI intelligence is currently generating">
            <span class="inline-spinner">⏳</span> Analyzing...
          </button>
        `;
      } else if (ep.ai_status === "failed") {
        aiActionBtns = `
          <button type="button" class="btn-generate-ai" data-id="${ep.id}" title="Retry generating intelligence with Gemini">
            <span>⚠️</span> Retry AI
          </button>
        `;
      } else {
        aiActionBtns = `
          <button type="button" class="btn-generate-ai" data-id="${ep.id}" title="Generate source-grounded insights with Gemini">
            <span>✨</span> AI Insights
          </button>
        `;
      }

      // Action button for failed scripts (EP #6)
      let scriptActionBtn = "";
      if (ep.script_status === "failed") {
        scriptActionBtn = `
          <button type="button" class="btn-retry-script" data-id="${ep.id}" title="Retry drafting podcast script">
            <span>🔄</span> Retry Script
          </button>
        `;
      }

      let langTracksHtml = "";
      if (Array.isArray(ep.available_audio_languages) && ep.available_audio_languages.length > 0) {
        langTracksHtml = `
          <div class="ep-lang-chips-container" title="Click to load and play audio in specific language">
            <span class="ep-lang-label" style="font-size:0.72rem; color:var(--text-faint); font-weight:600;">Available Tracks:</span>
            ${ep.available_audio_languages.map(l => {
              const flag = l === 'odia' ? '🇮🇳' : l === 'hindi' ? '🇮🇳' : l === 'hinglish' ? '🇮🇳' : '🇬🇧';
              const isCurrentActiveTrack = isThisEpActive && audioLanguageSelect && audioLanguageSelect.value.toLowerCase() === l.toLowerCase();
              return `<button type="button" class="ep-lang-chip ${isCurrentActiveTrack ? 'active-lang' : ''}" data-id="${ep.id}" data-lang="${l}">${flag} ${l.toUpperCase()}</button>`;
            }).join("")}
          </div>
        `;
      }

      const durationFormatted = ep.audio_duration_formatted || (ep.audio_duration_seconds ? formatSeconds(ep.audio_duration_seconds) : null);

      card.innerHTML = `
        <div class="episode-item-main">
          <div class="episode-item-meta">
            <span class="episode-status-badge ${status}">${status}</span>
            ${formatAiBadge(ep)}
            ${formatScriptBadge(ep)}
            ${formatAudioBadge(ep)}
            ${durationFormatted ? `<span class="episode-duration-pill" title="Audio Track Duration">⏱️ ${durationFormatted}</span>` : ""}
            <span class="episode-sources-count">${sourcesCount} source${sourcesCount === 1 ? '' : 's'}</span>
            ${dateFormatted ? `<span class="episode-item-date">${dateFormatted}</span>` : ""}
            ${isThisEpActive ? `<span class="now-playing-pill"><span class="playing-pulse"></span> Selected in Studio</span>` : ""}
          </div>
          <h4 class="episode-item-title">${title}</h4>
          ${desc ? `<p class="episode-item-desc">${desc}</p>` : ""}
          ${langTracksHtml}
        </div>
        <div class="episode-item-actions">
          ${listenBtn}
          ${studioBtn}
          ${aiActionBtns}
          ${scriptActionBtn}
          <button type="button" class="btn-delete-ep" data-id="${ep.id}" title="Delete episode">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            Delete
          </button>
        </div>
      `;

      // Wire quick-listen language chips
      card.querySelectorAll(".ep-lang-chip").forEach(chip => {
        chip.addEventListener("click", (e) => {
          e.stopPropagation();
          const targetLang = chip.getAttribute("data-lang");
          if (audioLanguageSelect) {
            audioLanguageSelect.value = targetLang;
          }
          selectEpisodeInStudio(ep, true);
        });
      });

      // Wire Listen / Play Episode button
      const playEpBtn = card.querySelector(".btn-play-ep");
      if (playEpBtn) {
        playEpBtn.addEventListener("click", () => {
          if (currentPlayingEpisode && currentPlayingEpisode.id === ep.id && htmlPodcastAudio && htmlPodcastAudio.src) {
            if (htmlPodcastAudio.paused) {
              htmlPodcastAudio.play().catch(e => console.warn(e));
            } else {
              htmlPodcastAudio.pause();
            }
          } else {
            selectEpisodeInStudio(ep, true);
          }
        });
      }

      // Wire Audio Studio button
      const studioBtnEl = card.querySelector(".btn-studio");
      if (studioBtnEl) {
        studioBtnEl.addEventListener("click", () => {
          selectEpisodeInStudio(ep, false);
        });
      }

      // Wire Retry Script button
      const retryScriptBtnEl = card.querySelector(".btn-retry-script");
      if (retryScriptBtnEl) {
        retryScriptBtnEl.addEventListener("click", async () => {
          await selectEpisodeInStudio(ep, false);
          generatePodcastScriptAction();
        });
      }

      // Wire Generate AI button
      const genBtn = card.querySelector(".btn-generate-ai");
      if (genBtn && !genBtn.disabled) {
        genBtn.addEventListener("click", () => {
          generateEpisodeIntelligence(ep.id, ep.title || "Episode #" + ep.id, genBtn);
        });
      }

      // Wire View AI button
      const viewBtn = card.querySelector(".btn-view-ai");
      if (viewBtn) {
        viewBtn.addEventListener("click", () => {
          if (ep.intelligence) {
            renderAIIntelligence(ep.id, ep.intelligence, ep.title || "Episode #" + ep.id);
          } else {
            viewEpisodeIntelligence(ep.id);
          }
        });
      }

      // Wire delete button
      const deleteBtn = card.querySelector(".btn-delete-ep");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", () => {
          deleteEpisodeById(ep.id, title);
        });
      }

      episodesListContainer.appendChild(card);
    });
  }

  async function generateEpisodeIntelligence(episodeId, epTitle, buttonEl) {
    const originalText = buttonEl ? buttonEl.innerHTML : "";
    if (buttonEl) {
      buttonEl.disabled = true;
      buttonEl.innerHTML = `<span>⏳</span> Generating AI Insights...`;
    }

    showInfoBanner("Gemini Intelligence", `Analyzing sources for "${epTitle}" using Gemini AI...`);

    try {
      const response = await fetch(`${API_BASE}/api/episodes/${episodeId}/generate-intelligence`, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json"
        }
      });

      const data = await response.json();

      if (response.ok && data.success && data.intelligence) {
        showInfoBanner("Intelligence Generated", `Successfully synthesized structured intelligence for "${epTitle}".`);
        renderAIIntelligence(data.episode_id, data.intelligence, epTitle);
        fetchEpisodes();
      } else {
        const errorMsg = data.error || "Unable to generate AI intelligence.";
        showInfoBanner("AI Generation Error", errorMsg);
        fetchEpisodes();
      }
    } catch (err) {
      showInfoBanner("AI Generation Error", "Network or server error while calling intelligence engine.");
      fetchEpisodes();
    } finally {
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.innerHTML = originalText;
      }
    }
  }

  async function viewEpisodeIntelligence(episodeId) {
    try {
      const response = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        headers: { "Accept": "application/json" }
      });
      const data = await response.json();

      if (response.ok && data.success && data.episode && data.episode.intelligence) {
        renderAIIntelligence(data.episode.id, data.episode.intelligence, data.episode.title);
      } else {
        showInfoBanner("AI Insights", "No AI intelligence found for this episode yet. Click 'Generate AI Insights' to create it.");
      }
    } catch (err) {
      showInfoBanner("Error", "Could not fetch episode intelligence details.");
    }
  }

  function renderAIIntelligence(episodeId, intelligence, episodeTitle) {
    if (!aiIntelligenceViewer) return;

    // Header info
    if (aiViewerTitle) {
      aiViewerTitle.textContent = `Insights: ${episodeTitle || 'Episode #' + episodeId}`;
    }
    if (aiViewerMeta) {
      aiViewerMeta.textContent = `Episode #${episodeId} • Grounded exclusively in supplied news sources`;
    }

    // 1. Overview
    if (aiOverviewText) {
      aiOverviewText.textContent = intelligence.overview || "No overview available.";
    }

    // 2. Key Takeaways
    if (aiKeyPointsList) {
      aiKeyPointsList.innerHTML = "";
      const points = Array.isArray(intelligence.key_points) ? intelligence.key_points : [];
      if (points.length === 0) {
        aiKeyPointsList.innerHTML = "<li>None provided.</li>";
      } else {
        points.forEach(pt => {
          const li = document.createElement("li");
          li.textContent = pt;
          aiKeyPointsList.appendChild(li);
        });
      }
    }

    // 3. Important Facts
    if (aiFactsList) {
      aiFactsList.innerHTML = "";
      const facts = Array.isArray(intelligence.important_facts) ? intelligence.important_facts : [];
      if (facts.length === 0) {
        aiFactsList.innerHTML = "<li>None provided.</li>";
      } else {
        facts.forEach(f => {
          const li = document.createElement("li");
          li.textContent = f;
          aiFactsList.appendChild(li);
        });
      }
    }

    // 4. Topics Chips
    if (aiTopicsChips) {
      aiTopicsChips.innerHTML = "";
      const topics = Array.isArray(intelligence.topics) ? intelligence.topics : [];
      if (topics.length === 0) {
        aiTopicsChips.innerHTML = "<span class=\"ai-chip\">General News</span>";
      } else {
        topics.forEach(t => {
          const chip = document.createElement("span");
          chip.className = "ai-chip";
          chip.textContent = t;
          aiTopicsChips.appendChild(chip);
        });
      }
    }

    // 5. Entities Chips
    if (aiEntitiesChips) {
      aiEntitiesChips.innerHTML = "";
      const entities = Array.isArray(intelligence.entities) ? intelligence.entities : [];
      if (entities.length === 0) {
        aiEntitiesChips.innerHTML = "<span class=\"ai-chip\">No specific entities extracted</span>";
      } else {
        entities.forEach(ent => {
          const chip = document.createElement("span");
          chip.className = "ai-entity-chip";
          const entName = typeof ent === "string" ? ent : (ent.name || "Entity");
          const entType = typeof ent === "object" && ent.type ? ent.type : "";
          const entContext = typeof ent === "object" && ent.context ? ent.context : "";

          chip.innerHTML = `
            <span>${escapeHtml(entName)}</span>
            ${entType ? `<span class="ai-entity-type-badge">${escapeHtml(entType)}</span>` : ""}
          `;
          if (entContext) {
            chip.title = entContext;
          }
          aiEntitiesChips.appendChild(chip);
        });
      }
    }

    // 6. Source Insights Cards
    if (aiSourcesInsightsContainer) {
      aiSourcesInsightsContainer.innerHTML = "";
      const sourceInsights = Array.isArray(intelligence.source_insights) ? intelligence.source_insights : [];
      if (sourceInsights.length === 0) {
        aiSourcesInsightsContainer.innerHTML = "<p class=\"ai-source-card-summary\">No source-specific insights breakdown provided.</p>";
      } else {
        sourceInsights.forEach(si => {
          const card = document.createElement("div");
          card.className = "ai-source-card";

          const sourceId = si.source_id ? escapeHtml(String(si.source_id)) : "Source";
          const summary = si.summary ? escapeHtml(si.summary) : "";
          const claims = Array.isArray(si.key_claims) ? si.key_claims : [];

          let claimsHtml = "";
          if (claims.length > 0) {
            claimsHtml = `
              <div class="ai-source-claims-title">Key Claims:</div>
              <ul class="ai-source-claims-list">
                ${claims.map(c => `<li>${escapeHtml(c)}</li>`).join("")}
              </ul>
            `;
          }

          card.innerHTML = `
            <div class="ai-source-card-header">
              <span class="ai-source-card-id">${sourceId}</span>
            </div>
            ${summary ? `<p class="ai-source-card-summary">${summary}</p>` : ""}
            ${claimsHtml}
          `;
          aiSourcesInsightsContainer.appendChild(card);
        });
      }
    }

    // 7. Confidence Badge
    if (aiConfidencePill) {
      const conf = (intelligence.confidence || "medium").toLowerCase();
      aiConfidencePill.className = `ai-conf-badge ${conf}`;
      aiConfidencePill.textContent = conf.toUpperCase();
    }

    // 8. Limitations & Grounding
    if (aiLimitationsList) {
      aiLimitationsList.innerHTML = "";
      const limits = Array.isArray(intelligence.limitations) ? intelligence.limitations : [];
      if (limits.length === 0) {
        aiLimitationsList.innerHTML = "<li>Grounded strictly in supplied article metadata and snippets.</li>";
      } else {
        limits.forEach(lim => {
          const li = document.createElement("li");
          li.textContent = lim;
          aiLimitationsList.appendChild(li);
        });
      }
    }

    // Reveal viewer and smoothly scroll
    aiIntelligenceViewer.hidden = false;
    aiIntelligenceViewer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function deleteEpisodeById(id, title) {
    if (!confirm(`Are you sure you want to delete episode #${id} "${title}"?`)) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/episodes/${id}`, {
        method: "DELETE",
        headers: { "Accept": "application/json" }
      });
      const data = await response.json();

      if (response.ok && data.success) {
        showInfoBanner("Episode Deleted", `Episode #${id} deleted successfully.`);
        if (aiIntelligenceViewer && !aiIntelligenceViewer.hidden) {
          aiIntelligenceViewer.hidden = true;
        }
        fetchEpisodes();
      } else {
        showInfoBanner("Delete Failed", data.error || "Unable to delete episode.");
      }
    } catch (err) {
      showInfoBanner("Error", "Network error while deleting episode.");
    }
  }

  // Wire AI Viewer Close Button
  if (btnCloseAiViewer) {
    btnCloseAiViewer.addEventListener("click", () => {
      if (aiIntelligenceViewer) {
        aiIntelligenceViewer.hidden = true;
      }
    });
  }

  // Wire Episode Creation Event Listeners
  if (btnCreatePodcast) {
    btnCreatePodcast.addEventListener("click", openCreationPanel);
  }

  if (btnCloseCreationPanel) {
    btnCloseCreationPanel.addEventListener("click", closeCreationPanel);
  }

  if (btnCancelEpisode) {
    btnCancelEpisode.addEventListener("click", closeCreationPanel);
  }

  if (btnSubmitEpisode) {
    btnSubmitEpisode.addEventListener("click", submitEpisodeCreation);
  }

  if (btnRefreshEpisodes) {
    btnRefreshEpisodes.addEventListener("click", fetchEpisodes);
  }

  // Saved Episodes Search & Filter Input Listeners (Phase 2 Enhancement)
  if (episodesSearchInput) {
    episodesSearchInput.addEventListener("input", (e) => {
      currentEpisodesSearchTerm = e.target.value;
      filterAndRenderEpisodes();
    });
  }

  if (btnClearSearchText) {
    btnClearSearchText.addEventListener("click", () => {
      currentEpisodesSearchTerm = "";
      if (episodesSearchInput) {
        episodesSearchInput.value = "";
        episodesSearchInput.focus();
      }
      filterAndRenderEpisodes();
    });
  }

  if (episodesFilterLanguage) {
    episodesFilterLanguage.addEventListener("change", (e) => {
      currentEpisodesLanguageFilter = e.target.value;
      filterAndRenderEpisodes();
    });
  }

  if (episodesFilterStatus) {
    episodesFilterStatus.addEventListener("change", (e) => {
      currentEpisodesStatusFilter = e.target.value;
      filterAndRenderEpisodes();
    });
  }

  if (btnClearFilters) {
    btnClearFilters.addEventListener("click", clearEpisodesFilters);
  }

  // =========================================================================
  // Phase 7: Unified Multi-Language Podcast Audio Studio & Script Logic
  // =========================================================================
  async function selectEpisodeInStudio(ep, autoPlay = false, isSilent = false) {
    if (!ep) return;

    // Fetch fresh episode details from server to ensure accurate tracks and statuses
    try {
      const response = await fetch(`${API_BASE}/api/episodes/${ep.id}`, {
        headers: { "Accept": "application/json" }
      });
      const data = await response.json();
      if (response.ok && data.success && data.episode) {
        ep = data.episode;
      }
    } catch (e) {
      console.warn("Could not fetch fresh episode details:", e);
    }

    currentStudioEpisode = ep;
    currentPlayingEpisode = ep;

    if (podcastStudioViewer) {
      podcastStudioViewer.hidden = false;
    }
    if (aiIntelligenceViewer && !aiIntelligenceViewer.hidden) {
      aiIntelligenceViewer.hidden = true;
    }

    // 1. Synchronize Headings and Metadata
    const titleText = ep.title || ("Episode #" + ep.id);
    const srcCount = ep.sources ? ep.sources.length : 0;
    if (studioViewerTitle) studioViewerTitle.textContent = titleText;
    if (playerHeading) playerHeading.textContent = titleText;
    if (studioViewerMeta) {
      studioViewerMeta.textContent = `Episode #${ep.id} • ${srcCount} news source${srcCount === 1 ? '' : 's'}`;
    }
    if (mainPlayerNote) {
      mainPlayerNote.textContent = `Episode #${ep.id}: "${titleText}" • Dual-speaker synthesis powered by Gemini & TTS.`;
    }

    // 2. Synchronize library cards visual highlight
    document.querySelectorAll(".episode-item-card").forEach(c => {
      const cardEpId = parseInt(c.dataset.id, 10);
      if (cardEpId === ep.id) {
        c.classList.add("now-playing");
      } else {
        c.classList.remove("now-playing");
        const otherBtn = c.querySelector(".btn-play-ep");
        if (otherBtn) {
          otherBtn.innerHTML = `<span>▶</span> Listen`;
          otherBtn.classList.remove("btn-playing");
        }
      }
    });

    // 3. Synchronize Language & Audio Tracks
    const availableTracks = Array.isArray(ep.available_audio_languages)
      ? ep.available_audio_languages.map(l => l.toLowerCase())
      : [];

    let targetLang = (audioLanguageSelect ? audioLanguageSelect.value.toLowerCase() : "") || (ep.audio_language || "english").toLowerCase();
    if (!availableTracks.includes(targetLang) && availableTracks.length > 0) {
      targetLang = availableTracks[0];
    }
    if (audioLanguageSelect) {
      audioLanguageSelect.value = targetLang;
    }
    updateStudioLangPills(ep, targetLang);

    if (availableTracks.includes(targetLang)) {
      const audioUrl = `${API_BASE}/api/episodes/${ep.id}/audio?lang=${encodeURIComponent(targetLang)}&t=${Date.now()}`;
      if (htmlPodcastAudio) {
        htmlPodcastAudio.src = audioUrl;
        htmlPodcastAudio.load();
        if (currentPlaybackSpeed) {
          htmlPodcastAudio.playbackRate = currentPlaybackSpeed;
        }
      }
      if (mainPlayBtn) {
        mainPlayBtn.disabled = false;
        mainPlayBtn.title = "Play episode audio";
      }
      if (mainRewindBtn) mainRewindBtn.disabled = false;
      if (mainForwardBtn) mainForwardBtn.disabled = false;
      if (studioActiveTrackPill) {
        studioActiveTrackPill.textContent = `Track: ${targetLang.toUpperCase()} (Ready)`;
        studioActiveTrackPill.className = "studio-track-pill ready";
      }
      if (playerSubheading) {
        playerSubheading.textContent = `Episode #${ep.id} • ${targetLang.toUpperCase()} • ${srcCount} news source${srcCount === 1 ? '' : 's'}`;
      }
      if (playerPhaseBadge) playerPhaseBadge.textContent = autoPlay ? "Buffering..." : "Audio Ready";
      if (btnDownloadAudio) btnDownloadAudio.disabled = false;
      showAudioStatusBanner(
        "success",
        `Audio Ready (${targetLang.toUpperCase()})`,
        `Dual-speaker audio track in ${targetLang.toUpperCase()} is loaded and ready for playback.`
      );
      if (autoPlay && htmlPodcastAudio) {
        htmlPodcastAudio.play().catch(e => console.warn("Autoplay notice:", e));
      }
    } else {
      if (htmlPodcastAudio) {
        htmlPodcastAudio.pause();
        htmlPodcastAudio.removeAttribute("src");
        htmlPodcastAudio.load();
      }
      setMainPlayerState(false);
      if (mainPlayBtn) mainPlayBtn.disabled = true;
      if (mainRewindBtn) mainRewindBtn.disabled = true;
      if (mainForwardBtn) mainForwardBtn.disabled = true;
      if (btnDownloadAudio) btnDownloadAudio.disabled = true;
      if (studioActiveTrackPill) {
        studioActiveTrackPill.textContent = `Track: ${targetLang.toUpperCase()} (Not Generated)`;
        studioActiveTrackPill.className = "studio-track-pill pending";
      }
      if (playerSubheading) {
        playerSubheading.textContent = `Episode #${ep.id} • ${targetLang.toUpperCase()} • Audio Not Yet Generated`;
      }
      if (playerPhaseBadge) playerPhaseBadge.textContent = "Audio Not Generated";
      showAudioStatusBanner(
        "info",
        `${targetLang.toUpperCase()} Audio Not Yet Generated`,
        `Click "Generate Podcast Audio" below to synthesize Host & CoHost dialogue in ${targetLang.toUpperCase()}.`
      );
    }

    // 4. Synchronize Dialogue Script
    const hasValidScript = Boolean(ep.podcast_script && (ep.script_ready || ep.script_status === "completed"));
    if (hasValidScript) {
      renderScriptDialogue(ep.podcast_script);
      if (btnCopyScript) btnCopyScript.disabled = false;
      if (btnGenerateAudio) {
        btnGenerateAudio.disabled = false;
        btnGenerateAudio.title = "Generate multi-speaker podcast audio";
      }
      if (btnGenerateScriptText) {
        btnGenerateScriptText.textContent = "Regenerate Script";
      }
    } else {
      if (btnCopyScript) btnCopyScript.disabled = true;
      if (scriptDialogueContainer) {
        if (ep.script_status === "failed") {
          scriptDialogueContainer.innerHTML = `
            <div class="episodes-empty-state">
              <p class="empty-msg" style="color: var(--color-danger, #ef4444);">Script generation failed for this episode.</p>
              <span class="empty-hint">Click "Retry Script" below to re-draft Host &amp; CoHost dialogue using Gemini AI.</span>
            </div>
          `;
        } else {
          scriptDialogueContainer.innerHTML = `
            <div class="episodes-empty-state">
              <p class="empty-msg">No podcast script generated yet.</p>
              <span class="empty-hint">Click "Generate Script" below to draft Host &amp; CoHost dialogue from AI intelligence.</span>
            </div>
          `;
        }
      }
      if (btnGenerateAudio) {
        btnGenerateAudio.disabled = true;
        btnGenerateAudio.title = "Generate a podcast script first before generating audio.";
      }
      if (btnGenerateScriptText) {
        btnGenerateScriptText.textContent = ep.script_status === "failed" ? "Retry Script" : "Generate Script";
      }
    }

    // 5. Smooth scroll unless initial page load
    if (!isSilent) {
      const previewSection = document.getElementById("podcast-preview");
      if (previewSection) {
        previewSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }

  // Backward compatible helpers to ensure no legacy callbacks break
  function openPodcastStudio(ep) {
    selectEpisodeInStudio(ep, false);
  }

  function loadEpisodeIntoMainPlayer(ep, autoPlay = false) {
    selectEpisodeInStudio(ep, autoPlay);
  }

  function renderScriptDialogue(script) {
    if (!scriptDialogueContainer) return;
    scriptDialogueContainer.innerHTML = "";

    function appendHeader(text) {
      const header = document.createElement("div");
      header.className = "dialogue-section-header";
      header.textContent = text;
      scriptDialogueContainer.appendChild(header);
    }

    function appendLine(speaker, text) {
      const bubble = document.createElement("div");
      const spk = (speaker || "host").toLowerCase() === "cohost" ? "cohost" : "host";
      bubble.className = `dialogue-turn ${spk}`;

      const tag = document.createElement("div");
      tag.className = "dialogue-speaker-tag";
      tag.textContent = spk === "cohost" ? "CoHost" : "Host";

      const body = document.createElement("div");
      body.className = "dialogue-turn-text";
      body.textContent = text;

      bubble.appendChild(tag);
      bubble.appendChild(body);
      scriptDialogueContainer.appendChild(bubble);
    }

    // 1. Intro
    if (script.intro && Array.isArray(script.intro.lines)) {
      appendHeader("— Introduction —");
      script.intro.lines.forEach(l => appendLine(l.speaker, l.text));
    }

    // 2. Segments
    if (Array.isArray(script.segments)) {
      script.segments.forEach((seg, sIdx) => {
        appendHeader(`— Segment ${sIdx + 1}: ${seg.title || 'Story'} —`);
        if (Array.isArray(seg.lines)) {
          seg.lines.forEach(l => appendLine(l.speaker, l.text));
        }
      });
    }

    // 3. Key Takeaways
    if (Array.isArray(script.key_takeaways)) {
      appendHeader("— Key Takeaways —");
      script.key_takeaways.forEach(l => appendLine(l.speaker, l.text));
    }

    // 4. Outro
    if (script.outro && Array.isArray(script.outro.lines)) {
      appendHeader("— Outro —");
      script.outro.lines.forEach(l => appendLine(l.speaker, l.text));
    }
  }

  function showAudioStatusBanner(type, title, msg) {
    if (!audioStatusBanner) return;
    audioStatusBanner.className = `audio-status-banner ${type}`;
    if (audioStatusIcon) {
      audioStatusIcon.textContent = type === "error" ? "⚠️" : type === "success" ? "✅" : "ℹ️";
    }
    if (audioStatusTitle) {
      audioStatusTitle.textContent = title;
    }
    if (audioStatusMsg) {
      audioStatusMsg.textContent = msg;
    }
    audioStatusBanner.hidden = false;
  }

  async function generatePodcastAudioAction() {
    if (!currentStudioEpisode) {
      showInfoBanner("Audio Generation", "Please select an episode first.");
      return;
    }

    const lang = audioLanguageSelect ? audioLanguageSelect.value.toLowerCase() : "english";
    const episodeId = currentStudioEpisode.id;

    if (btnGenerateAudio) {
      btnGenerateAudio.disabled = true;
    }
    if (btnGenerateAudioText) {
      btnGenerateAudioText.textContent = "Synthesizing Audio...";
    }

    // Pause player and reset src during synthesis so stale playback is prevented
    if (htmlPodcastAudio) {
      htmlPodcastAudio.pause();
      htmlPodcastAudio.removeAttribute("src");
      htmlPodcastAudio.load();
    }
    setMainPlayerState(false);
    if (playerPhaseBadge) playerPhaseBadge.textContent = "Generating...";

    showAudioStatusBanner("info", "Generating Podcast Audio...", `Synthesizing Host & CoHost dialogue in ${lang.toUpperCase()}. Merging audio tracks...`);

    try {
      const response = await fetch(`${API_BASE}/api/episodes/${episodeId}/generate-audio`, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ language: lang })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        showAudioStatusBanner("success", "Podcast Audio Ready!", `Generated audio in ${data.audio_language.toUpperCase()}. Player ready below.`);
        
        currentStudioEpisode.audio_status = "completed";
        currentStudioEpisode.audio_language = data.audio_language;
        currentStudioEpisode.audio_path = data.audio_path;
        currentStudioEpisode.audio_generated_at = data.audio_generated_at;

        if (!Array.isArray(currentStudioEpisode.available_audio_languages)) {
          currentStudioEpisode.available_audio_languages = [];
        }
        if (!currentStudioEpisode.available_audio_languages.includes(data.audio_language)) {
          currentStudioEpisode.available_audio_languages.push(data.audio_language);
        }

        // Re-synchronize studio with freshly generated audio
        selectEpisodeInStudio(currentStudioEpisode, false, false);
        fetchEpisodes();
      } else {
        const errorMsg = data.error || "Failed to generate podcast audio.";
        showAudioStatusBanner("error", "Audio Generation Failed", errorMsg);
        if (playerPhaseBadge) playerPhaseBadge.textContent = "Audio Failed";
        fetchEpisodes();
      }
    } catch (err) {
      showAudioStatusBanner("error", "Audio Generation Error", "Network error communicating with audio generation service.");
      if (playerPhaseBadge) playerPhaseBadge.textContent = "Audio Error";
      fetchEpisodes();
    } finally {
      if (btnGenerateAudio) {
        btnGenerateAudio.disabled = false;
      }
      if (btnGenerateAudioText) {
        btnGenerateAudioText.textContent = "Generate Podcast Audio";
      }
    }
  }

  async function generatePodcastScriptAction() {
    if (!currentStudioEpisode) return;

    const episodeId = currentStudioEpisode.id;
    const lang = audioLanguageSelect ? audioLanguageSelect.value.toLowerCase() : "english";

    if (btnGenerateScriptInStudio) {
      btnGenerateScriptInStudio.disabled = true;
    }
    if (btnGenerateScriptText) {
      btnGenerateScriptText.textContent = "Generating Script...";
    }

    showAudioStatusBanner("info", "Generating Podcast Script...", `Drafting grounded two-speaker dialogue turns in ${lang.toUpperCase()} using Gemini AI...`);

    try {
      const response = await fetch(`${API_BASE}/api/episodes/${episodeId}/generate-script`, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ length: "standard", language: lang })
      });

      const data = await response.json();

      if (response.ok && data.success && data.podcast_script) {
        currentStudioEpisode.podcast_script = data.podcast_script;
        currentStudioEpisode.script_status = "completed";
        currentStudioEpisode.script_ready = true;

        renderScriptDialogue(data.podcast_script);
        showAudioStatusBanner("success", "Script Generated!", `Two-speaker script in ${lang.toUpperCase()} is ready. You can now synthesize podcast audio.`);

        if (btnGenerateAudio) {
          btnGenerateAudio.disabled = false;
          btnGenerateAudio.title = "Generate multi-speaker podcast audio";
        }
        fetchEpisodes();
      } else {
        const errorMsg = data.error || "Failed to generate podcast script.";
        showAudioStatusBanner("error", "Script Generation Failed", errorMsg);
      }
    } catch (err) {
      showAudioStatusBanner("error", "Script Error", "Network error communicating with script generation service.");
    } finally {
      if (btnGenerateScriptInStudio) {
        btnGenerateScriptInStudio.disabled = false;
      }
      if (btnGenerateScriptText) {
        btnGenerateScriptText.textContent = currentStudioEpisode.podcast_script ? "Regenerate Script" : "Generate Script";
      }
    }
  }

  // Download Active Track as MP3
  function downloadActiveTrackAction() {
    if (!currentStudioEpisode) {
      showInfoBanner("Select Episode", "Please select an episode from Saved Episodes first.");
      return;
    }

    const lang = (audioLanguageSelect ? audioLanguageSelect.value : "english").toLowerCase();
    const availableLangs = Array.isArray(currentStudioEpisode.available_audio_languages)
      ? currentStudioEpisode.available_audio_languages.map(l => l.toLowerCase())
      : [];

    if (!availableLangs.includes(lang)) {
      showInfoBanner(
        "Audio Required",
        `No audio file is available to download for the ${lang.toUpperCase()} track. Please generate audio first.`
      );
      return;
    }

    const safeTitle = (currentStudioEpisode.title || "podcast")
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, "_")
      .slice(0, 30);
    const dlFilename = `podcast_buddy_ep${currentStudioEpisode.id}_${lang}_${safeTitle}.mp3`;
    const dlUrl = `${API_BASE}/api/episodes/${currentStudioEpisode.id}/audio?lang=${encodeURIComponent(lang)}&download=1`;

    const a = document.createElement("a");
    a.href = dlUrl;
    a.download = dlFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    showInfoBanner(
      "Download Started",
      `Downloading ${lang.toUpperCase()} audio track for Episode #${currentStudioEpisode.id} (${dlFilename}).`
    );
  }

  // Copy Dialogue Script to Clipboard
  function copyScriptToClipboardAction() {
    if (!currentStudioEpisode || !currentStudioEpisode.podcast_script) {
      showInfoBanner("Script Required", "No dialogue script available to copy for this episode.");
      return;
    }

    const script = currentStudioEpisode.podcast_script;
    const title = currentStudioEpisode.title || `Episode #${currentStudioEpisode.id}`;
    let text = `# ${title}\n\n`;

    if (script.intro && Array.isArray(script.intro.lines) && script.intro.lines.length > 0) {
      text += `## Introduction\n`;
      script.intro.lines.forEach(l => {
        text += `${l.speaker || 'Host'}: ${l.text}\n`;
      });
      text += `\n`;
    }

    if (Array.isArray(script.segments) && script.segments.length > 0) {
      script.segments.forEach((seg, sIdx) => {
        text += `## Segment ${sIdx + 1}: ${seg.title || 'Discussion'}\n`;
        if (Array.isArray(seg.lines)) {
          seg.lines.forEach(l => {
            text += `${l.speaker || 'Host'}: ${l.text}\n`;
          });
        }
        text += `\n`;
      });
    }

    if (Array.isArray(script.key_takeaways) && script.key_takeaways.length > 0) {
      text += `## Key Takeaways\n`;
      script.key_takeaways.forEach(l => {
        text += `${l.speaker || 'Host'}: ${l.text}\n`;
      });
      text += `\n`;
    }

    if (script.outro && Array.isArray(script.outro.lines) && script.outro.lines.length > 0) {
      text += `## Outro\n`;
      script.outro.lines.forEach(l => {
        text += `${l.speaker || 'Host'}: ${l.text}\n`;
      });
      text += `\n`;
    }

    const handleSuccess = () => {
      if (btnCopyScriptText) {
        const orig = btnCopyScriptText.textContent;
        btnCopyScriptText.textContent = "✓ Copied!";
        setTimeout(() => {
          btnCopyScriptText.textContent = orig;
        }, 2200);
      }
      showInfoBanner("Script Copied", `Copied full dialogue script for '${title.slice(0, 35)}' to clipboard.`);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(handleSuccess).catch(err => {
        console.warn("Clipboard API failed, falling back to execCommand:", err);
        fallbackCopyText(text, handleSuccess);
      });
    } else {
      fallbackCopyText(text, handleSuccess);
    }
  }

  function fallbackCopyText(text, onSuccess) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      ta.setAttribute("readonly", "");
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      ta.setSelectionRange(0, 99999);
      document.execCommand("copy");
      document.body.removeChild(ta);
      onSuccess();
    } catch (e) {
      onSuccess();
    }
  }

  // Wire Studio Event Listeners
  if (btnCloseStudioViewer) {
    btnCloseStudioViewer.addEventListener("click", () => {
      if (podcastStudioViewer) {
        podcastStudioViewer.hidden = true;
      }
    });
  }

  if (btnGenerateAudio) {
    btnGenerateAudio.addEventListener("click", generatePodcastAudioAction);
  }

  if (btnGenerateScriptInStudio) {
    btnGenerateScriptInStudio.addEventListener("click", generatePodcastScriptAction);
  }

  if (btnDownloadAudio) {
    btnDownloadAudio.addEventListener("click", downloadActiveTrackAction);
  }

  if (btnCopyScript) {
    btnCopyScript.addEventListener("click", copyScriptToClipboardAction);
  }

  if (audioLanguageSelect) {
    audioLanguageSelect.addEventListener("change", async () => {
      if (!currentStudioEpisode) return;
      const lang = audioLanguageSelect.value.toLowerCase();

      const availableLangs = Array.isArray(currentStudioEpisode.available_audio_languages)
        ? currentStudioEpisode.available_audio_languages.map(l => l.toLowerCase())
        : [];

      if (availableLangs.includes(lang)) {
        if (studioActiveTrackPill) {
          studioActiveTrackPill.textContent = `Track: ${lang.toUpperCase()} (Ready)`;
          studioActiveTrackPill.className = "studio-track-pill ready";
        }
        if (playerSubheading) {
          const srcCount = currentStudioEpisode.sources ? currentStudioEpisode.sources.length : 0;
          playerSubheading.textContent = `Episode #${currentStudioEpisode.id} • ${lang.toUpperCase()} • ${srcCount} news source${srcCount === 1 ? '' : 's'}`;
        }
        if (htmlPodcastAudio) {
          htmlPodcastAudio.src = `${API_BASE}/api/episodes/${currentStudioEpisode.id}/audio?lang=${encodeURIComponent(lang)}&t=${Date.now()}`;
          htmlPodcastAudio.load();
          if (currentPlaybackSpeed) {
            htmlPodcastAudio.playbackRate = currentPlaybackSpeed;
          }
        }
        if (mainPlayBtn) mainPlayBtn.disabled = false;
        if (mainRewindBtn) mainRewindBtn.disabled = false;
        if (mainForwardBtn) mainForwardBtn.disabled = false;
        if (btnDownloadAudio) btnDownloadAudio.disabled = false;
        if (playerPhaseBadge) playerPhaseBadge.textContent = "Audio Ready";
        showAudioStatusBanner(
          "success",
          `Audio Track Loaded (${lang.toUpperCase()})`,
          `Loaded existing ${lang.toUpperCase()} audio track for this episode.`
        );
      } else {
        if (htmlPodcastAudio) {
          htmlPodcastAudio.pause();
          htmlPodcastAudio.removeAttribute("src");
          htmlPodcastAudio.load();
        }
        setMainPlayerState(false);
        if (mainPlayBtn) mainPlayBtn.disabled = true;
        if (mainRewindBtn) mainRewindBtn.disabled = true;
        if (mainForwardBtn) mainForwardBtn.disabled = true;
        if (btnDownloadAudio) btnDownloadAudio.disabled = true;
        if (studioActiveTrackPill) {
          studioActiveTrackPill.textContent = `Track: ${lang.toUpperCase()} (Not Generated)`;
          studioActiveTrackPill.className = "studio-track-pill pending";
        }
        if (playerSubheading) {
          playerSubheading.textContent = `Episode #${currentStudioEpisode.id} • ${lang.toUpperCase()} • Audio Not Yet Generated`;
        }
        if (playerPhaseBadge) playerPhaseBadge.textContent = "Audio Not Generated";
        if (btnGenerateAudio) {
          const hasScript = Boolean(currentStudioEpisode.podcast_script && (currentStudioEpisode.script_ready || currentStudioEpisode.script_status === 'completed'));
          btnGenerateAudio.disabled = !hasScript;
        }
        showAudioStatusBanner(
          "info",
          `${lang.toUpperCase()} Audio Not Yet Generated`,
          `Click "Generate Podcast Audio" below to synthesize Host & CoHost dialogue in ${lang.toUpperCase()}.`
        );
      }
      updateStudioLangPills(currentStudioEpisode, lang);
    });
  }

  // =========================================================================
  // Main Player Playback Controller
  // =========================================================================
  function formatSeconds(sec) {
    if (isNaN(sec) || sec < 0) return "--:--";
    const totalSecs = Math.round(sec);
    const hrs = Math.floor(totalSecs / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;
    if (hrs > 0) {
      return `${hrs.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function setMainPlayerState(isPlaying) {
    if (mainPlayIcon) mainPlayIcon.style.display = isPlaying ? "none" : "block";
    if (mainPauseIcon) mainPauseIcon.style.display = isPlaying ? "block" : "none";
    if (waveformBars) {
      if (isPlaying) {
        waveformBars.classList.add("is-playing");
      } else {
        waveformBars.classList.remove("is-playing");
      }
    }
    if (playerPhaseBadge) {
      playerPhaseBadge.textContent = isPlaying ? "Now Playing" : "Paused";
    }

    // Sync button state on active episode card in library
    if (currentPlayingEpisode) {
      const activeCard = document.querySelector(`.episode-item-card[data-id="${currentPlayingEpisode.id}"]`);
      if (activeCard) {
        const playBtn = activeCard.querySelector(".btn-play-ep");
        if (playBtn) {
          if (isPlaying) {
            playBtn.innerHTML = `<span>⏸</span> Pause`;
            playBtn.classList.add("btn-playing");
            playBtn.title = "Pause audio playback";
          } else {
            playBtn.innerHTML = `<span>▶</span> Listen`;
            playBtn.classList.remove("btn-playing");
            playBtn.title = "Listen to generated podcast audio";
          }
        }
      }
    }
  }

  if (htmlPodcastAudio) {
    htmlPodcastAudio.addEventListener("error", (e) => {
      console.warn("Audio playback error:", e);
      setMainPlayerState(false);
      if (playerPhaseBadge) playerPhaseBadge.textContent = "Audio Unavailable";
      if (mainPlayerNote) {
        mainPlayerNote.textContent = "Unable to stream audio track for this language.";
      }
    });

    htmlPodcastAudio.addEventListener("waiting", () => {
      if (playerPhaseBadge) playerPhaseBadge.textContent = "Buffering...";
    });

    htmlPodcastAudio.addEventListener("playing", () => {
      setMainPlayerState(true);
      if (playerPhaseBadge) playerPhaseBadge.textContent = "Now Playing";
    });

    htmlPodcastAudio.addEventListener("play", () => {
      if (currentPlaybackSpeed && !isNaN(currentPlaybackSpeed)) {
        htmlPodcastAudio.playbackRate = currentPlaybackSpeed;
      }
      setMainPlayerState(true);
    });
    htmlPodcastAudio.addEventListener("pause", () => setMainPlayerState(false));

    htmlPodcastAudio.addEventListener("ended", () => {
      setMainPlayerState(false);
      if (playerPhaseBadge) playerPhaseBadge.textContent = "Finished";
      if (mainProgressFill) mainProgressFill.style.width = "100%";
    });

    htmlPodcastAudio.addEventListener("timeupdate", () => {
      if (!htmlPodcastAudio.duration || isNaN(htmlPodcastAudio.duration)) return;
      const cur = htmlPodcastAudio.currentTime;
      const dur = htmlPodcastAudio.duration;
      const pct = (cur / dur) * 100;
      if (mainProgressFill) mainProgressFill.style.width = `${pct}%`;
      if (mainTimeCurrent) mainTimeCurrent.textContent = formatSeconds(cur);
      if (mainTimeDuration) mainTimeDuration.textContent = formatSeconds(dur);
      if (audioPlayerDuration) audioPlayerDuration.textContent = formatSeconds(dur);
    });

    htmlPodcastAudio.addEventListener("loadedmetadata", () => {
      if (htmlPodcastAudio.duration && !isNaN(htmlPodcastAudio.duration)) {
        const durFormatted = formatSeconds(htmlPodcastAudio.duration);
        if (mainTimeDuration) mainTimeDuration.textContent = durFormatted;
        if (audioPlayerDuration) audioPlayerDuration.textContent = durFormatted;
      }
      if (currentPlaybackSpeed && !isNaN(currentPlaybackSpeed)) {
        htmlPodcastAudio.playbackRate = currentPlaybackSpeed;
      }
    });
  }

  if (mainPlayBtn) {
    mainPlayBtn.addEventListener("click", () => {
      if (!htmlPodcastAudio || !htmlPodcastAudio.src) {
        showInfoBanner("Audio Required", "No podcast audio track loaded. Select an episode with ready audio or generate audio in the studio.");
        return;
      }

      if (htmlPodcastAudio.paused) {
        htmlPodcastAudio.play().catch(e => console.warn(e));
      } else {
        htmlPodcastAudio.pause();
      }
    });
  }

  if (mainRewindBtn) {
    mainRewindBtn.addEventListener("click", () => {
      if (htmlPodcastAudio) {
        htmlPodcastAudio.currentTime = Math.max(0, htmlPodcastAudio.currentTime - 15);
      }
    });
  }

  if (mainForwardBtn) {
    mainForwardBtn.addEventListener("click", () => {
      if (htmlPodcastAudio) {
        htmlPodcastAudio.currentTime = Math.min(htmlPodcastAudio.duration || 0, htmlPodcastAudio.currentTime + 15);
      }
    });
  }

  // =========================================================================
  // Playback Speed Controller (Phase 2 Enhancement: 0.75x, 1.0x, 1.25x, 1.5x)
  // =========================================================================
  const playbackRates = [0.75, 1.0, 1.25, 1.5];
  let currentPlaybackRateIndex = 1; // Default: 1.0x (index 1)
  let currentPlaybackSpeed = 1.0;

  function setPlaybackSpeed(rate) {
    const parsed = parseFloat(rate);
    if (isNaN(parsed) || parsed <= 0) return;
    currentPlaybackSpeed = parsed;

    const idx = playbackRates.indexOf(currentPlaybackSpeed);
    if (idx !== -1) {
      currentPlaybackRateIndex = idx;
    }

    if (htmlPodcastAudio) {
      htmlPodcastAudio.playbackRate = currentPlaybackSpeed;
    }

    if (mainSpeedBtn) {
      mainSpeedBtn.textContent = `${currentPlaybackSpeed}x`;
    }

    const speedButtons = document.querySelectorAll(".speed-btn");
    speedButtons.forEach(btn => {
      const btnSpeed = parseFloat(btn.getAttribute("data-speed"));
      const isMatch = Math.abs(btnSpeed - currentPlaybackSpeed) < 0.01;
      btn.classList.toggle("active", isMatch);
      btn.setAttribute("aria-checked", isMatch ? "true" : "false");
    });
  }

  if (mainSpeedBtn) {
    mainSpeedBtn.addEventListener("click", () => {
      currentPlaybackRateIndex = (currentPlaybackRateIndex + 1) % playbackRates.length;
      setPlaybackSpeed(playbackRates[currentPlaybackRateIndex]);
    });
  }

  if (playerSpeedSelector) {
    playerSpeedSelector.addEventListener("click", (e) => {
      const btn = e.target.closest(".speed-btn");
      if (btn && btn.dataset.speed) {
        setPlaybackSpeed(parseFloat(btn.dataset.speed));
      }
    });
  }

  if (mainProgressBar) {
    mainProgressBar.addEventListener("click", (e) => {
      if (!htmlPodcastAudio || !htmlPodcastAudio.duration) return;
      const rect = mainProgressBar.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const width = rect.width;
      const pct = Math.max(0, Math.min(1, clickX / width));
      htmlPodcastAudio.currentTime = pct * htmlPodcastAudio.duration;
    });
  }

  // =========================================================================
  // Studio Language Selector Pills Sync & Click Handlers
  // =========================================================================
  function updateStudioLangPills(ep, currentLang) {
    const availableTracks = Array.isArray(ep?.available_audio_languages)
      ? ep.available_audio_languages.map(l => l.toLowerCase())
      : [];

    const pills = document.querySelectorAll(".lang-pill-btn");
    pills.forEach(pill => {
      const pillLang = pill.getAttribute("data-lang")?.toLowerCase();
      const statusSpan = pill.querySelector(".lang-pill-status");
      const isReady = availableTracks.includes(pillLang);

      if (statusSpan) {
        statusSpan.textContent = isReady ? "Ready" : "--";
        statusSpan.className = `lang-pill-status ${isReady ? 'ready' : 'none'}`;
      }
      pill.dataset.status = isReady ? "ready" : "none";

      const isActive = pillLang === currentLang?.toLowerCase();
      pill.classList.toggle("active", isActive);
      pill.setAttribute("aria-checked", isActive ? "true" : "false");
    });
  }

  // Wire quick language pill clicks to synchronize select dropdown
  const langPills = document.querySelectorAll(".lang-pill-btn");
  langPills.forEach(pill => {
    pill.addEventListener("click", () => {
      const lang = pill.getAttribute("data-lang");
      if (!lang || !audioLanguageSelect) return;
      audioLanguageSelect.value = lang;
      audioLanguageSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });

  // =========================================================================
  // Volume Slider & Mute Toggle Controls
  // =========================================================================
  function updateVolumeIcons(vol) {
    if (volumeIconHigh && volumeIconMuted) {
      if (vol === 0) {
        volumeIconHigh.style.display = "none";
        volumeIconMuted.style.display = "block";
      } else {
        volumeIconHigh.style.display = "block";
        volumeIconMuted.style.display = "none";
      }
    }
  }

  if (mainVolumeSlider && htmlPodcastAudio) {
    mainVolumeSlider.addEventListener("input", () => {
      const vol = parseFloat(mainVolumeSlider.value);
      htmlPodcastAudio.volume = vol;
      if (vol > 0) lastNonZeroVolume = vol;
      updateVolumeIcons(vol);
    });
  }

  if (mainVolumeBtn && htmlPodcastAudio) {
    mainVolumeBtn.addEventListener("click", () => {
      if (htmlPodcastAudio.volume > 0) {
        lastNonZeroVolume = htmlPodcastAudio.volume;
        htmlPodcastAudio.volume = 0;
        if (mainVolumeSlider) mainVolumeSlider.value = 0;
      } else {
        const restoreVol = lastNonZeroVolume || 1.0;
        htmlPodcastAudio.volume = restoreVol;
        if (mainVolumeSlider) mainVolumeSlider.value = restoreVol;
      }
      updateVolumeIcons(htmlPodcastAudio.volume);
    });
  }

  // =========================================================================
  // Global Keyboard Accessibility (Space, Arrows, Mute)
  // =========================================================================
  window.addEventListener("keydown", (e) => {
    const activeEl = document.activeElement;
    const isInput = activeEl && (
      activeEl.tagName === "INPUT" ||
      activeEl.tagName === "TEXTAREA" ||
      activeEl.tagName === "SELECT" ||
      activeEl.isContentEditable
    );
    if (isInput) return;

    if (e.code === "Space" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      if (mainPlayBtn && !mainPlayBtn.disabled) {
        mainPlayBtn.click();
      }
    } else if (e.code === "ArrowLeft" || e.key === "ArrowLeft") {
      e.preventDefault();
      if (mainRewindBtn && !mainRewindBtn.disabled) {
        mainRewindBtn.click();
      }
    } else if (e.code === "ArrowRight" || e.key === "ArrowRight") {
      e.preventDefault();
      if (mainForwardBtn && !mainForwardBtn.disabled) {
        mainForwardBtn.click();
      }
    } else if (e.key === "m" || e.key === "M" || e.code === "KeyM") {
      e.preventDefault();
      if (mainVolumeBtn) {
        mainVolumeBtn.click();
      }
    }
  });

  if (mainProgressBar && htmlPodcastAudio) {
    mainProgressBar.addEventListener("keydown", (e) => {
      if (!htmlPodcastAudio.duration) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        htmlPodcastAudio.currentTime = Math.max(0, htmlPodcastAudio.currentTime - 5);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        htmlPodcastAudio.currentTime = Math.min(htmlPodcastAudio.duration, htmlPodcastAudio.currentTime + 5);
      } else if (e.key === "Home") {
        e.preventDefault();
        htmlPodcastAudio.currentTime = 0;
      } else if (e.key === "End") {
        e.preventDefault();
        htmlPodcastAudio.currentTime = htmlPodcastAudio.duration;
      }
    });
  }

  // Initial setup
  setNewsView("empty");
  checkHealth();
  updateClearButtonVisibility();
  updateSelectionCounter();
  fetchEpisodes();
});
