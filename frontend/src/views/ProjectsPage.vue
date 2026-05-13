<template>
  <section>
    <div class="page-header">
      <div>
        <h1>项目经验</h1>
        <div class="page-subtitle">把技能点和真实项目经历关联起来，后续用于面试复盘。</div>
      </div>
      <el-button type="primary" @click="dialogVisible = true">新增项目</el-button>
    </div>

    <div v-loading="loading">
      <el-empty v-if="!loading && !projects.length" description="还没有项目经验" />
      <el-row v-else :gutter="14">
        <el-col v-for="project in projects" :key="project.project_id" :lg="8" :md="12" :xs="24">
          <el-card class="project-card" shadow="never">
            <h3>{{ project.name }}</h3>
            <div class="muted">{{ project.role }} · {{ project.period }}</div>
            <p>{{ project.description }}</p>
            <p class="muted">{{ project.outcome }}</p>
            <div class="tag-list">
              <el-tag v-for="skill in project.skills || []" :key="skill.skill_name" effect="plain">
                {{ skill.skill_name }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="dialogVisible" title="新增项目经验" width="680px">
      <el-form label-position="top">
        <el-form-item label="项目名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="你的角色"><el-input v-model="form.role" /></el-form-item>
        <el-form-item label="时间范围"><el-input v-model="form.period" placeholder="例如：2023.03 - 2024.06" /></el-form-item>
        <el-form-item label="项目描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="项目结果"><el-input v-model="form.outcome" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="关联技能">
          <el-select v-model="form.skills" multiple filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="skill in skills" :key="skill.name" :label="skill.name" :value="skill.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="证明材料/亮点"><el-input v-model="form.evidence" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createProject, getProjects, getSkills } from "../api";

const projects = ref([]);
const skills = ref([]);
const dialogVisible = ref(false);
const loading = ref(false);
const saving = ref(false);
const initialForm = { name: "", role: "", period: "", description: "", outcome: "", skills: [], evidence: "" };
const form = reactive({ ...initialForm });

function resetForm() {
  Object.assign(form, { ...initialForm, skills: [] });
}

async function load() {
  loading.value = true;
  try {
    const [projectData, skillData] = await Promise.all([getProjects(), getSkills()]);
    projects.value = projectData.projects || [];
    skills.value = skillData.skills || [];
  } finally {
    loading.value = false;
  }
}

async function submit() {
  if (!form.name.trim()) {
    ElMessage.warning("请填写项目名称");
    return;
  }
  try {
    saving.value = true;
    await createProject(form);
    ElMessage.success("项目已保存");
    dialogVisible.value = false;
    resetForm();
    await load();
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    await load();
  } catch (error) {
    ElMessage.error(error.message);
  }
});
</script>

<style scoped>
.project-card {
  margin-bottom: 14px;
}

.project-card h3 {
  margin-top: 0;
}
</style>
