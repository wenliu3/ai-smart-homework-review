import { ref, onUnmounted } from "vue";
import { ElNotification } from "element-plus";
import { checkAiSupport } from "@/config/ai-config";

/**
 * AI评价轮询组合式函数
 * 用于在AI评价过程中进行智能轮询，及时获取评价结果
 */
export function useAiReviewPolling() {
  // 轮询状态
  const isPolling = ref(false);
  const pollingCount = ref(0);

  // 轮询定时器
  let pollingTimer: NodeJS.Timeout | null = null;

  /**
   * 获取轮询间隔（渐进式轮询）
   * @param count 轮询次数
   * @returns 轮询间隔（毫秒）
   */
  const getPollingInterval = (count: number): number => {
    if (count < 10) return 3000; // 前30秒：每3秒一次
    if (count < 22) return 5000; // 30-60秒：每5秒一次
    if (count < 40) return 8000; // 1-3分钟：每8秒一次
    return 15000; // 3分钟后：每15秒一次
  };

  /**
   * 判断是否需要继续轮询
   * @param submissionStatus 提交状态
   * @param hasAiReview 是否有AI评价结果
   * @param assignment 作业信息
   * @param maxCount 最大轮询次数
   * @returns 是否继续轮询
   */
  const shouldContinuePolling = (
    submissionStatus?: string,
    hasAiReview?: boolean,
    assignment?: any,
    maxCount = 60 // 最多轮询60次（约5-8分钟）
  ): boolean => {
    // 如果已经有AI评价结果，停止轮询
    if (hasAiReview) {
      console.log("🛑 停止轮询：AI评价已完成");
      return false;
    }

    // 如果状态不是submitted，停止轮询
    if (submissionStatus !== "submitted") {
      console.log("🛑 停止轮询：提交状态变更为", submissionStatus);
      return false;
    }

    // 使用统一的AI支持检查
    if (assignment) {
      try {
        const aiSupport = checkAiSupport(assignment);

        if (!aiSupport.supported) {
          console.log("🛑 停止轮询：", aiSupport.reason);
          return false;
        }
      } catch (error) {
        console.warn("⚠️ 无法检查AI支持状态，继续轮询");
      }
    }

    // 如果轮询次数超过最大值，停止轮询
    if (pollingCount.value >= maxCount) {
      console.log("🛑 停止轮询：达到最大轮询次数", maxCount);
      return false;
    }

    return true;
  };

  /**
   * 开始轮询
   * @param loadDataFn 数据加载函数
   * @param getCurrentStatus 获取当前状态的函数
   */
  const startPolling = (
    loadDataFn: () => Promise<void>,
    getCurrentStatus: () => {
      status?: string;
      hasAiReview?: boolean;
      hasAiError?: boolean;
      assignment?: any;
    }
  ) => {
    // 如果已经在轮询中，先停止之前的轮询
    if (isPolling.value) {
      stopPolling();
    }

    console.log("🔄 开始AI评价轮询...");
    isPolling.value = true;
    pollingCount.value = 0;

    const poll = async () => {
      try {
        // 执行数据加载
        await loadDataFn();

        // 获取当前状态
        const { status, hasAiReview, hasAiError, assignment } =
          getCurrentStatus();

        pollingCount.value++;
        console.log(
          `🔄 轮询第${pollingCount.value}次，状态: ${status}, AI评价: ${
            hasAiReview ? "已完成" : "进行中"
          }, AI错误: ${hasAiError ? "有错误" : "无错误"}`
        );

        // 🔥 优先检查AI错误状态
        if (hasAiError) {
          console.log("❌ 检测到AI评价失败，停止轮询");
          stopPolling();
          return;
        }

        // 检查是否需要继续轮询
        if (!shouldContinuePolling(status, hasAiReview, assignment)) {
          if (hasAiReview) {
            // AI评价完成，显示通知
            ElNotification({
              title: "AI评价完成",
              message: "您的作业已完成AI智能评价，请查看评价结果",
              type: "success",
              duration: 5000,
              position: "top-right",
            });
            console.log("✅ AI评价完成，停止轮询");
          } else {
            console.log("⏹️ 轮询条件不满足，停止轮询");
          }

          stopPolling();
          return;
        }

        // 设置下次轮询
        const interval = getPollingInterval(pollingCount.value);
        pollingTimer = setTimeout(poll, interval);
      } catch (error) {
        console.error("❌ 轮询过程中发生错误:", error);
        // 出错时也要继续轮询，但延长间隔
        const interval = Math.max(
          getPollingInterval(pollingCount.value) * 2,
          10000
        );
        pollingTimer = setTimeout(poll, interval);
      }
    };

    // 开始第一次轮询（延迟2秒开始，给AI一些处理时间）
    pollingTimer = setTimeout(poll, 2000);
  };

  /**
   * 停止轮询
   */
  const stopPolling = () => {
    if (pollingTimer) {
      clearTimeout(pollingTimer);
      pollingTimer = null;
    }
    isPolling.value = false;
    pollingCount.value = 0;
    console.log("⏹️ AI评价轮询已停止");
  };

  /**
   * 页面可见性变化处理
   * 当页面不可见时暂停轮询，可见时恢复
   */
  const handleVisibilityChange = (
    loadDataFn: () => Promise<void>,
    getCurrentStatus: () => { status?: string; hasAiReview?: boolean }
  ) => {
    const onVisibilityChange = () => {
      if (document.hidden) {
        // 页面不可见，暂停轮询
        if (isPolling.value) {
          console.log("👁️ 页面不可见，暂停轮询");
          stopPolling();
        }
      } else {
        // 页面可见，检查是否需要恢复轮询
        const { status, hasAiReview } = getCurrentStatus();
        if (shouldContinuePolling(status, hasAiReview)) {
          console.log("👁️ 页面可见，恢复轮询");
          startPolling(loadDataFn, getCurrentStatus);
        }
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);

    // 返回清理函数
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  };

  // 组件卸载时自动清理
  onUnmounted(() => {
    stopPolling();
  });

  return {
    // 状态
    isPolling,
    pollingCount,

    // 方法
    startPolling,
    stopPolling,
    handleVisibilityChange,
    shouldContinuePolling,
  };
}
