# Refactor Verification Checklist

## 1. Static checks

- [ ] `python -m pyright .` 통과 (`0 errors`)
- [ ] `python tools/smoke_refactor.py` 통과
- [ ] `python tools/benchmark_performance.py` 실행 확인
- [ ] `python -m py_compile "사내 규정검색기 v9 PyQt6.spec"` 통과
- [ ] `python -m unittest discover -s tests -v` 통과
- [ ] `python -m pytest -q` 통과
- [ ] 추적 텍스트 파일 `UTF-8(no BOM)` / `LF` 유지 확인
- [ ] `tests/test_repo_text_encoding.py`가 UTF-8 디코딩/replacement char 회귀를 함께 검증하는지 확인
- [ ] Windows PowerShell/Python 출력 모지바케와 실제 UTF-8 파일 손상을 구분해 확인
- [ ] `pyrightconfig.json` / `.vscode/settings.json`이 optional dependency missing-import 노이즈 없이 `python -m pyright .` 0 errors를 유지하는지 확인

## 1-1. 권장 검증 명령

```bash
python -m pyright .
python tools/smoke_refactor.py
python tools/benchmark_performance.py
python -m py_compile "사내 규정검색기 v9 PyQt6.spec"
python -m unittest discover -s tests -v
python -m pytest -q
```

## 2. App startup

- [ ] 앱 실행/초기 모델 로드 상태 표시
- [ ] 모델 로드 결과에 따른 검색/폴더 버튼 활성화
- [ ] 모델만 로드된 상태에서는 검색 패널이 비활성화되고, searchable index 준비 후 활성화되는지 확인
- [ ] 빈 상태 카드/라벨 배경이 전역 스타일에 가려지지 않는지 확인

## 3. Search UX

- [ ] 확장자/파일명/경로 필터 동작
- [ ] 경로 필터가 `/` 와 `\` 입력에서 동일하게 동작
- [ ] 무공백 한국어 질의(`휴가규정`)와 조사 포함 질의(`휴가를`)가 적중
- [ ] 정렬(`점수순`/`파일명순`/`최근 수정순`) 동작
- [ ] 결과가 파일 단위로 그룹화되고 `근거 청크 n개`, `대표 청크 #n`가 표시
- [ ] 결과 카드 하이라이트/복사/북마크 동작
- [ ] 검색 중 기존 결과가 유지되고 인라인 진행 카드/취소 버튼이 표시되는지 확인
- [ ] 검색 중 필터/정렬/히스토리/결과 수 입력이 함께 잠기는지 확인
- [ ] 무결과 + 필터 적용 상태에서 필터 요약과 `필터 초기화`가 표시되는지 확인
- [ ] 히스토리 선택 시 query뿐 아니라 filters/sort/k/hybrid가 복원되고 즉시 재검색되는지 확인
- [ ] 결과 상세 모달에서 파일 열기/경로 복사/근거 청크 이동/전체 문서 보기가 동작하는지 확인
- [ ] 폰트 슬라이더 변경 시 현재 결과 카드 본문 폰트가 즉시 반영되는지 확인
- [ ] 조사 제거 질의(`휴가를`)와 무공백 질의(`휴가규정`)가 하이라이트에도 반영되는지 확인
- [ ] 결과 점수 툴팁이 `랭킹 점수` wording과 벡터/키워드 구성요소를 표시
- [ ] 결과 내보내기(txt/csv) 헤더가 `랭킹 점수` 기준으로 출력되고 CSV escaping이 유지되는지 확인
- [ ] 검색 후 검색어 유지 옵션이 설정에 따라 동작
- [ ] 파일 탭 `크기`/`청크`, 북마크 탭 `랭킹 점수`가 숫자 기준으로 정렬되는지 확인

## 4. Folder/document flow

- [ ] 최근 폴더 목록 표시 및 재로드
- [ ] 암호화 PDF 비밀번호 입력/세션 재사용 동작
- [ ] 암호화 PDF 비밀번호 미입력/오입력 파일이 해당 파일만 이번 인덱스에서 제외되는지 확인
- [ ] 문서 처리 진행/취소 동작
- [ ] 처리 후 파일 통계/캐시 크기 갱신
- [ ] 동일 폴더에서 모델만 변경 시 텍스트 재추출 없이 벡터 캐시만 재생성되는지 확인
- [ ] text cache(`text_cache.sqlite`) / vector cache(`vector_meta.json`)가 schema v3 기준으로 생성되는지 확인
- [ ] text cache file metadata에 fingerprint가 저장되고 same-size modified file도 stale cache 없이 판별되는지 확인
- [ ] 벡터 인덱스 실패 시에도 `bm25_only` 검색 모드로 폴백하는지 확인
- [ ] 수정 파일 재추출 실패 시 이전 본문이 검색되지 않고 해당 파일이 현재 인덱스에서 제외되는지 확인
- [ ] 청크 수가 임계값을 넘으면 `memory_warning` 경고가 표시되는지 확인
- [ ] 캐시 삭제 후 파일 목록/결과/진단/PDF 비밀번호 세션이 함께 초기화되는지 확인

## 5. Diagnostics and errors

- [ ] 진단 탭 인덱스 상태 표시
- [ ] 검색 로그 요약 표시
- [ ] 마지막 검색 통계(`vector_fetch_k`, `bm25_candidates`, `filtered_out`) 표시
- [ ] 진단에 `search_mode`, `vector_ready`, `memory_warning`가 노출되는지 확인
- [ ] 진단 zip 내보내기 동작
- [ ] 오류 코드별 가이드 메시지 표시
- [ ] 오류 대화상자에 `op_id`가 함께 표시되는지 확인
- [ ] 오프라인 모델 다운로드 실패 시 실제 import 실패 패키지명(`Pillow`/`scikit-learn`/`sentence_transformers`)이 노출되는지 확인

## 5-1. Offline model download / packaging

- [ ] onefile EXE에서 모델 선택 다이얼로그가 강제 종료 없이 열리고 완료까지 진행되는지 확인
- [ ] onefile EXE에서 `SNU SBERT` 다운로드 완료 동작 확인
- [ ] onefile EXE에서 취소 시 "현재 모델 다운로드가 끝나면 중단" 안내가 표시되는지 확인
- [ ] 부분 실패 시 `DOWNLOAD_PARTIAL_FAIL` 가이드 문구와 실패 모델 목록이 함께 표시되는지 확인
- [ ] 설정창 모델 목록에서 다운로드 완료 모델이 상단 우선 표시되는지 확인
- [ ] `다운로드 모델 우선 선택` 버튼이 다운로드 상태에 맞게 활성/비활성되는지 확인
- [ ] `model_inventory.json` 갱신 후 모델 상태/용량 표시가 반복 전체 스캔 없이 유지되는지 확인
- [ ] spec hiddenimports에 `regfinder.search_text`가 포함되어 있는지 확인

## 6. Shutdown

- [ ] 종료 시 설정 저장
- [ ] 실행 중 워커 취소 처리
- [ ] `qa.cleanup()` 호출
