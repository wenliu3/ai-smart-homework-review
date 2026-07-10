<template>
  <div class="work-edit-container">
    <!-- 页面头部 - 响应式设计 -->
    <div
      class="flex items-center justify-between max-w-4xl mx-auto sm:px-6 lg:px-8 py-4 mb-2"
    >
      <div class="flex items-center gap-3">
        <el-button
          link
          @click="goBack"
          :icon="ArrowLeft"
          class="!p-2 !text-gray-600 hover:!text-blue-600 hover:!bg-blue-50 !rounded-lg"
        >
          <span class="hidden sm:inline ml-1">返回</span>
        </el-button>

        <h1 class="text-lg sm:text-xl font-semibold text-gray-900 truncate">
          {{ isEdit ? "编辑作业" : "创建作业" }}
        </h1>
      </div>

      <div>
        <el-button
          @click="handleSaveDraft"
          :loading="saving"
          class="flex-1 sm:flex-none !text-sm"
        >
          保存草稿
        </el-button>
        <el-button
          type="primary"
          @click="handlePublish"
          :loading="saving"
          class="flex-1 sm:flex-none !text-sm"
        >
          {{ isEdit ? "更新并发布" : "发布作业" }}
        </el-button>
      </div>
    </div>

    <!-- 表单内容 - 响应式容器 -->
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200">
        <el-form
          ref="formRef"
          :model="formData"
          :rules="formRules"
          :label-width="isMobile ? 'auto' : '100px'"
          :label-position="isMobile ? 'top' : 'left'"
          size="default"
          class="assignment-form"
          :scroll-to-error="true"
          :scroll-into-view-options="{
            behavior: 'smooth',
            block: 'center',
            inline: 'center',
          }"
        >
          <!-- 基本信息区域 -->
          <div class="form-section">
            <div class="section-header">
              <h3 class="section-title">基本信息</h3>
            </div>
            <div class="section-content">
              <!-- 作业标题 -->
              <el-form-item label="作业标题" prop="title" class="form-item">
                <el-input
                  v-model="formData.title"
                  placeholder="请输入作业标题"
                  maxlength="100"
                  show-word-limit
                  class="w-full"
                />
              </el-form-item>

              <!-- 作业描述 -->
              <el-form-item
                label="作业描述"
                prop="description"
                class="form-item"
              >
                <div class="w-full">
                  <wang-editor
                    v-model="formData.description"
                    :height="isMobile ? '320px' : '350px'"
                    placeholder="请输入作业描述，支持富文本格式"
                    :max-length="3000"
                    @exceed="handleDescriptionExceed"
                    class="w-full"
                  />
                </div>
              </el-form-item>
            </div>
          </div>

          <!-- 配置信息区域 -->
          <div class="form-section">
            <div class="section-header">
              <h3 class="section-title">配置信息</h3>
            </div>
            <div class="section-content">
              <!-- 关联班级 -->
              <div class="mb-6">
                <el-form-item label="关联班级" prop="classes" class="form-item">
                  <class-selector v-model="formData.classes" />
                </el-form-item>
              </div>

              <!-- AI批改规则 -->
              <div class="mb-6">
                <el-form-item
                  label="AI批改规则"
                  prop="aiRule"
                  class="form-item"
                >
                  <ai-rule-selector v-model="formData.aiRule" />
                </el-form-item>
              </div>

              <!-- 时间设置 - 响应式网格 -->
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <el-form-item
                  label="开始时间"
                  prop="startDate"
                  class="form-item"
                >
                  <el-date-picker
                    v-model="formData.startDate"
                    type="datetime"
                    placeholder="请选择开始时间"
                    format="YYYY-MM-DD HH:mm"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                    :size="isMobile ? 'default' : 'default'"
                  />
                </el-form-item>
                <el-form-item label="截止时间" prop="endDate" class="form-item">
                  <el-date-picker
                    v-model="formData.endDate"
                    type="datetime"
                    placeholder="请选择截止时间"
                    format="YYYY-MM-DD HH:mm"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                    :size="isMobile ? 'default' : 'default'"
                  />
                </el-form-item>
              </div>

              <!-- 其他设置 -->
              <el-form-item label="附件设置" class="form-item">
                <div class="flex items-center gap-3">
                  <el-switch v-model="formData.allowAttachments" />
                  <span class="text-sm text-gray-600">允许学生上传附件</span>
                </div>
              </el-form-item>

              <!-- 教师上传附件 -->
              <el-form-item label="作业附件" class="form-item">
                <div class="w-full">
                  <!-- 上传中进度 -->
                  <div v-if="uploading" class="mb-2">
                    <el-progress :percentage="uploadProgress" :stroke-width="8" />
                    <span class="text-xs text-blue-500">正在上传... {{ uploadProgress }}%</span>
                  </div>
                  <!-- 已上传文件列表 -->
                  <div v-if="assignmentAttachments.length > 0" class="mb-2">
                    <div
                      v-for="(f, i) in assignmentAttachments"
                      :key="i"
                      class="flex items-center p-2 bg-gray-50 rounded mb-1"
                    >
                      <el-icon class="text-blue-500 mr-2"><Document /></el-icon>
                      <span class="flex-1 text-sm">{{ f.fileName }}</span>
                      <span class="text-xs text-gray-400 mr-2">{{ formatFileSize(f.fileSize) }}</span>
                      <el-button type="danger" size="small" text @click="removeAttachment(i)">删除</el-button>
                    </div>
                  </div>
                  <input
                    ref="assignmentFileInputRef"
                    type="file"
                    multiple
                    accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.txt"
                    style="display:none"
                    @change="onAssignmentFilesSelected"
                  />
                  <el-button type="primary" size="small" @click="triggerAssignmentFileSelect" :disabled="uploading">
                    <el-icon><Upload /></el-icon>
                    上传附件（供学生下载）
                  </el-button>
                  <div class="text-xs text-gray-400 mt-1">支持 jpg、png、pdf、doc、docx、txt，单文件不超过20MB</div>
                </div>
              </el-form-item>
            </div>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, Upload, Document } from "@element-plus/icons-vue";
