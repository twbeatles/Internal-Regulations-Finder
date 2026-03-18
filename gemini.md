# 🤖 Gemini AI Guidelines: 사내 규정 검색기 v9.3

## 핵심 상태

- 단일 스크립트 구조 → `regfinder` 패키지 구조로 분리 완료
- 2차 리팩토링: UI 빌더/설정·진단 로직/QA 진단 로직을 믹스인으로 추가 분리
- 워커 관리는 `WorkerRegistry`로 통합
- 설정은 `ConfigManager`(schema_version=3) 기반으로 마이그레이션 처리
- 캐시는 `CACHE_SCHEMA_VERSION=3` 기준으로 텍스트(SQLite)와 모델별 벡터 캐시로 분리
- 정적 분석 기준은 `pyrightconfig.json`으로 고정
- frozen(onefile) 모델 다운로드는 subprocess 대신 in-process 경로 사용
- 오프라인 임베딩 런타임은 `Pillow` / `scikit-learn` / `sentence_transformers` 사전검증 추가
- `FileUtils.safe_read()`는 `UTF-8 -> CP949 -> EUC-KR` fast path 후 lazy `charset_normalizer` fallback 사용
- 검색 정규화는 `regfinder.search_text`로 통합되어 BM25/필터/하이라이트가 같은 규칙을 사용
- 무공백 한국어 질의와 조사 제거 기반 semantic matching을 지원
- 검색 결과는 파일 단위로 그룹화되며 `match_count`, `snippet_chunk_idx`를 함께 유지
- 벡터 인덱스 실패 시에도 `bm25_only` 검색 모드로 폴백 가능
- 진단 탭/내부 상태는 `search_mode`, `vector_ready`, `memory_warning`를 표시
- 모델 다운로드 상태는 Hugging Face 로컬 캐시(`models--.../blobs`, `snapshots`) 기준으로 판별
- 모델 다운로드 상태/용량은 `model_inventory.json` 캐시를 통해 재스캔 비용을 줄임
- 모델 다운로드 상태 접근은 `ModelDownloadState` 타입 계약으로 고정되어 Pylance 추론이 흔들리지 않음
- `.vscode/settings.json`과 `tests/test_repo_text_encoding.py`로 UTF-8/워크스페이스 진단 재발을 방지

## 현재 사용자 기능

- 검색 필터: 확장자/파일명/경로
- 검색 정렬: 랭킹점수순/파일명순/최근 수정순
- 파일 단위 검색 결과, 대표 청크, 근거 청크 수 표시
- 랭킹 점수 툴팁(상대 점수 + 벡터/키워드 구성요소)
- 결과 북마크 저장/내보내기
- 최근 폴더 다중 관리
- 진단 탭(인덱스 상태 + 검색 로그 요약 + 마지막 검색 통계)
- 오류 코드별 가이드 메시지
- 검색 후 검색어 유지 옵션
- 경로 필터 슬래시 정규화(`/`, `\`)
- 다운로드 실패 시 `op_id`와 실제 import 실패 패키지명을 함께 노출
- 모델 로드 성공 직후 검색창 입력 가능
- 설정창 모델 목록은 다운로드 완료 모델을 상단 우선 정렬
- 동일 폴더에서 모델만 바뀌면 텍스트 재추출 없이 벡터 캐시만 재생성
- 대규모 인덱스는 hard fail 대신 경고만 표시

## 운영 규칙

1. 워커 `run()`에서 UI 직접 변경 금지
2. 시그널 기반으로만 UI 업데이트
3. 검색/인덱스 상태는 `RegulationQASystem` public API를 통해 조회
4. 종료 시 워커 취소 및 리소스 정리
5. 추적 텍스트 파일은 `.editorconfig`, `.gitattributes` 기준으로 `UTF-8(no BOM)` / `LF` 유지
6. PyInstaller 경량화 시 `PIL` / `Pillow` / `scikit-learn` / `charset_normalizer` 제외 여부를 먼저 검토

## 검증 명령

```bash
python -m pyright .
python tools/smoke_refactor.py
python tools/benchmark_performance.py
python -m py_compile "사내 규정검색기 v9 PyQt6.spec"
python -m unittest discover -s tests -v
python -m pytest -q
```
