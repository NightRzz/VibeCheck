const totalCount = document.getElementById("total-count");
const avgScore = document.getElementById("avg-score");
const scoreRange = document.getElementById("score-range");
const statsScopeLabel = document.getElementById("stats-scope-label");
const globalViewButton = document.getElementById("global-view-button");
const gaugeScore = document.getElementById("gauge-score");
const latestText = document.getElementById("latest-text");
const latestSource = document.getElementById("latest-source");
const latestAuthor = document.getElementById("latest-author");
const latestTime = document.getElementById("latest-time");
const feedList = document.getElementById("feed-list");
const videoList = document.getElementById("video-list");
const trackForm = document.getElementById("track-form");
const trackInput = document.getElementById("track-input");
const trackButton = document.getElementById("track-button");
const trackFeedback = document.getElementById("track-feedback");

const state = {
  activeVideoId: null,
  globalAnalytics: createAnalyticsSnapshot(),
  trackedVideos: [],
  analyticsByVideo: new Map(),
  latestByVideo: new Map(),
  pendingVideoIds: new Set(),
  globalLatest: null,
  lastSeenId: 0,
  refreshTimerId: null,
};

function createAnalyticsSnapshot(videoId = null, title = "Global View") {
  return {
    videoId,
    title,
    totalMessages: 0,
    averageScore: 0,
    minScore: 0,
    maxScore: 0,
    hasData: false,
  };
}

function normalizeAnalytics(payload) {
  return {
    videoId: payload.video_id ?? null,
    title: payload.title ?? (payload.video_id ?? "Global View"),
    totalMessages: Number(payload.total_messages ?? 0),
    averageScore: Number(payload.average_score ?? 0),
    minScore: Number(payload.min_score ?? 0),
    maxScore: Number(payload.max_score ?? 0),
    hasData: Number(payload.total_messages ?? 0) > 0,
  };
}

function getScoreColor(score) {
  if (score >= 0.25) {
    return "#1f8a70";
  }
  if (score <= -0.25) {
    return "#c44536";
  }
  return "#d0a529";
}

function setGauge(score) {
  const normalized = Math.max(0, Math.min(100, ((score + 1) / 2) * 100));
  const color = getScoreColor(score);
  document.documentElement.style.setProperty("--gauge-fill", normalized.toFixed(2));
  document.documentElement.style.setProperty("--gauge-color", color);
  gaugeScore.textContent = score.toFixed(2);
}

function formatTimestamp(value) {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleString();
}

function findVideo(videoId) {
  return state.trackedVideos.find((video) => video.video_id === videoId) ?? null;
}

function getViewedAnalytics() {
  if (!state.activeVideoId) {
    return state.globalAnalytics;
  }

  return (
    state.analyticsByVideo.get(state.activeVideoId) ??
    createAnalyticsSnapshot(
      state.activeVideoId,
      findVideo(state.activeVideoId)?.title ?? state.activeVideoId,
    )
  );
}

function renderSummary() {
  const analytics = getViewedAnalytics();
  totalCount.textContent = analytics.totalMessages;
  statsScopeLabel.textContent = analytics.title || "Global View";
  globalViewButton.classList.toggle("is-active", state.activeVideoId === null);

  if (!analytics.hasData) {
    avgScore.textContent = "0.00";
    scoreRange.textContent = "0.00 / 0.00";
    setGauge(0);
    return;
  }

  avgScore.textContent = analytics.averageScore.toFixed(2);
  scoreRange.textContent = `${analytics.minScore.toFixed(2)} / ${analytics.maxScore.toFixed(2)}`;
  setGauge(analytics.averageScore);
}

function setTrackLoading(isLoading) {
  trackButton.disabled = isLoading;
  trackButton.classList.toggle("loading", isLoading);
}

function setTrackFeedback(message, isError = false) {
  trackFeedback.textContent = message;
  trackFeedback.classList.toggle("error", isError);
}

function markVideoFetched(videoId) {
  if (!videoId || !state.pendingVideoIds.has(videoId)) {
    return;
  }

  state.pendingVideoIds.delete(videoId);
  renderTrackedVideos();
}

function renderFeedItem(item) {
  const score = Number(item.score);
  const article = document.createElement("article");
  article.className = "feed-card";
  article.style.setProperty("--gauge-color", getScoreColor(score));

  const source = document.createElement("span");
  source.textContent = item.video_id ? `YouTube / ${item.video_id}` : item.source_id;

  const scoreElement = document.createElement("strong");
  scoreElement.textContent = score.toFixed(2);

  const text = document.createElement("p");
  text.textContent = item.text;

  const meta = document.createElement("div");
  meta.className = "feed-meta";

  const author = document.createElement("span");
  author.textContent = `author: ${item.author ?? "n/a"}`;

  const time = document.createElement("span");
  time.textContent = `time: ${formatTimestamp(item.timestamp)}`;

  meta.append(author, time);
  article.append(source, scoreElement, text, meta);
  return article;
}

