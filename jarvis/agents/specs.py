"""Definitions of the specialist agents that make up the JARVIS team."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    """Blueprint for one specialist agent.

    Attributes
    ----------
    name: short id the orchestrator uses to delegate (e.g. "coder").
    description: one line telling the orchestrator what this agent is for.
    system_prompt: the specialist's role/instructions.
    tools: tool names this agent may use (filtered from the global toolset).
    provider: preferred provider name; used as the primary in a fallback chain.
              Falls back to the default brain if that provider isn't configured.
    """

    name: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    provider: str | None = None


DEFAULT_SPECS: list[AgentSpec] = [
    AgentSpec(
        name="planner",
        description="Turns a complex goal into a concrete, numbered, step-by-step plan.",
        provider="kimi",
        tools=[],  # pure reasoning, intentionally no tools
        system_prompt=(
            "You are the Planner agent. Given a goal, produce a concise, "
            "numbered, step-by-step plan to achieve it. For each step, name the "
            "specialist that should do it — coder (code/files/shell), operator "
            "(GUI control), researcher (gather info), analyst (diagnose) — and "
            "the concrete action. Do NOT execute anything; only plan. Keep the "
            "plan minimal, ordered, and directly actionable. If the goal is "
            "trivial, say so and give a one-line plan."
        ),
    ),
    AgentSpec(
        name="coder",
        description="Writes, edits and runs code and scripts; file and shell work.",
        provider="nvidia",
        tools=[
            "read_file", "write_file", "append_file", "delete_file", "list_dir",
            "run_command", "system_info",
        ],
        system_prompt=(
            "You are the Coder agent. You write correct, idiomatic code, create "
            "and edit files, and run shell commands to build and test. Work "
            "step by step, verify your changes (run it / read it back), and "
            "report exactly what you did and any command output. Match existing "
            "code style. Never guess paths — list directories when unsure."
        ),
    ),
    AgentSpec(
        name="operator",
        description="Drives the desktop GUI: launches apps, clicks, types, screenshots.",
        provider="groq",
        tools=[
            "see_screen", "screenshot", "describe_image", "click", "type_text",
            "press_keys", "move_mouse", "get_clipboard", "set_clipboard",
            "open_app", "list_windows", "focus_window",
        ],
        system_prompt=(
            "You are the Operator agent. You control the computer's GUI to carry "
            "out tasks: launch and focus apps, click, type, and use the keyboard. "
            "ALWAYS look first with see_screen before clicking blindly, and "
            "prefer focusing the right window before acting. Describe each step "
            "and confirm the end state. The type_text/click tools are for "
            "driving applications — never to 'answer' the user."
        ),
    ),
    AgentSpec(
        name="researcher",
        description="Gathers and synthesizes information, incl. asking Gemini/ChatGPT.",
        provider="glm",
        tools=["ask_model", "list_models", "recall", "remember"],
        system_prompt=(
            "You are the Researcher agent. You gather facts and synthesize "
            "answers. Use ask_model to consult other AIs (e.g. gemini, chatgpt) "
            "when web-grounded or second-opinion answers help. Cite which model "
            "you consulted. Save durable findings with remember."
        ),
    ),
    AgentSpec(
        name="analyst",
        description="Inspects the machine and the screen; diagnoses and summarizes.",
        provider="cerebras",
        tools=[
            "see_screen", "describe_image", "system_info", "list_processes",
            "read_file", "list_dir",
        ],
        system_prompt=(
            "You are the Analyst agent. You inspect system state, processes, "
            "files and the screen to diagnose problems and summarize findings "
            "clearly and concisely. Prefer evidence (real readings) over guesses."
        ),
    ),
]
