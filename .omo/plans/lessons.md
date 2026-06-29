# Lessons Learned — GEN-AI Transformer PDF 가공 프로젝트

> **세션**: 2026-06-29  
> **목적**: [강의자료1]GEN-AI_Transformer.pdf 150페이지 → 중간고사 학습자료  
> **작성**: 프로젝트 종료 후 retrospective

---

## 🔴 Critical (반드시 고쳐야 할 실수)

### 1. PDF 한국어 텍스트 추출 — 삽질 타임라인

| 시도 | 도구 | 결과 | 소요 시간 |
|---|---|---|---|
| 1차 | `pdftotext -raw` | ❌ 깨짐 | 5분 |
| 2차 | PyMuPDF (`fitz`) | ❌ 깨짐 | 15분 |
| 3차 | `pdfjs-dist` (Node.js) | ❌ 깨짐 | 20분 |
| 4차 | `pdf-parse` (Node.js) | ❌ 깨짐 | 10분 |
| 5차 | `pdftotext` 인코딩 옵션 변경 | ❌ 깨짐 | 10분 |

**총 낭비: ~60분**

**✅ 교훈**: PDF 한국어 텍스트가 깨지면 **즉시 OCR로 전환**할 것. `pdftotext` 1~2회 실패 시 더 붙잡지 말고 곧바로 tesseract 설치로 넘어간다.

**🔬 원인 분석**:
- 해당 PDF는 **font subsetting**이 적용되어 있어 일반 extractor가 내부 폰트 매핑을 읽지 못함
- 또는 CID(CIDFont) 매핑이 TrueType Collection의 특정 서브셋을 참조
- PyMuPDF/pdfjs-dist는 일부 CJK CID 폰트에서 실패

**✅ Fix**: 
```powershell
scoop install poppler tesseract tesseract-languages
# poppler: pdftopng (page→image 변환용)
# tesseract: OCR engine
# tesseract-languages: kor+eng 언어팩
```

---

### 2. `look_at` on PNG — 120s 타임아웃

| 시도 | 대상 | 결과 |
|---|---|---|
| `look_at(page-48.png)` | Transformer 아키텍처 도식 | ❌ 120s timeout |
| `look_at(page-54.png)` | Self-Attention 계산 도식 | ❌ 120s timeout |

**✅ 교훈**: `look_at`(multimodal-looker)이 120s 이상 걸리면 **하드 타임아웃**이 발생하며 결과를 얻을 수 없다. 다음 전략 중 하나를 써야 함:

1. **OCR 텍스트 + 도메인 지식**으로 대체 (본 프로젝트에서 사용)
2. 더 작은 이미지로 리사이즈 후 재시도 (미검증)
3. 로컬 Ollama multimodal 모델 (예: `qwen3.5:9b`는 텍스트 전용이라 불가. LLaVA 계열 모델 필요)

---

### 3. PowerShell 환경 차이 간과

| 문제 | 설명 |
|---|---|
| `&&` 사용 불가 | PowerShell 5.1은 `&&` 미지원 → `; if ($?) { ... }` 필요 |
| 경로 공백 처리 | `C:\Users\User\Documents\GenAI\00. 교안\...` — 공백+한글 경로 조합 |
| `Get-Content` 기본 인코딩 | PowerShell 5.1의 `Get-Content`는 BOM 없는 UTF-8을 제대로 읽지 못함 |

**✅ 교훈**: 스크립트 명령을 작성할 때 환경(win32/PowerShell 5.1)을 먼저 인지하고, `&&` 대신 PowerShell 조건문을 사용할 것. 파일 읽기는 `Read` 툴을 쓰는 것이 가장 안전.

---

### 4. tesseract 한국어 OCR 품질

| 상황 | 품질 | 예시 |
|---|---|---|
| 본문 한글 텍스트 | 양호 (90%+) | "트랜스포머는 인코더-디코더 구조" |
| 도식 내 한글+영문 혼합 | 보통 (60~80%) | `FOX 01591 Hh(e)Vd` 같은 garbled |
| 수식/숫자 | 낮음 (40~60%) | `3.4 5E` → 의도: `3.5B` |

**✅ 교훈**: 
- OCR 출력을 **그대로 신뢰하지 말 것** — 특히 수식과 숫자
- Post-processing: 도메인 지식을 이용한 후보정 필수
- 시험 자료로 쓸 때는 OCR 원문보다 **enriched version**을 만들 것

