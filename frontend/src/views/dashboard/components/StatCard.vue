<template>
  <div
    class="stat-card"
    :class="[`stat-card--${variant}`, { 'stat-card--loading': loading }]"
  >
    <div class="stat-card__icon" v-if="icon">
      <component :is="iconComponent" :class="iconClass" />
    </div>

    <div class="stat-card__content">
      <div class="stat-card__title">{{ title }}</div>
      <div class="stat-card__value">
        <span class="value-number">{{ formattedValue }}</span>
        <span class="value-unit" v-if="unit">{{ unit }}</span>
      </div>
      <div class="stat-card__subtitle" v-if="subtitle">{{ subtitle }}</div>

      <!-- 趋势指示器 -->
      <div class="stat-card__trend" v-if="trend">
        <el-icon :class="trendIconClass">
          <component :is="trendIcon" />
        </el-icon>
        <span :class="trendTextClass">{{ trendText }}</span>
      </div>

      <!-- 进度条 -->
      <div
        class="stat-card__progress"
        v-if="showProgress && progress !== undefined"
      >
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{ width: `${Math.min(progress, 100)}%` }"
          ></div>
        </div>
        <span class="progress-text">{{ progress }}%</span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div class="stat-card__loading" v-if="loading">
      <el-icon class="is-loading">
        <Loading />
      </el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import {
  Loading,
  User,
  School,
  Document,
  List,
  // Robot, // 这个图标不存在，用其他替代
  TrendCharts,
  ArrowUp,
  ArrowDown,
  Minus,
} from "@element-plus/icons-vue";

interface Props {
  title: string;
  value: number | string;
  unit?: string;
  subtitle?: string;
  icon?: string;
  variant?: "default" | "primary" | "success" | "warning" | "danger" | "info";
  loading?: boolean;
  trend?: "up" | "down" | "stable";
  trendValue?: number;
  progress?: number;
  showProgress?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  loading: false,
  showProgress: false,
});

// 图标映射
const iconMap: Record<string, any> = {
  user: User,
  school: School,
  document: Document,
  list: List,
  robot: TrendCharts, // 用TrendCharts替代Robot
  trend: TrendCharts,
};

const iconComponent = computed(() => {
  return props.icon ? iconMap[props.icon] || User : null;
});

const iconClass = computed(() => {
  return `stat-icon stat-icon--${props.variant}`;
});

// 格式化数值显示
const formattedValue = computed(() => {
  if (props.loading) return "--";

  if (typeof props.value === "number") {
    // 大数值格式化
    if (props.value >= 10000) {
      return (props.value / 10000).toFixed(1) + "万";
    } else if (props.value >= 1000) {
      return (props.value / 1000).toFixed(1) + "k";
    }
    return props.value.toLocaleString();
  }

  return props.value;
});

// 趋势相关计算
const trendIcon = computed(() => {
  switch (props.trend) {
    case "up":
      return ArrowUp;
    case "down":
      return ArrowDown;
    case "stable":
      return Minus;
    default:
      return null;
  }
});

const trendIconClass = computed(() => {
  return `trend-icon trend-icon--${props.trend}`;
});

const trendTextClass = computed(() => {
  return `trend-text trend-text--${props.trend}`;
});

const trendText = computed(() => {
  if (!props.trendValue) return "";

  const prefix = props.trend === "up" ? "+" : props.trend === "down" ? "-" : "";
  return `${prefix}${Math.abs(props.trendValue)}%`;
});
</script>

<style scoped>
.stat-card {
  position: relative;
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f0f0f0;
  transition: all 0.3s ease;
  overflow: hidden;
}

.stat-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.stat-card--loading {
  opacity: 0.7;
}

