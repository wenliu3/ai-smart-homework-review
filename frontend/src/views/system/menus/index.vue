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
        <el-form-item label="菜单名称">
          <el-input
            v-model="searchForm.name"
            placeholder="请输入菜单名称"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="路径">
          <el-input
            v-model="searchForm.path"
            placeholder="请输入菜单路径"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="菜单状态"
            clearable
            style="width: 120px"
          >
            <el-option label="全部" value="" />
            <el-option label="正常" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示状态">
          <el-select
            v-model="searchForm.hidden"
            placeholder="显示状态"
            clearable
            style="width: 120px"
          >
            <el-option label="全部" value="" />
            <el-option label="显示" :value="false" />
            <el-option label="隐藏" :value="true" />
          </el-select>
        </el-form-item>
        <el-form-item class="mb-0 flex-shrink-0">
          <el-button type="primary" @click="loadMenuData">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><Refresh /></el-icon>重置
          </el-button>
          <el-button type="primary" @click="handleAddMenu">
            <el-icon><Plus /></el-icon>新增
          </el-button>
          <el-button @click="toggleExpandAll">
            {{ expandAll ? "折叠" : "展开" }}
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <!-- 表格区域 -->
    <template #table="{ tableHeight }">
      <menu-table
        class="h-full"
        :menu-data="menuList"
        :max-height="tableHeight"
        :loading="loading"
        :default-expand-all="expandAll"
        :is-mobile="isMobile"
        @add-submenu="handleAddSubmenu"
        @edit="handleEditMenu"
        @delete="handleDeleteMenu"
        ref="menuTableRef"
      />
    </template>

    <!-- 其他组件 -->
    <template #extra>
      <!-- 菜单表单 -->
      <menu-form
        :is-mobile="isMobile"
        @success="loadMenuData"
        ref="menuFormRef"
      />
    </template>
  </adaptive-table-container>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getMenuList, deleteMenu } from "@/api/menu";
import { useStore } from "vuex";
import { Search, Refresh, Plus } from "@element-plus/icons-vue";

// 导入组件
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";
import MenuTable from "./components/MenuTable.vue";
import MenuForm from "./components/MenuForm.vue";

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
  status: "",
  path: "",
  hidden: "", // 默认为空字符串，表示不筛选
});

// 数据状态
const loading = ref(true);
const menuList = ref([]);

// 组件引用
const adaptiveTableRef = ref(null);
const menuFormRef = ref(null);

// 触发重新计算表格高度的计数器
const recalculateTrigger = ref(0);

// 重置搜索
const resetSearch = () => {
  // 重置所有搜索条件
  searchForm.name = "";
  searchForm.path = "";
  searchForm.status = "";
  searchForm.hidden = "";
  loadMenuData();
};

// 树形展开控制
const expandAll = ref(false);
const menuTableRef = ref();

// 切换展开/折叠状态
const toggleExpandAll = () => {
  if (expandAll.value) {
    expandAll.value = false;
    menuTableRef.value.collapseAll();
  } else {
    expandAll.value = true;
    menuTableRef.value.expandAll();
  }
};

// 加载菜单数据
const loadMenuData = async () => {
  loading.value = true;
  try {
    // 构建查询参数
    const params = {
      tree: "true", // 请求树形结构数据
    };

    // 添加搜索条件
    if (searchForm.name) params.name = searchForm.name;
    if (searchForm.path) params.path = searchForm.path;
    if (searchForm.status) params.status = searchForm.status;

    // 特殊处理隐藏状态
    if (searchForm.hidden !== "") {
      // 确保布尔值被正确传递为字符串
      params.hidden =
        searchForm.hidden === true || searchForm.hidden === "true"
          ? "true"
          : "false";
      console.log(
        "发送hidden参数:",
        params.hidden,
        "原始值类型:",
        typeof searchForm.hidden
      );
    }

    console.log("发送菜单搜索请求参数:", params);
    const data = await getMenuList(params);
    console.log("接收到的菜单数据:", data?.length || 0, "条记录");
    menuList.value = Array.isArray(data) ? data : [];

    // 触发表格高度重新计算
    recalculateTrigger.value++;
  } catch (error) {
    console.error("加载菜单失败", error);
    //ElMessage.error('加载菜单列表失败')
  } finally {
    loading.value = false;
  }
};

// 打开添加菜单对话框
const handleAddMenu = () => {
  nextTick(() => {
    menuFormRef.value.openForm("add");
  });
};

// 打开添加子菜单对话框
const handleAddSubmenu = (parentId) => {
  nextTick(() => {
    menuFormRef.value.openForm("addSubmenu", "", parentId);
  });
};

// 打开编辑菜单对话框
const handleEditMenu = (menu) => {
  nextTick(() => {
    menuFormRef.value.openForm("edit", menu._id);
  });
};

// 处理删除菜单
const handleDeleteMenu = async (menu) => {
  if (!menu || !menu._id) {
    ElMessage.error("菜单数据不完整，无法删除");
    return;
  }

  // 检查子菜单
  if (menu.children && menu.children.length > 0) {
    ElMessage.warning("该菜单下还有子菜单，不能删除");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除菜单 "${menu.name}" 吗？`,
      "删除提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await deleteMenu(menu._id);
    ElMessage.success("删除成功");
    // 刷新数据
    loadMenuData();
  } catch (error) {
    if (error === "cancel") return;
    console.error("删除菜单失败", error);
    ElMessage.error("删除失败");
  }
};

// 加载初始数据
onMounted(() => {
  loadMenuData();
});
</script>
