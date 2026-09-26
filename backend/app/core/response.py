"""
SkillQuest AI 统一响应模块

约定统一响应结构：
    { "code": 0, "message": "success", "data": {} }

  - code:    业务码，0 表示成功，非 0 表示失败
  - message: 人类可读的说明信息
  - data:    业务数据体
"""

from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# 成功业务码约定（后续业务模块可扩展）
SUCCESS_CODE = 0
GENERAL_ERROR_CODE = 1


def success(data: Any = None, message: str = "success", code: int = SUCCESS_CODE) -> Dict[str, Any]:
    """构造成功响应体。"""
    return {"code": code, "message": message, "data": data if data is not None else {}}


def fail(message: str = "error", code: int = GENERAL_ERROR_CODE, data: Any = None) -> Dict[str, Any]:
    """构造失败响应体。"""
    return {"code": code, "message": message, "data": data if data is not None else {}}


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """将 Starlette/FastAPI 的标准 HTTPException 转为统一格式。"""
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(message=str(exc.detail), code=exc.status_code),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """将请求参数校验异常转为统一格式。"""
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first_error.get("loc", []) if x != "body")
    message = f"参数校验失败: {field} {first_error.get('msg', '')}".strip()
    return JSONResponse(
        status_code=422,
        content=fail(message=message, code=422),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理未捕获异常，避免向客户端泄露堆栈。"""
    return JSONResponse(
        status_code=500,
        content=fail(message="服务器内部错误", code=500),
    )


def register_exception_handlers(app) -> None:
    """挂载全部异常处理器到 FastAPI 实例。"""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)