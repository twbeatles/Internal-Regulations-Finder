# -*- mode: python ; coding: utf-8 -*-
"""
사내 규정 검색기 v9.2 (PyQt6)
PyInstaller 빌드 설정 파일

빌드 명령:
    pyinstaller "사내 규정검색기 v9 PyQt6.spec"

출력:
    dist/사내 규정검색기 v9.2/

주의사항:
    - Python 3.9+ 필요
    - 가상환경에서 빌드 권장
    - 첫 빌드 시 5~10분 소요
    
변경 이력:
    v9.2: 키보드 단축키, 검색 내보내기, 버그 수정
    v9.1: UI/UX 개선, 검색어 하이라이트
    v9.0: PyQt6 기반 초기 버전
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ============================================================================
# 분석 설정
# ============================================================================
a = Analysis(
    ['사내 규정검색기 v9 PyQt6.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 필요 시 아이콘, 리소스 파일 추가
        # ('icon.ico', '.'),
        # ('assets', 'assets'),
    ],
    hiddenimports=[
        # ========================================
        # PyQt6
        # ========================================
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',
        
        # ========================================
        # PyTorch
        # ========================================
        'torch',
        'torch.nn',
        'torch.nn.functional',
        'torch.cuda',
        'torch.backends',
        'torch.backends.cudnn',
        'torch.utils',
        'torch.utils.data',
        
        # ========================================
        # Transformers / HuggingFace
        # ========================================
        'transformers',
        'transformers.models',
        'transformers.tokenization_utils',
        'transformers.tokenization_utils_base',
        'transformers.utils',
        'sentence_transformers',
        'sentence_transformers.models',
        'huggingface_hub',
        'huggingface_hub.file_download',
        'huggingface_hub.utils',
        
        # ========================================
        # LangChain
        # ========================================
        'langchain',
        'langchain.text_splitter',
        'langchain.docstore',
        'langchain.docstore.document',
        'langchain_core',
        'langchain_core.documents',
        'langchain_community',
        'langchain_community.vectorstores',
        'langchain_community.vectorstores.faiss',
        'langchain_huggingface',
        'langchain_huggingface.embeddings',
        
        # ========================================
        # FAISS (벡터 검색)
        # ========================================
        'faiss',
        'faiss.swigfaiss',
        
        # ========================================
        # 문서 처리
        # ========================================
        'docx',
        'docx.document',
        'docx.table',
        'docx.opc',
        'docx.opc.constants',
        'pypdf',
        'pypdf._reader',
        'pypdf.generic',
        
        # ========================================
        # 데이터 처리
        # ========================================
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'scipy',
        'scipy.sparse',
        'scipy.sparse._sparsetools',
        'sklearn',
        'sklearn.metrics',
        'sklearn.preprocessing',
        
        # ========================================
        # 네트워크 / 유틸리티
        # ========================================
        'tqdm',
        'tqdm.auto',
        'regex',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'packaging',
        'packaging.version',
        'packaging.specifiers',
        'filelock',
        'safetensors',
        'tokenizers',
        
        # ========================================
        # 표준 라이브러리 (누락 방지)
        # ========================================
        'json',
        'hashlib',
        'tempfile',
        'shutil',
        'logging',
        'threading',
        're',
        'gc',
        'math',
        'time',
        'email',
        'email.mime',
        'email.mime.text',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 모듈 제외 (용량 절약)
        'matplotlib',
        'PIL',
        'cv2',
        'opencv',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'black',
        'pylint',
        'mypy',
        'sphinx',
        'tkinter',  # PyQt6 사용하므로 제외
        'PySide6',  # PyQt6 사용하므로 제외
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
# 실행 파일 생성 (폴더 모드)
# ============================================================================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='사내 규정검색기 v9.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI 앱이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',  # 아이콘 파일 있을 경우 활성화
)

# ============================================================================
# 폴더 수집 (권장 방식)
# ============================================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='사내 규정검색기 v9.2',
)

# ============================================================================
# 단일 EXE 빌드 (선택사항)
# 아래 주석 해제 시 COLLECT 대신 사용
# 주의: 단일 EXE는 시작 속도가 느림 (압축 해제 필요)
# ============================================================================
# exe_onefile = EXE(
#     pyz,
#     a.scripts,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     [],
#     name='사내 규정검색기 v9.2',
#     debug=False,
#     bootloader_ignore_signals=False,
#     strip=False,
#     upx=True,
#     runtime_tmpdir=None,
#     console=False,
# )
