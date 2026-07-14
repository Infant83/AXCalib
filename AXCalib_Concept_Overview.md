# AXCalib

## AX Certification Agent Library

> **AX 역량 평가, 평가 보정, 수준 판정 및 인증을 위한 에이전트 라이브러리**

---

## 1. 문서 목적

이 문서는 **AXCalib**의 핵심 아이디어와 기본 구상을 정리한 초기 개념 문서다.

AXCalib는 향후 실제 작업 워크스페이스에서 에이전트, 라이브러리, API, 서비스, 플랫폼 또는 평가 하네스로 발전할 수 있다. 다만 현재 단계에서는 특정 구현 방식, 프레임워크, 디렉터리 구조, 에이전트 오케스트레이션 방식이나 배포 형태를 강하게 고정하지 않는다.

이 문서의 목적은 다음과 같다.

- 프로젝트가 해결하려는 문제와 목표를 명확히 한다.
- `AXCalib`라는 이름과 제품 정체성을 정의한다.
- 평가, 보정, 수준 판정, 인증을 연결하는 기본 개념을 정리한다.
- 향후 구현 과정에서 공통 참조점으로 사용할 수 있는 용어와 원칙을 마련한다.
- 워크스페이스에서 아이디어를 확장하거나 수정할 때 출발점이 되는 살아 있는 문서로 활용한다.

이 문서에 포함된 모듈명, 에이전트명, 인터페이스 예시는 모두 **개념적 예시**이며 구현 계약이 아니다.

---

## 2. 프로젝트 개요

### 2.1 프로젝트명

**AXCalib**

### 2.2 공식 확장명

**AX Certification Agent Library**

### 2.3 한글 설명

**AX 역량 평가, 평가 보정, 수준 판정 및 인증을 위한 에이전트 라이브러리**

### 2.4 한 줄 정의

> AXCalib는 다양한 평가 증거를 에이전트가 분석하고, 평가 결과를 보정하며, AX 역량 수준을 판정하고 인증할 수 있도록 지원하는 확장 가능한 에이전트 라이브러리다.

### 2.5 영문 한 줄 정의

> AXCalib is an extensible agent library for evidence-based AX competency assessment, calibration, level determination, and certification.

---

## 3. 이름의 의미

`AXCalib`는 다음 요소를 결합한 이름이다.

- **AX**: AI Transformation
- **C**: Certification
- **A**: Agent
- **Lib**: Library

즉,

> **AX + Certification + Agent + Library → AXCalib**

동시에 `Calib`는 **Calibration**을 자연스럽게 연상시킨다. 이는 AXCalib가 단순히 답안을 채점하는 도구가 아니라, 평가 기준과 에이전트 판단을 지속적으로 보정하고 신뢰할 수 있는 인증 결과를 생성하는 체계를 지향한다는 점과 잘 맞는다.

또한 `AXCalib`는 다음의 세 가지 의미를 함께 가진다.

1. **AX Certification Agent Library**라는 직접적인 제품 정체성
2. 평가 일관성과 신뢰도를 높이는 **Calibration**의 의미
3. 역량 수준과 품질을 연상시키는 **Caliber**의 의미

---

## 4. 문제 정의

AX 교육과 업무 전환이 확대되면서 개인, 팀, 교육과정, 조직의 AX 역량을 평가하고 인증하려는 요구가 증가하고 있다. 그러나 기존의 단순 시험이나 일회성 점수만으로는 실제 AX 수행 역량을 충분히 설명하기 어렵다.

특히 다음과 같은 문제가 존재한다.

- 지식형 시험 결과와 실제 수행 능력 사이에 차이가 있다.
- 프로젝트, 코드, 문서, 워크플로, 실행 로그 등 다양한 증거를 함께 평가하기 어렵다.
- 평가자의 주관과 편차를 통제하기 어렵다.
- LLM 또는 에이전트 기반 평가 결과의 일관성과 재현성이 충분하지 않을 수 있다.
- 동일한 수준 체계를 여러 교육과정과 조직에 일관되게 적용하기 어렵다.
- 인증 결과가 어떤 근거와 평가 절차로 만들어졌는지 설명하기 어렵다.
- 역량 수준 판정, 인증서 발급, 검증, 재인증이 서로 분리되어 있다.

