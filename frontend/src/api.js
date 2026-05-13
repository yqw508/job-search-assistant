async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });

  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { ok: false, error: text };
    }
  }

  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `请求失败：${response.status}`);
  }
  return data;
}

export function getDashboard() {
  return request("/api/dashboard");
}

export function getJobs() {
  return request("/api/jobs");
}

export function getJobDetail(jobKey) {
  return request(`/api/jobs/detail?job_key=${encodeURIComponent(jobKey)}`);
}

export function updateJobStatus(payload) {
  return request("/api/jobs/status", { method: "POST", body: JSON.stringify(payload) });
}

export function getSkills() {
  return request("/api/skills");
}

export function getSkillDetail(name) {
  return request(`/api/skills/detail?name=${encodeURIComponent(name)}`);
}

export function saveSkillProfile(payload) {
  return request("/api/skills/profile", { method: "POST", body: JSON.stringify(payload) });
}

export function getProjects() {
  return request("/api/projects");
}

export function createProject(payload) {
  return request("/api/projects", { method: "POST", body: JSON.stringify(payload) });
}

export function getInterviews() {
  return request("/api/interviews");
}

export function createInterview(payload) {
  return request("/api/interviews", { method: "POST", body: JSON.stringify(payload) });
}

export function getSettings() {
  return request("/api/settings");
}

export function updateSettings(payload) {
  return request("/api/settings", { method: "POST", body: JSON.stringify(payload) });
}
