const assert = require("assert");
const path = require("path");

global.location = { origin: "https://www.zhipin.com" };

const { parseJobCard } = require(path.join(
  __dirname,
  "..",
  "..",
  "extension",
  "content.js"
));

class FakeElement {
  constructor(tagName, attrs, children, ownText) {
    this.tagName = tagName.toLowerCase();
    this.attrs = attrs || {};
    this.children = children || [];
    this.ownText = ownText || "";
  }

  get textContent() {
    return [this.ownText]
      .concat(this.children.map((child) => child.textContent))
      .join(" ");
  }

  getAttribute(name) {
    return this.attrs[name] || "";
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const selectors = selector
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    const matches = [];

    for (const singleSelector of selectors) {
      for (const node of this.descendants()) {
        if (matchesSelectorChain(node, singleSelector, this)) {
          matches.push(node);
        }
      }
    }

    return matches.filter((node, index) => matches.indexOf(node) === index);
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
  if (!matchesSimpleSelector(node, parts[parts.length - 1])) {
    return false;
  }

  let current = node;
  for (let index = parts.length - 2; index >= 0; index -= 1) {
    current = findAncestor(current, root, (ancestor) =>
      matchesSimpleSelector(ancestor, parts[index])
    );
    if (!current) {
      return false;
    }
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
  const attrContains = selector.match(/^([a-z]+)?\[([^*=\]]+)\*="([^"]+)"\]$/i);
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
    return (
      (!tag || node.tagName === tag.toLowerCase()) && Boolean(node.getAttribute(attrName))
    );
  }

  if (selector.startsWith(".")) {
    return node
      .getAttribute("class")
      .split(/\s+/)
      .includes(selector.slice(1));
  }

  return node.tagName === selector.toLowerCase();
}

const card = element("div", { class: "job-card-wrapper" }, [
  element("a", { href: "/job_detail/example.html" }, [
    element("span", { class: "job-name" }, [], " Java   后端开发工程师 "),
  ]),
  element("span", { class: "salary" }, [], "25-35K"),
  element("span", { class: "job-area" }, [], "广州"),
  element("ul", { class: "tag-list" }, [
    element("li", {}, [], "Java"),
    element("li", {}, [], "Spring Boot"),
  ]),
  element("span", { class: "company-name" }, [], " 示例公司 "),
  element("ul", { class: "company-tag-list" }, [
    element("li", {}, [], "互联网"),
    element("li", {}, [], "100-499人"),
  ]),
]);

const job = parseJobCard(card);

assert.strictEqual(job.title, "Java 后端开发工程师");
assert.strictEqual(job.salary, "25-35K");
assert.strictEqual(job.location, "广州");
assert.strictEqual(job.company, "示例公司");
assert.strictEqual(job.company_size, "100-499人");
assert.strictEqual(job.url, "https://www.zhipin.com/job_detail/example.html");
assert.deepStrictEqual(job.tags, ["Java", "Spring Boot"]);
assert.deepStrictEqual(job.company_info, ["互联网", "100-499人"]);
assert.ok(job.description.includes("Java 后端开发工程师"));

console.log("content_parser_test passed");