AXCalib는 이러한 문제를 해결하기 위해 **증거 기반 평가**, **에이전트 기반 판단**, **평가 보정**, **수준 판정**, **인증 및 검증**을 하나의 일관된 개념 체계로 연결하고자 한다.

---

## 5. 비전과 지향점

### 5.1 비전

> AX 역량을 객관적으로 설명하고, 재현 가능하게 평가하며, 신뢰할 수 있는 형태로 인증하는 개방형 기반을 만든다.

### 5.2 핵심 지향점

AXCalib는 다음을 지향한다.

- **Evidence-based**: 단순 응답이 아니라 다양한 수행 증거를 기반으로 평가한다.
- **Agentic**: 에이전트가 증거 수집, 분석, 채점, 검토, 판정 및 설명을 협력적으로 수행할 수 있다.
- **Calibrated**: 모델, 에이전트, 루브릭 및 평가 데이터의 편차를 점검하고 보정한다.
- **Explainable**: 결과뿐 아니라 판단 근거, 적용 기준 및 불확실성을 설명할 수 있다.
- **Composable**: 필요한 기능을 조합하여 다양한 평가 시나리오를 구성할 수 있다.
- **Extensible**: 교육, 직무, 산업, 조직 수준으로 평가 범위를 확장할 수 있다.
- **Auditable**: 평가 과정, 사용된 기준, 모델, 데이터 및 결과 이력을 추적할 수 있다.
- **Implementation-agnostic**: 특정 LLM, 오케스트레이션 프레임워크 또는 배포 환경에 과도하게 종속되지 않는다.

---

## 6. 기본 범위

AXCalib의 기본 범위는 다음 네 개의 축으로 이해할 수 있다.

### 6.1 Assessment

평가 대상이 가진 AX 관련 지식, 수행 능력, 산출물 및 행동 증거를 분석한다.

평가 대상은 다음과 같이 확장될 수 있다.

- 개인 학습자
- 실무자
- 프로젝트 팀
- 교육과정
- 조직
- AI 또는 Agent 시스템
- AX 관련 솔루션과 서비스

### 6.2 Calibration

평가 결과의 일관성과 신뢰도를 높이기 위해 평가 기준과 판단 체계를 보정한다.

보정 대상은 다음을 포함할 수 있다.

- 에이전트 간 점수 편차
- 모델 간 판정 편차
- 루브릭 해석 차이
- 평가 항목 난이도
- Level 경계값
- confidence score
- 분야 또는 직무별 기준 차이
- 시간에 따른 평가 기준 변화

### 6.3 Level Determination

평가 결과를 기반으로 AX 역량 수준을 판정한다.

수준 판정은 단일 점수에만 의존하지 않고 다음 요소를 종합할 수 있다.

- 지식 평가 결과
- 실습 수행 결과
- 프로젝트 품질
- 증거의 충분성
- 평가 결과의 신뢰도
- 필수 역량 충족 여부
- 평가 항목 간 균형
- 위험 또는 결격 조건

### 6.4 Certification

수준 판정 결과를 공식적인 인증 결과로 변환하고, 인증 상태와 근거를 관리한다.

인증은 다음 기능으로 확장될 수 있다.

- 인증 조건 검토
- 인증 결과 생성
- 인증서 또는 디지털 Credential 발급
- 인증 유효기간 관리
- 재인증
- 인증 취소 또는 상태 변경
- 인증 결과 검증
- 인증 근거 및 이력 추적

---

## 7. 핵심 개념 모델

AXCalib의 기본적인 개념 관계는 다음과 같다.

