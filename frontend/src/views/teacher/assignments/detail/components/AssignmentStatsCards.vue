<template>
  <div class="assignment-stats-cards">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon class-icon">
              <el-icon><School /></el-icon>
            </div>
            <div class="stats-info">
              <div class="stats-value">{{ classCount }}</div>
              <div class="stats-label">关联班级</div>
              <div class="class-tags">
                <template v-if="displayClasses.length > 0">
                  <el-tag
                    v-for="cls in displayClasses"
                    :key="cls.id"
                    size="small"
                    type="warning"
                    class="class-tag"
                  >
                    {{ cls.name }}
                  </el-tag>
                  <el-tooltip
                    v-if="hiddenClassCount > 0"
                    :content="hiddenClassNames"
                    placement="bottom"
                  >
                    <el-tag size="small" type="warning" class="more-tag">
                      +{{ hiddenClassCount }}
                    </el-tag>
                  </el-tooltip>
                </template>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon students-icon">
              <el-icon><User /></el-icon>
            </div>
            <div class="stats-info">
              <div class="stats-value">
                <span class="primary-num">{{ submittedCount }}</span>
                <span class="secondary-num">/ {{ totalStudents }}</span>
              </div>
              <div class="stats-label">已提交/总学生</div>
              <div class="stats-percent">
                <el-progress
                  :percentage="submissionRate"
                  :show-text="false"
                  :stroke-width="4"
                  :color="submissionRateColor"
                />
                <span class="percent-text"
                  >{{ submissionRate.toFixed(1) }}%</span
                >
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon reviewed-icon">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="stats-info">
              <div class="stats-value">
                <span class="primary-num">{{ reviewedCount }}</span>
                <span class="secondary-num">/ {{ submittedCount }}</span>
              </div>
              <div class="stats-label">已批改/已提交</div>
              <div class="stats-percent">
                <el-progress
                  :percentage="reviewRate"
                  :show-text="false"
                  :stroke-width="4"
                  color="#67c23a"
                />
                <span class="percent-text">{{ reviewRate.toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="stats-card">
          <div class="stats-content">
            <div class="stats-icon pending-icon">
              <el-icon><Clock /></el-icon>
            </div>
            <div class="stats-info">
              <div class="stats-value">{{ pendingCount }}</div>
              <div class="stats-label">待批改</div>
              <div class="stats-tip" v-if="pendingCount > 0">
                <el-tag type="warning" size="small">需要处理</el-tag>
              </div>
              <div class="stats-tip" v-else-if="submittedCount > 0">
                <el-tag type="success" size="small">全部完成</el-tag>
              </div>
              <div class="stats-tip" v-else>
                <el-tag type="info" size="small">暂无提交</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { School, User, CircleCheck, Clock } from "@element-plus/icons-vue";
import type { AssignmentDetail } from "@/api/assignments";

interface Props {
  assignmentDetail: AssignmentDetail | null;
}

const props = defineProps<Props>();

// 计算统计数据
const classCount = computed(() => props.assignmentDetail?.classes?.length || 0);
const totalStudents = computed(
  () => props.assignmentDetail?.totalStudents || 0
);
const submittedCount = computed(
  () => props.assignmentDetail?.submissionStats?.totalSubmissions || 0
);
const reviewedCount = computed(
  () => props.assignmentDetail?.submissionStats?.reviewedSubmissions || 0
);
const pendingCount = computed(
  () => props.assignmentDetail?.submissionStats?.pendingSubmissions || 0
);

// 计算提交率
const submissionRate = computed(() => {
  if (totalStudents.value === 0) return 0;
  return (submittedCount.value / totalStudents.value) * 100;
});

// 计算批改率
const reviewRate = computed(() => {
  if (submittedCount.value === 0) return 0;
  return (reviewedCount.value / submittedCount.value) * 100;
});

// 提交率颜色
const submissionRateColor = computed(() => {
  const rate = submissionRate.value;
  if (rate >= 80) return "#67c23a";
  if (rate >= 60) return "#e6a23c";
  return "#f56c6c";
});

// 班级标签相关
const displayClasses = computed(() => {
  const classes = props.assignmentDetail?.classes || [];
  return classes.slice(0, 2); // 最多显示2个班级标签
});

const hiddenClassCount = computed(() => {
  const classes = props.assignmentDetail?.classes || [];
  return Math.max(0, classes.length - 2);
});

const hiddenClassNames = computed(() => {
  const classes = props.assignmentDetail?.classes || [];
  if (classes.length <= 2) return "";
  return classes
    .slice(2)
    .map((cls) => cls.name)
    .join("、");
});

defineOptions({
  name: "AssignmentStatsCards",
});
</script>

<style scoped>
.assignment-stats-cards {
  margin-bottom: 16px;
}

.stats-card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
}

.stats-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.stats-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stats-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
  flex-shrink: 0;
}

.class-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.students-icon {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.reviewed-icon {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.pending-icon {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.stats-info {
  flex: 1;
  min-width: 0;
}

.stats-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.2;
  margin-bottom: 4px;
}

.primary-num {
  color: #1f2937;
}

.secondary-num {
  color: #9ca3af;
  font-size: 18px;
  font-weight: 500;
}

.stats-label {
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
}

.stats-percent {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.stats-percent :deep(.el-progress) {
  flex: 1;
}

.percent-text {
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
  min-width: 45px;
  text-align: right;
}

.stats-tip {
  /* margin-top: 8px; */
}

.class-tags {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.class-tag {
  font-size: 14px;
  height: 18px;
  line-height: 16px;
  padding: 0 5px;
  border-radius: 3px;
  transform: scale(0.9);
  transform-origin: left center;
}

.more-tag {
  font-size: 11px;
  height: 18px;
  line-height: 16px;
  padding: 0 5px;
  border-radius: 3px;
  transform: scale(0.9);
  transform-origin: left center;
  cursor: help;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .stats-value {
    font-size: 20px;
  }

  .secondary-num {
    font-size: 16px;
  }

  .stats-icon {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }
}

@media (max-width: 992px) {
  .assignment-stats-cards :deep(.el-row) {
    margin-left: 0 !important;
    margin-right: 0 !important;
  }

  .assignment-stats-cards :deep(.el-col) {
    padding-left: 8px !important;
    padding-right: 8px !important;
  }
}

@media (max-width: 768px) {
  .assignment-stats-cards :deep(.el-col) {
    margin-bottom: 12px;
    padding-left: 4px !important;
    padding-right: 4px !important;
  }

  .stats-content {
    gap: 12px;
  }

  .stats-icon {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }

  .stats-value {
    font-size: 18px;
  }
}

@media (max-width: 576px) {
  .assignment-stats-cards :deep(.el-col) {
    flex: 0 0 50% !important;
    max-width: 50% !important;
  }
}

.stats-card :deep(.el-card__body) {
  padding: 10px 20px;
}
</style>
