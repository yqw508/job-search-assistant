const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const popupPath = path.join(__dirname, "..", "..", "extension", "popup.js");
const source = fs.readFileSync(popupPath, "utf8");

[
  'const SERVICE_URL = "http://127.0.0.1:8765"',
  'const saveButton = document.getElementById("save")',
  'const unsaveButton = document.getElementById("unsave")',
  'const dashboardButton = document.getElementById("dashboard")',
  'type: "COLLECT_BOSS_CURRENT_DETAIL"',
  "/jobs/save",
  "/jobs/unsave",
  "本地服务没有响应",
].forEach((fragment) => {
  assert.ok(source.includes(fragment), `popup.js is missing: ${fragment}`);
});

[
  "collectDetails",
  "COLLECT_BOSS_JOBS",
  "detailsInput",
].forEach((fragment) => {
  assert.ok(!source.includes(fragment), `popup.js still contains old detail flow: ${fragment}`);
});

const buttons = {};
const sandbox = {
  document: {
    getElementById(id) {
      if (!buttons[id]) {
        buttons[id] = {
          disabled: false,
          textContent: "",
          addEventListener() {},
        };
      }
      return buttons[id];
    },
  },
  chrome: {
    tabs: {
      query: async () => [],
      sendMessage: async () => ({ ok: true, job: {} }),
      create: async () => ({}),
    },
    scripting: {
      executeScript: async () => [],
    },
  },
  fetch: async () => ({ ok: true, json: async () => ({ ok: true }) }),
  module: { exports: {} },
  exports: {},
  URL: URL,
  Error: Error,
  String: String,
};

vm.runInNewContext(source, sandbox, { filename: popupPath });

assert.strictEqual(typeof sandbox.module.exports.isBossHost, "function");
assert.strictEqual(sandbox.module.exports.isBossHost("zhipin.com"), true);
assert.strictEqual(sandbox.module.exports.isBossHost("www.zhipin.com"), true);
assert.strictEqual(sandbox.module.exports.isBossHost("m.zhipin.com"), true);
assert.strictEqual(sandbox.module.exports.isBossHost("evilzhipin.com"), false);
assert.strictEqual(sandbox.module.exports.isBossHost("zhipin.com.evil.com"), false);

assert.strictEqual(sandbox.module.exports.isBossTab({ url: "https://zhipin.com/guangzhou/" }), true);
assert.strictEqual(sandbox.module.exports.isBossTab({ url: "https://www.zhipin.com/guangzhou/" }), true);
assert.strictEqual(sandbox.module.exports.isBossTab({ url: "http://www.zhipin.com/guangzhou/" }), false);
assert.strictEqual(sandbox.module.exports.isBossTab({ url: "chrome://extensions/" }), false);

assert.strictEqual(
  sandbox.module.exports.isMissingContentScriptError(
    new Error("Could not establish connection. Receiving end does not exist.")
  ),
  true
);

(async () => {
  let sendCount = 0;
  let injected = false;
  sandbox.chrome.tabs.sendMessage = async () => {
    sendCount += 1;
    if (sendCount === 1) {
      throw new Error("Could not establish connection. Receiving end does not exist.");
    }
    return { ok: true, job: { title: "Java 后端开发工程师" } };
  };
  sandbox.chrome.scripting.executeScript = async (args) => {
    injected = true;
    assert.strictEqual(args.target.tabId, 123);
    assert.deepStrictEqual(Array.from(args.files), ["content.js"]);
  };

  const result = await sandbox.module.exports.sendCurrentJobMessage({ id: 123 });
  assert.deepStrictEqual(result, { ok: true, job: { title: "Java 后端开发工程师" } });
  assert.strictEqual(sendCount, 2);
  assert.strictEqual(injected, true);

  console.log("popup_static_test passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