```text
Evaluation Target
      ↓
Evidence Collection
      ↓
Evidence Normalization
      ↓
Rubric-based Assessment
      ↓
Scoring and Reasoning
      ↓
Stage-aware Similar Case Review
      ↓
Agent Recommendation and Report
      ↓
Administrator HITL and Notification
      ↓
Level Determination
      ↓
Certification Decision
      ↓
Credential / Report / Verification Record
```

이 흐름은 등록심의와 완료평가의 두 Gate에 반복 적용된다. 일부 분석 단계는 병렬화할 수
있지만 Agent recommendation을 관리자 final decision으로 자동 승격하지 않는다. 두 Gate의
HITL 진입에는 승인요청 알림과 감사기록이 필요하다.

---

## 8. 평가 증거

AXCalib는 평가 대상에 대한 다양한 형태의 증거를 다룰 수 있어야 한다.

예시 증거는 다음과 같다.

- 객관식 및 주관식 답변
- 대화형 질의응답 기록
- 코드 및 저장소
- 프로젝트 문서
- 프롬프트와 Agent 정의
- 워크플로 또는 파이프라인 구성
- 실행 로그 및 테스트 결과
- 데이터 분석 결과
- 발표 자료
- 포트폴리오
- 교육 이수 기록
- 동료 또는 전문가 평가
- 시스템 사용 기록
- 운영 성과 지표

모든 증거를 동일한 방식으로 처리할 필요는 없다. 중요한 것은 각 증거가 어떤 역량을 뒷받침하며, 신뢰 수준과 출처가 무엇인지 표현할 수 있는 공통 메타데이터를 갖추는 것이다.

개념적으로 증거는 다음 속성을 가질 수 있다.

| 속성 | 설명 |
|---|---|
| Source | 증거가 생성되거나 수집된 출처 |
| Type | 문서, 코드, 로그, 응답, 프로젝트 등 증거 유형 |
| Subject | 증거가 연결되는 평가 대상 |
| Competency | 해당 증거가 뒷받침하는 역량 영역 |
| Validity | 평가에 사용할 수 있는 유효성 |
| Reliability | 증거 자체의 신뢰 수준 |
| Timestamp | 생성 또는 제출 시점 |
| Provenance | 생성, 수정, 전달 및 검증 이력 |

---

## 9. 평가 루브릭

루브릭은 평가 항목, 판단 기준, 점수 체계 및 Level 조건을 표현하는 핵심 자산이다.

AXCalib는 루브릭을 고정된 형식으로 제한하기보다 다음 요소를 표현할 수 있는 유연한 모델을 지향한다.

- 평가 목적
- 대상 직무 또는 역할
- 역량 영역
- 평가 항목
- 성취 기준
- 점수 또는 등급 기준
- 필수 조건
- 가중치
- 증거 요구사항
- 평가 방법
- 판정 불확실성
- 예외 및 결격 조건
- 적용 버전과 유효기간

루브릭은 사람과 Agent가 함께 읽을 수 있어야 하며, 필요할 경우 기계적으로 실행 가능한 정책이나 규칙으로 변환될 수 있어야 한다.

---

## 10. 에이전트 개념

AXCalib에서 Agent는 단순한 챗봇이 아니라 특정 평가 책임을 수행하는 판단 단위다.

초기 단계에서는 단일 Agent로 구현할 수도 있고, 이후 필요에 따라 역할을 분리할 수도 있다. 다음 에이전트 명칭은 역할을 설명하기 위한 예시이며 실제 구조를 강제하지 않는다.

| 개념적 Agent | 주요 역할 |
|---|---|
| Assessment Agent | 평가 대상과 제출물을 분석하고 평가 항목별 판단을 생성 |
| Evidence Agent | 증거를 수집, 분류, 정규화하고 평가 가능성을 확인 |
| Rubric Agent | 적절한 루브릭을 선택하거나 평가 맥락에 맞게 해석 |
| Scoring Agent | 항목별 점수, 등급, confidence 및 근거를 생성 |
| Calibration Agent | 평가 결과의 편차, 일관성 및 경계값을 점검하고 보정 |
| Leveling Agent | 여러 평가 결과를 종합하여 AX Level을 판정 |
| Certification Agent | 인증 조건을 검토하고 인증 가능 여부를 결정 |
| Verification Agent | 발급된 인증과 증거 이력의 유효성을 검증 |
| Audit Agent | 평가 과정과 판단 근거를 추적하고 감사 가능한 기록을 생성 |

