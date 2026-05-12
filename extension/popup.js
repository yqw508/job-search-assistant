const SERVICE_URL = "http://127.0.0.1:8765";

const statusEl = document.getElementById("status");
const saveButton = document.getElementById("save");
const unsaveButton = document.getElementById("unsave");
const dashboardButton = document.getElementById("dashboard");

function setStatus(text) {
  statusEl.textContent = text;
}

function setBusy(isBusy) {
  saveButton.disabled = isBusy;
  unsaveButton.disabled = isBusy;
  dashboardButton.disabled = isBusy;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function checkService() {
  const response = await fetch(`${SERVICE_URL}/health`);
  if (!response.ok) {
    throw new Error("本地服务没有响应，请先运行 start_service.bat");
  }
  return response.json();
}

function isMissingContentScriptError(error) {
  const message = String(error && error.message ? error.message : error);
  return (
    message.includes("Receiving end does not exist") ||
    message.includes("Could not establish connection")
  );
}

function isBossHost(hostname) {
  return hostname === "zhipin.com" || hostname.endsWith(".zhipin.com");
}

function isBossTab(tab) {
  if (!tab || !tab.url) return false;
  try {
    const url = new URL(tab.url);
    return url.protocol === "https:" && isBossHost(url.hostname);
  } catch (error) {
    return false;
  }
}

async function collectCurrentJob(tab) {
  return chrome.tabs.sendMessage(tab.id, {
    type: "COLLECT_BOSS_CURRENT_DETAIL",
  });
}

async function sendCurrentJobMessage(tab) {
  try {
    return await collectCurrentJob(tab);
  } catch (error) {
    if (!isMissingContentScriptError(error)) throw error;

    setStatus("正在注入页面读取脚本...");
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });

    return collectCurrentJob(tab);
  }
}

async function currentBossJob() {
  await checkService();
  const tab = await getActiveTab();
  if (!isBossTab(tab)) {
    throw new Error("请先切换到 Boss 岗位页面，并手动点开一个岗位详情");
  }

  const result = await sendCurrentJobMessage(tab);
  if (!result || !result.ok || !result.job) {
    throw new Error((result && result.error) || "没有读取到当前岗位详情");
  }
  return result.job;
}

async function saveJob(job) {
  const response = await fetch(`${SERVICE_URL}/jobs/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "boss", job }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "收藏失败");
  }
  return payload;
}

async function unsaveJob(job) {
  const response = await fetch(`${SERVICE_URL}/jobs/unsave`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "取消收藏失败");
  }
  return payload;
}

saveButton.addEventListener("click", async function () {
  setBusy(true);
  try {
    setStatus("正在读取当前岗位详情...");
    const job = await currentBossJob();
    setStatus("正在保存并计算匹配度...");
    const result = await saveJob(job);
    const saved = result.job || {};
    setStatus(
      `已收藏：${saved.title || job.title || "当前岗位"}，匹配度 ${saved.score ?? 0} 分。`
    );
  } catch (error) {
    setStatus(`失败：${error && error.message ? error.message : String(error)}`);
  } finally {
    setBusy(false);
  }
});

unsaveButton.addEventListener("click", async function () {
  setBusy(true);
  try {
    setStatus("正在读取当前岗位...");
    const job = await currentBossJob();
    await unsaveJob(job);
    setStatus(`已取消收藏：${job.title || "当前岗位"}`);
  } catch (error) {
    setStatus(`失败：${error && error.message ? error.message : String(error)}`);
  } finally {
    setBusy(false);
  }
});

dashboardButton.addEventListener("click", async function () {
  await chrome.tabs.create({ url: SERVICE_URL });
});

checkService()
  .then(function () {
    setStatus("本地服务已连接。手动打开岗位详情后即可收藏。");
  })
  .catch(function () {
    setStatus("本地服务未连接，请先运行 start_service.bat。");
  });

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    isBossHost,
    isBossTab,
    isMissingContentScriptError,
    sendCurrentJobMessage,
  };
}
