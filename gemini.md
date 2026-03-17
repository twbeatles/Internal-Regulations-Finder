# 🤖 Gemini AI Guidelines: 사내 규정 검색기 v9.3

## 핵심 상태

- 단일 스크립트 구조 → `regfinder` 패키지 구조로 분리 완료
- 2차 리팩토링: UI 빌더/설정·진단 로직/QA 진단 로직을 믹스인으로 추가 분리
- 워커 관리는 `WorkerRegistry`로 통합
- 설정은 `ConfigManager`(schema_version=2) 기반으로 마이그레이션 처리
- 정적 분석 기준은 `pyrightconfig.json`으로 고정
- frozen(onefile) 모델 다운로드는 subprocess 대신 in-process 경로 사용
- 오프라인 임베딩 런타임은 `Pillow` / `scikit-learn` / `sentence_transformers` 사전검증 추가
- 전역 QSS는 화면 컨테이너 단위 배경 적용으로 조정되어 라벨 배경 덮어쓰기 회귀를 방지
- 모델 다운로드 상태는 Hugging Face 로컬 캐시(`models--.../blobs`, `snapshots`) 기준으로 판별

## 현재 사용자 기능

- 검색 필터: 확장자/파일명/경로
- 검색 정렬: 점수순/파일명순/최근 수정순
- 결과 북마크 저장/내보내기
- 최근 폴더 다중 관리
- 진단 탭(인덱스 상태 + 검색 로그 요약)
- 오류 코드별 가이드 메시지
- 다운로드 실패 시 `op_id`와 실제 import 실패 패키지명을 함께 노출
- 모델 로드 성공 직후 검색창 입력 가능
- 설정창 모델 목록은 다운로드 완료 모델을 상단 우선 정렬

## 운영 규칙

1. 워커 `run()`에서 UI 직접 변경 금지
2. 시그널 기반으로만 UI 업데이트
3. 검색/인덱스 상태는 `RegulationQASystem` public API를 통해 조회
4. 종료 시 워커 취소 및 리소스 정리
5. 추적 텍스트 파일은 `.editorconfig`, `.gitattributes` 기준으로 `UTF-8(no BOM)` / `LF` 유지
6. PyInstaller 경량화 시 `PIL` / `Pillow` / `scikit-learn` 제외 여부를 먼저 검토

## 검증 명령

```bash
pyright .
python tools/smoke_refactor.py
python -m py_compile "사내 규정검색기 v9 PyQt6.spec"
python -m unittest discover -s tests -v
pytest -q
```
