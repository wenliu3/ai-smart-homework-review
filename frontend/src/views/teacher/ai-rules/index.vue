<template>
  <div class="w-full">
    <!-- 搜索和操作区域 -->
    <!-- 搜索表单 -->
    <el-form
      :inline="true"
      :model="searchForm"
      size="default"
      class="flex flex-wrap items-center"
    >
      <el-form-item label="规则名称">
        <el-input
          v-model="searchForm.search"
          placeholder="请输入规则名称"
          clearable
          style="width: 180px"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select
          v-model="searchForm.status"
          placeholder="规则状态"
          clearable
          style="width: 120px"
        >
          <el-option label="全部" value="" />
          <el-option label="启用" value="active" />
          <el-option label="禁用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item label="可见性">
        <el-select
          v-model="searchForm.visibility"
          placeholder="可见性"
          clearable
          style="width: 120px"
        >
          <el-option label="全部" value="" />
          <el-option label="私有" value="private" />
          <el-option label="公开" value="public" />
          <el-option label="系统" value="system" />
        </el-select>
      </el-form-item>
      <el-form-item label="模型类型">
        <el-select
          v-model="searchForm.modelType"
          placeholder="模型类型"
          clearable
          style="width: 140px"
        >
          <el-option label="全部" value="" />
          <el-option label="DeepSeek" value="deepseek" />
          <el-option label="小米" value="mimo" />
        </el-select>
      </el-form-item>
      <el-form-item class="mb-0 flex-shrink-0">
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>搜索
        </el-button>
        <el-button @click="resetSearch">
          <el-icon><Refresh /></el-icon>重置
        </el-button>
        <el-button type="primary" @click="handleAddRule">
          <el-icon><Plus /></el-icon>新增
        </el-button>
      </el-form-item>
    </el-form>

    <!-- AI规则列表 -->
    <el-card
      shadow="never"
      v-loading="loading"
      element-loading-text="加载中..."
    >
      <!-- AI规则表格 -->
      <ai-rule-table
        :rule-data="ruleList"
        :loading="loading"
        :is-mobile="isMobile"
        :current-user="currentUser"
        @edit="handleEditRule"
        @delete="handleDeleteRule"
        @copy="handleCopyRule"
        @view="handleViewRule"
      />

      <!-- 分页 -->
      <div class="flex justify-end mt-4">
        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- AI规则表单 -->
    <ai-rule-form
      :is-mobile="isMobile"
      @success="loadRuleData"
      ref="ruleFormRef"
    />

    <!-- AI规则详情 -->
    <ai-rule-detail
      @success="loadRuleData"
      @edit="handleEditFromDetail"
      ref="ruleDetailRef"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getAiRuleList, deleteAiRule, copyAiRule } from "../../../api/ai-rule";
import { Plus, Refresh, Search } from "@element-plus/icons-vue";
import { useStore } from "vuex";

// 导入组件
import AdaptiveTableContainer from "@/components/AdaptiveTableContainer.vue";
import AiRuleTable from "./components/AiRuleTable.vue";
import AiRuleForm from "./components/AiRuleForm.vue";
import AiRuleDetail from "./components/AiRuleDetail.vue";

// Store
const store = useStore();

// 响应式设计 - 检测设备类型
const device = computed(() => store.getters["app/device"]);
const isMobile = computed(
  () => device.value === "mobile" || device.value === "tablet"
);

// 获取当前用户信息
const currentUser = computed(() => store.getters["user/getUserInfo"]);

// 搜索表单数据
const searchForm = reactive({
  search: "",
  status: "",
  visibility: "",
  modelType: "",
});

// 分页数据
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});

// 数据状态
const loading = ref(false);
const ruleList = ref([]);

// 组件引用
const adaptiveTableRef = ref(null);
const ruleFormRef = ref(null);
const ruleDetailRef = ref(null);

// 触发重新计算表格高度的计数器
const recalculateTrigger = ref(0);

// 重置搜索
const resetSearch = () => {
  searchForm.search = "";
  searchForm.status = "";
  searchForm.visibility = "";
  searchForm.modelType = "";
  pagination.page = 1;
  loadRuleData();
};

// 处理搜索
const handleSearch = () => {
  pagination.page = 1;
  loadRuleData();
};

// 处理分页变化
const handleSizeChange = (val) => {
  pagination.pageSize = val;
  loadRuleData();
};

const handleCurrentChange = (val) => {
  pagination.page = val;
  loadRuleData();
};

// 加载AI规则数据
const loadRuleData = async () => {
  loading.value = true;
  try {
    // 构建查询参数
    const params: any = {
      page: pagination.page,
      pageSize: pagination.pageSize,
    };

    // 添加搜索条件
    if (searchForm.search) params.search = searchForm.search;
    if (searchForm.status) params.status = searchForm.status;
    if (searchForm.visibility) params.visibility = searchForm.visibility;
    if (searchForm.modelType) params.modelType = searchForm.modelType;

    const response = await getAiRuleList(params);
    ruleList.value = response.items || [];
    pagination.total = response.total || 0;

    // 触发表格高度重新计算
    recalculateTrigger.value++;
  } catch (error) {
    console.error("加载AI规则数据失败", error);
    ElMessage.error("加载AI规则列表失败");
  } finally {
    loading.value = false;
  }
};

// 打开添加规则对话框
const handleAddRule = () => {
  ruleFormRef.value.openForm("add");
};

// 打开编辑规则对话框
const handleEditRule = (rule) => {
  ruleFormRef.value.openForm("edit", rule.id);
};

// 查看规则详情
const handleViewRule = (rule) => {
  ruleDetailRef.value.openDetail(rule.id);
};

// 从详情页面编辑规则
const handleEditFromDetail = (rule) => {
  ruleFormRef.value.openForm("edit", rule.id);
};

// 处理删除规则
const handleDeleteRule = async (rule) => {
  if (!rule || !rule.id) {
    ElMessage.error("规则数据不完整，无法删除");
    return;
  }

  // 系统规则不能删除
  if (rule.visibility === "system") {
    ElMessage.warning("系统规则不能删除");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除规则 "${rule.name}" 吗？删除后无法恢复！`,
      "删除提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );

    await deleteAiRule(rule.id);
    ElMessage.success("删除成功");
    // 刷新数据
    loadRuleData();
  } catch (error) {
    if (error === "cancel") return;
    console.error("删除规则失败", error);
    ElMessage.error("删除失败：" + (error.message || "未知错误"));
  }
};

// 处理复制规则
const handleCopyRule = async (rule) => {
  if (!rule || !rule.id) {
    ElMessage.error("规则数据不完整，无法复制");
    return;
  }

  try {
    await ElMessageBox.prompt("请输入新规则名称", "复制规则", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputValue: `${rule.name} - 副本`,
      inputValidator: (value) => {
        if (!value || value.trim() === "") {
          return "规则名称不能为空";
        }
        if (value.length > 50) {
          return "规则名称不能超过50个字符";
        }
        return true;
      },
    }).then(async ({ value }) => {
      await copyAiRule(rule.id, value.trim());
      ElMessage.success("复制成功");
      // 刷新数据
      loadRuleData();
    });
  } catch (error) {
    if (error === "cancel") return;
    console.error("复制规则失败", error);
    ElMessage.error("复制失败：" + (error.message || "未知错误"));
  }
};

// 加载初始数据
onMounted(() => {
  loadRuleData();
});
</script>

<style scoped>
.ai-rule-form {
  padding-right: 16px;
}
</style>
