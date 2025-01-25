import hashlib
from socket import gethostbyname, gethostname
from typing import TypedDict


class GlobalVarsDict(TypedDict):
    server_api_url: str
    own_api_url: str
    slug: str


GLOBAL_VARS: GlobalVarsDict = {
    "server_api_url": "",
    "own_api_url": f"https://{gethostbyname(gethostname())}:10514",
    "slug": f"maki-{hashlib.sha256(gethostname().encode()).hexdigest()[0:8]}",
}
