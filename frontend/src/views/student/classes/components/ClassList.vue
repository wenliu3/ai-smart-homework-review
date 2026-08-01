<template>
  <aside class="class-list">
    <header class="class-list__header">
      <div>
        <p>COURSES</p>
        <h2>班级列表</h2>
      </div>
      <el-tooltip content="加入班级" placement="bottom">
        <el-button
          class="class-list__join"
          type="primary"
          :icon="Plus"
          circle
          @click="handleJoinClass"
        />
      </el-tooltip>
    </header>

    <div class="class-list__search">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索班级"
        clearable
        :prefix-icon="Search"
        @keyup.enter="handleSearch"
        @clear="handleClearSearch"
      />
      <el-button :loading="searchLoading" @click="handleSearch">搜索</el-button>
    </div>

    <div class="class-list__scroll">
      <div v-if="classLoading" class="class-list__loading">
        <el-skeleton
          v-for="i in 3"
          :key="i"
          animated
          class="class-list__skeleton"
        />
      </div>

      <el-empty
        v-else-if="classes.length === 0"
        description="暂无班级"
        :image-size="80"
      >
        <el-button type="primary" @click="handleJoinClass">加入班级</el-button>
      </el-empty>

      <div v-else class="class-list__cards">
        <button
          v-for="classItem in classes"
          :key="classItem._id"
          type="button"
          class="class-card"
          :class="{ active: selectedClassId === classItem._id }"
          @click="handleSelectClass(classItem)"
        >
          <span
            class="class-card__accent"
            :style="getClassCoverStyle(classItem.name)"
            aria-hidden="true"
          ></span>
          <span class="class-card__content">
            <span class="class-card__title-row">
              <strong :title="classItem.name">{{ classItem.name }}</strong>
              <span
                class="class-card__status"
                :class="`class-card__status--${getClassStatusType(
                  classItem.status
                )}`"
              >
                {{ getClassStatusText(classItem.status) }}
              </span>
            </span>
            <span class="class-card__meta">
              <span
                ><el-icon><User /></el-icon
                >{{ classItem.teacherName || "未知教师" }}</span
              >
              <span
                ><el-icon><UserFilled /></el-icon
                >{{ classItem.studentCount || 0 }} 人</span
              >
            </span>
          </span>
        </button>

        <div class="class-list__footer">
          <el-button
            v-if="!pageState.isAllLoaded"
            text
            type="primary"
            :loading="loadingMore"
            @click="loadMore"
          >
            {{ loadingMore ? "加载中..." : "加载更多" }}
          </el-button>
          <span v-else>已显示全部班级</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { inject, nextTick, onMounted, reactive, ref, type Ref } from "vue";
import { ElMessage } from "element-plus";
import { Plus, Search, User, UserFilled } from "@element-plus/icons-vue";
import { getClassList } from "../../../../api/classes";
import { useClassManagement } from "../composables/useClassManagement";

const selectedClassId = inject<Ref<string | null>>("selectedClassId")!;
const setSelectedClass = inject<(classItem: any) => void>("setSelectedClass")!;
const showJoinDialog = inject<Ref<boolean>>("showJoinDialog")!;

const classLoading = ref(true);
const loadingMore = ref(false);
const searchLoading = ref(false);
const classes = ref<any[]>([]);
const searchKeyword = ref("");
const pageState = reactive({
  page: 1,
  limit: 10,
  total: 0,
  isAllLoaded: false,
});

const { getClassStatusType, getClassStatusText } = useClassManagement();

const coverPalettes = [
  ["#6558d9", "#8d7be8"],
  ["#3178c6", "#6aa8e8"],
  ["#2f8f83", "#68b9a9"],
  ["#a45f92", "#d285b6"],
  ["#4f67a8", "#8198d1"],
  ["#8b6b3f", "#c49a62"],
];

const getClassCoverStyle = (name = "") => {
  const hash = Array.from(name).reduce(
    (sum, char) => sum + char.charCodeAt(0),
    0
  );
  const [start, end] = coverPalettes[hash % coverPalettes.length];
  return { background: `linear-gradient(135deg, ${start}, ${end})` };
};

const loadClasses = async (type = "initData", search?: string) => {
  if (type === "initData") {
    classLoading.value = true;
    pageState.page = 1;
    pageState.isAllLoaded = false;
  } else {
    loadingMore.value = true;
  }

  try {
    const response = await getClassList({
      page: pageState.page,
      limit: pageState.limit,
      ...(search ? { search } : {}),
    });
    const items = response.items || [];
    pageState.total = response.total;
    classes.value = type === "loadMore" ? classes.value.concat(items) : items;
    pageState.isAllLoaded = classes.value.length >= response.total;
    if (!pageState.isAllLoaded) pageState.page += 1;

    if (classes.value.length && !selectedClassId.value) {
      handleSelectClass(classes.value[0]);
    }
  } catch (error) {
    console.error("加载班级列表失败:", error);
    ElMessage.error("加载班级列表失败");
  } finally {
    classLoading.value = false;
    loadingMore.value = false;
    searchLoading.value = false;
    if (type === "loadMore") {
      nextTick(() => {
        const target = document.querySelector(".class-list__scroll");
        target?.scrollTo({ top: target.scrollHeight, behavior: "smooth" });
      });
    }
  }
};

const handleSearch = async () => {
  if (searchLoading.value) return;
  searchLoading.value = true;
  await loadClasses("initData", searchKeyword.value.trim());
};

const handleClearSearch = async () => {
  searchKeyword.value = "";
  await loadClasses("initData");
};

const loadMore = () => loadClasses("loadMore", searchKeyword.value.trim());
const handleSelectClass = (classItem: any) => setSelectedClass(classItem);
const handleJoinClass = () => {
  showJoinDialog.value = true;
};
const refresh = () => loadClasses("initData", searchKeyword.value.trim());

defineExpose({ refresh });
onMounted(() => loadClasses());
</script>

<style scoped>
.class-list {
  display: flex;
  width: 350px;
  flex: 0 0 350px;
  flex-direction: column;
  border-right: 1px solid #e9eaf1;
  background: #fff;
}

.class-list__header,
.class-list__search {
  padding: 18px;
  border-bottom: 1px solid #eef0f5;
}
.class-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.class-list__header p {
  margin: 0 0 3px;
  color: #6b5ed5;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.class-list__header h2 {
  margin: 0;
  color: #2d3248;
  font-size: 18px;
}
.class-list__join {
  border: 0;
  background: linear-gradient(135deg, #685bdc, #5548c3);
}

.class-list__search {
  display: flex;
  gap: 8px;
}
.class-list__search :deep(.el-input__wrapper) {
  border-radius: 9px;
  box-shadow: 0 0 0 1px #e5e7ef inset;
}

.class-list__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
  background: #f9fafc;
}
.class-list__loading {
  display: grid;
  gap: 12px;
}
.class-list__skeleton {
  height: 116px;
  border-radius: 13px;
  background: #fff;
}
.class-list__cards {
  display: grid;
  gap: 12px;
}

.class-card {
  display: grid;
  overflow: hidden;
  padding: 0;
  border: 1px solid #e7e9f0;
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.class-card:hover {
  transform: translateY(-1px);
  border-color: #cfcaf3;
  box-shadow: 0 10px 24px rgba(64, 57, 117, 0.09);
}
.class-card.active {
  border-color: #8e83e5;
  box-shadow: 0 0 0 2px rgba(105, 91, 220, 0.12),
    0 10px 26px rgba(64, 57, 117, 0.09);
}

.class-card__accent {
  display: block;
  height: 7px;
  background: linear-gradient(135deg, #6558d9, #8d7be8);
}

.class-card__content {
  display: grid;
  gap: 11px;
  padding: 13px 14px 14px;
}
.class-card__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.class-card__title-row strong {
  overflow: hidden;
  color: #31364b;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.class-card__status {
  flex: 0 0 auto;
  padding: 3px 7px;
  border-radius: 999px;
  background: #f0f1f4;
  color: #858b9c;
  font-size: 10px;
  font-weight: 700;
}
.class-card__status--success {
  background: #eaf8f2;
  color: #29936b;
}
.class-card__status--warning {
  background: #fff5e7;
  color: #c17a25;
}

.class-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #8e95a7;
  font-size: 11px;
}
.class-card__meta > span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.class-list__footer {
  padding: 6px 0 2px;
  color: #a0a5b4;
  text-align: center;
  font-size: 11px;
}
.class-list__scroll::-webkit-scrollbar {
  width: 5px;
}
.class-list__scroll::-webkit-scrollbar-thumb {
  border-radius: 5px;
  background: #ced1dc;
}

@media (max-width: 860px) {
  .class-list {
    width: 100%;
    flex-basis: auto;
    border-right: 0;
    border-bottom: 1px solid #e9eaf1;
  }
  .class-list__scroll {
    overflow-x: auto;
    overflow-y: hidden;
  }
  .class-list__cards {
    display: flex;
  }
  .class-card {
    width: 250px;
    flex: 0 0 250px;
  }
  .class-list__footer {
    display: flex;
    min-width: 100px;
    align-items: center;
  }
}
</style>
