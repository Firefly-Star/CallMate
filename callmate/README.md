# CallMate — 实时通话辅助 AI

> 帮 i 人轻松打电话的工具 (´･ω･`)ﾉ

[![CI](https://github.com/Firefly-Star/CallMate/actions/workflows/test.yml/badge.svg)](https://github.com/Firefly-Star/CallMate/actions/workflows/test.yml)

## 这是什么？

一个实时监听通话内容，帮你分析和建议「接下来该说什么」的 AI 助手。

你只需要事先告诉它：
- 通话对象是谁
- 你和对方的关系（朋友？导师？同事？甲方？）
- 这次通话的目的是什么

然后它就会在通话中：
1. 实时转写对方说的话
2. 结合关系背景和对话历史，推理出最适合你的回应
3. 通过终端界面悄悄告诉你怎么接话

## 为什么做这个？

因为打电话是很难的，尤其是对于 i 人来说。

- 实时对话没有「撤回」按钮
- 你不知道对方的话是什么意思、该怎么接
- 通话结束后总后悔「刚才应该那样说就好了」

CallMate 就是你的通话 copilot。

## 快速开始

### 安装

```bash
pip install callmate
```

### 使用

```bash
# 设置 API 密钥
cp .env.template .env
# 编辑 .env 填入你的 Deepgram 和 LLM API 密钥

# 启动 CallMate
callmate
```

> 🚧 MVP 开发中，完整使用说明待补充。

## 开发

### 环境搭建

```bash
conda env create -f environment.yml
conda activate callmate
pip install -e .
```

### 运行测试

```bash
pytest -v
```

## 技术栈

- Python 3.11+
- Deepgram API（实时语音转写）
- Claude Haiku / GPT-4o mini（对话推理）
- PulseAudio / pulsectl（音频捕获）
- 终端 UI

## 许可证

MIT
