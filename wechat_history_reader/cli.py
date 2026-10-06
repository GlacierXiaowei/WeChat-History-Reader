from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from .runtime_doctor import RuntimeDoctor


class CliUsageError(ValueError):
    pass


def create_service(state_root: Any = None) -> Any:
    from .application import create_service as factory

    return factory(state_root)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def _error_result(
    scope: str,
    status: str,
    error: str,
    *,
    mode: str = "compact",
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "scope": scope, "error": error}
    if scope in {"conversation", "recent"}:
        result.update({"count": 0, "has_more": False, "next_cursor": ""})
        result["messages" if mode.casefold() == "records" else "rows"] = []
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
    except Exception as exc:
        status = getattr(exc, "status", None)
        return _error_result(scope, status or "error", str(exc), mode=mode)


def _add_common_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--cursor", default="")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--start-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--mode", choices=("compact", "records"), default="compact")
    parser.add_argument("--include-raw-content", action="store_true")


def _add_refresh(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--refresh", dest="refresh", action="store_true")
    group.add_argument("--no-refresh", dest="refresh", action="store_false")
    parser.set_defaults(refresh=True)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="wechat-history-reader")
    parser.add_argument("--state-root", default=None)
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=JsonArgumentParser,
    )

    doctor = commands.add_parser("doctor")
    doctor.add_argument("--repair", action="store_true")

    configure = commands.add_parser("configure-history")
    configure.add_argument("--db-dir", default="")
    configure.add_argument("--discover", action="store_true")

    commands.add_parser("refresh-history")

    find = commands.add_parser("find-conversations")
    find.add_argument("--query", required=True)
    find.add_argument("--limit", type=int, default=20)
    find.add_argument("--chat-kind", choices=("any", "direct", "group"), default="any")
    find.add_argument("--member-count", type=int, default=None)
    find.add_argument("--min-member-count", type=int, default=None)

    read = commands.add_parser("read-conversation")
    read.add_argument("--chat", default=None)
    read.add_argument("--snapshot-id", default="")
    read.add_argument("--create-snapshot", action="store_true")
    read.add_argument("--member-count", type=int, default=None)
    read.add_argument("--min-member-count", type=int, default=None)
    _add_common_filters(read)
    _add_refresh(read)

    recent = commands.add_parser("read-recent")
    _add_common_filters(recent)

    export = commands.add_parser("export-conversation")
    export.add_argument("--chat", required=True)
    export.add_argument("--member-count", type=int, default=None)
    export.add_argument("--min-member-count", type=int, default=None)
    export.add_argument("--start-time", default="")
    export.add_argument("--end-time", default="")
    export.add_argument("--output-dir", default=None)
    _add_refresh(export)

    image = commands.add_parser("decode-image")
    image.add_argument("--chat", required=True)
    image.add_argument("--message-id", required=True)
    image.add_argument("--output-dir", default=None)
    image.add_argument("--member-count", type=int, default=None)
    image.add_argument("--min-member-count", type=int, default=None)
    return parser


def _dispatch(arguments: argparse.Namespace, service: Any) -> dict[str, Any]:
    command = arguments.command
    if command == "doctor":
        doctor = RuntimeDoctor(backend=service.backend, state_root=service.state_root)
        return doctor.repair(arguments.state_root) if arguments.repair else doctor.check(arguments.state_root)
    if command == "configure-history":
        return safe_call(
            "configure",
            lambda: service.configure_history(
                db_dir=arguments.db_dir,
                discover=arguments.discover,
            ),
        )
    if command == "refresh-history":
        return safe_call("refresh", service.refresh_history)
    if command == "find-conversations":
        return safe_call(
            "find",
            lambda: service.find_conversations(
                query=arguments.query,
                limit=arguments.limit,
                chat_kind=arguments.chat_kind,
                member_count=arguments.member_count,
                min_member_count=arguments.min_member_count,
            ),
        )
    if command == "read-conversation":
        return safe_call(
            "conversation",
            lambda: service.read_conversation(
                chat=arguments.chat,
                snapshot_id=arguments.snapshot_id,
                limit=arguments.limit,
                cursor=arguments.cursor,
                keyword=arguments.keyword,
                start_time=arguments.start_time,
                end_time=arguments.end_time,
                mode=arguments.mode,
                include_raw_content=arguments.include_raw_content,
                create_snapshot=arguments.create_snapshot,
                member_count=arguments.member_count,
                min_member_count=arguments.min_member_count,
                refresh=arguments.refresh,
            ),
            mode=arguments.mode,
        )
    if command == "read-recent":
        return safe_call(
            "recent",
            lambda: service.read_recent_across_chats(
                limit=arguments.limit,
                cursor=arguments.cursor,
                keyword=arguments.keyword,
                start_time=arguments.start_time,
                end_time=arguments.end_time,
                mode=arguments.mode,
                include_raw_content=arguments.include_raw_content,
            ),
            mode=arguments.mode,
        )
    if command == "export-conversation":
        return safe_call(
            "export",
            lambda: service.export_conversation(
                chat=arguments.chat,
                member_count=arguments.member_count,
                min_member_count=arguments.min_member_count,
                start_time=arguments.start_time,
                end_time=arguments.end_time,
                output_dir=arguments.output_dir,
                refresh=arguments.refresh,
            ),
        )
    if command == "decode-image":
        return safe_call(
            "image",
            lambda: service.decode_conversation_image(
                chat=arguments.chat,
                message_id=arguments.message_id,
                output_dir=arguments.output_dir,
                member_count=arguments.member_count,
                min_member_count=arguments.min_member_count,
            ),
        )
    raise CliUsageError(f"unknown command: {command}")


def main(argv: list[str] | None = None, *, service: Any = None) -> int:
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
        if arguments.command == "doctor":
            if service is None:
                try:
                    service = create_service(arguments.state_root)
                except Exception:
                    service = type(
                        "RuntimeOnlyService",
                        (),
                        {"backend": None, "state_root": arguments.state_root},
                    )()
        elif service is None:
            service = create_service(arguments.state_root)
        result = _dispatch(arguments, service)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0 if result.get("status") not in {"error", "python_missing", "python_unsupported"} else 1
    except CliUsageError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
