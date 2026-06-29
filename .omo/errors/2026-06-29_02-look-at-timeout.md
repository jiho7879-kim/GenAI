# [2026-06-29] look_at (multimodal-looker) 120s 타임아웃

## 분류
- [x] Environment Issue: MCP/agent polling timeout
- [ ] Code Error
- [ ] Direction Error
- [ ] Performance Issue

## 상황
- 의도: PDF page PNG 이미지(48, 54, 55, 61번)를 분석하여 Transformer 아키텍처 도식 설명 추출
- 발생: 모든 호출이 120초 이후 hard timeout
- 원인 추정: multimodal-looker agent가 CPU-only 환경에서 이미지 처리 완료 전에 polling timeout 도달

## 실패 기록
```python
# 실패한 호출 (전부 120s timeout)
look_at(file_path="page-48.png", goal="Transformer 아키텍처 설명")
look_at(file_path="page-54.png", goal="Self-Attention 행렬 연산 설명")
```

## 수정 기록
look_at을 사용할 수 없었으므로, **OCR 텍스트 + 도메인 지식**으로 대체:
1. OCR로 읽은 page 내용에서 도식 관련 키워드/구조 추출
2. Transformer 논문("Attention is All You Need")에 대한 도메인 지식으로 내용 재구성
3. 텍스트 기반 ASCII 다이어그램으로 시각적 내용 대체

```markdown
# 예시: Self-Attention 행렬 연산을 텍스트로 재구성
```
Q (Query)      K (Key)        Q·K^T        Softmax      Attention Value
   ↓             ↓               ↓             ↓              ↓
 [d_k×N]   ×  [N×d_k]   =   [N×N]     →   [N×N]    ×   [N×d_v]  =  [N×d_v]
```
```

## 차이점 분석
- `look_at`(multimodal-looker)은 polling 기반 → 처리 시간이 120s를 넘으면 결과를 얻을 수 없음
- OCR 텍스트 + 도메인 지식 조합은 100% 정확하지 않지만, 구조적 이해에는 충분

## 재발 방지
- `look_at` 의존 금지 (해당 도구 개선 전까지)
- 대안 1: OCR 텍스트 + 도메인 지식 (지금 사용)
- 대안 2: 이미지를 절반 크기로 리사이즈 후 재시도
- 대안 3: 로컬 multimodal 모델(LLaVA 등)을 Ollama에 올려서 처리
