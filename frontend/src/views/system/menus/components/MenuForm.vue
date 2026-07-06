<template>
  <!-- 弹框默认打开，通过 v-if控制是否展示隐藏 -->

  <el-dialog
    v-model="dialogVisible"
    :title="getFormTitle"
    :width="isMobile ? '95%' : '700px'"
    :close-on-click-modal="false"
    append-to-body
    destroy-on-close
    class="menu-form-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :label-width="isMobile ? '90px' : '100px'"
      class="overflow-y-auto pr-2 md:pr-4"
      :style="{ maxHeight: isMobile ? '50vh' : '60vh' }"
      v-loading="loading"
    >
      <!-- 基本信息区域 -->
      <div class="form-section mb-4">
        <div
          class="section-title mb-2 text-gray-500 text-sm font-medium border-b pb-1"
        >
          基本信息
        </div>

        <!-- 第一行：菜单类型和上级菜单 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="菜单类型" prop="type">
            <el-radio-group v-model="form.type" :disabled="formType === 'edit'">
              <el-radio-button :value="'menu'">菜单</el-radio-button>
              <el-radio-button :value="'button'">按钮</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="上级菜单" prop="parentId" required>
            <el-cascader
              v-model="form.parentId"
              :options="menuCascaderOptions"
              :props="cascaderProps"
              :show-all-levels="false"
              placeholder="请选择上级菜单"
              :disabled="formType === 'addSubmenu'"
              clearable
              filterable
              style="width: 100%"
            />
          </el-form-item>
        </div>

        <!-- 第二行：菜单名称和编码 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
          <el-form-item label="菜单名称" prop="name">
            <el-input v-model="form.name" placeholder="请输入菜单名称" />
          </el-form-item>

          <el-form-item label="权限编码" prop="code">
            <el-input
              v-model="form.code"
              placeholder="请输入权限编码"
              :disabled="formType === 'edit'"
            />
          </el-form-item>
        </div>
        <div class="mt-1 text-gray-400 text-xs ml-24">
          <span v-if="form.type === 'menu'"
            >菜单权限编码创建后不可修改，用于系统识别和前端菜单权限控制</span
          >
          <span v-else
            >按钮权限编码创建后不可修改，用于前端按钮权限控制和后端API权限验证</span
          >
        </div>
      </div>

      <!-- 路由配置区域 - 仅菜单类型显示 -->
      <div v-if="form.type === 'menu'" class="form-section mb-4">
        <div
          class="section-title mb-2 text-gray-500 text-sm font-medium border-b pb-1"
        >
          路由配置
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="路由路径" prop="path">
            <el-input
              v-model="form.path"
              placeholder="请输入路由路径，以/开头"
            />
          </el-form-item>

          <el-form-item label="组件路径" prop="component">
            <el-input v-model="form.component" placeholder="请输入组件路径" />
          </el-form-item>
        </div>

        <!-- 放在一行 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="重定向" prop="redirect">
            <el-input
              v-model="form.redirect"
              placeholder="顶级菜单可填写默认重定向的子页面路径"
            />
          </el-form-item>

          <el-form-item label="图标" prop="icon">
            <el-input v-model="form.icon" placeholder="请输入图标名称" />
          </el-form-item>
        </div>
      </div>

      <!-- 其他设置区域 -->
      <div class="form-section mb-4">
        <div
          class="section-title mb-2 text-gray-500 text-sm font-medium border-b pb-1"
        >
          其他设置
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="排序" prop="sort">
            <el-input-number
              v-model="form.sort"
              :min="0"
              :max="1000"
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="菜单状态" prop="status">
            <el-radio-group v-model="form.status">
              <el-radio :value="'active'">正常</el-radio>
              <el-radio :value="'inactive'">禁用</el-radio>
            </el-radio-group>
          </el-form-item>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="是否隐藏" prop="hidden">
            <el-switch v-model="form.hidden" />
            <span class="text-gray-400 text-xs ml-2">隐藏后不在菜单中显示</span>
          </el-form-item>

          <el-form-item
            label="页面缓存"
            prop="meta.keepAlive"
            v-if="form.type === 'menu'"
          >
            <el-switch v-model="form.meta.keepAlive" />
            <span class="text-gray-400 text-xs ml-2">开启后页面会被缓存</span>
          </el-form-item>
        </div>

        <div
          class="grid grid-cols-1 md:grid-cols-2 gap-4"
          v-if="form.type === 'menu'"
        >
          <el-form-item label="页面标题" prop="meta.title">
            <el-input
              v-model="form.meta.title"
              placeholder="页面标题，默认与菜单名称一致"
            />
          </el-form-item>

          <el-form-item label="是否验证" prop="meta.requireAuth">
            <el-switch v-model="form.meta.requireAuth" />
            <span class="text-gray-400 text-xs ml-2">开启后需要登录</span>
          </el-form-item>
        </div>
      </div>
    </el-form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading"
          >确定</el-button
        >
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { getMenuById, createMenu, updateMenu, getMenuList } from "@/api/menu";

