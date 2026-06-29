---
title: "Langchain 모듈 경로 변경 — langchain.chains → langchain_classic.chains"
date: 2026-06-29
category: code-error
severity: medium
---

## 증상 (Symptom)

`from langchain.chains import RetrievalQA` 실행 시 ModuleNotFoundError 발생.

```
ModuleNotFoundError: No module named 'langchain.chains'
```

## 시도한 해결책 (Attempted Solutions)

### 시도 1: langchain.text_splitter도 같은 문제 확인
`from langchain.text_splitter import RecursiveCharacterTextSplitter` → 동일한 ModuleNotFoundError

두 모듈 모두 langchain 1.x에서 standalone 패키지로 분리됨.

### 시도 2: 설치된 패키지 확인
```python
import langchain
print(langchain.__version__)  # 1.3.11
```

`langchain 1.3.11`에서는 `langchain.chains`와 `langchain.text_splitter`가 제거되고
`langchain_classic`과 `langchain_text_splitters`로 분리됨.

### 해결: standalone 패키지 import로 변경

```python
# BEFORE (실패)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA

# AFTER (성공)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.chains import RetrievalQA
```

## 근본 원인 분석 (Root Cause)

Langchain 생태계가 modular architecture로 전환되면서:
- `langchain.chains` → `langchain-classic` 패키지의 `langchain_classic.chains`
- `langchain.text_splitter` → `langchain-text-splitters` 패키지의 `langchain_text_splitters`

이미 `pip install langchain` 시 의존성으로 함께 설치되지만, import 경로가 변경됨.

## 교훈 (Lesson Learned)

1. **requirements.txt에 버전 제한을 걸더라도 Pipfile.lock이 없으면 최신 버전 설치됨**
   - `langchain>=0.3.0` → 실제 설치: 1.3.11 (API 변경 있음)
   - 해결: `langchain==0.3.0`으로 고정하거나, new API 경로 사용
2. **최초 import 테스트는 필수**: 모든 프레임워크 업데이트로 인한 호환성 문제는 실행해봐야 앎
3. **requirements.txt 업데이트 필요**: 정확한 버전을 명시하거나, 설치 확인 후 업데이트

## 최종 코드 / Fix (Resolution)

변경 파일:
- `src/ingest.py` line 21: `langchain.text_splitter` → `langchain_text_splitters`
- `src/rag_chain.py` line 14: `langchain.chains` → `langchain_classic.chains`