function syncLatestPanel() {
  const activeItem = state.activeVideoId
    ? state.latestByVideo.get(state.activeVideoId) ?? null
    : null;
  const item = activeItem ?? state.globalLatest;

  if (!item) {
    latestText.textContent = "Waiting for the first tracked comment...";
    latestSource.textContent = "video: n/a";
    latestAuthor.textContent = "author: n/a";
    latestTime.textContent = "time: n/a";
    setGauge(0);
    return;
  }

  const score = Number(item.score);
  latestText.textContent = item.text;
  latestSource.textContent = `video: ${item.video_id ?? item.source_id}`;
  latestAuthor.textContent = `author: ${item.author ?? "n/a"}`;
  latestTime.textContent = `time: ${formatTimestamp(item.timestamp)}`;

  if (!state.activeVideoId || state.activeVideoId === item.video_id) {
    setGauge(score);
  }
}

function renderTrackedVideos() {
  videoList.innerHTML = "";
  const activeVideos = state.trackedVideos.filter((video) => video.is_active);

  if (activeVideos.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state";
    emptyState.textContent = "No videos are being tracked yet.";
    videoList.appendChild(emptyState);
    return;
  }

  for (const video of activeVideos) {
    const article = document.createElement("article");
    article.className = "video-card";
    if (state.pendingVideoIds.has(video.video_id)) {
      article.classList.add("pending");
    }
    if (state.activeVideoId === video.video_id) {
      article.classList.add("active-view");
    }

    article.addEventListener("click", () => selectVideo(video.video_id));

    const label = document.createElement("span");
    label.className = "video-label";
    label.textContent = video.video_id;

    const title = document.createElement("p");
    title.className = "video-title";
    title.textContent = video.title;

    const summary = document.createElement("p");
    summary.className = "video-summary";
    summary.textContent = `${Number(video.message_count ?? 0)} msgs | ${Number(video.average_score ?? 0).toFixed(2)} vibe`;

    const meta = document.createElement("div");
    meta.className = "video-meta";

    const added = document.createElement("span");
    added.textContent = `added: ${formatTimestamp(video.added_at)}`;

    const status = document.createElement("span");
    status.textContent = state.pendingVideoIds.has(video.video_id)
      ? "fetching first batch"
      : "active";

    meta.append(added, status);

    const removeButton = document.createElement("button");
    removeButton.className = "video-delete";
    removeButton.type = "button";
    removeButton.setAttribute("aria-label", `Stop tracking ${video.title}`);
    removeButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteTrackedVideo(video.video_id);
    });

    article.append(label, title, summary, meta, removeButton);
    videoList.appendChild(article);
  }
}

async function loadAnalytics() {
  const response = await fetch("/analytics");
  const payload = await response.json();

  const snapshot = normalizeAnalytics(payload);
  state.globalAnalytics.minScore = snapshot.minScore;
  state.globalAnalytics.maxScore = snapshot.maxScore;
  state.globalAnalytics.title = snapshot.title;
  state.globalLatest = null;
  state.latestByVideo.clear();
  feedList.innerHTML = "";

  for (const item of payload.recent ?? []) {
    state.lastSeenId = Math.max(state.lastSeenId, Number(item.id ?? 0));
    if (!state.globalLatest) {
      state.globalLatest = item;
    }
    if (item.video_id && !state.latestByVideo.has(item.video_id)) {
      state.latestByVideo.set(item.video_id, item);
      markVideoFetched(item.video_id);
    }
    feedList.appendChild(renderFeedItem(item));
  }

  renderSummary();
  syncLatestPanel();
}

async function loadTrackedVideos() {
  const response = await fetch("/v1/tracked");
  const payload = await response.json();
  state.trackedVideos = Array.isArray(payload.items) ? payload.items : [];

  const global = payload.global ?? { total_messages: 0, average_score: null };
  state.globalAnalytics.title = "Global View";
  state.globalAnalytics.totalMessages = Number(global.total_messages ?? 0);
  state.globalAnalytics.averageScore = Number(global.average_score ?? 0);
  state.globalAnalytics.hasData = state.globalAnalytics.totalMessages > 0;

  for (const video of state.trackedVideos) {
    const snapshot = state.analyticsByVideo.get(video.video_id) ?? createAnalyticsSnapshot(
      video.video_id,
      video.title,
    );
    snapshot.title = video.title;
    snapshot.totalMessages = Number(video.message_count ?? 0);
    snapshot.averageScore = Number(video.average_score ?? 0);
    snapshot.hasData = snapshot.totalMessages > 0;
    state.analyticsByVideo.set(video.video_id, snapshot);
  }

  const activeIds = new Set(
    state.trackedVideos
      .filter((video) => video.is_active)
      .map((video) => video.video_id),
  );
  for (const pendingId of [...state.pendingVideoIds]) {
    if (!activeIds.has(pendingId)) {
      state.pendingVideoIds.delete(pendingId);
    }
  }

  if (state.activeVideoId && !activeIds.has(state.activeVideoId)) {
    state.activeVideoId = null;
  }

  renderTrackedVideos();
  renderSummary();
  syncLatestPanel();
}