import type { FormInstance, FormRules } from "element-plus";
import {
  getAssignment,
  createAssignment,
  updateAssignment,
  updateAssignmentStatus,
  AssignmentStatus,
} from "@/api/assignments";
import type { CreateAssignmentDto, AiRuleSnapshot } from "@/types/assignments";
import WangEditor from "@/components/WangEditor.vue";
import ClassSelector from "../components/ClassSelector.vue";
import AiRuleSelector from "../components/AiRuleSelector.vue";
import moment from "moment";

const route = useRoute();
const router = useRouter();

// 响应式检测
const isMobile = ref(false);

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768;
};
// 检测window的size事件
window.addEventListener("resize", checkMobile);
// 是否编辑模式
const isEdit = computed(() => !!route.query.id);
const assignmentId = computed(() => route.query.id as string);

// 表单引用
const formRef = ref<FormInstance>();

// 状态
const saving = ref(false);
const loading = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const assignmentFileInputRef = ref<HTMLInputElement | null>(null);
const assignmentAttachments = ref<Array<{
  fileName: string;
  fileUrl: string;
  fileSize: number;
  fileType: string;
}>>([]);

// 表单数据
const formData = reactive<CreateAssignmentDto & { allowAttachments: boolean }>({
  title: "",
  description: "",
  classes: [],
  aiRule: null as AiRuleSnapshot | null,
  startDate: "",
  endDate: "",
  allowAttachments: false,
});

