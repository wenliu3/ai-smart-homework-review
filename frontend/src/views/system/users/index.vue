<template>
  <adaptive-table-container
    :loading="loading"
    loading-text="加载中..."
    :recalculate-trigger="recalculateTrigger"
    ref="adaptiveTableRef"
  >
    <!-- 搜索区域 -->
    <template #search>
      <el-form
        :inline="true"
        :model="searchForm"
        size="default"
        class="flex flex-wrap items-center"
      >
        <el-form-item label="关键词">
          <el-input
            v-model="searchForm.keyword"
            placeholder="用户名/姓名/邮箱"
            clearable
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select
            v-model="searchForm.role"
            placeholder="用户角色"
            clearable
            style="width: 120px"
          >
            <el-option label="全部" value="" />
            <el-option label="超级管理员" value="superadmin" />
            <el-option label="教师" value="teacher" />
            <el-option label="学生" value="student" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="用户状态"
            clearable
            style="width: 120px"
          >
            <el-option label="全部" value="" />
            <el-option label="正常" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item class="mb-0 flex-shrink-0">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><Refresh /></el-icon>重置
          </el-button>
          <el-button type="primary" @click="handleAddUser">
            <el-icon><Plus /></el-icon>新增
          </el-button>
          <el-button type="success" @click="handleImportUsers">
            <el-icon><Upload /></el-icon>批量导入
          </el-button>
          <el-button
            type="danger"
            @click="handleBatchDelete"
            :disabled="selectedUsers.length === 0"
          >
            <el-icon><Delete /></el-icon>批量删除 ({{ selectedUsers.length }})
          </el-button>
        </el-form-item>
      </el-form>
    </template>
    <!-- 表格区域 -->
    <template #table="{ tableHeight }">
      <user-table
        :user-data="userList"
        :is-mobile="isMobile"
        :max-height="tableHeight"
        @edit="handleEditUser"
        @delete="handleDeleteUser"
        @change-status="handleChangeStatus"
        @reset-password="handleResetPassword"
        @selection-change="handleSelectionChange"
        ref="userTableRef"
      />
    </template>

    <!-- 分页区域 -->
    <template #pagination>
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.limit"
        :page-sizes="[10, 20, 50, 100]"
        :background="true"
        layout="total, sizes, prev, pager, next, jumper"
        :total="pagination.total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </template>

    <!-- 其他组件 -->
    <template #extra>
      <!-- 用户表单 -->
      <user-form
        :is-mobile="isMobile"
        @success="loadUserData"
        ref="userFormRef"
      />

      <!-- 用户导入对话框 -->
      <import-users-dialog @success="loadUserData" ref="importDialogRef" />

      <!-- 批量删除结果对话框 -->
      <batch-delete-result-dialog ref="batchDeleteResultRef" />
    </template>
  </adaptive-table-container>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  getUsers,
  deleteUser,
  updateUser,
  resetUserPassword,
  deleteUsersBatch,
} from "../../../api/user";
import { Plus, Refresh, Search, Upload, Delete } from "@element-plus/icons-vue";
import { useStore } from "vuex";
import type { User, UserStatus, UserQueryParams } from "../../../types/user";

// 导入组件
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";
import UserTable from "./components/UserTable.vue";
import UserForm from "./components/UserForm.vue";
import ImportUsersDialog from "./components/ImportUsersDialog.vue";
import BatchDeleteResultDialog from "./components/BatchDeleteResultDialog.vue";

// Store
const store = useStore();

// 响应式设计 - 检测设备类型
const device = computed(() => store.getters["app/device"]);
const isMobile = computed(
  () => device.value === "mobile" || device.value === "tablet"
);

// 搜索表单数据
const searchForm = reactive({
  keyword: "",
  role: "",
  status: "",
});

// 分页数据
const pagination = reactive({
  page: 1,
  limit: 10,
  total: 0,
});

// 数据状态
const loading = ref(true);
const userList = ref<User[]>([]);
const selectedUsers = ref<User[]>([]); // 选中的用户列表

// 组件引用
const adaptiveTableRef = ref(null);
const userFormRef = ref(null);
const importDialogRef = ref(null);
const userTableRef = ref(null); // 用户表格引用
const batchDeleteResultRef = ref(null); // 批量删除结果对话框引用

// 触发重新计算表格高度的计数器
const recalculateTrigger = ref(0);

// 重置搜索
const resetSearch = () => {
  searchForm.keyword = "";
  searchForm.role = "";
  searchForm.status = "";
  pagination.page = 1;
  loadUserData();
};

