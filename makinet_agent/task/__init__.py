import asyncio
import shlex
import signal
import string
import subprocess
import threading
from random import choices
from typing import Annotated, Any, Literal, Optional, TextIO

from loguru import logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
)

from .loggers import MemoryLogger, RunnerLoggers
from .manager import task_manager


class TaskStatus(BaseModel):
    """任务状态。"""

    status: Literal["running", "stopped", "ready"]
    return_code: Optional[int] = None


class Task(BaseModel):
    slug: str = Field(
        default_factory=lambda: "".join(choices(string.hexdigits, k=8)), frozen=True
    )
    command: str
    loggers: list[Annotated[RunnerLoggers, Field(discriminator="logger_name")]] = []
    timeout: Optional[int] = None
    stop_command: Optional[str] = (
        None  # 软停止命令，会被直接输入进程的 stdin 后（附带一个回车）
    )

    @field_validator("loggers", mode="before")
    @classmethod
    def _validate_loggers(cls, loggers: list[RunnerLoggers]) -> list[RunnerLoggers]:
        if len(loggers) == 0:
            loggers.append(MemoryLogger(logger_name="memory", logging=False))

        return loggers

    @computed_field
    @property
    def status(self) -> TaskStatus:
        if self._process is None:
            return TaskStatus(status="ready", return_code=None)

        if self._process.poll() is None:
            return TaskStatus(status="running", return_code=None)

        return TaskStatus(
            status="stopped", return_code=self._process.returncode  # type: ignore
        )

    def _run(self) -> tuple[TextIO | None, TextIO | None, TextIO | None]:
        logger.debug(f"Running task {self.slug}")

        self._process = subprocess.Popen(
            shlex.split(shlex.quote(self.command)),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return self._process.stdin, self._process.stdout, self._process.stderr  # type: ignore

    def _stop(self):
        """软停止。发送 SIGINT 信号（等同于按下 Ctrl+C），目标可以自行处理。"""
        if self._process is not None:
            self._process.send_signal(signal.SIGINT)
            for _logger in self.loggers:
                _logger.stop_log()

    def _terminate(self):
        """软停止。发送 SIGTERM 信号，比 SIGINT 更暴力，但仍是可以被目标忽略的。"""
        if self._process is not None:
            self._process.send_signal(signal.SIGTERM)
            for _logger in self.loggers:
                _logger.stop_log()

    def _kill(self):
        """硬停止。发送 SIGKILL 信号，比 SIGINT 更暴力，进程将会被直接杀死。"""
        if self._process is not None:
            self._process.send_signal(signal.SIGKILL)
            for _logger in self.loggers:
                _logger.stop_log()

    def run(self):
        """运行任务。与 _run 不同的是，本方法会记录日志，且只返回 stdin 流。"""
        stdin, stdout, stderr = self._run()

        for _logger in self.loggers:
            if stdout is not None:
                _logger.start_log(stdout)

            if stderr is not None:
                _logger.start_log(stderr)

        def sidecar():
            """用于监控进程状态的线程，当进程结束时，会自动停止日志记录。"""
            try:
                self._process.wait(self.timeout)
            except TimeoutError:
                logger.info(f"Task {self.slug} timed out")
                stopping_task = asyncio.create_task(self.stop())

                while not stopping_task.done():
                    continue
            finally:
                for _logger in self.loggers:
                    _logger.stop_log()

        threading.Thread(target=sidecar).start()

        return stdin

    def run_command(self, command: str, append_newline: bool = True):
        if self._process is None:
            raise RuntimeError("Runner is not running")

        if self._process.stdin is None:
            raise RuntimeError("Runner stdin is not available")

        if append_newline:
            command += "\r\n"

        self._process.stdin.write(command)
        self._process.stdin.flush()

    async def stop(self):
        """智能停止。

        行为：
            1. 如果 self.stop_command 不为空，则执行 self.stop_command 命令，否则发送 SIGINT 信号，然后从 2. 开始继续执行。
            2. 如等待 10s 后仍未停止，则发送 SIGTERM 信号。
            3. 如再等待 10s 后仍未停止，则发送 SIGKILL 信号。
        """
        if self.stop_command is not None:
            self.run_command(self.stop_command)
        else:
            self._stop()

        await asyncio.sleep(10)

        if self._process is not None and self._process.poll() is None:
            self._terminate()
            await asyncio.sleep(10)

        if self._process is not None and self._process.poll() is None:
            self._kill()

    def get_logger(self, logger_name: str) -> RunnerLoggers | None:
        """获取日志记录器。"""
        for _logger in self.loggers:
            if _logger.logger_name == logger_name:
                return _logger

        return None
