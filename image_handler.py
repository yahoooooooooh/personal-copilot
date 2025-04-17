# image_handler.py (v1.5 - 修复图像模型提示问题并支持Artifacts渲染)
import threading
import customtkinter as ctk
import tkinter as tk
import os
import sys
import datetime
import requests
from PIL import Image
import grok_client
from prompts import PROMPT_NETWORKING, PROMPT_ARTIFACTS # 导入 PROMPT_ARTIFACTS 用于识别
import web_search
import logging
import api_client  # 导入DeepSeek客户端
import tempfile

class ImageHandler:
    def __init__(self, controller, app, ui_elements):
        """
        初始化图像处理器。
        参数:
            controller: AppController 实例，用于访问状态和配置。
            app: 主应用程序实例，用于 UI 更新。
            ui_elements: UI 控件字典，用于更新界面。
        """
        self.controller = controller
        self.app = app
        self.ui = ui_elements
        self.chat_display = self.ui.get('chat_display')  # 使用固定的 Textbox
        self.status_label = self.ui.get('status_label')

    def send_grok_image_message_thread(self, user_input, message_history, model):
        """处理图像生成模型的请求，移除中转模型逻辑"""
        try:
            if not self.controller.is_streaming:
                logging.info("[Grok 图像线程] 开始时 is_streaming 为 False，中止。")
                return

            logging.info("[Grok 图像线程] 开始处理图像生成请求")

            # --- 关键修改：为图像模型准备干净的消息历史 ---
            # 图像模型通常只需要最后一个用户提示，但为保持上下文，我们传递用户和助手的对话，移除系统提示
            image_model_history = []
            last_user_prompt = ""
            for msg in message_history:
                role = msg.get("role")
                content = msg.get("content", "")
                # 忽略系统消息，特别是包含 Artifacts 指令的
                if role == "system":
                    logging.info("[Grok 图像线程] 忽略系统消息，不发送给图像模型: %s...", content[:50])
                    continue
                elif role == "user":
                    image_model_history.append({"role": "user", "content": content})
                    last_user_prompt = content # 记录最后的用户输入
                elif role == "assistant":
                    image_model_history.append({"role": "assistant", "content": content})
                
            # 确保最后一条是用户消息（如果历史记录不为空）
            if image_model_history and image_model_history[-1]["role"] != "user":
                 # 如果最后不是用户消息，可能需要添加 user_input，或者确保 message_history 总是以用户消息结尾
                 logging.warning("[Grok 图像线程] 准备发送给图像模型的历史记录最后一条不是用户消息。")
                 # 如果 last_user_prompt 有效，可以考虑只发送它
                 if last_user_prompt:
                     logging.info("[Grok 图像线程] 使用最后记录的用户提示作为图像生成提示。")
                     # image_model_history = [{"role": "user", "content": last_user_prompt}] # 或者只发送最后的用户提示
                 else:
                     logging.error("[Grok 图像线程] 无法确定用于图像生成的提示！")
                     self.app.after(0, self.controller.message_handler.handle_stream_end, ValueError("无法确定图像生成提示"), user_input, None, "Grok")
                     return

            # 如果历史记录为空（不太可能，但作为保险），只使用 user_input
            if not image_model_history and user_input:
                 logging.warning("[Grok 图像线程] 过滤后的历史记录为空，仅使用当前用户输入作为提示。")
                 image_model_history = [{"role": "user", "content": user_input}]
            elif not image_model_history and not user_input:
                 logging.error("[Grok 图像线程] 没有有效的用户提示可用于图像生成！")
                 self.app.after(0, self.controller.message_handler.handle_stream_end, ValueError("无有效图像生成提示"), user_input, None, "Grok")
                 return
                 
            # --- 结束关键修改 ---

            logging.info("[Grok 图像线程] 准备调用 Grok 图像生成 API (模型: %s) 使用过滤后的历史记录", model)
            # 使用过滤后的历史记录调用API
            image_url = grok_client.get_grok_image_response(image_model_history, model=model)
            logging.info("[Grok 图像线程] API 调用完成，图像 URL: %s", image_url)

            if self.controller.is_streaming:
                if image_url and image_url.startswith("http"):
                    # 尝试下载图像并保存到指定目录
                    try:
                        response = requests.get(image_url, stream=True, timeout=10)
                        if response.status_code == 200:
                            # 指定保存目录，使用环境变量或默认路径
                            save_dir = os.getenv("IMAGE_SAVE_DIR", os.path.join(tempfile.gettempdir(), "grok_images"))
                            # 确保目录存在
                            os.makedirs(save_dir, exist_ok=True)
                            # 使用时间戳生成唯一文件名
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            # 尝试从URL获取文件扩展名，如果失败则默认为.png
                            try:
                                file_extension = os.path.splitext(image_url.split('?')[0])[-1] # 处理可能的URL参数
                                if not file_extension or len(file_extension) > 5: # 简单检查扩展名有效性
                                    file_extension = '.png'
                            except Exception:
                                file_extension = '.png'
                                
                            save_file = os.path.join(save_dir, f"grok_image_{timestamp}{file_extension}")
                            with open(save_file, 'wb') as f:
                                for chunk in response.iter_content(1024):
                                    f.write(chunk)
                            logging.info("[Grok 图像线程] 图像已保存到: %s", save_file)
                            
                            # --- 关键修改：根据 Artifacts 模式决定显示方式 ---
                            if self.controller.chat_manager.is_artifacts_mode_enabled():
                                logging.info("[Grok 图像线程] Artifacts模式启用，渲染图片到浏览器")
                                # 移除思考中消息（如果存在）
                                self.controller._remove_thinking_message()
                                # 调用渲染方法
                                self.app.after(0, self.controller.render_artifacts_image, save_file)
                                # 因为图片显示在浏览器，主聊天区可以显示一个简单的提示
                                self.app.after(10, self.controller.display_message, "assistant", "图像已生成，请查看浏览器。")
                                # 结束流处理，并传递 save_file 作为 full_response
                                self.app.after(20, self.controller.message_handler.handle_stream_end, None, user_input, save_file, "Grok")
                            else:
                                logging.info("[Grok 图像线程] Artifacts模式禁用，在聊天区域显示图片路径")
                                # 否则只显示本地路径，不显示图片
                                self.app.after(0, self.display_image_path, save_file)
                        else:
                            logging.error("[Grok 图像线程] 下载图像失败，状态码: %d", response.status_code)
                            self.app.after(0, self.controller.message_handler.handle_stream_end, None, user_input, f"图像生成成功，但下载失败 (状态码: {response.status_code}): {image_url}\n请手动访问链接查看。", "Grok")
                    except Exception as download_err:
                        logging.error("[Grok 图像线程] 下载图像时出错: %s", download_err)
                        self.app.after(0, self.controller.message_handler.handle_stream_end, None, user_input, f"图像生成成功，但无法下载: {image_url}\n请手动访问链接查看。", "Grok")
                elif image_url: # 如果返回的不是URL，可能是错误信息
                     logging.warning("[Grok 图像线程] API 返回的不是有效的 URL: %s", image_url)
                     self.app.after(0, self.controller.message_handler.handle_stream_end, None, user_input, image_url, "Grok")
                else: # 如果 image_url 为 None 或空
                     logging.error("[Grok 图像线程] API 未返回有效的图像 URL 或错误信息")
                     self.app.after(0, self.controller.message_handler.handle_stream_end, ValueError("API未返回图像URL"), user_input, None, "Grok")
            else:
                logging.info("[Grok 图像线程] API 调用完成，但 is_streaming 已为 False，不调用 handle_stream_end")

        except ConnectionError as conn_err:
            logging.error("[Grok 图像线程] API 连接错误: %s", conn_err)
            if self.controller.is_streaming: self.app.after(0, self.controller.message_handler.handle_stream_end, conn_err, user_input, None, "Grok")
        except Exception as e:
            logging.error("[Grok 图像线程] 发送消息线程出错: %s", e, exc_info=True) # 添加 exc_info=True 获取更详细的回溯信息
            if self.controller.is_streaming: self.app.after(0, self.controller.message_handler.handle_stream_end, e, user_input, None, "Grok")

    def display_image_path(self, image_path):
        """在聊天流中显示图像的本地文件路径，仅在非Artifacts模式下调用"""
        try:
            # 移除"思考中..."消息
            self.controller._remove_thinking_message()
            
            # 确保 chat_display 存在
            if not self.chat_display:
                logging.error("[错误] chat_display 未初始化，无法显示图像路径")
                self.app.after(0, self.controller.message_handler.handle_stream_end, None, None, f"图像生成成功，但无法显示路径: chat_display 未初始化", "Grok")
                return

            # 插入 AI 标题和文件路径
            self.chat_display.configure(state="normal")
            last_line = self.chat_display.get("end-2l", "end-1l").strip()
            if not last_line.startswith("AI:"):
                self.chat_display.insert("end", "AI:\n")
            # 准备要插入的消息内容
            message_content = f"生成的图像已保存到本地（点击路径打开文件）：\n{image_path}\n\n"
            self.chat_display.insert("end", message_content)
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")

            logging.info("图像本地路径已显示在聊天流中")
            # 结束流处理，并将图片路径消息保存到历史记录
            self.app.after(0, self.controller.message_handler.handle_stream_end, None, None, message_content.strip(), "Grok")
            
        except Exception as e:
            logging.error("显示图像路径时出错: %s", e)
            self.app.after(0, self.controller.message_handler.handle_stream_end, None, None, f"图像生成成功，但无法显示路径: {e}", "Grok")
