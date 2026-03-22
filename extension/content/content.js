// DLGate Content Script
// Injects "DL List" button on SoundCloud and Hypeddit pages

(function () {
  const BUTTON_CLASS = "dlgate-add-btn";
  let currentUrl = location.href;

  function isSoundCloudTrackPage() {
    const path = location.pathname.replace(/\/$/, "");
    const segments = path.split("/").filter(Boolean);
    if (segments.length !== 2) return false;
    const reserved = [
      "discover", "stream", "you", "search", "upload",
      "settings", "messages", "notifications", "charts", "stations",
    ];
    if (reserved.includes(segments[0])) return false;
    const reservedSecond = [
      "sets", "likes", "reposts", "followers", "following",
      "tracks", "albums", "playlists", "popular-tracks", "comments",
    ];
    if (reservedSecond.includes(segments[1])) return false;
    return true;
  }

  function isHypedditPage() {
    return location.hostname.includes("hypeddit.com");
  }

  function getTrackInfoFromPage() {
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

  function getTrackInfoFromFeedItem(item) {
    // Extract track URL from the feed item's title link
    const titleLink = item.querySelector(
      "a.soundTitle__title, a.sc-link-primary[href*='/']"
    );
    const artistLink = item.querySelector(
      "a.soundTitle__username, a.sc-link-light[href*='/']"
    );

    if (!titleLink) return null;

    const href = titleLink.href;
    if (!href) return null;

    // Validate it looks like a track URL (artist/track pattern)
    try {
      const url = new URL(href);
      const segments = url.pathname.replace(/\/$/, "").split("/").filter(Boolean);
      if (segments.length !== 2) return null;
    } catch {
      return null;
    }

    return {
      url: href.split("?")[0],
      title: titleLink.textContent.trim() || "",
      artist: artistLink ? artistLink.textContent.trim() : "",
      type: "soundcloud",
    };
  }

  function createButton(trackInfo) {
    const btn = document.createElement("button");
    btn.className = `${BUTTON_CLASS} dlgate-btn`;
    btn.textContent = "+ DL List";
    btn.dataset.dlgateUrl = trackInfo.url;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleClick(btn, trackInfo);
    });
    return btn;
  }

  async function handleClick(btn, trackInfo) {
    if (btn.classList.contains("dlgate-btn-added")) return;

    btn.textContent = "...";
    btn.disabled = true;

    const response = await chrome.runtime.sendMessage({
      type: "ADD_URL",
      data: trackInfo,
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

  async function checkIfAdded(btn, url) {
    const response = await chrome.runtime.sendMessage({
      type: "CHECK_URL",
      url,
    });

    if (response.exists) {
      btn.textContent = "Added";
      btn.classList.add("dlgate-btn-added");
    }
  }

  // --- Track page injection (after cart icon) ---
  function injectTrackPageButton() {
    if (!isSoundCloudTrackPage() && !isHypedditPage()) return;

    // Already injected on this page?
    const existing = document.querySelector(
      ".soundActions .dlgate-add-btn, .dlgate-btn-fixed"
    );
    if (existing) return;

    const trackInfo = getTrackInfoFromPage();
    if (!trackInfo) return;

    const btn = createButton(trackInfo);

    if (isSoundCloudTrackPage()) {
      // Find the action bar and insert after the last button (cart icon is typically last)
      const actionBar = document.querySelector(
        ".soundActions .sc-button-toolbar"
      );
      if (actionBar) {
        // Insert at the end of the toolbar (after cart icon)
        actionBar.appendChild(btn);
      } else {
        // Fallback: try the soundActions container
        const actions = document.querySelector(".soundActions");
        if (actions) {
          actions.appendChild(btn);
        } else {
          btn.classList.add("dlgate-btn-fixed");
          document.body.appendChild(btn);
        }
      }
    } else if (isHypedditPage()) {
      btn.classList.add("dlgate-btn-fixed");
      document.body.appendChild(btn);
    }

    checkIfAdded(btn, trackInfo.url);
  }

  // --- Feed injection ---
  function injectFeedButtons() {
    // Find all sound items in the feed that don't already have our button
    const soundItems = document.querySelectorAll(
      ".soundList__item, .stream__list li, .userStream__list li, .searchList__item"
    );

    for (const item of soundItems) {
      if (item.querySelector(`.${BUTTON_CLASS}`)) continue;

      const trackInfo = getTrackInfoFromFeedItem(item);
      if (!trackInfo) continue;

      const btn = createButton(trackInfo);
      btn.classList.add("dlgate-btn-feed");

      // Find the action buttons row within this item
      const toolbar = item.querySelector(".sc-button-toolbar");
      if (toolbar) {
        toolbar.appendChild(btn);
      } else {
        // Fallback: find any action/engagement area
        const actions = item.querySelector(
          ".soundActions, .sound__soundActions"
        );
        if (actions) {
          actions.appendChild(btn);
        }
      }

      checkIfAdded(btn, trackInfo.url);
    }
  }

  // --- Main injection logic ---
  function injectAll() {
    injectTrackPageButton();
    if (location.hostname.includes("soundcloud.com")) {
      injectFeedButtons();
    }
  }

  // SoundCloud is an SPA - watch for URL changes
  function watchUrlChanges() {
    setInterval(() => {
      if (location.href !== currentUrl) {
        currentUrl = location.href;
        setTimeout(injectAll, 1000);
      }
    }, 500);
  }

  // Also use MutationObserver for SoundCloud SPA transitions & lazy-loaded feed items
  function watchDomChanges() {
    let debounceTimer = null;
    const observer = new MutationObserver(() => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        injectAll();
      }, 500);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Initial injection
  setTimeout(injectAll, 1000);
  watchUrlChanges();
  watchDomChanges();
})();
