<template>
  <section>
    <div class="page-header">
      <div>
        <h1>匹配配置</h1>
        <div class="page-subtitle">配置岗位筛选、技能关键词和通勤匹配条件。</div>
      </div>
      <el-button type="primary" :loading="saving" @click="submit">保存配置</el-button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :md="8" :xs="24">
            <el-form-item label="最低薪资上限 K">
              <el-input-number v-model="settings.min_salary_k" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :md="8" :xs="24">
            <el-form-item label="最低公司规模">
              <el-input-number v-model="settings.min_company_size" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :md="8" :xs="24">
            <el-form-item label="目标工作地">
              <el-input v-model="settings.required_location" placeholder="例如：广州" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="加分关键词">
          <el-input v-model="settings.positive_keywords_text" type="textarea" :rows="4" placeholder="每行一个关键词，例如 Java、Spring Boot、C端" />
        </el-form-item>
        <el-form-item label="C 端关键词">
          <el-input v-model="settings.c_side_keywords_text" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="排除关键词">
          <el-input v-model="settings.exclude_keywords_text" type="textarea" :rows="3" placeholder="例如 外包、驻场、派遣" />
        </el-form-item>

        <el-divider>通勤配置</el-divider>
        <el-row :gutter="16">
          <el-col :md="10" :xs="24">
            <el-form-item label="家庭位置">
              <el-input v-model="settings.home_address" placeholder="用于计算公共交通时间" />
            </el-form-item>
          </el-col>
          <el-col :md="6" :xs="24">
            <el-form-item label="最长通勤分钟">
              <el-input-number v-model="settings.max_commute_minutes" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :md="8" :xs="24">
            <el-form-item label="地图 API Key">
              <el-input v-model="settings.map_api_key" show-password />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { getSettings, updateSettings } from "../api";

const loading = ref(false);
const saving = ref(false);
const settings = reactive({
  min_salary_k: 22,
  min_company_size: 100,
  required_location: "",
  positive_keywords_text: "",
  c_side_keywords_text: "",
  exclude_keywords_text: "",
  home_address: "",
  max_commute_minutes: 60,
  map_api_key: "",
  map_provider: "amap"
});

function toText(items) {
  return Array.isArray(items) ? items.join("\n") : "";
}

function toList(text) {
  return String(text || "")
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function submit() {
  try {
    saving.value = true;
    const data = await updateSettings({
      ...settings,
      positive_keywords: toList(settings.positive_keywords_text),
      c_side_keywords: toList(settings.c_side_keywords_text),
      exclude_keywords: toList(settings.exclude_keywords_text)
    });
    Object.assign(settings, data.settings || {});
    settings.positive_keywords_text = toText(settings.positive_keywords);
    settings.c_side_keywords_text = toText(settings.c_side_keywords);
    settings.exclude_keywords_text = toText(settings.exclude_keywords);
    ElMessage.success("配置已保存");
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    const data = await getSettings();
    Object.assign(settings, data.settings || {});
    settings.positive_keywords_text = toText(settings.positive_keywords);
    settings.c_side_keywords_text = toText(settings.c_side_keywords);
    settings.exclude_keywords_text = toText(settings.exclude_keywords);
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
});
</script>
