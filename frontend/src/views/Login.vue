<template>
  <div
    class="min-h-screen w-full bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8"
  >
    <!-- 主登录卡片 -->
    <div class="login-main-card">
      <!-- 左侧视频背景区域 -->
      <div class="login-left-section">
        <!-- 视频背景 -->
        <video class="video-background" autoplay muted loop playsinline>
          <source src="@/assets/video/ip.mp4" type="video/mp4" />
          您的浏览器不支持视频播放
        </video>

        <!-- 视频上方的内容覆盖层 -->
        <!-- <div class="video-overlay">
          <div class="logo-content">
            <div class="logo-text-content">
              <h1 class="logo-title">AI智能作业批改系统</h1>
              <p class="logo-description">
                智能化作业批改平台<br>提升教学效率，优化学习体验
              </p>
            </div>
          </div>
        </div> -->
      </div>

      <!-- 右侧登录表单区域 -->
      <div class="login-right-section">
        <div class="login-form-container">
          <!-- 表单标题 -->
          <div class="form-header">
            <h3 class="form-title">
              {{ isRegister ? "注册账户" : "用户登录" }}
            </h3>
            <p class="form-subtitle">
              {{ isRegister ? "创建您的账户" : "欢迎回来" }}
            </p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            @submit.prevent="submitForm"
            class="mt-2"
          >
            <!-- 注册表单显示用户名字段 -->
            <el-form-item v-if="isRegister" label="用户名" prop="username">
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                class="!rounded"
              ></el-input>
            </el-form-item>

            <!-- 登录方式选择 -->
            <el-form-item v-if="!isRegister" label="登录方式" prop="loginType">
              <el-segmented 
                v-model="form.loginType" 
                :options="[
                  { label: '用户名登录', value: 'username' },
                  { label: '学号登录', value: 'studentId' },
                  { label: '邮箱登录', value: 'email' }
                ]"
                @change="handleLoginTypeChange"
                class="w-full"
              />
            </el-form-item>

            <!-- 用户名字段（登录） -->
            <el-form-item v-if="!isRegister && form.loginType === 'username'" label="用户名" prop="username">
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                class="!rounded"
              ></el-input>
            </el-form-item>

            <!-- 学号字段 -->
            <el-form-item v-if="!isRegister && form.loginType === 'studentId'" label="学号" prop="studentId">
              <el-input
                v-model="form.studentId"
                placeholder="请输入学号"
                class="!rounded"
              ></el-input>
            </el-form-item>

            <!-- 邮箱字段 -->
            <el-form-item v-if="isRegister || form.loginType === 'email'" label="邮箱" prop="email">
              <el-input
                v-model="form.email"
                placeholder="请输入邮箱"
                class="!rounded"
              ></el-input>
            </el-form-item>

            <!-- 密码字段 -->
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                placeholder="请输入密码"
                type="password"
                show-password
                class="!rounded"
              ></el-input>
            </el-form-item>

            <!-- 注册表单显示确认密码字段 -->
            <el-form-item
              v-if="isRegister"
              label="确认密码"
              prop="confirmPassword"
            >
              <el-input
                v-model="form.confirmPassword"
                placeholder="请再次输入密码"
                type="password"
                show-password
                class="!rounded"
              ></el-input>
            </el-form-item>

            <!-- 记住我选项 -->
            <el-form-item v-if="!isRegister">
              <div class="flex justify-between items-center w-full">
                <div class="flex items-center">
                  <el-checkbox v-model="form.rememberMe">记住我</el-checkbox>
                  <el-tooltip
                    content="勾选后30天内免登录，让您的学习更便捷"
                    placement="top"
                    effect="dark"
                  >
                    <el-icon class="ml-1 text-gray-400 cursor-help">
                      <QuestionFilled />
                    </el-icon>
                  </el-tooltip>
                </div>
                <a
                  href="#"
                  @click.prevent="handleForgotPassword"
                  class="text-blue-500 hover:text-blue-700 text-sm transition-colors"
                >
                  忘记密码?
                </a>
              </div>
            </el-form-item>

            <!-- 提交按钮 -->
            <el-form-item label-width="0px">
              <el-button
                class="w-full !flex justify-center items-center py-2 !rounded"
                type="primary"
                native-type="submit"
                :loading="loading"
              >
                {{ isRegister ? "注册" : "登录" }}
              </el-button>
            </el-form-item>

            <!-- 错误信息 -->
            <div v-if="error" class="text-red-500 text-sm mb-4 text-center">
              {{ error }}
            </div>

            <!-- 切换登录/注册表单 -->
            <!-- <div class="text-center text-sm mt-4">
          <span v-if="isRegister">
            已有账号?
            <a href="#" @click.prevent="isRegister = false" class="text-blue-500 hover:text-blue-700 transition-colors">点击登录</a>
          </span>
          <span v-else>
            没有账号?
            <a href="#" @click.prevent="isRegister = true" class="text-blue-500 hover:text-blue-700 transition-colors">点击注册</a>
          </span>
        </div> -->
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useStore } from "vuex";
import { ElMessage } from "element-plus";
import { QuestionFilled } from "@element-plus/icons-vue";
import type { FormInstance, FormRules } from "element-plus";

