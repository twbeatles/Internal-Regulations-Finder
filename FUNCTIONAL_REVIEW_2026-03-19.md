# 기능 구현 점검 리뷰 및 반영 상태 (2026-03-19)

이 문서는 2026-03-19 기준 기능 구현 점검 결과와 반영 상태를 함께 정리한 기록이다.

## 원래 점검 포인트

1. GUI에서 `bm25_only` fallback 검색이 실제로 가능한지
2. 수정 파일 재추출 실패 시 stale cache가 남지 않는지
3. 암호화 PDF 비밀번호 입력이 UI까지 연결되어 있는지
4. frozen(onefile) 다운로드 취소 semantics가 사용자에게 명확한지
5. 하이라이트가 검색 정규화 규칙과 일치하는지
6. CSV 내보내기가 안전한지
7. 캐시 삭제 후 UI 상태가 런타임 상태와 일치하는지

## 반영 상태

- `bm25_only` 검색 진입 차단 제거: 완료
- 수정 파일 stale cache 제거: 완료
- 암호화 PDF 사전 비밀번호 입력 + 세션 메모리 재사용: 완료
- frozen(onefile) 다운로드 취소 안내/결과 메시지 보강: 완료
- 검색 정규화 기반 하이라이트 보강: 완료
- 검색 결과/북마크 CSV 내보내기 `csv` 모듈 기반 정리: 완료
- 캐시 삭제 후 파일/결과/버튼 상태 재동기화: 완료

## 코드/문서 정합성 체크 결과

- `README.md`: 현재 사용자 동작 기준으로 갱신
- `claude.md`: 개발/운영 메모 기준으로 갱신
- `gemini.md`: 구조/운영 규칙 기준으로 갱신
- `PROJECT_STRUCTURE_ANALYSIS.md`: 최근 반영 항목과 테스트 목록 갱신
- `docs/refactor_mapping.md`, `docs/refactor_checklist.md`: 체크 항목과 단계 매핑을 최신 동작 기준으로 보강
- `사내 규정검색기 v9 PyQt6.spec`: onefile 취소 semantics 및 PDF 비밀번호 메모 반영
- `.gitignore`: 포터블 실행 시 생성되는 JSON 상태 파일, `models/`, `logs/`, 진단 zip, 결과/북마크 내보내기 이름을 이미 포괄하고 있어 추가 수정 불필요 확인

## 검증

```bash
python -m pytest -q
python -m pyright .
```

- `pytest`: 전체 통과
- `pyright`: 0 errors
