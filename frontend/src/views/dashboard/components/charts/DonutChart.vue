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
  showPercentage?: boolean;
  innerRadius?: string;
  outerRadius?: string;
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
  loading: false,
  loadingText: "加载中...",
  showPercentage: true,
  innerRadius: "40%",
  outerRadius: "70%",
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

  // 计算总数用于显示百分比
  const total = props.data.reduce((sum, item) => sum + item.value, 0);

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
      trigger: "item",
      formatter: (params: any) => {
        const percentage = ((params.value / total) * 100).toFixed(1);
        return `${params.seriesName}<br/>${params.name}: ${params.value} (${percentage}%)`;
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

    legend: {
      orient: "horizontal",
      bottom: "5%",
      left: "center",
      itemGap: 20,
      textStyle: {
        fontSize: 12,
        color: "#666",
      },
      formatter: (name: string) => {
        const item = props.data.find((d) => d.name === name);
        if (item && props.showPercentage) {
          const percentage = ((item.value / total) * 100).toFixed(1);
          return `${name} (${percentage}%)`;
        }
        return name;
      },
    },

    series: [
      {
        name: props.title || "统计",
        type: "pie",
        radius: [props.innerRadius, props.outerRadius],
        center: ["50%", "45%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: "#fff",
          borderWidth: 2,
        },
        label: {
          show: false,
          position: "center",
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 18,
            fontWeight: "bold",
            formatter: (params: any) => {
              const percentage = ((params.value / total) * 100).toFixed(1);
              return `${params.name}\n${percentage}%`;
            },
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: "rgba(0, 0, 0, 0.2)",
          },
        },
        labelLine: {
          show: false,
        },
        data: props.data.map((item) => ({
          name: item.name,
          value: item.value,
          itemStyle: item.color
            ? {
                color: item.color,
                borderColor: "#fff",
                borderWidth: 2,
              }
            : {
                borderColor: "#fff",
                borderWidth: 2,
              },
        })),
      },
    ],

    animation: true,
    animationType: "scale",
    animationEasing: "elasticOut",
    animationDelay: (idx: number) => idx * 100,
  };
});
</script>

<style scoped>
/* 组件特定样式 */
</style>
