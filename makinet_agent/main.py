import asyncio
from typing import Annotated, Any, Optional

import psutil
import uvicorn
from fastapi import FastAPI
from loguru import logger
from typer import Option, Typer

from . import utils
from .global_vars import GLOBAL_VARS
from .models.agent import AgentCPUInfo, AgentInfo, AgentMemoryInfo
from .routers.action import action_router

app = FastAPI(title="Maki's Net Agent", version="0.0.1-alpha.1")
app.include_router(action_router, prefix="/actions")


@app.get("/ping", response_model=AgentInfo)
def ping():
    return AgentInfo(
        slug=GLOBAL_VARS["slug"],
        memory=AgentMemoryInfo(
            total=psutil.virtual_memory().total,
            available=psutil.virtual_memory().available,
            percent=psutil.virtual_memory().percent,
            used=psutil.virtual_memory().used,
            free=psutil.virtual_memory().free,
        ),
        cpu=AgentCPUInfo(
            percent=psutil.cpu_percent(),
            freq_current=psutil.cpu_freq().current,
            count_logical=psutil.cpu_count(logical=True),
            count_physical=psutil.cpu_count(logical=False),
        ),
        system_load=psutil.getloadavg(),
    )


cli = Typer(name="MakiNet Agent")


@cli.command()
def server(
    server_api_url: Annotated[str, Option("--api-url", help="Server API URL")],
    own_api_url: Annotated[
        Optional[str], Option("--own-api-url", help="Own API URL")
    ] = None,
    host: Annotated[str, Option("--host", "-h", help="Host to bind to")] = "0.0.0.0",
    port: Annotated[int, Option("--port", "-p", help="Port to bind to")] = 10514,
    debug: Annotated[bool, Option("--debug", "-v", help="Enable debug mode")] = False,
    slug: Annotated[
        Optional[str],
        Option(
            "--slug", "-s", help="Agent slug. Keep default to generate by hostname."
        ),
    ] = None,
):
    app.debug = debug

    GLOBAL_VARS["server_api_url"] = server_api_url

    if slug is not None:
        GLOBAL_VARS["slug"] = slug

    if own_api_url is not None:
        GLOBAL_VARS["own_api_url"] = own_api_url
    else:
        logger.warning(
            f"No own_api_url specified, using default {GLOBAL_VARS['own_api_url']}"
        )

    utils.check_certs()
    utils.check_aria2c()

    asyncio.get_event_loop().run_until_complete(utils.register_to_control_plane())
    uvicorn.run(
        app,
        host=host,
        port=port,
        loop="asyncio",
        ssl_certfile=utils.DEFAULT_CERT_FILE_DIR.joinpath("server.crt"),
        ssl_keyfile=utils.DEFAULT_CERT_FILE_DIR.joinpath("server.key"),
    )


if __name__ == "__main__":
    cli()
