<template>
  <div class="chart-container" :style="{ height: height + 'px' }">
    <div v-if="loading" class="loading-overlay">
      <el-icon class="is-loading">
        <Loading />
      </el-icon>
      <span class="loading-text">{{ loadingText }}</span>
    </div>
    <div
      ref="chartRef"
      :style="{ height: '100%', width: '100%' }"
      class="chart-content"
    ></div>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  onMounted,
  onUnmounted,
  watch,
  nextTick,
  onBeforeUnmount,
} from "vue";
import * as echarts from "echarts/core";
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
} from "echarts/components";
import {
  PieChart,
  BarChart,
  LineChart,
  GaugeChart,
  RadarChart,
} from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import { Loading } from "@element-plus/icons-vue";

// 注册必要的组件
echarts.use([
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  PieChart,
  BarChart,
  LineChart,
  GaugeChart,
  RadarChart,
  CanvasRenderer,
]);

interface Props {
  options: any;
  height?: number;
  loading?: boolean;
  loadingText?: string;
  theme?: string;
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
  loading: false,
  loadingText: "加载中...",
  theme: "default",
});

const chartRef = ref<HTMLElement>();
let chartInstance: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

// 主题配置
const themeConfig = {
  color: [
    "#007AFF",
    "#34C759",
    "#FF9F0A",
    "#FF3B30",
    "#AF52DE",
    "#5AC8FA",
    "#FF2D92",
    "#30D158",
    "#8E8E93",
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
  ],
  backgroundColor: "transparent",
  textStyle: {
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    color: "#1D1D1F",
    fontSize: 12,
  },
  animation: true,
  animationDuration: 1000,
  animationEasing: "cubicOut",
};

onMounted(async () => {
  await nextTick();
  initChart();
});

onBeforeUnmount(() => {
  cleanup();
});

onUnmounted(() => {
  cleanup();
});

watch(
  () => props.options,
  (newOptions) => {
    if (chartInstance && newOptions) {
      chartInstance.setOption(newOptions, true);
    }
  },
  { deep: true }
);

watch(
  () => props.loading,
  (newLoading) => {
    if (chartInstance) {
      if (newLoading) {
        chartInstance.showLoading("default", {
          text: props.loadingText,
          color: "#007AFF",
          textColor: "#1D1D1F",
          maskColor: "rgba(255, 255, 255, 0.8)",
          zlevel: 0,
        });
      } else {
        chartInstance.hideLoading();
      }
    }
  }
);

function initChart() {
  if (!chartRef.value) return;

  try {
    chartInstance = echarts.init(chartRef.value, themeConfig);

    if (props.options) {
      chartInstance.setOption(props.options);
    }

    // 设置加载状态
    if (props.loading) {
      chartInstance.showLoading("default", {
        text: props.loadingText,
        color: "#007AFF",
        textColor: "#1D1D1F",
        maskColor: "rgba(255, 255, 255, 0.8)",
        zlevel: 0,
      });
    }

    // 使用 ResizeObserver 替代 window resize 事件
    setupResizeObserver();
  } catch (error) {
    console.error("图表初始化失败:", error);
  }
}

function setupResizeObserver() {
  if (!chartRef.value || !chartInstance) return;

  resizeObserver = new ResizeObserver(() => {
    if (chartInstance) {
      chartInstance.resize();
    }
  });

  resizeObserver.observe(chartRef.value);
}

function cleanup() {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }

  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
}

// 暴露图表实例给父组件
defineExpose({
  getChartInstance: () => chartInstance,
  resize: () => chartInstance?.resize(),
  refresh: () => {
    if (chartInstance && props.options) {
      chartInstance.setOption(props.options, true);
    }
  },
});
</script>

<style scoped>
.chart-container {
  position: relative;
  width: 100%;
}

.chart-content {
  transition: opacity 0.3s ease;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.loading-text {
  margin-top: 8px;
  font-size: 14px;
  color: #666;
}

.is-loading {
  font-size: 24px;
  color: #007aff;
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
