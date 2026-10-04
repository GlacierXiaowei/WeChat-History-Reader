from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .exporter import HistoryExporter
from .find_all_keys_windows import SCANNER_BUILD_ID
from .local_backend import LocalHistoryBackend, ReaderUnavailableError, RuntimePaths
from .service import HistoryService


paths = RuntimePaths()
service = HistoryService(
    LocalHistoryBackend(paths),
    HistoryExporter(paths.exports),
    state_root=paths.root,
)
mcp = FastMCP(
    "get-wechat-history",
    instructions=(
        "Get WeChat History 2.0. Configure or check only for setup. "
        "For a known contact, group, or chat_id call read_conversation directly. "
        "Use find_conversations only for ambiguous lookup; never use "
        "read_recent_across_chats to locate a known chat. Reads default to compact "
        "AI rows; use records for evidence and create_snapshot for long fixed reads."
    ),
)


def _error_result(
    scope: str,
    status: str,
    error: str,
    *,
    mode: str = "compact",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "scope": scope,
        "error": error,
    }
    if scope in {"conversation", "recent"}:
        result.update({"count": 0, "has_more": False, "next_cursor": ""})
        result["messages" if str(mode).casefold() == "records" else "rows"] = []
    if scope == "find":
        result.update({"conversations": [], "count": 0})
    return result


def safe_call(
    scope: str,
    callback: Callable[[], dict[str, Any]],
    *,
    mode: str = "compact",
) -> dict[str, Any]:
    try:
        return callback()
    except ReaderUnavailableError as exc:
        return _error_result(scope, exc.status, str(exc), mode=mode)
    except Exception as exc:
        return _error_result(scope, "error", str(exc), mode=mode)


@mcp.tool()
def configure_history(db_dir: str = "", discover: bool = False) -> dict[str, Any]:
    """Configure or switch the local WeChat data directory.

    Pass db_dir when known. Use discover=true only when one local discovery is explicitly allowed.
    """
    result = safe_call(
        "configure",
        lambda: service.configure_history(db_dir=db_dir, discover=discover),
    )
    result["scanner_build_id"] = SCANNER_BUILD_ID
    return result


@mcp.tool()
def check_history() -> dict[str, Any]:
    """Diagnose configuration, WeChat process state, keys, and database access."""
    result = safe_call("check", service.check_history)
    result["scanner_build_id"] = SCANNER_BUILD_ID
    return result


@mcp.tool()
def refresh_history() -> dict[str, Any]:
    """Force one local database refresh; success returns only status and refreshed_at."""
    return safe_call("refresh", service.refresh_history)


@mcp.tool()
def find_conversations(
    query: str,
    limit: int = 20,
    chat_kind: str = "any",
    member_count: int | None = None,
    min_member_count: int | None = None,
) -> dict[str, Any]:
    """Find direct or group conversations when the target is ambiguous."""
    return safe_call(
        "find",
        lambda: service.find_conversations(
            query,
            limit=limit,
            chat_kind=chat_kind,
            member_count=member_count,
            min_member_count=min_member_count,
        ),
    )


@mcp.tool()
def read_conversation(
    chat: str | None = None,
    snapshot_id: str = "",
    limit: int = 100,
    cursor: str = "",
    keyword: str = "",
    start_time: str = "",
    end_time: str = "",
    mode: str = "compact",
    include_raw_content: bool = False,
    create_snapshot: bool = False,
    member_count: int | None = None,
    min_member_count: int | None = None,
) -> dict[str, Any]:
    """Read one known conversation directly in compact AI rows, or continue a machine snapshot.

    Use chat for a known person, group, or chat_id. Use snapshot_id only for a prior
    create_snapshot result. chat and snapshot_id are mutually exclusive. compact is
    the default; records is only for evidence or raw content.
    """
    return safe_call(
        "conversation",
        lambda: service.read_conversation(
            chat,
            snapshot_id=snapshot_id,
            limit=limit,
            cursor=cursor,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
            include_raw_content=include_raw_content,
            create_snapshot=create_snapshot,
            member_count=member_count,
            min_member_count=min_member_count,
        ),
        mode=mode,
    )


@mcp.tool()
def read_recent_across_chats(
    limit: int = 100,
    cursor: str = "",
    keyword: str = "",
    start_time: str = "",
    end_time: str = "",
    mode: str = "compact",
    include_raw_content: bool = False,
) -> dict[str, Any]:
    """Read recent messages across chats only; never use this to locate a known chat."""
    return safe_call(
        "recent",
        lambda: service.read_recent_across_chats(
            limit=limit,
            cursor=cursor,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
            include_raw_content=include_raw_content,
        ),
        mode=mode,
    )


@mcp.tool()
def export_conversation(
    chat: str,
    member_count: int | None = None,
    min_member_count: int | None = None,
    start_time: str = "",
    end_time: str = "",
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Export a conversation permanently only when the user explicitly requests it."""
    return safe_call(
        "export",
        lambda: service.export_conversation(
            chat,
            member_count=member_count,
            min_member_count=min_member_count,
            start_time=start_time,
            end_time=end_time,
            output_dir=output_dir,
        ),
    )


@mcp.tool()
def decode_conversation_image(
    chat: str,
    message_id: str,
    output_dir: str | None = None,
    member_count: int | None = None,
    min_member_count: int | None = None,
) -> dict[str, Any]:
    """Decode one image message identified by message_id from a conversation read."""
    return safe_call(
        "image",
        lambda: service.decode_conversation_image(
            chat,
            message_id,
            output_dir=output_dir,
            member_count=member_count,
            min_member_count=min_member_count,
        ),
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
