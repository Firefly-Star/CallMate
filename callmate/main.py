#!/usr/bin/env python3
"""CallMate — real-time call assistant.

Usage:
    callmate                          # Normal mode (req. audio + API keys)
    callmate --mock                   # Mock mode (type what the other person says)
    callmate --mock --profile 张老师   # Mock mode with specific profile
"""

from __future__ import annotations

import argparse
import sys

from callmate.core.dialogue_manager import DialogueManager
from callmate.core.advisor import create_advisor, MockAdvisor
from callmate.core.presenter import Presenter
from callmate.core.command_handler import CommandHandler
from callmate.storage.profile_store import ProfileStore, Profile


def main():
    args = _parse_args()

    # Init components
    profile_store = ProfileStore()
    dialogue_mgr = DialogueManager()
    advisor = create_advisor("mock")  # always mock for now
    presenter = Presenter()
    cmd_handler = _build_command_handler(presenter, dialogue_mgr, profile_store, advisor)

    # Profile selection
    profile = _select_profile(profile_store, args.profile)

    # Prepare session
    soul, profile_text, transcript = dialogue_mgr.build_prompt(profile)
    presenter = Presenter(profile_name=profile.name if profile else "")

    # Start UI
    presenter.start()
    presenter.set_status("Mock 模式 — 输入对方说的话开始通话")

    print("\n" + "=" * 60, file=sys.stderr)
    print(" CallMate Mock 模式", file=sys.stderr)
    print(" 输入对方说的话，CallMate 会给出建议", file=sys.stderr)
    print(" 输入 /help 查看所有命令", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)

    _run_mock_loop(presenter, dialogue_mgr, advisor, profile, cmd_handler)

    # Cleanup
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
):
    """Main mock loop: type what the other person says, then type your reply."""
    should_exit = False
    expecting_reply = False

    while not should_exit:
        user_input = presenter.get_input()

        if not user_input:
            continue

        # Check for slash command
        cmd = CommandHandler.parse(user_input)
        if cmd:
            if cmd.name == "quit":
                should_exit = True
                cmd_handler.execute(cmd)
                break
            response = cmd_handler.execute(cmd)
            if response:
                # Show multi-line output (like /help) in history
                for line in response.split("\n"):
                    presenter.add_message("system", line)
            continue

        if expecting_reply:
            # User is typing their own response
            presenter.add_message("user", user_input)
            dialogue_mgr.add_message("user", user_input)
            expecting_reply = False
            presenter.set_status("")
        else:
            # User is typing what the other person said
            presenter.add_message("other", user_input)
            dialogue_mgr.add_message("other", user_input)

            # Get suggestions from advisor
            soul, profile_text, transcript = dialogue_mgr.build_prompt(profile)
            suggestions = advisor.advise(soul, profile_text, transcript)
            presenter.update_suggestions(suggestions)
            expecting_reply = True
            presenter.set_status("输入你的回复，或输入对方说的话继续")


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
        profile = store.get(p)
        info = f"{profile.relationship}" if profile and profile.relationship else ""
        print(f"  {i}. {p} {info}", file=sys.stderr)
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

def _build_command_handler(presenter, dialogue_mgr, profile_store, advisor):
    _current_profile_name = [""]

    def on_quit():
        pass  # handled in main loop

    def on_refresh():
        soul, profile_text, transcript = dialogue_mgr.build_prompt()
        suggestions = advisor.advise(soul, profile_text, transcript)
        presenter.update_suggestions(suggestions)

    def on_profile_switch(name: str) -> str:
        profile = profile_store.get(name)
        if not profile:
            return f"未找到对象: {name}"
        _current_profile_name[0] = name
        return f"已切换到: {name}"

    def get_current_profile() -> str:
        return _current_profile_name[0]

    return CommandHandler(
        on_quit=on_quit,
        on_refresh=on_refresh,
        on_profile_switch=on_profile_switch,
        on_note=lambda text: None,
        get_profile_list=profile_store.list,
        get_current_profile=get_current_profile,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CallMate — real-time call assistant")
    parser.add_argument("--mock", action="store_true", help="Mock mode (type text, no audio)")
    parser.add_argument("--profile", type=str, help="Profile name to use")
    return parser.parse_args()


if __name__ == "__main__":
    main()