// 路由实例
const router = useRouter();
const route = useRoute();

// Vuex store实例
const store = useStore();

// 表单引用
const formRef = ref<FormInstance>();

// 状态管理
const isRegister = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);

// 表单数据
const form = reactive({
  username: "",
  email: "",
  studentId: "",
  password: "",
  confirmPassword: "",
  rememberMe: true, // 默认勾选记住密码
  loginType: "username", // 默认用户名登录
});

// 校验密码是否一致
const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error("两次输入的密码不一致"));
  } else {
    callback();
  }
};

// 表单校验规则
const rules = reactive<FormRules>({
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "请输入正确的邮箱格式", trigger: "blur" },
  ],
  studentId: [
    { required: true, message: "请输入学号", trigger: "blur" },
    { min: 1, max: 20, message: "学号长度应在1-20个字符之间", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 6, message: "密码长度至少为6个字符", trigger: "blur" },
  ],
  confirmPassword: [
    { required: true, message: "请确认密码", trigger: "blur" },
    { validator: validateConfirmPassword, trigger: "blur" },
  ],
});

// 处理登录方式切换
const handleLoginTypeChange = (value: string) => {
  // 清空相应字段的值和错误信息
  if (value === 'email') {
    form.studentId = '';
  } else if (value === 'studentId') {
    form.email = '';
  }
  // 清除表单验证错误
  formRef.value?.clearValidate(['email', 'studentId']);
};

// 处理忘记密码
const handleForgotPassword = () => {
  ElMessage.info({
    message: "请联系管理员重置密码",
    duration: 3000,
    showClose: true,
  });
};

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return;

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true;
      error.value = null;

      try {
        if (isRegister.value) {
          // 注册逻辑
          await store.dispatch("user/register", {
            username: form.username,
            email: form.email,
            password: form.password,
          });

          ElMessage.success("注册成功");
        } else {
          // 登录逻辑 - 根据登录类型选择不同的字段
          let identifier = form.username;
          if (form.loginType === 'email') identifier = form.email;
          else if (form.loginType === 'studentId') identifier = form.studentId;

          const loginData = {
            usernameOrEmailOrStudentId: identifier,
            password: form.password,
            rememberMe: form.rememberMe,
          };
          
          const loginResponse = await store.dispatch("user/login", loginData);

          ElMessage.success("登录成功");

          // 检查是否需要强制修改密码
          if (loginResponse.mustChangePassword) {
            // 跳转到强制修改密码页面，并保存原始跳转地址
            const redirectUrl =
              (route.query.redirect as string) || "/dashboard";
            router.push(
              `/force-change-password?redirect=${encodeURIComponent(
                redirectUrl
              )}`
            );
          } else {
            // 登录成功后跳转到dashboard，由权限控制逻辑根据角色自动分配
            router.push((route.query.redirect as string) || "/dashboard");
          }
        }
      } catch (err: any) {
        console.error("登录/注册失败:", err);
        error.value =
          err.message || (isRegister.value ? "注册失败" : "登录失败");
      } finally {
        loading.value = false;
      }
    }
  });
};

