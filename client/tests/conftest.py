import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "http://localhost:3000"


@pytest.fixture(scope="session")
def driver():
    """
    Single Chrome instance shared across all tests in the session.
    scope="session" means the browser opens once and closes at the end.

    Requires the Next.js dev server to be running:
        cd client && npm run dev
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.binary_location = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    # options.add_argument("--headless")  # uncomment to run without opening a window

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.implicitly_wait(5)  # wait up to 5s for elements to appear before failing
    driver.maximize_window()

    yield driver

    driver.quit()


@pytest.fixture(autouse=True)
def reset_to_home(driver):
    """Navigate back to the homepage before each test."""
    driver.get(BASE_URL)
