# 诗词PK - 双人诗词对战语音游戏

一款基于 Web 的双人诗词对战游戏，支持语音和文字两种答题方式。系统朗读诗词上句，玩家通过麦克风语音或文字输入回答下句，答对加分、答错扣分，先达 3 分且领先对手 2 分者获胜。赛后 AI 自动解析未答对的诗词，并支持语音播报赏析内容。

## 技术栈

- **后端**: Python 3.10+ / FastAPI + WebSocket
- **前端**: 原生 HTML + CSS + JavaScript（单文件，零构建）
- **语音识别**: 科大讯飞语音听写（WebSocket 流式识别，MP3 编码传输）
- **语音合成**: 浏览器 SpeechSynthesis API（系统 TTS）
- **AI 诗词解析**: 智谱 GLM-4-Flash（赛后生成诗词赏析）
- **数据存储**: JSON 诗词题库

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥（可选）

项目默认已内置可用的 API 密钥，如需替换可修改 `backend/config.py` 或通过环境变量设置：

- **讯飞语音识别**: `IFLYTEK_APP_ID`、`IFLYTEK_API_KEY`、`IFLYTEK_API_SECRET`
  - 注册地址: https://www.xfyun.cn/
- **智谱 AI**: `ZHIPU_API_KEY`
  - 注册地址: https://open.bigmodel.cn

### 3. 启动服务

```bash
cd backend
python main.py
```

或：

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问游戏

浏览器打开 http://localhost:8000

在同一页面上输入两位玩家的姓名，点击"开始比赛"即可。

## 游戏玩法

### 比赛流程

1. 在大厅输入两位玩家姓名，点击"开始比赛"
2. 系统随机决定先手，并抽取一首诗词朗读上句（语音自动播报）
3. 轮到答题的玩家有两种作答方式：
   - **语音答题**: 按住"说话"按钮，对着麦克风说出下句，松开后自动识别并提交
   - **文字答题**: 在下方输入框中手动输入下句，点击"提交"或按回车
4. 系统判定答案并语音播报结果（正确/错误 + 正确答案）
5. 双方交替答题，每回合切换答题玩家

### 计分规则

- 答对 +1 分，答错 -1 分（最低 0 分）
- 每题限时 60 秒，超时视为答错

### 获胜条件

先达到 3 分且领先对手至少 2 分的玩家获胜。

### 赛后赏析

比赛结束后，AI 会从双方各自答错的诗词中各选取 2 首，生成全面的诗词赏析，包括创作背景、白话译文、逐句赏析、艺术手法、名句点评和主题思想。每首诗词卡片底部有"语音播报"按钮，点击即可朗读整篇赏析内容。

## 语音识别说明

- 语音识别基于科大讯飞 WebSocket 流式方案，音频经 lamejs 编码为 MP3 后传输，识别延迟低
- 按住说话期间页面会实时显示识别结果，松开后自动提交
- 若浏览器不支持麦克风或无权限，可直接使用文字输入答题
- 内置调试模式：无麦克风时可验证讯飞连接，并通过文字输入模拟语音识别

## 项目结构

```
PoetryPK/
├── docs/
│   └── TECHNICAL_DESIGN.md     # 技术设计文档
├── backend/
│   ├── main.py                 # FastAPI 入口 + WebSocket
│   ├── game_engine.py          # 比赛引擎
│   ├── poem_bank.py            # 题库管理
│   ├── poem_analyzer.py        # 诗词解析（LLM + 预置）
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
