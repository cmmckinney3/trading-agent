import json
import os
from pathlib import Path

from utils.llm import chat_completions_create

CODE_AGENT_SYSTEM_PROMPT = """You are an expert software engineer acting as an autonomous code editing agent.

You will be given a codebase path and a task. Use your tools to explore, read, and edit files.

Rules:
- Always read a file before writing it (unless creating from scratch)
- Make minimal, focused changes — don't refactor things unrelated to the task
- Match existing code style, naming conventions, and patterns
- After writing a file, re-read it to verify it looks correct
- Only touch files relevant to the task
- When finished, call mark_complete with a clear summary of every file changed and why

For open-ended quality improvement:
- Scan the codebase first to understand the structure
- Look for: duplicated logic, inconsistent error handling, unclear naming, dead code, missing validation
- Fix issues one file at a time, verify each change before moving on
- Stop when you've made meaningful improvements — don't over-engineer

Never guess at file contents. Always read before editing."""

CODE_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory. Uses glob patterns. Returns paths relative to the codebase root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to list, relative to codebase root. Use '.' for the root.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter results (e.g. '**/*.py', '*.js'). Defaults to '**/*' (all files, recursive).",
                    },
                },
                "required": ["directory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the codebase root.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates it if it doesn't exist, overwrites if it does. Always read first before overwriting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the codebase root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_complete",
            "description": "Call this when the task is fully complete. Summarize every file changed and what was done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of all changes made — which files, what changed, and why.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]


def _safe_path(codebase_path: str, relative_path: str) -> Path | None:
    base = Path(codebase_path).resolve()
    target = (base / relative_path).resolve()
    try:
        target.relative_to(base)
        return target
    except ValueError:
        return None


def _execute_code_tool(name: str, args: dict, codebase_path: str) -> dict:
    if name == "list_files":
        directory = args.get("directory", ".")
        pattern = args.get("pattern", "**/*")
        dir_path = _safe_path(codebase_path, directory)
        if not dir_path:
            return {"error": "Path escapes codebase root"}
        if not dir_path.exists():
            return {"error": f"Directory not found: {directory}"}
        matches = list(dir_path.glob(pattern))
        base = Path(codebase_path).resolve()
        rel_paths = sorted(
            str(m.relative_to(base)).replace("\\", "/")
            for m in matches
            if m.is_file()
        )
        return {"files": rel_paths[:150], "total": len(rel_paths)}

    if name == "read_file":
        path = _safe_path(codebase_path, args["path"])
        if not path:
            return {"error": "Path escapes codebase root"}
        if not path.exists():
            return {"error": f"File not found: {args['path']}"}
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > 60000:
                content = content[:60000] + "\n\n[... truncated ...]"
            return {"content": content, "lines": content.count("\n") + 1}
        except Exception as e:
            return {"error": str(e)}

    if name == "write_file":
        path = _safe_path(codebase_path, args["path"])
        if not path:
            return {"error": "Path escapes codebase root"}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return {"success": True, "path": args["path"]}
        except Exception as e:
            return {"error": str(e)}

    if name == "mark_complete":
        return {"done": True, "summary": args.get("summary", "")}

    return {"error": f"Unknown tool: {name}"}


def _llm_kwargs(ai_config: dict) -> dict:
    return {
        "model": ai_config["model"],
        "api_key": ai_config.get("api_key") or None,
        "base_url": ai_config.get("base_url") or None,
    }


def run_code_agent(goal: str, codebase_path: str, ai_config: dict, max_rounds: int = 20):
    """Generator — yields log event dicts as the agent works."""
    if not os.path.isdir(codebase_path):
        yield {"type": "error", "message": f"Directory not found: {codebase_path}"}
        return

    messages = [
        {"role": "system", "content": CODE_AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Codebase path: {codebase_path}\n\n"
                f"Task: {goal}\n\n"
                "Start by exploring the codebase structure, then proceed with the task."
            ),
        },
    ]

    changed_files: list[str] = []

    for round_num in range(1, max_rounds + 1):
        yield {"type": "round", "round": round_num, "max": max_rounds}

        try:
            response = chat_completions_create(
                messages=messages,
                temperature=0.2,
                tools=CODE_AGENT_TOOLS,
                **_llm_kwargs(ai_config),
            )
        except Exception as e:
            yield {"type": "error", "message": f"LLM error: {e}"}
            return

        if response.get("content"):
            yield {"type": "thought", "content": response["content"]}

        if not response.get("tool_calls"):
            yield {
                "type": "done",
                "summary": response.get("content", "Agent finished without calling mark_complete."),
                "changed_files": changed_files,
            }
            return

        messages.append({
            "role": "assistant",
            "content": response.get("content") or None,
            "tool_calls": response["tool_calls_raw"],
        })

        for tc in response["tool_calls"]:
            args = json.loads(tc["arguments"])
            yield {"type": "tool_call", "name": tc["name"], "args": args}

            result = _execute_code_tool(tc["name"], args, codebase_path)

            if tc["name"] == "write_file" and result.get("success"):
                p = args["path"]
                if p not in changed_files:
                    changed_files.append(p)

            if tc["name"] == "mark_complete":
                yield {
                    "type": "done",
                    "summary": args.get("summary", ""),
                    "changed_files": changed_files,
                }
                return

            yield {"type": "tool_result", "name": tc["name"], "result": result}

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, default=str),
            })

    yield {
        "type": "max_rounds",
        "message": f"Reached the maximum of {max_rounds} rounds.",
        "changed_files": changed_files,
    }
