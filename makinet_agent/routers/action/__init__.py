from fastapi import APIRouter

from . import image

action_router = APIRouter()

action_router.include_router(image.image_router, prefix="/image")
