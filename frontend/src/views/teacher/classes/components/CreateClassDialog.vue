<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑班级' : '创建班级'"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    destroy-on-close
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="80px"
      class="space-y-4"
    >
      <el-form-item label="班级名称" prop="name">
        <el-input
          v-model="formData.name"
          placeholder="请输入班级名称"
          maxlength="50"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item label="班级描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          placeholder="请输入班级描述（可选）"
          :rows="3"
          maxlength="200"
          show-word-limit
          clearable
        />
      </el-form-item>

      <el-form-item label="班级人数" prop="maxStudents">
        <el-input-number
          v-model="formData.maxStudents"
          :min="1"
          :max="60"
          :step="1"
          placeholder="请设置班级最大人数"
          class="w-full"
          controls-position="right"
        />
        <div class="text-xs text-gray-500 mt-1">
          <span v-if="!isEdit">设置班级最大学生数量，范围1-60人，默认60人</span>
          <span v-else class="text-amber-600">
            ⚠️ 编辑时不能小于当前学生数({{
              classData?.studentCount || 0
            }}人)，如需缩减请先移除部分学生
          </span>
        </div>
      </el-form-item>

      <el-form-item v-if="!isEdit" label="邀请码" prop="code">
        <div class="flex items-center space-x-2 w-full">
          <el-input
            v-model="formData.code"
            placeholder="自动生成或自定义邀请码"
            maxlength="10"
            clearable
            class="flex-1"
          />
          <el-button
            :icon="Refresh"
            @click="generateRandomCode"
            title="生成随机邀请码"
          />
        </div>
        <div class="text-xs text-gray-500 mt-1">
          留空则自动生成，长度4-10位，支持字母和数字
        </div>
      </el-form-item>

      <el-form-item v-if="isEdit" label="班级状态" prop="status">
        <el-select
          v-model="formData.status"
          placeholder="选择班级状态"
          class="w-full"
        >
          <el-option label="活跃" value="active" />
          <el-option label="暂停" value="inactive" />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-end space-x-3">
        <el-button @click="handleCancel"> 取消 </el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          {{ isEdit ? "保存" : "创建" }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
// 使用相对路径导入
import { createClass, updateClass } from "../../../../api/classes";

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

interface CreateClassParams {
  name: string;
  description?: string;
  code?: string;
  maxStudents?: number;
}

interface UpdateClassParams {
  name?: string;
  description?: string;
  status?: "active" | "inactive" | "disbanded";
  maxStudents?: number;
}

interface Props {
  modelValue: boolean;
  classData?: Class | null;
}

interface Emits {
  (e: "update:modelValue", value: boolean): void;
  (e: "success"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 表单引用
const formRef = ref<FormInstance>();

// 对话框显示状态
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

// 是否为编辑模式
const isEdit = computed(() => !!props.classData);

// 加载状态
const loading = ref(false);

// 表单数据
const formData = reactive<CreateClassParams & UpdateClassParams>({
  name: "",
  description: "",
  code: "",
  status: "active",
  maxStudents: 60,
});

// 表单验证规则
const formRules: FormRules = {
  name: [
    { required: true, message: "请输入班级名称", trigger: "blur" },
    { min: 2, max: 50, message: "班级名称长度为2-50个字符", trigger: "blur" },
  ],
  description: [
    { max: 200, message: "班级描述长度不能超过200个字符", trigger: "blur" },
  ],
  code: [
    { min: 4, max: 10, message: "邀请码长度为4-10个字符", trigger: "blur" },
    {
      pattern: /^[A-Za-z0-9]+$/,
      message: "邀请码只能包含字母和数字",
      trigger: "blur",
    },
  ],
  status: [{ required: true, message: "请选择班级状态", trigger: "change" }],
  maxStudents: [
    { required: true, message: "请设置班级最大人数", trigger: "change" },
  ],
};

// 重置表单 - 移到watch之前
const resetForm = () => {
  Object.assign(formData, {
    name: "",
    description: "",
    code: "",
    status: "active",
    maxStudents: 60,
  });
  nextTick(() => {
    formRef.value?.clearValidate();
  });
};

// 监听props变化，初始化表单数据
watch(
  () => props.classData,
  (newVal) => {
    if (newVal) {
      // 编辑模式
      Object.assign(formData, {
        name: newVal.name,
        description: newVal.description || "",
        status: newVal.status,
        maxStudents: newVal.maxStudents,
      });
    } else {
      // 创建模式
      resetForm();
    }
  },
  { immediate: true }
);

// 生成随机邀请码
const generateRandomCode = () => {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let result = "";
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  formData.code = result;
};

// 处理取消
const handleCancel = () => {
  resetForm();
  dialogVisible.value = false;
};

// 处理提交
const handleSubmit = async () => {
  if (!formRef.value) return;

  try {
    await formRef.value.validate();
    loading.value = true;

    if (isEdit.value && props.classData) {
      // 编辑班级 - 允许空字符串清空描述
      const updateData: UpdateClassParams = {
        name: formData.name,
        description: formData.description, // 编辑时：直接传递值，空字符串表示清空描述
        status: formData.status,
        maxStudents: formData.maxStudents,
      };

      await updateClass(props.classData._id, updateData);
      ElMessage.success("班级信息更新成功");
      emit("success");
      dialogVisible.value = false;
    } else {
      // 创建班级 - 空描述时不传递字段
      const createData: CreateClassParams = {
        name: formData.name,
        description: formData.description || undefined, // 创建时：空描述不传递字段，让后端使用默认值
        code: formData.code || undefined,
        maxStudents: formData.maxStudents,
      };

      await createClass(createData);
      ElMessage.success("班级创建成功");

      // 创建成功后重置表单
      resetForm();

      emit("success");
      dialogVisible.value = false;
    }
  } catch (error: any) {
    console.error("操作失败:", error);
  } finally {
    loading.value = false;
  }
};
</script>

<script lang="ts">
// 添加默认导出以支持常规导入
import { defineComponent } from "vue";

export default defineComponent({
  name: "CreateClassDialog",
});
</script>

<style scoped>
:deep(.el-dialog__body) {
  padding: 20px 24px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #374151;
}
</style>
