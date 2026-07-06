<template>
  <div>
    <el-dialog
      :title="dialogTitle"
      v-model="dialogVisible"
      :width="isMobile ? '95%' : '700px'"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="80px"
        label-position="right"
        status-icon
      >
        <el-row :gutter="20">
          <!-- 左侧列 -->
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                :disabled="formMode === 'edit'"
              ></el-input>
            </el-form-item>

            <el-form-item label="邮箱" prop="email">
              <el-input
                v-model="form.email"
                placeholder="请输入邮箱"
              ></el-input>
            </el-form-item>

            <el-form-item label="用户角色" prop="role">
              <el-select
                v-model="form.role"
                placeholder="请选择用户角色"
                style="width: 100%"
              >
                <el-option label="超级管理员" value="superadmin" />
                <el-option label="教师" value="teacher" />
                <el-option label="学生" value="student" />
              </el-select>
            </el-form-item>

            <el-form-item
              label="密码"
              prop="password"
              v-if="formMode === 'add'"
            >
              <el-input
                v-model="form.password"
                type="password"
                placeholder="请输入密码"
                show-password
              ></el-input>
            </el-form-item>

            <el-form-item
              label="学号"
              prop="studentId"
              v-if="form.role === 'student'"
            >
              <el-input
                v-model="form.studentId"
                placeholder="请输入学号"
              ></el-input>
            </el-form-item>
          </el-col>

          <!-- 右侧列 -->
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" placeholder="请输入姓名"></el-input>
            </el-form-item>

            <el-form-item label="手机号" prop="phone">
              <el-input
                v-model="form.phone"
                placeholder="请输入手机号"
              ></el-input>
            </el-form-item>

            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio label="active">正常</el-radio>
                <el-radio label="inactive">禁用</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item
              label="确认密码"
              prop="confirmPassword"
              v-if="formMode === 'add'"
            >
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="请再次输入密码"
                show-password
              ></el-input>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm" :loading="submitting">
            {{ formMode === "add" ? "创建" : "保存" }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick } from "vue";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus/es/components/form";
import { createUser, getUser, updateUser } from "@/api/user";
import { assignRolesToUser } from "@/api/user-role";
import { getRoleList } from "@/api/role";
import type { CreateUserDto, UpdateUserDto, User } from "@/types/user";

// 组件属性
const props = defineProps({
  isMobile: {
    type: Boolean,
    default: false,
  },
});

// 组件事件
const emit = defineEmits(["success"]);

// 表单引用
const formRef = ref<FormInstance | null>(null);

// 对话框控制
const dialogVisible = ref(false);
const submitting = ref(false);
const formMode = ref<"add" | "edit">("add");
const userId = ref("");

// 对话框标题
const dialogTitle = computed(() => {
  return formMode.value === "add" ? "新增用户" : "编辑用户";
});

// 表单数据
const form = reactive<CreateUserDto & { confirmPassword?: string }>({
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
  name: "",
  role: "student",
  studentId: "",
  phone: "",
  status: "active",
});

// 表单验证规则
const rules = reactive<FormRules>({
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 2, max: 20, message: "长度应为2-20个字符", trigger: "blur" },
  ],
  name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "请输入有效的邮箱地址", trigger: "blur" },
  ],
  phone: [
    {
      pattern: /^1[3-9]\d{9}$/,
      message: "请输入有效的手机号",
      trigger: "blur",
    },
  ],
  role: [{ required: true, message: "请选择用户角色", trigger: "change" }],
  password: [
    {
      required: true,
      message: "请输入密码",
      trigger: "blur",
      validator: (rule, value, callback) => {
        if (formMode.value === "add" && (!value || value.length < 6)) {
          callback(new Error("密码长度不能少于6个字符"));
        } else {
          if (form.confirmPassword && formRef.value) {
            formRef.value.validateField("confirmPassword");
          }
          callback();
        }
      },
    },
  ],
  confirmPassword: [
    {
      required: true,
      message: "请再次输入密码",
      trigger: "blur",
      validator: (rule, value, callback) => {
        if (formMode.value === "add" && value !== form.password) {
          callback(new Error("两次输入的密码不一致"));
        } else {
          callback();
        }
      },
    },
  ],
  status: [{ required: true, message: "请选择用户状态", trigger: "change" }],
  studentId: [
    {
      required: true,
      message: "请输入学号",
      trigger: "blur",
      validator: (rule, value, callback) => {
        if (form.role === "student" && !value) {
          callback(new Error("学生角色必须填写学号"));
        } else {
          callback();
        }
      },
    },
  ],
});

