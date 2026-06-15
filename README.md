# 诗词PK - 双人诗词对战语音游戏

一款基于 Web 的双人诗词对战游戏，通过语音对话完成诗词接龙。系统朗读上句，玩家按住按钮语音回答下句，答对加分、答错扣分，先达 3 分且领先对手 2 分者获胜。赛后自动解析未答对的诗词。

## 技术栈

- **后端**: Python 3.10+ / FastAPI + WebSocket
- **前端**: 原生 HTML + CSS + JavaScript（单文件，零构建）
- **语音识别**: 浏览器 Web Speech API（按住说话模式）
- **语音合成**: 浏览器 SpeechSynthesis API
- **数据存储**: JSON 诗词题库

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
cd backend
python main.py
```

或：

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 访问游戏

浏览器打开 http://localhost:8000

两个浏览器标签页（或两台设备）分别打开，一个创建房间，另一个输入房间码加入。

## 游戏规则

1. 两人加入同一房间后，点击"准备"开始比赛
2. 系统随机抽取一首诗，朗读上句
3. 当前玩家按住"说话"按钮，语音回答下句
4. 答对 +1 分，答错 -1 分（最低 0 分）
5. 每题限时 15 秒，超时视为答错
6. 先达到 3 分且领先对手至少 2 分的玩家获胜
7. 比赛结束后，系统从未答对的诗词中选取 2 首进行全面解析

## 项目结构

```
PoetryPK/
├── docs/
│   └── TECHNICAL_DESIGN.md     # 技术设计文档
├── backend/
│   ├── main.py                 # FastAPI 入口 + WebSocket
│   ├── game_engine.py          # 比赛引擎
│   ├── poem_bank.py            # 题库管理
│   ├── poem_analyzer.py        # 诗词解析
│   ├── models.py               # 数据模型
│   ├── config.py               # 配置项
│   └── data/
│       └── poems.json          # 诗词题库（50首）
├── frontend/
│   └── index.html              # 单文件前端
├── requirements.txt
└── README.md
```

## 扩展题库

编辑 `backend/data/poems.json`，按照现有格式添加新诗词即可。每首诗需要包含：

- `id`: 唯一编号（递增）
- `title`: 标题
- `author`: 作者
- `dynasty`: 朝代
- `content`: 全文
- `lines`: 上下句配对数组
- `tags`: 标签
- `analysis`: 解析（background / translation / appreciation / technique / famous_lines / theme）