async function loadVideoAnalytics(videoId) {
  const response = await fetch(`/v1/analytics/${encodeURIComponent(videoId)}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail ?? "Unable to load video analytics.");
  }

  const snapshot = normalizeAnalytics(payload);
  state.analyticsByVideo.set(videoId, snapshot);
  renderSummary();
  syncLatestPanel();
}

function selectVideo(videoId) {
  state.activeVideoId = videoId;
  renderTrackedVideos();
  renderSummary();
  syncLatestPanel();
  loadVideoAnalytics(videoId).catch((error) => {
    setTrackFeedback(error.message || "Unable to load video analytics.", true);
  });
}

function scheduleStatsRefresh() {
  if (state.refreshTimerId !== null) {
    return;
  }

  state.refreshTimerId = window.setTimeout(async () => {
    state.refreshTimerId = null;

    try {
      if (state.activeVideoId) {
        await Promise.all([
          loadTrackedVideos(),
          loadVideoAnalytics(state.activeVideoId),
        ]);
      } else {
        await Promise.all([loadTrackedVideos(), loadAnalytics()]);
      }
    } catch (error) {
      setTrackFeedback(
        error.message || "Unable to refresh live analytics.",
        true,
      );
    }
  }, 250);
}

async function submitTrack(event) {
  event.preventDefault();
  const value = trackInput.value.trim();
  if (!value) {
    setTrackFeedback("Enter a YouTube URL or video ID first.", true);
    return;
  }

  setTrackLoading(true);
  setTrackFeedback("Resolving video metadata...");

  try {
    const response = await fetch("/v1/track", {
      method: "POST",
      headers: {
        "Content-Type": "application/json; charset=utf-8",
      },
      body: JSON.stringify({ video: value }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail ?? "Unable to track that video.");
    }

    state.pendingVideoIds.add(payload.video_id);
    trackInput.value = "";
    setTrackFeedback(`Tracking ${payload.title}.`);
    await loadTrackedVideos();
  } catch (error) {
    setTrackFeedback(error.message || "Unable to track that video.", true);
  } finally {
    setTrackLoading(false);
  }
}

async function deleteTrackedVideo(videoId) {
  try {
    const response = await fetch(`/v1/track/${encodeURIComponent(videoId)}`, {
      method: "DELETE",
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail ?? "Unable to stop tracking that video.");
    }

    state.pendingVideoIds.delete(videoId);
    state.latestByVideo.delete(videoId);
    state.analyticsByVideo.delete(videoId);
    if (state.activeVideoId === videoId) {
      state.activeVideoId = null;
    }

    setTrackFeedback("Tracking removed.");
    await Promise.all([loadTrackedVideos(), loadAnalytics()]);
  } catch (error) {
    setTrackFeedback(error.message || "Unable to stop tracking that video.", true);
  }
}

function connectLiveFeed() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(
    `${protocol}://${window.location.host}/live-feed?last_seen_id=${state.lastSeenId}`,
  );

  socket.onmessage = (event) => {
    const item = JSON.parse(event.data);
    const itemId = Number(item.id ?? 0);
    if (itemId <= state.lastSeenId) {
      return;
    }

    state.lastSeenId = itemId;

    if (item.video_id) {
      markVideoFetched(item.video_id);
      state.latestByVideo.set(item.video_id, item);
    }

    state.globalLatest = item;
    syncLatestPanel();

    feedList.prepend(renderFeedItem(item));
    while (feedList.children.length > 10) {
      feedList.removeChild(feedList.lastChild);
    }

    scheduleStatsRefresh();
  };

  socket.onclose = () => {
    window.setTimeout(connectLiveFeed, 1500);
  };
}

globalViewButton.addEventListener("click", () => {
  state.activeVideoId = null;
  renderTrackedVideos();
  renderSummary();
  syncLatestPanel();
});

trackForm.addEventListener("submit", submitTrack);

Promise.all([loadAnalytics(), loadTrackedVideos()])
  .then(() => {
    connectLiveFeed();
  })
  .catch((error) => {
    console.error(error);
    setTrackFeedback("Dashboard bootstrap failed. Check the API logs.", true);
  });
