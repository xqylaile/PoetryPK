"""
诗词PK - 题库管理模块
负责加载诗词数据、随机抽取诗词
"""

import json
import random
from pathlib import Path
from typing import Optional

from config import POEMS_FILE


class PoemBank:
    """诗词题库管理"""

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path) if data_path else POEMS_FILE
        self.poems: list[dict] = []
        self._load()

    def _load(self):
        """从 JSON 文件加载题库"""
        if not self.data_path.exists():
            raise FileNotFoundError(f"题库文件不存在: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.poems = data.get("poems", [])
        print(f"[题库] 已加载 {len(self.poems)} 首诗词")

    def get_total_count(self) -> int:
        """题库总数"""
        return len(self.poems)

    def get_available_poems(self, exclude_ids: set[int]) -> list[dict]:
        """获取未被使用的诗词列表"""
        return [p for p in self.poems if p["id"] not in exclude_ids]

    def get_random_poem(self, exclude_ids: set[int]) -> Optional[dict]:
        """
        从题库中随机抽取一首未使用的诗

        Args:
            exclude_ids: 已使用过的诗词ID集合

        Returns:
            诗词字典，题库耗尽时返回 None
        """
        available = self.get_available_poems(exclude_ids)
        if not available:
            return None
        return random.choice(available)

    def get_random_line(self, poem: dict) -> tuple[int, str, str]:
        """
        从诗中随机选取一组上下句

        Args:
            poem: 诗词字典

        Returns:
            (line_index, upper_line, lower_line)
        """
        lines = poem.get("lines", [])
        if not lines:
            raise ValueError(f"诗词 '{poem.get('title', '?')}' 没有上下句数据")

        chosen = random.choice(lines)
        return chosen["index"], chosen["upper"], chosen["lower"]

    def get_poem_by_id(self, poem_id: int) -> Optional[dict]:
        """根据ID获取诗词完整信息"""
        for poem in self.poems:
            if poem["id"] == poem_id:
                return poem
        return None

    def get_analysis_poems(self, wrong_poem_ids: list[int]) -> list[dict]:
        """
        从答错的诗词ID列表中选取诗词，返回包含解析的完整信息

        Args:
            wrong_poem_ids: 答错的诗词ID列表（可能包含重复）

        Returns:
            诗词列表（去重后），最多返回全部答错的诗词
        """
        # 去重
        unique_ids = list(set(wrong_poem_ids))
        result = []
        for pid in unique_ids:
            poem = self.get_poem_by_id(pid)
            if poem:
                result.append(poem)
        return result
