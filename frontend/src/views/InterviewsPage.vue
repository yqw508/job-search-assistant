<template>
  <section>
    <div class="page-header">
      <div>
        <h1>面试记录</h1>
        <div class="page-subtitle">统计高频问题和薄弱技能，形成补齐清单。</div>
      </div>
      <el-tag type="info">{{ interviews.length }} 条记录</el-tag>
    </div>

    <el-row v-loading="loading" :gutter="16">
      <el-col :lg="10" :xs="24">
        <el-card class="section-card" shadow="never">
          <template #header>高频/薄弱技能</template>
          <el-empty v-if="!skillStats.length" description="暂无技能统计" />
          <el-table v-else :data="skillStats" border>
            <el-table-column prop="skill_name" label="技能" />
            <el-table-column prop="question_count" label="问题数" width="90" />
            <el-table-column prop="low_score_count" label="低分" width="80" />
            <el-table-column prop="average_score" label="均分" width="80" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :lg="14" :xs="24">
        <el-card class="section-card" shadow="never">
          <template #header>面试时间线</template>
          <InterviewList :interviews="interviews" />
        </el-card>
      </el-col>
    </el-row>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { getInterviews } from "../api";
import InterviewList from "../components/InterviewList.vue";

const loading = ref(false);
const interviews = ref([]);
const skillStats = ref([]);

onMounted(async () => {
  loading.value = true;
  try {
    const data = await getInterviews();
    interviews.value = data.interviews || [];
    skillStats.value = data.skill_stats || [];
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
});
</script>