/* 变体样式 */
.stat-card--primary {
  background: linear-gradient(135deg, #007aff 0%, #5ac8fa 100%);
  color: white;
  border: none;
}

.stat-card--success {
  background: linear-gradient(135deg, #34c759 0%, #30d158 100%);
  color: white;
  border: none;
}

.stat-card--warning {
  background: linear-gradient(135deg, #ff9f0a 0%, #ffcc02 100%);
  color: white;
  border: none;
}

.stat-card--danger {
  background: linear-gradient(135deg, #ff3b30 0%, #ff6b6b 100%);
  color: white;
  border: none;
}

.stat-card--info {
  background: linear-gradient(135deg, #af52de 0%, #da70d6 100%);
  color: white;
  border: none;
}

.stat-card__icon {
  position: absolute;
  top: 16px;
  right: 16px;
  opacity: 0.3;
}

.stat-icon {
  font-size: 24px;
}

.stat-icon--primary,
.stat-icon--success,
.stat-icon--warning,
.stat-icon--danger,
.stat-icon--info {
  color: rgba(255, 255, 255, 0.8);
}

.stat-card__content {
  position: relative;
  z-index: 1;
}

.stat-card__title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.stat-card--primary .stat-card__title,
.stat-card--success .stat-card__title,
.stat-card--warning .stat-card__title,
.stat-card--danger .stat-card__title,
.stat-card--info .stat-card__title {
  color: rgba(255, 255, 255, 0.9);
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  margin-bottom: 4px;
}

.value-number {
  font-size: 28px;
  font-weight: 700;
  color: #1d1d1f;
  line-height: 1;
}

.stat-card--primary .value-number,
.stat-card--success .value-number,
.stat-card--warning .value-number,
.stat-card--danger .value-number,
.stat-card--info .value-number {
  color: white;
}

.value-unit {
  font-size: 14px;
  color: #666;
  margin-left: 4px;
  font-weight: 400;
}

.stat-card--primary .value-unit,
.stat-card--success .value-unit,
.stat-card--warning .value-unit,
.stat-card--danger .value-unit,
.stat-card--info .value-unit {
  color: rgba(255, 255, 255, 0.8);
}

.stat-card__subtitle {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.stat-card--primary .stat-card__subtitle,
.stat-card--success .stat-card__subtitle,
.stat-card--warning .stat-card__subtitle,
.stat-card--danger .stat-card__subtitle,
.stat-card--info .stat-card__subtitle {
  color: rgba(255, 255, 255, 0.7);
}

.stat-card__trend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
}

.trend-icon {
  font-size: 14px;
}

.trend-icon--up {
  color: #34c759;
}

.trend-icon--down {
  color: #ff3b30;
}

.trend-icon--stable {
  color: #8e8e93;
}

.trend-text {
  font-size: 12px;
  font-weight: 500;
}

.trend-text--up {
  color: #34c759;
}

.trend-text--down {
  color: #ff3b30;
}

.trend-text--stable {
  color: #8e8e93;
}

.stat-card__progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
}

.stat-card--primary .progress-bar,
.stat-card--success .progress-bar,
.stat-card--warning .progress-bar,
.stat-card--danger .progress-bar,
.stat-card--info .progress-bar {
  background: rgba(255, 255, 255, 0.3);
}

.progress-fill {
  height: 100%;
  background: #007aff;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.stat-card--success .progress-fill {
  background: rgba(255, 255, 255, 0.9);
}

.stat-card--warning .progress-fill {
  background: rgba(255, 255, 255, 0.9);
}

.stat-card--danger .progress-fill {
  background: rgba(255, 255, 255, 0.9);
}

.stat-card--info .progress-fill {
  background: rgba(255, 255, 255, 0.9);
}

.progress-text {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  min-width: 35px;
  text-align: right;
}

.stat-card--primary .progress-text,
.stat-card--success .progress-text,
.stat-card--warning .progress-text,
.stat-card--danger .progress-text,
.stat-card--info .progress-text {
  color: rgba(255, 255, 255, 0.9);
}

.stat-card__loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(2px);
}

.is-loading {
  font-size: 20px;
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

/* 响应式设计 */
@media (max-width: 768px) {
  .stat-card {
    padding: 16px;
  }

  .value-number {
    font-size: 24px;
  }

  .stat-card__title {
    font-size: 13px;
  }
}
</style>
