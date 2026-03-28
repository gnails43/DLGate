// Handle messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ADD_URL") {
    addUrl(message.data).then((result) => sendResponse(result));
    return true; // async
  }
  if (message.type === "CHECK_URL") {
    checkUrl(message.url).then((exists) => sendResponse({ exists }));
    return true;
  }
  if (message.type === "GET_COUNT") {
    getCount().then((count) => sendResponse({ count }));
    return true;
  }
});

async function addUrl(data) {
  const { dlgate_urls = [] } = await chrome.storage.local.get("dlgate_urls");

  // Check for duplicate
  if (dlgate_urls.some((item) => item.url === data.url)) {
    return { success: false, reason: "duplicate" };
  }

  dlgate_urls.push({
    url: data.url,
    title: data.title || "",
    artist: data.artist || "",
    added_at: new Date().toISOString(),
    type: data.type || "soundcloud",
  });

  await chrome.storage.local.set({ dlgate_urls });
  updateBadge(dlgate_urls.length);
  return { success: true };
}

async function checkUrl(url) {
  const { dlgate_urls = [] } = await chrome.storage.local.get("dlgate_urls");
  return dlgate_urls.some((item) => item.url === url);
}

async function getCount() {
  const { dlgate_urls = [] } = await chrome.storage.local.get("dlgate_urls");
  return dlgate_urls.length;
}

function updateBadge(count) {
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#ff5500" });
}

// Initialize badge on startup
chrome.runtime.onStartup.addListener(async () => {
  const count = await getCount();
  updateBadge(count);
});

chrome.runtime.onInstalled.addListener(async () => {
  const count = await getCount();
  updateBadge(count);
});
