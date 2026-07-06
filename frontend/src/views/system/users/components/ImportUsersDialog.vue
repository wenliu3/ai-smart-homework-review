<template>
  <el-dialog
    v-model="dialogVisible"
    title="批量导入用户"
    width="800px"
    :close-on-click-modal="false"
    :destroy-on-close="true"
  >
    <!-- 步骤导航 -->
    <el-steps :active="activeStep" finish-status="success" simple class="mb-6">
      <el-step title="上传文件" />
      <el-step title="预览数据" />
      <el-step title="导入结果" />
    </el-steps>

    <!-- 步骤1: 上传文件 -->
    <div v-if="activeStep === 0" class="step-content">
      <el-upload
        class="upload-area w-full"
        drag
        action="/"
        :http-request="handleHttpRequest"
        :limit="1"
        :file-list="fileList"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip text-center mt-4">
            <p>仅支持.xlsx、.xls格式的Excel文件</p>
            <p class="text-red-500">单次最多导入100条数据</p>
            <div class="text-gray-600 text-sm mt-2 mb-2">
              <p><strong>必填字段：</strong>姓名、学号</p>
              <p><strong>可选字段：</strong>用户名、邮箱、手机号（如果填写需符合格式要求）</p>
              <p class="text-blue-600">💡 用户名为空时，将自动使用姓名作为用户名</p>
            </div>
            <el-button
              type="primary"
              @click="handleDownloadTemplate"
              class="mt-2"
            >
              <el-icon><download /></el-icon>
              下载导入模板
            </el-button>
          </div>
        </template>
      </el-upload>
    </div>

    <!-- 步骤2: 预览数据 -->
    <div v-else-if="activeStep === 1" class="step-content">
      <div v-if="validationMessage" class="mb-2">
        <el-alert
          :title="validationMessage"
          type="warning"
          show-icon
          :closable="false"
        />
      </div>
      <div class="preview-header mb-4">
        <el-alert
          title="请确认以下数据无误后继续"
          type="info"
          show-icon
          :closable="false"
        />
      </div>
      <el-table
        :data="previewData"
        border
        max-height="300px"
        style="width: 100%"
      >
        <el-table-column type="index" width="50" label="#" />
        <el-table-column prop="name" label="姓名" width="100">
          <template #default="{ row }">
            <span class="text-red-600">{{ row.name }}</span>
            <el-tag size="small" type="danger" class="ml-1">必填</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="studentId" label="学号" width="120">
          <template #default="{ row }">
            <span class="text-red-600">{{ row.studentId }}</span>
            <el-tag size="small" type="danger" class="ml-1">必填</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120">
          <template #default="{ row }">
            <span>{{ row.username || row.name }}</span>
            <el-tag v-if="!row.username" size="small" type="info" class="ml-1">自动</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180">
          <template #default="{ row }">
            <span v-if="row.email">{{ row.email }}</span>
            <span v-else class="text-gray-400">未填写</span>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" width="120">
          <template #default="{ row }">
            <span v-if="row.phone">{{ row.phone }}</span>
            <span v-else class="text-gray-400">未填写</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 步骤3: 导入结果 -->
    <div v-else class="step-content">
      <el-result
        :icon="importResult.success ? 'success' : 'error'"
        :title="importResult.title"
        :sub-title="importResult.subTitle"
      >
        <template #extra>
          <div class="import-result-details text-center mb-4">
            <p>成功导入: {{ importResult.successCount }} 条</p>
            <p>导入失败: {{ importResult.failureCount }} 条</p>
            <!-- 失败详情按钮 -->
            <el-button
              v-if="importResult.failures && importResult.failures.length > 0"
              type="danger"
              @click="showFailureDialog = true"
              size="small"
              class="mt-2"
            >
              查看失败详情
            </el-button>
          </div>
        </template>
      </el-result>
    </div>

    <!-- 对话框底部按钮 -->
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">{{
          activeStep === 2 ? "完成" : "取消"
        }}</el-button>
        <!--  -->
        <template v-if="activeStep === 1">
          <el-button @click="activeStep = 0">上一步</el-button>
          <el-button type="primary" @click="importUsers" :loading="importing">
            {{ importing ? "导入中..." : "确认导入" }}
          </el-button>
        </template>
      </div>
    </template>
    <!-- 失败详情二级弹窗 -->
    <FailureDetailDialog
      :visible="showFailureDialog"
      :failures="importResult.failures || []"
      title="导入失败详情"
      @close="showFailureDialog = false"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { ElMessage } from "element-plus";
import { UploadFilled, Download } from "@element-plus/icons-vue";
import { downloadTemplate } from "@/api/template";
import { importUsersBatch } from "@/api/user";
import * as XLSX from "xlsx";
import FailureDetailDialog from "./FailureDetailDialog.vue";

// 定义导入结果的类型

// 对话框控制
const dialogVisible = ref(false);

// 步骤控制
const activeStep = ref(0);
const fileList = ref([]);
const previewData = ref([]);
const importing = ref(false);
const importResult = ref({
  success: true,
  title: "导入成功",
  subTitle: "用户数据已成功导入系统",
  successCount: 0,
  failureCount: 0,
  failures: [],
});

const showFailureDialog = ref(false);
const validationMessage = ref("");

// 打开对话框
const open = () => {
  dialogVisible.value = true;
  resetDialog();
};

// 关闭对话框
const closeDialog = () => {
  if (importing.value) return;
  dialogVisible.value = false;
};