에이전트는 필요에 따라 다음 방식으로 운영될 수 있다.

- 단일 모델 기반
- 다중 모델 합의
- 역할 기반 다중 Agent
- 규칙 엔진과 Agent 결합
- Human-in-the-loop
- GitLab Merge Request 또는 email 기반 관리자 승인요청
- 외부 도구 또는 서비스 연동
- 배치 평가
- 실시간 대화형 평가

---

## 11. Calibration의 의미

Calibration은 AXCalib의 정체성을 구성하는 핵심 개념이다.

AXCalib에서 보정은 단순히 점수에 보정계수를 곱하는 것을 의미하지 않는다. 평가 결과가 실제 역량 수준을 얼마나 신뢰성 있게 반영하는지 확인하고 조정하는 전체 활동을 포함한다.

### 11.1 평가자 보정

- 동일한 제출물에 대해 여러 Agent가 유사한 판단을 내리는가
- 특정 모델이 지속적으로 높은 점수 또는 낮은 점수를 주는가
- 평가 근거의 해석이 Agent마다 크게 다른가

### 11.2 루브릭 보정

- 평가 항목이 의도한 역량을 실제로 측정하는가
- 모호하거나 중복되는 기준은 없는가
- Level 간 차이가 충분히 구분되는가

### 11.3 난이도 보정

- 서로 다른 과제나 평가 세트의 난이도가 비교 가능한가
- 특정 분야나 직무에 과도하게 유리한 항목은 없는가

### 11.4 신뢰도 보정

- confidence score가 실제 오류 가능성과 일치하는가
- 낮은 확신의 판정을 자동 인증으로 처리하지 않도록 할 수 있는가

### 11.5 경계값 보정

- Level 판정 임계값이 실제 수행 능력과 정렬되어 있는가
- 특정 점수 하나로 Level이 과도하게 변화하지 않는가

향후에는 calibration dataset, benchmark, expert review, inter-rater agreement, error analysis 및 statistical calibration 기법을 함께 사용할 수 있다.

---

## 12. AX Level 개념

AXCalib는 특정 Level 체계를 처음부터 고정하지 않는다. 조직과 교육 목적에 따라 다른 Level 모델을 적용할 수 있어야 한다.

다만 기본적인 예시는 다음과 같이 생각할 수 있다.

| 예시 Level | 의미 |
|---|---|
| Awareness | AX 개념과 활용 가능성을 이해 |
| Literacy | 기본 도구와 핵심 개념을 이해하고 사용할 수 있음 |
| Practitioner | 실제 업무에 AX 도구와 방법을 적용할 수 있음 |
| Builder | Agent, 자동화, 데이터 또는 AI 기반 워크플로를 구축할 수 있음 |
| Architect | 조직 또는 시스템 수준의 AX 구조를 설계할 수 있음 |
| Strategist | AX 전략, 운영 모델, 거버넌스 및 전환을 주도할 수 있음 |

실제 프로젝트에서는 Level 이름, 단계 수, 필수 역량, 직무별 기준 및 인증 조건을 별도의 프레임워크로 정의하는 것이 바람직하다.

---

## 13. 주요 결과물

AXCalib는 평가 과정에서 다음과 같은 결과물을 생성할 수 있다.

### 13.1 Assessment Result

- 평가 항목별 결과
- 점수 또는 등급
- 근거와 인용된 증거
- confidence
- 부족한 증거
- 평가 제한사항

### 13.2 Competency Profile

