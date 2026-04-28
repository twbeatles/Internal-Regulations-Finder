import zipfile

from regfinder.document_extractor import BaseOCREngine, DocumentExtractor, TesseractOCREngine


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


def test_extract_pdf_segments_keep_page_metadata(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    extractor = DocumentExtractor(pdf_reader_factory=_FakePdfReader)
    segments, error = extractor.extract_segments(str(pdf_path))

    assert error is None
    assert segments[0].text == "기존 텍스트"
    assert segments[0].page_start == 1
    assert segments[0].page_end == 1


def test_extract_hwpx_reads_xml_text(tmp_path):
    hwpx_path = tmp_path / "sample.hwpx"
    with zipfile.ZipFile(hwpx_path, "w") as zf:
        zf.writestr(
            "Contents/section0.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <section><p><run><t>휴가 규정</t></run></p><p><run><t>본문 내용</t></run></p></section>
            """,
        )

    extractor = DocumentExtractor()
    text, error = extractor.extract(str(hwpx_path))

    assert error is None
    assert "휴가 규정" in text
    assert "본문 내용" in text


def test_tesseract_ocr_reports_missing_optional_dependencies(monkeypatch, tmp_path):
    pdf_path = tmp_path / "image.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_import_module(name: str):
        raise ImportError(f"missing {name}")

    monkeypatch.setattr("regfinder.document_extractor._import_module", fake_import_module)
    text, error = TesseractOCREngine().extract_pdf_images(str(pdf_path))

    assert text == ""
    assert "의존성 없음" in (error or "")
