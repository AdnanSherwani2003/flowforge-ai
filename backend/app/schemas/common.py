from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Page size limit")
    offset: int = Field(..., ge=0, description="Number of items skipped")