- 역량 영역별 수준
- 강점과 취약점
- Level별 준비도
- 역량 Gap
- 추천 학습 또는 개선 경로

### 13.3 Level Decision

- 판정된 AX Level
- 판정 근거
- 필수 조건 충족 여부
- 보류 또는 재평가 조건
- 판정 신뢰도

### 13.4 Certification Decision

- 인증 가능 여부
- 인증 범위
- 인증 유효기간
- 인증 조건
- 재인증 또는 추가 검토 필요성

### 13.5 Credential

- 인증 대상
- 인증 Level 또는 유형
- 발급자
- 발급 시점과 유효기간
- 평가 및 루브릭 버전
- 검증 가능한 식별자

### 13.6 Audit Record

- 사용된 모델과 Agent
- 평가 워크플로
- 적용 루브릭
- 증거 목록
- 주요 판단 과정
- 변경 및 검토 이력

---

## 14. 활용 시나리오

### 14.1 개인 역량 인증

학습자의 시험 답안, 프로젝트, 코드, 포트폴리오를 종합하여 AX Level을 판정하고 인증한다.

### 14.2 교육과정 성과 평가

교육과정의 학습 목표와 평가 결과를 연결하여 수료생의 실제 AX 수행 역량을 검증한다.

### 14.3 직무 기반 인증

연구자, 개발자, 기획자, 운영자, 리더 등 직무별 루브릭을 적용하여 역할에 적합한 AX 역량을 평가한다.

### 14.4 조직 AX Readiness 평가

개인 평가 결과, 팀 역량, 프로세스, 데이터, 기술 및 거버넌스 증거를 종합하여 조직의 AX 준비도를 분석한다.

### 14.5 프로젝트 또는 솔루션 인증

특정 프로젝트나 Agent 시스템이 정의된 품질, 안전성, 재현성 및 운영 기준을 충족하는지 평가한다.

### 14.6 지속적 재평가

일회성 시험이 아니라 프로젝트 활동과 운영 데이터를 지속적으로 분석하여 역량 변화와 인증 유효성을 갱신한다.

---

## 15. 제품 및 구현 형태의 확장 가능성

AXCalib는 처음에는 작은 라이브러리 또는 평가 Agent로 시작할 수 있으며, 이후 필요에 따라 다양한 형태로 확장할 수 있다.

가능한 형태는 다음과 같다.

| 형태 | 설명 |
|---|---|
| Core Library | 평가, 보정, Level 판정 및 인증의 기본 기능 제공 |
| Agent Package | 특정 역할을 수행하는 평가 및 인증 Agent 제공 |
| CLI | 로컬 또는 CI 환경에서 평가와 인증 수행 |
| API | 외부 서비스가 평가와 인증 기능을 호출하도록 제공 |
| SDK | Python, TypeScript 등 개발 환경에 통합 |
| Evaluation Harness | 벤치마크, 반복 평가, 모델 비교 및 보정 수행 |
| Self-hosted Server | 조직 내부 환경에서 평가 서비스 운영 |
| Web Platform | 평가 운영, 결과 확인, 인증 관리 및 대시보드 제공 |
| Registry | 루브릭, Level 프레임워크, 인증 및 검증 기록 관리 |
| Studio | 평가 흐름, 루브릭 및 Agent 구성을 작성하고 실험 |

현재 단계에서는 이 중 하나를 최종 형태로 고정하지 않는다. 실제 워크스페이스에서는 가장 작은 유효 기능부터 구현하고, 사용 사례와 검증 결과에 따라 확장하는 방식을 권장한다.

---

## 16. 설계 원칙

### 16.1 결과보다 근거를 우선한다

점수와 Level뿐 아니라 어떤 증거와 기준으로 판단했는지 남겨야 한다.

### 16.2 자동화와 책임성을 함께 고려한다

Agent가 평가를 자동화하더라도 등록심의와 완료평가의 최종 통과·미통과는 관리자 검토를
반드시 거쳐야 한다. 관리자 검토 대상이 생기면 승인요청 알림도 반드시 기록하거나 전달한다.

