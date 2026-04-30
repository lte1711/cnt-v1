---
title: 소규모 실거래 + 병행 검증 계획
date: 2026-04-28
status: ACTIVE
---

## 현재 상태

```
Closed Trades: 53
Expectancy: +0.000614
LIVE_GATE: LIVE_READY
Target: 60 trades (7 more trades needed)
```

## 목표 (48시간 내)

이제부터 **소규모 실거래를 진행**하면서:
- 실시간 성능 모니터링
- 5 trade 단위 mini evaluation 실행
- 리스크 엔진 정상 작동 검증

---

## Phase 1: 소규모 거래 준비 (1시간)

### 1.1 거래 규모 설정

```
현재 설정 검토 필요:
- 커밋할 거래액 (testnet이지만 비율 검증)
- Position size control
- 최대 노출도 (MAX_PORTFOLIO_EXPOSURE)
```

### 1.2 자동화 검증 스크립트 준비

필요한 스크립트:
- `mini_evaluation.py` - 5 trade 단위 평가
- `live_monitor.py` - 실시간 상태 트래킹
- `signal_quality_check.py` - 신호 품질 검증

---

## Phase 2: 실거래 + 병행 검증 (48시간)

### 2.1 거래 루프

```
run.ps1 (기존 진입점)
  -> main.py
    -> engine (ONE_SHOT mode, 정상)
      -> pullback_v1 신호 생성
      -> 신호 랭킹 및 선택
      -> 주문 실행
      -> 상태 저장
```

### 2.2 병행 검증 (매 3-5시간)

```
Trade [[54-58]]: 기본 모니터링
Trade [[59-60]]: Mini evaluation
  - Expectancy 안정성
  - Win rate 변화
  - Risk trigger 정상 작동
  - 리스크 가드 차단 검증
```

### 2.3 자동화 체크포인트

```bash
# 매 N거래마다 자동 실행
- Performance snapshot 재생성
- Live gate 재평가
- 신호 품질 보고서
- 거래 진행 현황
```

---

## Phase 3: 데이터 포인트 (60 trades)

```
기대값 안정 구간 (60 trades):
- 통계 신뢰도: HIGH
- 다음 단계: FULL_FILTER_RERUN ×3
```

---

## 모니터링 대시보드

### 필요 메트릭

```json
{
  "current_trade_count": 54,
  "target_trade_count": 60,
  "expectancy": "+0.000614",
  "win_rate": "52.83%",
  "net_pnl": "+0.032564",
  "risk_status": "NORMAL",
  "last_signal_time": "2026-04-28T...",
  "last_trade_result": "WIN/LOSS/...",
  "pending_trades": 0,
  "open_positions": 0
}
```

### 실시간 로깅

```
logs/monitor.log
  - 거래 진입/종료 시간
  - PnL 결과
  - 리스크 트리거 발동 여부
  - Signal quality score
```

---

## 즉시 확인 사항

### 질문 1: 거래 규모
- 현재 position size가 무엇인가?
- testnet이지만 소규모로 축소 필요한가?

### 질문 2: 모니터링 빈도
- 매 거래마다 검증할까?
- 5 trade 단위로만 검증할까?
- 8시간 단위로 검증할까?

### 질문 3: 스톱 트리거
- 60 trades 중단 후 즉시 evaluation?
- 아니면 진부터 계속?

---

## 다음 단계 (60 trades 도달 시)

```
1. Mini evaluation 최종 결과 검토
2. FULL_FILTER_RERUN ×3 시작
3. 최종 배포 판정 (50-70 trades 구간)
```

---

## 체크리스트

- [ ] 거래 규모 설정 확정
- [ ] Mini evaluation 스크립트 작성
- [ ] Live monitor 스크립트 작성
- [ ] 자동화 체크포인트 설정
- [ ] 모니터링 대시보드 활성화
- [ ] 실거래 시작
- [ ] 10-15분 모니터링 후 자동화 진행
