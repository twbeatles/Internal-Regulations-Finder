# 🤖 Gemini AI Guidelines: 사내 규정 검색기 v9.3

## 핵심 상태

- 단일 스크립트 구조 → `regfinder` 패키지 구조로 분리 완료
- 2차 리팩토링: UI 빌더/설정·진단 로직/QA 진단 로직을 믹스인으로 추가 분리
- 워커 관리는 `WorkerRegistry`로 통합
- 설정은 `ConfigManager`(schema_version=2) 기반으로 마이그레이션 처리

## 현재 사용자 기능

- 검색 필터: 확장자/파일명/경로
- 검색 정렬: 점수순/파일명순/최근 수정순
- 결과 북마크 저장/내보내기
- 최근 폴더 다중 관리
- 진단 탭(인덱스 상태 + 검색 로그 요약)
- 오류 코드별 가이드 메시지

## 운영 규칙

1. 워커 `run()`에서 UI 직접 변경 금지
2. 시그널 기반으로만 UI 업데이트
3. 검색/인덱스 상태는 `RegulationQASystem` public API를 통해 조회
4. 종료 시 워커 취소 및 리소스 정리

## 검증 명령

```bash
python tools/smoke_refactor.py
python -m unittest discover -s tests -v
pytest -q
```
