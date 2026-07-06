<template>
  <div class="wang-editor">
    <Toolbar
      style="border-bottom: 1px solid #ccc"
      :editor="editorRef"
      :defaultConfig="toolbarConfig"
      :mode="mode"
    />
    <Editor
      :style="{ height: editorHeight, overflowY: 'hidden' }"
      v-model="valueHtml"
      :defaultConfig="editorConfig"
      :mode="mode"
      @onCreated="handleCreated"
      @onChange="handleChange"
      @onDestroyed="handleDestroyed"
      @onFocus="handleFocus"
      @onBlur="handleBlur"
    />
    <!-- 字数统计显示 -->
    <div v-if="maxLength" class="word-count-container">
      <span
        class="word-count"
        :class="{ 'word-count-exceed': currentLength > maxLength }"
      >
        {{ currentLength }}/{{ maxLength }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  onBeforeUnmount,
  ref,
  shallowRef,
  watch,
  onMounted,
  nextTick,
} from "vue";
import { Editor, Toolbar } from "@wangeditor/editor-for-vue";
import type {
  IDomEditor,
  IEditorConfig,
  IToolbarConfig,
} from "@wangeditor/editor";
import { ElMessage } from "element-plus";
import { DomEditor } from "@wangeditor/editor";

interface Props {
  modelValue?: string;
  height?: string;
  mode?: "default" | "simple";
  placeholder?: string;
  readonly?: boolean;
  maxLength?: number; // 新增：最大字数限制
}

interface Emits {
  (e: "update:modelValue", value: string): void;
  (e: "change", value: string): void;
  (e: "focus"): void;
  (e: "blur"): void;
  (e: "exceed", length: number): void; // 新增：超出字数限制时触发
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: "",
  height: "400px",
  mode: "default",
  placeholder: "请输入内容...",
  readonly: false,
  maxLength: undefined,
});

const emit = defineEmits<Emits>();

// 编辑器实例，必须用 shallowRef
const editorRef = shallowRef<IDomEditor>();

// 内容 HTML
const valueHtml = ref("");

// 当前字数
const currentLength = ref(0);

// 计算编辑器高度
const editorHeight = ref(props.height);

// 工具栏配置
const toolbarConfig: Partial<IToolbarConfig> = {
  // 使用excludeKeys方式，更简洁
  excludeKeys: [
    "group-video", // 排除视频相关功能
    "fullScreen", // 排除全屏功能
    "group-image", // 排除图片相关功能
    "group-table", // 排除表格相关功能
    "group-list", // 排除列表相关功能
    "group-code", // 排除代码相关功能
    "group-formula", // 排除公式相关功能
    "insertLink",
    "codeBlock",
  ],
};
// 获取工具栏的配置

// 编辑器配置
const editorConfig: Partial<IEditorConfig> = {
  placeholder: props.placeholder,
  readOnly: props.readonly,
};

// 计算纯文本字数的函数
const getTextLength = (html: string): number => {
  if (!html) return 0;

  // 创建临时DOM元素来提取纯文本
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = html;
  const text = tempDiv.textContent || tempDiv.innerText || "";

  // 移除多余的空白字符并计算长度
  return text.replace(/\s+/g, " ").trim().length;
};

// 组件销毁时，也及时销毁编辑器
onBeforeUnmount(() => {
  const editor = editorRef.value;
  if (editor == null) return;
  editor.destroy();
});

// 编辑器回调函数
const handleCreated = (editor: IDomEditor) => {
  editorRef.value = editor; // 记录 editor 实例，重要！

  // 初始化字数统计
  if (props.maxLength) {
    currentLength.value = getTextLength(valueHtml.value);
  }
};

const handleChange = (editor: IDomEditor) => {
  const html = editor.getHtml();

  // 如果设置了字数限制，进行检查
  if (props.maxLength) {
    const textLength = getTextLength(html);
    currentLength.value = textLength;

    // 如果超出字数限制
    if (textLength > props.maxLength) {
      emit("exceed", textLength);
      ElMessage.warning(
        `内容超出字数限制，当前${textLength}字，最多${props.maxLength}字`
      );
      return; // 不更新内容
    }
  }

  emit("update:modelValue", html);
  emit("change", html);
};

const handleDestroyed = (editor: IDomEditor) => {
  if (import.meta.env.DEV) console.log("editor destroyed", editor);
};

const handleFocus = (editor: IDomEditor) => {
  emit("focus");
};

const handleBlur = (editor: IDomEditor) => {
  emit("blur");
};

// 监听外部传入的内容变化
watch(
  () => props.modelValue,
  (val) => {
    if (val !== valueHtml.value) {
      valueHtml.value = val || "";

      // 更新字数统计
      if (props.maxLength) {
        currentLength.value = getTextLength(val || "");
      }
    }
  },
  { immediate: true }
);

// 监听高度变化
watch(
  () => props.height,
  (val) => {
    editorHeight.value = val;
  }
);

// 暴露编辑器实例给父组件
defineExpose({
  getEditor: () => editorRef.value,
  getTextLength: () => currentLength.value,
});

// 添加默认导出
defineOptions({
  name: "WangEditor",
});

onMounted(() => {
  nextTick(() => {
    const toolbar = DomEditor.getToolbar(editorRef.value);
    const curToolbarConfig = toolbar.getConfig();
    if (import.meta.env.DEV) console.log(curToolbarConfig.toolbarKeys);
  });
});
</script>

<style scoped>
.wang-editor {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  width: 100%;
}

.wang-editor :deep(.w-e-text-placeholder) {
  color: #c0c4cc;
}

.wang-editor :deep(.w-e-text-container) {
  background-color: #fff;
}

.wang-editor :deep(.w-e-toolbar) {
  background-color: #fafafa;
  border-bottom: 1px solid #e5e7eb;
  flex-wrap: wrap;
}

/* 移动端工具栏优化 */

.word-count-container {
  position: absolute;
  bottom: 8px;
  right: 12px;
  background: rgba(255, 255, 255, 0.95);
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  z-index: 10;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* 移动端字数统计优化 */
@media (max-width: 768px) {
  .word-count-container {
    bottom: 6px;
    right: 8px;
    padding: 3px 6px;
    font-size: 11px;
  }
}

.word-count {
  font-size: inherit;
  color: #6b7280;
}

.word-count-exceed {
  color: #ef4444 !important;
  font-weight: 500;
}
</style>
