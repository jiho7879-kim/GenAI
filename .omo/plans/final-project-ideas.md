# Final Project 아이디어 — Samsung Gen AI Intensive Course

> **과정**: 삼성전자 Gen AI 인텐시브 과정 (3차수, 2026.6.29~7.10)  
> **평가 비중**: 프로젝트 50% (중간 25% + 기말 25%)  
> **프로젝트 기간**: 7/8(화) ~ 7/10(목) — 3일 (24H)  
> **제출**: 마지막날 23:59까지 구글 설문(드라이브 링크)  
> **환경**: CPU-only (Intel Iris Xe, 32GB RAM), Ollama + Zen Free Hybrid, Streamlit, Langchain/Langgraph, MCP

---

## 📋 프로젝트 선정 기준

| 기준 | 설명 |
|---|---|
| **3일 안에 완성 가능** | 24H = 기획 4H + 개발 14H + 테스트/발표 6H |
| **모듈 전범위 커버** | Transformer 이해 → RAG → Multi-Agent → Streamlit 시각화 |
| **현업 연관성** | 삼성 DS(반도체) 실제 업무 데이터/시나리오 활용 |
| **데이터 접근성** | 사외망(비보안)에서 구할 수 있는 public 데이터 |
| **로컬 구동 가능** | Ollama qwen3.5 모델 기준, API 키 불필요 |
| **시연 임팩트** | Streamlit 대시보드로 눈에 보이는 결과물 |

---

## 🏆 추천 프로젝트 (채점자 관점 반영)

---

### 1. 🔥 Hot Pick: 반도체 공정 이상감지 Agentic RAG 시스템

**난이도**: ⭐⭐⭐⭐  
**모듈 커버**: Transformer + RAG + Multi-Agent + Streamlit

#### 개요
```
사용자 질문 → Supervising Agent
                  ├── RAG Agent (SEM defect DB 검색)
                  ├── Analysis Agent (유사사례 비교/분석)  
                  └── Report Agent (종합 리포트 생성)
                              ↓
                    Streamlit Dashboard 출력
```

#### 데이터
- **SECS/GEM** 통신 프로토콜 문서 (public)
- 반도체 공정 장비 매뉴얼 PDF들
- wafer defect 패턴 이미지 설명 데이터
- 공정 파라미터 로그 샘플 (SEMI 표준 기반 합성 데이터)

#### 상세 시나리오
```
User: "Particle defect가 Oxide CMP 후에 자주 발생하는데 
       가능한 원인과 체크할 파라미터를 알려줘"

① Supervising Agent: 의도 분류 → RAG Agent 호출
② RAG Agent: 공정 매뉴얼 + defect DB에서 관련 레코드 검색
③ Analysis Agent: "Particle → Slurry残留, Pad Conditioning 불량" 분석
④ Report Agent: 파라미터 체크리스트 + 액션플랜 생성
⑤ Streamlit: 대화형 리포트 + 공정 파라미터 시각화
```

#### Streamlit 구조
```python
# 제안하는 UI 구성
st.title("반도체 공정 이상감지 Assistant")
col1, col2 = st.columns(2)
with col1:
    st.chat_input("질문 입력")
    # 채팅 히스토리
with col2:
    st.subheader("RAG 검색 결과")
    st.dataframe(retrieved_chunks)
    st.subheader("Agent Reasoning Trace")
    st.json(agent_thought_process)
```

#### 평가 포인트
| 항목 | 비중 | 설명 |
|---|---|---|
| Agent 설계 | 30% | Multi-Agent 구조, 역할 분담의 적절성 |
| RAG 품질 | 25% | Chunking 전략, 검색 정확도 |
| UI 완성도 | 20% | Streamlit, 사용자 경험 |
| 현업 연관성 | 15% | 실제 업무 활용 가능성 |
| 발표 | 10% | 문제 정의 → 해결 과정 → 인사이트 |

---

### 2. 💼 Practical Pick: 설비 고장예지 Agent (Predictive Maintenance)

**난이도**: ⭐⭐⭐  
**모듈 커버**: LLM + RAG + Agent + Streamlit

#### 개요
```
PM history DB 장비 센서 데이터
      ↓           ↓
  RAG (문서) + Analysis (수치)
      ↓           ↓
  Supervisor Agent → 통합 진단 리포트
```

#### 데이터
- https://archive.ics.uci.edu/ — SECOM (Semiconductor Manufacturing)
- Kaggle: Predictive Maintenance Dataset
- 설비 PM(Preventive Maintenance) 이력 (합성)

#### 시나리오 예시
```
"Dry Etcher #03의 최근 7일간 Pressure 변동 추이를 분석하고
이상 징후가 있다면 관련 PM 이력과 함께 리포트를 작성해줘"
```

