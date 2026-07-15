<!-- 管理员班级管理页面 -->
<template>
  <div class="classes-management">
    <!-- 页面头部 -->
    <div class="page-header-bar">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">班级管理</h1>
        <p class="text-gray-600 mt-1">管理所有班级，可代任意教师创建/编辑/解散班级</p>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          :icon="Plus"
          @click="handleCreateClass"
          size="default"
        >
          创建班级
        </el-button>
        <el-button
          :icon="Refresh"
          @click="refreshData"
          :loading="loading"
          size="default"
        >
          刷新
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <div class="search-section">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <div class="search-row">
          <el-form-item label="班级名称">
            <el-input
              v-model="searchForm.search"
              placeholder="搜索班级名称"
              :prefix-icon="Search"
              clearable
              style="width: 200px"
              @keyup.enter="handleSearch"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select
              v-model="searchForm.status"
              placeholder="选择状态"
              clearable
              style="width: 120px"
            >
              <el-option label="活跃" value="active" />
              <el-option label="暂停" value="inactive" />
              <el-option label="已解散" value="disbanded" />
            </el-select>
          </el-form-item>
          <el-form-item label="教师">
            <el-select
              v-model="searchForm.teacherId"
              placeholder="选择教师"
              clearable
              filterable
              style="width: 160px"
            >
              <el-option
                v-for="t in teacherList"
                :key="t.id"
                :label="t.name"
                :value="t.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
          <el-form-item class="ml-auto">
            <el-button-group>
              <el-button
                :type="viewMode === 'grid' ? 'primary' : 'default'"
                :icon="Operation"
                size="default"
                @click="viewMode = 'grid'"
              />
              <el-button
                :type="viewMode === 'list' ? 'primary' : 'default'"
                :icon="Menu"
                size="default"
                @click="viewMode = 'list'"
              />
            </el-button-group>
          </el-form-item>
        </div>
      </el-form>
    </div>

    <!-- 班级列表 -->
    <div class="content-section" v-loading="loading" element-loading-text="加载中...">
      <div v-if="classList.length === 0" class="empty-state">
        <div class="empty-icon">📚</div>
        <h3 class="empty-title">暂无班级</h3>
        <p class="empty-desc">点击"创建班级"按钮开始管理班级</p>
        <el-button type="primary" :icon="Plus" @click="handleCreateClass">创建班级</el-button>
      </div>

      <!-- 使用教师端的 ClassCard 组件 -->
      <div v-else-if="viewMode === 'grid'" class="classes-grid">
        <TeacherClassCard
          v-for="item in classList"
          :key="item._id"
          :class-data="item"
          view-mode="grid"
          @view="handleViewClass"
          @edit="handleEditClass"
          @disband="handleDeleteClass"
          @regenerate-code="handleRegenerateCode"
        />
      </div>

      <div v-else class="classes-list">
        <TeacherClassCard
          v-for="item in classList"
          :key="item._id"
          :class-data="item"
          view-mode="list"
          @view="handleViewClass"
          @edit="handleEditClass"
          @disband="handleDeleteClass"
          @regenerate-code="handleRegenerateCode"
        />
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="pagination.total > 0" class="pagination-section">
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.limit"
        :page-sizes="[3, 6, 10, 24, 48]"
        :total="pagination.total"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 创建/编辑班级对话框（管理员版，可选教师） -->
    <AdminCreateClassDialog
      v-model="showCreateDialog"
      :class-data="editingClass"
      :teachers="teacherList"
      @success="handleCreateSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Refresh, Search, Operation, Menu } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";
import {
  getClassList,
  disbandClass,
  regenerateClassCode,
} from "../../../api/classes";
import { getUsers } from "@/api/user";
import type { Class } from "../../../types/classes";
import TeacherClassCard from "../../teacher/classes/components/ClassCard.vue";
import AdminCreateClassDialog from "./components/AdminCreateClassDialog.vue";

const router = useRouter();

// 状态
const loading = ref(false);
const classList = ref<Class[]>([]);
const teacherList = ref<{ id: number; name: string }[]>([]);
const showCreateDialog = ref(false);
const editingClass = ref<Class | null>(null);
const viewMode = ref<"grid" | "list">("grid");

