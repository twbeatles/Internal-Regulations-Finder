from pathlib import Path
import zlib

from regfinder.document_extractor import DocumentExtractor


class FakeStream:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload


class FakeOle:
    def __init__(self, streams):
        self._streams = streams

    def listdir(self):
        items = []
        for key in self._streams.keys():
            parts = key.split("/")
            if len(parts) >= 2 and parts[0] == "BodyText" and parts[1].startswith("Section"):
                items.append(parts)
        return items

    def exists(self, name):
        return name in self._streams

    def openstream(self, name):
        return FakeStream(self._streams[name])

    def close(self):
        return None


class FakeHwpModule:
    def __init__(self, fixtures):
        self._fixtures = fixtures

    def OleFileIO(self, path):
        return FakeOle(self._fixtures[Path(path).name])


def _raw_deflate(data):
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(data) + compressor.flush()


def test_extract_hwp_supports_multiple_sections(tmp_path):
    fp = tmp_path / "multi.hwp"
    fp.write_text("x", encoding="utf-8")

    fixtures = {
        "multi.hwp": {
            "BodyText/Section1": "section-1".encode("utf-16"),
            "BodyText/Section0": _raw_deflate("section-0".encode("utf-16")),
        }
    }

    extractor = DocumentExtractor()
    extractor._hwp_module = FakeHwpModule(fixtures)

    content, error = extractor.extract(str(fp))

    assert error is None
    assert "section-0" in content
    assert "section-1" in content
    assert content.index("section-0") < content.index("section-1")


def test_extract_hwp_reports_failure_reason(tmp_path):
    fp = tmp_path / "broken.hwp"
    fp.write_text("x", encoding="utf-8")

    fixtures = {
        "broken.hwp": {
            "BodyText/Section0": b"\x01\x02\x03\x04",
        }
    }

    extractor = DocumentExtractor()
    extractor._hwp_module = FakeHwpModule(fixtures)

    content, error = extractor.extract(str(fp))

    assert content == ""
    assert error is not None
    assert "HWP 텍스트 추출 실패" in error
