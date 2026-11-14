"""公共错误类型与退出码。"""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    USAGE = 2
    PATH_NOT_FOUND = 10
    GAME_INCOMPLETE = 11
    WORKSPACE_ERROR = 12


class ElinToolError(Exception):
    """所有命令错误的基类，exit_code 决定 CLI 退出码。"""

    exit_code = ExitCode.USAGE


class PathNotFoundError(ElinToolError):
    exit_code = ExitCode.PATH_NOT_FOUND


class GameIncompleteError(ElinToolError):
    exit_code = ExitCode.GAME_INCOMPLETE


class WorkspaceError(ElinToolError):
    exit_code = ExitCode.WORKSPACE_ERROR
