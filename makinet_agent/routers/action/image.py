import asyncio

from asgiref.sync import sync_to_async
from fastapi import APIRouter
from pydantic import AnyUrl

from makinet_agent.models.image import Image
from makinet_agent.utils import DEFAULT_IMAGE_FILE_DIR

image_router = APIRouter(tags=["actions/image"])


@image_router.get("/ls", response_model=list[Image])
async def list_images():
    return await asyncio.gather(
        *[
            sync_to_async(Image.load_metadata)(x)
            for x in DEFAULT_IMAGE_FILE_DIR.rglob("*")
        ]
    )


@image_router.post(
    "/pull", response_model=Image, summary="拉取镜像。注意可能会**超时**，应当配置好。"
)
async def pull_image(image_url: AnyUrl):
    return (await Image.pull(str(image_url))).without_content()
