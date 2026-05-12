(function () {
  function normalizeText(value) {
    return (value || "").replace(/\s+/g, " ").trim();
  }

  function textOf(root, selector) {
    if (!root || !selector || typeof root.querySelector !== "function") {
      return "";
    }
    var element = root.querySelector(selector);
    return element ? normalizeText(element.textContent) : "";
  }

  function listText(root, selector) {
    if (!root || !selector || typeof root.querySelectorAll !== "function") {
      return [];
    }
    return Array.prototype.slice
      .call(root.querySelectorAll(selector))
      .map(function (element) {
        return normalizeText(element.textContent);
      })
      .filter(Boolean);
  }

  function absoluteUrl(href) {
    if (!href) {
      return "";
    }
    return new URL(href, location.origin).href;
  }

  function firstHref(root, selector) {
    if (!root || typeof root.querySelector !== "function") {
      return "";
    }
    var link = root.querySelector(selector);
    return link && typeof link.getAttribute === "function"
      ? link.getAttribute("href") || ""
      : "";
  }

  function parseJobCard(card) {
    var title = textOf(card, ".job-name,.job-title");
    var salary = textOf(card, ".salary");
    var locationText = textOf(card, ".job-area,.job-location");
    var tags = listText(card, ".tag-list li,.job-card-footer li");
    var company = textOf(card, ".company-name");
    var companyInfo = listText(card, ".company-tag-list li,.company-info li");
    var detailHref =
      firstHref(card, 'a[href*="/job_detail/"]') || firstHref(card, "a[href]");

    return {
      title: title,
      salary: salary,
      location: locationText,
      tags: tags,
      company: company,
      company_size: companyInfo.length ? companyInfo[companyInfo.length - 1] : "",
      company_info: companyInfo,
      url: absoluteUrl(detailHref),
      description: normalizeText(card && card.textContent).slice(0, 1000),
    };
  }

  function collectCurrentPageJobs() {
    var cards = Array.prototype.slice.call(
      document.querySelectorAll(".job-card-wrapper,.job-card-box")
    );
    return cards.map(parseJobCard).filter(function (job) {
      return job.title && job.company && job.url;
    });
  }

  function findNextButton() {
    var candidates = Array.prototype.slice.call(
      document.querySelectorAll("a,button")
    );
    return (
      candidates.find(function (element) {
        return /下一页|下页|next/i.test(normalizeText(element.textContent));
      }) || null
    );
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  async function collectJobs(maxPages) {
    var pageLimit = Math.max(1, Math.min(3, parseInt(maxPages, 10) || 1));
    var jobs = [];
    var seen = new Set();

    for (var page = 0; page < pageLimit; page += 1) {
      collectCurrentPageJobs().forEach(function (job) {
        var key = job.url || [job.title, job.company, job.salary].join("|");
        if (!seen.has(key)) {
          seen.add(key);
          jobs.push(job);
        }
      });

      if (page >= pageLimit - 1) {
        break;
      }

      var nextButton = findNextButton();
      if (!nextButton || typeof nextButton.click !== "function") {
        break;
      }

      nextButton.click();
      await sleep(2500);
    }

    return jobs;
  }

  if (
    typeof chrome !== "undefined" &&
    chrome.runtime &&
    chrome.runtime.onMessage
  ) {
    chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
      if (!message || message.type !== "COLLECT_BOSS_JOBS") {
        return false;
      }

      collectJobs(message.maxPages)
        .then(function (jobs) {
          sendResponse({ ok: true, jobs: jobs });
        })
        .catch(function (error) {
          sendResponse({
            ok: false,
            error: error && error.message ? error.message : String(error),
          });
        });

      return true;
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      textOf: textOf,
      listText: listText,
      absoluteUrl: absoluteUrl,
      parseJobCard: parseJobCard,
      collectCurrentPageJobs: collectCurrentPageJobs,
      findNextButton: findNextButton,
      sleep: sleep,
      collectJobs: collectJobs,
      normalizeText: normalizeText,
    };
  }
})();
