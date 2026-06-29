---
title: "pip install 타임아웃 — Windows + 대용량 ML 패키지 설치"
date: 2026-06-29
category: code-error
severity: low
---

## 증상 (Symptom)

`pip install -r requirements.txt` 실행 시 5분(300초) 타임아웃 발생.
설치가 완료되었는지, 실패했는지, 진행중인지 알 수 없음.

```
[shell] shell tool terminated command after exceeding timeout 300000 ms.
```

## 시도한 해결책 (Attempted Solutions)

### 시도 1: 전체 패키지 한 번에 설치 (실패)
- `pip install -r requirements.txt` → 5분 타임아웃
- 원인: torch 2.12.1 + sentence-transformers + streamlit의 거대한 의존성 트리

### 시도 2: pip list로 이미 설치된 패키지 확인 (성공)
```powershell
pip list | Select-String "streamlit|langchain|faiss|sentence|pymupdf|arxiv|dotnet|tqdm"
```

결과:
```
faiss-cpu          1.14.3    ✅
langchain-protocol 0.0.18    ✅ (partial)
PyMuPDF            1.27.2.3  ✅
python-dotenv      1.2.2     ✅
tqdm               4.68.3    ✅
```

누락: streamlit, langchain(전체), langchain-community, langchain-ollama, sentence-transformers, arxiv

### 시도 3: 개별 패키지 그룹 설치 (성공)
```powershell
pip install streamlit langchain langchain-community langchain-ollama sentence-transformers arxiv
```
- 600초(10분) 타임아웃으로 재설정
- 성공! 모든 패키지 설치 완료
- `Successfully installed aiohttp-3.14.1 arxiv-4.0.0 ... sentence-transformers-5.6.0 streamlit-1.58.0 transformers-5.12.1 torch-2.12.1`

## 근본 원인 분석 (Root Cause)

1. **Windows에서 ML 패키지 설치가 느림**: torch 2.12.1 (2GB+), transformers 5.12.1, sentence-transformers 5.6.0 모두 큰 패키지
2. **pip resolve 시간**: 25개+ 의존성의 의존성 트리를 Windows에서 resolve하는 데 수분 소요
3. **C++ build tools 필요 여부 확인 실패**: 일부 패키지가 컴파일이 필요할 수 있으나 사전 컴파일된 wheel이 있어서 다행히 문제 없음

## 교훈 (Lesson Learned)

1. **첫 pip install은 충분히 긴 타임아웃 설정**: ML 프로젝트는 최소 10분(600초) 이상
2. **순차적 설치 고려**: torch → sentence-transformers → streamlit → langchain 순으로 설치하면 진행상황 확인 가능
3. **pip list로 사전 설치 확인**: 대부분의 패키지가 이미 Python 3.13에 설치되어 있었음

## 최종 코드 / Fix (Resolution)

```powershell
# 타임아웃 10분으로 증가
pip install -r requirements.txt --timeout 600
# 또는 이미 설치된 패키지가 많다면:
pip install streamlit langchain langchain-community langchain-ollama sentence-transformers arxiv
```

모든 패키지 설치 성공. Import chain 검증 완료.
