<template>
  <el-empty v-if="!interviews.length" description="还没有面试记录" />
  <el-timeline v-else>
    <el-timeline-item v-for="item in interviews" :key="item.interview_id" :timestamp="item.interview_time">
      <el-card shadow="never">
        <div class="interview-head">
          <strong>{{ item.company }} · {{ item.title }} · {{ item.round_name }}</strong>
          <el-tag>{{ item.performance_score || 0 }} 分</el-tag>
        </div>
        <p>{{ item.summary || "暂无总结" }}</p>
        <div class="tag-list">
          <el-tag v-for="skill in split(item.skill_names)" :key="skill" type="success" effect="plain">{{ skill }}</el-tag>
        </div>
      </el-card>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup>
defineProps({ interviews: { type: Array, default: () => [] } });

function split(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
</script>

<style scoped>
.interview-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
</style>