// 检查当前用户是否已登录
onMounted(() => {
  // 这里为空，可以根据需要添加逻辑
});
</script>

<style scoped>
/* 主登录卡片 */
.login-main-card {
  width: 100%;
  max-width: 900px;
  min-height: 500px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  display: flex;
  overflow: hidden;
  animation: cardSlideIn 0.6s ease-out;
}

@keyframes cardSlideIn {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 左侧视频背景区域 */
.login-left-section {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #edeee9;
}

/* 视频背景 */
.video-background {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: auto;
  height: 85%;
  max-width: 100%;
  object-fit: contain;
  z-index: 1;
}

/* 视频覆盖层 */
.video-overlay {
  position: relative;
  z-index: 2;
  background: rgba(0, 0, 0, 0.4); /* 半透明黑色遮罩 */
  backdrop-filter: blur(2px);
  border-radius: 15px;
  padding: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-content {
  text-align: center;
  color: white;
  position: relative;
  z-index: 1;
}

/* 移除了logo-image样式，因为现在使用视频背景 */

.logo-title {
  font-size: 1.8rem;
  font-weight: 700;
  margin: 0 0 1rem 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.logo-description {
  font-size: 1rem;
  opacity: 0.9;
  line-height: 1.6;
  margin: 0;
}

/* 右侧登录表单区域 */
.login-right-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  background: white;
}

.login-form-container {
  width: 100%;
  max-width: 350px;
}

.form-header {
  text-align: center;
  margin-bottom: 2rem;
}

.form-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 0.5rem 0;
}

.form-subtitle {
  color: #6b7280;
  font-size: 0.9rem;
  margin: 0;
}

/* 表单样式 */
.el-form-item {
  margin-bottom: 1.5rem;
}

 
.el-input :deep(.el-input__wrapper) {
  border-radius: 10px;
  border: 2px solid #e5e7eb;
  box-shadow: none;
  transition: all 0.3s ease;
  height: 48px;
}

.el-input :deep(.el-input__wrapper):hover {
  border-color: #667eea;
}

.el-input :deep(.el-input__wrapper.is-focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.el-input :deep(.el-input__inner) {
  height: 44px;
  font-size: 0.95rem;
}

.el-button {
  width: 100%;
  height: 48px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.el-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
}

.el-button:active {
  transform: translateY(0);
}

/* 链接样式 */
a {
  color: #667eea;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.3s ease;
}

a:hover {
  color: #5a67d8;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-main-card {
    flex-direction: column;
    max-width: 400px;
    min-height: auto;
    margin: 1rem;
  }

  .login-left-section {
    min-height: 200px; /* 确保视频区域有最小高度 */
  }

  .login-right-section {
    padding: 2rem 1rem;
  }

  .video-overlay {
    padding: 1.5rem 1rem; /* 小屏幕时减少内边距 */
  }

  .logo-title {
    font-size: 1.5rem;
  }

  .logo-description {
    display: none; /* 小屏幕时隐藏描述文字 */
  }

  .form-title {
    font-size: 1.5rem;
  }
}

@media (max-width: 480px) {
  .login-main-card {
    margin: 0.5rem;
    border-radius: 15px;
  }

  .login-left-section,
  .login-right-section {
    padding: 1.5rem 1rem;
  }
}

/* 渐变背景动画 */
@keyframes gradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.bg-gradient-to-br {
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
}
</style>
