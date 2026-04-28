# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Sequence, Tuple, cast

from ..core.file_utils import FileUtils
from ..core.runtime import _import_attr, _import_module


@dataclass(frozen=True)
class DocumentSegment:
    text: str
    page_start: int | None = None
    page_end: int | None = None


class BaseOCREngine:
    """PDF 이미지 OCR 확장 포인트."""

    def extract_pdf_images(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        raise NotImplementedError


class NoOpOCREngine(BaseOCREngine):
    """OCR 미연결 기본 구현."""

    def extract_pdf_images(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        return "", "OCR 엔진 미설정"


class TesseractOCREngine(BaseOCREngine):
    """선택형 Tesseract OCR 엔진."""

    def __init__(self, *, tesseract_cmd: str = "", languages: str = "kor+eng", dpi: int = 200) -> None:
        self.tesseract_cmd = str(tesseract_cmd or "").strip()
        self.languages = str(languages or "kor+eng").strip() or "kor+eng"
        self.dpi = max(72, int(dpi or 200))

    def extract_pdf_images(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        try:
            fitz = cast(Any, _import_module("fitz"))
            pytesseract = cast(Any, _import_module("pytesseract"))
            image_open = cast(Any, _import_attr("PIL.Image", "open"))
        except ImportError as e:
            return "", f"Tesseract OCR 의존성 없음: {e}"

        try:
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            doc = fitz.open(pdf_path)
        except Exception as e:
            return "", f"OCR PDF 열기 실패: {e}"

        texts: List[str] = []
        try:
            scale = self.dpi / 72.0
            matrix = fitz.Matrix(scale, scale)
            for page_index in range(len(doc)):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                image = image_open(io.BytesIO(pix.tobytes("png")))
                page_text = pytesseract.image_to_string(image, lang=self.languages)
                if page_text and page_text.strip():
                    texts.append(page_text.strip())
        except Exception as e:
            return "", f"Tesseract OCR 오류: {e}"
        finally:
            try:
                doc.close()
            except Exception:
                pass

        if texts:
            return "\n\n".join(texts), None
        return "", "Tesseract OCR 결과 없음"


class DocxParagraph(Protocol):
    text: str


class DocxCell(Protocol):
    text: str


class DocxRow(Protocol):
    cells: Sequence[DocxCell]


class DocxTable(Protocol):
    rows: Sequence[DocxRow]


class DocxDocument(Protocol):
    paragraphs: Sequence[DocxParagraph]
    tables: Sequence[DocxTable]


class DocxFactory(Protocol):
    def __call__(self, path: str) -> DocxDocument: ...


class PdfPage(Protocol):
    def extract_text(self) -> Optional[str]: ...


class PdfReaderLike(Protocol):
    is_encrypted: bool

    @property
    def pages(self) -> Sequence[PdfPage]: ...

    def decrypt(self, password: str) -> Any: ...


class PdfReaderFactory(Protocol):
    def __call__(self, path: str) -> PdfReaderLike: ...


class OleStream(Protocol):
    def read(self) -> bytes: ...


class OleLike(Protocol):
    def listdir(self) -> Sequence[Sequence[str]]: ...

    def exists(self, name: str) -> bool: ...

    def openstream(self, name: str) -> OleStream: ...

    def close(self) -> None: ...


class HwpModule(Protocol):
    def OleFileIO(self, path: str) -> OleLike: ...


class DocumentExtractor:
    def __init__(
        self,
        *,
        docx_factory: Optional[DocxFactory] = None,
        pdf_reader_factory: Optional[PdfReaderFactory] = None,
        hwp_module: Optional[HwpModule] = None,
    ):
        self._docx_factory = docx_factory
        self._pdf_reader_factory = pdf_reader_factory
        self._hwp_module = hwp_module
        self._docx_import_attempted = docx_factory is not None
        self._pdf_import_attempted = pdf_reader_factory is not None
        self._hwp_import_attempted = hwp_module is not None

    @property
    def docx(self) -> Optional[DocxFactory]:
        if not self._docx_import_attempted:
            self._docx_import_attempted = True
            try:
                self._docx_factory = cast(DocxFactory, _import_attr("docx", "Document"))
            except ImportError:
                self._docx_factory = None
        return self._docx_factory

    @property
    def pdf(self) -> Optional[PdfReaderFactory]:
        if not self._pdf_import_attempted:
            self._pdf_import_attempted = True
            try:
                self._pdf_reader_factory = cast(PdfReaderFactory, _import_attr("pypdf", "PdfReader"))
            except ImportError:
                self._pdf_reader_factory = None
        return self._pdf_reader_factory

    def check_pdf_encrypted(self, path: str) -> Tuple[bool, Optional[str]]:
        """PDF 암호화 여부 확인."""
        pdf_reader_factory = self.pdf
        if pdf_reader_factory is None:
            return False, "PDF 라이브러리 없음"
        try:
            reader = pdf_reader_factory(path)
            return bool(getattr(reader, "is_encrypted", False)), None
        except Exception as e:
            return False, f"PDF 검사 오류: {e}"

    def extract(
        self,
        path: str,
        pdf_password: Optional[str] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        ocr_options: Optional[dict[str, Any]] = None,
    ) -> Tuple[str, Optional[str]]:
        segments, error = self.extract_segments(
            path,
            pdf_password=pdf_password,
            ocr_engine=ocr_engine,
            ocr_options=ocr_options,
        )
        if error:
            return "", error
        return "\n\n".join(segment.text for segment in segments if segment.text.strip()), None

    def extract_segments(
        self,
        path: str,
        pdf_password: Optional[str] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        ocr_options: Optional[dict[str, Any]] = None,
    ) -> Tuple[List[DocumentSegment], Optional[str]]:
        if not path or not os.path.exists(path):
            return [], f"파일 없음: {path}"
        if not os.path.isfile(path):
            return [], f"파일이 아님: {path}"
        ext = os.path.splitext(path)[1].lower()
        if ext == ".txt":
            return self._segments_from_text_result(self._extract_txt(path))
        if ext == ".docx":
            return self._segments_from_text_result(self._extract_docx(path))
        if ext == ".pdf":
            return self._extract_pdf_segments(
                path,
                pdf_password=pdf_password,
                ocr_engine=ocr_engine,
                ocr_options=ocr_options,
            )
        if ext == ".hwp":
            return self._segments_from_text_result(self._extract_hwp(path))
        if ext == ".hwpx":
            return self._segments_from_text_result(self._extract_hwpx(path))
        return [], f"지원하지 않는 형식: {ext}"

    def _segments_from_text_result(self, result: Tuple[str, Optional[str]]) -> Tuple[List[DocumentSegment], Optional[str]]:
        text, error = result
        if error:
            return [], error
        cleaned = text.strip()
        if not cleaned:
            return [], None
        return [DocumentSegment(cleaned)], None

    def _extract_txt(self, path: str) -> Tuple[str, Optional[str]]:
        return FileUtils.safe_read(path)

    def _extract_docx(self, path: str) -> Tuple[str, Optional[str]]:
        docx_factory = self.docx
        if docx_factory is None:
            return "", "DOCX 라이브러리 없음"
        try:
            doc = docx_factory(path)
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))
            return "\n\n".join(parts), None
        except Exception as e:
            return "", f"DOCX 오류: {e}"

    def _try_pdf_decrypt(self, reader: PdfReaderLike, password: str) -> bool:
        try:
            result = reader.decrypt(password)
            if isinstance(result, bool):
                return result
            if isinstance(result, int):
                return result != 0
            return True
        except Exception:
            return False

    def _extract_pdf(
        self,
        path: str,
        pdf_password: Optional[str] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        ocr_options: Optional[dict[str, Any]] = None,
    ) -> Tuple[str, Optional[str]]:
        segments, error = self._extract_pdf_segments(
            path,
            pdf_password=pdf_password,
            ocr_engine=ocr_engine,
            ocr_options=ocr_options,
        )
        if error:
            return "", error
        return "\n\n".join(segment.text for segment in segments if segment.text.strip()), None

    def _extract_pdf_segments(
        self,
        path: str,
        pdf_password: Optional[str] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        ocr_options: Optional[dict[str, Any]] = None,
    ) -> Tuple[List[DocumentSegment], Optional[str]]:
        pdf_reader_factory = self.pdf
        if pdf_reader_factory is None:
            return [], "PDF 라이브러리 없음"
        try:
            reader = pdf_reader_factory(path)
            if reader.is_encrypted:
                if pdf_password:
                    if not self._try_pdf_decrypt(reader, pdf_password):
                        return [], "암호화된 PDF (비밀번호 불일치)"
                elif not self._try_pdf_decrypt(reader, ""):
                    return [], "암호화된 PDF (비밀번호 필요)"

            segments: List[DocumentSegment] = []
            has_empty_page = False
            for page_number, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        segments.append(DocumentSegment(text.strip(), page_number, page_number))
                    else:
                        has_empty_page = True
                except Exception:
                    has_empty_page = True
                    continue

            engine = ocr_engine or NoOpOCREngine()
            if not segments:
                try:
                    ocr_text, ocr_error = engine.extract_pdf_images(path)
                    if ocr_text and ocr_text.strip():
                        return [DocumentSegment(ocr_text.strip())], None
                    if ocr_error:
                        return [], f"텍스트 없음 (이미지 PDF, {ocr_error})"
                except Exception as e:
                    return [], f"텍스트 없음 (이미지 PDF, OCR 오류: {e})"
                return [], "텍스트 없음 (이미지 PDF)"

            if has_empty_page and isinstance(ocr_options, dict) and bool(ocr_options.get("mixed_pdf", False)):
                try:
                    ocr_text, _ = engine.extract_pdf_images(path)
                except Exception:
                    ocr_text = ""
                if ocr_text and ocr_text.strip():
                    merged_text = "\n\n".join(segment.text for segment in segments)
                    compact_existing = re.sub(r"\s+", "", merged_text)
                    compact_ocr = re.sub(r"\s+", "", ocr_text.strip())
                    if compact_ocr and compact_ocr not in compact_existing:
                        segments.append(DocumentSegment(ocr_text.strip()))

            return segments, None
        except Exception as e:
            return [], f"PDF 오류: {e}"

    @property
    def hwp(self) -> Optional[HwpModule]:
        """HWP 파일 처리를 위한 olefile 모듈 로드"""
        if not self._hwp_import_attempted:
            self._hwp_import_attempted = True
            try:
                self._hwp_module = cast(HwpModule, _import_module("olefile"))
            except ImportError:
                self._hwp_module = None
        return self._hwp_module

    def _extract_hwp(self, path: str) -> Tuple[str, Optional[str]]:
        """HWP 파일에서 텍스트 추출 (olefile 사용)"""
        hwp_module = self.hwp
        if hwp_module is None:
            return "", "HWP 라이브러리 없음 (pip install olefile)"

        ole: Optional[OleLike] = None
        try:
            ole = hwp_module.OleFileIO(path)
            section_texts, section_error = self._extract_hwp_sections(ole)
            if section_texts:
                return "\n\n".join(section_texts), None

            if ole.exists("PrvText"):
                encoded = ole.openstream("PrvText").read()
                preview = self._decode_hwp_text(encoded)
                if preview:
                    return preview, None
                return "", "HWP 텍스트 추출 실패 (빈 내용)"

            if section_error:
                return "", f"HWP 텍스트 추출 실패 ({section_error})"
            return "", "HWP 텍스트 추출 실패 (본문 섹션 없음)"
        except Exception as e:
            return "", f"HWP 오류: {e}"
        finally:
            if ole is not None:
                try:
                    ole.close()
                except Exception:
                    pass

    def _extract_hwpx(self, path: str) -> Tuple[str, Optional[str]]:
        try:
            with zipfile.ZipFile(path) as zf:
                names = sorted(
                    name
                    for name in zf.namelist()
                    if name.lower().endswith(".xml")
                    and (
                        name.lower().startswith("contents/")
                        or "/section" in name.lower()
                        or "bodytext" in name.lower()
                    )
                )
                if not names:
                    names = sorted(name for name in zf.namelist() if name.lower().endswith(".xml"))

                parts: List[str] = []
                for name in names:
                    try:
                        raw = zf.read(name)
                        root = ET.fromstring(raw)
                    except Exception:
                        continue
                    text = self._extract_xml_text(root)
                    if text:
                        parts.append(text)
                if parts:
                    return "\n\n".join(parts), None
                return "", "HWPX 텍스트 추출 실패 (본문 XML 없음)"
        except zipfile.BadZipFile as e:
            return "", f"HWPX 오류: 잘못된 zip 형식 ({e})"
        except Exception as e:
            return "", f"HWPX 오류: {e}"

    def _extract_xml_text(self, root: ET.Element) -> str:
        lines: List[str] = []
        current: List[str] = []

        def _flush() -> None:
            text = "".join(current).strip()
            current.clear()
            if text:
                lines.append(re.sub(r"\s+", " ", text))

        for elem in root.iter():
            tag = elem.tag.split("}", 1)[-1].lower()
            if elem.text and elem.text.strip():
                current.append(elem.text)
            if tag in {"p", "paragraph", "tr", "row", "table", "section"}:
                _flush()
            if elem.tail and elem.tail.strip():
                current.append(elem.tail)
        _flush()
        return "\n".join(lines).strip()

    def _decode_hwp_text(self, raw: bytes) -> str:
        text = raw.decode("utf-16", errors="ignore")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        return text.strip()

    def _hwp_text_quality(self, text: str) -> float:
        if not text:
            return 0.0
        allowed = 0
        for ch in text:
            code = ord(ch)
            if ch.isspace() or ch.isdigit():
                allowed += 1
                continue
            if "a" <= ch.lower() <= "z":
                allowed += 1
                continue
            if 0xAC00 <= code <= 0xD7A3:
                allowed += 1
                continue
            if ch in ".,;:!?()[]{}<>+-=*/'\"_#%&":
                allowed += 1
        return allowed / len(text)

    def _extract_hwp_sections(self, ole: OleLike) -> Tuple[List[str], Optional[str]]:
        sections: List[Tuple[int, str]] = []
        for entry in ole.listdir():
            if len(entry) < 2:
                continue
            if entry[0] != "BodyText":
                continue
            if not entry[1].startswith("Section"):
                continue
            m = re.search(r"(\d+)$", entry[1])
            section_idx = int(m.group(1)) if m else 10 ** 6
            stream_name = "/".join(entry)
            sections.append((section_idx, stream_name))

        if not sections:
            return [], None

        sections.sort(key=lambda x: x[0])
        texts: List[str] = []
        errors: List[str] = []

        for _, stream_name in sections:
            try:
                raw = ole.openstream(stream_name).read()
            except Exception as e:
                errors.append(f"{stream_name}: 스트림 읽기 실패 ({e})")
                continue

            decoded = self._decode_hwp_text(raw)
            decoded_score = self._hwp_text_quality(decoded)
            inflated_decoded = ""
            inflated_score = 0.0
            try:
                inflated = zlib.decompress(raw, -15)
                inflated_decoded = self._decode_hwp_text(inflated)
                inflated_score = self._hwp_text_quality(inflated_decoded)
            except Exception:
                inflated_decoded = ""
                inflated_score = 0.0

            chosen = ""
            if inflated_decoded and (inflated_score > decoded_score + 0.15 or decoded_score < 0.35):
                chosen = inflated_decoded
            elif decoded and decoded_score >= 0.35:
                chosen = decoded
            elif inflated_decoded and inflated_score >= 0.35:
                chosen = inflated_decoded

            if chosen:
                texts.append(chosen)
            elif inflated_decoded:
                errors.append(f"{stream_name}: 압축 해제 후 디코딩 실패")
            else:
                errors.append(f"{stream_name}: 디코딩 실패")

        if texts:
            return texts, None
        if errors:
            return [], errors[0]
        return [], "본문 섹션에서 텍스트를 찾지 못함"
