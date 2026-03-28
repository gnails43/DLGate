document.addEventListener("DOMContentLoaded", init);

async function init() {
  await renderList();
  document.getElementById("exportBtn").addEventListener("click", exportList);
  document.getElementById("clearBtn").addEventListener("click", clearList);
}

async function getUrls() {
  const { dlgate_urls = [] } = await chrome.storage.local.get("dlgate_urls");
  return dlgate_urls;
}

async function saveUrls(urls) {
  await chrome.storage.local.set({ dlgate_urls: urls });
  updateBadge(urls.length);
}

function updateBadge(count) {
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#ff5500" });
}

async function renderList() {
  const urls = await getUrls();
  const listEl = document.getElementById("list");
  const emptyEl = document.getElementById("empty");
  const countEl = document.getElementById("count");

  countEl.textContent = urls.length;

  if (urls.length === 0) {
    listEl.style.display = "none";
    emptyEl.style.display = "block";
    return;
  }

  listEl.style.display = "block";
  emptyEl.style.display = "none";

  listEl.innerHTML = urls
    .map(
      (item, i) => `
    <div class="list-item">
      <div class="list-item-info">
        <div class="list-item-title" title="${escapeHtml(item.url)}">${escapeHtml(item.title || item.url)}</div>
        <div class="list-item-artist">${escapeHtml(item.artist)}</div>
      </div>
      <span class="list-item-type">${item.type}</span>
      <button class="list-item-remove" data-index="${i}" title="Remove">&times;</button>
    </div>
  `
    )
    .join("");

  listEl.querySelectorAll(".list-item-remove").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const index = parseInt(e.target.dataset.index);
      const urls = await getUrls();
      urls.splice(index, 1);
      await saveUrls(urls);
      await renderList();
    });
  });
}

async function exportList() {
  const urls = await getUrls();
  if (urls.length === 0) return;

  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const filename = `dlgate-list-${date}.json`;
  const blob = new Blob([JSON.stringify(urls, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);

  await chrome.downloads.download({ url, filename, saveAs: true });
  URL.revokeObjectURL(url);

  // Ask to clear
  if (confirm("Export complete. Clear the list?")) {
    await saveUrls([]);
    await renderList();
  }
}

async function clearList() {
  const urls = await getUrls();
  if (urls.length === 0) return;
  if (!confirm(`Remove all ${urls.length} tracks from the list?`)) return;
  await saveUrls([]);
  await renderList();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
