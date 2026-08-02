"""Celery 父进程收口批改 Run：硬超时（time_limit）的最后兜底。

软超时（soft_time_limit）由子进程内的 SoftTimeLimitExceeded 捕获，在
execute_grading_job 的 except 分支用稳定错误码标记 run；硬超时（time_limit）
是 Celery 父进程直接终止子进程，子进程没有任何机会执行收口逻辑。因此必须
在父进程的 Request.on_timeout 钩子里，用独立会话把 run 收口为
failed/AGENT_GRADING_TIMEOUT。

本模块只依赖 assistant_database / crud.agent_run / agent.contracts /
tasks.celery_app，绝不反向依赖 tasks.grading，避免循环导入。
"""
import logging

from celery.worker.request import Request as CeleryRequest

from ..agent.contracts import AGENT_GRADING_TIMEOUT
from ..assistant_database import AssistantSessionLocal
from ..crud import agent_run
from .celery_app import celery_app

logger = logging.getLogger(__name__)


def mark_grading_timeout_from_request(payload: dict) -> None:
    """把 payload 对应的批改 run 收口为 failed/AGENT_GRADING_TIMEOUT。

    由 Celery 父进程在硬超时钩子里调用：自建并关闭 AssistantSessionLocal 会话，
    复用 agent_run.fail_run 语义（只对 running/processing 生效、幂等、
    completed/cancelled 等终态永不被覆盖）。任何异常只记录日志，绝不向上抛——
    绝不用清理异常遮盖 Celery 原始超时失败。
    """
    run_id = (payload or {}).get("run_id")
    user_id = (payload or {}).get("user_id")
    if not run_id or user_id is None:
        logger.warning(
            "批改硬超时收口缺少 run_id/user_id，跳过收口: %s", payload,
        )
        return
    db = AssistantSessionLocal()
    try:
        agent_run.fail_run(db, run_id, user_id, AGENT_GRADING_TIMEOUT)
    except Exception:
        logger.exception(
            "批改硬超时收口 run 失败 run_id=%s user_id=%s", run_id, user_id,
        )
    finally:
        db.close()


class GradingTaskRequest(CeleryRequest):
    """批改任务的 Celery Request：硬超时时在父进程收口对应 run。

    execute_using_pool 把 Request.on_timeout 注册为池的 timeout_callback；
    硬超时（soft=False）时父进程调用它，此时子进程已被 kill，只有这里能写库。
    """

    def on_timeout(self, soft, timeout):
        super().on_timeout(soft, timeout)
        if not soft:
            mark_grading_timeout_from_request(self.kwargs)


class GradingTask(celery_app.Task):
    """批改任务基类：挂上自定义 Request 以拦截父进程硬超时收口。"""

    Request = GradingTaskRequest
