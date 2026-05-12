const assert = require("assert");
const fs = require("fs");
const path = require("path");

global.location = {
  origin: "https://www.zhipin.com",
  href: "https://www.zhipin.com/guangzhou/",
};

const {
  candidateCards,
  collectCurrentDetailJob,
  collectJobs,
  collectRightDetailText,
  findJobCardFromLink,
  findNextButton,
  firstSalary,
  normalizeText,
  parseJobCard,
} = require(path.join(__dirname, "..", "..", "extension", "content.js"));

class FakeElement {
  constructor(tagName, attrs, children, ownText) {
    this.tagName = tagName.toLowerCase();
    this.attrs = attrs || {};
    this.children = children || [];
    this.ownText = ownText || "";
    this.parentElement = null;
    this.dispatchCount = 0;
    this.children.forEach((child) => {
      child.parentElement = this;
    });
  }

  get textContent() {
    return [this.ownText].concat(this.children.map((child) => child.textContent)).join(" ");
  }

  get innerText() {
    return [this.ownText].concat(this.children.map((child) => child.innerText)).join("\n");
  }

  getAttribute(name) {
    return this.attrs[name] || "";
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const selectors = selector.split(",").map((part) => part.trim()).filter(Boolean);
    const matches = [];

    for (const singleSelector of selectors) {
      if (singleSelector.includes(">")) continue;
      for (const node of this.descendants()) {
        if (matchesSelectorChain(node, singleSelector, this)) {
          matches.push(node);
        }
      }
    }

    return matches.filter((node, index) => matches.indexOf(node) === index);
  }

  matches(selector) {
    return matchesSimpleSelector(this, selector);
  }

  dispatchEvent() {
    this.dispatchCount += 1;
    return true;
  }

  getBoundingClientRect() {
    return { width: 100, height: 20 };
  }

  descendants() {
    const all = [];
    const visit = (node) => {
      all.push(node);
      node.children.forEach(visit);
    };
    this.children.forEach(visit);
    return all;
  }
}

function element(tagName, attrs, children, ownText) {
  if (typeof attrs === "string") {
    return new FakeElement(tagName, {}, [], attrs);
  }
  return new FakeElement(tagName, attrs, children, ownText);
}

function matchesSelectorChain(node, selector, root) {
  const parts = selector.split(/\s+/).filter(Boolean);
  if (!matchesSimpleSelector(node, parts[parts.length - 1])) return false;

  let current = node;
  for (let index = parts.length - 2; index >= 0; index -= 1) {
    current = findAncestor(current, root, (ancestor) =>
      matchesSimpleSelector(ancestor, parts[index])
    );
    if (!current) return false;
  }

  return true;
}

function findAncestor(node, root, predicate) {
  const path = [];
  const walk = (candidate) => {
    for (const child of candidate.children) {
      if (child === node) {
        path.push(candidate);
        return true;
      }
      if (walk(child)) {
        path.push(candidate);
        return true;
      }
    }
    return false;
  };

  walk(root);
  return path.find(predicate) || null;
}

function matchesSimpleSelector(node, selector) {
  const attrContains = selector.match(/^([a-z]+)?\[([^*=\]]+)\*=['"]([^'"]+)['"]\]$/i);
  if (attrContains) {
    const tag = attrContains[1];
    const attrName = attrContains[2];
    const expected = attrContains[3];
    return (
      (!tag || node.tagName === tag.toLowerCase()) &&
      node.getAttribute(attrName).includes(expected)
    );
  }

  const attrExists = selector.match(/^([a-z]+)?\[([^*=\]]+)\]$/i);
  if (attrExists) {
    const tag = attrExists[1];
    const attrName = attrExists[2];
    return (!tag || node.tagName === tag.toLowerCase()) && Boolean(node.getAttribute(attrName));
  }

  const classContains = selector.match(/^\[class\*=['"]([^'"]+)['"]\]$/);
  if (classContains) {
    return node.getAttribute("class").includes(classContains[1]);
  }

  if (selector.startsWith(".")) {
    return node.getAttribute("class").split(/\s+/).includes(selector.slice(1));
  }

  return node.tagName === selector.toLowerCase();
}

