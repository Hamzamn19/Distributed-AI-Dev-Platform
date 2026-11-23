"""Template copy tests."""

import pytest

from dap.master.core.project_template import copy_template


def _template(tmp_path):
    template = tmp_path / "templates" / "webapp"
    (template / "backend").mkdir(parents=True)
    (template / "backend" / "main.py").write_text("app = None\n", "utf-8")
    (template / "index.html").write_text("<html></html>\n", "utf-8")
    return template


def test_template_is_copied_directly_under_the_project_id(tmp_path):
    root = tmp_path / "workspace"
    target = copy_template("p-1", _template(tmp_path), root)
    assert target == root / "p-1"
    assert (target / "index.html").read_text("utf-8") == "<html></html>\n"
    assert (target / "backend" / "main.py").is_file()


def test_existing_project_folder_is_not_overwritten(tmp_path):
    template, root = _template(tmp_path), tmp_path / "workspace"
    copy_template("p-1", template, root)
    with pytest.raises(FileExistsError):
        copy_template("p-1", template, root)


def test_missing_template_and_unsafe_id_are_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        copy_template("p-1", tmp_path / "nope", tmp_path / "workspace")
    with pytest.raises(ValueError):
        copy_template("../x", _template(tmp_path), tmp_path / "workspace")