---

### 3. 🧠 Technical Pick: 논문 기반 Transformer 비교 실험 도구

**난이도**: ⭐⭐⭐  
**모듈 커버**: Transformer 이해 + Streamlit 시각화 (RAG/Agent 최소)

#### 개요
수업에서 배운 Transformer 개념을 직접 **시각화하고 실험**할 수 있는 교육용 도구

#### 주요 기능
```python
# Self-Attention 시각화
st.subheader("Scaled Dot-Product Attention")
seq_len = st.slider("시퀀스 길이", 2, 10, 4)
d_model = st.selectbox("d_model", [64, 128, 256, 512])
```

1. **Self-Attention 시각화**: Q, K, V 행렬 → Attention heatmap
2. **Positional Encoding**: sin/cos 곡선 그리기, pos별 거리 계산
3. **Multi-Head 비교**: 서로 다른 head의 attention 패턴 비교
4. **GPT/BERT 구조 비교**: Masked vs bidirectional attention 차이

#### 평가 포인트
- Transformer 수업 내용의 이해도 (50%)
- 시각화의 직관성 (30%)
- 코드 품질 (20%)

> ⚠️ **단점**: Agent/RAG를 거의 사용하지 않으므로 M2/M3 학습내용 반영 어려움. 프로젝트 점수에서 불리할 수 있음.

---

### 4. 🔍 Research Pick: 사내 규정 준수 Agentic RAG

**난이도**: ⭐⭐⭐⭐  
**모듈 커버**: RAG + Multi-Agent + Streamlit

#### 개요
```
"이 설계 변경이 어떤 안전 규정에 위배되나요?"
  → Safety Agent (규정 검색)
  → Compliance Agent (위반 조항 추출)
  → Risk Agent (리스크 레벨 판단)
  → Report Agent (요약 리포트 + 참조 문서 링크)
```

#### 데이터
- 산업안전보건법 PDF (public)
- 반도체 안전 규정 샘플 (공개 자료)
- ISO 45001 문서

#### 장점
- **실제 수요 있음**: 현업에서 컴플라이언스 체크는 매일 필요한 업무
- **데이터 구축 용이**: 공개 규정 문서만으로도 충분
- **확장성**: 이후 진짜 사내 규정으로 쉽게 전환 가능

---

### 5. ⚡ Simple but Solid: 설비 장애 대응 Knowledge Base Assistant

**난이도**: ⭐⭐  
**모듈 커버**: RAG + Single Agent + Streamlit

#### 개요
가장 기본적이지만 **완성도**에 집중한 프로젝트

```
사용자: "동탄 EUV 스캐너에서 웨이퍼 정렬 실패 에러가 났어요"
  → RAG: 장애 대응 메뉴얼 검색
  → LLM: 단계별 조치사항 생성
  → Streamlit: 대화형 UI + 메뉴얼 원문 표시
```

#### 추천 이유
- 3일 안에 **완성 보장**
- RAG 파이프라인에 집중 → 깊이 있는 학습 증명 가능
- 유지보수 매뉴얼은 모든 공장에 존재 → 실제 PoC로 연결 쉬움

#### 그러나 단점
- Agent 활용도 낮음 → Multi-Agent 파트에서 점수 감점 가능
- 단순 RAG 챗봇은 차별화 어려움

---

## 📊 프로젝트 난이도 vs 점수 예측 매트릭스

```
점수
  ↑
 100│    ★4 (Agentic RAG + 
 95 │     현업 연계)        ★3 (규정 준수)
 90 │                         
 85 │              ★3 (설비예지)
 80 │
 75 │    ★2 (단순 RAG)  ★3 (Transformer 시각화)
 70 │
    └──────────────────────────────→ 난이도
      하              중              상
```

---

## 🗓️ 3일 프로젝트 타임라인 예시 (Top Pick 기준)

### Day 1 (7/8, 화) — 기획 + 데이터 준비

| 시간 | 작업 | 세부 내용 |
|---|---|---|
| 08:30~09:30 | 프로젝트 가이드라인 안내 | 주제 선정, 일정 계획 |
| 09:30~11:00 | **주제 선정 + 기획안 작성** | 문제 정의, 데이터 확보 방안 |
| 11:00~12:00 | 데이터 수집 | 공정 매뉴얼 PDF, 합성 데이터 생성 |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | **Data Ingestion** | PDF → chunking → vector store (FAISS) |
| 15:00~16:00 | Baseline RAG 구축 | Langchain retrieval chain |
| 16:00~17:00 | 자습/보강 | RAG 성능 테스트 |

### Day 2 (7/9, 수) — 핵심 개발

