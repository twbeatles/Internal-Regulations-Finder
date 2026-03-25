# -*- mode: python ; coding: utf-8 -*-
"""
사내 규정검색기 v9.3 (PyQt6) - Onefile Build
단일 EXE 빌드 설정

빌드 명령:
    pyinstaller "사내 규정검색기 v9 PyQt6.spec"

출력:
    dist/사내 규정검색기 v9.3_onefile.exe

참고:
    실제 출력 파일명은 아래 EXE(...)의 name 값으로 결정됩니다.
    앱 설정 탭의 `🧰 진단 내보내기`는 빌드와 무관하지만, 배포 환경에서 문제 재현/분석을 위한 로그/설정/환경 요약 zip을 생성합니다.
    모델 다운로드는 스크립트 실행 시 subprocess 경로를 사용하며,
    frozen(onefile) 실행에서는 in-process 경로로 폴백됩니다.
    따라서 onefile EXE의 다운로드 취소는 현재 모델 완료 후 중단될 수 있습니다.
    암호화 PDF 비밀번호는 GUI에서 폴더 로드 전 사전 입력되며 세션 메모리에만 유지됩니다.
    이미지 PDF용 OCR 엔진은 기본 번들에 포함하지 않습니다.
    `sentence_transformers` import 경로는 `transformers -> PIL.Image` 와
    `sentence_transformers -> sklearn.metrics` 체인을 타므로,
    경량화 시 `Pillow` / `scikit-learn` 제외 여부를 주의해야 합니다.
    `FileUtils.safe_read()` 는 `charset_normalizer` 를 동적 import 하므로,
    lazy fallback 경로가 EXE에서도 유지되도록 hiddenimports에 포함합니다.
    설정창 모델 다운로드 상태 표시는 `models--<org>--<name>/blobs,snapshots`
    Hugging Face 캐시 구조를 기준으로 판별합니다.
    `pyrightconfig.json`, `.editorconfig`, `.gitattributes`, `.vscode/settings.json`
    같은 개발용 품질 설정 파일과 `tests/test_repo_text_encoding.py` 같은 회귀 테스트는 번들 대상이 아닙니다.
    `.pytest_localappdata`, `.regfinder_logs` 같은 로컬 테스트/로그 디렉터리도 번들 대상이 아닙니다.
    최신 UI는 검색 중 인라인 진행 카드와 결과 상세 모달을 사용하지만 별도 데이터 파일 추가는 필요하지 않습니다.
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

sentence_transformers_hiddenimports = collect_submodules('sentence_transformers')
sentence_transformers_datas = collect_data_files('sentence_transformers')
sentence_transformers_metadata = copy_metadata('sentence-transformers')
charset_normalizer_hiddenimports = collect_submodules('charset_normalizer')
sklearn_metadata = copy_metadata('scikit-learn')
pillow_metadata = copy_metadata('pillow')

hiddenimports = [
    # Internal package entrypoints
    'regfinder',
    'regfinder.app_main',
    'regfinder.main_window',
    'regfinder.main_window_mixins',
    'regfinder.main_window_ui_mixin',
    'regfinder.ui_components',
    'regfinder.ui_style',
    'regfinder.workers',
    'regfinder.qa_system',
    'regfinder.qa_system_mixins',
    'regfinder.document_extractor',
    'regfinder.bm25',
    'regfinder.search_text',
    'regfinder.file_utils',
    'regfinder.text_cache',
    'regfinder.model_inventory',
    'regfinder.worker_registry',
    'regfinder.persistence',
    'regfinder.runtime',
    'regfinder.app_types',

    # PyQt6 runtime
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',

    # NLP / embeddings runtime
    'torch',
    'transformers',
    'sentence_transformers',
    'langchain_huggingface',
    'langchain_huggingface.embeddings',
    'langchain_community.vectorstores.faiss',
    'langchain_text_splitters',
    'langchain_core.documents',
    'faiss',
    'sklearn',
    'sklearn.metrics',
    'sklearn.metrics.pairwise',
    'PIL',
    'PIL.Image',
    'charset_normalizer',

    # Document extraction
    'docx',
    'pypdf',
    'olefile',
] + sentence_transformers_hiddenimports + charset_normalizer_hiddenimports

excludes = [
    # Unused UI / analysis stacks
    'matplotlib', 'matplotlib.pyplot',
    'cv2', 'opencv', 'opencv-python',
    'pandas',
    'IPython', 'jupyter', 'notebook',
    'pytest', 'black', 'pylint', 'mypy', 'sphinx',
    'pyright',
    'tkinter', '_tkinter', 'Tkinter',
    'PySide6', 'PySide2', 'PyQt5',
    'tensorflow', 'keras',
    'flask', 'django',
    'plotly', 'seaborn', 'bokeh',

    # LangChain optional integrations not used by this app
    'langchain',
    'langchain_classic',
    'langchain_community.document_loaders',
    'playwright',
    'selenium',
    'unstructured',
    'bs4',
    'beautifulsoup4',
    'sqlalchemy',
    'dask',
    'pyarrow',

    # Optional PDF / browser stacks not used by current extractor
    'pdfminer',
    'pymupdf',
    'fitz',
    'pypdfium2',
    'pypdfium2_raw',

    # Optional vision / compile stacks not used for sentence embeddings
    'torchvision',
]

# ============================================================================
# 분석 설정
# ============================================================================
a = Analysis(
    ['사내 규정검색기 v9 PyQt6.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=sentence_transformers_datas + sentence_transformers_metadata + sklearn_metadata + pillow_metadata,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ============================================================================
# PYZ 압축
# ============================================================================
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# ============================================================================
# 단일 EXE 빌드 (Onefile)
# ============================================================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='사내 규정검색기 v9.3_onefile',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 비활성화 (DLL 호환성)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
