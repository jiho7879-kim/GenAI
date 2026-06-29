---
title: "Harness Engineering — 검증 인프라 구축 (ruff + pytest + check_all harness)"
date: 2026-06-29
category: decision
severity: info
---

## 증상 (Symptom)

프로젝트에 코드 품질 검증 도구가 없어서 lint 에러, import 실패, 스타일 불일치 등이 발견되지 않은 채로 커밋/배포될 위험이 있었음.

## 결정 (Decision)

Python 생태계의 현대적인 도구들을 harness로 도입:

| 계층 | 도구 | 역할 | 설치 방식 |
|------|------|------|-----------|
| Linter | ruff (check) | 논리 오류, 안티패턴, unused import 탐지 | `ruff.toml` |
| Formatter | ruff (format) | 코드 스타일 일관성 강제 | `ruff.toml` |
| Import 검증 | `scripts/validate_imports.py` | 모든 모듈 import 가능 확인 | Python 스크립트 |
| 단위 테스트 | pytest | 회귀 방지 + 로직 검증 | `tests/` |
| 단일 명령어 | `scripts/check_all.ps1` | 위 4가지를 순차 실행 | PowerShell |

## 선택지 비교 (Linter)

| 옵션 | 장점 | 단점 | 선택? |
|------|------|------|-------|
| **ruff** | 속도 빠름, flake8+isort+pycodestyle 통합, auto-fix | 상대적으로 최신 | ✅ |
| pylint | 전통적, 더 엄격함 | 느림, verbose, 설정 복잡 | ❌ |
| pyflakes+pycodestyle | 가벼움 | 분리된 도구, 속도 느림 | ❌ |

## 교훈 (Lesson Learned)

- ruff v0.15.x부터 `[per-file-ignores]`가 `[lint.per-file-ignores]`로 변경됨 (설치 시점 확인 필요)
- `app.py`는 `sys.path.insert` 이후 import가 있어서 `E402`를 `per-file-ignores`로 예외처리 필요
- `scripts/` 디렉토리의 `generate_pptx.py`는 standalone 스크립트이므로 lint에서 제외

## Harness 구조

```
.\scripts\check_all.ps1  →  Layer 1: ruff format --check
                        →  Layer 2: ruff check
                        →  Layer 3: validate_imports.py
                        →  Layer 4: pytest tests/
```

## 추가된 파일

| 파일 | 역할 |
|------|------|
| `ruff.toml` | ruff 설정 (lint rules, format style, per-file-ignores) |
| `scripts/check_all.ps1` | 단일 명령어 검증 harness |
| `scripts/validate_imports.py` | import 체인 검증 |
| `tests/conftest.py` | pytest 설정 |
| `tests/test_ingest.py` | ingest 메타데이터 단위 테스트 (8개) |
