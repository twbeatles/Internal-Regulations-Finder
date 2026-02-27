from regfinder.qa_system import RegulationQASystem


def test_build_bm25_sets_none_when_docs_empty():
    qa = RegulationQASystem()

    qa.documents = ["alpha beta"]
    qa._build_bm25()
    assert qa.bm25 is not None

    qa.documents = []
    qa._build_bm25()
    assert qa.bm25 is None