// 定义默认表单数据常量
const DEFAULT_FORM = {
  name: "",
  code: "",
  path: "",
  component: "",
  redirect: "",
  type: "menu",
  parentId: "0",
  icon: "",
  sort: 0,
  hidden: false,
  status: "active",
  meta: {
    title: "",
    keepAlive: false,
    requireAuth: true,
  },
};

// 简化props，只保留必要属性
const props = defineProps({
  modelValue: Boolean,
  isMobile: {
    type: Boolean,
    default: false,
  },
});

// 简化emits，只保留必要事件
const emit = defineEmits(["success"]);

// 内部状态管理
const formType = ref("add"); // add, edit, addSubmenu
const currentId = ref(""); // 当前编辑的菜单ID
const loading = ref(false); // 加载状态
const submitLoading = ref(false); // 提交状态
const menuList = ref([]); // 菜单列表数据
const menuListLoading = ref(false);

// 表单引用
const formRef = ref(null);

// 对话框可见状态
const dialogVisible = ref(false);
// 动态表单标题
const getFormTitle = computed(() => {
  const titles = {
    add: "新增菜单",
    edit: "编辑菜单",
    addSubmenu: "新增子菜单",
  };
  return titles[formType.value] || "菜单表单";
});

// 使用深拷贝创建表单数据
const createFormData = () => JSON.parse(JSON.stringify(DEFAULT_FORM));

// 表单数据
const form = reactive(createFormData());

// 表单校验规则
const rules = reactive({
  name: [{ required: true, message: "请输入菜单名称", trigger: "blur" }],
  code: [{ required: true, message: "请输入菜单编码", trigger: "blur" }],
  path: [{ required: true, message: "请输入路由路径", trigger: "blur" }],
  type: [{ required: true, message: "请选择菜单类型", trigger: "change" }],
  parentId: [{ required: true, message: "请选择上级菜单", trigger: "change" }],
  sort: [{ required: true, message: "请输入排序号", trigger: "blur" }],
});

// 级联选择器配置
const cascaderProps = {
  value: "_id",
  label: "name",
  children: "children",
  checkStrictly: true,
  emitPath: false,
};

// 加载所有菜单列表
const loadAllMenus = async () => {
  try {
    menuListLoading.value = true;
    const data = await getMenuList({ tree: "true" });
    menuList.value = Array.isArray(data) ? data : [];
  } catch (error) {
    // console.error('加载菜单列表失败', error)
  } finally {
    menuListLoading.value = false;
  }
};

// 计算属性：级联选择器数据
const menuCascaderOptions = computed(() => {
  // 创建顶级菜单选项
  const rootOption = { _id: "0", name: "顶级菜单", children: [] };

  // 如果没有菜单数据，直接返回
  if (!menuList.value || menuList.value.length === 0) {
    return [rootOption];
  }

  // 获取当前编辑的菜单ID（如果是编辑模式）
  const currentMenuId = currentId.value;

  // 递归处理菜单项，标记按钮和当前编辑菜单为禁用状态
  const processMenuItems = (items) => {
    return items.map((item) => {
      // 创建新的菜单项对象，只包含必要属性
      const newItem = {
        _id: item._id,
        name: item.name,
        type: item.type,
        // 禁用条件：1. 是按钮类型 2. 是当前正在编辑的菜单
        disabled: item.type === "button" || item._id === currentMenuId,
      };

      // 处理子菜单
      if (item.children && item.children.length > 0) {
        newItem.children = processMenuItems(item.children);
      }

      return newItem;
    });
  };

  // 处理菜单项
  rootOption.children = processMenuItems(menuList.value);
  return [rootOption];
});

// 重置表单到默认状态
const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields();
  }

  // 使用深拷贝重置表单数据
  Object.assign(form, createFormData());

  // 重置内部状态
  currentId.value = "";
};

