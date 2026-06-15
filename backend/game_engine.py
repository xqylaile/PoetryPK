"""
诗词PK - 比赛引擎
负责房间管理、出题、计分、胜负判定
"""

import random
import re
import string
from difflib import SequenceMatcher
from typing import Optional

from config import (
    TARGET_SCORE,
    LEAD_REQUIRED,
    ANSWER_TIME_LIMIT,
    SIMILARITY_THRESHOLD,
    HOMOPHONE_MAP,
    ANALYSIS_POEM_COUNT,
)
from models import (
    GameSession,
    GameStatus,
    Player,
    Question,
    WrongAnswer,
    RoundResult,
)
from poem_bank import PoemBank
from poem_analyzer import PoemAnalyzer


class GameEngine:
    """核心比赛引擎"""

    def __init__(self, poem_bank: PoemBank):
        self.poem_bank = poem_bank
        self.analyzer = PoemAnalyzer()
        self.sessions: dict[str, GameSession] = {}  # room_id -> GameSession

    # --- 房间管理 ---

    def create_room(self, player_name: str) -> tuple[GameSession, Player]:
        """
        创建房间

        Returns:
            (session, player) 元组
        """
        room_id = self._generate_room_id()
        player_id = self._generate_player_id()

        player = Player(player_id=player_id, name=player_name)
        session = GameSession(
            session_id=room_id,
            players=[player],
            status=GameStatus.WAITING,
        )
        self.sessions[room_id] = session
        return session, player

    def join_room(self, room_id: str, player_name: str) -> tuple[Optional[GameSession], Optional[Player], str]:
        """
        加入房间

        Returns:
            (session, player, error_message) 元组
            成功时 error_message 为空字符串
        """
        session = self.sessions.get(room_id)
        if not session:
            return None, None, "房间不存在"

        if session.status != GameStatus.WAITING:
            return None, None, "比赛已经开始，无法加入"

        if session.is_full:
            return None, None, "房间已满"

        player_id = self._generate_player_id()
        player = Player(player_id=player_id, name=player_name)
        session.players.append(player)
        return session, player, ""

    def set_ready(self, session: GameSession, player_id: str) -> bool:
        """设置玩家准备状态，返回是否双方都已准备"""
        player = session.get_player(player_id)
        if not player:
            return False

        player.is_ready = True
        return all(p.is_ready for p in session.players)

    def start_game(self, session: GameSession) -> int:
        """
        开始比赛，返回先手玩家索引

        初始化分数，随机决定谁先手
        """
        session.status = GameStatus.PLAYING
        session.round_number = 0
        session.current_turn = random.randint(0, 1)
        session.scores = {p.player_id: 0 for p in session.players}
        session.used_poem_ids = set()
        session.wrong_answers = []
        session.current_question = None
        return session.current_turn

    def remove_session(self, room_id: str):
        """移除房间"""
        self.sessions.pop(room_id, None)

    # --- 出题 ---

    def next_question(self, session: GameSession) -> Optional[Question]:
        """
        从题库中随机抽取未被使用的诗词，生成下一道题目

        Returns:
            Question 对象，题库耗尽时返回 None
        """
        poem = self.poem_bank.get_random_poem(session.used_poem_ids)
        if not poem:
            return None

        line_index, upper_line, expected_lower = self.poem_bank.get_random_line(poem)
        session.used_poem_ids.add(poem["id"])
        session.round_number += 1
        session.status = GameStatus.ANSWERING

        question = Question(
            poem_id=poem["id"],
            poem_title=poem["title"],
            poem_author=poem["author"],
            poem_dynasty=poem.get("dynasty", ""),
            line_index=line_index,
            upper_line=upper_line,
            expected_lower=expected_lower,
        )
        session.current_question = question
        return question

    # --- 答案判定 ---

    def judge_answer(self, expected: str, actual: str) -> bool:
        """
        判定答案是否正确（模糊匹配 + 容错）

        策略：
        1. 去标点空格后精确匹配
        2. 多音字/同音字替换后匹配
        3. 编辑距离模糊匹配（相似度 >= 80%）
        """
        if not actual or not actual.strip():
            return False

        # 预处理
        expected_clean = self._preprocess(expected)
        actual_clean = self._preprocess(actual)

        if not expected_clean or not actual_clean:
            return False

        # 精确匹配
        if expected_clean == actual_clean:
            return True

        # 多音字/同音字替换后匹配
        actual_replaced = self._replace_homophones(actual_clean)
        expected_replaced = self._replace_homophones(expected_clean)
        if expected_replaced == actual_replaced:
            return True

        # 编辑距离容错
        similarity = SequenceMatcher(None, expected_clean, actual_clean).ratio()
        return similarity >= SIMILARITY_THRESHOLD

    @staticmethod
    def _preprocess(text: str) -> str:
        """预处理文本：去标点、空格，转小写"""
        # 去除所有空白字符
        text = re.sub(r'\s+', '', text)
        # 去除常见中英文标点
        for p in list('，。！？、；：【】《》（）,.!?;()[]{}') + ['"', "'", '\u201c', '\u201d', '\u2018', '\u2019', '\u00b7', '\u2014', '\u2026']:
            text = text.replace(p, '')
        return text.lower().strip()

    @staticmethod
    def _replace_homophones(text: str) -> str:
        """替换同音字/多音字"""
        for standard, variants in HOMOPHONE_MAP.items():
            for v in variants:
                text = text.replace(v, standard)
        return text

    # --- 计分与回合管理 ---

    def process_answer(self, session: GameSession, player_id: str, answer: str) -> RoundResult:
        """
        处理玩家回答

        Args:
            session: 游戏会话
            player_id: 回答的玩家ID
            answer: 玩家的回答文本

        Returns:
            RoundResult 包含判定结果和当前分数
        """
        question = session.current_question
        if not question:
            raise ValueError("当前没有题目")

        player = session.get_player(player_id)
        correct = self.judge_answer(question.expected_lower, answer)

        # 更新分数
        score_change = 1 if correct else -1
        session.scores[player_id] = max(0, session.scores[player_id] + score_change)

        # 记录答错
        if not correct:
            wrong = WrongAnswer(
                poem_id=question.poem_id,
                poem_title=question.poem_title,
                poem_author=question.poem_author,
                poem_dynasty=question.poem_dynasty,
                player_id=player_id,
                player_name=player.name,
                upper_line=question.upper_line,
                expected_lower=question.expected_lower,
                actual_answer=answer,
            )
            session.wrong_answers.append(wrong)

        session.status = GameStatus.ROUND_END
        session.current_question = None

        return RoundResult(
            correct=correct,
            player_id=player_id,
            player_name=player.name,
            answer=answer,
            expected=question.expected_lower,
            score_change=score_change,
            scores=dict(session.scores),
        )

    def process_timeout(self, session: GameSession) -> RoundResult:
        """
        处理答题超时

        Returns:
            RoundResult
        """
        player = session.get_current_player()
        return self.process_answer(session, player.player_id, "")

    def check_winner(self, session: GameSession) -> Optional[str]:
        """
        检查是否有玩家获胜

        获胜条件：分数 >= TARGET_SCORE 且领先对手 >= LEAD_REQUIRED 分

        Returns:
            获胜玩家ID，无人获胜时返回 None
        """
        players = session.players
        if len(players) != 2:
            return None

        p1_id, p2_id = players[0].player_id, players[1].player_id
        s1 = session.scores.get(p1_id, 0)
        s2 = session.scores.get(p2_id, 0)

        if s1 >= TARGET_SCORE and (s1 - s2) >= LEAD_REQUIRED:
            return p1_id
        if s2 >= TARGET_SCORE and (s2 - s1) >= LEAD_REQUIRED:
            return p2_id

        return None

    def advance_turn(self, session: GameSession):
        """切换到下一个玩家并恢复比赛状态"""
        session.switch_turn()
        session.status = GameStatus.PLAYING

    # --- 赛后解析 ---

    def get_wrong_poems_by_player(self, session: GameSession) -> dict[str, list[int]]:
        """
        按玩家分组，返回各自答错的诗词ID列表（去重）

        Returns:
            {player_id: [poem_id, ...], ...}
        """
        result = {}
        for player in session.players:
            ids = list(set(
                w.poem_id for w in session.wrong_answers
                if w.player_id == player.player_id
            ))
            result[player.player_id] = ids
        return result

    async def get_post_game_analysis(self, session: GameSession) -> list[dict]:
        """
        赛后解析：从双方各自的答错诗词中各选2首，调用 LLM 生成全面解析

        Returns:
            解析结果列表，每项包含 player_name 标识归属
        """
        wrong_by_player = self.get_wrong_poems_by_player(session)
        all_results = []
        print(f"[赛后解析] 双方答错统计: { {k: len(v) for k, v in wrong_by_player.items()} }")

        for player in session.players:
            player_id = player.player_id
            wrong_ids = wrong_by_player.get(player_id, [])
            print(f"[赛后解析] 玩家 {player.name} 答错 {len(wrong_ids)} 首")

            if not wrong_ids:
                # 该玩家全部答对，随机选2首推荐赏析
                all_ids = [p["id"] for p in self.poem_bank.poems]
                selected_ids = random.sample(all_ids, min(ANALYSIS_POEM_COUNT, len(all_ids)))
                print(f"[赛后解析] 玩家 {player.name} 全对，随机推荐: {selected_ids}")
            else:
                selected_ids = self.analyzer.select_wrong_poems(wrong_ids, ANALYSIS_POEM_COUNT)
                print(f"[赛后解析] 玩家 {player.name} 选取解析: {selected_ids}")

            for pid in selected_ids:
                poem = self.poem_bank.get_poem_by_id(pid)
                if poem:
                    print(f"[赛后解析] 正在解析诗词 id={pid} 《{poem.get('title', '?')}》...")
                    # 调用 LLM 生成解析
                    analysis = await self.analyzer.generate_analysis_llm(poem)
                    llm_flag = analysis.get("llm_generated", False)
                    print(f"[赛后解析] 诗词 id={pid} 解析完成 (LLM生成={llm_flag})")
                    analysis["player_name"] = player.name
                    analysis["player_id"] = player_id
                    all_results.append(analysis)
                else:
                    print(f"[赛后解析] 诗词 id={pid} 不存在，跳过")

        return all_results

    # --- 工具方法 ---

    @staticmethod
    def _generate_room_id() -> str:
        """生成6位房间码"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    @staticmethod
    def _generate_player_id() -> str:
        """生成玩家ID"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
