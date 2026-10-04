"""Compatibility entrypoint for local plugin installations."""

from get_wechat_history.mcp_server import (
    check_history,
    configure_history,
    decode_conversation_image,
    export_conversation,
    find_conversations,
    mcp,
    read_conversation,
    read_recent_across_chats,
    refresh_history,
    safe_call,
)


if __name__ == "__main__":
    mcp.run(transport="stdio")
