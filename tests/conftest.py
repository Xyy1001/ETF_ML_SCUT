"""
Playwright配置和fixtures
"""

import pytest
from playwright.sync_api import Playwright, Browser, BrowserContext, Page


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """浏览器上下文参数配置"""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1920,
            "height": 1080,
        },
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """浏览器启动参数配置"""
    return {
        **browser_type_launch_args,
        "headless": True,  # CI环境使用无头模式
        "slow_mo": 100,  # 减慢操作，便于观察（可选）
    }


@pytest.fixture(scope="function")
def context(browser: Browser):
    """为每个测试创建独立的浏览器上下文"""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext):
    """为每个测试创建新页面"""
    page = context.new_page()
    yield page
    page.close()
