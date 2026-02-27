# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import platform
import subprocess
from typing import Dict, Optional, Tuple

import charset_normalizer

from .runtime import logger

class FileUtils:
    @staticmethod
    def safe_read(path: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            with open(path, 'rb') as f:
                raw_data = f.read()
            
            # 1. charset_normalizer를 통한 정밀 감지
            res = charset_normalizer.from_bytes(raw_data).best()
            if res and res.encoding:
                encoding = res.encoding
                confidence = res.coherence
            else:
                encoding, confidence = 'utf-8', 0
                
            # 2. 신뢰도가 낮을 경우 한글 환경Fallback
            if confidence < 0.5:
                for enc in ['utf-8', 'cp949', 'euc-kr']:
                    try:
                        return raw_data.decode(enc), None
                    except UnicodeDecodeError:
                        continue
            return raw_data.decode(encoding, errors='ignore'), None
        except Exception as e:
            logger.exception(f"파일 읽기 오류: {path}")
            return None, str(e)
    
    @staticmethod
    def get_metadata(path: str) -> Optional[Dict]:
        try:
            stat = os.stat(path)
            return {'size': stat.st_size, 'mtime': stat.st_mtime}
        except OSError as e:
            logger.debug(f"파일 메타데이터 조회 실패: {path} - {e}")
            return None
    
    @staticmethod
    def open_file(path: str):
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', path], check=False)
            else:
                subprocess.run(['xdg-open', path], check=False)
        except Exception as e:
            logger.error(f"파일 열기 실패: {e}")
    
    @staticmethod
    def format_size(size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
