"""
诗词PK - 数据模型定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from fastapi import WebSocket


class GameStatus(str, Enum):
    """游戏状态枚举"""
    WAITING = "waiting"          # 等待第二位玩家加入
    READY = "ready"              # 双方就绪，等待开始
    PLAYING = "playing"          # 比赛进行中
    ANSWERING = "answering"      # 当前玩家正在答题
    ROUND_END = "round_end"      # 单回合结束
    FINISHED = "finished"        # 比赛结束


@dataclass
class Player:
    """玩家信息"""
    player_id: str
    name: str
    ws: Optional[WebSocket] = None
    is_ready: bool = False


@dataclass
class Question:
    """当前题目"""
    poem_id: int
    poem_title: str
    poem_author: str
    poem_dynasty: str
    line_index: int              # 诗句在诗中的位置索引
    upper_line: str              # 系统朗读的上句
    expected_lower: str          # 期望回答的下句


@dataclass
class WrongAnswer:
    """答错记录"""
    poem_id: int
    poem_title: str
    poem_author: str
    poem_dynasty: str
    player_id: str
    player_name: str
    upper_line: str
    expected_lower: str
    actual_answer: str           # 玩家实际回答（空字符串表示超时）


@dataclass
class RoundResult:
    """单回合结果"""
    correct: bool
    player_id: str
    player_name: str
    answer: str                  # 玩家回答
    expected: str                # 正确答案
    score_change: int            # 分数变化（+1 或 -1）
    scores: dict                 # 当前所有玩家分数 {player_id: score}


@dataclass
class GameSession:
    """游戏会话（一个房间）"""
    session_id: str                                    # 房间ID（6位随机码）
    players: list[Player] = field(default_factory=list)
    status: GameStatus = GameStatus.WAITING
    current_turn: int = 0                              # 当前答题玩家索引（0 或 1）
    round_number: int = 0                              # 当前回合数
    scores: dict = field(default_factory=dict)         # {player_id: score}
    used_poem_ids: set = field(default_factory=set)    # 本场已使用的诗词ID
    wrong_answers: list = field(default_factory=list)  # 答错记录
    current_question: Optional[Question] = None        # 当前题目

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def is_full(self) -> bool:
        return len(self.players) >= 2

    def get_player(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def get_opponent(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.player_id != player_id:
                return p
        return None

    def get_current_player(self) -> Optional[Player]:
        if 0 <= self.current_turn < len(self.players):
            return self.players[self.current_turn]
        return None

    def switch_turn(self):
        """切换到下一个玩家"""
        self.current_turn = 1 - self.current_turn