// 处理搜索
const handleSearch = () => {
  pagination.page = 1;
  loadUserData();
};

// 处理分页变化
const handleSizeChange = (val: number) => {
  pagination.limit = val;
  loadUserData();
};

const handleCurrentChange = (val: number) => {
  pagination.page = val;
  loadUserData();
};

// 加载用户数据
const loadUserData = async () => {
  loading.value = true;
  try {
    // 构建查询参数
    const params: UserQueryParams = {
      page: pagination.page,
      limit: pagination.limit,
      keyword: searchForm.keyword || undefined,
      role: (searchForm.role || undefined) as any,
      status: (searchForm.status || undefined) as any,
    };

    const response = await getUsers(params);
    userList.value = response.items || [];
    pagination.total = response.total || 0;

    // 触发表格高度重新计算
    recalculateTrigger.value++;
  } catch (error) {
    console.error("加载用户数据失败", error);
    ElMessage.error("加载用户列表失败");
  } finally {
    loading.value = false;
  }
};

// 打开添加用户对话框
const handleAddUser = () => {
  userFormRef.value?.openForm("add");
};

// 打开编辑用户对话框
const handleEditUser = (user: User) => {
  userFormRef.value?.openForm("edit", user._id);
};

// 处理删除用户
const handleDeleteUser = async (user: User) => {
  if (!user || !user._id) {
    ElMessage.error("用户数据不完整，无法删除");
    return;
  }

  // 禁止删除超级管理员
  if (user.role === "superadmin") {
    ElMessage.warning("超级管理员用户不能删除");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.name}" 吗？删除后无法恢复！`,
      "删除提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await deleteUser(user._id);
    ElMessage.success("删除成功");
    // 刷新数据
    loadUserData();
  } catch (error) {
    if (error === "cancel") return;
    console.error("删除用户失败", error);
    ElMessage.error("删除失败：" + (error.message || "未知错误"));
  }
};

// 处理修改用户状态
const handleChangeStatus = async (user: User, status: UserStatus) => {
  if (!user || !user._id) {
    ElMessage.error("用户数据不完整，无法修改状态");
    return;
  }

  try {
    await updateUser(user._id, { status });
    ElMessage.success("状态修改成功");
    // 刷新数据
    loadUserData();
  } catch (error) {
    console.error("修改用户状态失败", error);
    ElMessage.error("状态修改失败：" + (error.message || "未知错误"));
  }
};

// 处理重置密码
const handleResetPassword = async (user: User) => {
  if (!user || !user._id) {
    ElMessage.error("用户数据不完整，无法重置密码");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要重置 "${user.name}" 的密码吗？`,
      "重置密码",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    let data = await resetUserPassword(user._id);
    // 弹出对话框提示用户的密码，点击确定一键复制密码信息
    ElMessageBox.alert(`${data.message}`, "密码重置成功", {
      confirmButtonText: "确定",
      type: "success",
    });
    // ElMessage.success('密码重置成功')
  } catch (error) {
    if (error === "cancel") return;
    console.error("重置密码失败", error);
    ElMessage.error("重置密码失败：" + (error.message || "未知错误"));
  }
};

// 打开导入用户对话框
const handleImportUsers = () => {
  importDialogRef.value?.open();
};

// 处理选择变化
const handleSelectionChange = (selected: User[]) => {
  selectedUsers.value = selected;
};

// 处理批量删除
const handleBatchDelete = async () => {
  if (selectedUsers.value.length === 0) {
    ElMessage.warning("请先选择要删除的用户");
    return;
  }

  try {
    const userNames = selectedUsers.value.map((user) => user.name).join("、");
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedUsers.value.length} 个用户吗？\n用户：${userNames}\n删除后无法恢复！`,
      "批量删除确认",
      {
        confirmButtonText: "确定删除",
        cancelButtonText: "取消",
        type: "warning",
        dangerouslyUseHTMLString: false,
      }
    );

    const userIds = selectedUsers.value.map((user) => user._id);
    const result = await deleteUsersBatch(userIds);

    // 使用新的结果对话框显示详细结果
    batchDeleteResultRef.value?.open(result);

    // 清空选择并刷新数据
    userTableRef.value?.clearSelection();
    selectedUsers.value = [];
    loadUserData();
  } catch (error) {
    if (error === "cancel") return;
    console.error("批量删除失败", error);
    ElMessage.error("批量删除失败：" + (error.message || "未知错误"));
  }
};

// 加载初始数据
onMounted(() => {
  loadUserData();
});
</script>
