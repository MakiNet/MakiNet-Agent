from typing import Annotated

import uvicorn
from fastapi import FastAPI
from typer import Option, Typer

from . import utils
from .routers.action import action_router

app = FastAPI(title="Maki's Net Agent", version="0.0.1-alpha.1")
app.include_router(action_router, prefix="/actions")

cli = Typer(name="MakiNet Agent")


@cli.command()
def server(
    host: Annotated[str, Option("--host", "-h", help="Host to bind to")] = "0.0.0.0",
    port: Annotated[int, Option("--port", "-p", help="Port to bind to")] = 10514,
    debug: Annotated[bool, Option("--debug", "-v", help="Enable debug mode")] = False,
):
    app.debug = debug

    utils.check_certs()
    utils.check_aria2c()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
