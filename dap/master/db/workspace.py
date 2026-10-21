"""S2-05: store generated files under <root>/<project_id>/<run_id>/.

Can selected project/run isolation on 21 October. Master integration is pending:
the caller supplies the workspace root and one run ID shared by all tasks in
that execution. This module does not create runs or execute generated files.

An identical retry is accepted; different content at an existing path is rejected.
All paths and existing contents are checked before writing. An operating-system
write failure may leave partial output; callers must not mark such a run complete.
"""

from pathlib import Path, PureWindowsPath
import re
import stat

from dap.shared.schemas import GeneratedFile


def _identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Project and run IDs must contain only letters, digits, '-' or '_'")
    _relative_path(value)
    return value


def _relative_path(value: str) -> Path:
    windows = PureWindowsPath(value)
    parts = value.replace("\\", "/").split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
    }
    if windows.drive or windows.root or any(
        part in ("", ".", "..")
        or part.endswith((".", " "))
        or part.split(".")[0].upper() in reserved
        or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        for part in parts
    ):
        raise ValueError(f"Generated file path must be a normal relative path: {value!r}")
    return Path(*parts)


def _reject_links(root: Path, relative: Path) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (
            current.exists()
            and getattr(current.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError(f"Generated file path crosses a filesystem link: {relative}")


def save_generated_files(
    project_id: str,
    run_id: str,
    files: list[GeneratedFile],
    *,
    workspace_root: Path,
) -> list[Path]:
    """Save UTF-8 text files and return paths in input order.

    Existing files from this run are retained. Identical content is a no-op;
    conflicting content raises FileExistsError. A new run uses a new directory.
    The caller must serialize writes to a run; this is not a concurrent writer.
    """
    root = Path(workspace_root).resolve()
    run_relative = Path(_identifier(project_id)) / _identifier(run_id)
    _reject_links(root, run_relative)
    run_directory = root / run_relative
    prepared: list[tuple[Path, bytes]] = []
    seen: set[str] = set()
    for file in files:
        relative = _relative_path(file.path)
        key = relative.as_posix().casefold()
        if key in seen:
            raise ValueError(f"Duplicate generated file path: {file.path!r}")
        seen.add(key)
        _reject_links(root, run_relative / relative)
        target = run_directory / relative
        content = file.content.encode("utf-8")
        if target.exists() and (not target.is_file() or target.read_bytes() != content):
            raise FileExistsError(f"Generated file conflicts with existing output: {relative}")
        prepared.append((target, content))

    targets = {path for path, _ in prepared}
    for target, _ in prepared:
        if any(parent in targets for parent in target.parents):
            raise ValueError("A generated file cannot also be another file's directory")
        parent = target.parent
        while parent != root:
            if parent.exists() and not parent.is_dir():
                raise FileExistsError(f"Output directory is an existing file: {parent}")
            parent = parent.parent

    for target, content in prepared:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(content)
    return [path for path, _ in prepared]
