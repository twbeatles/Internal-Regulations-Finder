# 기능 구현 점검 리뷰 및 반영 상태 (2026-03-19)

이 문서는 2026-03-19 기준 기능 구현 점검 결과와 반영 상태를 함께 정리한 기록이다.

## 원래 점검 포인트

1. GUI에서 m25_only fallback 검색이 실제로 가능한지
2. 수정 파일 재추출 실패 시 stale cache가 남지 않는지
3. 암호화 PDF 비밀번호 입력이 UI까지 연결되어 있는지
4. frozen(onefile) 다운로드 취소 semantics가 사용자에게 명확한지
5. 하이라이트가 검색 정규화 규칙과 일치하는지
6. CSV 내보내기가 안전한지
7. 캐시 삭제 후 UI 상태가 런타임 상태와 일치하는지

## 반영 상태

- m25_only 검색 진입 차단 제거: 완료
- 수정 파일 stale cache 제거: 완료
- 암호화 PDF 사전 비밀번호 입력 + 세션 메모리 재사용: 완료
- frozen(onefile) 다운로드 취소 안내/결과 메시지 보강: 완료
- 검색 정규화 기반 하이라이트 보강: 완료
- 검색 결과/북마크 CSV 내보내기 csv 모듈 기반 정리: 완료
- 캐시 삭제 후 파일/결과/버튼 상태 재동기화: 완료

## 코드/문서 정합성 체크 결과

- README.md: 현재 사용자 동작 기준으로 갱신
- claude.md: 개발/운영 메모 기준으로 갱신
- gemini.md: 구조/운영 규칙 기준으로 갱신
- PROJECT_STRUCTURE_ANALYSIS.md: 최근 반영 항목과 테스트 목록 갱신
- docs/refactor_mapping.md, docs/refactor_checklist.md: 체크 항목과 단계 매핑을 최신 동작 기준으로 보강
- 사내 규정검색기 v9 PyQt6.spec: onefile 취소 semantics 및 PDF 비밀번호 메모 반영
- .gitignore: .pytest_localappdata/, .regfinder_logs/ 같은 로컬 테스트/로그 디렉터리까지 반영

## 2026-03-25 후속 정합성 보강

- UI/UX 리뷰 문서 기준 개선사항 일괄 반영 완료
- 검색 busy state / 인라인 진행 카드 / 결과 상세 모달 / 필터 초기화 UX 반영 완료
- 검색 히스토리 확장 저장(q, ilters, sort_by, k, hybrid) 및 조건 복원 즉시 재검색 반영 완료
- 파일/북마크 숫자 정렬, 결과 카드 폰트 즉시 반영, 링크 툴팁 wording 정리 완료
- pyrightconfig.json, .vscode/settings.json에서 Pylance/Pyright missing-import noise 완화 및 workspace path 설정 반영 완료
- untime.py writable log fallback, 	ext_cache.py file fingerprint 기반 stale cache 보강 완료

## 2026-04-16 구현 리스크 후속 반영

- 첫 실행 상태에서 ModelInventory.snapshot()이 잠기지 않도록 refresh 경로를 정리했다.
- 폴더 로드 취소/실패 시 기존 BM25/Vector 인덱스와 결과 상태가 복구되도록 qa_system에 스냅샷 복원 로직을 추가했다.
- 임베딩 모델이 없어도 초기 폴더 스캔과 BM25-only 인덱싱이 가능하도록 검색 가능 상태를 완화했다.
- 접근 권한이 없는 하위 폴더는 전체 실패 대신 건너뛰고, 완료 메시지에서 skipped 경로 수를 안내하도록 수정했다.
- OCR 설정(ocr_enabled, ocr_mixed_pdf)을 설정 저장/복원과 UI 토글에 연결했고, 혼합 PDF에서 텍스트가 비어 있는 페이지에 OCR 보강을 적용했다.
- 검색 히스토리는 검색어만이 아니라 필터/정렬/검색 모드 전체 조합을 기준으로 dedup 하도록 바꿨다.
- 앱 종료 시 워커 취소 요청 후 짧게 completion을 기다린 다음 정리하도록 종료 순서를 보강했다.

## 연계 문서

- UI_UX_REVIEW_2026-03-25.md: 사용자 흐름 중심의 UX 후속 사항과 정합성 기록
- IMPLEMENTATION_RISK_REVIEW_2026-04-16.md: 구현 리스크 검토 항목, 수정 내용, 검증 결과
- README.md, claude.md, gemini.md: 현재 동작 기준의 사용자/개발 문서

## 검증

`ash
python -m pytest -q
python -m pyright .
`

- pytest: 전체 통과 예정 기준으로 유지
- pyright: 0 errors