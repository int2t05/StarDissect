# S4 任务队列测试:状态机全路径(执行器注入,无 LLM;REQ-TASK-001..006、PRD FIG-02)
import pytest

from app.db import init_db
from app.tasks import queue


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "app.db"
    init_db(db)
    c = queue.connect(db)
    c.execute("INSERT INTO repos(id, full_name, status) VALUES (1,'o/r','已分类')")
    c.execute("INSERT INTO repos(id, full_name, status) VALUES (2,'o/r2','已分类')")
    c.commit()
    return c


def _ok(task_id):
    return ("ok", 1)


def test_enqueue_and_duplicate_rejected(conn):
    t = queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    assert t["status"] == "排队"
    with pytest.raises(queue.DuplicateTask):
        queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)


def test_step_runs_to_completion(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    assert queue.step(conn, _ok) is True
    row = conn.execute("SELECT status FROM tasks WHERE repo_id=1").fetchone()
    assert row["status"] == "完成"


def test_limited_with_output_archives_restricted(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)

    def partial(task_id):
        raise queue.TaskLimited(partial=True, reason="轮次上限")

    queue.step(conn, partial)
    row = conn.execute("SELECT status, fail_reason FROM tasks WHERE repo_id=1").fetchone()
    assert (row["status"], row["fail_reason"]) == ("受限完成", "轮次上限")


def test_limited_without_output_archives_failed(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)

    def empty(task_id):
        raise queue.TaskLimited(partial=False, reason="任务超时")

    queue.step(conn, empty)
    row = conn.execute("SELECT status, fail_reason FROM tasks WHERE repo_id=1").fetchone()
    assert (row["status"], row["fail_reason"]) == ("失败", "任务超时")


def test_error_archives_failed_with_reason(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)

    def boom(task_id):
        raise RuntimeError("git clone 失败")

    queue.step(conn, boom)
    row = conn.execute("SELECT status, fail_reason FROM tasks WHERE repo_id=1").fetchone()
    assert row["status"] == "失败" and "git clone" in row["fail_reason"]


def test_cancel_pending_only_target(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    queue.enqueue(conn, 2, "analyze", priority=100, turn_limit=30, time_limit_sec=1800)
    target = conn.execute("SELECT id FROM tasks WHERE repo_id=1").fetchone()["id"]
    assert queue.cancel_pending(conn, task_id=target) == 1  # 只删目标
    assert conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='排队'").fetchone()["c"] == 1


def test_priority_ordering(conn):
    # 新 star(priority=0)先于历史批次(100)
    queue.enqueue(conn, 2, "analyze", priority=100, turn_limit=30, time_limit_sec=1800)
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    queue.step(conn, _ok)
    first = conn.execute("SELECT repo_id FROM tasks WHERE status='完成'").fetchone()["repo_id"]
    assert first == 1


def test_pause_blocks_step(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    queue.set_paused(conn, True)
    assert queue.step(conn, _ok) is False
    queue.set_paused(conn, False)
    assert queue.step(conn, _ok) is True


def test_exclude_repo_drops_pending_and_blocks(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    queue.exclude_repo(conn, 1)
    assert conn.execute("SELECT excluded FROM repos WHERE id=1").fetchone()["excluded"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"] == 0
    with pytest.raises(queue.ExcludedRepo):
        queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)


def test_recover_marks_running_as_interrupted(conn):
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    conn.execute("UPDATE tasks SET status='进行', started_at='2026-10-09'")
    conn.commit()
    queue.recover(conn)
    assert conn.execute("SELECT status FROM tasks").fetchone()["status"] == "中断"
    # 中断后可重新入队(人工重试,REQ-TASK-006)
    queue.enqueue(conn, 1, "analyze", priority=0, turn_limit=30, time_limit_sec=1800)
    assert conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='排队'").fetchone()["c"] == 1
