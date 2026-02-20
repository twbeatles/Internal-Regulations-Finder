# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from typing import Optional, Tuple

from .file_utils import FileUtils
from .runtime import _import_attr, _import_module

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
    
    def extract(self, path: str) -> Tuple[str, Optional[str]]:
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
            return self._extract_pdf(path)
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
    
    def _extract_pdf(self, path: str) -> Tuple[str, Optional[str]]:
        if not self.pdf:
            return "", "PDF 라이브러리 없음"
        try:
            reader = self.pdf(path)
            if reader.is_encrypted:
                try:
                    reader.decrypt('')
                except Exception as e:
                    return "", "암호화된 PDF"
            texts = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        texts.append(text.strip())
                except Exception:
                    continue
            if not texts:
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
        try:
            ole = self.hwp.OleFileIO(path)
            # HWP 5.0 형식의 본문 미리보기 스트림
            if ole.exists("PrvText"):
                encoded = ole.openstream("PrvText").read()
                text = encoded.decode('utf-16', errors='ignore')
                ole.close()
                if text.strip():
                    return text.strip(), None
                return "", "HWP 텍스트 추출 실패 (빈 내용)"
            # BodyText 섹션에서 시도
            elif ole.exists("BodyText/Section0"):
                encoded = ole.openstream("BodyText/Section0").read()
                text = encoded.decode('utf-16', errors='ignore')
                ole.close()
                # 제어 문자 제거
                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                if text.strip():
                    return text.strip(), None
            ole.close()
            return "", "HWP 텍스트 추출 실패"
        except Exception as e:
            return "", f"HWP 오류: {e}"