### 16.3 평가와 인증을 분리하되 연결한다

평가 결과가 곧바로 인증을 의미하지 않을 수 있다. 인증은 별도의 정책과 조건을 통해 결정될 수 있어야 한다.

### 16.4 루브릭과 모델을 버전 관리한다

동일한 이름의 평가라도 기준이나 모델이 바뀌면 결과의 의미가 달라질 수 있으므로 버전과 적용 시점을 추적해야 한다.

### 16.5 불확실성을 숨기지 않는다

판정이 불명확하거나 증거가 부족할 경우 이를 명시하고 보류, 추가 평가 또는 사람 검토로 연결해야 한다.

### 16.6 구성 가능성을 유지한다

단일한 평가 방식보다 평가 대상, 직무, 산업 및 위험 수준에 따라 구성 요소를 조합할 수 있어야 한다.

### 16.7 특정 구현 기술에 종속되지 않는다

특정 LLM, Agent 프레임워크, Vector DB, Workflow Engine 또는 Cloud에 과도하게 의존하지 않도록 개념과 구현을 분리한다.

### 16.8 작은 단위로 검증한다

처음부터 완전한 인증 플랫폼을 만들기보다 하나의 평가 대상, 하나의 루브릭, 제한된 증거 유형으로 시작해 신뢰성과 유용성을 검증한다.

### 16.9 유사도보다 비교근거를 우선한다

유사과제 검색은 registration/completion stage를 분리하고, raw similarity를 합격점수로 직접
사용하지 않는다. 설정 가능한 portion은 공통점·차이점·적용 한계를 포함한
historical-consistency 신호에 적용하며 사람의 최종 판단을 대체하지 않는다.

---

## 17. 초기 개발에서 우선 검증할 질문

초기 프로토타입에서는 다음 질문에 답하는 것이 중요하다.

1. 어떤 AX 역량을 가장 먼저 평가할 것인가?
2. 평가 결과를 뒷받침하는 최소 증거는 무엇인가?
3. 사람 평가와 Agent 평가의 일치도는 어느 정도인가?
4. 동일한 제출물에 대해 반복 평가 결과가 얼마나 안정적인가?
5. Level 경계에서 어떤 오류가 발생하는가?
6. 평가 Agent의 근거 설명이 전문가 검토에 충분한가?
7. 낮은 confidence 결과를 어떤 방식으로 처리할 것인가?
8. 루브릭 변경이 기존 인증 결과에 어떤 영향을 주는가?
9. 평가와 인증 사이에 어떤 별도 정책이 필요한가?
10. 어떤 정보가 감사 및 재현을 위해 반드시 기록되어야 하는가?

---

## 18. 초기 구현 방향 예시

초기 구현은 다음과 같이 작게 시작할 수 있다.

### 단계 1: 단일 평가 시나리오

- 하나의 AX 직무 또는 교육과정 선택
- 소수의 역량 영역 정의
- 하나의 루브릭 작성
- 제한된 형식의 제출물 평가
- 구조화된 결과 생성

### 단계 2: Level 판정

- 평가 결과를 Level 조건과 연결
- 필수 항목과 임계값 정의
- 판정 근거와 confidence 기록

### 단계 3: Calibration

- 전문가 평가 샘플 구축
- Agent 결과와 전문가 결과 비교
- 편차, 반복성 및 경계 오류 분석

### 단계 4: Certification

- 평가 결과와 인증 정책 분리
- 인증 여부와 유효기간 결정
- 검증 가능한 결과 형식 생성

### 단계 5: 확장

- 다중 Agent
- 다중 모델
- 다양한 증거 유형
- API 또는 CLI
- 지속 평가 및 Registry

이 순서는 제안일 뿐이며 실제 우선순위는 워크스페이스의 목적과 사용 사례에 맞게 조정한다.

---

## 19. 개념적 사용 예시

