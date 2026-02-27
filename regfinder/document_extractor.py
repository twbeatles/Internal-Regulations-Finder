# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import zlib
from typing import List, Optional, Tuple

from .file_utils import FileUtils
from .runtime import _import_attr, _import_module

class BaseOCREngine:
    """PDF 이미지 OCR 확장 포인트."""

    def extract_pdf_images(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        raise NotImplementedError


class NoOpOCREngine(BaseOCREngine):
    """OCR 미연결 기본 구현."""

    def extract_pdf_images(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        return "", "OCR 엔진 미설정"


class DocumentExtractor:
    def __init__(self):
        self._docx_module = None
        self._pdf_module = None
        self._hwp_module = None
    
    @property
    def docx(self):
        if self._docx_module is None:
            try:
                self._docx_module = _import_attr("docx", "Document")
            except ImportError:
                self._docx_module = False
        return self._docx_module
    
    @property
    def pdf(self):
        if self._pdf_module is None:
            try:
                self._pdf_module = _import_attr("pypdf", "PdfReader")
            except ImportError:
                self._pdf_module = False
        return self._pdf_module

    def check_pdf_encrypted(self, path: str) -> Tuple[bool, Optional[str]]:
        """PDF 암호화 여부 확인."""
        if not self.pdf:
            return False, "PDF 라이브러리 없음"
        try:
            reader = self.pdf(path)
            return bool(getattr(reader, "is_encrypted", False)), None
        except Exception as e:
            return False, f"PDF 검사 오류: {e}"

    def extract(
        self,
        path: str,
        pdf_password: Optional[str] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
    ) -> Tuple[str, Optional[str]]:
        if not path or not os.path.exists(path):
            return "", f"파일 없음: {path}"
        if not os.path.isfile(path):
            return "", f"파일이 아님: {path}"
        ext = os.path.splitext(path)[1].lower()
        if ext == '.txt':
            return self._extract_txt(path)
        elif ext == '.docx':
            return self._extract_docx(path)
        elif ext == '.pdf':
            return self._extract_pdf(path, pdf_password=pdf_password, ocr_engine=ocr_engine)
        elif ext == '.hwp':
            return self._extract_hwp(path)
        return "", f"지원하지 않는 형식: {ext}"
    
    def _extract_txt(self, path: str) -> Tuple[str, Optional[str]]:
        return FileUtils.safe_read(path)
    
    def _extract_docx(self, path: str) -> Tuple[str, Optional[str]]:
        if not self.docx:
            return "", "DOCX 라이브러리 없음"
        try:
            doc = self.docx(path)
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        parts.append(' | '.join(cells))
            return '\n\n'.join(parts), None
        except Exception as e:
            return "", f"DOCX 오류: {e}"
    
    def _try_pdf_decrypt(self, reader, password: str) -> bool:
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
    ) -> Tuple[str, Optional[str]]:
        if not self.pdf:
            return "", "PDF 라이브러리 없음"
        try:
            reader = self.pdf(path)
            if reader.is_encrypted:
                if pdf_password:
                    if not self._try_pdf_decrypt(reader, pdf_password):
                        return "", "암호화된 PDF (비밀번호 불일치)"
                elif not self._try_pdf_decrypt(reader, ""):
                    return "", "암호화된 PDF (비밀번호 필요)"

            texts = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        texts.append(text.strip())
                except Exception:
                    continue

            if not texts:
                engine = ocr_engine or NoOpOCREngine()
                try:
                    ocr_text, ocr_error = engine.extract_pdf_images(path)
                    if ocr_text and ocr_text.strip():
                        return ocr_text.strip(), None
                    if ocr_error:
                        return "", f"텍스트 없음 (이미지 PDF, {ocr_error})"
                except Exception as e:
                    return "", f"텍스트 없음 (이미지 PDF, OCR 오류: {e})"
                return "", "텍스트 없음 (이미지 PDF)"

            return '\n\n'.join(texts), None
        except Exception as e:
            return "", f"PDF 오류: {e}"
    
    @property
    def hwp(self):
        """HWP 파일 처리용 olefile 모듈 로드"""
        if self._hwp_module is None:
            try:
                self._hwp_module = _import_module("olefile")
            except ImportError:
                self._hwp_module = False
        return self._hwp_module
    
    def _extract_hwp(self, path: str) -> Tuple[str, Optional[str]]:
        """HWP 파일에서 텍스트 추출 (olefile 사용)"""
        if not self.hwp:
            return "", "HWP 라이브러리 없음 (pip install olefile)"

        ole = None
        try:
            ole = self.hwp.OleFileIO(path)
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

    def _extract_hwp_sections(self, ole) -> Tuple[List[str], Optional[str]]:
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
                errors.append(f"{stream_name}: 스트림 열기 실패 ({e})")
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
