"""Snowflake 简化版 ID 生成器 — 单节点纯数字递增 ID。

结构: 41 位时间戳 (ms since 2024-01-01) + 12 位序列号 = 15 位纯数字
线程安全，同毫秒内支持 4096 个 ID。
"""

import threading
import time

_EPOCH = 1700000000000  # 2024-01-01 00:00:00 毫秒
_SEQ_MAX = 4095  # 12 位序列号

_seq = 0
_seq_lock = threading.Lock()
_last_ms = 0


def generate_task_id() -> str:
    global _seq, _last_ms
    with _seq_lock:
        ms = int(time.time() * 1000) - _EPOCH
        if ms == _last_ms:
            _seq = (_seq + 1) & _SEQ_MAX
            if _seq == 0:
                while ms <= _last_ms:
                    ms = int(time.time() * 1000) - _EPOCH
        else:
            _seq = 0
        _last_ms = ms
    return str((ms << 12) | _seq)