다음 코드는 향후 API의 방향을 설명하기 위한 개념적 예시이며 실제 인터페이스를 고정하지 않는다.

```python
from axcalib import CertificationAgent, EvaluationContext

agent = CertificationAgent(
    framework="ax-level-v1",
    rubric="agentic-workflow-practitioner",
)

result = agent.evaluate(
    EvaluationContext(
        subject="candidate-001",
        evidence=[
            "project_report.pdf",
            "workflow.yaml",
            "repository/",
        ],
    )
)

print(result.level)
print(result.confidence)
print(result.rationale)
print(result.certification_status)
```

개념적 CLI 예시는 다음과 같다.

```bash
axcalib evaluate ./submission
axcalib level ./assessment-result.json
axcalib certify ./level-decision.json
axcalib verify ./credential.json
axcalib calibrate ./benchmark-set
```

---

## 20. 권장 용어

| 용어 | 권장 의미 |
|---|---|
| AX | AI Transformation |
| Assessment | 평가 대상의 역량과 증거를 분석하는 과정 |
| Evidence | 판단을 뒷받침하는 제출물, 기록 또는 관찰 정보 |
| Rubric | 평가 기준과 성취 수준을 정의한 체계 |
| Score | 특정 항목에 대한 정량적 평가 값 |
| Rating | 등급 또는 범주형 평가 결과 |
| Level | 종합 역량 수준 |
| Calibration | 평가 일관성, 정확성 및 신뢰도 보정 |
| Confidence | 판정에 대한 신뢰 수준 또는 불확실성 표현 |
| Certification | 정의된 정책에 따라 역량을 공식적으로 인정하는 절차 |
| Credential | 인증 결과를 표현하는 검증 가능한 기록 |
| Verification | 인증 또는 Credential의 유효성을 확인하는 과정 |
| Provenance | 증거와 결과의 출처 및 변경 이력 |
| Audit Trail | 평가와 인증 과정의 추적 가능한 기록 |

---

## 21. 비목표

현재 단계에서 AXCalib는 다음을 반드시 목표로 하지 않는다.

- 모든 산업과 직무를 포괄하는 단일 AX 표준을 즉시 정의하는 것
- 사람 평가자를 완전히 제거하는 것
- LLM의 단일 판단을 공식 인증으로 바로 사용하는 것
- 특정 Agent 프레임워크에 최적화된 구조를 먼저 고정하는 것
- 복잡한 인증 플랫폼 전체를 한 번에 구현하는 것
- 모든 평가를 하나의 점수로 환원하는 것
- 블록체인이나 특정 Credential 표준을 필수 전제로 삼는 것
- 초기 단계부터 강한 디렉터리, 패키지 또는 배포 구조를 확정하는 것

---

## 22. 향후 결정이 필요한 항목

다음 항목은 실제 구현과 실험을 진행하며 결정한다.

- 첫 번째 평가 대상과 사용 사례
- AX Level 프레임워크의 범위
- 루브릭 표현 형식
- 평가 결과 스키마
- 증거 저장 및 참조 방식
- Agent 역할 분리 수준
- 모델 선택 및 교체 전략
- 평가 반복성과 합의 방식
- Calibration 데이터셋 구성
- Human-in-the-loop 세부 권한, 관리자 SLA와 override 정책
- 승인요청 운영수단: GitLab Merge Request, email 또는 둘 다
- stage별 similarity portion의 기본값과 운영 상한
- mentor 배정과 미배정 완료 제출 승인정책
- 인증 유효기간과 재인증 기준
- Credential 표현과 검증 방식
- 개인정보, 보안 및 데이터 보존 정책
- API, CLI, 라이브러리 및 플랫폼의 우선순위
- 오픈소스와 내부 전용 구성의 경계

---

## 23. 브랜드 문구 후보

### 대표 슬로건

> **Calibrate Assessment. Certify AX.**

### 대안 문구

> **Evidence-Based Agents for AX Certification.**

> **Composable Agents for Reliable AX Assessment.**

