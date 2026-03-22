// DLGate Content Script
// Injects "DL List" button on SoundCloud and Hypeddit pages

(function () {
  const BUTTON_ID = "dlgate-add-btn";
  let currentUrl = location.href;

  function isSoundCloudTrackPage() {
    // Track pages: soundcloud.com/artist/track-name (exactly 2 path segments, not /sets/, /likes, etc.)
    const path = location.pathname.replace(/\/$/, "");
    const segments = path.split("/").filter(Boolean);
    if (segments.length !== 2) return false;
    const reserved = [
      "discover",
      "stream",
      "you",
      "search",
      "upload",
      "settings",
      "messages",
      "notifications",
      "charts",
      "stations",
    ];
    if (reserved.includes(segments[0])) return false;
    // Exclude sets, reposts, likes, etc.
    const reservedSecond = [
      "sets",
      "likes",
      "reposts",
      "followers",
      "following",
      "tracks",
      "albums",
      "playlists",
      "popular-tracks",
      "comments",
    ];
    if (reservedSecond.includes(segments[1])) return false;
    return true;
  }

  function isHypedditPage() {
    return location.hostname.includes("hypeddit.com");
  }

  function getTrackInfo() {
    if (isSoundCloudTrackPage()) {
      const titleEl = document.querySelector(
        ".soundTitle__title span, .listenDetails__trackTitle span"
      );
      const artistEl = document.querySelector(
        ".soundTitle__username, .listenDetails__artist"
      );
      return {
        url: location.href.split("?")[0],
        title: titleEl ? titleEl.textContent.trim() : document.title,
        artist: artistEl ? artistEl.textContent.trim() : "",
        type: "soundcloud",
      };
    }
    if (isHypedditPage()) {
      const titleEl = document.querySelector(
        ".track-title, .fangate-track-title, h1"
      );
      const artistEl = document.querySelector(
        ".track-artist, .fangate-artist-name"
      );
      return {
        url: location.href.split("?")[0],
        title: titleEl ? titleEl.textContent.trim() : document.title,
        artist: artistEl ? artistEl.textContent.trim() : "",
        type: "hypeddit",
      };
    }
    return null;
  }

  function createButton() {
    const btn = document.createElement("button");
    btn.id = BUTTON_ID;
    btn.className = "dlgate-btn";
    btn.textContent = "+ DL List";
    btn.addEventListener("click", handleClick);
    return btn;
  }

  async function handleClick() {
    const btn = document.getElementById(BUTTON_ID);
    if (!btn || btn.classList.contains("dlgate-btn-added")) return;

    const info = getTrackInfo();
    if (!info) return;

    btn.textContent = "...";
    btn.disabled = true;

    const response = await chrome.runtime.sendMessage({
      type: "ADD_URL",
      data: info,
    });

    if (response.success) {
      btn.textContent = "Added";
      btn.classList.add("dlgate-btn-added");
    } else if (response.reason === "duplicate") {
      btn.textContent = "Already added";
      btn.classList.add("dlgate-btn-added");
    } else {
      btn.textContent = "Error";
      btn.disabled = false;
    }
  }

  async function checkAndUpdateButton() {
    const btn = document.getElementById(BUTTON_ID);
    if (!btn) return;

    const url = location.href.split("?")[0];
    const response = await chrome.runtime.sendMessage({
      type: "CHECK_URL",
      url,
    });

    if (response.exists) {
      btn.textContent = "Added";
      btn.classList.add("dlgate-btn-added");
    } else {
      btn.textContent = "+ DL List";
      btn.classList.remove("dlgate-btn-added");
      btn.disabled = false;
    }
  }

  function injectButton() {
    // Remove existing button
    const existing = document.getElementById(BUTTON_ID);
    if (existing) existing.remove();

    if (!isSoundCloudTrackPage() && !isHypedditPage()) return;

    const btn = createButton();

    if (isSoundCloudTrackPage()) {
      // Try to inject near the action bar
      const actionBar = document.querySelector(
        ".soundActions, .listenEngagement__actions"
      );
      if (actionBar) {
        actionBar.prepend(btn);
      } else {
        // Fallback: fixed position button
        btn.classList.add("dlgate-btn-fixed");
        document.body.appendChild(btn);
      }
    } else if (isHypedditPage()) {
      btn.classList.add("dlgate-btn-fixed");
      document.body.appendChild(btn);
    }

    checkAndUpdateButton();
  }

  // SoundCloud is an SPA - watch for URL changes
  function watchUrlChanges() {
    setInterval(() => {
      if (location.href !== currentUrl) {
        currentUrl = location.href;
        // Small delay for SPA content to render
        setTimeout(injectButton, 1000);
      }
    }, 500);
  }

  // Also use MutationObserver for SoundCloud SPA transitions
  function watchDomChanges() {
    const observer = new MutationObserver(() => {
      if (
        (isSoundCloudTrackPage() || isHypedditPage()) &&
        !document.getElementById(BUTTON_ID)
      ) {
        injectButton();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Initial injection
  setTimeout(injectButton, 1000);
  watchUrlChanges();
  watchDomChanges();
})();
