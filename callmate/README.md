# CallMate — 实时通话辅助 AI

[![CI](https://github.com/Firefly-Star/CallMate/actions/workflows/test.yml/badge.svg)](https://github.com/Firefly-Star/CallMate/actions/workflows/test.yml)

> 帮 i 人轻松打电话 (´･ω･)ﾉ

通话进行时实时转写对方说的话，结合「你是谁 / 对方是谁 / 这通电话要干什么」三层上下文，
推理出此刻最合适的接法，给出 2–3 条带理由的建议。它不替你说话，只在你卡住的那三秒里递一句台词。

---

## 现在能跑到哪一步

先说实话，免得你 clone 下来发现跑不动：

| 模式 | 启动命令 | 音频来源 | 转写 | 建议生成 | 状态 |
|---|---|---|---|---|---|
| 纯文本 Mock | `callmate --mock` | 你手动打字 | — | 固定话术 | ✅ 可跑 |
| 流式 Mock | `callmate --mock-stream` | 模拟事件流 | MockStreamer | 固定话术 | ✅ 可跑 |
| 真实通话 | — | sounddevice 采集 | Deepgram Listen V2 | OpenAI 兼容 / Anthropic | ⏳ 未接线 |

`main.py` 目前把 advisor 和 transcriber 都固定成 mock 后端。真实链路的三个部件——
音频采集（`core/audio_capture.py`）、Deepgram 实时转写（`core/transcriber.py`）、
LLM 建议生成（`core/advisor.py` 里的 `OpenAIAdvisor` / `AnthropicAdvisor`）——
代码都写完并且有单元测试，但**还没有接到 CLI 入口上**。这是本仓库的第一优先待办，
见 [Roadmap](#roadmap)。

---

## 为什么做这个

即时语音通话对内向的人是一种高压力沟通：不像文字可以反复斟酌，也没有撤回键。

- 对方话里有话，不敢追问
- 知道该回应，但一时想不出得体的说法
- 冷场时脑子空白
- 挂断之后才想到「刚才应该那样说」

CallMate 不替代你说话，只想把「想不出该说什么」的那几秒补上。

---

## 快速开始

> **不是** `pip install callmate` —— PyPI 上没有这个包。从源码装：

```bash
git clone https://github.com/Firefly-Star/CallMate.git
cd CallMate

python -m venv .venv
# Linux / macOS
. .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -e callmate/
callmate --mock
```

也可以用 conda（仓库里保留了 `environment.yml`）：

```bash
conda env create -f environment.yml
conda activate callmate
```

**不需要任何 API key 就能跑起来** —— Mock 模式下不联网。

---

## 怎么用

终端界面分三块：上方是通话对象与状态栏，中间是对话历史，下方是建议区与输入栏。

```
┌─ CallMate ─────────── 张老师 (导师) ─────────── Mock 模式 ─┐
│ 对方: 你这个课题的进度怎么样了？                            │
│                                                            │
│ 建议                                                       │
│ 1. 老师，实验跑完了，正在整理数据，周五前给您完整报告。     │
│    └ 给明确时间点，比「快了」更容易让对方放心               │
│ 2. 主体实验已完成，还差一组对照，想请您看看设计是否合理。   │
│    └ 把一个待决策点抛回去，把通话变成讨论                   │
│                                                            │
│ > _                                                        │
└────────────────────────────────────────────────────────────┘
```

### 命令

| 命令 | 作用 |
|---|---|
| `/help` | 显示帮助 |
| `/profile` | 查看当前通话对象 |
| `/profile <名字>` | 切换对象（不存在时会问你要不要创建） |
| `/refresh` | 手动重新生成建议 |
| `/note <文本>` | 加一条备注（不发给对方，只影响后续推理） |
| `/quit`、`/end` | 结束通话，退出 |

### 两种 Mock 模式的区别

- **`--mock`**：你打一行字 = 对方说了一句话，立刻给出建议。用来验证「建议质量」。
- **`--mock-stream`**：`MockStreamer` 按事件序列模拟 Deepgram 的实时回调（中间结果 → 最终结果、
  说话人交替），逐字流式显示。用来验证「实时链路会不会串台」，不需要麦克风也不需要 API key。

---

## 架构

```
callmate/
├── main.py                  CLI 入口、两种 mock 循环、通话结束流程
├── core/
│   ├── audio_capture.py     sounddevice 采集（PulseAudio / Mock 双后端，chunked 回调）
│   ├── transcriber.py       Deepgram Listen V2 实时转写 + Mock 后端
│   ├── advisor.py           建议生成：OpenAIAdvisor / AnthropicAdvisor / MockAdvisor
│   ├── dialogue_manager.py  对话历史 + SOUL.md + 三层 prompt 组装
│   ├── presenter.py         ANSI 终端 UI（历史 / 建议 / 输入三区，无第三方 UI 依赖）
│   └── command_handler.py   slash 命令解析与分发
├── storage/
│   ├── profile_store.py     对象档案 CRUD（JSON）
│   └── history_store.py     通话记录落盘（一次通话一个 JSON）
├── utils/
│   ├── config.py            .env 读取与默认值
│   └── mock_stream.py       模拟 Deepgram 事件序列
└── tests/                   9 个测试文件，见下
```

### 三层 prompt

建议质量取决于喂进去的上下文。`dialogue_manager.build_prompt()` 把它拆成三段：

| 层 | 来源 | 内容 |
|---|---|---|
| **SOUL** | `~/.callmate/soul.md` | 你自己的说话风格与原则（首次运行会写一份默认的） |
| **PROFILE** | `~/.callmate/profiles.json` | 对方是谁：关系、场合、常聊话题、备注、关键词 |
| **TRANSCRIPT** | 内存中的对话历史 | 这通电话到目前为止的原话 |

`advisor.advise()` 只接收这三段，返回 `[{"text": "建议的话", "reason": "为什么这么说"}]`。
把「理由」和「台词」分开返回，是因为通话中你只需要一眼扫到台词，理由用来事后复盘。

---

## 数据存在哪

全部在本地，不上传、不联网（除了你显式启用的 API 调用）：

| 路径 | 内容 |
|---|---|
| `~/.callmate/profiles.json` | 对象档案（**明文 JSON**，别往里写密码） |
| `~/.callmate/history/call_<时间戳>.json` | 每次通话的完整记录 |
| `~/.callmate/soul.md` | 你的说话风格 |
| `~/.callmate/.env` | API key（也可以放在项目根目录的 `.env`） |

---

## 测试

```bash
cd callmate
python -m pytest -v
```

9 个测试文件，覆盖 advisor / audio_capture / command_handler / dialogue_manager /
mock_stream / presenter / profile_store / transcriber / main。CI 在 ubuntu + Python 3.11 上
每次 push 和 PR 都跑一遍。

CI 里不装 PortAudio，所以 `audio_capture` 对 `sounddevice` 做的是**延迟导入**——
这个改动就是为「没有音频硬件的 CI 环境也能跑测试」而做的。Mock 后端（`MockAdvisor` /
`MockTranscriberBackend` / `MockStreamer`）的存在让绝大部分逻辑不依赖外部服务。

---

## 已知限制

- **真实链路未接线**：这是最大的一个，见上面状态表。
- **只做桌面端**。Android 拿不到通话音频（系统封死，root/刷机不现实），手机端暂不考虑——
  详细取舍写在 `需求文档.md` 与 `决策记录.md`。
- **音频捕获有平台差异**：Linux 走 PulseAudio（`parec` 和 `sounddevice` 两条路都试过，
  见决策记录），Windows 的虚拟音频设备方案还没验证。
- **`profiles.json` 是明文**，且没有加密。它记录的是你的人际关系，请自行评估。
- **建议质量强依赖 profile 填得好不好**。「对方是导师、这次想请两周假」和「对方是导师」
  生成的结果差很远。
- 仓库里 `callmate/README.md` 与本文件内容一致，是为了让 `pip install -e callmate/`
  能拿到 `long_description`，不是漏删的冗余文件。

---

## Roadmap

按优先级：

1. **把真实链路接进 CLI**：加 `--provider openai|anthropic`、`--asr deepgram`，让
   `create_advisor()` / `Transcriber` 的选择来自命令行而不是硬编码 mock
2. **端到端联调**：真实麦克风 → Deepgram 流式 → LLM → 终端，跑通一通真实电话
3. **profile 加密存储**
4. 打包发布到 PyPI（现在 `pip install callmate` 是装不到的）

---

## 文档

- [`需求文档.md`](需求文档.md) — 目标用户、平台策略、按迭代拆解的功能清单
- [`决策记录.md`](决策记录.md) — 为什么选 Desktop 而不是手机、音频怎么抓、ASR 为什么换 V2
- [`迭代计划.md`](迭代计划.md) — 迭代节奏与当前进度

---

## License

[MIT](LICENSE)
