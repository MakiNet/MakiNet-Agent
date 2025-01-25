from typing import Annotated, Optional

from pydantic import BaseModel, Field

from ..global_vars import GLOBAL_VARS


class AgentMemoryInfo(BaseModel):
    total: int = Field(description="总内存")
    available: int = Field(description="可用内存")
    percent: float = Field(description="内存使用率")
    used: int = Field(description="已使用内存")
    free: int = Field(description="空闲内存")


class AgentCPUInfo(BaseModel):
    percent: float = Field(description="CPU 使用率")
    freq_max: Optional[float] = Field(
        description="最大频率", deprecated=True, default=None
    )
    freq_min: Optional[float] = Field(
        description="最小频率", deprecated=True, default=None
    )
    freq_current: float = Field(description="当前频率")
    count_logical: int | None = Field(description="逻辑 CPU 数量")
    count_physical: int | None = Field(description="物理 CPU 数量")


class AgentInfo(BaseModel):
    slug: Annotated[str, Field(default_factory=lambda: GLOBAL_VARS["slug"])]
    memory: AgentMemoryInfo = Field(description="内存信息")
    cpu: AgentCPUInfo = Field(description="CPU 信息")
    system_load: tuple[float, float, float] = Field(description="系统负载")
