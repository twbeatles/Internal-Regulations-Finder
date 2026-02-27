from pathlib import Path

from regfinder.document_extractor import BaseOCREngine, DocumentExtractor


class FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class FakePdfReader:
    def __init__(self, path):
        name = Path(path).stem
        self.is_encrypted = "enc" in name
        if "image" in name:
            self.pages = [FakePage("")]
        else:
            self.pages = [FakePage("sample text")]

    def decrypt(self, password):
        return 1 if password == "secret" else 0


class DummyOCREngine(BaseOCREngine):
    def extract_pdf_images(self, pdf_path):
        return "ocr text", None


def _make_extractor():
    extractor = DocumentExtractor()
    extractor._pdf_module = FakePdfReader
    return extractor


def test_check_pdf_encrypted(tmp_path):
    fp = tmp_path / "enc.pdf"
    fp.write_text("x", encoding="utf-8")

    extractor = _make_extractor()
    encrypted, error = extractor.check_pdf_encrypted(str(fp))

    assert encrypted is True
    assert error is None


def test_extract_pdf_requires_password(tmp_path):
    fp = tmp_path / "enc.pdf"
    fp.write_text("x", encoding="utf-8")

    extractor = _make_extractor()

    _, error_missing = extractor.extract(str(fp))
    _, error_bad = extractor.extract(str(fp), pdf_password="bad")
    text_ok, error_ok = extractor.extract(str(fp), pdf_password="secret")

    assert "비밀번호 필요" in (error_missing or "")
    assert "비밀번호 불일치" in (error_bad or "")
    assert text_ok == "sample text"
    assert error_ok is None


def test_extract_image_pdf_uses_ocr_hook(tmp_path):
    fp = tmp_path / "image.pdf"
    fp.write_text("x", encoding="utf-8")

    extractor = _make_extractor()

    no_ocr_text, no_ocr_error = extractor.extract(str(fp))
    ocr_text, ocr_error = extractor.extract(str(fp), ocr_engine=DummyOCREngine())

    assert no_ocr_text == ""
    assert "OCR 엔진 미설정" in (no_ocr_error or "")
    assert ocr_text == "ocr text"
    assert ocr_error is None
