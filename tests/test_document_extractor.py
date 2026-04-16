from regfinder.document_extractor import BaseOCREngine, DocumentExtractor


class _FakePdfPage:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class _FakePdfReader:
    def __init__(self, path: str) -> None:
        self.is_encrypted = False
        self.pages = [
            _FakePdfPage("기존 텍스트"),
            _FakePdfPage(""),
            _FakePdfPage(None),
        ]

    def decrypt(self, password: str):
        return True


class _FakeOCREngine(BaseOCREngine):
    def extract_pdf_images(self, pdf_path: str):
        return "OCR로 추출된 추가 텍스트", None


def test_extract_pdf_appends_ocr_text_for_mixed_pdf_pages(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    extractor = DocumentExtractor(pdf_reader_factory=_FakePdfReader)

    text, error = extractor.extract(
        str(pdf_path),
        ocr_engine=_FakeOCREngine(),
        ocr_options={"mixed_pdf": True},
    )

    assert error is None
    assert "기존 텍스트" in text
    assert "OCR로 추출된 추가 텍스트" in text
