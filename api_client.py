# api_client.py (增强错误处理并使用 logging 模块)
import os
from openai import OpenAI, RateLimitError, AuthenticationError
import time
import logging

client = None
DEEPSEEK_MODEL = "deepseek-chat"

def initialize_api_client(api_key):
    """初始化 DeepSeek API 客户端"""
    global client
    if not api_key:
        logging.error("[API Client] 错误: 未提供 API Key")
        return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        logging.info("[API Client] 客户端初始化成功 (模型: %s)", DEEPSEEK_MODEL)
        return client
    except Exception as e:
        logging.error("[API Client] 客户端初始化失败: %s", e)
        client = None
        return None

def get_deepseek_response_stream(messages, chunk_callback):
    """
    调用 DeepSeek API 获取流式回复。
    参数:
        messages (list): 发送给模型的完整消息列表。
        chunk_callback (function): 每收到一个数据块时调用的回调函数。
                                   回调函数接收一个参数：收到的文本块 (str)。
                                   如果回调函数返回 False，则停止接收。
    返回:
        str: 累积的完整回复文本。
    异常:
        Exception: 如果 API 调用或流处理失败，则抛出异常。
    """
    global client, DEEPSEEK_MODEL
    if not client:
        raise ConnectionError("API 客户端未初始化")

    logging.info("[API Client] 准备调用流式 API (模型: %s)", DEEPSEEK_MODEL)
    start_time = time.time()
    accumulated_text = ""  # 用于累积完整回复

    try:
        # 优化请求参数，减少不必要的数据传输
        stream = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            stream=True,
            timeout=30,  # 添加超时设置，单位为秒
            temperature=0.7,  # 设置温度参数，控制生成文本的创造性
            max_tokens=4096  # 设置最大 token 数，限制响应长度
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                content_piece = chunk.choices[0].delta.content
                accumulated_text += content_piece  # 累积文本
                # 调用回调传递数据块
                if chunk_callback(content_piece) is False:
                    logging.info("[API Client] 回调函数请求停止接收")
                    break

        end_time = time.time()
        logging.info("[API Client] 流式 API 调用完成! 耗时: %.2f 秒", end_time - start_time)
        return accumulated_text  # 返回累积的完整文本

    except RateLimitError as rle:
        error_msg = "请求频率过高，DeepSeek API 限流。请稍后再试或检查您的API配额。"
        logging.error("[API Client] 流式 API 调用出错 - 限流: %s", rle)
        raise Exception(error_msg)
    except AuthenticationError as ae:
        error_msg = "DeepSeek API 认证失败。请检查您的API密钥是否正确。"
        logging.error("[API Client] 流式 API 调用出错 - 认证失败: %s", ae)
        raise Exception(error_msg)
    except ConnectionError as ce:
        error_msg = "无法连接到 DeepSeek API 服务器。请检查网络连接或API密钥是否有效。"
        logging.error("[API Client] 流式 API 调用出错 - 连接错误: %s", ce)
        raise ConnectionError(error_msg)
    except Exception as e:
        error_msg = f"DeepSeek API 调用或处理过程中发生未知错误: {str(e)}"
        logging.error("[API Client] 流式 API 调用或处理出错: %s", e)
        raise Exception(error_msg)

def set_deepseek_model(model_name):
    global DEEPSEEK_MODEL
    DEEPSEEK_MODEL = model_name
    logging.info("[API Client] 模型已切换为: %s", DEEPSEEK_MODEL)
