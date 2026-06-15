# 诗词PK — 技术设计文档

## 一、项目概述

### 1.1 产品定位
一款基于 Web 的双人诗词对战游戏，通过语音对话完成诗词接龙，支持浏览器原生语音识别（STT）和语音合成（TTS），获胜规则为"先达 3 分且领先对手 2 分"。赛后自动从未答对的诗词中选取两首进行全面解析。

### 1.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 | HTML + CSS + JavaScript（单文件） | 零构建依赖，浏览器直接运行 |
| 语音识别 | Web Speech API (SpeechRecognition) | 按住说话模式，浏览器原生 |
| 语音合成 | SpeechSynthesis API | 浏览器原生 TTS，朗读诗词 |
| 后端 | Python 3.10+ / FastAPI | 轻量异步框架 |
| 实时通信 | WebSocket (FastAPI WebSocket) | 双人实时状态同步 |
| 数据存储 | SQLite + JSON 诗词文件 | SQLite 存储对战记录，JSON 存储题库 |
| 部署 | Uvicorn | ASGI 服务器，单进程即可 |

### 1.3 项目目录结构

```
PoetryPK/
├── docs/
│   └── TECHNICAL_DESIGN.md     # 本文档
├── backend/
│   ├── main.py                 # FastAPI 应用入口 + WebSocket
│   ├── game_engine.py          # 比赛引擎（回合、计分、胜负判定）
│   ├── poem_bank.py            # 题库管理（加载、随机抽取）
│   ├── poem_analyzer.py        # 诗词解析（赛后赏析）
│   ├── models.py               # 数据模型定义
│   ├── config.py               # 配置项
│   └── data/
│       └── poems.json          # 诗词题库数据
├── frontend/
│   └── index.html              # 单文件前端（HTML + CSS + JS）
├── requirements.txt            # Python 依赖
└── README.md                   # 项目说明
```

---

## 二、核心业务流程

### 2.1 比赛状态机

```
[等待匹配] ──(两人就绪)──> [比赛开始]
                              │
                              v
                        [出题阶段]
                        系统朗读上句(TTS)
                              │
                              v
                        [答题阶段]
                        当前玩家按住说话
                              │
                        ┌─────┴─────┐
                        v           v
                   [回答正确]   [回答错误]
                   +1分         -1分
                        │           │
                        └─────┬─────┘
                              v
                        [胜负判定]
                   ┌──────┐     ┌──────┐
                   │ 未达标 │     │ 已达标 │
                   └──┬───┘     └──┬───┘
                      v            v
                 [切换回合]    [比赛结束]
                 换人答题          │
                      │           v
                      │      [赛后解析]
                      │      选2首答错诗词
                      │      生成全面赏析
                      │           │
                      v           v
                 [出题阶段]   [展示结果]
```

### 2.2 回合流转规则

1. **开局**：随机决定谁先手，先手玩家回答第一题。
2. **轮次交替**：每答完一题（无论对错），切换答题权给对方。
3. **出题**：每次从题库中随机抽取一首诗，取其中一句作为"上句"，要求回答对应的"下句"。同一场比赛中同一首诗不会被重复抽取。
4. **答题计时**：每题限时 15 秒，超时视为答错。
5. **胜负判定**：每回合结束后检查——当前领先方分数 >= 3 **且** 领先对方 >= 2 分，则该玩家获胜。
6. **赛后解析**：比赛结束后，从所有参赛者"未答对"的诗词池中随机选取 2 首，由后端生成全面解析（作者背景、创作背景、逐句赏析、艺术手法、名句点评）。

### 2.3 答题判定逻辑

语音识别结果与标准答案的比对采用**模糊匹配**策略：

