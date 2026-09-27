#!/usr/bin/env python3
"""
AutoKafka 前端进度同步工具

用于实时更新 frontend/public/data/tasks.json，
让前端能够展示写作任务的实时进度（进行中 + 历史）。

使用方式（在 Claude 中通过 Bash 调用）：
    # 初始化新任务（自动归档旧的进行中任务）
    python3 tools/progress_updater.py init "文章标题"

    # 添加思考步骤
    python3 tools/progress_updater.py step "输入路由" "确定主题（演进脉络角度）"

    # 更新状态和进度
    python3 tools/progress_updater.py status researching 20

    # 更新研究报告
    python3 tools/progress_updater.py research '{"title": "...", "summary": "..."}'

    # 更新文章内容
    python3 tools/progress_updater.py article '{"title": "...", "content": "...", "wordCount": 2000}'

    # 更新审核分数
    python3 tools/progress_updater.py review '{"overall": 85, "dimensions": [...]}'

    # 更新公众号发布结果
    python3 tools/progress_updater.py publish '{"success": true, "mediaId": "xxx", "publishedAt": "..."}'

    # 标记完成
    python3 tools/progress_updater.py complete
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 配置路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent  # auto_kafka/
TASKS_FILE = PROJECT_ROOT / "frontend" / "public" / "data" / "tasks.json"
MAX_HISTORY = 20  # 最多保留的历史任务数


def ensure_dir():
    """确保目录存在"""
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_tasks():
    """加载任务列表"""
    if TASKS_FILE.exists():
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            # 兼容旧的单任务格式
            elif isinstance(data, dict) and 'id' in data:
                return [data]
    return []


def save_tasks(tasks):
    """保存任务列表"""
    ensure_dir()
    with open(TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"[Progress] Updated: {TASKS_FILE}")


def now_iso():
    """返回 ISO 格式时间戳"""
    return datetime.now().isoformat() + "Z"


def get_current_task(tasks):
    """获取当前进行中的任务"""
    for task in tasks:
        if task.get('status') not in ['completed', 'failed']:
            return task
    return None


def init_task(title: str):
    """初始化新任务"""
    tasks = load_tasks()

    # 将当前进行中的任务标记为失败（被中断）
    for task in tasks:
        if task.get('status') not in ['completed', 'failed']:
            task['status'] = 'failed'
            task['currentPhase'] = '已中断'
            task['completedAt'] = now_iso()

    # 创建新任务
    new_task = {
        "id": f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "title": title,
        "status": "researching",
        "currentPhase": "初始化",
        "progress": 0,
        "createdAt": now_iso(),
        "thinkingSteps": []
    }

    # 新任务放在列表开头
    tasks.insert(0, new_task)

    # 限制历史任务数量
    if len(tasks) > MAX_HISTORY:
        tasks = tasks[:MAX_HISTORY]

    save_tasks(tasks)
    print(f"[Progress] Initialized task: {title}")
    return new_task


def add_step(phase: str, content: str):
    """添加思考步骤"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    step_id = f"step-{len(current.get('thinkingSteps', [])) + 1}"
    step = {
        "id": step_id,
        "phase": phase,
        "content": content,
        "timestamp": now_iso(),
        "status": "completed"
    }

    if "thinkingSteps" not in current:
        current["thinkingSteps"] = []
    current["thinkingSteps"].append(step)
    current["currentPhase"] = phase

    save_tasks(tasks)
    print(f"[Progress] Added step: {phase}")


def update_status(status: str, progress: int):
    """更新状态和进度"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    current["status"] = status
    current["progress"] = min(100, max(0, progress))

    # 根据状态更新 currentPhase
    phase_map = {
        "researching": "深度研究中",
        "writing": "文章撰写中",
        "reviewing": "质量审核中",
        "publishing": "发布公众号中",
        "completed": "全部完成",
        "failed": "任务失败"
    }
    if status in phase_map:
        current["currentPhase"] = phase_map[status]

    save_tasks(tasks)
    print(f"[Progress] Status: {status}, Progress: {progress}%")


def update_research(research_json: str):
    """更新研究报告"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    try:
        research = json.loads(research_json)
        current["researchReport"] = research
        save_tasks(tasks)
        print("[Progress] Updated research report")
    except json.JSONDecodeError as e:
        print(f"[Error] Invalid JSON: {e}")


def update_article(article_json: str):
    """更新文章内容"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    try:
        article = json.loads(article_json)
        current["article"] = article
        save_tasks(tasks)
        print(f"[Progress] Updated article: {article.get('wordCount', 0)} words")
    except json.JSONDecodeError as e:
        print(f"[Error] Invalid JSON: {e}")


def update_review(review_json: str):
    """更新审核分数"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    try:
        review = json.loads(review_json)
        current["reviewScores"] = review
        save_tasks(tasks)
        print("[Progress] Updated review scores")
    except json.JSONDecodeError as e:
        print(f"[Error] Invalid JSON: {e}")


def update_publish(publish_json: str):
    """更新公众号发布结果"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    try:
        publish = json.loads(publish_json)
        current["publishResult"] = publish
        save_tasks(tasks)
        if publish.get("success"):
            print(f"[Progress] Published to WeChat draft: {publish.get('mediaId', '')}")
        else:
            print(f"[Progress] Publish failed: {publish.get('error', 'unknown')}")
    except json.JSONDecodeError as e:
        print(f"[Error] Invalid JSON: {e}")


def complete_task():
    """标记任务完成"""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print("[Error] No active task found. Run 'init' first.")
        return

    current["status"] = "completed"
    current["progress"] = 100
    current["currentPhase"] = "全部完成"
    current["completedAt"] = now_iso()

    save_tasks(tasks)
    print("[Progress] Task completed!")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "init" and len(sys.argv) >= 3:
        init_task(sys.argv[2])
    elif cmd == "step" and len(sys.argv) >= 4:
        add_step(sys.argv[2], sys.argv[3])
    elif cmd == "status" and len(sys.argv) >= 4:
        update_status(sys.argv[2], int(sys.argv[3]))
    elif cmd == "research" and len(sys.argv) >= 3:
        update_research(sys.argv[2])
    elif cmd == "article" and len(sys.argv) >= 3:
        update_article(sys.argv[2])
    elif cmd == "review" and len(sys.argv) >= 3:
        update_review(sys.argv[2])
    elif cmd == "publish" and len(sys.argv) >= 3:
        update_publish(sys.argv[2])
    elif cmd == "complete":
        complete_task()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
