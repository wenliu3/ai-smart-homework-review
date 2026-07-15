<!-- 管理员版创建/编辑班级对话框 — 可选教师 -->
<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑班级' : '创建班级'"
    width="520px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
      <!-- 选择教师 -->
      <el-form-item label="授课教师" prop="teacherId">
        <el-select
          v-model="formData.teacherId"
          placeholder="选择负责此班级的教师"
          filterable
          class="w-full"
        >
          <el-option
            v-for="t in teachers"
            :key="t.id"
            :label="`${t.name} (ID:${t.id})`"
            :value="t.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="班级名称" prop="name">
        <el-input v-model="formData.name" placeholder="请输入班级名称" maxlength="50" show-word-limit clearable />
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

      <el-form-item label="最大人数" prop="maxStudents">
        <el-input-number v-model="formData.maxStudents" :min="1" :max="200" :step="1" class="w-full" controls-position="right" />
      </el-form-item>

      <el-form-item v-if="!isEdit" label="邀请码" prop="code">
        <div class="flex items-center gap-2 w-full">
          <el-input v-model="formData.code" placeholder="留空自动生成" maxlength="10" clearable class="flex-1" />
          <el-button :icon="Refresh" @click="generateCode" title="随机生成" />
        </div>
      </el-form-item>

      <el-form-item v-if="isEdit" label="班级状态" prop="status">
        <el-select v-model="formData.status" class="w-full">
          <el-option label="活跃" value="active" />
          <el-option label="暂停" value="inactive" />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ isEdit ? "保存" : "创建" }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { createClassForTeacher, updateClass } from "../../../../api/classes";
import type { Class } from "../../../../types/classes";

interface TeacherItem {
  id: number;
  name: string;
}

interface Props {
  modelValue: boolean;
  classData?: Class | null;
  teachers?: TeacherItem[];
}

const props = withDefaults(defineProps<Props>(), { teachers: () => [] });
const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "success"): void;
}>();

const formRef = ref<FormInstance>();
const loading = ref(false);

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const isEdit = computed(() => !!props.classData);

const formData = reactive({
  teacherId: null as number | null,
  name: "",
  description: "",
  code: "",
  status: "active" as string,
  maxStudents: 60,
});

const formRules: FormRules = {
  teacherId: [{ required: true, message: "请选择教师", trigger: "change" }],
  name: [
    { required: true, message: "请输入班级名称", trigger: "blur" },
    { min: 2, max: 50, message: "长度2-50字符", trigger: "blur" },
  ],
  code: [{ min: 4, max: 10, message: "邀请码4-10位", trigger: "blur" }],
};

const resetForm = () => {
  Object.assign(formData, { teacherId: null, name: "", description: "", code: "", status: "active", maxStudents: 60 });
  nextTick(() => formRef.value?.clearValidate());
};

watch(
  () => props.classData,
  (val) => {
    if (val) {
      Object.assign(formData, {
        name: (val as any).name || "",
        description: (val as any).description || "",
        status: (val as any).status || "active",
        maxStudents: (val as any).maxStudents || 60,
        code: "",
        teacherId: parseInt((val as any).teacherId) || null,
      });
    } else {
      resetForm();
    }
  },
  { immediate: true }
);

const generateCode = () => {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  formData.code = Array.from({ length: 6 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
};

const handleCancel = () => {
  resetForm();
  dialogVisible.value = false;
};

const handleSubmit = async () => {
  if (!formRef.value) return;
  try {
    await formRef.value.validate();
    loading.value = true;

    if (isEdit.value && props.classData) {
      await updateClass((props.classData as any)._id, {
        name: formData.name,
        description: formData.description || undefined,
        status: formData.status,
        maxStudents: formData.maxStudents,
        teacherId: formData.teacherId || undefined,
      });
      ElMessage.success("班级信息已更新");
    } else {
      await createClassForTeacher({
        name: formData.name,
        description: formData.description || undefined,
        code: formData.code || undefined,
        maxStudents: formData.maxStudents,
        teacherId: formData.teacherId!,
      });
      ElMessage.success("班级创建成功");
      resetForm();
    }
    emit("success");
    dialogVisible.value = false;
  } catch (error: any) {
    if (error?.message) ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
};
</script>