| 시간 | 작업 |
|---|---|
| 08:30~10:00 | **Multi-Agent 구조 설계** (Langgraph) |
| 10:00~12:00 | Supervisor Agent + RAG Agent 구현 |
| 12:00~13:00 | 중식 |
| 13:00~15:00 | Analysis Agent + Report Agent 구현 |
| 15:00~17:00 | **Streamlit UI 연동** (채팅 + Agent trace 표시) |
| 16:00~17:00 | 자습/보강 |

### Day 3 (7/10, 목) — 완성 + 발표

| 시간 | 작업 |
|---|---|
| 08:30~10:00 | 통합 테스트 + 디버깅 |
| 10:00~12:00 | **Edge case 처리** (OOM, chunking 최적화) |
| 12:00~13:00 | 중식 |
| 13:00~15:00 | **README/발표자료 준비** + 시연 스크립트 |
| 15:00~16:00 | 최종 점검 + 제출 |
| 16:00~17:00 | 시연 리허설 |
| 17:00~17:20 | **최종 평가** |

---

## ⚠️ 주의사항 (경험 기반)

### 환경 제약

| 제약 | 대책 |
|---|---|
| **사외망** → Knox 접속 불가 | Public 데이터만 사용. API 키가 필요한 서비스(OpenAI 등) 사용 불가 → **로컬 Ollama**로 모든 추론 처리 |
| **CPU-only** (iGPU 1GB) | qwen3.5:4b (3.4GB) 추천. chunk size 500~1000 이하. 가능하면 임베딩은 `all-MiniLM-L6-v2` 같은 경량 모델 사용 |
| **Ollama 컨텍스트 윈도우** | qwen3.5:4b의 ctx window 확인. 너무 긴 문서는 Map-Reduce split 필요 |
| **FAISS (메모리)** | 임베딩 벡터 수가 많으면 RAM 부족 → 100~200 chunk로 제한 |

### 프로젝트 점수 전략

| 항목 | 조언 |
|---|---|
| **50% = 프로젝트** | 시험보다 프로젝트 비중이 2배 큼. 시험 공부보다 **프로젝트 완성도**에 집중 |
| **Agent 구조 설계** | 단순 RAG보다 Multi-Agent가 고득점. Supervisor + Specialist 패턴 권장 |
| **발표 자료** | README에 프로젝트 구조도, Agent 흐름도, 실제 실행 결과 스크린샷 포함 |
| **에러 핸들링** | "어떤 어려움이 있었고 어떻게 해결했는가"가 차별화 포인트 |
| **실패 인정** | 안 된 부분을 솔직히 공유하고 원인 분석을 하면 오히려 가산점 |

---

## 📁 프로젝트 제출 체크리스트

- [ ] `README.md` — 프로젝트 개요, 설치/실행 방법, 구조도
- [ ] `architecture.png` — Agent 설계 다이어그램
- [ ] `demo.mp4` or `screenshots/` — 실제 실행 결과 (3~5장)
- [ ] `requirements.txt` — 의존성 목록
- [ ] `src/` — 전체 소스코드
- [ ] `data/` — 사용한 데이터 (용량 클 경우 샘플만)
- [ ] `presentation.pdf` — 발표자료 (문제 정의 → 접근법 → 결과 → 인사이트)

---

## 💡 추가 팁

### "나의 업무에서 분석해 볼 만한 데이터는?"
→ 3일차에 교수님이 던진 이 질문에 프로젝트 발표 때 답할 수 있어야 함

| 직무 | 추천 데이터 |
|---|---|
| 공정/제조 | Particle map, 수율 데이터, 설비 로그 |
| 설비/장비 | PM 이력, 센서 시계열, 알람 로그 |
| 품질/분석 | 불량 분석 리포트, SPC 데이터 |
| 물류/SCM | 재고 데이터, 리드타임, 공급사 정보 |
| EHS/안전 | 안전 점검표, 사고 이력, MSDS |

### 발표 5분 스크립트 뼈대
```
1. (30초) 문제 정의 — "우리 공장에서 이런 불편함이 있었다"
2. (1분) 접근법 — "Transformer 기반 LLM으로 ~~하고, RAG로 ~~하고, Multi-Agent로 ~~"
3. (2분) 시연 — 실제 실행 라이브 데모
4. (1분) 기술적 인사이트 — "가장 어려웠던 점은 ~~였고, 이렇게 해결했다"
5. (30초) 현업 적용 계획 — "이걸 실제로 도입하면 ~~ 효과를 기대한다"
```

> **최종 추천**: **Top Pick (반도체 공정 이상감지 Agentic RAG)** —  
> Transformer → RAG → Multi-Agent → Streamlit 전 범위 커버,  
> 현업(삼성 DS) 연관성 높음, 3일 안에 개발 가능, 시연 임팩트 좋음.
