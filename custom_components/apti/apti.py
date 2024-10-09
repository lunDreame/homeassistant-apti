import aiohttp
import re

from bs4 import BeautifulSoup
from collections.abc import Callable, Set
from datetime import datetime
from dataclasses import dataclass, field

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .helper import get_text_or_log
from .until import format_date_two_months_ago, get_target_month
from .const import LOGGER


@dataclass
class APTiMaint:
    """APT.i maintenance class."""

    cost: list = field(default_factory=list)     # 관리비 항목
    payment: dict = field(default_factory=dict)  # 관리비 납부 액
    update_time: datetime = field(default_factory=datetime.now)


@dataclass
class APTiEnergy:
    """APT.i energy class."""

    usage: dict = field(default_factory=dict)   # 에너지 항목(사용량)
    detail: list = field(default_factory=list)  # 에너지 항목(상세 사용량)  
    type: list = field(default_factory=list)    # 에너지 종류(사용량)
    update_time: datetime = field(default_factory=datetime.now)


@dataclass
class APTiData:
    """APT.i data class."""
    
    maint: APTiMaint = field(default_factory=APTiMaint)
    energy: APTiEnergy = field(default_factory=APTiEnergy)
    callbacks: Set[Callable] = field(default_factory=set)

    def add_callback(self, callback: Callable):
        """Add a callback"""
        self.callbacks.add(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove a callback"""
        self.callbacks.discard(callback)
    
    def update_callback(self):
        """Updates registered callbacks."""
        for callback in self.callbacks:
            if callable(callback):
                callback()


class APTiAPI:
    """APT.i API class."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the session and basic information."""
        self.hass = hass
        self.entry = entry
        self.username: str | None = None
        self.password: str | None = None
        self.session = aiohttp.ClientSession()
        self.logged_in = False
        self.se_token: str | None = None
        self.apti_codesave: str | None = None
        self.dong_ho: str | None = None
        self.data = APTiData()
    
    async def login(self, username: str = None, password: str = None):
        """Login to APT.i."""
        if username and password:
            self.username = username
            self.password = password
        else:
            self.username = self.entry.data[CONF_USERNAME]
            self.password = self.entry.data[CONF_PASSWORD]

        url = "https://www.apti.co.kr/member/login_ok.asp"
        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {
            "pageGubu": "I",
            "pageMode": "I",
            "pwd": self.password,
            "id": self.username,
            "gubu": "H",
            "hp_id": self.username,
            "hp_pwd": self.password,
        }

        try:
            async with self.session.post(url, headers=headers, data=data, timeout=5) as response:
                if response.status != 200:
                    LOGGER.error("APTi login failed.")
                    return

                cookies = ' '.join(response.headers.getall('Set-Cookie', []))
                self.se_token = re.search(r'se%5Ftoken=([^;]+)', cookies)
                self.apti_codesave = re.search(r'apti=codesave=([^;]+)', cookies)

                if self.se_token:
                    self.se_token = self.se_token.group(1)
                    LOGGER.debug(f"Se token: {self.se_token}")
                if self.apti_codesave:
                    self.apti_codesave = self.apti_codesave.group(1)
                    LOGGER.debug(f"APTi codesave: {self.apti_codesave}")

                self.logged_in = True
        except Exception as ex:
            LOGGER.error(f"Exception during APTi login: {ex}")

    async def get_maint_fee_item(self):
        """Get the maintenance fee items."""
        url = "https://www.apti.co.kr/apti/manage/manage_dataJquery.asp?ajaxGubu=L&orderType=&chkType=ADD"
        headers = {"cookie": f"se%5Ftoken={self.se_token};"}
        params = {
            "listNum": "20",
            "manageDataTot": "23",
            "code": self.apti_codesave,
            "dongho": self.dong_ho,
            "billym": format_date_two_months_ago(),
        }

        try:
            async with self.session.get(url, headers=headers, params=params, timeout=5) as response:
                if response.status != 200:
                    return

                raw_data = await response.content.read()
                resp = raw_data.decode("EUC-KR")
                #LOGGER.debug(f"get_maint_fee_item: {resp}")

                soup = BeautifulSoup(resp, "html.parser")
                links = soup.find_all("a", class_="black")

                for link in links:
                    row = link.find_parent("td").parent
                    category = link.text
                    current_month, previous_month, change = [
                        td.text.strip() for td in row.find_all("td")[1:4]
                    ]
                    if all([category, current_month, previous_month, change]):
                        self.data.maint.cost.append({
                            "항목": category,
                            "당월": current_month,
                            "전월": previous_month,
                            "증감": change
                        })
                    else:
                        LOGGER.warning(
                            f"Skipping row due to missing values: %s, %s, %s, %s",
                            category, current_month, previous_month, change
                        )
        except Exception as ex:
            LOGGER.error(f"An exception occurred while processing maintenance fee item: {ex}")

    async def get_maint_fee_payment(self):
        """Get the payment of maintenance fees."""
        url = "https://www.apti.co.kr/apti/manage/manage_cost.asp?menucd=ACAI"
        headers = {"cookie": f"se%5Ftoken={self.se_token};"}

        try:
            async with self.session.get(url, headers=headers, timeout=5) as response:
                if response.status != 200:
                    return

                raw_data = await response.content.read()
                resp = raw_data.decode("EUC-KR")
                soup = BeautifulSoup(resp, "html.parser")

                self.dong_ho = get_text_or_log(soup, 'input[name="dongho"]', "동호 정보를 찾을 수 없습니다.", attr="value")
                LOGGER.debug(f"APT DongHo: {self.dong_ho}")
                target_month = get_target_month()

                cost_info = {
                    "납부 마감일": get_text_or_log(
                        soup, "div.endBox span", "납부 마감일을 찾을 수 없습니다."
                    ),
                    f"{target_month}월분 부과 금액": get_text_or_log(
                        soup.find("dt", text=f"{target_month}월분 부과 금액"), 
                        None, f"{target_month}월분 부과 금액을 찾을 수 없습니다.", "find_next_sibling"
                    ),
                    "납부할 금액": get_text_or_log(
                        soup.find("dt", text="납부하실 금액"), None, "납부할 금액을 찾을 수 없습니다.", "find_next_sibling"
                    ),
                    "전년 동월 비교": get_text_or_log(
                        soup, ".compaWrap li.compaBox .cost_txt p.price", "전년 동월 비교 금액을 찾을 수 없습니다."
                    ),
                    "우리집 이번달 금액": get_text_or_log(
                        soup, ".compaWrap li.compaBox .cost_ico.current p.t_2", "이번달 금액을 찾을 수 없습니다."
                    )
                }
                payment_span = soup.select_one("span.costPay")
                if payment_span:
                    cost_info["납부할 금액"] = payment_span.text.strip() + "원"
                else:
                    LOGGER.warning("납부할 금액의 span 요소를 찾을 수 없습니다.")

                self.data.maint.payment.update(cost_info)
        except Exception as ex:
            LOGGER.error(f"An exception occurred while processing maintenance fee payment: {ex}")

    async def get_energy_category(self):
        """Get the usage by energy category."""
        url = "https://www.apti.co.kr/apti/manage/manage_energy.asp?menucd=ACAD"
        headers = {"cookie": f"se%5Ftoken={self.se_token};"}

        try:
            async with self.session.get(url, headers=headers, timeout=5) as response:
                if response.status != 200:
                    return
                
                raw_data = await response.content.read()
                resp = raw_data.decode("EUC-KR")
                soup = BeautifulSoup(resp, "html.parser")

                energy_top = soup.find("div", class_="energyTop")
                total_usage = energy_top.find("strong", class_="data1").text.strip()
                month = energy_top.find("span", class_="month").text.strip()
    
                energy_data = soup.find("div", class_="energy_data")
                average_comparison = energy_data.find("strong").text.strip()
    
                energy_analysis = soup.find("div", class_="energy_data2")
                analysis_items = energy_analysis.find_all("li")
                energy_breakdown = {
                    item.contents[0].strip(): item.find("strong").text.strip() 
                    for item in analysis_items
                }
                self.data.energy.usage.update({
                    "월": month,
                    "전체 사용량": total_usage,
                    "평균 대비": average_comparison,
                    **energy_breakdown
                })

                energy_boxes = soup.find_all("div", class_="engBox")    
                for box in energy_boxes:
                    energy_type = box.find("h3").text.strip()
                    usage = box.find("li").find("strong").text.strip()
                    cost = box.find("li", class_="line").find_next_sibling("li").find("strong").text.strip()
                    comparison = box.find("div", class_="txtBox").find("strong").text.strip()
        
                    self.data.energy.detail.append({
                        "유형": energy_type,
                        "사용량": usage,
                        "비용": cost,
                        "비교": comparison
                    })
        except Exception as ex:
            LOGGER.error(f"An exception occurred while processing energy usage category: {ex}")

    async def get_energy_type(self):
        """Get the usage by energy type."""
        url = "https://www.apti.co.kr/apti/manage/manage_energyGogi.asp?menucd=ACAE"
        headers = {"cookie": f"se%5Ftoken={self.se_token};"}

        try:
            async with self.session.get(url, headers=headers, timeout=5) as response:
                if response.status != 200:
                    return
                
                raw_data = await response.content.read()
                resp = raw_data.decode("EUC-KR")
                soup = BeautifulSoup(resp, "html.parser")

                electricity = soup.find("div", class_="billBox clearfix")
                if electricity:
                    electricity_info = {
                        "에너지 유형": "전기",
                        "총액": electricity.find("div", class_="enePay").text.strip(),
                        "사용량": electricity.find("p", class_="eneDownTxt").text.split("(")[1].split(")")[0].strip(),
                        "평균 사용량": electricity.find("p", class_="eneUpTxt").text.split("(")[1].split(")")[0].strip(),
                        "비교": electricity.find("div", class_="energy_data date1").find("strong").text.strip(),
                    }

                    details = electricity.find("div", class_="tbl_bill").find_all("tr")
                    for row in details:
                        cols = row.find_all("td")
                        electricity_info[row.th.text.strip()] = cols[0].text.strip()
                        if len(cols) > 1:
                            electricity_info[row.find_all("th")[1].text.strip()] = cols[1].text.strip()

                    self.data.energy.type.append(electricity_info)

                heat = soup.find_all("div", class_="billBox clearfix")[1]
                if heat:
                    heat_info = {
                        "에너지 유형": "열",
                        "총액": heat.find("div", class_="enePay").text.strip(),
                        "비교": heat.find("div", class_="energy_data date1").find("strong").text.strip(),
                    }

                    details = heat.find("div", class_="tbl_bill").find_all("tr")
                    for row in details:
                        cols = row.find_all("td")
                        heat_info[row.th.text.strip()] = cols[0].text.strip()
                        if len(cols) > 1:
                            heat_info[row.find_all("th")[1].text.strip()] = cols[1].text.strip()
                        
                    self.data.energy.type.append(heat_info)
        except Exception as ex:
            LOGGER.error(f"An exception occurred while processing energy usage type: {ex}")
    
    async def _visit_reservation(self):
        """Vehicle visit reservation."""
