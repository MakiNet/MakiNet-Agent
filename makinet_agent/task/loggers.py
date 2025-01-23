import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Literal, TextIO, Union

import loguru
from loguru import logger
from pydantic import BaseModel, Field


class RunnerLogger(BaseModel, ABC):
    logger_name: str

    @abstractmethod
    def start_log(self, stream: TextIO): ...

    @abstractmethod
    def stop_log(self): ...

    @abstractmethod
    def log(self, message: str): ...

    @abstractmethod
    def get_logs(self) -> Iterable[str]: ...


class ConsoleLogger(RunnerLogger):
    """控制台日志。将日志打印于控制台上。"""

    logger_name: Literal["console"] = Field("console")  # type: ignore
    log_prefix: str = ""
    logging: bool = Field(False, exclude=True)

    def start_log(self, stream: TextIO):
        def logger():
            while stream.readable() and self.logging:
                line = stream.readline().strip()

                if line:
                    self.log(line)
                else:
                    time.sleep(0.1)

        self.logging = True
        thread = threading.Thread(target=logger)
        thread.start()

    def stop_log(self):
        self.logging = False

    def log(self, message: str):
        logger.info(f"[{self.log_prefix}] {message}")

    def get_logs(self):
        raise NotImplementedError("ConsoleLogger does not support get_logs")


class MemoryLogger(RunnerLogger):
    logger_name: Literal["memory"] = Field("memory")  # type: ignore
    maximum_logs: int = 1000
    logs: list[str] = Field(default_factory=list)

    logging: bool = Field(False, exclude=True)

    def start_log(self, stream: TextIO):
        def logger():
            while stream.readable() and self.logging:
                line = stream.readline().strip()
                if line:
                    self.log(line)
                else:
                    time.sleep(0.1)

        self.logging = True
        thread = threading.Thread(target=logger)
        thread.start()

    def stop_log(self):
        self.logging = False

    def log(self, message: str):
        # 如果超过最大日志数量，则删除最早的日志
        if len(self.logs) >= self.maximum_logs:
            self.logs.pop(0)

        self.logs.append(message)

    def get_logs(self):
        return (x for x in self.logs)


class FileLogger(RunnerLogger):
    logger_name: Literal["file"] = Field("file")  # type: ignore
    log_file: Path
    log_prefix: str = ""
    logging: bool = Field(False, exclude=True)

    def start_log(self, stream: TextIO):
        def logger():
            while stream.readable() and self.logging:
                line = stream.readline()
                if line:
                    self.log(line)
                else:
                    time.sleep(0.1)

        self.logging = True
        thread = threading.Thread(target=logger)
        thread.start()

    def stop_log(self):
        self.logging = False

    def log(self, message: str):
        with open(self.log_file, "a") as f:
            f.write(f"[{self.log_prefix}] {message}")

    def get_logs(self):
        with open(self.log_file, "r") as f:
            while True:
                line = f.readline()

                if line:
                    yield line
                else:
                    break


RunnerLoggers = Union[ConsoleLogger, MemoryLogger, FileLogger]