> **Assess Competency. Calibrate Judgment. Certify the Level.**

### 한국어 문구

> **AX 역량을 평가하고, 판단을 보정하며, 수준을 인증하다.**

---

## 24. 프로젝트 설명문 후보

### 짧은 설명

> AXCalib는 AX 역량 평가와 인증을 위한 에이전트 라이브러리다.

### 중간 길이 설명

> AXCalib는 다양한 수행 증거를 분석하고, 평가 결과를 보정하며, AX Level 판정과 인증을 지원하는 확장 가능한 에이전트 라이브러리다.

### 기술 중심 설명

> AXCalib provides composable agents, evaluation workflows, rubrics, calibration mechanisms, and certification primitives for building reliable AX competency assessment systems.

### 플랫폼 확장형 설명

> AXCalib는 라이브러리에서 시작하여 평가 하네스, API, 인증 서비스 및 AX 역량 관리 플랫폼으로 확장할 수 있는 개방형 기반을 지향한다.

---

## 25. 문서 운영 원칙

이 문서는 프로젝트 진행에 따라 계속 수정되는 **Living Document**로 사용한다.

권장 운영 방식은 다음과 같다.

- 검증된 결정과 아직 가설인 내용을 구분한다.
- 구현 세부사항보다 프로젝트의 목적과 설계 의도를 우선 기록한다.
- 중요한 용어와 개념 변경은 문서에 반영한다.
- 새로운 사용 사례가 추가되면 기존 개념과 충돌하는지 검토한다.
- 초기에는 구조를 과도하게 고정하지 않되, 반복적으로 확인된 패턴은 점진적으로 표준화한다.
- 실제 코드와 문서의 차이가 커지지 않도록 정기적으로 갱신한다.

---

## 26. 현재 제안 상태

| 항목 | 현재 상태 |
|---|---|
| 프로젝트명 | AXCalib |
| 공식 확장명 | AX Certification Agent Library |
| 핵심 목적 | AX 역량 평가, 보정, Level 판정 및 인증 |
| 핵심 접근 | 증거 기반, Agent 기반, 설명 가능, 감사 가능 |
| 초기 구현 형태 | Python Library와 executable offline harness |
| 구현 구성 원칙 | 요소 모듈을 국소 pipeline으로 완결하고 versioned total workflow에서 조합 |
| 작업계획 가시성 | workflow 구조도와 module별 상태·의존성·Exit Evidence를 문서로 추적 |
| AX Level 체계 | 향후 정의 또는 외부 프레임워크 연동 가능 |
| 기술 스택 | Python 3.12+, src/axcalib, uv/hatchling baseline |
| 현재 구현 | 두 Gate reference state machine, HITL recording notification, lexical retrieval smoke |
| Agent Framework | Core 비종속; Deep Agents는 optional 후보 |
| 배포 형태 | 미정; 현재 offline/local only |
| 라이선스 및 공개 범위 | 미정 |

---

## 27. 핵심 요약

AXCalib는 단순한 시험 채점 도구가 아니다.

AXCalib가 지향하는 것은 다음의 연결이다.

```text
Evidence
  → Assessment
  → Calibration
  → Level Determination
  → Certification
  → Verification
```

그 중심에는 다음 질문이 있다.

> **어떤 사람이, 팀이, 교육과정이 또는 시스템이 특정 AX 역량을 갖추었다고 신뢰할 수 있는 근거는 무엇이며, 그 판단을 어떻게 일관되고 설명 가능하게 만들 것인가?**

AXCalib는 이 질문에 답하기 위한 에이전트, 루브릭, 평가 흐름, 보정 방법 및 인증 구성 요소를 제공하는 기반으로 발전한다.

---

## 28. 변경 기록

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-12 | AXCalib 초기 개념 문서 작성 |
| 2026-07-14 | 두 Gate 관리자 HITL·알림, 선택적 mentor, stage RAG/portion과 P1 harness 상태 반영 |
