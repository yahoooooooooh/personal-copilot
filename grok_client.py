# grok_client.py (v1.7 - 增强错误处理)
import os
from openai import OpenAI, RateLimitError, AuthenticationError
import time
import sys
import requests

# 全局变量
grok_client = None
DEFAULT_GROK_MODEL = "grok-3-beta"  # 默认文本模型

def initialize_grok_client():
    """初始化 Grok 客户端"""
    global grok_client
    local_grok_api_key = os.getenv("GROK_API_KEY")
    if not local_grok_api_key:
        print("--- [Grok Client] 错误: 未在 .env 文件中或环境变量中找到 GROK_API_KEY ---")
        return None
    try:
        print(f"--- [Grok Client] 正在使用 API Key: ...{local_grok_api_key[-4:]}")
        grok_client = OpenAI(api_key=local_grok_api_key, base_url="https://api.x.ai/v1")
        print(f"--- [Grok Client] 客户端初始化成功 (默认模型: {DEFAULT_GROK_MODEL}) ---")
        return grok_client
    except Exception as e:
        print(f"!!! [Grok Client] 客户端初始化失败: {e} !!!")
        grok_client = None
        return None

def get_grok_response_stream(messages, chunk_callback, model=DEFAULT_GROK_MODEL):
    """
    调用 Grok API 获取流式回复（适用于文本模型）。
    参数:
        messages (list): 发送给模型的完整消息列表。
        chunk_callback (function): 每收到一个数据块时调用的回调函数。
                                   回调函数接收一个参数：收到的文本块 (str)。
                                   如果回调函数返回 False，则停止接收。
        model (str): 指定使用的模型，默认为 DEFAULT_GROK_MODEL。
    返回:
        str: 累积的完整回复文本。
    异常:
        Exception: 如果 API 调用或流处理失败，则抛出异常。
    """
    global grok_client
    if not grok_client:
        print("--- [Grok Client] 客户端未初始化，尝试重新初始化... ---")
        if not initialize_grok_client():
            raise ConnectionError("Grok 客户端未初始化或初始化失败")

    print(f"--- [Grok Client] 准备调用 Grok 流式 API (模型: {model}) ---")
    start_time = time.time()
    accumulated_text = ""

    try:
        # 优化请求参数，减少不必要的数据传输
        stream = grok_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.7,  # 设置温度参数，控制生成文本的创造性
            max_tokens=4096  # 设置最大 token 数，限制响应长度
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                content_piece = chunk.choices[0].delta.content
                accumulated_text += content_piece
                if chunk_callback(content_piece) is False:
                    print("--- [Grok Client] 回调函数请求停止接收 ---")
                    break
            else:
                # 如果没有文本内容，可能是图像模型返回的数据
                print("--- [Grok Client] 警告: 收到非文本内容块，可能不支持该模型的输出格式 ---")

        end_time = time.time()
        print(f"--- [Grok Client] Grok 流式 API 调用完成! 耗时: {end_time - start_time:.2f} 秒 ---")
        if not accumulated_text:
            print("--- [Grok Client] 警告: 未收到任何文本内容，可能该模型不支持文本对话 ---")
            accumulated_text = "抱歉，该模型可能不支持文本对话或返回了非文本内容（如图像）。请尝试切换到其他模型。"
        return accumulated_text

    except RateLimitError as rle:
        error_msg = "请求频率过高，Grok API 限流。请稍后再试或检查您的API配额。"
        print(f"!!! [Grok Client] 流式 API 调用出错 - 限流: {rle} !!!")
        raise Exception(error_msg)
    except AuthenticationError as ae:
        error_msg = "Grok API 认证失败。请检查您的API密钥是否正确。"
        print(f"!!! [Grok Client] 流式 API 调用出错 - 认证失败: {ae} !!!")
        raise Exception(error_msg)
    except ConnectionError as ce:
        error_msg = "无法连接到 Grok API 服务器。请检查网络连接或API密钥是否有效。"
        print(f"!!! [Grok Client] 流式 API 调用出错 - 连接错误: {ce} !!!")
        raise ConnectionError(error_msg)
    except Exception as e:
        error_msg = f"Grok API 调用或处理过程中发生未知错误: {str(e)}"
        print(f"!!! [Grok Client] 流式 API 调用或处理出错: {e} !!!")
        raise Exception(error_msg)

def get_grok_image_response(messages, model="grok-2-image-latest"):
    """
    调用 Grok API 获取图像生成结果（适用于图像模型）。
    参数:
        messages (list): 发送给模型的完整消息列表。
        model (str): 指定使用的图像生成模型，默认为 grok-2-image-latest。
    返回:
        str: 图像 URL 或错误信息。
    异常:
        Exception: 如果 API 调用失败，则抛出异常。
    """
    global grok_client
    if not grok_client:
        print("--- [Grok Client] 客户端未初始化，尝试重新初始化... ---")
        if not initialize_grok_client():
            raise ConnectionError("Grok 客户端未初始化或初始化失败")

    print(f"--- [Grok Client] 准备调用 Grok 图像生成 API (模型: {model}) ---")
    start_time = time.time()

    try:
        # 提取用户提示词（假设最后一个用户消息是图像生成提示）
        prompt = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                prompt = msg.get("content", "")
                break

        if not prompt:
            print("--- [Grok Client] 警告: 未找到用户提示词 ---")
            return "图像生成失败，未找到有效的提示词。"

        # 使用图像生成端点，简化参数
        response = grok_client.images.generate(
            model=model,
            prompt=prompt,
            n=1  # 生成一张图像
            # 移除 size 参数，因为不受支持
        )

        end_time = time.time()
        print(f"--- [Grok Client] Grok 图像生成 API 调用完成! 耗时: {end_time - start_time:.2f} 秒 ---")

        # 提取图像 URL（根据 OpenAI 风格的响应格式）
        if response.data and len(response.data) > 0 and hasattr(response.data[0], 'url'):
            image_url = response.data[0].url
            print(f"--- [Grok Client] 找到图像 URL: {image_url} ---")
            return image_url
        else:
            print("--- [Grok Client] 警告: 响应中未找到图像 URL ---")
            return "图像生成成功，但未找到图像 URL。"

    except RateLimitError as rle:
        error_msg = "请求频率过高，Grok API 限流。请稍后再试或检查您的API配额。"
        print(f"!!! [Grok Client] 图像生成 API 调用出错 - 限流: {rle} !!!")
        raise Exception(error_msg)
    except AuthenticationError as ae:
        error_msg = "Grok API 认证失败。请检查您的API密钥是否正确。"
        print(f"!!! [Grok Client] 图像生成 API 调用出错 - 认证失败: {ae} !!!")
        raise Exception(error_msg)
    except ConnectionError as ce:
        error_msg = "无法连接到 Grok API 服务器。请检查网络连接或API密钥是否有效。"
        print(f"!!! [Grok Client] 图像生成 API 调用出错 - 连接错误: {ce} !!!")
        raise ConnectionError(error_msg)
    except Exception as e:
        error_msg = f"Grok API 图像生成过程中发生未知错误: {str(e)}"
        print(f"!!! [Grok Client] 图像生成 API 调用出错: {e} !!!")
        raise Exception(error_msg)