// 表单验证规则
const formRules: FormRules = {
  title: [
    { required: true, message: "请输入作业标题", trigger: "blur" },
    {
      min: 2,
      max: 100,
      message: "标题长度在 2 到 100 个字符",
      trigger: "blur",
    },
  ],
  description: [
    { required: true, message: "请输入作业描述", trigger: "blur" },
    {
      validator: (rule, value, callback) => {
        if (!value || value.trim() === "") {
          callback(new Error("请输入作业描述"));
          return;
        }

        // 计算纯文本字数
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = value;
        const text = tempDiv.textContent || tempDiv.innerText || "";
        const textLength = text.replace(/\s+/g, " ").trim().length;

        if (textLength > 3000) {
          callback(new Error(`作业描述不能超过3000字，当前${textLength}字`));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  classes: [{ required: true, message: "请选择关联班级", trigger: "change" }],
  aiRule: [{ required: true, message: "请选择AI批改规则", trigger: "change" }],
  startDate: [
    { required: true, message: "请选择开始时间", trigger: "change" },
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback(new Error("请选择开始时间"));
          return;
        }

        const startDateTime = new Date(value);
        const now = new Date();

        // 新建作业时，开始时间不能早于当前时间（允许1分钟误差）
        if (!isEdit.value && startDateTime.getTime() < now.getTime() - 60000) {
          callback(new Error("开始时间不能早于当前时间"));
          return;
        }

        callback();
      },
      trigger: "change",
    },
  ],
  //
  endDate: [
    { required: true, message: "请选择截止时间", trigger: "change" },
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback(new Error("请选择截止时间"));
          return;
        }

        const endDateTime = new Date(value);
        const now = new Date();

        // 检查截止时间是否晚于当前时间
        if (endDateTime <= now) {
          callback(new Error("截止时间必须晚于当前时间"));
          return;
        }

        // 检查截止时间是否晚于开始时间
        if (formData.startDate && endDateTime <= new Date(formData.startDate)) {
          callback(new Error("截止时间必须晚于开始时间"));
          return;
        }

        callback();
      },
      trigger: "change",
    },
  ],
};

