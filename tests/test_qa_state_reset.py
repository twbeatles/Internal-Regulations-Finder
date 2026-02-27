import os

from regfinder.qa_system import RegulationQASystem


def test_reset_runtime_state_clears_all():
    qa = RegulationQASystem()
    qa.vector_store = object()
    qa.embedding_model = object()
    qa.model_id = "model-id"
    qa.documents = ["doc"]
    qa.doc_meta = [{"a": 1}]
    qa.doc_ids = ["doc#0"]
    qa.file_infos["x"] = object()
    qa.current_folder = "C:/tmp"
    qa._vector_id_mode = "doc_id"

    qa.reset_runtime_state(reset_model=True)

    assert qa.vector_store is None
    assert qa.embedding_model is None
    assert qa.model_id is None
    assert qa.documents == []
    assert qa.doc_meta == []
    assert qa.doc_ids == []
    assert qa.file_infos == {}
    assert qa.current_folder == ""
    assert qa._vector_id_mode == "auto"


def test_clear_cache_resets_memory(tmp_path):
    qa = RegulationQASystem()
    qa.cache_path = str(tmp_path / "cache")
    os.makedirs(qa.cache_path, exist_ok=True)
    (tmp_path / "cache" / "dummy.txt").write_text("x", encoding="utf-8")

    qa.vector_store = object()
    qa.documents = ["doc"]
    qa.doc_meta = [{"a": 1}]
    qa.doc_ids = ["doc#0"]

    result = qa.clear_cache(reset_memory=True)

    assert result.success is True
    assert "디스크+메모리" in result.message
    assert not os.path.exists(qa.cache_path)
    assert qa.vector_store is None
    assert qa.documents == []
    assert qa.doc_meta == []
    assert qa.doc_ids == []