const classicCard = element("div", { class: "job-card-wrapper" }, [
  element("a", { href: "/job_detail/example.html" }, [
    element("span", { class: "job-name" }, [], " Java 后端开发工程师 "),
  ]),
  element("span", { class: "salary" }, [], "25-35K"),
  element("span", { class: "job-area" }, [], "广州·天河"),
  element("ul", { class: "tag-list" }, [
    element("li", {}, [], "5-10年"),
    element("li", {}, [], "本科"),
  ]),
  element("span", { class: "company-name" }, [], "未来科技有限公司"),
  element("ul", { class: "company-tag-list" }, [
    element("li", {}, [], "互联网"),
    element("li", {}, [], "B轮"),
    element("li", {}, [], "100-499人"),
  ]),
]);

const job = parseJobCard(classicCard);
assert.strictEqual(job.title, "Java 后端开发工程师");
assert.strictEqual(job.salary, "25-35K");
assert.strictEqual(job.location, "广州·天河");
assert.strictEqual(job.company, "未来科技有限公司");
assert.strictEqual(job.company_size, "100-499人");
assert.strictEqual(job.url, "https://www.zhipin.com/job_detail/example.html");
assert.strictEqual(job.experience, "5-10年");
assert.strictEqual(job.education, "本科");
assert.strictEqual(job.industry, "互联网");
assert.strictEqual(job.financing, "B轮");

assert.strictEqual(firstSalary("广州 Java 22K以上 本科"), "22K以上");
assert.strictEqual(firstSalary("广州 Java 20-28K x 13薪 本科"), "20-28K x 13薪");
assert.strictEqual(normalizeText("\ue033\ue031-\ue035\ue031K"), "20-40K");
assert.strictEqual(firstSalary("高级Java\ue033\ue033-\ue034\ue036K"), "22-35K");

const parentRichCard = element("article", { class: "job-card-rich" }, [
  element("div", {}, [
    element("a", { href: "/job_detail/rich.html" }, [], "Java后端工程师22-35K"),
  ]),
  element("span", {}, [], "5-10年"),
  element("span", {}, [], "本科"),
  element("span", {}, [], "广州·天河区·棠下"),
  element("span", {}, [], "星辰软件有限公司"),
  element("span", {}, [], "100-499人"),
]);
const parentRichAnchor = parentRichCard.querySelector('a[href*="/job_detail/"]');
const parentRichCandidate = findJobCardFromLink(parentRichAnchor);
const parentRichJob = parseJobCard(parentRichCandidate);
assert.strictEqual(parentRichCandidate, parentRichCard);
assert.strictEqual(parentRichJob.salary, "22-35K");
assert.strictEqual(parentRichJob.location, "广州·天河区·棠下");
assert.strictEqual(parentRichJob.company_size, "100-499人");

const detailBlock = element(
  "section",
  { class: "job-sec-text" },
  [],
  "职位描述：\n岗位职责：\n1. 负责 C 端交易系统 Java Spring Boot 开发。YiSkaYF{display:inline-block;width:0.1px;height:0.1px;overflow:hidden;visibility:hidden;}AtAWrBQspQF{font-style:normal;font-weight:normal;}\n2. 独立完成模块设计、编码和自测。"
);
const detailRestBlock = element(
  "section",
  { class: "job-detail-section" },
  [],
  "岗位职责：\n3. 保证所负责系统的安全性、稳定性及可扩展性。\n4. 深入了解业务知识，并能敏锐发现业务痛点。\n\n任职要求：\n1. 全日制本科以上学历，5年以上 Java 开发经验。\n2. 熟练使用 Spring、Spring Boot、MyBatis 等框架。\n3. 熟练掌握 MySQL、MongoDB 等主流数据库，具备 SQL 调优能力。\n4. 掌握 JVM、缓存、消息中间件等核心技术。\n5. 有强烈技术热情和钻研精神。\n6. 具备较强业务理解及抽象能力。\n7. 能熟练利用生成式 AI 提升工作效率优先。\n最终一行：负责核心交易链路。"
  + "\n\n竞争力分析\n你的匹配度较低，建议完善简历。\n相似职位\n推荐 Java 开发岗位"
);
const detailContainer = element("aside", { class: "job-detail-card" }, [
  element("h2", {}, [], "Java后端工程师"),
  element("span", {}, [], "22-35K"),
  element("span", {}, [], "广州·天河区·棠下"),
  element("span", {}, [], "星辰软件有限公司"),
  detailBlock,
  detailRestBlock,
]);

