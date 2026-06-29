---
title: "Ingest Metadata Persistence — FAISS 옆에 JSON 메타데이터 파일 추가"
date: 2026-06-29
category: decision
severity: medium
---

## 증상 (Symptom)

Streamlit 앱을 새로고침하면 `st.session_state.ingested_files`가 초기화되어 사이드바에 "No papers ingested yet."만 표시됨. FAISS 인덱스는 디스크에 영구 저장되지만, 어떤 파일이 들어있는지 추적할 방법이 없어 사용자가 매번 PDF를 다시 업로드해야 한다고 착각함.

## 시도한 해결책 (Attempted Solutions)

1. **session_state만 사용** → Streamlit 특성상 페이지 새로고침 시 모든 state 소멸. 근본적인 해결책 아님.
2. **FAISS Document metadata에서 파일명 추출** → 가능하지만 FAISS 로딩이 필요해 무거움. 빈번한 UI 업데이트에 부적합.

## 근본 원인 분석 (Root Cause)

- FAISS 인덱스(`index.faiss` + `index.pkl`)는 영구 저장됨
- 하지만 **어떤 파일이 언제 ingest되었는지**에 대한 메타데이터가 없음
- `ingested_files` 목록이 session state에만 있어서 refresh 시 사라짐
- UI는 `ingested_files`가 비어있으면 "No papers ingested yet."만 표시 → RAG가 실제로는 작동 가능함에도 불구하고 잘못된 인상

## 교훈 (Lesson Learned)

- 영구 저장소(FAISS index) 옆에 사람이 읽을 수 있는 메타데이터 파일을 함께 두면 디버깅과 UI 업데이트에 유리함
- JSON은 스키마 변경에 유연하고, git diff도 가능함
- Migration 고려: 기존 FAISS만 있는 환경에서도 UI가 정상 동작해야 함

## 최종 코드 / Fix (Resolution)

### `src/ingest.py`에 추가된 함수들:

| 함수 | 역할 |
|------|------|
| `save_ingest_metadata()` | ingest 성공 시 `vectorstore/ingest_metadata.json`에 기록 |
| `load_ingest_metadata()` | JSON 파일 읽기 (없으면 빈 dict) |
| `get_ingested_files()` | 등록된 파일명 리스트 반환 |
| `remove_ingest_metadata()` | 특정 파일 메타데이터 삭제 |

### `app.py` 변경사항:

1. 사이드바에서 `load_ingest_metadata()`로 파일 목록 로드 (page 수, chunk 수 표시)
2. 최초 로드 시 `get_ingested_files()`를 `st.session_state.ingested_files`에 주입
3. migration fallback: metadata가 없고 FAISS만 있는 경우 "N vectors available" 표시
4. About 탭의 "Papers Ingested" 메트릭도 persistent metadata 기반으로 변경

### Metadata JSON Schema:

```json
{
  "files": {
    "paper1.pdf": {
      "ingested_at": 1719567890.0,
      "chunks": 42,
      "pages": 10,
      "path": "data/papers/paper1.pdf"
    }
  }
}
```

### Migration 처리:

기존에 `vectorstore/index.faiss`만 존재하는 환경(metadata가 없는 환경)에서도 앱이 정상 동작하도록 fallback 추가:
```python
elif store_info["exists"] and store_info["vector_count"] > 0:
    st.caption(f"📚 {store_info['vector_count']} vectors available (previously ingested)")
```