// 初始化新增表单数据
const initAddForm = (parentId = "") => {
  // 先重置表单
  resetForm();

  // 如果有父级ID，设置父级ID
  if (parentId) {
    form.parentId = parentId;
  }
};

// 初始化编辑表单数据
const initEditForm = (menuData) => {
  // 先重置表单
  resetForm();
  console.log(menuData, "menuData");

  // 设置当前ID
  currentId.value = menuData._id;

  // 设置表单数据 - 确保所有字段都有默认值
  Object.assign(form, {
    ...createFormData(), // 先用默认值初始化
    ...menuData,
    parentId: menuData.parentId || "0", // 再用实际数据覆盖
    meta: {
      ...createFormData().meta, // 先用默认值初始化meta
      ...(menuData.meta || {}), // 再用实际数据覆盖
    },
  });
};

// 加载菜单详情数据
const loadMenuDetail = async (id) => {
  if (!id) return;

  try {
    loading.value = true;
    const menuDetail = await getMenuById(id);
    initEditForm(menuDetail);
  } catch (error) {
    console.error("获取菜单详情失败", error);
    ElMessage.error("获取菜单详情失败");
  } finally {
    loading.value = false;
  }
};

// 对外暴露的方法 - 打开表单
const openForm = async (type = "add", id = "", parentId = "") => {
  formType.value = type;
  dialogVisible.value = true;
  try {
    // 加载最新的菜单列表
    await loadAllMenus();
    if (type === "edit" && id) {
      await loadMenuDetail(id);
    } else if (type === "addSubmenu" && parentId) {
      initAddForm(parentId);
    } else {
      initAddForm();
    }
  } catch (error) {
    console.error("初始化表单失败", error);
    ElMessage.error("初始化表单失败");
  }
};

// 准备提交数据 - 处理特殊字段
const prepareSubmitData = (formData, isEdit) => {
  const data = { ...formData };

  // 处理按钮类型的特殊逻辑
  if (data.type === "button") {
    data.component = "";
    data.redirect = "";
  }

  // 确保meta存在且title与name同步
  if (!data.meta) data.meta = {};
  data.meta.title = data.name;

  // 处理更新和创建的不同字段要求
  if (isEdit) {
    const id = data._id; // 保存ID用于API调用

    // 更新时移除不可修改字段 - 确保移除_id和__v等系统字段
    const {
      _id,
      __v,
      code,
      type,
      isSystem,
      createdAt,
      updatedAt,
      createdBy,
      children,
      permission,
      ...updateData
    } = data;

    return { id, data: updateData };
  } else {
    // 创建时移除不需要的字段
    const {
      _id,
      __v,
      isSystem,
      createdAt,
      updatedAt,
      createdBy,
      children,
      permission,
      ...createData
    } = data;
    return { data: createData };
  }
};

// 取消
const handleCancel = () => {
  dialogVisible.value = false;
  resetForm();
};

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return;

  try {
    const valid = await formRef.value.validate();
    if (!valid) return;

    submitLoading.value = true;

    // 准备提交数据
    const isEdit = formType.value === "edit";
    const { id, data } = prepareSubmitData(form, isEdit);

    // 调用API
    if (isEdit) {
      await updateMenu(id, data);
      ElMessage.success("更新成功");
    } else {
      await createMenu(data);
      ElMessage.success("创建成功");
    }

    // 提交成功，关闭对话框
    dialogVisible.value = false;

    // 触发成功事件，通知父组件刷新数据
    emit("success");
  } catch (error) {
    console.error("提交表单失败", error);
    ElMessage.error("操作失败，请检查表单数据");
  } finally {
    submitLoading.value = false;
  }
};

// 监听相关字段变化，实现自动设置值
watch(
  () => form.name,
  (newName) => {
    if (form.meta && !form.meta.title) {
      form.meta.title = newName;
    }
  }
);

// 暴露方法给父组件
defineExpose({
  openForm,
  resetForm,
});
</script>

<style scoped>
:deep(.el-dialog__header) {
  @apply py-4 px-5 border-b border-gray-200 m-0;
}

:deep(.el-dialog__body) {
  @apply p-5;
}

:deep(.el-dialog__footer) {
  @apply py-4 px-5 border-t border-gray-200;
}

/* 移动端适配 */
@media (max-width: 768px) {
  :deep(.el-form-item__label) {
    @apply text-sm;
  }

  :deep(.el-dialog__body) {
    @apply p-4;
  }
}
</style>