const listingDocument = {
  querySelectorAll(selector) {
    if (selector === "a,button") {
      return [
        element("a", { href: "#" }, [], "上一页"),
        element("button", {}, [], "下一页"),
      ];
    }
    if (selector === 'a[href*="/job_detail/"]') {
      return [parentRichAnchor];
    }
    if (selector.includes("job-sec-text")) {
      return [detailBlock];
    }
    if (selector === "[class*='job-card']") {
      return [parentRichCard];
    }
    return [];
  },
  body: element("body", {}, [parentRichCard, detailContainer]),
  title: "Boss 岗位列表",
};
global.document = listingDocument;

assert.strictEqual(candidateCards().length, 1);
assert.strictEqual(findNextButton().textContent, "下一页");
assert.ok(collectRightDetailText().includes("Java Spring Boot"));
assert.ok(!collectRightDetailText().includes("display:inline-block"));
assert.ok(!collectRightDetailText().includes("font-style"));

const currentDetailJob = collectCurrentDetailJob();
assert.ok(currentDetailJob.description.includes("Java Spring Boot"));
assert.strictEqual(currentDetailJob.salary, "22-35K");
assert.strictEqual(currentDetailJob.company_size, "100-499人");
assert.ok(currentDetailJob.description.includes("4. 深入了解业务知识"));
assert.ok(currentDetailJob.description.includes("\n任职要求"));
assert.ok(currentDetailJob.description.includes("7. 能熟练利用生成式 AI"));
assert.ok(!currentDetailJob.description.includes("YiSkaYF"));
assert.ok(!currentDetailJob.description.includes("AtAWrBQspQF"));
assert.ok(currentDetailJob.description.includes("最终一行：负责核心交易链路。"));
assert.ok(!currentDetailJob.description.includes("竞争力分析"));
assert.ok(!currentDetailJob.description.includes("相似职位"));

const detailOnlyContainer = element("aside", { class: "job-detail-card" }, [
  element("h2", {}, [], "Java后端工程师"),
  element("span", {}, [], "22-35K"),
  element("span", {}, [], "广州·天河区·棠下"),
  detailBlock,
]);
global.document = {
  querySelectorAll(selector) {
    if (selector.includes("job-sec-text")) return [detailBlock];
    return [];
  },
  body: element("body", {}, [
    detailOnlyContainer,
    element("aside", { class: "company-side" }, [], "星辰软件有限公司 计算机软件 1000-9999人"),
  ]),
  title: "Boss 岗位详情",
};
assert.strictEqual(collectCurrentDetailJob().company_size, "1000-9999人");
global.document = listingDocument;

