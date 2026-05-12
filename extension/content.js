(function () {
  const BOSS_PRIVATE_DIGITS = {
    "\ue031": "0",
    "\ue032": "1",
    "\ue033": "2",
    "\ue034": "3",
    "\ue035": "4",
    "\ue036": "5",
    "\ue037": "6",
    "\ue038": "7",
    "\ue039": "8",
    "\ue030": "9",
  };

  const SALARY_PATTERN =
    /(?:\d+(?:\.\d+)?\s*[Kk]\s*[-~—–]\s*\d+(?:\.\d+)?\s*[Kk]|\d+(?:\.\d+)?\s*[-~—–]\s*\d+(?:\.\d+)?\s*[Kk]|\d+(?:\.\d+)?\s*(?:\u4e07|[wW])?\s*[-~—–]\s*\d+(?:\.\d+)?\s*(?:\u4e07|[wW])|\d+(?:\.\d+)?\s*[Kk]\s*(?:\u4ee5\u4e0a)?|\d+(?:\.\d+)?\s*(?:\u4e07|[wW])\s*(?:\u4ee5\u4e0a)?)(?:\s*[·xX×/]\s*\d+\s*\u85aa)?/u;
  const LOCATION_PATTERN =
    /(?:广州|深圳|惠州|佛山|东莞|珠海|中山)(?:[·\-—–][\u4e00-\u9fa5A-Za-z0-9]+){0,2}/u;
  const DETAIL_MARKER_PATTERN =
    /职位描述|岗位职责|任职要求|工作内容|岗位要求|职位详情|岗位描述|工作职责/;
  const DETAIL_SELECTOR =
    ".job-sec-text,.job-detail-section,.job-detail-body,.job-detail-content,.job-detail-box,.job-detail-card,.detail-content,[class*='job-sec'],[class*='detail'],[class*='Detail']";
  const DETAIL_STOP_SECTION_PATTERN =
    /(?:^|\n|\s)(竞争力分析|相似职位|推荐职位|看过该职位的人还看了|公司介绍|工商信息|工作地址|职位发布者|BOSS直聘温馨提示|求职安全提示)(?:\s|[:：]|$)/;

  function normalizeBossDigits(value) {
    return String(value || "").replace(/[\ue030-\ue039]/g, (char) => {
      return BOSS_PRIVATE_DIGITS[char] || char;
    });
  }

  function normalizeText(value) {
    return normalizeBossDigits(value).replace(/\s+/g, " ").trim();
  }

  function normalizeDetailText(value) {
    const normalized = normalizeBossDigits(value)
      .replace(/[A-Za-z0-9_-]{2,}\{[^{}]*(?:display|visibility|width|height|font-size|font-style|font-weight|line-height|overflow)[^{}]*\}/g, "")
      .replace(/\{[^{}]*(?:display|visibility|width|height|font-size|font-style|font-weight|line-height|overflow)[^{}]*\}/g, "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .replace(/[ \t\f\v]+/g, " ")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    return trimNonJobDetailSections(normalized);
  }

  function trimNonJobDetailSections(text) {
    const normalized = String(text || "");
    const match = normalized.match(DETAIL_STOP_SECTION_PATTERN);
    return match && typeof match.index === "number"
      ? normalized.slice(0, match.index).trim()
      : normalized;
  }

  function textOf(root, selector) {
    if (!root || !selector || typeof root.querySelector !== "function") return "";
    const element = root.querySelector(selector);
    return element ? normalizeText(element.textContent) : "";
  }

  function listText(root, selector) {
    if (!root || !selector || typeof root.querySelectorAll !== "function") return [];
    return Array.from(root.querySelectorAll(selector))
      .map((element) => normalizeText(element.textContent))
      .filter(Boolean);
  }

  function absoluteUrl(href) {
    if (!href) return "";
    try {
      return new URL(href, location.origin).href;
    } catch (error) {
      return "";
    }
  }

  function firstHref(root, selector) {
    if (!root || typeof root.querySelector !== "function") return "";
    const link = root.querySelector(selector);
    return link && typeof link.getAttribute === "function"
      ? link.getAttribute("href") || ""
      : "";
  }

  function selfOrFirstHref(root, selector) {
    if (!root) return "";
    if (
      typeof root.matches === "function" &&
      root.matches(selector) &&
      typeof root.getAttribute === "function"
    ) {
      return root.getAttribute("href") || "";
    }
    return firstHref(root, selector);
  }

  function firstSalary(text) {
    const match = normalizeText(text).match(SALARY_PATTERN);
    return match ? normalizeText(match[0]) : "";
  }

  function inferSalary(card) {
    const explicit = textOf(
      card,
      ".salary,.job-salary,[class*='salary'],[class*='Salary'],[class*='wage'],[class*='pay']"
    );
    return firstSalary(explicit) || firstSalary(card && card.textContent);
  }

  function inferTitle(card) {
    const salary = inferSalary(card);
    const rawTitle =
      textOf(card, ".job-name,.job-title,.job-card-left .name,.job-card-body .name") ||
      textOf(card, "a[href*='/job_detail/']") ||
      normalizeText(card && card.textContent).split(/\s{2,}| {2,}/)[0];
    return normalizeText(rawTitle.replace(salary, ""));
  }

  function inferCompany(card) {
    const explicit = textOf(card, ".company-name,.boss-name,.company");
    if (explicit) return explicit;

    const match = normalizeText(card && card.textContent).match(
      /[\u4e00-\u9fa5A-Za-z0-9（）()·&.\-]{2,40}(?:科技|网络|信息|软件|智能|集团|公司|有限公司)/
    );
    return match ? match[0] : "";
  }

  function cleanCompanyNameText(text) {
    const normalized = normalizeText(text)
      .replace(/公司基本信息/g, " ")
      .replace(/查看全部职位/g, " ");
    const suffixMatch = normalized.match(
      /[\u4e00-\u9fa5A-Za-z0-9（）()·&.\-]{2,40}(?:科技|网络|信息|软件|智能|集团|公司|有限公司)/
    );
    if (suffixMatch) return suffixMatch[0];

    const excluded = /融资|未融资|不需要融资|人$|计算机软件|互联网|移动互联网|电子商务|企业服务|游戏|查看|职位|基本信息/;
    return (
      normalized
        .split(/\s+|[|｜,，、]/)
        .map((item) => item.trim())
        .find((item) => item.length >= 2 && item.length <= 30 && !excluded.test(item)) || ""
    );
  }

  function inferLocation(card) {
    const explicit = listText(
      card,
      ".job-area,.job-location,.location,[class*='area'],[class*='Area'],[class*='location'],[class*='Location'],[class*='addr'],[class*='Addr']"
    ).find((text) => LOCATION_PATTERN.test(text));
    if (explicit) {
      const match = explicit.match(LOCATION_PATTERN);
      return match ? normalizeText(match[0]) : explicit;
    }

    const match = normalizeText(card && card.textContent).match(LOCATION_PATTERN);
    return match ? match[0] : "";
  }

  function inferExperience(text, tags) {
    const pattern = /经验不限|在校|应届|\d+\s*-\s*\d+\s*年|\d+\s*年以?上?/;
    const tagged = (tags || []).find((item) => pattern.test(item));
    if (tagged) return tagged;
    const match = normalizeText(text).match(pattern);
    return match ? match[0] : "";
  }

  function inferEducation(text, tags) {
    const pattern = /博士|硕士|本科|大专|中专|高中|学历不限/;
    const tagged = (tags || []).find((item) => pattern.test(item));
    if (tagged) return tagged;
    const match = normalizeText(text).match(pattern);
    return match ? match[0] : "";
  }

  function inferCompanySize(text, companyInfo) {
    const pattern = /\d+\s*-\s*\d+\s*人|\d+\s*人以上|少于\s*\d+\s*人/;
    const tagged = (companyInfo || []).find((item) => pattern.test(item));
    if (tagged) return tagged;
    const match = normalizeText(text).match(pattern);
    return match ? match[0] : "";
  }

  function inferCompanySizeFromPage() {
    return inferCompanySize(document.body && document.body.textContent, []);
  }

  function firstTextFromPage(selectors) {
    for (const selector of selectors) {
      let text = textOf(document, selector);
      if (!text && document && typeof document.querySelectorAll === "function") {
        const element = document.querySelectorAll(selector)[0];
        text = element ? normalizeText(element.textContent) : "";
      }
      if (text) return text;
    }
    return "";
  }

  function companyNameFromPage() {
    const panels = Array.from(
      document.querySelectorAll(
        ".company-basic-info,.company-card,.sider-company,.company-info,[class*='company'],aside,section,div"
      )
    )
      .map((panel) => {
        const text = normalizeText(panel.textContent);
        let score = 0;
        if (/公司基本信息/.test(text)) score += 10;
        if (/HR|招聘者|招聘人|先生|女士/.test(text)) score += 8;
        if (/\d+\s*-\s*\d+\s*人|\d+\s*人以上|少于\s*\d+\s*人/.test(text)) score += 5;
        if (/融资|未融资|不需要融资/.test(text)) score += 3;
        if (/计算机软件|互联网|移动互联网|电子商务|企业服务|游戏/.test(text)) score += 3;
        if (/职位描述|岗位职责|任职要求/.test(text)) score -= 20;
        if (text.length > 1000) score -= 10;
        return { panel, text, score };
      })
      .sort((a, b) => b.score - a.score || a.text.length - b.text.length);

    for (const { panel, text, score } of panels) {
      if (score <= 0) continue;
      const direct = textOf(
        panel,
        ".company-name,.company-logo-name,.name,h3,[class*='company-name'],[class*='companyName']"
      );
      const cleanedDirect = cleanCompanyNameText(direct);
      if (cleanedDirect) return cleanedDirect;
      const cleaned = cleanCompanyNameText(text);
      if (cleaned) return cleaned;
    }

    const direct = firstTextFromPage([
      ".company-basic-info h3",
      ".company-card h3",
      ".sider-company .name",
      ".company-info .name",
      ".job-company",
    ]);
    const cleanedDirect = cleanCompanyNameText(direct);
    if (cleanedDirect) return cleanedDirect;

    return "";
  }

  function parseJobCard(card) {
    const tags = listText(card, ".tag-list li,.job-card-footer li,.job-tags span,.job-tags li");
    const companyInfo = listText(
      card,
      ".company-tag-list li,.company-info li,.company-tags span,.company-tags li"
    );
    const detailHref =
      selfOrFirstHref(card, 'a[href*="/job_detail/"]') ||
      selfOrFirstHref(card, "a[href]");
    const fullText = normalizeText(card && card.textContent);

    return {
      title: inferTitle(card),
      salary: inferSalary(card),
      location: inferLocation(card),
      experience: inferExperience(fullText, tags),
      education: inferEducation(fullText, tags),
      company: inferCompany(card),
      industry: companyInfo[0] || "",
      financing: companyInfo[1] || "",
      company_size: inferCompanySize(fullText, companyInfo),
      source: "boss",
      source_url: absoluteUrl(detailHref),
      url: absoluteUrl(detailHref),
      description: fullText.slice(0, 1000),
    };
  }

  function looksLikeJobText(text) {
    return (
      text.length >= 12 &&
      Boolean(firstSalary(text)) &&
      /Java|后端|开发|工程师|架构|Spring|Spring Boot|服务端|客户端/.test(text)
    );
  }

  function jobCardCompletenessScore(element) {
    if (!element) return -1;
    const text = normalizeText(element.textContent);
    if (!text || text.length > 20000) return -1;

    let score = 0;
    if (selfOrFirstHref(element, 'a[href*="/job_detail/"]')) score += 3;
    if (firstSalary(text)) score += 4;
    if (LOCATION_PATTERN.test(text)) score += 4;
    if (/经验不限|在校|应届|\d+\s*-\s*\d+\s*年|\d+\s*年以?上?/.test(text)) score += 2;
    if (/博士|硕士|本科|大专|中专|高中|学历不限/.test(text)) score += 2;
    if (/(?:科技|网络|信息|软件|智能|集团|公司|有限公司|电商|游戏)/.test(text)) score += 2;
    if (/\d+\s*-\s*\d+\s*人|\d+\s*人以上|少于\s*\d+\s*人/.test(text)) score += 1;
    if (text.length >= 30 && text.length <= 800) score += 2;
    if (text.length < 12) score -= 4;
    return score;
  }

  function findJobCardFromLink(link) {
    let current = link;
    let best = link;
    let bestScore = jobCardCompletenessScore(link);

    for (let depth = 0; current && depth < 8; depth += 1) {
      const score = jobCardCompletenessScore(current);
      if (score > bestScore) {
        best = current;
        bestScore = score;
      }
      current = current.parentElement;
    }

    return best;
  }

  function addCandidate(cards, seen, element) {
    if (!element || seen.has(element)) return;
    const text = normalizeText(element.textContent);
    const href = selfOrFirstHref(element, 'a[href*="/job_detail/"]');
    if ((href || looksLikeJobText(text)) && text.length >= 2) {
      seen.add(element);
      cards.push(element);
    }
  }

  function candidateCards() {
    const selectors = [
      ".job-card-wrapper",
      ".job-card-box",
      ".job-list-box",
      "[class*='job-card']",
      "[class*='jobCard']",
      "li",
      ".rec-job-list > div",
      ".job-list > div",
    ];
    const cards = [];
    const seen = new Set();

    document.querySelectorAll('a[href*="/job_detail/"]').forEach((link) => {
      addCandidate(cards, seen, findJobCardFromLink(link));
    });

    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((element) => {
        addCandidate(cards, seen, element);
      });
    });

    return cards;
  }

  function collectCurrentPageJobs() {
    return candidateCards()
      .map(parseJobCard)
      .filter((job) => job.title && (job.company || job.salary || job.url));
  }

  function visibleTextOf(element) {
    if (!element) return "";
    if (typeof element.getBoundingClientRect === "function") {
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return "";
    }
    return normalizeText(element.textContent);
  }

  function visibleDetailTextOf(element) {
    if (!element) return "";
    if (typeof element.getBoundingClientRect === "function") {
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return "";
    }
    const text =
      typeof element.innerText === "string" && element.innerText
        ? element.innerText
        : element.textContent;
    return normalizeDetailText(text);
  }

  function detailCompletenessScore(text) {
    const normalized = normalizeDetailText(text);
    if (!normalized || normalized.length < 20 || normalized.length > 30000) return -1;

    let score = 0;
    if (DETAIL_MARKER_PATTERN.test(normalized)) score += 8;
    if (/岗位职责|工作职责|工作内容|职位描述/.test(normalized)) score += 8;
    if (/任职要求|岗位要求/.test(normalized)) score += 10;
    if (/Java|Spring|Spring Boot|MySQL|Redis|Kafka|MQ/i.test(normalized)) score += 4;

    const numberedItems = normalized.match(/(?:^|\n)\s*(?:\d+[\.\、]|[一二三四五六七八九十]+[、.])/g) || [];
    score += Math.min(numberedItems.length, 12) * 2;

    const lineCount = normalized.split("\n").filter((line) => line.trim()).length;
    score += Math.min(lineCount, 20);

    if (normalized.length >= 120) score += 6;
    if (normalized.length >= 400) score += 6;
    if (normalized.length >= 1000) score += 4;

    return score;
  }

  function collectRightDetail() {
    const detailBlocks = Array.from(document.querySelectorAll(DETAIL_SELECTOR))
      .map((element) => {
        const text = visibleDetailTextOf(element);
        return { element, text, score: detailCompletenessScore(text) };
      })
      .filter((item) => {
        return (
          item.text.length >= 20 &&
          item.text.length <= 20000 &&
          item.score >= 0 &&
          DETAIL_MARKER_PATTERN.test(item.text)
        );
      });

    if (detailBlocks.length > 0) {
      return detailBlocks.sort((a, b) => b.score - a.score || b.text.length - a.text.length)[0];
    }

    const bodyText = visibleDetailTextOf(document.body);
    const marker = bodyText.search(DETAIL_MARKER_PATTERN);
    if (marker >= 0) {
      return { element: document.body, text: bodyText.slice(marker, marker + 12000) };
    }

    return { element: null, text: "" };
  }

  function collectRightDetailText() {
    return collectRightDetail().text;
  }

  function stripSalaryFromTitle(title) {
    const salary = firstSalary(title);
    return normalizeText(String(title || "").replace(salary, ""));
  }

  function findJobForDetail(detailText) {
    const jobs = collectCurrentPageJobs();
    return (
      jobs.find((job) => {
        const title = stripSalaryFromTitle(job.title);
        return title && title.length >= 2 && detailText.includes(title);
      }) ||
      jobs.find((job) => {
        return job.company && job.company.length >= 2 && detailText.includes(job.company);
      }) ||
      null
    );
  }

  function findDetailContextElement(detailElement) {
    let current = detailElement;
    let best = detailElement;
    let bestScore = detailCompletenessScore(visibleDetailTextOf(detailElement));

    for (let depth = 0; current && depth < 6; depth += 1) {
      const text = visibleDetailTextOf(current);
      if (text.length > 0 && text.length <= 20000 && DETAIL_MARKER_PATTERN.test(text)) {
        const score = detailCompletenessScore(text);
        if (score > bestScore) {
          best = current;
          bestScore = score;
        }
      }
      current = current.parentElement;
    }

    return best;
  }

  function bestDescriptionText(detail) {
    const candidates = [];
    if (detail && detail.text) {
      candidates.push({ text: detail.text, score: detailCompletenessScore(detail.text) });
    }

    let current = detail && detail.element && detail.element !== document.body
      ? detail.element
      : null;
    for (let depth = 0; current && depth < 6; depth += 1) {
      const text = visibleDetailTextOf(current);
      const score = detailCompletenessScore(text);
      if (score >= 0 && DETAIL_MARKER_PATTERN.test(text)) {
        candidates.push({ text, score });
      }
      current = current.parentElement;
    }

    const best = candidates.sort((a, b) => b.score - a.score || b.text.length - a.text.length)[0];
    return best ? best.text : "";
  }

  function collectStandaloneDetailJob(detail, description) {
    const bodyText = normalizeText(document.body && document.body.textContent);
    const titleText = firstTextFromPage([
      ".job-title",
      ".job-name",
      ".job-primary .name",
      ".job-banner h1",
      ".info-primary h1",
      ".job-detail-header h1",
      ".job-detail-container h1",
      "h1",
    ]);
    const headerText = firstTextFromPage([
      ".job-primary",
      ".job-banner",
      ".info-primary",
      ".job-detail-header",
      ".job-detail-container",
    ]);
    const companyText = companyNameFromPage();
    const metadataText = normalizeText([titleText, companyText, bodyText].join(" "));
    const sourceText = normalizeText([
      titleText,
      headerText,
      detail && detail.element ? detail.element.textContent : "",
      description,
      bodyText.slice(0, 3000),
    ].join(" "));

    return {
      title: stripSalaryFromTitle(titleText) || "",
      salary: firstSalary(titleText) || firstSalary(sourceText),
      location: inferLocation(document.body),
      experience: inferExperience(sourceText, []),
      education: inferEducation(sourceText, []),
      company: companyText || inferCompany(document.body),
      industry: "",
      financing: "",
      company_size: inferCompanySize(metadataText, []),
      source: "boss",
      source_url: location.href,
      url: location.href,
    };
  }

  function isLikelyBadDetailTitle(title) {
    const normalized = normalizeText(title);
    return (
      !normalized ||
      normalized.length > 80 ||
      DETAIL_MARKER_PATTERN.test(normalized) ||
      /任职要求|岗位职责|工作职责|工作内容/.test(normalized)
    );
  }

  function collectCurrentDetailJob() {
    const detail = collectRightDetail();
    if (!detail.text) return null;

    const detailContext =
      detail.element && detail.element !== document.body
        ? findDetailContextElement(detail.element)
        : null;
    const detailMatchText = normalizeText(
      [detailContext ? detailContext.textContent : "", detail.text].join(" ")
    );
    const matchedJob = findJobForDetail(detailMatchText);
    const detailJob = detailContext ? parseJobCard(detailContext) : {};
    const job = {
      ...detailJob,
      ...Object.fromEntries(
        Object.entries(matchedJob || {}).filter((entry) => Boolean(entry[1]))
      ),
    };
    const description = bestDescriptionText(detail) || detail.text;
    const standaloneJob = collectStandaloneDetailJob(detail, description);
    const standaloneDetailPage = /\/job_detail\//.test(location.href);
    if (isLikelyBadDetailTitle(job.title)) {
      job.title = "";
    }

    return {
      title: (standaloneDetailPage ? standaloneJob.title : job.title) || job.title || standaloneJob.title || "当前职位详情",
      salary: (standaloneDetailPage ? standaloneJob.salary : job.salary) || job.salary || standaloneJob.salary || "",
      location: (standaloneDetailPage ? standaloneJob.location : job.location) || job.location || standaloneJob.location || "",
      experience: (standaloneDetailPage ? standaloneJob.experience : job.experience) || job.experience || standaloneJob.experience || "",
      education: (standaloneDetailPage ? standaloneJob.education : job.education) || job.education || standaloneJob.education || "",
      company: (standaloneDetailPage ? standaloneJob.company : job.company) || job.company || standaloneJob.company || "",
      industry: (standaloneDetailPage ? standaloneJob.industry : job.industry) || job.industry || standaloneJob.industry || "",
      financing: (standaloneDetailPage ? standaloneJob.financing : job.financing) || job.financing || standaloneJob.financing || "",
      company_size: (standaloneDetailPage ? standaloneJob.company_size : job.company_size) || job.company_size || standaloneJob.company_size || inferCompanySizeFromPage(),
      source: "boss",
      source_url: (standaloneDetailPage ? standaloneJob.source_url : job.source_url) || job.source_url || standaloneJob.source_url || location.href,
      url: (standaloneDetailPage ? standaloneJob.url : job.url) || job.url || standaloneJob.url || location.href,
      description: description.slice(0, 12000),
    };
  }

  function jobKey(job) {
    return job.url || [job.title, job.company, job.salary].join("|");
  }

  function pageSignature() {
    return collectCurrentPageJobs().slice(0, 8).map(jobKey).join("||");
  }

  function findNextButton() {
    return (
      Array.from(document.querySelectorAll("a,button")).find((element) =>
        /下一页|下页|next/i.test(normalizeText(element.textContent))
      ) || null
    );
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function waitForPageSignatureChange(previousSignature) {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await sleep(300);
      const nextSignature = pageSignature();
      if (nextSignature && nextSignature !== previousSignature) return true;
    }
    return false;
  }

  async function collectJobs(maxPages) {
    const pageLimit = Math.max(1, Math.min(3, parseInt(maxPages, 10) || 1));
    const jobs = [];
    const seen = new Set();
    const seenPageSignatures = new Set();

    for (let page = 0; page < pageLimit; page += 1) {
      const currentSignature = pageSignature();
      if (currentSignature && seenPageSignatures.has(currentSignature)) break;
      if (currentSignature) seenPageSignatures.add(currentSignature);

      collectCurrentPageJobs().forEach((job) => {
        const key = jobKey(job);
        if (!seen.has(key)) {
          seen.add(key);
          jobs.push(job);
        }
      });

      if (page >= pageLimit - 1) break;
      const nextButton = findNextButton();
      if (!nextButton || typeof nextButton.click !== "function") break;

      nextButton.click();
      const changed = await waitForPageSignatureChange(currentSignature);
      if (!changed) break;
    }

    return jobs;
  }

  function collectDebugInfo() {
    const bodyText = normalizeText(document.body && document.body.textContent);
    return {
      url: location.href,
      title: document.title || "",
      jobLinks: document.querySelectorAll('a[href*="/job_detail/"]').length,
      salaryTexts: (bodyText.match(new RegExp(SALARY_PATTERN.source, "gu")) || []).length,
      candidates: candidateCards().length,
      bodyTextLength: bodyText.length,
      selectedDetailLength: collectRightDetailText().length,
      hasVisibleDetail: Boolean(collectRightDetailText()),
    };
  }

  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (!message) return false;

      if (message.type === "COLLECT_BOSS_CURRENT_DETAIL") {
        const job = collectCurrentDetailJob();
        sendResponse({
          ok: Boolean(job),
          job,
          error: job ? "" : "没有读取到当前右侧职位描述，请先手动点开一个岗位详情。",
          debug: collectDebugInfo(),
        });
        return false;
      }

      if (message.type !== "COLLECT_BOSS_JOBS") return false;

      collectJobs(message.maxPages)
        .then((jobs) => sendResponse({ ok: true, jobs, debug: collectDebugInfo() }))
        .catch((error) =>
          sendResponse({
            ok: false,
            error: error && error.message ? error.message : String(error),
            debug: collectDebugInfo(),
          })
        );

      return true;
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      textOf,
      listText,
      absoluteUrl,
      parseJobCard,
      collectCurrentPageJobs,
      findNextButton,
      sleep,
      collectJobs,
      normalizeText,
      candidateCards,
      firstSalary,
      collectDebugInfo,
      findJobCardFromLink,
      collectRightDetailText,
      collectCurrentDetailJob,
      pageSignature,
      waitForPageSignatureChange,
    };
  }
})();
