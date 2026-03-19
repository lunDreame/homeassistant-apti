# APTi Home Assistant Custom Integration

[아파트아이 App Store](https://apps.apple.com/kr/app/%EC%95%84%ED%8C%8C%ED%8A%B8%EC%95%84%EC%9D%B4-%EA%B5%AD%EB%82%B41%EC%9C%84-%EC%95%84%ED%8C%8C%ED%8A%B8%EC%95%B1/id1457413104)

## 생성 엔티티

- 요약 센서:
  - 당월/전월 관리비, 납부대상 금액, 관리비 마감일, 청구월, 전용면적
  - 에너지 우리집/평균 요금, 평균 대비 비율
  - 다음 청구월, 보유 캐시, 쿠폰수
  - 주차 누적시간/잔여시간/예상요금/기본시간/기본단가/방문차량 건수
  - 납부이력 최근 납부월/납부일/납부금액
- 상세 센서(동적):
  - `management_fee.detail[]` 각 항목별 센서 (예: 일반관리비, 세대전기료, 세대수도료, 세대급탕비 등)
  - `discount.maintenance[]`, `discount.energy[]`, `discount.energy[].data[]` 할인 항목별 센서
  - 납부이력 상태코드(001~005)별 건수/합계 센서
  - 방문차량 상세 센서(속성에 차량별 입출차/체류시간)
- 바이너리 센서:
  - 관리비 납부완료, 자동이체, 전자고지
  - 주차 서비스 가능/예약제/예약가능/예외시간(공휴일·토·일)/운영단지/신청완료/주차중

## 설치 방법

1. `custom_components/apti` 폴더를 Home Assistant 설정 디렉터리의 `custom_components` 아래에 복사
2. Home Assistant 재시작
3. 설정 > 기기 및 서비스 > 통합 추가 > `APTi`
4. 휴대폰 로그인용 아이디/비밀번호 입력

## 설정 옵션

- `scan_interval` (분): 데이터 갱신 주기 (기본 10분)
