"""
诗词PK - 全局配置
"""

import os
from pathlib import Path

# --- 路径配置 ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
POEMS_FILE = DATA_DIR / "poems.json"

# --- 游戏配置 ---
TARGET_SCORE = 3           # 目标分数，先达到此分数的玩家有机会获胜
LEAD_REQUIRED = 2          # 必须领先对手的分数
ANSWER_TIME_LIMIT = 60     # 每题答题时限（秒）
ANALYSIS_POEM_COUNT = 2    # 赛后每方解析的诗词数量

# --- LLM 配置（智谱 GLM-4-Flash） ---
# 注册地址: https://open.bigmodel.cn  注册后在控制台获取 API Key
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "c4ed6582364f4a22a1488f950aac255f.pr8afr2tpmSGcz6T")
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
ZHIPU_MODEL = "glm-4-flash"  # 完全免费的模型

# --- 答案判定配置 ---
SIMILARITY_THRESHOLD = 0.8  # 模糊匹配相似度阈值

# 同音字/多音字映射表（键为标准字，值为可替换的等价字）
HOMOPHONE_MAP = {
    "的": ["得", "地"],
    "长": ["常"],
    "清": ["青"],
    "生": ["声"],
    "明": ["名", "鸣"],
    "在": ["再"],
    "做": ["作"],
    "像": ["象"],
    "已": ["以"],
    "知": ["之"],
    "到": ["道"],
    "向": ["象"],
    "为": ["位", "未", "谓"],
    "他": ["她", "它"],
    "着": ["著"],
    "里": ["裏"],
    "那": ["哪"],
    "只": ["祇"],
    "不": ["弗"],
    "无": ["毋"],
    "与": ["於"],
}

# --- 服务器配置 ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# --- WebSocket 配置 ---
WS_HEARTBEAT_INTERVAL = 30   # 心跳间隔（秒）
ROOM_TIMEOUT = 60            # 房间超时时间（秒），断线后保留房间的时长
