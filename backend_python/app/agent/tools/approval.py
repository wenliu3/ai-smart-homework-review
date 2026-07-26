"""受控写操作草案工具：只构造草案，不执行业务写入。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from ..contracts import ActionDraft, ActionType, RiskLevel


def canonical_action_payload(
    action_type: str,
    target_type: str,
    target_id: str | None,
    parameters: dict,
) -> bytes:
    return json.dumps(
        {
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "parameters": parameters,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def calculate_payload_hash(
    action_type: str,
    target_type: str,
    target_id: str | None,
    parameters: dict,
) -> str:
    return hashlib.sha256(canonical_action_payload(
        action_type,
        target_type,
        target_id,
        parameters,
    )).hexdigest()


def create_action_draft(
    *,
    action_type: str,
    target_type: str,
    target_id: str | None,
    parameters: dict,
    summary: str,
    risk_level: str,
    ttl_seconds: int = 900,
    idempotency_seed: str = "",
) -> ActionDraft:
    """创建服务端签名草案；不接受客户端提供哈希或幂等键。"""

    if ttl_seconds <= 0 or ttl_seconds > 3600:
        raise ValueError("审批有效期必须在 1-3600 秒之间")
    action = ActionType(action_type)
    risk = RiskLevel(risk_level)
    payload_hash = calculate_payload_hash(
        action.value,
        target_type,
        target_id,
        parameters,
    )
    idempotency_key = hashlib.sha256(
        f"{payload_hash}:{idempotency_seed}".encode("utf-8"),
    ).hexdigest()
    return ActionDraft(
        action_type=action,
        target_type=target_type,
        target_id=target_id,
        parameters=parameters,
        summary=summary,
        risk_level=risk,
        expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
        payload_hash=payload_hash,
        idempotency_key=idempotency_key,
    )


__all__ = [
    "calculate_payload_hash",
    "canonical_action_payload",
    "create_action_draft",
]
