import hashlib
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Self

import bson
from loguru import logger
from pydantic import BaseModel, computed_field, field_validator
from yarl import URL

from makinet_agent import utils


class ImageLayer(BaseModel):
    checksum: dict[
        str, str
    ]  # Path, sha256  # 保留所有文件的 sha256，而非仅 content 中内容
    content: dict[str, bytes]  # Path, content
    deleted_files: list[str] = []

    @computed_field
    @property
    def slug(self) -> str:
        return hashlib.sha256(
            " ".join(self.checksum.values()).encode("utf-8")
        ).hexdigest()

    @field_validator("content", mode="before")
    def validate_content(cls, content: dict[str, bytes]):
        for path, _ in content.items():
            if Path(path).is_absolute():
                raise ValueError("Path must be relative")

        return content

    def pack(self, path: Path, compression: bool):
        """将镜像打包为 Zip 文件

        Args:
            path (Path): Zip 文件路径
            compression (bool): 是否压缩镜像文件

        Note:
            镜像文件结构:
                - info.bson: 镜像信息文件（除 self.content 以外的所有内容）
                - content.bson: 镜像内容文件（self.content 的 BSON 结构，Key 已被转为 str）
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(
            file=path,
            mode="w",
            compression=zipfile.ZIP_STORED if not compression else zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as zip_file:
            zip_file.writestr(
                "info.bson",
                bson.dumps(self.model_dump(mode="json", exclude={"content"})),
            )

            # 防止出现绝对路径，并将 Path 转换为 str
            for file_path, content in self.content.items():
                if Path(file_path).is_absolute():
                    logger.error("Error when packing image: Path must be relative")

            zip_file.writestr("content.bson", bson.dumps(self.content))

    @classmethod
    def unpack(cls, path: Path):
        """从 Zip 文件中解包镜像
        Args:
            path (Path): Zip 文件路径

        Returns:
            ImageLayer: 解包后的镜像
        """
        with zipfile.ZipFile(path, "r") as zip_file:
            info: dict[str, Any] = bson.loads(zip_file.read("info.bson"))  # type: ignore
            content: dict[str, bytes] = bson.loads(zip_file.read("content.bson"))  # type: ignore

        return cls(**info, content=content)

    @classmethod
    def load_metadata(cls, path: Path):
        """从 Zip 文件中加载镜像元数据
        Args:
            path (Path): Zip 文件路径
        Returns:
            ImageLayer: 镜像元数据
        """
        with zipfile.ZipFile(path, "r") as zip_file:
            info: dict[str, Any] = bson.loads(zip_file.read("info.bson"))  # type: ignore
        return cls(**info)


class Image(BaseModel):
    """镜像。

    Note:
        启动时从 .image.env 中加载环境变量
    """

    slug: str
    version: str
    layers: list[ImageLayer]

    # also used by the makinet control plane and agent, do not change it without changing the other one.
    def pack(self, path: Path, compression: bool):
        """将镜像打包为 Zip 文件
        Args:
            path (Path): Zip 文件路径
            compression (bool): 是否压缩镜像文件

        Note:
            镜像文件结构:
                - info.bson: 镜像信息文件（除 self.layers 以外的所有内容）
                - layers/: 镜像层文件夹
                    - layer_0.zip: 镜像层 0
                    - layer_1.zip: 镜像层 1
                    - ...
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(
            path,
            "w",
            compression=zipfile.ZIP_STORED if not compression else zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as zip_file:
            zip_file.writestr(
                "info.bson",
                bson.dumps(self.model_dump(mode="json", exclude={"layers"})),
            )

            zip_file.mkdir("layers")
            with tempfile.TemporaryDirectory() as tmpdir:
                for i, layer in enumerate(self.layers):
                    layer.pack(Path(tmpdir) / f"layers/layer_{i}.zip", compression)

                    # 压缩镜像层
                    zip_file.write(
                        Path(tmpdir) / f"layers/layer_{i}.zip",
                        f"layers/layer_{i}.zip",
                    )

    # also used by the makinet control plane and agent, do not change it without changing the other one.
    @classmethod
    def unpack(cls, path: Path):
        """从 Zip 文件中解包镜像
        Args:
            path (Path): Zip 文件路径
        Returns:
            Image: 解包后的镜像
        """
        with zipfile.ZipFile(path, "r") as zip_file:
            info: dict[str, Any] = bson.loads(zip_file.read("info.bson"))  # type: ignore
            layers: list[ImageLayer] = []

            for i in range(len(zip_file.namelist())):
                # 该文件不是 layers 文件夹下的文件，继续循环
                if f"layers/layer_{i}.zip" not in zip_file.namelist():
                    continue

                # 解压镜像层
                with tempfile.TemporaryDirectory() as tmp_dir:
                    zip_file.extract(f"layers/layer_{i}.zip", tmp_dir)
                    layers.append(
                        ImageLayer.unpack(Path(tmp_dir) / f"layers/layer_{i}.zip")
                    )

        return cls(**info, layers=layers)

    # also used by the makinet control plane and agent, do not change it without changing the other one.
    @classmethod
    def load_metadata(cls, path: Path):
        """从 Zip 文件中加载镜像元数据
        Args:
            path (Path): Zip 文件路径
        Returns:
            Image: 镜像元数据
        """
        with zipfile.ZipFile(path, "r") as zip_file:
            info: dict[str, Any] = bson.loads(zip_file.read("info.bson"))  # type: ignore
            layers: list[ImageLayer] = []

            for i in range(len(zip_file.namelist())):
                # 该文件不是 layers 文件夹下的文件，继续循环
                if f"layers/layer_{i}.zip" not in zip_file.namelist():
                    continue
                layers.append(
                    ImageLayer.load_metadata(Path(path) / f"layers/layer_{i}.zip")
                )

        return cls(**info)

    # also used by the makinet control plane and agent, do not change it without changing the other one.
    def extract_to_directory(self, path: Path):
        """将镜像解包到目录中
        Args:
            path (Path): 目录路径
        """
        path.mkdir(parents=True, exist_ok=True)

        for layer in self.layers:
            for file_path, content in layer.content.items():
                (path / file_path).parent.mkdir(parents=True, exist_ok=True)
                (path / file_path).write_bytes(content)

            for deleted_file in layer.deleted_files:
                (path / deleted_file).unlink(missing_ok=True)

    # also used by the makinet control plane and agent, do not change it without changing the other one.
    def get_file_list(self) -> list[str]:
        return list(self.layers[-1].checksum.keys())

    # also used by the makinet control plane and agent, do not change it without changing the other one.
    def __repr__(self) -> str:
        return f"""Image(
    slug={self.slug},
    version={self.version},
    layers={len(self.layers)},
    files={self.get_file_list()[0:3]}...
)"""

    # only used by the client
    @classmethod
    async def pull(cls, url: URL | str):
        if isinstance(url, str):
            url = URL(url)

        image_path = await utils.download_file(
            url, utils.DEFAULT_IMAGE_FILE_DIR / f"{url.name}"
        )

        try:
            return cls.unpack(image_path)
        except Exception as e:
            # clean
            image_path.unlink(missing_ok=True)

            raise ValueError(f"Error when unpacking image: {e}")

    def without_content(self) -> Self:
        return self.model_copy(
            update={
                "layers": [
                    layer.model_copy(update={"content": {}}) for layer in self.layers
                ]
            }
        )
