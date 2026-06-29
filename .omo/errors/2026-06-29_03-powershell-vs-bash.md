# [2026-06-29] PowerShell 환경 차이로 인한 명령어 실패

## 분류
- [x] Environment Issue: OS/Shell 차이
- [ ] Code Error
- [ ] Direction Error
- [ ] Performance Issue

## 상황
- 의도: Linux/Mac 기준 bash 명령어를 Windows에서 동일하게 실행
- 발생: `&&` 연산자, 경로 공백 처리, 인코딩 관련 오류
- 원인 추정: PowerShell 5.1은 bash와 문법 및 동작 방식이 다름

## 실패 기록

### 1. `&&` 연산자 사용 실패
```powershell
# 실패 (bash 기준)
cd some_dir && python script.py
# PowerShell: &&는 PS 7+에서만 지원, PS 5.1에서는 에러
```

### 2. 경로 공백 처리 실패
```powershell
# 실패
Get-ChildItem C:\Users\User\Documents\GenAI\00. 교안
# 공백 때문에 경로 인식 실패
```

## 수정 기록

### 1. `&&` → `; if ($?) { }`
```powershell
# 수정
Set-Location some_dir; if ($?) { python script.py }
```

### 2. 경로 공백 → 큰따옴표로 감싸기
```powershell
# 수정
Get-ChildItem "C:\Users\User\Documents\GenAI\00. 교안"
```

### 3. 한글 경로 문제 → ASCII 전용 경로 사용
```powershell
# 수정: 임시 경로 활용
$tmp = "$env:TEMP\opencode"
# 한글 없는 경로에서 작업 후 결과만 복사
```

## 차이점 분석
- PowerShell 5.1 (Windows 기본)은 bash와 근본적으로 다른 shell
- `&&`, `||`, `$()`, 경로 처리, 인코딩 모두 다름
- 명령어를 작성하기 전에 **OS/Shell 환경을 먼저 확인**해야 함

## 재발 방지
- 명령어 실행 전 env 확인: `platform: win32`
- 체크리스트:
  - [ ] `&&` 사용 금지 → `; if ($?) { }` 사용
  - [ ] 경로에 공백/한글 있으면 큰따옴표 처리
  - [ ] 한글 경로는 ASCII 전용 경로로 변환 후 사용
