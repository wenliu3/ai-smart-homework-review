<template>
  <div class="force-change-password-container">
    <el-card class="change-password-card">
      <template #header>
        <div class="card-header">
          <h2>强制修改密码</h2>
        </div>
      </template>

      <div class="notice-section">
        <el-alert
          title="为了您的账户安全"
          type="warning"
          :closable="false"
          show-icon
        >
          <template #default>
            <p>{{ noticeMessage }}</p>
            <p>请设置一个安全性更高的新密码后继续使用系统。</p>
          </template>
        </el-alert>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        label-position="right"
        @submit.prevent="submitForm"
      >
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input
            v-model="form.currentPassword"
            placeholder="请输入当前密码"
            type="password"
            show-password
          ></el-input>
        </el-form-item>

        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            placeholder="请输入新密码"
            type="password"
            show-password
          ></el-input>
          <div class="password-tips">
            <p>密码要求：</p>
            <ul>
              <li>至少8个字符</li>
              <li>包含大小写字母、数字和特殊字符</li>
            </ul>
          </div>
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            placeholder="请再次输入新密码"
            type="password"
            show-password
          ></el-input>
        </el-form-item>

        <el-form-item>
          <el-button
            class="submit-button"
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
          >
            修改密码
          </el-button>
        </el-form-item>

        <div v-if="error" class="error-message">{{ error }}</div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useStore } from "vuex";
import { useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { firstChangePassword } from "../api/auth";
import { ElMessage } from "element-plus";

// Store和路由实例
const store = useStore();
const router = useRouter();

// 表单引用
const formRef = ref<FormInstance>();

// 状态管理
const loading = ref(false);
const error = ref<string | null>(null);

// 用户信息
const userInfo = computed(() => store.getters["user/getUserInfo"]);
const isFirstLogin = computed(() => userInfo.value?.isFirstLogin);

// 提示消息
const noticeMessage = computed(() => {
  if (isFirstLogin.value) {
    return "检测到您是首次登录，为了保护您的账户安全，请立即修改默认密码。";
  }
  return "管理员已重置您的密码，为了保护您的账户安全，请立即修改密码。";
});

// 表单数据
const form = reactive({
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
});

// 校验新密码强度
const validateNewPassword = (rule: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error("请输入新密码"));
    return;
  }

  if (value.length < 8) {
    callback(new Error("密码长度至少为8个字符"));
    return;
  }

  // 检查密码复杂度
  const hasUppercase = /[A-Z]/.test(value);
  const hasLowercase = /[a-z]/.test(value);
  const hasNumbers = /\d/.test(value);
  const hasSpecialChars = /[^A-Za-z0-9]/.test(value);

  if (!hasUppercase) {
    callback(new Error("密码必须包含大写字母"));
    return;
  }

  if (!hasLowercase) {
    callback(new Error("密码必须包含小写字母"));
    return;
  }

  if (!hasNumbers) {
    callback(new Error("密码必须包含数字"));
    return;
  }

  if (!hasSpecialChars) {
    callback(new Error("密码必须包含特殊字符"));
    return;
  }

  callback();
};

// 校验确认密码
const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error("请确认新密码"));
    return;
  }

  if (value !== form.newPassword) {
    callback(new Error("两次输入的密码不一致"));
    return;
  }

  callback();
};

// 表单校验规则
const rules = reactive<FormRules>({
  currentPassword: [
    { required: true, message: "请输入当前密码", trigger: "blur" },
  ],
  newPassword: [
    { required: true, validator: validateNewPassword, trigger: "blur" },
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: "blur" },
  ],
});

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return;

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true;
      error.value = null;

      try {
        await firstChangePassword({
          currentPassword: form.currentPassword,
          newPassword: form.newPassword,
          confirmPassword: form.confirmPassword,
        });

        ElMessage.success("密码修改成功！");

        // 清除强制修改密码标记
        store.commit("user/SET_USER_INFO", {
          ...userInfo.value,
          mustChangePassword: false,
        });

        // 跳转到dashboard或用户想要访问的页面
        const redirect = router.currentRoute.value.query.redirect as string;
        router.push(redirect || "/dashboard");
      } catch (err: any) {
        console.error("修改密码失败:", err);
        error.value = err.message || "修改密码失败，请重试";
      } finally {
        loading.value = false;
      }
    }
  });
};

// 组件挂载时检查是否需要强制修改密码
onMounted(() => {
  const mustChangePassword = store.getters["user/mustChangePassword"];

  if (!mustChangePassword) {
    // 如果不需要强制修改密码，跳转到dashboard
    router.push("/dashboard");
  }
});
</script>

<style scoped>
.force-change-password-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f7fa;
  padding: 20px;
}

.change-password-card {
  width: 500px;
  max-width: 100%;
}

.card-header {
  display: flex;
  justify-content: center;
  color: #409eff;
}

.card-header h2 {
  margin: 0;
  font-size: 24px;
}

.notice-section {
  margin-bottom: 24px;
}

.submit-button {
  width: 100%;
  padding: 12px;
  font-size: 16px;
}

.error-message {
  color: #f56c6c;
  margin-top: 12px;
  text-align: center;
  font-size: 14px;
}

.password-tips {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.password-tips p {
  margin: 4px 0;
}

.password-tips ul {
  margin: 4px 0;
  padding-left: 16px;
}

.password-tips li {
  margin: 2px 0;
}

:deep(.el-alert) {
  border-radius: 8px;
}

:deep(.el-alert__content) {
  line-height: 1.6;
}

:deep(.el-form-item__label) {
  font-weight: 600;
}
</style>
