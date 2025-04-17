# web_search.py (v1.2 - 适配 Python 3.9，修改类型提示语法)
import os
from tavily import TavilyClient
import logging
from typing import Union  # 导入 typing.Union 以支持 Python 3.9

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='--- [%(levelname)s - %(module)s] %(message)s')

def perform_search(query: str, max_results: int = 3) -> Union[str, None]:
    """Performs a web search using Tavily API and returns formatted results.
    参数:
        query (str): 搜索查询字符串
        max_results (int): 最大返回结果数量，默认为3
    返回:
        Union[str, None]: 格式化后的搜索结果字符串，如果搜索失败则返回None
    """
    # --- 在函数内部获取 API Key ---
    local_tavily_api_key = os.getenv("TAVILY_API_KEY")

    if not local_tavily_api_key:  # 使用函数内获取的 key
        logging.warning("Tavily API Key not found in environment variables.")
        return None
    try:
        logging.info(f"Performing Tavily search for query: '{query[:50]}...'")
        # --- 使用函数内获取的 key 初始化客户端 ---
        client = TavilyClient(api_key=local_tavily_api_key)
        # search_depth='advanced' 可能提供更详细结果，但消耗点数可能更多
        # 优化搜索参数，减少不必要的数据传输
        response = client.search(
            query=query, 
            search_depth="basic", 
            max_results=max_results,
            include_raw_content=False,  # 不包含原始内容，减少数据量
            include_images=False  # 不包含图片，减少数据量
        )

        if response and 'results' in response and response['results']:
            formatted_results = []
            for i, result in enumerate(response['results']):
                title = result.get('title', 'N/A')
                content = result.get('content', 'N/A').strip()  # 移除片段首尾空白
                url = result.get('url', 'N/A')
                # 简化格式，减少 token 占用
                formatted_results.append(f"[{i+1}] {title}\n   {content}\n   (Source: {url})")
            final_string = "\n\n".join(formatted_results)
            logging.info(f"Tavily search successful, returning {len(response['results'])} results.")
            # logging.debug(f"Formatted results:\n{final_string}")  # Debug 时可以取消注释
            return final_string
        else:
            logging.info(f"No results found or empty response from Tavily for query: {query}")
            return None
    except Exception as e:
        logging.error(f"Error during Tavily search for query '{query}': {e}", exc_info=True)  # 记录完整错误
        return None

# 简单测试 (可选)
# if __name__ == '__main__':
#     # 如果要单独测试此文件，需要确保 .env 文件在正确的位置或手动设置环境变量
#     # load_dotenv()  # 可能需要加载 .env
#     results = perform_search("最新的 AI 新闻有哪些？")
#     if results:
#         print("Search Results:\n", results)
#     else:
#         print("Search failed or no results.")
