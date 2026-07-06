<template>
  <el-dialog
    v-model="dialogVisible"
    :title="getFormTitle"
    :width="isMobile ? '95%' : '650px'"
    :close-on-click-modal="false"
    append-to-body
    destroy-on-close
    class="role-form-dialog"
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

        <!-- 角色名称 -->
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入角色名称" />
        </el-form-item>

        <!-- 角色编码 -->
        <el-form-item label="角色编码" prop="code">
          <el-input
            v-model="form.code"
            placeholder="请输入角色编码"
            :disabled="formType === 'edit'"
          />
          <div class="text-gray-400 text-xs mt-1">
            角色编码是唯一标识，创建后不能修改。例如：admin、teacher
          </div>
        </el-form-item>

        <!-- 角色描述 -->
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            placeholder="请输入角色描述"
            :rows="3"
          />
        </el-form-item>
      </div>

      <!-- 菜单权限区域 -->
      <div class="form-section mb-4">
        <div
          class="section-title mb-2 text-gray-500 text-sm font-medium border-b pb-1"
        >
          菜单权限
        </div>

        <el-alert type="info" show-icon class="mb-2">
          <div>
            <div>选择菜单后会自动包含其中的按钮权限</div>
            <div>选中父级菜单会自动选中所有子菜单</div>
            <div class="text-red-500">状态为"禁用"的菜单无法选择</div>
          </div>
        </el-alert>

        <div class="menu-tree-container">
          <el-tree
            ref="menuTreeRef"
            :data="menuTreeData"
            node-key="_id"
            show-checkbox
            default-expand-all
            :props="{
              label: 'name',
              children: 'children',
              disabled: 'disabled',
            }"
            v-loading="menuTreeLoading"
          >
            <template #default="{ data }">
              <div class="flex items-center">
                <span :class="{ 'text-gray-400': data.status === 'inactive' }">
                  {{ data.name }}
                </span>
                <el-tag
                  v-if="data.status === 'inactive'"
                  size="small"
                  type="info"
                  class="ml-2"
                  >禁用</el-tag
                >
              </div>
            </template>
          </el-tree>
        </div>
      </div>

      <!-- 其他设置区域 -->
      <div class="form-section mb-4">
        <div
          class="section-title mb-2 text-gray-500 text-sm font-medium border-b pb-1"
        >
          其他设置
        </div>

        <!-- 角色状态 -->
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio :value="'active'">正常</el-radio>
            <el-radio :value="'inactive'">禁用</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 备注信息 -->
        <el-form-item label="备注" prop="remark">
          <el-input
            v-model="form.remark"
            type="textarea"
            placeholder="请输入备注信息"
            :rows="2"
          />
        </el-form-item>
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
import { ref, reactive, computed, nextTick } from "vue";
import { ElMessage } from "element-plus";
import { getRoleWithMenus, createRole, updateRole } from "@/api/role";
import { getMenuList } from "@/api/menu";

// 组件props和emits
const props = defineProps({
  isMobile: { type: Boolean, default: false },
});
const emit = defineEmits(["success"]);

// 表单默认数据
const DEFAULT_FORM = {
  name: "",
  code: "",
  description: "",
  status: "active",
  remark: "",
  menuIds: [],
};

// 表单数据和辅助函数
const createFormData = () => JSON.parse(JSON.stringify(DEFAULT_FORM));
const form = reactive(createFormData());

// 状态管理
const formType = ref("add");
const currentId = ref("");
const loading = ref(false);
const submitLoading = ref(false);
const menuTreeLoading = ref(false);
const menuTreeData = ref([]);
const formRef = ref(null);
const menuTreeRef = ref(null);
const dialogVisible = ref(false);

// 表单标题
const getFormTitle = computed(() =>
  formType.value === "add" ? "新增角色" : "编辑角色"
);

// 表单校验规则
const rules = reactive({
  name: [{ required: true, message: "请输入角色名称", trigger: "blur" }],
  code: [
    { required: true, message: "请输入角色编码", trigger: "blur" },
    {
      pattern: /^[a-z][a-z0-9_]*$/,
      message: "角色编码只能包含小写字母、数字和下划线，且必须以字母开头",
      trigger: "blur",
    },
  ],
  description: [{ required: true, message: "请输入角色描述", trigger: "blur" }],
  status: [{ required: true, message: "请选择角色状态", trigger: "change" }],
});

