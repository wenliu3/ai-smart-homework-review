<template>
  <BaseChart
    :options="chartOptions"
    :loading="loading"
    :height="height"
    :loading-text="loadingText"
  />
</template>

<script setup lang="ts">
import { computed } from "vue";
import BaseChart from "./BaseChart.vue";

interface ChartData {
  name: string;
  value: number;
  color?: string;
}

interface Props {
  data: ChartData[];
  title?: string;
  loading?: boolean;
  loadingText?: string;
  height?: number;
  horizontal?: boolean;
  showValue?: boolean;
  unit?: string;
  maxValue?: number;
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
  loading: false,
  loadingText: "加载中...",
  horizontal: false,
  showValue: true,
  unit: "",
});

const chartOptions = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {
      title: {
        text: "暂无数据",
        left: "center",
        top: "center",
        textStyle: {
          fontSize: 16,
          color: "#999",
        },
      },
    };
  }

  const maxDataValue = Math.max(...props.data.map((item) => item.value));
  const yAxisMax = props.maxValue || Math.ceil(maxDataValue * 1.1);

  return {
    title: props.title
      ? {
          text: props.title,
          left: "center",
          top: "top",
          textStyle: {
            fontSize: 16,
            fontWeight: "normal",
            color: "#1D1D1F",
          },
        }
      : undefined,

    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
      formatter: (params: any) => {
        const data = params[0];
        return `${data.name}<br/>${data.seriesName}: ${data.value}${props.unit}`;
      },
      backgroundColor: "rgba(255, 255, 255, 0.95)",
      borderColor: "#E5E5E5",
      borderWidth: 1,
      textStyle: {
        color: "#1D1D1F",
        fontSize: 12,
      },
      extraCssText:
        "box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); border-radius: 6px;",
    },

    grid: {
      left: props.horizontal ? "20%" : "10%",
      right: "10%",
      top: props.title ? "15%" : "10%",
      bottom: "15%",
      containLabel: true,
    },

    xAxis: {
      type: props.horizontal ? "value" : "category",
      data: props.horizontal ? undefined : props.data.map((item) => item.name),
      max: props.horizontal ? yAxisMax : undefined,
      axisLabel: {
        color: "#666",
        fontSize: 12,
        interval: 0,
        rotate: props.horizontal ? 0 : props.data.length > 6 ? 45 : 0,
        formatter: props.horizontal
          ? (value: number) => `${value}${props.unit}`
          : undefined,
      },
      axisLine: {
        lineStyle: {
          color: "#E5E5E5",
        },
      },
      axisTick: {
        show: false,
      },
    },

    yAxis: {
      type: props.horizontal ? "category" : "value",
      data: props.horizontal ? props.data.map((item) => item.name) : undefined,
      max: props.horizontal ? undefined : yAxisMax,
      axisLabel: {
        color: "#666",
        fontSize: 12,
        formatter: props.horizontal
          ? undefined
          : (value: number) => `${value}${props.unit}`,
      },
      axisLine: {
        show: false,
      },
      axisTick: {
        show: false,
      },
      splitLine: {
        lineStyle: {
          color: "#F5F5F5",
          type: "dashed",
        },
      },
    },

    series: [
      {
        name: props.title || "数值",
        type: "bar",
        data: props.data.map((item, index) => ({
          name: item.name,
          value: item.value,
          itemStyle: {
            color: item.color || `hsl(${(index * 137.5) % 360}, 70%, 60%)`,
            borderRadius: props.horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
          },
        })),
        barWidth: "60%",
        label: props.showValue
          ? {
              show: true,
              position: props.horizontal ? "right" : "top",
              formatter: (params: any) => `${params.value}${props.unit}`,
              color: "#666",
              fontSize: 11,
            }
          : undefined,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: "rgba(0, 0, 0, 0.2)",
          },
        },
      },
    ],

    animation: true,
    animationDuration: 1000,
    animationEasing: "cubicOut",
    animationDelay: (idx: number) => idx * 100,
  };
});
</script>

<style scoped>
/* 组件特定样式 */
</style>
