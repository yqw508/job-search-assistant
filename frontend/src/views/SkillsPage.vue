<template>
  <section>
    <div class="page-header">
      <div>
        <h1>技能库</h1>
        <div class="page-subtitle">从岗位描述、面试问题和项目经验中沉淀技能点。</div>
      </div>
      <el-tag type="info">{{ filteredSkills.length }} 个技能点</el-tag>
    </div>

    <div class="toolbar">
      <el-input v-model="keyword" clearable placeholder="搜索技能或分类" style="width: 280px" />
    </div>

    <div v-loading="loading">
      <el-empty v-if="!loading && !filteredSkills.length" description="暂无技能点" />
      <el-row v-else :gutter="14">
        <el-col v-for="skill in filteredSkills" :key="skill.name" :lg="8" :md="12" :xs="24">
          <el-card class="skill-card" shadow="never" @click="openSkill(skill)">
            <div class="skill-head">
              <strong>{{ skill.name }}</strong>
              <el-tag>{{ skill.category || "未分类" }}</el-tag>
            </div>
            <el-progress :percentage="Number(skill.mastery_score || 0)" />
            <p class="muted">{{ skill.notes || "还没有补充掌握程度和学习计划" }}</p>
            <div class="tag-list">
              <el-tag effect="plain">岗位 {{ skill.job_count || 0 }}</el-tag>
              <el-tag effect="plain">提及 {{ skill.mention_count || 0 }}</el-tag>
              <el-tag effect="plain">项目 {{ skill.project_count || 0 }}</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="dialogVisible" :title="selectedSkill?.name || '技能详情'" width="760px">
      <template v-if="selectedSkill">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="分类">{{ selectedSkill.category || "未分类" }}</el-descriptions-item>
          <el-descriptions-item label="掌握程度">{{ selectedSkill.mastery_level || "未填写" }}</el-descriptions-item>
          <el-descriptions-item label="掌握分">{{ selectedSkill.mastery_score || 0 }}</el-descriptions-item>
          <el-descriptions-item label="岗位提及">{{ selectedSkill.job_count || 0 }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <p class="description">{{ selectedSkill.notes || "暂无备注" }}</p>
        <el-divider>关联岗位</el-divider>
        <el-table :data="selectedSkill.jobs || []" size="small">
          <el-table-column prop="title" label="岗位" />
          <el-table-column prop="company" label="公司" />
          <el-table-column prop="importance" label="重要度" width="90" />
        </el-table>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { getSkillDetail, getSkills } from "../api";

const loading = ref(false);
const skills = ref([]);
const keyword = ref("");
const dialogVisible = ref(false);
const selectedSkill = ref(null);

const filteredSkills = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  if (!text) return skills.value;
  return skills.value.filter((skill) => [skill.name, skill.category].join(" ").toLowerCase().includes(text));
});

async function openSkill(skill) {
  try {
    const data = await getSkillDetail(skill.name);
    selectedSkill.value = data.skill || skill;
    dialogVisible.value = true;
  } catch (error) {
    ElMessage.error(error.message);
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    const data = await getSkills();
    skills.value = data.skills || [];
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.skill-card {
  margin-bottom: 14px;
  cursor: pointer;
}

.skill-card:hover {
  border-color: #2563eb;
}

.skill-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
</style>
