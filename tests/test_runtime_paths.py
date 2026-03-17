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


def test_get_model_cache_dir_name():
    assert runtime.get_model_cache_dir_name("snunlp/KR-SBERT-V40K-klueNLI-augSTS") == (
        "models--snunlp--KR-SBERT-V40K-klueNLI-augSTS"
    )


def test_is_model_downloaded_requires_blobs_and_snapshots(tmp_path):
    model_id = "demo/sample-model"
    model_cache_path = tmp_path / runtime.get_model_cache_dir_name(model_id)
    (model_cache_path / "blobs").mkdir(parents=True)
    (model_cache_path / "snapshots" / "123abc").mkdir(parents=True)

    assert runtime.is_model_downloaded(model_id, models_dir=str(tmp_path)) is False

    blob_file = model_cache_path / "blobs" / "deadbeef"
    blob_file.write_bytes(b"ok")

    assert runtime.is_model_downloaded(model_id, models_dir=str(tmp_path)) is True
