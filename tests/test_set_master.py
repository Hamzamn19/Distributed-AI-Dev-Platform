"""scripts/set_master.py points the workers' env files at a new master."""

from scripts import set_master


def test_every_worker_file_gets_the_new_master_and_the_rest_stays(tmp_path):
    (tmp_path / ".env.for-can").write_text("AGENT_TOKEN=t\nMASTER_URL=http://old:8000\nAGENT_ID=agent-can\n")
    (tmp_path / ".env.worker1").write_text("MASTER_URL=http://localhost:8000\n")
    (tmp_path / ".env.for-baran").write_text("MASTER_PORT=8000\n")  # the master: no MASTER_URL
    (tmp_path / ".env").write_text("MASTER_URL=http://keep:8000\n")
    assert set_master.main(["http://100.1.2.3:8000/"], root=tmp_path) == 0
    assert (tmp_path / ".env.for-can").read_text() == (
        "AGENT_TOKEN=t\nMASTER_URL=http://100.1.2.3:8000\nAGENT_ID=agent-can\n")
    assert (tmp_path / ".env.worker1").read_text() == "MASTER_URL=http://100.1.2.3:8000\n"
    assert (tmp_path / ".env.for-baran").read_text() == "MASTER_PORT=8000\n"
    assert (tmp_path / ".env").read_text() == "MASTER_URL=http://keep:8000\n"


def test_a_wrong_address_changes_nothing(tmp_path):
    (tmp_path / ".env.for-can").write_text("MASTER_URL=http://old:8000\n")
    assert set_master.main(["100.1.2.3"], root=tmp_path) == 1
    assert (tmp_path / ".env.for-can").read_text() == "MASTER_URL=http://old:8000\n"
