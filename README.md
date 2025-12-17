# 사내 규정 검색기 v9.0

로컬 AI 기반 사내 규정 문서 검색 프로그램

## 주요 기능

### 🔍 하이브리드 검색
- **벡터 검색**: HuggingFace 한국어 임베딩 모델 사용
- **키워드 검색**: BM25 알고리즘 적용
- **가중치 결합**: 벡터(70%) + 키워드(30%) 하이브리드 점수

### 📄 지원 문서 형식
- TXT (텍스트)
- DOCX (Microsoft Word)
- PDF (표준 PDF, 이미지 PDF 제외)

### ⚡ 성능 최적화
- 증분 인덱싱 (변경 파일만 재처리)
- 캐시 시스템 (빠른 재로드)
- 배치 처리 (메모리 효율)
- CUDA GPU 지원

### 🎨 UI 특징
- CustomTkinter 기반 모던 UI
- 다크/라이트 테마 지원
- 토스트 알림 (스택 지원)
- 검색 결과 점수 시각화
- 검색어 하이라이트

---

## 설치 및 실행

### 요구 사항
- Python 3.9+
- Windows 10/11

### 의존성 설치
```bash
pip install customtkinter torch langchain langchain-huggingface langchain-community faiss-cpu python-docx pypdf
```

### 실행
```bash
python "사내 규정검색기 v8 claude 리팩토링.py"
```

---

## 사용 방법

1. **모델 로딩**: 프로그램 시작 시 자동으로 AI 모델 로드
2. **폴더 선택**: `📂 열기` 버튼으로 규정 문서 폴더 선택
3. **문서 처리**: 자동으로 문서 분석 및 인덱싱
4. **검색**: 검색어 입력 후 Enter 또는 `🔍 검색` 버튼

---

## 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+O` | 폴더 열기 |
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+H` | 검색 기록 |
| `Ctrl+S` | 기록 저장 |
| `Esc` | 검색어 지우기 |

---

## 설정

### AI 모델 선택
- **SNU SBERT (고성능)**: `snunlp/KR-SBERT-V40K-klueNLI-augSTS`
- **BM-K Simal (균형)**: `BM-K/ko-simal-roberta-base`
- **JHGan SBERT (빠름)**: `jhgan/ko-sbert-nli` (기본값)

### 검색 모드
- **하이브리드**: 벡터 + 키워드 결합 (권장)
- **벡터만**: 의미 기반 검색

---

## 빌드 (EXE)

```bash
pyinstaller "사내 규정검색기.spec"
```

---

## 버전 히스토리

### v9.0 (2024-12)
- 예외 처리 강화 (8개 bare except 수정)
- 검색 점수 정규화 개선 (min-max)
- BM25 토크나이징 안정성 강화
- Toast 스택 시스템
- ResultCard 점수 시각화
- 검색어 하이라이트
- JSON 내보내기 지원
- 파일 통계 패널
- 키보드 단축키 도움말

### v8.1
- 초기 버전
- 하이브리드 검색
- 증분 인덱싱
- 캐시 시스템

---

## 라이선스

내부 사용 전용