global.location.href = "https://www.zhipin.com/job_detail/standalone.html";
const standaloneHeader = element("section", { class: "job-primary" }, [
  element("h1", { class: "name" }, [], "资深开发经理"),
  element("span", { class: "salary" }, [], "20-25K"),
  element("span", {}, [], "广州"),
  element("span", {}, [], "10年以上"),
  element("span", {}, [], "本科"),
]);
const standaloneDescription = element(
  "section",
  { class: "job-detail-section" },
  [],
  "职位描述\n岗位职责：\n1. 负责政府项目整体技术架构设计、核心模块开发，主导国产操作系统、国产数据库、中间件全链条信创适配与性能调优。\n2. 以 Java 为核心技术栈，打通前后端全栈开发。\n\n任职要求：\n1. 统招本科及以上，10 年左右软件开发经验。\n2. 精通 Java 微服务体系及主流框架，熟练 Vue/React 前端技术。\n\n加分项：\n拥有政务大模型、AI Agent 落地经验。"
);
const standaloneCompany = element("aside", { class: "side-card-obfuscated" }, [
  element("div", {}, [], "公司基本信息"),
  element("div", { class: "company-logo-name" }, [], "广州长曜网络科技"),
  element("span", {}, [], "未融资"),
  element("span", {}, [], "20-99人"),
  element("span", {}, [], "计算机软件"),
]);
const standaloneHrInfo = element("section", { class: "boss-card-obfuscated" }, [
  element("span", {}, [], "冯先生"),
  element("span", {}, [], "刚刚活跃"),
  element("span", {}, [], "广州长曜网络科技 · HR"),
]);
const wrongRecommendedCompany = element("div", { class: "company-name" }, [], "数说故事人工智能");
global.document = {
  querySelectorAll(selector) {
    if (selector.includes("job-detail-section")) return [standaloneDescription];
    if (selector === ".job-primary") return [standaloneHeader];
    if (selector === ".job-primary .name") return [standaloneHeader.children[0]];
    if (selector === ".company-name") return [wrongRecommendedCompany];
    if (selector === ".company-basic-info") return [];
    if (selector.includes("aside,section,div")) return [
      standaloneHeader,
      standaloneDescription,
      wrongRecommendedCompany,
      standaloneHrInfo,
      standaloneCompany,
      standaloneCompany.children[0],
      standaloneCompany.children[1],
    ];
    if (selector.includes("[class*='company']")) return [wrongRecommendedCompany, standaloneCompany, standaloneCompany.children[1]];
    if (selector === "[class*='job-card']") return [];
    if (selector === 'a[href*="/job_detail/"]') return [];
    return [];
  },
  body: element("body", {}, [standaloneHeader, standaloneDescription, wrongRecommendedCompany, standaloneHrInfo, standaloneCompany]),
  title: "资深开发经理",
};
const standaloneJob = collectCurrentDetailJob();
assert.strictEqual(standaloneJob.title, "资深开发经理");
assert.strictEqual(standaloneJob.salary, "20-25K");
assert.strictEqual(standaloneJob.location, "广州");
assert.strictEqual(standaloneJob.experience, "10年以上");
assert.strictEqual(standaloneJob.education, "本科");
assert.strictEqual(standaloneJob.company, "广州长曜网络科技");
assert.strictEqual(standaloneJob.company_size, "20-99人");
assert.ok(standaloneJob.description.includes("加分项"));
assert.ok(standaloneJob.description.includes("AI Agent"));

global.document = {
  querySelectorAll(selector) {
    if (selector.includes("job-detail-section")) return [standaloneDescription];
    if (selector === ".job-primary") return [standaloneHeader];
    if (selector === ".job-primary .name") return [standaloneHeader.children[0]];
    if (selector === ".company-name") return [wrongRecommendedCompany];
    if (selector.includes("aside,section,div")) return [standaloneHeader, standaloneDescription, wrongRecommendedCompany, standaloneHrInfo];
    if (selector === "[class*='job-card']") return [];
    if (selector === 'a[href*="/job_detail/"]') return [];
    return [];
  },
  body: element("body", {}, [standaloneHeader, standaloneDescription, wrongRecommendedCompany, standaloneHrInfo]),
  title: "资深开发经理",
};
assert.strictEqual(collectCurrentDetailJob().company, "广州长曜网络科技");
global.location.href = "https://www.zhipin.com/guangzhou/";
global.document = listingDocument;

(async () => {
  const jobs = await collectJobs(1);
  assert.strictEqual(jobs.length, 1);
  assert.strictEqual(parentRichAnchor.dispatchCount, 0);

  const source = fs.readFileSync(path.join(__dirname, "..", "..", "extension", "content.js"), "utf8");
  [
    "triggerCardSelection",
    "dispatchSelectionEvent",
    "collectCurrentPageJobsWithDetails",
    "MouseEvent",
  ].forEach((fragment) => {
    assert.ok(!source.includes(fragment), `content.js contains risky auto-click code: ${fragment}`);
  });

  console.log("content_parser_test passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