// 存储原始用户数据（用于比较角色是否变化）
const originalUserData = ref<User | null>(null);

// 角色映射表（角色代码到角色ID的映射）
const roleMapping = ref<Record<string, string>>({});

// 加载角色映射
const loadRoleMapping = async () => {
  try {
    const response = await getRoleList();
    const mapping: Record<string, string> = {};
    response.items.forEach((role) => {
      mapping[role.code] = role._id;
    });
    roleMapping.value = mapping;
  } catch (error) {
    console.error("加载角色映射失败", error);
  }
};

// 打开表单对话框
const openForm = async (mode: "add" | "edit", id: string = "") => {
  formMode.value = mode;
  userId.value = id;
  dialogVisible.value = true;

  resetForm();

  // 加载角色映射（用于角色同步）
  await loadRoleMapping();

  if (mode === "edit" && id) {
    await loadUserData(id);
  }
};

// 重置表单
const resetForm = () => {
  nextTick(() => {
    formRef.value?.resetFields();

    // 重置表单数据
    Object.assign(form, {
      username: "",
      email: "",
      password: "",
      confirmPassword: "",
      name: "",
      role: "student",
      studentId: "",
      phone: "",
      status: "active",
    });
  });
};

// 加载用户数据
const loadUserData = async (id: string) => {
  try {
    const userData = await getUser(id);
    originalUserData.value = userData; // 保存原始数据

    // 填充表单数据
    Object.assign(form, {
      username: userData.username || "",
      email: userData.email || "",
      name: userData.name || "",
      role: userData.role || "student",
      studentId: userData.studentId || "",
      phone: userData.phone || "",
      status: userData.status || "active",
    });
  } catch (error) {
    console.error("加载用户数据失败", error);
    ElMessage.error("加载用户数据失败");
    dialogVisible.value = false;
  }
};

// 提交表单
const submitForm = () => {
  if (!formRef.value) return;

  // 额外检查学生角色是否填写了学号
  if (form.role === "student" && !form.studentId) {
    ElMessage.warning("学生角色必须填写学号");
    return;
  }

  formRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true;
      try {
        const userData = {
          username: form.username,
          email: form.email,
          name: form.name,
          role: form.role,
          studentId: form.role === "student" ? form.studentId : undefined,
          phone: form.phone || undefined,
          status: form.status,
        };

        if (formMode.value === "add") {
          await createUser({
            ...userData,
            password: form.password,
          } as CreateUserDto);
          ElMessage.success("创建用户成功");
        } else {
          // 更新用户基本信息
          await updateUser(userId.value, userData as UpdateUserDto);

          // 检查角色是否发生变化，如果变化则同步角色分配
          if (
            originalUserData.value &&
            originalUserData.value.role !== form.role
          ) {
            const roleId = roleMapping.value[form.role];
            if (roleId) {
              await assignRolesToUser(userId.value, [roleId]);
              console.log(
                `用户角色已从 ${originalUserData.value.role} 更新为 ${form.role}`
              );
            }
          }

          ElMessage.success("更新用户成功");
        }

        dialogVisible.value = false;
        emit("success");
      } catch (error) {
        console.error(
          `${formMode.value === "add" ? "创建" : "更新"}用户失败`,
          error
        );
        ElMessage.error(
          `${formMode.value === "add" ? "创建" : "更新"}用户失败`
        );
      } finally {
        submitting.value = false;
      }
    }
  });
};

// 暴露方法给父组件
defineExpose({
  openForm,
});
</script>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
