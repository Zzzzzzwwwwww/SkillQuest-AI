"""
SkillQuest AI 通用 Schema

- PageParams：分页查询参数（FastAPI 依赖注入）
- PageResult[T]：统一分页响应体（Pydantic v2 泛型）
"""

from typing import Generic, List, Optional, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应体模型：{ code, message, data }。

    配合 success() 使用，使 Swagger 文档与实际响应格式一致。
    """

    code: int = 0
    message: str = "success"
    data: T


class PageParams:
    """分页查询参数（页号从 1 开始，默认值由 Query 提供）。"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数(1-100)"),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

    @property
    def skip(self) -> int:
        """SQLAlchemy offset 别名。"""
        return self.offset


class PageResult(BaseModel, Generic[T]):
    """统一分页响应：data 内直接返回本结构。"""

    items: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """总页数（规则计算）。"""
        if self.total <= 0 or self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_more(self) -> bool:
        """是否还有下一页（规则计算）。"""
        return self.page * self.page_size < self.total


class IdNameOut(BaseModel):
    """通用 ID + 名称结构。"""

    id: int
    name: str


class Option(BaseModel):
    """通用选项结构（下拉/筛选）。"""

    value: str
    label: str
    optional: Optional[str] = None