<template>
  <article
    class="stat-card"
    :class="[`stat-card--${variant}`, { 'stat-card--loading': loading }]"
  >
    <div class="stat-card__top">
      <span class="stat-card__title">{{ title }}</span>
      <span v-if="iconComponent" class="stat-card__icon">
        <component :is="iconComponent" />
      </span>
    </div>

    <div class="stat-card__value">
      <strong>{{ formattedValue }}</strong>
      <span v-if="unit">{{ unit }}</span>
    </div>
    <p v-if="subtitle" class="stat-card__subtitle">{{ subtitle }}</p>

    <div v-if="trend" class="stat-card__trend" :class="`is-${trend}`">
      <el-icon><component :is="trendIcon" /></el-icon>
      <span>{{ trendText }}</span>
    </div>

    <div
      v-if="showProgress && progress !== undefined"
      class="stat-card__progress"
    >
      <span
        ><i :style="{ width: `${Math.min(Math.max(progress, 0), 100)}%` }"></i
      ></span>
      <small>{{ progress }}%</small>
    </div>

    <div v-if="loading" class="stat-card__loading">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowDown,
  ArrowUp,
  Document,
  List,
  Loading,
  Minus,
  School,
  TrendCharts,
  User,
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

const iconMap: Record<string, any> = {
  user: User,
  school: School,
  document: Document,
  list: List,
  robot: TrendCharts,
  trend: TrendCharts,
};

const iconComponent = computed(() =>
  props.icon ? iconMap[props.icon] || User : null
);

const formattedValue = computed(() => {
  if (props.loading) return "--";
  if (typeof props.value !== "number") return props.value;
  if (props.value >= 10000) return `${(props.value / 10000).toFixed(1)}万`;
  if (props.value >= 1000) return `${(props.value / 1000).toFixed(1)}k`;
  return props.value.toLocaleString();
});

const trendIcon = computed(() => {
  if (props.trend === "up") return ArrowUp;
  if (props.trend === "down") return ArrowDown;
  return Minus;
});

const trendText = computed(() => {
  const prefix = props.trend === "up" ? "+" : props.trend === "down" ? "-" : "";
  return props.trendValue !== undefined
    ? `${prefix}${Math.abs(props.trendValue)}%`
    : props.trend === "stable"
    ? "保持稳定"
    : "";
});
</script>

<style scoped>
.stat-card {
  position: relative;
  min-width: 0;
  overflow: hidden;
  padding: 17px 18px;
  border: 1px solid #e8eaf1;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 40, 68, 0.045);
}

.stat-card::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: #7d74a8;
  content: "";
}

.stat-card--primary::before {
  background: #6558d9;
}
.stat-card--success::before {
  background: #2b9b70;
}
.stat-card--warning::before {
  background: #d39136;
}
.stat-card--danger::before {
  background: #dd5965;
}
.stat-card--info::before {
  background: #568bc6;
}

.stat-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.stat-card__title {
  color: #747b8f;
  font-size: 12px;
  font-weight: 600;
}
.stat-card__icon {
  display: inline-flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: #f1efff;
  color: #6558d9;
}
.stat-card--success .stat-card__icon {
  background: #eaf8f2;
  color: #278e68;
}
.stat-card--warning .stat-card__icon {
  background: #fff5e6;
  color: #c17b27;
}
.stat-card--danger .stat-card__icon {
  background: #fff0f1;
  color: #d6525e;
}
.stat-card--info .stat-card__icon {
  background: #edf5ff;
  color: #4f82be;
}
.stat-card__icon :deep(svg) {
  width: 16px;
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 11px;
}
.stat-card__value strong {
  overflow: hidden;
  color: #2d3248;
  font-size: 27px;
  line-height: 1;
  text-overflow: ellipsis;
}
.stat-card__value span {
  color: #878ea2;
  font-size: 12px;
}
.stat-card__subtitle {
  margin: 7px 0 0;
  color: #9ca2b3;
  font-size: 10px;
}

.stat-card__trend {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  color: #8d93a4;
  font-size: 10px;
}
.stat-card__trend.is-up {
  color: #278e68;
}
.stat-card__trend.is-down {
  color: #d6525e;
}

.stat-card__progress {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 10px;
}
.stat-card__progress > span {
  height: 5px;
  flex: 1;
  overflow: hidden;
  border-radius: 5px;
  background: #eceef3;
}
.stat-card__progress i {
  display: block;
  height: 100%;
  border-radius: 5px;
  background: linear-gradient(90deg, #d3a04b, #ebc56f);
}
.stat-card__progress small {
  min-width: 30px;
  color: #8c92a3;
  font-size: 9px;
  text-align: right;
}

.stat-card__loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.84);
  color: #6558d9;
  backdrop-filter: blur(2px);
}
.is-loading {
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 520px) {
  .stat-card {
    padding: 14px;
  }
  .stat-card__value strong {
    font-size: 23px;
  }
}
</style>