// 打开表单
const openForm = async (type, id) => {
  // 重置表单
  resetForm();

  // 设置表单类型和显示对话框
  formType.value = type;
  currentId.value = id || "";
  dialogVisible.value = true;

  try {
    // 先加载菜单树，再加载角色数据
    await loadMenuTreeData();

    // 如果是编辑模式，加载角色数据
    if (type === "edit" && id) {
      await loadRoleData(id);
    }

    // 等待DOM更新后，聚焦第一个输入框
    nextTick(() => {
      const firstInput = formRef.value?.$el.querySelector("input");
      if (firstInput) firstInput.focus();
    });
  } catch (error) {
    console.error("初始化表单失败", error);
    ElMessage.error("表单初始化失败");
  }
};

// 加载角色数据
const loadRoleData = async (id) => {
  loading.value = true;
  try {
    // 使用getRoleWithMenus获取角色及其菜单信息
    const response = await getRoleWithMenus(id);

    // 填充基本表单数据
    Object.keys(form).forEach((key) => {
      if (response[key] !== undefined) {
        form[key] = response[key];
      }
    });

    // 设置菜单树选中状态
    if (menuTreeRef.value && form.menuIds?.length > 0) {
      nextTick(() => {
        // 筛选出可用的叶子节点
        const leafNodes = form.menuIds.filter((id) => {
          const node = menuTreeRef.value.getNode(id);
          return node && node.isLeaf && !node.disabled;
        });

        // 设置树控件的选中状态，只选中可用的叶子节点
        menuTreeRef.value.setCheckedKeys(leafNodes);
      });
    }

    console.log("加载角色数据成功:", form.name);
  } catch (error) {
    console.error("加载角色数据失败", error);
    ElMessage.error("加载角色数据失败");
    dialogVisible.value = false;
  } finally {
    loading.value = false;
  }
};

// 加载菜单树数据
const loadMenuTreeData = async () => {
  menuTreeLoading.value = true;
  try {
    const response = await getMenuList({ tree: "true" });

    // 处理菜单数据，为禁用状态的菜单添加disabled属性
    const processMenuData = (menuItems) => {
      return menuItems.map((item) => {
        // 创建新对象，保留原有属性
        const newItem = { ...item };

        // 如果菜单状态为禁用，设置disabled属性为true
        if (item.status === "inactive") {
          newItem.disabled = true;
          // 同时标记子菜单为禁用状态
          if (item.children && item.children.length > 0) {
            newItem.children = item.children.map((child) => ({
              ...child,
              disabled: true,
            }));
          }
        }

        // 递归处理子菜单
        else if (item.children && item.children.length > 0) {
          newItem.children = processMenuData(item.children);
        }

        return newItem;
      });
    };

    // 处理菜单数据
    menuTreeData.value = Array.isArray(response)
      ? processMenuData(response)
      : [];

    console.log("加载菜单树数据成功:", menuTreeData.value.length, "条记录");
  } catch (error) {
    console.error("加载菜单树数据失败", error);
    ElMessage.error("加载菜单树数据失败");
  } finally {
    menuTreeLoading.value = false;
  }
};

// 重置表单
const resetForm = () => {
  // 重置所有状态
  Object.assign(form, createFormData());
  formRef.value?.resetFields();
  menuTreeRef.value?.setCheckedKeys([]);
  submitLoading.value = false;
};

// 取消表单
const handleCancel = () => {
  dialogVisible.value = false;
};

// 提交表单
const handleSubmit = async () => {
  // 表单验证
  if (!formRef.value) return;

  try {
    await formRef.value.validate();
  } catch (error) {
    return;
  }

  // 获取选中的菜单ID
  if (menuTreeRef.value) {
    const checkedKeys = menuTreeRef.value.getCheckedKeys();
    const halfCheckedKeys = menuTreeRef.value.getHalfCheckedKeys();

    // 合并并去重
    form.menuIds = [...new Set([...checkedKeys, ...halfCheckedKeys])];
  }

  submitLoading.value = true;

  try {
    if (formType.value === "add") {
      await createRole(form);
      ElMessage.success("创建角色成功");
    } else {
      // 更新角色 - 删除code字段，因为角色编码不能修改
      const { code, ...updateData } = form;
      await updateRole(currentId.value, updateData);
      ElMessage.success("更新角色成功");
    }

    // 关闭对话框并通知父组件刷新
    dialogVisible.value = false;
    emit("success");
  } catch (error) {
    console.error("提交角色表单失败", error);
    ElMessage.error("操作失败：" + (error.message || "未知错误"));
  } finally {
    submitLoading.value = false;
  }
};

// 对外暴露方法
defineExpose({
  openForm,
});
</script>

<style scoped>
.form-section {
  position: relative;
}

.menu-tree-container {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 10px;
}
</style>