---

### 5. 너무 많은 PDF 라이브러리 serial 시도

**✅ 교훈**: 문제가 발생하면 **3번의 실패**를 기준으로 삼아라. 3번 실패 후에는 접근법 자체를 바꾸고(텍스트 추출 → OCR), 이전 접근법은 완전히 포기할 것. 같은 카테고리(pdf text extractor)의 다른 도구를 계속 시도하는 것은 **극도의 비효율**.

---

## 🟡 Warning (주의할 점)

### 6. 긴 경로 + 한글 = 툴에 따라 오류

일부 툴이 `C:\Users\User\Documents\GenAI\00. 교안\` 경로를 제대로 처리하지 못함.

**✅ 교훈**: MCP/agent 툴에 한글 경로를 넘길 때는 `$env:TEMP\opencode\` 같은 ASCII 전용 경로로 파일을 복사하거나, 경로를 큰따옴표로 감싸서 전달.

### 7. 150페이지 PDF → OCR에 ~30분 소요

페이지 당 평균 3~5초, 150페이지 = ~10분. 여기에 tesseract 로딩 시간까지 포함 시 실시간 대기 필요.

**✅ 교훈**: 대용량 OCR은 **background task**로 실행하고 기다려야 함. 한 번에 150페이지를 한 번에 돌리면 중간에 실패했을 때 재시도 비용이 큼. **페이지 단위로 나누어** OCR하는 것이 안전:

```powershell
# Bad: for f in *.png; do tesseract $f stdout -l kor+eng > $f.txt; done
# → 하나 실패하면 전체 재시도

# Good: 개별 실행 + 개별 결과 확인
tesseract page-1.png stdout -l kor+eng > page-1.txt
tesseract page-2.png stdout -l kor+eng > page-2.txt
```

### 8. Ollama 모델 메모리 관리

| 모델 | 크기 | CPU only 환경 비고 |
|---|---|---|
| qwen3.5:9b | 6.6GB | 32GB RAM에서 구동 가능 (느림) |
| qwen3.5:4b | 3.4GB | 빠름, 충분히 usable |
| qwen2.5-coder:7b | 4.7GB | 코딩용으로만 사용 |

CPU-only(iGPU 1GB) 환경이므로 추론 속도가 느림. Agent용 모델과 직접 사용 모델을 분리할 것.

---

## 🟢 Keep (잘한 점)

### 9. 단계적 접근법

```
PDF 거절 (text extract 실패) → poppler/tesseract 설치 → PNG 변환 → OCR → 분석 → 학습자료
```
각 단계를 병렬이 아닌 **명확한 순차 의존성**으로 분리하여 진행함. ← 올바름.

### 10. 빈약한 OCR → domain knowledge enrichment

OCR 결과의 품질이 낮았던 부분(수식, 그림 설명)을 Transformer/LLM 분야 도메인 지식으로 보강함. 특히:
- Scaled Dot-Product Attention 수식 명확화
- Self-Attention 행렬 연산 과정 상세화
- Positional Encoding sin/cos 설명 재구성
- GPT/BERT 비교 분석

### 11. 학습자료에 다이어그램 텍스트 재구성 포함

`look_at` 타임아웃에도 불구하고, OCR로 읽은 내용과 Transformer 논문 원 지식을 결합하여 **텍스트 기반 다이어그램**을 재구성함 (섹션 13).

---

## 📋 Action Items for Next PDF Project

- [ ] 한국어 PDF 만나면 `pdftotext` 1회 시도 → 실패 시 **즉시 tesseract OCR** 경로로 전환
- [ ] tesseract는 페이지 단위로 나누어 OCR
- [ ] `look_at`은 해당 도구가 개선될 때까지 사용 보류 (대신 domain knowledge로 대체)
- [ ] 한글 경로 파일은 작업 전에 ASCII 전용 경로로 복사
- [ ] PowerShell 명령어는 `&&` 대신 `; if ($?) { }` 패턴 사용
- [ ] 수식/숫자 OCR 출력은 반드시 검증
- [ ] CPU-only 환경에서는 qwen3.5:4b(3.4GB)를 기본값으로, 무거운 작업만 qwen3.5:9b(6.6GB) 사용
- [ ] 3회 동일 카테고리 실패 시 **접근법 자체를 전환**할 것
