"""S2-05: generated files are durable and isolated by project and run."""

from pathlib import Path
import subprocess
import sys

import pytest

from dap.master.db.workspace import save_generated_files
from dap.shared.schemas import GeneratedFile


def test_files_survive_another_process_and_runs_remain_separate(tmp_path):
    root = tmp_path / "workspace"
    original = save_generated_files(
        "project-1", "run-1",
        [GeneratedFile(path="db/schema.sql", content="-- Kitaplar\nCREATE TABLE books (id INTEGER);\n")],
        workspace_root=root,
    )[0]
    newer = save_generated_files(
        "project-1", "run-2", [GeneratedFile(path="db/schema.sql", content="-- New version\n")],
        workspace_root=root,
    )[0]
    other = save_generated_files(
        "project-2", "run-1", [GeneratedFile(path="db/schema.sql", content="-- Other project\n")],
        workspace_root=root,
    )[0]
    assert original == root / "project-1" / "run-1" / "db" / "schema.sql"
    result = subprocess.run(
        [sys.executable, "-c", "from pathlib import Path; import sys; print(Path(sys.argv[1]).read_bytes().hex())", str(original)],
        capture_output=True, text=True, check=True, timeout=15,
    )
    assert bytes.fromhex(result.stdout.strip()).decode("utf-8") == "-- Kitaplar\nCREATE TABLE books (id INTEGER);\n"
    assert newer.read_text("utf-8") == "-- New version\n"
    assert other.read_text("utf-8") == "-- Other project\n"


def test_same_run_accepts_more_tasks_and_identical_retry(tmp_path):
    first = GeneratedFile(path="db/schema.sql", content="-- schema")
    paths = save_generated_files("project-1", "run-1", [first], workspace_root=tmp_path)
    before = paths[0].stat().st_mtime_ns
    assert save_generated_files("project-1", "run-1", [first], workspace_root=tmp_path) == paths
    assert paths[0].stat().st_mtime_ns == before
    second = GeneratedFile(path="backend\\main.py", content="print('hello')")
    save_generated_files("project-1", "run-1", [second], workspace_root=tmp_path)
    assert paths[0].read_text("utf-8") == first.content
    assert (tmp_path / "project-1/run-1/backend/main.py").read_text("utf-8") == second.content


def test_conflict_does_not_overwrite_or_write_part_of_batch(tmp_path):
    original = GeneratedFile(path="schema.sql", content="-- original")
    save_generated_files("project-1", "run-1", [original], workspace_root=tmp_path)
    with pytest.raises(FileExistsError):
        save_generated_files(
            "project-1", "run-1",
            [GeneratedFile(path="new.txt", content="new"), GeneratedFile(path="schema.sql", content="changed")],
            workspace_root=tmp_path,
        )
    assert (tmp_path / "project-1/run-1/schema.sql").read_text("utf-8") == original.content
    assert not (tmp_path / "project-1/run-1/new.txt").exists()


@pytest.mark.parametrize("path", ["../escape.sql", "/absolute.sql", "C:\\escape.sql", "a/../../escape", "schema.sql:stream", "NUL.txt", "folder./file.sql"])
def test_invalid_generated_path_is_rejected_before_any_writes(tmp_path, path):
    root = tmp_path / "workspace"
    with pytest.raises(ValueError):
        save_generated_files(
            "project-1", "run-1",
            [GeneratedFile(path="valid.sql", content="valid"), GeneratedFile(path=path, content="invalid")],
            workspace_root=root,
        )
    assert not root.exists()


@pytest.mark.parametrize("project,run", [("../other", "run-1"), ("project-1", "../other"), ("project-1", "")])
def test_invalid_identifiers_are_rejected(tmp_path, project, run):
    with pytest.raises(ValueError):
        save_generated_files(project, run, [], workspace_root=tmp_path / "workspace")


@pytest.mark.parametrize("paths", [("schema.sql", "SCHEMA.sql"), ("db", "db/schema.sql")])
def test_duplicate_or_overlapping_paths_are_rejected(tmp_path, paths):
    root = tmp_path / "workspace"
    with pytest.raises(ValueError):
        save_generated_files(
            "project-1", "run-1", [GeneratedFile(path=path, content="text") for path in paths],
            workspace_root=root,
        )
    assert not root.exists()


def test_existing_file_cannot_be_used_as_directory(tmp_path):
    directory = tmp_path / "project-1/run-1"
    directory.mkdir(parents=True)
    (directory / "db").write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        save_generated_files(
            "project-1", "run-1", [GeneratedFile(path="db/schema.sql", content="new")],
            workspace_root=tmp_path,
        )
    assert (directory / "db").read_text("utf-8") == "existing"
