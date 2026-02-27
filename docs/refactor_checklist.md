# Refactor Verification Checklist

## 1. Static checks

- [ ] `python tools/smoke_refactor.py` 통과
- [ ] `python -m py_compile "사내 규정검색기 v9 PyQt6.spec"` 통과
- [ ] `python -m unittest discover -s tests -v` 통과
- [ ] `pytest -q` 통과

## 2. App startup

- [ ] 앱 실행/초기 모델 로드 상태 표시
- [ ] 모델 로드 결과에 따른 검색/폴더 버튼 활성화

## 3. Search UX

- [ ] 확장자/파일명/경로 필터 동작
- [ ] 정렬(점수/파일명/최근 수정) 동작
- [ ] 결과 카드 하이라이트/복사/북마크 동작
- [ ] 결과 내보내기(txt/csv) 동작

## 4. Folder/document flow

- [ ] 최근 폴더 목록 표시 및 재로드
- [ ] 암호화 PDF 비밀번호 입력/세션 재사용 동작
- [ ] 문서 처리 진행/취소 동작
- [ ] 처리 후 파일 통계/캐시 크기 갱신

## 5. Diagnostics and errors

- [ ] 진단 탭 인덱스 상태 표시
- [ ] 검색 로그 요약 표시
- [ ] 진단 zip 내보내기 동작
- [ ] 오류 코드별 가이드 메시지 표시

## 6. Shutdown

- [ ] 종료 시 설정 저장
- [ ] 실행 중 워커 취소 처리
- [ ] `qa.cleanup()` 호출
