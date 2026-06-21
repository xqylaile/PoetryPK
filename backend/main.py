"""
诗词PK - FastAPI 应用入口
本地双人模式：单连接管理整场比赛
"""

import asyncio
import base64
import hashlib
import hmac
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# 将 backend 目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    HOST, PORT, ANSWER_TIME_LIMIT,
    IFLYTEK_APP_ID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET,
)
from models import GameStatus
from poem_bank import PoemBank
from game_engine import GameEngine

# --- 初始化 ---
app = FastAPI(title="诗词PK", version="1.0.0")

# 加载题库和引擎
poem_bank = PoemBank()
engine = GameEngine(poem_bank)

# 前端路径
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# --- HTTP 路由 ---

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>前端页面未找到</h1><p>请确保 frontend/index.html 存在</p>")


@app.get("/api/poems/count")
async def get_poem_count():
    """获取题库总数"""
    return {"count": poem_bank.get_total_count()}


@app.get("/api/poems/{poem_id}")
async def get_poem(poem_id: int):
    """获取指定诗词详情"""
    poem = poem_bank.get_poem_by_id(poem_id)
    if not poem:
        return {"error": "诗词不存在"}
    return poem


@app.get("/api/iflytek/ws_url")
async def get_iflytek_ws_url():
    """
    生成讯飞语音听写 WebSocket 鉴权 URL
    密钥在后端签名，不暴露给前端
    """
    try:
        host = "ws-api.xfyun.cn"
        path = "/v2/iat"
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # 构建签名原文
        signature_origin = (
            f"host: {host}\n"
            f"date: {date_str}\n"
            f"GET {path} HTTP/1.1"
        )

        # HMAC-SHA256 签名
        signature_sha = hmac.new(
            IFLYTEK_API_SECRET.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode("utf-8")

        # 构建 authorization
        authorization_origin = (
            f'api_key="{IFLYTEK_API_KEY}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        # 拼接 WebSocket URL
        params = {
            "authorization": authorization,
            "date": date_str,
            "host": host,
        }
        url = f"wss://{host}{path}?{urlencode(params)}"

        return {"url": url, "app_id": IFLYTEK_APP_ID}
    except Exception as e:
        print(f"[讯飞] 鉴权URL生成失败: {type(e).__name__}: {e}")
        return {"error": str(e)}


# --- WebSocket 游戏通信（本地双人，单连接） ---

# 当前活跃的 WebSocket 连接和对应的游戏会话
_active_sessions: dict[str, WebSocket] = {}  # session_id -> ws


@app.websocket("/ws/game")
async def websocket_game(ws: WebSocket):
    """游戏 WebSocket 连接 —— 一条连接管理整场比赛"""
    await ws.accept()
    session_id = None

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_error(ws, "消息格式错误，需要 JSON")
                continue

            msg_type = msg.get("type", "")

            # --- 开始比赛（一次性创建双方玩家 + 开局） ---
            if msg_type == "start_game":
                player1_name = msg.get("player1_name", "玩家1").strip()
                player2_name = msg.get("player2_name", "玩家2").strip()

                if not player1_name or not player2_name:
                    await send_error(ws, "请输入两位玩家姓名")
                    continue

                if player1_name == player2_name:
                    player2_name = player2_name + "(2)"

                # 创建房间并加入两位玩家
                session, p1 = engine.create_room(player1_name)
                _, p2, _ = engine.join_room(session.session_id, player2_name)

                session_id = session.session_id
                _active_sessions[session_id] = ws

                # 设置双方 ws（同一连接）
                p1.ws = ws
                p2.ws = ws

                # 直接开始比赛
                first_turn = engine.start_game(session)
                first_player = session.players[first_turn]

                await send_json(ws, {
                    "type": "game_start",
                    "first_player": first_player.player_id,
                    "first_player_name": first_player.name,
                    "players": [
                        {"id": pp.player_id, "name": pp.name}
                        for pp in session.players
                    ],
                })

                # 自动出第一题
                await _send_new_round(session, ws)

            # --- 提交答案 ---
            elif msg_type == "stop_recording":
                session = _get_session(session_id)
                if not session or session.status != GameStatus.ANSWERING:
                    await send_error(ws, "当前不是答题阶段")
                    continue

                answer_text = msg.get("text", "").strip()
                await _process_answer(session, ws, answer_text)

            # --- 答题超时 ---
            elif msg_type == "timeout":
                session = _get_session(session_id)
                if not session or session.status != GameStatus.ANSWERING:
                    continue

                await _process_answer(session, ws, "")

            else:
                await send_error(ws, f"未知消息类型: {msg_type}")

    except WebSocketDisconnect:
        # 连接断开，清理会话
        if session_id:
            session = _get_session(session_id)
            if session and session.status != GameStatus.FINISHED:
                engine.remove_session(session_id)
            _active_sessions.pop(session_id, None)


# --- 内部辅助方法 ---

def _get_session(session_id: str):
    """根据会话ID获取会话"""
    if not session_id:
        return None
    return engine.sessions.get(session_id)


async def send_json(ws: WebSocket, data: dict):
    """发送 JSON 消息"""
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        print(f"[WebSocket] 发送消息失败: type={data.get('type', '?')}, 错误={type(e).__name__}: {e}")


async def send_error(ws: WebSocket, message: str):
    """发送错误消息"""
    await send_json(ws, {"type": "error", "message": message})


async def _send_new_round(session, ws: WebSocket):
    """出新题"""
    question = engine.next_question(session)

    if not question:
        # 题库耗尽，直接结束
        await _finish_game(session, ws)
        return

    current_player = session.get_current_player()

    await send_json(ws, {
        "type": "new_round",
        "round_number": session.round_number,
        "current_player": current_player.player_id,
        "current_player_name": current_player.name,
        "upper_line": question.upper_line,
        "poem_title": question.poem_title,
        "poem_author": question.poem_author,
        "time_limit": ANSWER_TIME_LIMIT,
    })

    # TTS 朗读上句
    await send_json(ws, {
        "type": "tts_speak",
        "text": question.upper_line,
        "rate": 0.8,
        "pitch": 1.0,
    })


async def _process_answer(session, ws: WebSocket, answer_text: str):
    """处理答题结果并推进游戏"""
    current_player = session.get_current_player()
    result = engine.process_answer(session, current_player.player_id, answer_text)

    # 发送答题结果
    await send_json(ws, {
        "type": "answer_result",
        "correct": result.correct,
        "player_id": result.player_id,
        "player_name": result.player_name,
        "answer": result.answer or "（超时未作答）",
        "expected_answer": result.expected,
        "score_change": result.score_change,
        "current_scores": result.scores,
        "scores_display": {
            pp.name: result.scores[pp.player_id]
            for pp in session.players
        },
    })

    # TTS 朗读答题结果
    if result.correct:
        tts_text = f"回答正确！下句是，{result.expected}"
    else:
        answer_part = ""
        if result.answer and result.answer.strip():
            answer_part = f"你回答的是，{result.answer}。"
        else:
            answer_part = "超时未作答。"
        tts_text = f"回答错误。{answer_part}正确答案是，{result.expected}"

    await send_json(ws, {
        "type": "tts_speak",
        "text": tts_text,
        "rate": 0.9,
        "pitch": 1.0,
    })

    # 检查是否有人获胜
    winner_id = engine.check_winner(session)

    if winner_id:
        await _finish_game(session, ws, winner_id)
    else:
        # 切换回合，出下一题
        engine.advance_turn(session)
        # 短暂延迟让前端展示结果
        await asyncio.sleep(2)
        await _send_new_round(session, ws)


async def _finish_game(session, ws: WebSocket, winner_id: str = None):
    """结束比赛并发送赛后解析"""
    print(f"[比赛结束] 会话={session.session_id}, 获胜者={winner_id}")
    session.status = GameStatus.FINISHED

    winner = session.get_player(winner_id) if winner_id else None

    # 发送比赛结束
    await send_json(ws, {
        "type": "game_over",
        "winner": winner_id,
        "winner_name": winner.name if winner else "平局",
        "final_scores": session.scores,
        "scores_display": {
            pp.name: session.scores[pp.player_id]
            for pp in session.players
        },
        "total_rounds": session.round_number,
    })

    # TTS 播报比赛结果
    if winner:
        p1 = session.players[0]
        p2 = session.players[1]
        s1 = session.scores.get(p1.player_id, 0)
        s2 = session.scores.get(p2.player_id, 0)
        tts_text = f"比赛结束！{winner.name}获胜！最终比分，{p1.name} {s1} 分，{p2.name} {s2} 分。"
    else:
        tts_text = "比赛结束，双方平局！"
    await send_json(ws, {
        "type": "tts_speak",
        "text": tts_text,
        "rate": 0.9,
        "pitch": 1.0,
    })
    print("[比赛结束] game_over 消息已发送，开始生成赛后解析...")

    # 生成赛后解析（调用 LLM，可能较慢）
    try:
        print("[赛后解析] 调用 get_post_game_analysis...")
        analysis_results = await engine.get_post_game_analysis(session)
        print(f"[赛后解析] 完成，共生成 {len(analysis_results)} 条解析")
    except Exception as e:
        print(f"[赛后解析] 生成失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        analysis_results = []

    print("[赛后解析] 正在推送 poem_analysis 消息...")
    await send_json(ws, {
        "type": "poem_analysis",
        "poems": analysis_results,
    })
    print("[赛后解析] poem_analysis 已发送")

    # 延迟清理
    await asyncio.sleep(5)
    engine.remove_session(session.session_id)
    _active_sessions.pop(session.session_id, None)
    print(f"[比赛结束] 会话 {session.session_id} 已清理")


# --- 启动 ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