// 初始化表单数据
const initFormData = () => {
  if (!isEdit.value) {
    // 新建模式，设置默认时间为当前本地时间
    const now = new Date();
    const pad = (n: number) => n.toString().padStart(2, '0');
    const toLocalStr = (d: Date) =>
      `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    
    formData.startDate = toLocalStr(now);
    formData.endDate = toLocalStr(new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000));
  }
};

// 加载作业数据（编辑模式）
const loadAssignmentData = async () => {
  if (!isEdit.value) return;

  loading.value = true;
  try {
    const assignment = await getAssignment(assignmentId.value);
    Object.assign(formData, {
      title: assignment.title,
      description: assignment.description,
      classes: assignment.classes.map((cls) => cls.id),
      aiRule: assignment.aiRule,
      startDate: moment(assignment.startDate).format("YYYY-MM-DD HH:mm:ss"),
      endDate: moment(assignment.endDate).format("YYYY-MM-DD HH:mm:ss"),
      allowAttachments: assignment.allowAttachments || false,
    });
    assignmentAttachments.value = assignment.attachments || [];
  } catch (error) {
    console.error("加载作业数据失败:", error);
    ElMessage.error("加载作业数据失败");
  } finally {
    loading.value = false;
  }
};

// 构建作业数据
const buildAssignmentData = (includeStatus = false) => {
  const data: any = {
    title: formData.title,
    description: formData.description,
    classes: formData.classes,
    aiRule: formData.aiRule,
    startDate: formData.startDate,
    endDate: formData.endDate,
    allowAttachments: formData.allowAttachments,
    attachments: assignmentAttachments.value,
  };

  if (includeStatus) {
    data.status = AssignmentStatus.DRAFT;
  }

  return data;
};

// 保存草稿
const handleSaveDraft = async () => {
  if (!formRef.value) return;

  try {
    // 表单校验失败时会自动滚动到错误字段，不需要额外提示
    await formRef.value.validate();
    saving.value = true;

    if (isEdit.value) {
      // 编辑模式：更新作业并设置为草稿状态
      const updateData = buildAssignmentData();
      updateData.status = AssignmentStatus.DRAFT; // 明确设置为草稿状态
      await updateAssignment(assignmentId.value, updateData);
      ElMessage.success("作业已保存为草稿");
    } else {
      // 创建模式：创建新作业
      await createAssignment(buildAssignmentData(true));
      ElMessage.success("作业创建成功");
      router.push("/teacher/assignments");
    }
  } catch (error) {
    // 只有API请求失败才显示错误提示，表单校验失败不显示
    if (saving.value) {
      console.error("保存失败:", error);
      ElMessage.error("保存失败");
    }
  } finally {
    saving.value = false;
  }
};

// 发布作业
const handlePublish = async () => {
  if (!formRef.value) return;

  try {
    // 表单校验失败时会自动滚动到错误字段，不需要额外提示
    await formRef.value.validate();

    await ElMessageBox.confirm(
      "确定要发布这个作业吗？发布后学生将能够看到并提交作业。",
      "确认发布",
      { type: "warning" }
    );

    saving.value = true;
    let currentAssignmentId: string;

    if (isEdit.value) {
      // 编辑模式：更新作业（包含AI规则）
      await updateAssignment(assignmentId.value, buildAssignmentData());
      currentAssignmentId = assignmentId.value;
    } else {
      // 创建模式：创建新作业
      const result = await createAssignment(buildAssignmentData(true));
      currentAssignmentId = result.id;
    }

    // 发布作业
    await updateAssignmentStatus(currentAssignmentId, {
      status: AssignmentStatus.PUBLISHED,
    });

    ElMessage.success("作业发布成功");
    // 判断是否有返回的url
    if (router.currentRoute.value.query.redirect) {
      router.push(router.currentRoute.value.query.redirect as string);
    } else {
      router.back();
    }
  } catch (error: any) {
    if (error !== "cancel") {
      // 只有API请求失败才显示错误提示，表单校验失败不显示
      if (saving.value) {
        console.error("发布失败:", error);
        ElMessage.error("发布失败");
      }
    }
  } finally {
    saving.value = false;
  }
};

// 返回
const goBack = () => {
  router.back();
};

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (!bytes) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
};

// 触发文件选择
const triggerAssignmentFileSelect = () => {
  assignmentFileInputRef.value?.click();
};

// 文件选择处理
const onAssignmentFilesSelected = (e: Event) => {
  const target = e.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) return;
  uploadAssignmentFiles(Array.from(files));
  target.value = ""; // 重置input，允许重复选择同一文件
};

// 上传附件文件
const uploadAssignmentFiles = (files: File[]) => {
  uploading.value = true;
  uploadProgress.value = 0;
  const token = localStorage.getItem("token");
  const formDataObj = new FormData();
  files.forEach((f) => formDataObj.append("files", f));
  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      uploadProgress.value = Math.round((e.loaded / e.total) * 100);
    }
  };
  xhr.onload = () => {
    uploading.value = false;
    try {
      const res = JSON.parse(xhr.responseText);
      if (res.code === 200 && res.data?.files) {
        res.data.files.forEach((f: any) => {
          assignmentAttachments.value.push({
            fileName: f.fileName,
            fileUrl: f.fileUrl,
            fileSize: f.fileSize,
            fileType: f.fileType,
          });
        });
        ElMessage.success(`成功上传 ${res.data.files.length} 个文件`);
      } else {
        ElMessage.error(res.message || "上传失败");
      }
    } catch {
      ElMessage.error("上传响应解析失败");
    }
  };
  xhr.onerror = () => {
    uploading.value = false;
    ElMessage.error("上传失败，请检查网络");
  };
  xhr.open("POST", "/api/upload/files");
  xhr.setRequestHeader("Authorization", `Bearer ${token}`);
  xhr.send(formDataObj);
};

// 删除附件
const removeAttachment = (index: number) => {
  const file = assignmentAttachments.value[index];
  // 尝试删除服务器上的文件
  const filename = (file.fileUrl || "").replace("/uploads/", "");
  if (filename) {
    const token = localStorage.getItem("token");
    fetch(`/api/upload/delete/${filename}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  assignmentAttachments.value.splice(index, 1);
  ElMessage.success("已删除附件");
};

// 处理富文本超出字数限制
const handleDescriptionExceed = (length: number) => {
  // 触发表单验证
  formRef.value?.validateField("description");
};

// 初始化
onMounted(() => {
  initFormData();
  loadAssignmentData();
  checkMobile();
});
</script>

<style scoped>
/* 作业编辑表单样式 */
.assignment-form {
  background: #ffffff;
}

/* 表单分区样式 */
.form-section {
  border-bottom: 1px solid #f0f2f5;
}

.form-section:last-child {
  border-bottom: none;
}

.section-header {
  padding: 20px 24px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid #e5e7eb;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  display: flex;
  align-items: center;
}

.section-title::before {
  content: "";
  width: 4px;
  height: 16px;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  margin-right: 12px;
  border-radius: 2px;
}

.section-content {
  padding: 24px;
}
</style>
