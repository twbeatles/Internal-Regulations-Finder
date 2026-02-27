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
"""

import os

block_cipher = None

# ============================================================================
# 분석 설정
# ============================================================================
a = Analysis(
    ['사내 규정검색기 v9 PyQt6.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Internal package (modular refactor)
        'regfinder',
        'regfinder.app_types',
        'regfinder.runtime',
        'regfinder.persistence',
        'regfinder.worker_registry',
        'regfinder.file_utils',
        'regfinder.bm25',
        'regfinder.document_extractor',
        'regfinder.qa_system_mixins',
        'regfinder.qa_system',
        'regfinder.workers',
        'regfinder.ui_style',
        'regfinder.ui_components',
        'regfinder.main_window_ui_mixin',
        'regfinder.main_window_mixins',
        'regfinder.main_window',
        'regfinder.app_main',

        # PyQt6 (필수)
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip',
        
        # PyTorch (필수 - 전체 포함)
        'torch', 'torch.nn', 'torch.nn.functional',
        'torch.utils', 'torch.utils.data', 'torch.distributed',
        'torch.backends', 'torch.backends.cudnn',
        'torch._utils', 'torch.autograd', 'torch.testing',
        
        # Transformers / HuggingFace (필수)
        'transformers', 'sentence_transformers', 'huggingface_hub',
        'huggingface_hub.file_download',
        
        # LangChain (필수)
        'langchain', 'langchain.text_splitter', 'langchain.docstore.document',
        'langchain_community', 'langchain_community.vectorstores',
        'langchain_community.vectorstores.faiss',
        'langchain_huggingface', 'langchain_huggingface.embeddings',
        
        # FAISS
        'faiss', 'faiss.swigfaiss',
        
        # 문서 처리
        'docx', 'docx.document', 'pypdf', 'olefile',
        
        # 데이터 처리
        'numpy', 'numpy.core._multiarray_umath',
        
        # 유틸리티
        'tqdm', 'tqdm.auto', 'regex', 'requests',
        'charset_normalizer', 'safetensors', 'tokenizers', 'filelock',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요 패키지 제외
        'matplotlib', 'matplotlib.pyplot',
        'PIL', 'Pillow',
        'cv2', 'opencv', 'opencv-python',
        'sklearn', 'scikit-learn',
        'pandas',
        'IPython', 'jupyter', 'notebook',
        'pytest', 'black', 'pylint', 'mypy', 'sphinx',
        'tkinter', '_tkinter', 'Tkinter',
        'PySide6', 'PySide2', 'PyQt5',
        'tensorflow', 'keras',
        'flask', 'django',
        'plotly', 'seaborn', 'bokeh',
    ],
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
