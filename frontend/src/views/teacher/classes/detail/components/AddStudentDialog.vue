<template>
  <el-dialog
    v-model="dialogVisible"
    title="添加学生"
    width="600px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <!-- 学号输入 -->
    <div class="mb-4">
      <div class="mb-2">
        <label class="text-sm font-medium text-gray-700">学号列表</label>
        <p class="text-xs text-gray-500 mt-1">
          请输入学号，一行一个，将自动去除空格和重复项
        </p>
      </div>
      <el-input
        v-model="studentNumbers"
        type="textarea"
        :rows="8"
        placeholder="请输入学号，一行一个，将自动格式化&#10;例如：&#10;2024001&#10;2024002&#10;2024003"
        resize="none"
        class="w-full"
      />
      <div class="mt-2 text-sm text-gray-500">
        <div>共 {{ validStudentNumbers.length }} 个有效学号</div>
      </div>
    </div>

    <!-- 添加结果展示 -->
    <div v-if="addResult" class="mt-4 p-4 bg-gray-50 rounded-lg">
      <h4 class="text-sm font-medium text-gray-900 mb-3">添加结果</h4>

      <!-- 统计信息 -->
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div class="text-center">
          <div class="text-2xl font-bold text-blue-600">
            {{ addResult.totalCount }}
          </div>
          <div class="text-sm text-gray-500">总数</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-green-600">
            {{ addResult.successCount }}
          </div>
          <div class="text-sm text-gray-500">成功</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-red-600">
            {{ addResult.failedCount }}
          </div>
          <div class="text-sm text-gray-500">失败</div>
        </div>
      </div>

      <!-- 失败详情 -->
      <div v-if="addResult.errors && addResult.errors.length > 0" class="mt-4">
        <div class="text-sm font-medium text-gray-700 mb-2">失败详情：</div>
        <div class="max-h-40 overflow-y-auto">
          <div
            v-for="(error, index) in addResult.errors"
            :key="index"
            class="flex justify-between items-center py-2 px-3 bg-red-50 border border-red-200 rounded mb-2"
          >
            <span class="text-sm text-gray-700">{{ error.id }}</span>
            <span class="text-sm text-red-600">{{ error.reason }}</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-between items-center">
        <div class="text-sm text-gray-500">
          {{
            validStudentNumbers.length > 0
              ? `准备添加 ${validStudentNumbers.length} 名学生`
              : ""
          }}
        </div>
        <div class="space-x-2">
          <el-button @click="handleCancel">取消</el-button>
          <el-button
            type="primary"
            :loading="submitting"
            :disabled="validStudentNumbers.length === 0"
            @click="handleSubmit"
          >
            添加 ({{ validStudentNumbers.length }})
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue";
import { ElMessage } from "element-plus";
// 暂时使用相对路径导入
import { addStudentsToClass } from "../../../../../api/classes";

// 本地定义类型，避免导入问题
interface AddStudentError {
  id: string;
  reason: string;
}

interface AddStudentsApiResponse {
  success: string[];
  failed: AddStudentError[];
}

interface Props {
  modelValue: boolean;
  classId: string;
}

interface Emits {
  (e: "update:modelValue", value: boolean): void;
  (e: "success"): void;
}

// 添加结果统计信息（用于前端展示）
interface AddStudentResult {
  totalCount: number;
  successCount: number;
  failedCount: number;
  errors: AddStudentError[];
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 对话框显示状态
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

// 数据状态
const submitting = ref(false);
const studentNumbers = ref("");
const addResult = ref<AddStudentResult | null>(null);

// 实时处理输入内容，去除空格并格式化
watch(
  studentNumbers,
  (newValue) => {
    if (!newValue) return;

    // 按行分割，去除每行的所有空格，过滤空行
    const lines = newValue
      .split("\n")
      .map((line) => line.replace(/\s+/g, "")) // 去除所有空格
      .filter((line) => line.length > 0); // 过滤空行

    // 去重
    const uniqueLines = Array.from(new Set(lines));

    // 重新组合成字符串，每行一个学号
    const processedValue = uniqueLines.join("\n");

    // 只有当处理后的值与当前值不同时才更新，避免无限循环
    if (processedValue !== newValue.trim()) {
      // 使用 nextTick 确保 DOM 更新后再设置值
      nextTick(() => {
        studentNumbers.value = processedValue;
      });
    }
  },
  { immediate: false }
);

// 处理学号输入，现在只需要简单分割即可（因为已经实时处理过了）
const validStudentNumbers = computed(() => {
  if (!studentNumbers.value.trim()) {
    return [];
  }

  return studentNumbers.value.split("\n").filter((num) => num.length > 0);
});

// 计算原始输入的有效行数（去除空行）
const originalValidCount = computed(() => {
  return validStudentNumbers.value.length;
});

// 计算重复的学号数量（由于实时去重，这个值现在总是0）
const duplicateCount = computed(() => {
  return 0; // 由于实时去重，不再有重复项
});

// 处理取消
const handleCancel = () => {
  studentNumbers.value = "";
  addResult.value = null;
  dialogVisible.value = false;
};

// 处理提交
const handleSubmit = async () => {
  if (validStudentNumbers.value.length === 0) {
    ElMessage.warning("请输入要添加的学号");
    return;
  }

  submitting.value = true;
  addResult.value = null;

  try {
    // 调用后端接口，传递学号数组
    const response: AddStudentsApiResponse = await addStudentsToClass(
      props.classId,
      {
        studentIds: validStudentNumbers.value,
      }
    );

    // 根据新的API返回格式处理结果
    // API返回格式：{ success: [], failed: [] }
    if (response && (response.success || response.failed)) {
      // 构建前端展示用的结果格式
      addResult.value = {
        totalCount: validStudentNumbers.value.length,
        successCount: response.success?.length || 0,
        failedCount: response.failed?.length || 0,
        errors: response.failed || [],
      };

      // 显示总体结果消息
      if (addResult.value.successCount > 0) {
        ElMessage.success(`成功添加 ${addResult.value.successCount} 名学生`);
      }

      if (addResult.value.failedCount > 0) {
        ElMessage.warning(`有 ${addResult.value.failedCount} 名学生添加失败`);
      }

      // 如果有成功添加的学生，触发刷新
      if (addResult.value.successCount > 0) {
        emit("success");
      }
    } else {
      ElMessage.error("添加学生失败：接口返回数据格式异常");
    }
  } finally {
    submitting.value = false;
  }
};

// 导出组件的名称供调试使用
defineOptions({
  name: "AddStudentDialog",
});
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "AddStudentDialog",
});
</script>

<style scoped>
/* 组件样式可以在这里添加 */
</style>
