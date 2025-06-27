"""
此模块通过 Playwright 从今日头条获取 topK 新闻 URL，
并保存新闻内容和对应的静态 HTML 文件。
"""
import os
from fastapi import FastAPI
from playwright.async_api import async_playwright
from conf.common_config import config

app = FastAPI()

async def fetch_topk_news(topk: int) -> list:
    """
    从今日头条获取 topK 新闻的 URL 和标题。

    :param topk: 需要获取的新闻数量。
    :return: 包含新闻 URL 和标题的列表。
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://www.toutiao.com/?wid=1751011824025')
        
        # 等待新闻列表加载
        await page.wait_for_selector('div[data-e2e="feed-item"]')
        
        news_list = []
        news_items = await page.query_selector_all('div[data-e2e="feed-item"]')[:topk]
        for item in news_items:
            link = await item.query_selector('a')
            if link:
                url = await link.get_attribute('href')
                title = await link.text_content()
                news_list.append({'url': url, 'title': title})
        
        await browser.close()
        return news_list

async def save_news_content(news_data: list):
    """
    保存新闻内容和静态 HTML 文件。

    :param news_data: 包含新闻 URL 和标题的列表。
    """
    news_dir = os.path.join(os.getcwd(), 'news_data')
    os.makedirs(news_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for news in news_data:
            page = await browser.new_page()
            await page.goto(news['url']) if news['url'] else None
            
            # 保存静态 HTML
            html_content = await page.content() if news['url'] else ''
            filename = f"{news['title'][:20]}.html".replace('/', '_')
            with open(os.path.join(news_dir, filename), 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        await browser.close()

@app.get("/topk_news")
async def get_topk_news(topk: int = 10):
    """
    获取 topK 新闻并保存内容。

    :param topk: 需要获取的新闻数量，默认值为 10。
    :return: 新闻列表。
    """
    news_data = await fetch_topk_news(topk)
    await save_news_content(news_data)
    return news_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.news_service_port)