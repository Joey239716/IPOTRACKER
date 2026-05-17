import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://localhost:3000"
TIMEOUT = 10


# ---------------------------------------------------------------------------
# Page load
# ---------------------------------------------------------------------------

class TestHomePage:
    def test_upcoming_ipos_heading_is_visible(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        heading = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Upcoming IPOs')]")))
        assert heading.is_displayed()

    def test_table_renders_rows(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tbody tr")))
        assert len(rows) > 0

    def test_navbar_is_visible(self, driver):
        nav = driver.find_element(By.CSS_SELECTOR, "nav")
        assert nav.is_displayed()

    def test_table_has_company_column(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
        header = driver.find_element(By.XPATH, "//thead//th[contains(text(),'Company') or .//*[contains(text(),'Company')]]")
        assert header.is_displayed()

    def test_exchange_badges_are_visible(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
        # Exchange badges are rounded pill spans in each row
        badges = driver.find_elements(By.CSS_SELECTOR, "tbody td span[class*='rounded-full']")
        assert len(badges) > 0

    def test_view_all_link_is_present(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
        link = driver.find_element(By.XPATH, "//a[contains(text(),'View All')]")
        assert link.is_displayed()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_input_is_present(self, driver):
        search = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='Search']")
        assert search.is_displayed()

    def test_search_filters_table(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))

        rows_before = len(driver.find_elements(By.CSS_SELECTOR, "tbody tr"))

        search = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='Search']")
        search.clear()
        search.send_keys("a")

        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "tbody tr")) > 0)
        rows_after = len(driver.find_elements(By.CSS_SELECTOR, "tbody tr"))

        assert rows_after <= rows_before


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestSorting:
    def test_clicking_same_header_twice_reverses_order(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))

        header = driver.find_element(By.CSS_SELECTOR, "thead th[class*='cursor-pointer']")

        header.click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
        first_asc = driver.find_elements(By.CSS_SELECTOR, "tbody tr")[0].text

        header = driver.find_element(By.CSS_SELECTOR, "thead th[class*='cursor-pointer']")
        header.click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
        first_desc = driver.find_elements(By.CSS_SELECTOR, "tbody tr")[0].text

        assert first_asc != first_desc


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_logo_click_returns_to_home(self, driver):
        driver.get(f"{BASE_URL}/about")
        logo = driver.find_element(By.CSS_SELECTOR, "nav a[href='/']")
        logo.click()
        WebDriverWait(driver, TIMEOUT).until(EC.url_to_be(f"{BASE_URL}/"))
        assert driver.current_url == f"{BASE_URL}/"

    def test_login_page_loads(self, driver):
        driver.get(f"{BASE_URL}/login")
        wait = WebDriverWait(driver, TIMEOUT)
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
        assert email_input.is_displayed()

    def test_login_page_has_password_field(self, driver):
        driver.get(f"{BASE_URL}/login")
        wait = WebDriverWait(driver, TIMEOUT)
        password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
        assert password_input.is_displayed()

    def test_about_page_loads(self, driver):
        driver.get(f"{BASE_URL}/about")
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        assert "localhost:3000/about" in driver.current_url


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------

class TestAuthGate:
    def test_unauthenticated_star_click_shows_login_modal(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))

        star_btn = driver.find_element(By.CSS_SELECTOR, "tbody tr button[aria-label='Toggle Watchlist']")
        star_btn.click()

        modal_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Sign Up')]"))
        )
        assert modal_btn.is_displayed()

    def test_sign_in_link_visible_in_navbar(self, driver):
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "nav")))
        sign_in = driver.find_element(By.XPATH, "//nav//*[contains(text(),'Sign In') or contains(text(),'Login') or contains(@href,'login')]")
        assert sign_in.is_displayed()
