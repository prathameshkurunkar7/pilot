from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Iterator

from pilot.context import CliContext
from pilot.exceptions import BenchError

_OWN_GROUP_OPTIONS = frozenset(["--verbose", "--yes", "-y", "--bench", "-b", "--help", "-h"])


def strip_bench_flag(args: list[str]) -> tuple[str | None, list[str]]:
    bench_name = None
    remaining = []
    skip_next = False
    for arg in args:
        if skip_next:
            bench_name = arg
            skip_next = False
            continue
        if arg in ("--bench", "-b"):
            skip_next = True
            continue
        if arg.startswith(("--bench=", "-b=")):
            bench_name = arg.split("=", 1)[1]
            continue
        remaining.append(arg)
    return bench_name, remaining


def is_frappe_passthrough(
    args: list[str], own_commands: frozenset[str] | None = None
) -> bool:
    if own_commands is None:
        from pilot.internal.cli_registry import command_names

        own_commands = command_names()

    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("-"):
            if is_own_group_option(arg):
                skip_next = arg in ("--bench", "-b")
                continue
            return True
        return arg not in own_commands
    return False


def is_own_group_option(arg: str) -> bool:
    if arg in _OWN_GROUP_OPTIONS:
        return True
    if "=" not in arg:
        return False
    key = arg.split("=", 1)[0]
    return key in ("--bench", "-b")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    args_list = sys.argv[1:]
    bench_name, remaining = strip_bench_flag(args_list)
    context = build_context(
        bench_name,
        verbose="--verbose" in args_list,
        assume_yes="--yes" in args_list or "-y" in args_list,
    )

    forwarded_args = forwarded_frappe_args(remaining)
    if forwarded_args is not None:
        run_frappe(context, forwarded_args)
    else:
        run_native(context, remaining)


@contextmanager
def error_boundary(context: CliContext) -> Iterator[None]:
    try:
        yield
    except BenchError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        if context.verbose:
            raise
        print(str(error), file=sys.stderr)
        sys.exit(1)


def build_context(bench_name: str | None, verbose: bool, assume_yes: bool) -> CliContext:
    from pilot.loader import cli_root

    return CliContext(
        installation_root=cli_root(),
        bench_name=bench_name,
        verbose=verbose,
        assume_yes=assume_yes,
    )


def forwarded_frappe_args(remaining: list[str]) -> list[str] | None:
    if remaining and remaining[0] == "frappe":
        return remaining[1:]
    if is_frappe_passthrough(remaining):
        return remaining
    return None


def run_frappe(context: CliContext, args: list[str]) -> None:
    from pilot import loader
    from pilot.commands.runtime.frappe import FrappeCommand

    with error_boundary(context):
        FrappeCommand(loader.load_bench(context), args=tuple(args)).run()


def run_native(context: CliContext, remaining: list[str]) -> None:
    import time

    from pilot.internal import cli_registry as registry

    parser = registry.build_parser()
    args = parser.parse_args(remaining)
    started = time.monotonic()
    with error_boundary(context):
        if context.all_benches:
            registry.dispatch_all(args, parser, context)
        else:
            registry.dispatch(args, parser, context)
    report_elapsed(time.monotonic() - started)


def report_elapsed(elapsed: float) -> None:
    if elapsed >= 2:
        minutes, seconds = divmod(int(elapsed), 60)
        print(f"\nDone in {minutes}m {seconds}s" if minutes else f"\nDone in {seconds}s")