1. 预处理：去除标点符号、空格，统一转为简体小写。
2. 精确匹配：预处理后完全一致 → 判定正确。
3. 容错匹配：编辑距离 <= 2 且相似度 >= 80% → 判定正确（应对语音识别误差，如"青山"识别为"清山"）。
4. 多音字/通假字白名单：维护一张常见诗词多音字映射表（如"乐"↔"悦"），匹配时等价处理。

---

## 三、数据模型设计

### 3.1 诗词题库结构（poems.json）

```json
{
  "poems": [
    {
      "id": 1,
      "title": "静夜思",
      "author": "李白",
      "dynasty": "唐",
      "content": "床前明月光，疑是地上霜。举头望明月，低头思故乡。",
      "lines": [
        {
          "index": 0,
          "upper": "床前明月光",
          "lower": "疑是地上霜"
        },
        {
          "index": 1,
          "upper": "举头望明月",
          "lower": "低头思故乡"
        }
      ],
      "tags": ["五言绝句", "思乡", "月亮"],
      "analysis": {
        "background": "此诗作于开元十四年（726年），李白旅居扬州旅舍时...",
        "appreciation": "全诗仅二十字，没有奇特新颖的词语...",
        "technique": "以明白如话的语言表达深切的思乡之情..."
      }
    }
  ]
}
```

### 3.2 比赛会话模型（内存管理）

```python
@dataclass
class GameSession:
    session_id: str                  # 房间ID（6位随机码）
    players: list[Player]            # 两位玩家
    status: GameStatus               # WAITING / PLAYING / FINISHED
    current_turn: int                # 当前答题玩家索引（0 或 1）
    round_number: int                # 当前回合数
    scores: dict[str, int]           # {player_id: score}
    used_poem_ids: set[int]          # 本场已使用的诗词ID
    wrong_answers: list[WrongAnswer] # 答错记录（用于赛后解析）
    current_question: Question | None # 当前题目

@dataclass
class Player:
    player_id: str
    name: str
    ws: WebSocket                    # WebSocket 连接

@dataclass
class Question:
    poem_id: int
    poem_title: str
    poem_author: str
    upper_line: str                  # 系统朗读的上句
    expected_lower: str              # 期望回答的下句
    time_limit: int = 15             # 答题时限（秒）

@dataclass
class WrongAnswer:
    poem_id: int
    player_id: str
    upper_line: str
    expected_lower: str
    actual_answer: str               # 玩家实际回答（或为空=超时）
```

### 3.3 游戏状态枚举

```python
class GameStatus(Enum):
    WAITING = "waiting"        # 等待第二位玩家加入
    PLAYING = "playing"        # 比赛进行中
    ANSWERING = "answering"    # 玩家正在答题
    ROUND_END = "round_end"    # 单回合结束
    FINISHED = "finished"      # 比赛结束
```

---

## 四、WebSocket 通信协议

所有消息使用 JSON 格式，通过 `type` 字段区分消息类型。

### 4.1 客户端 → 服务端

| type | 说明 | 关键字段 |
|------|------|----------|
| `join_room` | 加入/创建房间 | `player_name`, `room_id?`（为空则创建新房间） |
| `ready` | 玩家准备就绪 | — |
| `start_recording` | 玩家按下说话按钮 | — |
| `stop_recording` | 玩家松开按钮 | `text`（前端识别结果） |
| `timeout` | 答题超时（前端计时器触发） | — |

### 4.2 服务端 → 客户端

| type | 说明 | 关键字段 |
|------|------|----------|
| `room_created` | 房间创建成功 | `room_id`, `player_id` |
| `player_joined` | 对手加入房间 | `opponent_name` |
| `game_start` | 比赛开始 | `first_player`（谁先手） |
| `new_round` | 新回合开始 | `round_number`, `current_player`, `upper_line` |
| `tts_speak` | 通知前端朗读上句 | `text`, `rate`, `pitch` |
| `answer_result` | 答题结果 | `correct`, `score_change`, `current_scores`, `expected_answer` |
| `turn_switch` | 切换答题权 | `next_player` |
| `game_over` | 比赛结束 | `winner`, `final_scores`, `total_rounds` |
| `poem_analysis` | 赛后诗词解析 | `poems`（2首诗词的完整解析） |
| `error` | 错误信息 | `message` |

