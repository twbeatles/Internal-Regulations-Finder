from regfinder import runtime


def test_get_app_directory_uses_entry_script(monkeypatch, tmp_path):
    script = tmp_path / "run.py"
    script.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.setattr(runtime.sys, "argv", [str(script)])

    assert runtime.get_app_directory() == str(tmp_path)


def test_get_app_directory_falls_back_to_cwd(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.setattr(runtime.sys, "argv", [""], raising=False)
    monkeypatch.setattr(runtime.os, "getcwd", lambda: str(tmp_path))

    assert runtime.get_app_directory() == str(tmp_path)
