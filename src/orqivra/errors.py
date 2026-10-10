"""Project exceptions and public process exit codes."""


class OrqivraError(Exception):
    """A user-facing failure with a stable command-line exit code."""

    exit_code = 2


class ConcurrentUpdateError(OrqivraError):
    """A state file changed or was locked by another writer."""

    exit_code = 3


class UnsafePathError(OrqivraError):
    """A path escapes its selected root or crosses an unsafe symlink."""

    exit_code = 4


class InputOutputError(OrqivraError):
    """A safe local file operation failed."""

    exit_code = 4
