"""Вызов Claude. С ключом ANTHROPIC_API_KEY — через официальный SDK, без ключа — через локальный Claude Code CLI."""
import os
import shutil
import subprocess

MODEL = os.getenv("LLM_MODEL", "claude-opus-5-5")


def complete(system: str, user: str) -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return _sdk(system, user)
    if shutil.which("claude"):
        return _cli(system, user)
    raise RuntimeError("Нет ANTHROPIC_API_KEY и не найден claude CLI")


def _sdk(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        return "HANDOFF"
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _cli(system: str, user: str) -> str:
    out = subprocess.run(
        ["claude", "-p", "--model", os.getenv("CLI_MODEL", "haiku"), "--system-prompt", system],
        input=user, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "claude CLI завершился с ошибкой")
    return out.stdout.strip()
