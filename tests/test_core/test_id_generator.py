"""Tests for id_generator — Snowflake ID generation."""

import threading
import time

from backend.core.id_generator import generate_task_id


class TestIdGenerator:
    def test_generates_numeric_string(self):
        id_ = generate_task_id()
        assert id_.isdigit()

    def test_monotonic_increasing(self):
        ids = [generate_task_id() for _ in range(100)]
        for i in range(len(ids) - 1):
            assert int(ids[i]) < int(ids[i + 1]), f"{ids[i]} >= {ids[i + 1]}"

    def test_unique_under_high_concurrency(self):
        count = 1000
        ids = []

        def produce():
            for _ in range(count // 10):
                ids.append(generate_task_id())

        threads = [threading.Thread(target=produce) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(ids)) == len(ids)

    def test_sequential_gap(self):
        a = int(generate_task_id())
        time.sleep(0.002)
        b = int(generate_task_id())
        assert b > a
