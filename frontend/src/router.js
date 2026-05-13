import { createRouter, createWebHistory } from "vue-router";

import DashboardPage from "./views/DashboardPage.vue";
import InterviewsPage from "./views/InterviewsPage.vue";
import JobDetailPage from "./views/JobDetailPage.vue";
import JobsPage from "./views/JobsPage.vue";
import ProjectsPage from "./views/ProjectsPage.vue";
import SettingsPage from "./views/SettingsPage.vue";
import SkillsPage from "./views/SkillsPage.vue";

const routes = [
  { path: "/", name: "dashboard", component: DashboardPage },
  { path: "/jobs", name: "jobs", component: JobsPage },
  { path: "/jobs/detail", name: "job-detail", component: JobDetailPage },
  { path: "/skills", name: "skills", component: SkillsPage },
  { path: "/projects", name: "projects", component: ProjectsPage },
  { path: "/interviews", name: "interviews", component: InterviewsPage },
  { path: "/settings", name: "settings", component: SettingsPage }
];

export default createRouter({
  history: createWebHistory(),
  routes
});
