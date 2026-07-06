<template>
  <div
    class="class-info-card bg-white rounded-lg shadow-sm border border-gray-200"
  >
    <!-- 卡片头部 -->
    <div class="p-4 border-b border-gray-100">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div class="mb-3 sm:mb-0">
          <div class="flex items-center space-x-3 mb-2">
            <h1 class="text-xl font-bold text-gray-900">
              {{ classData.name }}
            </h1>
            <el-tag :type="statusTagType" size="default" class="font-medium">
              {{ statusText }}
            </el-tag>
          </div>
          <p v-if="classData.description" class="text-gray-600 text-sm">
            {{ classData.description }}
          </p>
          <p v-else class="text-gray-400 italic text-sm">暂无描述</p>
        </div>

        <div class="flex items-center space-x-2">
          <el-button
            type="primary"
            :icon="Edit"
            size="default"
            @click="$emit('edit')"
          >
            编辑班级
          </el-button>
          <el-dropdown trigger="click" @command="handleCommand">
            <el-button :icon="MoreFilled" size="default" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  command="regenerate-code"
                  :icon="RefreshRight"
                >
                  刷新邀请码
                </el-dropdown-item>
                <el-dropdown-item
                  command="disband"
                  :icon="Delete"
                  divided
                  class="text-red-600"
                  v-if="classData.status !== 'disbanded'"
                >
                  解散班级
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- 卡片内容 -->
    <div class="p-4">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <!-- 邀请码 -->
        <div class="bg-blue-50 rounded-lg p-3">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-blue-600">班级邀请码</span>
            <el-button
              :icon="CopyDocument"
              size="small"
              text
              @click="copyCode"
              class="text-blue-500 hover:text-blue-700"
              title="复制邀请码"
            />
          </div>
          <div class="text-lg font-bold text-blue-700 font-mono">
            {{ classData.code }}
          </div>
        </div>

        <!-- 学生数量 -->
        <div class="bg-green-50 rounded-lg p-3">
          <div class="text-sm font-medium text-green-600 mb-2">学生数量</div>
          <div class="text-lg font-bold text-green-700">
            {{ classData.studentCount }} / {{ classData.maxStudents }} 人
          </div>
        </div>

        <!-- 创建时间 -->
        <div class="bg-purple-50 rounded-lg p-3">
          <div class="text-sm font-medium text-purple-600 mb-2">创建时间</div>
          <div class="text-sm font-bold text-purple-700">
            {{ formatDate(classData.createdAt) }}
          </div>
        </div>

        <!-- 最后更新 -->
        <div class="bg-orange-50 rounded-lg p-3">
          <div class="text-sm font-medium text-orange-600 mb-2">最后更新</div>
          <div class="text-sm font-bold text-orange-700">
            {{ formatDate(classData.updatedAt) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ElMessage } from "element-plus";
import moment from "moment";
import {
  Edit,
  MoreFilled,
  RefreshRight,
  Delete,
  CopyDocument,
} from "@element-plus/icons-vue";

// 本地定义类型，避免导入问题
interface Class {
  _id: string;
  name: string;
  code: string;
  teacherId: string;
  teacherName?: string;
  status: "active" | "inactive" | "disbanded";
  studentCount: number;
  maxStudents: number;
  description?: string;
  createdAt: string;
  updatedAt: string;
}

interface Props {
  classData: Class;
}

interface Emits {
  (e: "edit"): void;
  (e: "disband"): void;
  (e: "regenerate-code"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 状态标签类型
const statusTagType = computed(() => {
  switch (props.classData.status) {
    case "active":
      return "success";
    case "inactive":
      return "warning";
    case "disbanded":
      return "danger";
    default:
      return "info";
  }
});

// 状态文本
const statusText = computed(() => {
  switch (props.classData.status) {
    case "active":
      return "活跃";
    case "inactive":
      return "暂停";
    case "disbanded":
      return "已解散";
    default:
      return "未知";
  }
});

// 格式化日期 - 使用moment库
const formatDate = (dateStr: string) => {
  return moment(dateStr).format("YYYY-MM-DD HH:mm:ss");
};

// 复制邀请码
const copyCode = async () => {
  try {
    await navigator.clipboard.writeText(props.classData.code);
    ElMessage.success("邀请码已复制到剪贴板");
  } catch (error) {
    console.error("复制失败:", error);
    ElMessage.error("复制失败");
  }
};

// 处理下拉菜单命令
const handleCommand = (command: string) => {
  switch (command) {
    case "disband":
      emit("disband");
      break;
    case "regenerate-code":
      emit("regenerate-code");
      break;
  }
};

// 组件名称
defineOptions({
  name: "ClassInfoCard",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "ClassInfoCard",
});
</script>

<style scoped>
.class-info-card {
  transition: all 0.3s ease;
}

.class-info-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}
</style>
