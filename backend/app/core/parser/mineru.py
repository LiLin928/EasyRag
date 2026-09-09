"""MinerU 文档解析适配器。"""
from dataclasses import dataclass
from typing import List, Optional
import httpx

from app.config import settings


@dataclass
class ParsedSection:
    """解析出的章节。"""
    level: int
    title: str
    content: str


@dataclass
class ParsedTable:
    """解析出的表格。"""
    rows: List[List[str]]
    caption: Optional[str] = None


@dataclass
class ParsedImage:
    """解析出的图片。"""
    url: str
    alt: Optional[str] = None


@dataclass
class ParsedDocument:
    """MinerU 解析结果。"""
    title: str
    sections: List[ParsedSection]
    tables: List[ParsedTable]
    images: List[ParsedImage]
    metadata: dict


class MinerUParser:
    """MinerU 文档解析器。"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or getattr(settings, "mineru_url", "http://localhost:8000")
    
    async def parse(self, file_path: str) -> ParsedDocument:
        """调用 MinerU 服务解析文档。
        
        Args:
            file_path: 文档路径（MinIO URL 或本地路径）
            
        Returns:
            结构化解析结果
        """
        async with httpx.AsyncClient() as client:
            # 上传文件到 MinerU
            with open(file_path, "rb") as f:
                response = await client.post(
                    f"{self.base_url}/parse",
                    files={"file": f},
                    timeout=300
                )
            response.raise_for_status()
            data = response.json()
        
        return ParsedDocument(
            title=data.get("title", ""),
            sections=[
                ParsedSection(
                    level=s.get("level", 1),
                    title=s.get("title", ""),
                    content=s.get("content", "")
                )
                for s in data.get("sections", [])
            ],
            tables=[
                ParsedTable(
                    rows=t.get("rows", []),
                    caption=t.get("caption")
                )
                for t in data.get("tables", [])
            ],
            images=[
                ParsedImage(url=i.get("url"), alt=i.get("alt"))
                for i in data.get("images", [])
            ],
            metadata=data.get("metadata", {})
        )
    
    async def parse_async(self, file_content: bytes, filename: str) -> ParsedDocument:
        """异步解析文件内容。
        
        Args:
            file_content: 文件字节内容
            filename: 文件名
            
        Returns:
            结构化解析结果
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/parse",
                files={"file": (filename, file_content)},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse_response(data)
    
    def _parse_response(self, data: dict) -> ParsedDocument:
        """解析 MinerU 响应。"""
        return ParsedDocument(
            title=data.get("title", ""),
            sections=[
                ParsedSection(
                    level=s.get("level", 1),
                    title=s.get("title", ""),
                    content=s.get("content", "")
                )
                for s in data.get("sections", [])
            ],
            tables=[
                ParsedTable(
                    rows=t.get("rows", []),
                    caption=t.get("caption")
                )
                for t in data.get("tables", [])
            ],
            images=[
                ParsedImage(url=i.get("url"), alt=i.get("alt"))
                for i in data.get("images", [])
            ],
            metadata=data.get("metadata", {})
        )
