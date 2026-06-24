#!/usr/bin/env python3
"""CallMate — real-time call assistant.

Usage:
    callmate --mock                   # Mock mode (type text, no audio)
    callmate --mock --profile 张老师   # Mock mode with specific profile
    callmate --mock-stream            # Stream mock: simulated real-time events
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from callmate.core.dialogue_manager import DialogueManager
from callmate.core.advisor import create_advisor, MockAdvisor
from callmate.core.presenter import Presenter
from callmate.core.command_handler import CommandHandler
from callmate.storage.profile_store import ProfileStore, Profile
from callmate.utils.mock_stream import MockStreamer, demo_conversation


def main():
    args = _parse_args()

    # Init components
    profile_store = ProfileStore()
    dialogue_mgr = DialogueManager()
    advisor = create_advisor("mock")

    # Profile selection
    profile = _select_profile(profile_store, args.profile)

    # Start UI
    presenter = Presenter(profile_name=profile.name if profile else "")
    cmd_handler = _build_command_handler(presenter, dialogue_mgr, profile_store, advisor)
    presenter.start()

    if args.mock_stream:
        presenter.set_status("Mock Stream 模式 — 模拟流式输入")
        print("\n" + "=" * 60, file=sys.stderr)
        print(" CallMate Mock Stream 模式", file=sys.stderr)
        print(" 对方在流式说话，你随时可以打字回复", file=sys.stderr)
        print(" 输入 /help 查看所有命令", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
        _run_mock_stream_loop(presenter, dialogue_mgr, advisor, profile, cmd_handler, profile_store)
    else:
        presenter.set_status("Mock 模式 — 输入对话内容（双方）")
        print("\n" + "=" * 60, file=sys.stderr)
        print(" CallMate Mock 模式", file=sys.stderr)
        print(" 输入对方说的话，CallMate 会给出建议", file=sys.stderr)
        print(" 输入 /help 查看所有命令", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
        _run_mock_loop(presenter, dialogue_mgr, advisor, profile, cmd_handler, profile_store)

    presenter.stop()
    sys.exit(0)


# ---------------------------------------------------------------------------
# Mock loop
# ---------------------------------------------------------------------------

def _run_mock_loop(
    presenter: Presenter,
    dialogue_mgr: DialogueManager,
    advisor: MockAdvisor,
    profile,
    cmd_handler: CommandHandler,
    profile_store: ProfileStore,
):
    """Mock loop: each line typed is something said in the conversation."""
    while True:
        user_input = presenter.get_input()
        if not user_input:
            continue

        cmd = CommandHandler.parse(user_input)
        if cmd:
            if cmd.name in ("quit", "end"):
                _handle_call_end(presenter, dialogue_mgr, profile, profile_store)
                break
            response = cmd_handler.execute(cmd)
            if response:
                for line in response.split("\n"):
                    presenter.add_message("system", line)
            continue

        # Whatever you type is part of the conversation
        dialogue_mgr.add_message("other", user_input)
        presenter.add_message("other", user_input)

        soul, profile_text, transcript = dialogue_mgr.build_prompt(profile)
        suggestions = advisor.advise(soul, profile_text, transcript)
        presenter.update_suggestions(suggestions)


# ---------------------------------------------------------------------------
# End-of-call flow
# ---------------------------------------------------------------------------

def _handle_call_end(
    presenter: Presenter,
    dialogue_mgr: DialogueManager,
    profile,
    profile_store: ProfileStore,
):
    """End-of-call: save history + prompt to create profile if missing."""
    presenter.set_status("通话结束。")

    # Save call history
    answer = input("\n是否保存此次通话记录？(Y/n): ").strip().lower()
    if answer != "n":
        record = {
            "profile": profile.name if profile else "未知",
            "messages": dialogue_mgr.get_history(),
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        print("  通话记录已保存。", file=sys.stderr)

    # Prompt to save profile if not set
    if not profile:
        answer = input("是否为此通话创建对象信息？(Y/n): ").strip().lower()
        if answer != "n":
            name = input("  请为此对象命名（留空=自动命名）: ").strip()
            if not name:
                name = f"未命名_{datetime.now().strftime('%m%d_%H%M')}"
            new_profile = Profile(name=name)
            profile_store.save(new_profile)
            print(f"  对象已保存: {name}", file=sys.stderr)

    presenter.set_status("通话已结束。输入 /quit 退出。")


# ---------------------------------------------------------------------------
# Mock Stream loop (simulated real-time events)
# ---------------------------------------------------------------------------

def _run_mock_stream_loop(
    presenter: Presenter,
    dialogue_mgr: DialogueManager,
    advisor: MockAdvisor,
    profile,
    cmd_handler: CommandHandler,
    profile_store: ProfileStore,
):
    """Stream mock: MockStreamer generates events, user types replies."""
    import threading

    streamer = MockStreamer()
    suggestions_lock = threading.Lock()
    pending_suggestions = None

    def on_utterance_end(text: str, speaker: int):
        nonlocal pending_suggestions
        role = "other" if speaker == 0 else "user"

        # Clear streaming display
        presenter.clear_streaming()

        # Add to dialogue
        dialogue_mgr.add_message(role, text)

        # Update UI
        presenter.add_message(role, text)

        # Trigger advisor only for other person's speech
        if speaker == 0:
            soul, profile_text, transcript = dialogue_mgr.build_prompt(profile)
            suggestions = advisor.advise(soul, profile_text, transcript)
            with suggestions_lock:
                pending_suggestions = suggestions
            presenter.update_suggestions(suggestions)
            presenter.set_status("对方说完了，你可以回复了")
        else:
            presenter.update_suggestions([])

    streamer.on_utterance_end(on_utterance_end)
    streamer.on_results(lambda text, speaker, is_final, speech_final: (
        presenter.show_streaming(text, speaker) if not is_final else None
    ))
    streamer.on_speech_started(lambda speaker: presenter.set_status(
        "对方正在说话…" if speaker == 0 else ""
    ))

    # Start streamer in background
    t = threading.Thread(target=streamer.run, daemon=True)
    t.start()

    # Main loop: user can type replies at any time
    while True:
        user_input = presenter.get_input()
        if not user_input:
            continue

        cmd = CommandHandler.parse(user_input)
        if cmd:
            if cmd.name in ("quit", "end"):
                _handle_call_end(presenter, dialogue_mgr, profile, profile_store)
                break
            response = cmd_handler.execute(cmd)
            if response:
                for line in response.split("\n"):
                    presenter.add_message("system", line)
            continue

        # User typed their own response
        dialogue_mgr.add_message("user", user_input)
        presenter.add_message("user", user_input)


# ---------------------------------------------------------------------------
# Profile selection
# ---------------------------------------------------------------------------

def _select_profile(store: ProfileStore, name: str | None = None) -> Profile | None:
    """Select a profile via CLI arg or interactive prompt."""
    if name:
        profile = store.get(name)
        if profile:
            return profile
        print(f"未找到对象: {name}", file=sys.stderr)
        return None

    profiles = store.list()
    if not profiles:
        return None

    if len(profiles) == 1:
        return store.get(profiles[0])

    print("可选通话对象:", file=sys.stderr)
    for i, p in enumerate(profiles, 1):
        pr = store.get(p)
        info = f" ({pr.relationship})" if pr and pr.relationship else ""
        print(f"  {i}. {p}{info}", file=sys.stderr)
    print("  0. 跳过（无预设信息）", file=sys.stderr)

    try:
        choice = input("选择 (0-{}) [1]: ".format(len(profiles))).strip()
        if not choice:
            choice = "1"
        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(profiles):
            return store.get(profiles[idx - 1])
    except (ValueError, EOFError):
        pass
    return None


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

def _build_command_handler(
    presenter, dialogue_mgr, profile_store, advisor
) -> CommandHandler:
    _current_profile_name = [""]

    def on_refresh():
        soul, profile_text, transcript = dialogue_mgr.build_prompt()
        suggestions = advisor.advise(soul, profile_text, transcript)
        presenter.update_suggestions(suggestions)

    def on_profile_switch(name: str) -> str:
        profile = profile_store.get(name)
        if not profile:
            # Profile doesn't exist — offer to create
            answer = input(f"  对象 '{name}' 不存在。是否创建？(Y/n): ").strip().lower()
            if answer != "n":
                rel = input("  关系（如：导师/同事/朋友，留空跳过）: ").strip()
                new_profile = Profile(name=name, relationship=rel)
                profile_store.save(new_profile)
                _current_profile_name[0] = name
                return f"对象已创建并切换到: {name}"
            return f"未找到对象: {name}"
        _current_profile_name[0] = name
        return f"已切换到: {name}"

    return CommandHandler(
        on_quit=lambda: None,
        on_refresh=on_refresh,
        on_profile_switch=on_profile_switch,
        on_note=lambda text: None,
        get_profile_list=profile_store.list,
        get_current_profile=lambda: _current_profile_name[0],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CallMate — real-time call assistant")
    parser.add_argument("--mock", action="store_true", help="Mock mode (type text, no audio)")
    parser.add_argument("--mock-stream", action="store_true", help="Stream mock (simulated real-time events)")
    parser.add_argument("--profile", type=str, help="Profile name to use")
    return parser.parse_args()


if __name__ == "__main__":
    main()
