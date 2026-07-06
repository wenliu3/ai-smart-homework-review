<template>
  <el-dialog
    v-model="visible"
    title="修改密码"
    width="650px"
    :close-on-click-modal="false"
    destroy-on-close
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      label-position="right"
      @submit.prevent="submitForm"
    >
      <el-form-item label="当前密码" prop="currentPassword">
        <el-input
          v-model="form.currentPassword"
          type="password"
          placeholder="请输入当前密码"
          show-password
          autocomplete="current-password"
        />
      </el-form-item>

      <el-form-item label="新密码" prop="newPassword">
        <el-input
          v-model="form.newPassword"
          type="password"
          placeholder="请输入新密码"
          show-password
          autocomplete="new-password"
        />
        <div class="password-tips">
          <p class="tip-title">密码要求：</p>
          <div class="tip-grid">
            <div class="tip-item" :class="{ valid: passwordChecks.length }">
              <el-icon class="tip-icon">
                <CircleCheckFilled v-if="passwordChecks.length" />
                <span v-else class="circle-empty">○</span>
              </el-icon>
              <span>至少8个字符</span>
            </div>
            <div class="tip-item" :class="{ valid: passwordChecks.uppercase }">
              <el-icon class="tip-icon">
                <CircleCheckFilled v-if="passwordChecks.uppercase" />
                <span v-else class="circle-empty">○</span>
              </el-icon>
              <span>包含大写字母</span>
            </div>
            <div class="tip-item" :class="{ valid: passwordChecks.lowercase }">
              <el-icon class="tip-icon">
                <CircleCheckFilled v-if="passwordChecks.lowercase" />
                <span v-else class="circle-empty">○</span>
              </el-icon>
              <span>包含小写字母</span>
            </div>
            <div class="tip-item" :class="{ valid: passwordChecks.number }">
              <el-icon class="tip-icon">
                <CircleCheckFilled v-if="passwordChecks.number" />
                <span v-else class="circle-empty">○</span>
              </el-icon>
              <span>包含数字</span>
            </div>
            <div class="tip-item" :class="{ valid: passwordChecks.special }">
              <el-icon class="tip-icon">
                <CircleCheckFilled v-if="passwordChecks.special" />
                <span v-else class="circle-empty">○</span>
              </el-icon>
              <span>包含特殊字符</span>
            </div>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          placeholder="请再次输入新密码"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose" :disabled="loading">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="loading">
          确认修改
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script lang="ts">
import { ref, reactive, computed, watch, defineComponent } from "vue";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import { CircleCheckFilled } from "@element-plus/icons-vue";
import { changePassword } from "../../api/auth";

export default defineComponent({
  name: "ChangePasswordDialog",
  components: {
    CircleCheckFilled,
  },
  props: {
    modelValue: {
      type: Boolean,
      required: true,
    },
  },
  emits: ["update:modelValue", "success"],
  setup(props, { emit }) {
    // 响应式数据
    const formRef = ref<FormInstance>();
    const loading = ref(false);

    // 控制弹窗显示
    const visible = computed({
      get: () => props.modelValue,
      set: (value) => emit("update:modelValue", value),
    });

    // 表单数据
    const form = reactive({
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    });

    // 密码强度检查
    const passwordChecks = computed(() => {
      const password = form.newPassword;
      return {
        length: password.length >= 8,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        number: /\d/.test(password),
        special: /[^A-Za-z0-9]/.test(password),
      };
    });

    // 验证新密码强度
    const validateNewPassword = (rule: any, value: string, callback: any) => {
      if (!value) {
        callback(new Error("请输入新密码"));
        return;
      }

      if (value === form.currentPassword) {
        callback(new Error("新密码不能与当前密码相同"));
        return;
      }

      if (value.length < 8) {
        callback(new Error("密码长度至少为8个字符"));
        return;
      }

      // 检查密码复杂度
      const checks = passwordChecks.value;

      if (!checks.uppercase) {
        callback(new Error("密码必须包含大写字母"));
        return;
      }

      if (!checks.lowercase) {
        callback(new Error("密码必须包含小写字母"));
        return;
      }

      if (!checks.number) {
        callback(new Error("密码必须包含数字"));
        return;
      }

      if (!checks.special) {
        callback(new Error("密码必须包含特殊字符"));
        return;
      }

      callback();
    };

    // 验证确认密码
    const validateConfirmPassword = (
      rule: any,
      value: string,
      callback: any
    ) => {
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

    // 表单验证规则
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

    // 重置表单
    const resetForm = () => {
      form.currentPassword = "";
      form.newPassword = "";
      form.confirmPassword = "";
      formRef.value?.clearValidate();
    };

    // 提交表单
    const submitForm = async () => {
      if (!formRef.value) return;

      const isValid = await formRef.value.validate().catch(() => false);
      if (!isValid) return;

      loading.value = true;

      try {
        await changePassword({
          currentPassword: form.currentPassword,
          newPassword: form.newPassword,
          confirmPassword: form.confirmPassword,
        });

        ElMessage.success("密码修改成功！");

        // 重置表单并关闭弹窗
        resetForm();
        visible.value = false;

        // 触发成功事件
        emit("success");
      } catch (error: any) {
        console.error("修改密码失败:", error);
        ElMessage.error(error.message || "修改密码失败，请重试");
      } finally {
        loading.value = false;
      }
    };

    // 关闭弹窗
    const handleClose = () => {
      if (loading.value) return;
      resetForm();
      visible.value = false;
    };

    // 监听弹窗显示状态，显示时重置表单
    watch(visible, (newVal) => {
      if (newVal) {
        resetForm();
      }
    });

    return {
      formRef,
      loading,
      visible,
      form,
      passwordChecks,
      rules,
      resetForm,
      submitForm,
      handleClose,
    };
  },
});
</script>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.password-tips {
  margin-top: 12px;
  padding: 10px 18px;
  background: linear-gradient(135deg, #f8f9fa 0%, #f1f3f4 100%);
  border-radius: 10px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.tip-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin: 0 0 12px 0;
}

.tip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  align-items: center;
}

@media (max-width: 768px) {
  .tip-grid {
    gap: 6px 16px;
  }
}

@media (max-width: 480px) {
  .tip-grid {
    gap: 6px;
  }

  .tip-item {
    min-width: 120px;
    font-size: 11px;
    padding: 3px 6px;
  }

  .password-tips {
    padding: 14px;
  }
}

.tip-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #909399;
  transition: all 0.3s ease;
  padding: 4px 8px;
  min-width: 140px;
  flex: 0 0 auto;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.02);
}

.tip-item.valid {
  color: #67c23a;
  background-color: rgba(103, 194, 58, 0.08);
  border: 1px solid rgba(103, 194, 58, 0.2);
}

.tip-icon {
  font-size: 14px;
  margin-right: 6px;
  transition: color 0.3s ease;
  color: #dcdfe6;
}

.tip-item.valid .tip-icon {
  color: #67c23a;
}

.tip-item span {
  line-height: 1.2;
}

.circle-empty {
  font-size: 14px;
  color: inherit;
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #606266;
}

/* 弹窗响应式 */
:deep(.el-dialog) {
  margin: 0 auto;
}

@media (max-width: 768px) {
  :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
  }
}

@media (max-width: 480px) {
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 3vh auto;
  }
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 16px;
}

:deep(.el-dialog__body) {
  padding-top: 24px;
}

:deep(.el-input__wrapper) {
  transition: all 0.3s ease;
}

:deep(.el-input__wrapper:hover) {
  border-color: #c0c4cc;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}
</style>