### 4.3 消息流时序图

```
玩家A(创建者)           服务端              玩家B(加入者)
    │                    │                    │
    │──join_room────────>│                    │
    │<─room_created──────│                    │
    │                    │<─join_room─────────│
    │<─player_joined─────│                    │
    │                    │──room_created──────>│ (给B分配身份)
    │                    │                    │
    │──ready────────────>│<───────────ready───│
    │                    │                    │
    │<─game_start────────│────────game_start─>│
    │                    │                    │
    │<─new_round─────────│────────new_round──>│
    │<─tts_speak─────────│                    │ (如果A先手)
    │                    │                    │
    │──start_recording──>│                    │
    │──stop_recording───>│                    │
    │                    │                    │
    │<─answer_result─────│────answer_result──>│ (广播结果)
    │<─turn_switch───────│────turn_switch────>│
    │                    │                    │
    │                    │   ... 循环 ...      │
    │                    │                    │
    │<─game_over─────────│─────game_over─────>│
    │<─poem_analysis─────│──poem_analysis────>│
```

---

## 五、前端架构设计

### 5.1 页面状态视图

前端为单页面应用，通过 JS 控制不同视图的显示/隐藏：

| 视图 | 说明 | 核心元素 |
|------|------|----------|
| `#view-lobby` | 大厅 | 输入昵称、创建房间/加入房间 |
| `#view-waiting` | 等待对手 | 显示房间号（可分享），等待动画 |
| `#view-ready` | 双方就绪 | 双方头像/昵称，"准备"按钮 |
| `#view-game` | 比赛界面 | 计分板、当前回合、上句展示、按住说话按钮、倒计时 |
| `#view-result` | 比赛结果 | 胜负动画、最终比分、诗词解析卡片 |

### 5.2 核心前端模块

```javascript
// 主要模块划分（全部在 index.html 的 <script> 中）
const WS = { ... }              // WebSocket 连接管理
const Audio = { ... }           // 语音识别 + TTS 封装
const UI = { ... }              // DOM 操作 + 视图切换
const Game = { ... }            // 游戏状态管理
const Timer = { ... }           // 倒计时管理
```

### 5.3 语音交互流程（前端）

```
按住说话按钮
    │
    ├─ mousedown/touchstart
    │   → 停止TTS播放（避免干扰识别）
    │   → 启动 SpeechRecognition
    │   → UI显示"正在聆听..." + 录音动画
    │   → 启动15秒倒计时
    │
    └─ mouseup/touchend
        → 停止 SpeechRecognition
        → 获取最终识别文本
        → 发送 stop_recording 消息给服务端
        → UI显示"识别中..."
```

### 5.4 TTS 朗读策略

```javascript
function speakPoemLine(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN';
    utterance.rate = 0.8;     // 稍慢，便于听清
    utterance.pitch = 1.0;
    utterance.onend = () => {
        // 朗读结束后，激活按住说话按钮
        UI.enableRecordButton();
    };
    speechSynthesis.speak(utterance);
}
```

### 5.5 UI 设计风格

