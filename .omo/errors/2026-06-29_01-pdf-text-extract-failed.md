# [2026-06-29] PDF 한국어 텍스트 추출 실패

## 분류
- [x] Environment Issue: PDF 인코딩/폰트 호환성 문제
- [ ] Code Error
- [ ] Direction Error
- [ ] Performance Issue

## 상황
- 의도: [강의자료1]GEN-AI_Transformer.pdf 150페이지에서 한국어 텍스트 추출
- 발생: pdftotext, PyMuPDF, pdfjs-dist, pdf-parse 전부 깨짐 (한글이 � 또는 garbled)
- 원인 추정: PDF 내 font subsetting으로 인해 일반 extractor가 내부 CID 폰트 매핑을 읽지 못함

## 실패 기록

### 시도 1: pdftotext (poppler)
```powershell
pdftotext -raw input.pdf output.txt  # ❌ 깨짐
pdftotext -layout input.pdf output.txt  # ❌ 깨짐
```

### 시도 2: PyMuPDF (Python)
```python
import fitz
doc = fitz.open("input.pdf")
text = ""
for page in doc:
    text += page.get_text()  # ❌ 한글 깨짐
```

### 시도 3: pdfjs-dist (Node.js)
```javascript
const pdf = await pdfjsLib.getDocument(data).promise;
// ❌ 한글 깨짐
```

### 시도 4: pdf-parse (Node.js)
```javascript
const data = await pdfParse(buffer);
// ❌ 한글 깨짐
```

## 수정 기록

### 최종 해결: Tesseract OCR (이미지 기반)
```powershell
# 1. poppler 설치 (pdftopng로 page→image)
scoop install poppler

# 2. tesseract + 한국어 언어팩 설치
scoop install tesseract tesseract-languages

# 3. PDF → 200 DPI PNG 변환
pdftopng -r 200 input.pdf page

# 4. OCR (kor+eng)
tesseract page-1.png stdout -l kor+eng --psm 6 > page-1.txt
```

## 차이점 분석
- PDF 텍스트 extractor는 **폰트 내부 인코딩**에 의존 → subset font에서 실패
- OCR(이미지)은 **픽셀 기반** → 폰트 인코딩과 무관하게 동작
- 단, OCR은 수식/숫자 인식률이 낮고 속도가 느림 (150페이지 ~30분)

## 재발 방지
- 한국어 PDF 만나면 **pdftotext 1회 시도 → 실패 시 즉시 OCR**으로 전환
- 동일 카테고리 도구 5개 serial 테스트 금지 (3회 실패 = 패러다임 전환)
- PDF 특성 먼저 확인: 폰트 포함 여부, subset 여부