// 重置对话框状态
const resetDialog = () => {
  activeStep.value = 0;
  fileList.value = [];
  previewData.value = [];
  importing.value = false;
  importResult.value = {
    success: true,
    title: "导入成功",
    subTitle: "用户数据已成功导入系统",
    successCount: 0,
    failureCount: 0,
    failures: [],
  };
};

// 下载模板
const handleDownloadTemplate = () => {
  downloadTemplate("user-import", "用户导入模板.xlsx");
};

const handleHttpRequest = async (options) => {
  const file = options.file;
  fileList.value = [file];
  previewData.value = [];
  validationMessage.value = "";
  await parseFile(file);
  fileList.value = [];
  // 必须调用options.onSuccess，否则el-upload会卡住
  options.onSuccess({}, file);
};

// 文件移除处理
const handleFileRemove = () => {
  fileList.value = [];
  previewData.value = [];
  validationMessage.value = "";
};

// 文件解析处理（参数为file）
const parseFile = async (file) => {
  if (!file) return;
  try {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        if (!e.target || !e.target.result) {
          throw new Error("文件读取失败");
        }
        const data = e.target.result;
        // 使用xlsx库解析Excel文件
        const workbook = XLSX.read(data, { type: "array" });
        const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
        const parsedData = XLSX.utils.sheet_to_json(firstSheet);

        // 必填字段：只有姓名和学号是必填的
        const requiredFields = ["name", "studentId"];
        const validData = [];
        const invalidRows = [];
        parsedData.forEach((row: any, idx: number) => {
          const item = {
            username: row["用户名"] || "",
            name: row["姓名"] || "",
            email: row["邮箱"] || "",
            studentId: row["学号"]?.toString() || "",
            phone: row["手机号"] || "",
          };
          
          // 检查必填字段（姓名和学号）
          const hasRequiredFields = requiredFields.every((field) => item[field]);
          if (!hasRequiredFields) {
            invalidRows.push(idx + 2); // Excel通常第2行开始是数据
            return;
          }
          
          // 如果用户名为空，使用姓名作为用户名
          if (!item.username && item.name) {
            item.username = item.name;
          }
          
          // 验证可选字段格式（有内容时才验证）
          let isValid = true;
          let errorMsg = "";
          
          // 邮箱格式验证（如果有内容）
          if (item.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(item.email)) {
            isValid = false;
            errorMsg = "邮箱格式不正确";
          }
          
          // 手机号格式验证（如果有内容）
          if (item.phone && !/^1[3-9]\d{9}$/.test(item.phone)) {
            isValid = false;
            errorMsg = errorMsg ? errorMsg + "，手机号格式不正确" : "手机号格式不正确";
          }
          
          if (isValid) {
            validData.push(item);
          } else {
            invalidRows.push(idx + 2); // Excel通常第2行开始是数据
          }
        });
        if (invalidRows.length > 0) {
          validationMessage.value = `有${
            invalidRows.length
          }条数据因缺少必填项（姓名、学号）或格式错误被忽略（行号: ${invalidRows.join(
            ", "
          )}），请检查表格内容`;
        } else {
          validationMessage.value = "";
        }
        // 限制导入数据不超过100条
        if (validData.length > 100) {
          validData.splice(100);
          validationMessage.value =
            (validationMessage.value ? validationMessage.value + "；" : "") +
            `数据超过最大限制，已自动截取前100条数据进行导入`;
        }
        if (validData.length === 0) {
          ElMessage.error("没有合规的数据可供导入，请检查表格内容");
          return;
        }
        previewData.value = validData;
        activeStep.value = 1; // 自动进入下一步
      } catch (error) {
        validationMessage.value = "";
        ElMessage.error("文件解析失败，请确保文件格式正确");
        console.error("文件解析错误:", error);
      }
    };
    reader.readAsArrayBuffer(file);
  } catch (error) {
    validationMessage.value = "";
    ElMessage.error("文件处理失败");
    console.error("文件处理错误:", error);
  }
};

// 导入用户
const importUsers = async () => {
  if (previewData.value.length === 0) {
    ElMessage.warning("没有要导入的数据");
    return;
  }

  importing.value = true;

  try {
    // 调用后端的批量导入API
    const response = await importUsersBatch(previewData.value);
    console.log(response, "response");
    // 更新导入结果
    importResult.value = {
      success: response.success,
      title: response.success ? "导入成功" : "部分导入成功",
      subTitle: response.success
        ? "所有用户数据已成功导入系统"
        : `部分用户导入失败，请检查失败原因`,
      successCount: response.successCount,
      failureCount: response.failureCount,
      failures: response.failures,
    };

    activeStep.value = 2;

    // 通知父组件导入成功
    if (response.successCount > 0) {
      emit("success");
    }
  } catch (error) {
    console.error("导入失败", error);

    importResult.value = {
      success: false,
      title: "导入失败",
      subTitle: "用户数据导入过程中出现错误",
      successCount: 0,
      failureCount: previewData.value.length,
      failures: [],
    };

    activeStep.value = 2;
  } finally {
    importing.value = false;
  }
};

// 定义组件事件
const emit = defineEmits(["success"]);

// 暴露方法
defineExpose({
  open,
});
</script>

<style scoped>
.step-content {
  min-height: 200px;
  margin-bottom: 16px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.el-upload {
  width: 100%;
  text-align: center;
}

.el-upload-dragger {
  width: 100%;
  height: 180px;
}
</style>
