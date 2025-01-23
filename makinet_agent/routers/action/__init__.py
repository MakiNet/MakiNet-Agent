from fastapi import APIRouter

from . import image, task

action_router = APIRouter(prefix="/action")

action_router.include_router(image.image_router, prefix="/image")
action_router.include_router(task.task_router, prefix="/task")
