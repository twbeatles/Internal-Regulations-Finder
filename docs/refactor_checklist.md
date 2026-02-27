# Refactor Verification Checklist

## 1. Static checks

- [ ] `python tools/smoke_refactor.py` 실행 시 `py_compile/import/sanity` 모두 통과
- [ ] `tools/symbol_inventory.py`로 `artifacts/symbols_after.json` 생성
- [ ] `symbols_before` 대비 `missing == 0`
- [ ] `python -m py_compile "사내 규정검색기 v9 PyQt6.spec"` 통과

## 2. App startup

- [ ] `python "사내 규정검색기 v9 PyQt6.py"` starts
- [ ] 스타일(QSS) 적용 확인
- [ ] 초기 모델 로드 상태 메시지 표시

## 3. Model flow

- [ ] 모델 로드 성공 시 검색/폴더 버튼 활성화
- [ ] 모델 변경(즉시 변경) 후 인덱스 초기화 및 재로드 동작
- [ ] 모델 로드 실패 시 폴더/검색 관련 버튼 비활성화 동작

## 4. Folder/document flow

- [ ] 폴더 선택 후 지원 파일 탐색
- [ ] 암호화 PDF 사전 감지 및 비밀번호 입력/세션 재사용 동작
- [ ] 문서 처리 진행 다이얼로그/취소 동작
- [ ] 처리 완료 후 파일 테이블/통계/캐시 크기 갱신
- [ ] 일부 실패 파일 경고 메시지 노출
- [ ] HWP 다중 섹션(`BodyText/Section*`) 추출 동작

## 5. Search flow

- [ ] 검색 수행/로딩 표시/완료 표시
- [ ] 1글자 검색어 입력 시 스레드 실행 전 즉시 안내
- [ ] 결과 카드 렌더링 + 하이라이트
- [ ] 히스토리 메뉴 표시 및 재검색
- [ ] 결과 내보내기(txt/csv)

## 6. Settings/data flow

- [ ] 설정 저장/재기동 반영 (`folder`, `model`, `font`, `hybrid`)
- [ ] 캐시 삭제(디스크+메모리) 후 검색 비활성화 및 재로드 안내
- [ ] 히스토리 삭제
- [ ] 진단 zip 내보내기
- [ ] 오프라인 모델 선택 다운로드 + 취소 응답성 확인

## 7. Shutdown

- [ ] 창 종료 시 `closeEvent`에서 설정 저장
- [ ] 실행 중 워커 cancel/wait + progress dialog 정리
- [ ] `qa.cleanup()` 호출

## 8. Smoke command

```bash
python tools/smoke_refactor.py
```

## 9. Pytest command

```bash
pytest -q
```

## 10. Symbol diff command

```bash
python tools/symbol_inventory.py --paths regfinder "사내 규정검색기 v9 PyQt6.py" --out artifacts/symbols_after.json --compare-before artifacts/symbols_before.json --compare-after artifacts/symbols_after.json
```
