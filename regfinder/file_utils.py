# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import platform
import subprocess
from typing import Dict, Iterable, List, Optional, Tuple

from .app_types import DiscoveredFile
from .runtime import logger

class FileUtils:
    @staticmethod
    def safe_read(path: str) -> Tuple[str, Optional[str]]:
        try:
            with open(path, 'rb') as f:
                raw_data = f.read()

            for enc in ('utf-8', 'cp949', 'euc-kr'):
                try:
                    return raw_data.decode(enc), None
                except UnicodeDecodeError:
                    continue

            charset_normalizer = importlib.import_module("charset_normalizer")
            res = charset_normalizer.from_bytes(raw_data).best()
            if res and getattr(res, "encoding", None):
                encoding = str(res.encoding)
                return raw_data.decode(encoding, errors='ignore'), None
            return raw_data.decode('utf-8', errors='ignore'), None
        except Exception as e:
            logger.exception(f"파일 읽기 오류: {path}")
            return "", str(e)
    
    @staticmethod
    def get_metadata(path: str) -> Optional[Dict]:
        try:
            stat = os.stat(path)
            mtime = getattr(stat, "st_mtime_ns", None)
            if mtime is None:
                mtime = int(stat.st_mtime * 1_000_000_000)
            return {'size': stat.st_size, 'mtime': float(mtime)}
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
        size_value = float(size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_value < 1024:
                return f"{size_value:.1f}{unit}"
            size_value /= 1024
        return f"{size_value:.1f}TB"

    @staticmethod
    def build_discovered_file(folder: str, path: str, *, stat_result: os.stat_result | None = None) -> DiscoveredFile:
        root = os.path.normpath(os.path.abspath(folder))
        absolute_path = os.path.normpath(os.path.abspath(path))
        stat_result = stat_result or os.stat(absolute_path)
        rel_path = os.path.relpath(absolute_path, root).replace("\\", "/")
        name = os.path.basename(absolute_path)
        extension = os.path.splitext(name)[1].lower()
        return DiscoveredFile(
            path=absolute_path,
            rel_path=rel_path,
            name=name,
            extension=extension,
            size=int(stat_result.st_size),
            mtime=float(getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))),
            file_key=rel_path,
        )

    @staticmethod
    def discover_files(
        folder: str,
        *,
        recursive: bool,
        supported_extensions: Iterable[str],
    ) -> List[DiscoveredFile]:
        root = os.path.normpath(os.path.abspath(folder))
        extensions = {str(ext).lower() for ext in supported_extensions}
        discovered: List[DiscoveredFile] = []

        def _scan(directory: str) -> None:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                _scan(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        extension = os.path.splitext(entry.name)[1].lower()
                        if extension not in extensions:
                            continue
                        stat_result = entry.stat(follow_symlinks=False)
                        discovered.append(
                            FileUtils.build_discovered_file(root, entry.path, stat_result=stat_result)
                        )
                    except PermissionError:
                        raise
                    except OSError as exc:
                        logger.debug(f"파일 탐색 중 항목 건너뜀: {entry.path} - {exc}")

        _scan(root)
        discovered.sort(key=lambda item: item.rel_path.lower())
        return discovered
