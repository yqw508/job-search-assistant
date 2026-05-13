<template>
  <el-container class="app-shell">
    <el-aside width="224px" class="sidebar">
      <div class="brand">
        <span class="brand-mark">求</span>
        <div>
          <strong>求职助手</strong>
          <small>Job Search Assistant</small>
        </div>
      </div>
      <el-menu :default-active="activeMenu" router class="side-menu">
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>首页统计</span>
        </el-menu-item>
        <el-menu-item index="/jobs">
          <el-icon><Briefcase /></el-icon>
          <span>岗位列表</span>
        </el-menu-item>
        <el-menu-item index="/skills">
          <el-icon><CollectionTag /></el-icon>
          <span>技能库</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><FolderOpened /></el-icon>
          <span>项目经验</span>
        </el-menu-item>
        <el-menu-item index="/interviews">
          <el-icon><ChatLineRound /></el-icon>
          <span>面试记录</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>匹配配置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import {
  Briefcase,
  ChatLineRound,
  CollectionTag,
  DataBoard,
  FolderOpened,
  Setting
} from "@element-plus/icons-vue";

const route = useRoute();
const activeMenu = computed(() => {
  if (route.path.startsWith("/jobs")) return "/jobs";
  if (route.path.startsWith("/skills")) return "/skills";
  if (route.path.startsWith("/projects")) return "/projects";
  if (route.path.startsWith("/interviews")) return "/interviews";
  return route.path;
});
</script>
