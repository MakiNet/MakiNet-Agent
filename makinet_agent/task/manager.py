try:
    from . import Task
except ImportError:
    pass


class TaskManager:
    def __init__(self):
        self.tasks: list["Task"] = []

    def add_task(self, task: "Task"):
        """添加任务并自动运行。如果有相同的 slug 的任务，会移除。

        Args:
            task (Task): 任务
        """
        task.run()

        # 检查有无相同 slug 的任务，有则移除
        same_slug_task = self.get_task(task.slug)
        if same_slug_task is not None:
            self.tasks.remove(same_slug_task)

        self.tasks.append(task)

    def get_task(self, slug: str) -> "Task | None":
        """获取任务

        Args:
            slug (str): 任务的 slug

        Returns:
            Task | None: 返回第一个 slug 匹配的任务，否则返回 None
        """
        for task in self.tasks:
            if task.slug == slug:
                return task

        return None


task_manager = TaskManager()