const searchForm = reactive({
  search: "",
  status: "" as string,
  teacherId: null as number | null,
});

const pagination = reactive({ page: 1, limit: 10, total: 0 });

// 加载教师列表
const loadTeachers = async () => {
  try {
    const res = await getUsers({ role: "teacher", limit: 100, page: 1 });
    // 适配后端返回格式
    const items = (res as any).items || res || [];
    teacherList.value = items.map((u: any) => ({ id: parseInt(u._id) || u.id, name: u.name }));
  } catch (e) {
    console.error("加载教师列表失败:", e);
  }
};

// 加载班级列表
const loadClassList = async () => {
  loading.value = true;
  try {
    const params: any = {
      page: pagination.page,
      limit: pagination.limit,
    };
    if (searchForm.search) params.search = searchForm.search;
    if (searchForm.status) params.status = searchForm.status;
    if (searchForm.teacherId) params.teacherId = searchForm.teacherId;

    const response = await getClassList(params);
    classList.value = (response as any).items || [];
    pagination.total = (response as any).total || 0;
  } catch (error) {
    console.error("加载班级列表失败:", error);
  } finally {
    loading.value = false;
  }
};

// 搜索
const handleSearch = () => { pagination.page = 1; loadClassList(); };
const resetSearch = () => {
  searchForm.search = "";
  searchForm.status = "";
  searchForm.teacherId = null;
  pagination.page = 1;
  loadClassList();
};
const refreshData = () => loadClassList();

// 分页
const handleSizeChange = (size: number) => { pagination.limit = size; loadClassList(); };
const handleCurrentChange = (page: number) => { pagination.page = page; loadClassList(); };

// 创建班级
const handleCreateClass = () => {
  editingClass.value = null;
  showCreateDialog.value = true;
};

// 查看
const handleViewClass = (classData: Class) => {
  router.push({ path: "/teacher/classes/detail", query: { id: (classData as any)._id } });
};

// 编辑
const handleEditClass = (classData: Class) => {
  editingClass.value = classData;
  showCreateDialog.value = true;
};

// 删除/解散
const handleDeleteClass = async (classData: Class) => {
  try {
    await ElMessageBox.confirm(
      `确定要解散班级"${classData.name}"吗？此操作不可撤销，班级内的学生将无法再查看该班级。`,
      "确认解散",
      { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" }
    );
    await disbandClass((classData as any)._id);
    ElMessage.success("班级已解散");
    loadClassList();
  } catch (error: any) {
    if (error !== "cancel") console.error("解散班级失败:", error);
  }
};

// 刷新邀请码
const handleRegenerateCode = async (classData: Class) => {
  try {
    await ElMessageBox.confirm(
      `确定要刷新班级"${classData.name}"的邀请码吗？旧邀请码将失效。`,
      "确认刷新",
      { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" }
    );
    const response: any = await regenerateClassCode((classData as any)._id);
    ElMessage.success(`新邀请码：${response.inviteCode || response.code}`);
    loadClassList();
  } catch (error: any) {
    if (error !== "cancel") console.error("刷新邀请码失败:", error);
  }
};

const handleCreateSuccess = () => {
  showCreateDialog.value = false;
  editingClass.value = null;
  loadClassList();
};

onMounted(() => {
  loadTeachers();
  loadClassList();
});
</script>

<style scoped>
.classes-management { padding: 20px; background: #fff; border-radius: 8px; }
.page-header-bar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #e4e7ed; }
.header-actions { display: flex; gap: 12px; }
.search-section { margin-bottom: 20px; }
.search-form { background: #fafafa; padding: 16px 20px; border-radius: 8px; border: 1px solid #e5e7eb; }
.search-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
.content-section { min-height: 400px; background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.classes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
.classes-list { display: flex; flex-direction: column; gap: 12px; }
.empty-state { text-align: center; padding: 80px 20px; }
.empty-icon { font-size: 64px; margin-bottom: 20px; }
.empty-title { font-size: 20px; font-weight: 600; color: #1f2937; margin: 0 0 12px 0; }
.empty-desc { font-size: 14px; color: #6b7280; margin: 0 0 24px 0; }
.pagination-section { margin-top: 24px; display: flex; justify-content: center; }
</style>
