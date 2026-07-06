<template>
  <div class="class-detail">
    <!-- 返回导航 -->
    <div class="flex items-center mb-4">
      <el-button
        :icon="ArrowLeft"
        size="default"
        @click="goBack"
        class="mr-3 flex-shrink-0"
      >
        <span class="hidden sm:inline">返回班级列表</span>
        <span class="sm:hidden">返回</span>
      </el-button>
      <el-breadcrumb separator="/" class="hidden sm:block">
        <el-breadcrumb-item>班级管理</el-breadcrumb-item>
        <el-breadcrumb-item v-if="classDetail">{{
          classDetail.name
        }}</el-breadcrumb-item>
      </el-breadcrumb>
      <!-- 移动端显示班级名称 -->
      <div v-if="classDetail" class="sm:hidden text-gray-600 text-sm truncate">
        {{ classDetail.name }}
      </div>
    </div>

    <!-- 班级信息卡片 -->
    <class-info-card
      v-if="classDetail"
      :class-data="classDetail"
      @edit="handleEditClass"
      @disband="handleDisbandClass"
      @regenerate-code="handleRegenerateCode"
      class="mb-4"
    />

    <!-- Element Plus Tab组件 -->
    <div
      class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden"
    >
      <el-tabs v-model="activeTab" size="default" class="class-detail-tabs">
        <el-tab-pane name="students" label="学生管理">
          <template #label>
            <span class="flex items-center">
              <el-icon class="mr-2"><User /></el-icon>
              学生管理
              <el-badge
                v-if="studentCount > 0"
                :value="studentCount"
                class="ml-2"
              />
            </span>
          </template>
        </el-tab-pane>

        <el-tab-pane name="assignments" label="作业管理">
          <template #label>
            <span class="flex items-center">
              <el-icon class="mr-2"><Document /></el-icon>
              作业管理
              <el-badge
                v-if="assignmentCount > 0"
                :value="assignmentCount"
                class="ml-2"
              />
            </span>
          </template>
        </el-tab-pane>
        <component
          :is="currentComponent"
          :class-id="classId"
          @student-count-change="handleStudentCountChange"
          @assignment-count-change="handleAssignmentCountChange"
        />
      </el-tabs>
    </div>

    <!-- 编辑班级对话框 -->
    <create-class-dialog
      v-model="showEditDialog"
      :class-data="classDetail"
      @success="handleEditSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, User, Document } from "@element-plus/icons-vue";
import {
  getClassDetail,
  disbandClass,
  regenerateClassCode,
} from "@/api/classes";
import type { Class } from "@/types/classes";

// 导入组件
import ClassInfoCard from "./components/ClassInfoCard.vue";
import StudentList from "./components/StudentList.vue";
import AssignmentManagement from "./components/AssignmentManagement.vue";
import CreateClassDialog from "../components/CreateClassDialog.vue";

const route = useRoute();
const router = useRouter();

// 班级ID - 从query参数获取
const classId = route.query.id as string;

// Tab状态
const activeTab = ref("students");

// 组件映射
const componentMap = {
  students: StudentList,
  assignments: AssignmentManagement,
};

// 当前组件
const currentComponent = computed(() => {
  return componentMap[activeTab.value as keyof typeof componentMap];
});

// 数据状态
const classDetail = ref<Class | null>(null);
const showEditDialog = ref(false);
const studentCount = ref(0); // 学生数量
const assignmentCount = ref(0); // 作业数量

// 返回上一页
const goBack = () => {
  router.push("/teacher/classes");
};

// 加载班级详情
const loadClassDetail = async () => {
  try {
    const classData = await getClassDetail(classId);
    classDetail.value = classData;
    studentCount.value = classData.studentCount || 0;
  } catch (error) {
    console.error("加载班级详情失败:", error);
    // ElMessage.error('加载班级详情失败')

    // 清除message所有弹框
    ElMessage.closeAll();

    // 详情查询失败，弹出对话框，提示用户
    ElMessageBox.alert("加载班级详情失败", "提示", {
      confirmButtonText: "返回班级列表",
      type: "error",
      callback: () => {
        router.push("/teacher/classes");
      },
    });
    return;
  }
};

// 班级操作
const handleEditClass = () => {
  showEditDialog.value = true;
};

const handleDisbandClass = async () => {
  if (!classDetail.value) return;

  try {
    await ElMessageBox.confirm(
      `确定要解散班级"${classDetail.value.name}"吗？此操作不可撤销。`,
      "确认解散",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await disbandClass(classId);
    ElMessage.success("班级已成功解散");
    router.push("/teacher/classes");
  } catch (error) {
    if (error !== "cancel") {
      console.error("解散班级失败:", error);
      ElMessage.error("解散班级失败");
    }
  }
};

const handleRegenerateCode = async () => {
  if (!classDetail.value) return;

  try {
    await ElMessageBox.confirm(
      `确定要刷新班级"${classDetail.value.name}"的邀请码吗？旧的邀请码将失效。`,
      "确认刷新",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    const response = await regenerateClassCode(classId);
    ElMessage.success(`新的邀请码：${response.inviteCode}`);
    loadClassDetail();
  } catch (error) {
    if (error !== "cancel") {
      console.error("刷新邀请码失败:", error);
      ElMessage.error("刷新邀请码失败");
    }
  }
};

const handleEditSuccess = () => {
  showEditDialog.value = false;
  loadClassDetail();
};

// 处理学生数量变化
const handleStudentCountChange = (count: number) => {
  studentCount.value = count;
  // 同时更新班级详情中的学生数量
  if (classDetail.value) {
    classDetail.value.studentCount = count;
  }
};

// 处理作业数量变化
const handleAssignmentCountChange = (count: number) => {
  console.log("作业数量变化:", count);

  assignmentCount.value = count;
};

// 初始化
onMounted(() => {
  loadClassDetail();
});
</script>

<style scoped>
.class-detail {
  background: #f8fafc;
  min-height: calc(100vh - 120px);
}

.class-detail-tabs {
  padding: 10px;
}
/* 最小化自定义样式，主要依赖组件原生配置 */
:deep(.class-detail-tabs .el-tabs__content) {
  padding: 0px 20px;
  min-height: 500px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .class-detail {
    background: #fff;
  }

  :deep(.class-detail-tabs .el-tabs__content) {
    padding: 16px;
  }
}
</style>
