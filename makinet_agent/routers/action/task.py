from fastapi import APIRouter, HTTPException

from makinet_agent.task import Task, task_manager

task_router = APIRouter(tags=["actions/task"])


@task_router.get("/list", response_model=list[Task])
def list_tasks():
    return task_manager.tasks.copy()


@task_router.get("/get/{slug}", response_model=Task | None)
def get_task(slug: str):
    return task_manager.get_task(slug)


@task_router.get("/logs/{slug}/{logger_name}", response_model=list[str])
def get_logs(slug: str, logger_name: str):
    task = task_manager.get_task(slug)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    runner_logger = task.get_logger(logger_name)

    if runner_logger is None:
        raise HTTPException(status_code=404, detail="Logger not found")

    return runner_logger.get_logs()


@task_router.post("/run", response_model=Task)
def run_task(task: Task):
    task_manager.add_task(task)

    return task
