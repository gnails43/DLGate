// DLGate Content Script
// Injects "DL List" button on SoundCloud and Hypeddit pages

(function () {
  const BUTTON_CLASS = "dlgate-add-btn";
  let currentUrl = location.href;

  function isHypedditPage() {
    return location.hostname.includes("hypeddit.com");
  }

  function getTrackInfoFromPage() {
    if (location.hostname.includes("soundcloud.com")) {
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

  function extractTrackUrlFromContext(element) {
    // Walk up from the button area to find the containing sound item,
    // then find the track title link within it
    let container = element;
    for (let i = 0; i < 15; i++) {
      if (!container.parentElement) break;
      container = container.parentElement;
      // Look for a title link in this container
      const titleLink = container.querySelector(
        'a[href*="/"]:not([href*="/tags/"]):not([href*="/discover"])'
      );
      if (titleLink) {
        const href = titleLink.href;
        try {
          const url = new URL(href);
          const segments = url.pathname
            .replace(/\/$/, "")
            .split("/")
            .filter(Boolean);
          // Must be artist/track format (2 segments)
          if (segments.length === 2 && !isReservedPath(segments)) {
            // Try to get title and artist text
            const titleText = titleLink.textContent.trim();
            // Look for artist link nearby
            let artistText = "";
            const artistLink = container.querySelector(
              'a.soundTitle__username, a[href="/' + segments[0] + '"]'
            );
            if (artistLink && artistLink !== titleLink) {
              artistText = artistLink.textContent.trim();
            }
            return {
              url: href.split("?")[0],
              title: titleText || "",
              artist: artistText || segments[0],
              type: "soundcloud",
            };
          }
        } catch {
          continue;
        }
      }
    }
    return null;
  }

  function isReservedPath(segments) {
    const reserved = [
      "discover", "stream", "you", "search", "upload", "feed",
      "settings", "messages", "notifications", "charts", "stations",
    ];
    if (reserved.includes(segments[0])) return true;
    const reservedSecond = [
      "sets", "likes", "reposts", "followers", "following",
      "tracks", "albums", "playlists", "popular-tracks", "comments",
    ];
    if (reservedSecond.includes(segments[1])) return true;
    return false;
  }

  function createButton(trackInfo) {
    const btn = document.createElement("button");
    btn.className = `${BUTTON_CLASS} dlgate-btn sc-button sc-button-small`;
    btn.textContent = "+ DL List";
    btn.title = "Add to DLGate download list";
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
    try {
      const response = await chrome.runtime.sendMessage({
        type: "CHECK_URL",
        url,
      });
      if (response.exists) {
        btn.textContent = "Added";
        btn.classList.add("dlgate-btn-added");
      }
    } catch {
      // Extension context may be invalidated
    }
  }

  function injectButtons() {
    if (isHypedditPage()) {
      injectHypedditButton();
      return;
    }

    if (!location.hostname.includes("soundcloud.com")) return;

    // Strategy: Find all button groups that contain SC action buttons,
    // and insert our button after the last button in each group.
    // SC button groups use .sc-button-group containers.
    const buttonGroups = document.querySelectorAll(
      ".sc-button-group, .soundActions .sc-button-toolbar"
    );

    for (const group of buttonGroups) {
      // Skip if already has our button
      if (group.querySelector(`.${BUTTON_CLASS}`)) continue;

      // Must contain at least a few SC buttons to be an action bar
      const scButtons = group.querySelectorAll(".sc-button");
      if (scButtons.length < 3) continue;

      // Get track info from surrounding context
      const trackInfo = extractTrackUrlFromContext(group);
      if (!trackInfo) continue;

      const btn = createButton(trackInfo);
      group.appendChild(btn);
      checkIfAdded(btn, trackInfo.url);
    }
  }

  function injectHypedditButton() {
    if (document.querySelector(`.${BUTTON_CLASS}`)) return;

    const trackInfo = getTrackInfoFromPage();
    if (!trackInfo) return;

    const btn = createButton(trackInfo);
    btn.classList.add("dlgate-btn-fixed");
    document.body.appendChild(btn);
    checkIfAdded(btn, trackInfo.url);
  }

  // SoundCloud is an SPA - watch for URL changes
  function watchUrlChanges() {
    setInterval(() => {
      if (location.href !== currentUrl) {
        currentUrl = location.href;
        setTimeout(injectButtons, 1500);
      }
    }, 500);
  }

  // MutationObserver for SPA transitions & lazy-loaded feed items
  function watchDomChanges() {
    let debounceTimer = null;
    const observer = new MutationObserver(() => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        injectButtons();
      }, 800);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Initial injection
  setTimeout(injectButtons, 1500);
  watchUrlChanges();
  watchDomChanges();
})();