- **主题**：中国风水墨画风格，淡雅配色
- **主色调**：墨色 (#2c3e50) + 宣纸色 (#f5f0e8) + 朱砂红 (#c0392b)
- **字体**：标题用书法体（霞鹜文楷），正文用思源宋体
- **布局**：移动端优先，竖屏设计，核心操作区居中

---

## 六、后端模块设计

### 6.1 比赛引擎（game_engine.py）

```python
class GameEngine:
    """核心比赛引擎"""

    def create_room(self, player_name: str) -> GameSession:
        """创建房间，返回6位房间码"""

    def join_room(self, room_id: str, player_name: str) -> GameSession:
        """加入房间"""

    def next_question(self, session: GameSession) -> Question:
        """从题库中随机抽取未被使用的诗词出题"""

    def judge_answer(self, question: Question, answer: str) -> bool:
        """判定答案（模糊匹配 + 容错）"""

    def update_score(self, session: GameSession, player_id: str, correct: bool):
        """更新分数（+1 或 -1）"""

    def check_winner(self, session: GameSession) -> str | None:
        """检查是否有人获胜（>= 3分 且 领先 >= 2分）"""

    def get_analysis_poems(self, session: GameSession) -> list[dict]:
        """从答错记录中选2首，返回完整解析"""
```

### 6.2 题库管理（poem_bank.py）

```python
class PoemBank:
    """诗词题库管理"""

    def __init__(self, data_path: str):
        """加载 poems.json"""

    def get_random_poem(self, exclude_ids: set[int]) -> dict:
        """从题库中随机抽取一首未使用的诗"""

    def get_random_line(self, poem: dict) -> tuple[str, str]:
        """从诗中随机选取一组上下句"""

    def get_poem_by_id(self, poem_id: int) -> dict:
        """根据ID获取诗词完整信息"""

    def get_total_count(self) -> int:
        """题库总数"""
```

### 6.3 诗词解析（poem_analyzer.py）

```python
class PoemAnalyzer:
    """赛后诗词解析"""

    def generate_analysis(self, poem: dict) -> dict:
        """
        生成诗词全面解析，返回结构化内容：
        {
            "title": "...",
            "author": "...",
            "dynasty": "...",
            "content": "...",
            "background": "创作背景",
            "translation": "白话译文",
            "appreciation": "逐句赏析",
            "technique": "艺术手法",
            "famous_lines": "名句点评",
            "theme": "主题思想"
        }
        """

    def select_wrong_poems(self, wrong_answers: list, count: int = 2) -> list:
        """从答错记录中随机选取指定数量的诗词"""
```

解析数据来源优先级：
1. 题库 JSON 中预置的 `analysis` 字段（人工整理，质量最高）
2. 如果题库中无预置解析，后端基于模板生成基础解析框架
3. 后续可扩展：接入 LLM（如通义千问）生成高质量赏析

### 6.4 答案判定算法

```python
import re
from difflib import SequenceMatcher

def judge_answer(expected: str, actual: str, homophone_map: dict) -> bool:
    """
    模糊匹配答案判定
    """
    # 1. 预处理
    expected_clean = re.sub(r'[，。！？、\s]', '', expected).lower()
    actual_clean = re.sub(r'[，。！？、\s]', '', actual).lower()

    # 2. 精确匹配
    if expected_clean == actual_clean:
        return True

    # 3. 多音字/通假字替换后再匹配
    for key, values in homophone_map.items():
        for v in values:
            actual_clean = actual_clean.replace(v, key)
    if expected_clean == actual_clean:
        return True

    # 4. 编辑距离容错
    similarity = SequenceMatcher(None, expected_clean, actual_clean).ratio()
    if similarity >= 0.8:
        return True

    return False
```

---

## 七、API 接口设计

### 7.1 HTTP 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 返回前端页面 |
| GET | `/api/poems/count` | 获取题库总数 |
| GET | `/api/poems/{id}` | 获取指定诗词详情 |

### 7.2 WebSocket 接口

| 路径 | 说明 |
|------|------|
| `ws://host/ws/game` | 游戏主连接，所有游戏通信通过此通道 |

---

## 八、题库数据规模与初始内容

### 8.1 初始题库规划

首批录入 **50 首**经典诗词，覆盖以下类别：

- 五言绝句（10首）：静夜思、春晓、登鹳雀楼、相思、鹿柴 等
- 七言绝句（10首）：早发白帝城、望庐山瀑布、清明、出塞 等
- 五言律诗（10首）：春望、望岳、送友人、山居秋暝 等
- 七言律诗（10首）：登高、锦瑟、黄鹤楼、蜀相 等
- 宋词精选（10首）：水调歌头、念奴娇·赤壁怀古、如梦令 等

每首诗包含：标题、作者、朝代、全文、上下句配对、标签、预置解析。

### 8.2 题库扩展方式

- 直接编辑 `poems.json` 添加新诗
- 后续可提供管理接口批量导入

---

## 九、胜负判定算法详解

```python
def check_winner(scores: dict[str, int], target: int = 3, lead: int = 2) -> str | None:
    """
    检查是否有玩家获胜

    获胜条件：
    1. 该玩家分数 >= target（默认3）
    2. 该玩家领先对手 >= lead 分（默认2）

    示例：
    - 3:1 → 玩家1获胜（>= 3 且领先2分）
    - 3:2 → 无人获胜（仅领先1分）
    - 4:2 → 玩家1获胜（>= 3 且领先2分）
    - 2:0 → 无人获胜（未达3分）
    """
    players = list(scores.keys())
    if len(players) != 2:
        return None

    p1, p2 = players
    s1, s2 = scores[p1], scores[p2]

    if s1 >= target and s1 - s2 >= lead:
        return p1
    if s2 >= target and s2 - s1 >= lead:
        return p2

    return None
```

---

## 十、关键技术难点与方案

### 10.1 语音识别准确率

| 问题 | 方案 |
|------|------|
| 古诗词发音不标准 | 降低识别置信度阈值，配合编辑距离容错 |
| 环境噪音干扰 | 按住说话模式天然减少噪音，前端加降噪预处理 |
| 同音字误识别 | 维护诗词专用多音字/同音字映射表 |
| 方言口音 | 容错匹配阈值放宽至 80% 相似度 |

### 10.2 WebSocket 连接管理

- 每个房间维护一个 `GameSession` 对象，存在内存中（dict[room_id -> GameSession]）
- 玩家断线重连：保留房间 60 秒，超时自动解散
- 心跳检测：每 30 秒 ping/pong，检测连接存活

### 10.3 并发安全

- 单进程模型（Uvicorn 单 worker），利用 Python asyncio 协程调度，无需锁
- 同一房间的消息串行处理（asyncio 天然保证）

---

## 十一、开发计划

### Phase 1：核心框架（预计工作量：主要部分）

- [ ] 项目脚手架搭建（目录结构、依赖配置）
- [ ] 诗词题库数据准备（poems.json，50首经典诗词）
- [ ] 后端 FastAPI + WebSocket 基础框架
- [ ] 题库管理模块（加载、随机抽取）
- [ ] 比赛引擎（创建/加入房间、出题、计分、胜负判定）
- [ ] 前端页面骨架（大厅、等待、比赛、结果四个视图）
- [ ] WebSocket 前后端联调
- [ ] 语音识别集成（Web Speech API）
- [ ] 语音合成集成（SpeechSynthesis API）
- [ ] 答案判定算法（模糊匹配 + 容错）

### Phase 2：体验优化

- [ ] 赛后诗词解析模块
- [ ] UI 美化（水墨风主题）
- [ ] 答题倒计时动画
- [ ] 音效反馈（答对/答错音效）
- [ ] 移动端适配

### Phase 3：扩展功能（可选）

- [ ] 接入 LLM 生成高质量诗词赏析
- [ ] 题库管理后台
- [ ] 历史战绩记录
- [ ] 多人模式（3-4人轮流）
- [ ] 难度等级（简单/中等/困难题库）

---

## 十二、依赖清单

### requirements.txt

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
websockets>=12.0
pydantic>=2.5.0
```

极简依赖，全部为标准 Python 生态常用包，无重型依赖。

---

## 十三、启动方式

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 访问
# 浏览器打开 http://localhost:8000
```
