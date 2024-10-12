[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# 아파트아이(APT.i)
APT.i 사용자를 위한 홈어시스턴트 커스텀 컴포넌트

## 기여
문제가 있나요? [Issues](https://github.com/lunDreame/homeassistant-apti/issues) 탭에 작성해 주세요.

- 더 좋은 아이디어가 있나요? [Pull requests](https://github.com/lunDreame/homeassistant-apti/pulls)로 공유해 주세요!

도움이 되셨나요? [카카오페이](https://qr.kakaopay.com/FWDWOBBmR) [토스](https://toss.me/lundreamer)

## 설치
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lunDreame&repository=homeassistant-apti&category=Integration)

이 통합을 설치하려면 이 GitHub Repo를 HACS Custom Repositories에 추가하거나 위의 배지를 클릭하세요. 설치 후 HomeAssistant를 재부팅하세요.

1. **기기 및 서비스** 메뉴에서 **통합구성요소 추가하기**를 클릭합니다.
2. **브랜드 이름 검색** 탭에 `아파트아이`을 입력하고 검색 결과에서 클릭합니다.
3. 아래 설명에 따라 설정을 진행합니다:
    1. 아이디 / 휴대폰 번호
       - 아파트아이 계정의 아이디 또는 휴대폰 번호를 입력해 주세요. 
       - 간편 로그인으로 가입한 경우 [해당](https://cafe.naver.com/koreassistant/18596) 글을 참조해 
          주세요. 공유해 주신 홍구 님 감사드립니다.
    2. 패스워드
       - 아파트아이 계정의 패스워드를 입력해 주세요.
4. 설정이 완료된 후, 컴포넌트가 로드되면 생성된 기기를 사용하실 수 있습니다.

### 준비
- 사전에 아파트아이에 가입되어 있지 않는 사용자분께서는 먼저 아파트아이 홈페이지 또는 앱을 통해 가입해 주세요.
- [대시보드 카드](#대시보드-카드)를 구성하실 분들께선 커스텀 카드들을 설치해 주세요.
   - ApexCharts Card: https://github.com/RomRider/apexcharts-card
   - Mini Graph Card: https://github.com/kalkih/mini-graph-card
   - Button Card: https://github.com/custom-cards/button-card 

## 기능
- 관리비 조회
- 에너지 조회
   ### 대시보드 카드:
    - [모든 관리 및 에너지 상태 포괄 카드](./cards/mgmt_energy_status.yaml)
    - [에너지 사용량 요약](./cards/energy_usage_summary.yaml)
    - [관리비 세부 내역](./cards/mgmt_fee_detail.yaml)
    - [월간 관리비 추이](./cards/monthly_mgmt_fee_trend.yaml)

## 디버깅
문제 파악을 위해 아래 코드를 `configuration.yaml` 파일에 추가 후 HomeAssistant를 재시작해 주세요.

```yaml
logger:
  default: info
  logs:
    custom_components.apti: debug
```

## 라이선스
아파트아이 통합은 [MIT License](./LICENSE)를 따릅니다.
