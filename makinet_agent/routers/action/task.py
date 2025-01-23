from fastapi import APIRouter

from makinet_agent.task import Task

task_router = APIRouter(tags=["actions/task"])


@task_router.post("/run", response_model=Task)
def run_task(task: Task):
    task.run()

    return task
