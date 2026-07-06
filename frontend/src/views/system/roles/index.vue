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
        <el-form-item label="角色名称">
          <el-input
            v-model="searchForm.name"
            placeholder="请输入角色名称"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="角色编码">
          <el-input
            v-model="searchForm.code"
            placeholder="请输入角色编码"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="角色状态"
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
          <el-button type="primary" @click="handleAddRole">
            <el-icon><Plus /></el-icon>新增
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <!-- 表格区域 -->
    <template #table="{ tableHeight }">
      <role-table
        :role-data="roleList"
        :is-mobile="isMobile"
        :max-height="tableHeight"
        @edit="handleEditRole"
        @delete="handleDeleteRole"
      />
    </template>

    <!-- 分页区域 -->
    <template #pagination>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.limit"
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
      <!-- 角色表单 -->
      <role-form
        :is-mobile="isMobile"
        @success="loadRoleData"
        ref="roleFormRef"
      />
    </template>
  </adaptive-table-container>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getRoleList, deleteRole } from "@/api/role";
import { Plus, Refresh, Search } from "@element-plus/icons-vue";
import { useStore } from "vuex";

// 导入组件
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";
import RoleTable from "./components/RoleTable.vue";
import RoleForm from "./components/RoleForm.vue";

// Store
const store = useStore();

// 响应式设计 - 检测设备类型
const device = computed(() => store.getters["app/device"]);
const isMobile = computed(
  () => device.value === "mobile" || device.value === "tablet"
);

// 搜索表单数据
const searchForm = reactive({
  name: "",
  code: "",
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
const roleList = ref([]);

// 组件引用
const adaptiveTableRef = ref(null);
const roleFormRef = ref(null);
const roleTableRef = ref(null);

// 触发重新计算表格高度的计数器
const recalculateTrigger = ref(0);

// 重置搜索
const resetSearch = () => {
  searchForm.name = "";
  searchForm.code = "";
  searchForm.status = "";
  pagination.page = 1;
  loadRoleData();
};

// 处理搜索
const handleSearch = () => {
  pagination.page = 1;
  loadRoleData();
};

// 处理分页变化
const handleSizeChange = (val) => {
  pagination.limit = val;
  loadRoleData();
};

const handleCurrentChange = (val) => {
  pagination.page = val;
  loadRoleData();
};

// 加载角色数据
const loadRoleData = async () => {
  loading.value = true;
  try {
    // 构建查询参数
    const params = {
      page: pagination.page,
      limit: pagination.limit,
    };

    // 添加搜索条件
    if (searchForm.name) params.search = searchForm.name;
    if (searchForm.code) params.code = searchForm.code;
    if (searchForm.status) params.status = searchForm.status;

    const response = await getRoleList(params);
    roleList.value = response.items || [];
    pagination.total = response.total || 0;

    // 触发表格高度重新计算
    recalculateTrigger.value++;

    // 触发表格高度重新计算
    recalculateTrigger.value++;
  } catch (error) {
    console.error("加载角色数据失败", error);
    ElMessage.error("加载角色列表失败");
  } finally {
    loading.value = false;
  }
};

// 打开添加角色对话框
const handleAddRole = () => {
  roleFormRef.value.openForm("add");
};

// 打开编辑角色对话框
const handleEditRole = (role) => {
  roleFormRef.value.openForm("edit", role._id);
};

// 处理删除角色
const handleDeleteRole = async (role) => {
  if (!role || !role._id) {
    ElMessage.error("角色数据不完整，无法删除");
    return;
  }

  // 系统预设角色不能删除
  if (role.isSystem) {
    ElMessage.warning("系统预设角色不能删除");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除角色 "${role.name}" 吗？删除后无法恢复！`,
      "删除提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await deleteRole(role._id);
    ElMessage.success("删除成功");
    // 刷新数据
    loadRoleData();
  } catch (error) {
    if (error === "cancel") return;
    console.error("删除角色失败", error);
    ElMessage.error("删除失败：" + (error.message || "未知错误"));
  }
};

// 加载初始数据
onMounted(() => {
  loadRoleData();
});
</script>

<style scoped>
.role-form {
  padding-right: 16px;
}
</style>
