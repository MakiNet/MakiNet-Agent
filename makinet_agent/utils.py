import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from socket import gethostname

import aiohttp
from asgiref.sync import sync_to_async
from loguru import logger
from OpenSSL import crypto
from yarl import URL

from .global_vars import GLOBAL_VARS

DEFAULT_CERT_FILE_DIR = Path.home().joinpath(".local/share/makinet-agent/certs")
DEFAULT_IMAGE_FILE_DIR = Path.home().joinpath(".local/share/makinet-agent/images")

DownloadWorkerPoolExecutor = ThreadPoolExecutor(max_workers=10)

DEFAULT_CERT_FILE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_IMAGE_FILE_DIR.mkdir(parents=True, exist_ok=True)


def generate_self_signed_certs(
    cert_file_dir: Path = DEFAULT_CERT_FILE_DIR,
):
    cert_file_dir.mkdir(parents=True, exist_ok=True)

    logger.debug("Start to generate certs")

    # 创建密钥
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # 创建证书
    cert = crypto.X509()
    cert.get_subject().C = "IT"
    cert.get_subject().ST = "Makinet"
    cert.get_subject().L = "Makinet"
    cert.get_subject().O = "Makinet"
    cert.get_subject().OU = "Makinet"
    cert.get_subject().CN = gethostname()
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, "sha256")

    cert_file_dir.joinpath("server.key").write_bytes(
        crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
    )
    cert_file_dir.joinpath("server.crt").write_bytes(
        crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
    )

    logger.debug("Generate certs success")


def check_certs(
    cert_file_dir: Path = DEFAULT_CERT_FILE_DIR,
):
    """检查证书，如果不存在则生成新的。

    Args:
        cert_file_dir (Path, optional): 证书文件夹. Defaults to DEFAULT_CERT_FILE_DIR.

    Returns:
        tuple[Path, Path]: 密钥文件和证书文件的路径，第一个是密钥文件，第二个是证书文件
    """
    cert_file_dir.mkdir(parents=True, exist_ok=True)

    key_file = cert_file_dir.joinpath("server.key")
    cert_file = cert_file_dir.joinpath("server.crt")

    if not key_file.exists() or not cert_file.exists():
        logger.warning("No certs found, generating new ones")
        logger.warning(
            "Self-signed certificates are not be trusted by your browser and os, we recommend you to use your own certificates issued by a trusted CA instead"
        )

        # 删除旧证书
        key_file.unlink(missing_ok=True)
        cert_file.unlink(missing_ok=True)

        # 生成新的
        generate_self_signed_certs(cert_file_dir)

    return (key_file, cert_file)


def check_aria2c():
    """检查 aria2c 是否安装。

    Raises:
        FileNotFoundError: 如果没有安装 aria2c，则抛出异常
    """

    if shutil.which("aria2c") is None:
        raise FileNotFoundError("aria2c not found, please install it first")


async def download_file(url: URL, path: Path):
    """下载文件。

    Args:
        url (URL): 文件 URL
        path (Path): 文件保存路径

    Raises:
        RuntimeError: 如果下载失败，则抛出异常
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Start to download {url}")

    path = path.absolute()

    process = await sync_to_async(
        subprocess.run, executor=DownloadWorkerPoolExecutor, thread_sensitive=False
    )(
        [
            "aria2c",
            "-x",
            "16",
            "-s",
            "16",
            "-k",
            "1M",
            str(url),
            "-d",
            path.parent,
            "-o",
            path.name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if process.returncode != 0:
        logger.error(f"Download {url} failed: {process.stderr.decode()}")
        raise RuntimeError(f"Download {url} failed")

    return path


async def register_to_control_plane():
    async with aiohttp.ClientSession(
        base_url=GLOBAL_VARS["server_api_url"],
        connector=aiohttp.TCPConnector(ssl=False, limit=10),
        timeout=aiohttp.ClientTimeout(total=10),
    ) as sess:
        response = await sess.post(
            f"/agent/register?slug={GLOBAL_VARS['slug']}&api_url={GLOBAL_VARS['own_api_url']}"
        )

        if response.status != 200:
            logger.error(f"Register to control plane failed: {await response.text()}")
            raise RuntimeError("Register to control plane failed")
