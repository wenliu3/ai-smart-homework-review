<template>
  <el-select
    :model-value="modelValue"
    @update:model-value="handleChange"
    multiple
    placeholder="请选择班级"
    style="width: 100%"
    :loading="loading"
    filterable
    collapse-tags
    collapse-tags-tooltip
  >
    <el-option
      v-for="cls in classList"
      :key="cls._id"
      :label="cls.name"
      :value="cls._id"
      :disabled="cls.status !== 'active'"
    >
      <div class="class-option">
        <span
          class="class-name"
          :class="{ 'disabled-class': cls.status !== 'active' }"
        >
          {{ cls.name }}
        </span>
        <div class="class-meta">
          <span class="class-info">{{ cls.studentCount }}人</span>
          <el-tag
            v-if="cls.status !== 'active'"
            :type="getStatusType(cls.status)"
            size="small"
            class="status-tag"
          >
            {{ getStatusText(cls.status) }}
          </el-tag>
        </div>
      </div>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getClassList as fetchClassList } from "@/api/classes";
import type { Class } from "@/types/classes";

interface Props {
  modelValue: string[];
}

interface Emits {
  (e: "update:modelValue", value: string[]): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const loading = ref(false);
const classList = ref<Class[]>([]);

// 获取班级列表
const loadClassList = async () => {
  loading.value = true;
  try {
    const response = await fetchClassList({
      page: 1,
      limit: 100, // 获取所有班级，不再过滤状态
    });

    classList.value = response.items;
  } catch (error) {
    console.error("获取班级列表失败:", error);
  } finally {
    loading.value = false;
  }
};

// 处理值变化
const handleChange = (value: string[]) => {
  // 过滤掉非活跃状态的班级
  const activeValues = value.filter((classId) => {
    const cls = classList.value.find((c) => c._id === classId);
    return cls && cls.status === "active";
  });
  emit("update:modelValue", activeValues);
};

// 获取状态类型
const getStatusType = (status: string) => {
  switch (status) {
    case "active":
      return "success";
    case "inactive":
      return "warning";
    case "disbanded":
      return "danger";
    default:
      return "info";
  }
};

// 获取状态文本
const getStatusText = (status: string) => {
  switch (status) {
    case "active":
      return "活跃";
    case "inactive":
      return "暂停";
    case "disbanded":
      return "已解散";
    default:
      return "未知";
  }
};

// 初始化
onMounted(() => {
  loadClassList();
});

// 添加默认导出
defineOptions({
  name: "ClassSelector",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "ClassSelector",
});
</script>

<style scoped>
.class-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.class-name {
  flex: 1;
  font-weight: 500;
}

.class-name.disabled-class {
  color: #c0c4cc;
}

.class-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.class-info {
  font-size: 12px;
  color: #909399;
}

.status-tag {
  margin-left: 4px;
}
</style>
