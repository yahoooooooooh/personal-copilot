# message_handler.py (v1.27 - 优化流式传输性能，减少UI更新频率，限制输出长度，修复Artifacts后聊天记录消失，隐藏Artifacts指令代码，修复模型回复出现两次，支持输入超长转为附件)
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import tempfile
from pathlib import Path
import api_client
import grok_client
import web_search
from prompts import PROMPT_NETWORKING
import logging
import datetime
import re

class MessageHandler:
    def __init__(self, controller, chat_manager, app, ui_elements):
        """
        初始化消息处理器。
        参数:
            controller: AppController 实例，用于访问状态和配置。
            chat_manager: ChatManager 实例，用于管理聊天历史。
            app: 主应用程序实例，用于 UI 更新。
            ui_elements: UI 控件字典，用于更新界面。
        """
        self.controller = controller
        self.chat_manager = chat_manager
        self.app = app
        self.ui = ui_elements
        self.input_entry = self.ui.get('input_entry')
        self.status_label = self.ui.get('status_label')
        self.chat_display = self.ui.get('chat_display')
        self.upload_button = self.ui.get('upload_button')
        # 新增：存储临时附件的列表
        self.temp_attachments = []
        # 绑定上传按钮事件
        if self.upload_button:
            self.upload_button.configure(command=self.handle_file_upload)
        # 新增：绑定输入框的粘贴事件（通过绑定 <Control-v>）
        if self.input_entry:
            self.input_entry.bind("<Control-v>", self.handle_paste_event)
        # 新增：用于分批更新UI的队列和标志
        self.chunk_queue = []
        self.is_processing_queue = False
        # 新增：用于累积流式传输数据的缓冲区和计时器
        self.stream_buffer = ""
        self.buffer_size_limit = 500  # 缓冲区大小限制，超过此大小更新UI
        self.buffer_time_limit = 500  # 缓冲区时间限制（毫秒），超过此时间更新UI
        self.last_buffer_flush = 0  # 上次清空缓冲区的时间戳
        # 新增：用于跟踪是否已经显示了部分流式传输内容
        self.has_displayed_streaming_content = False

    def handle_file_upload(self):
        """处理文件上传"""
        file_path = filedialog.askopenfilename(
            title="选择TXT文件",
            filetypes=[("Text files", "*.txt")]
        )
        if not file_path:
            logging.info("[文件上传] 用户取消了文件选择")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logging.info("[文件上传] 成功读取文件: %s, 长度: %d 字符", file_path, len(content))
            self.save_as_attachment(content, source=os.path.basename(file_path))
        except Exception as e:
            logging.error("[文件上传] 读取文件出错: %s", e)
            messagebox.showerror("文件读取错误", f"无法读取文件：{e}")

    def handle_paste_event(self, event):
        """处理粘贴事件，检查内容长度并转为附件"""
        try:
            # 获取剪贴板内容
            pasted_text = self.app.clipboard_get()
            if len(pasted_text) > 100:  # 超过100字符转为附件
                logging.info("[粘贴事件] 粘贴内容长度 %d 超过阈值 100，自动转为附件", len(pasted_text))
                self.save_as_attachment(pasted_text, source="粘贴内容")
                # 清空输入框，显示提示信息
                self.input_entry.delete("1.0", tk.END)
                self.input_entry.insert("1.0", f"已将粘贴内容（{len(pasted_text)}字符）保存为附件，继续输入...")
                # 阻止默认粘贴行为
                return "break"
        except tk.TclError:
            logging.warning("[粘贴事件] 无法获取剪贴板内容")
        except Exception as e:
            logging.error("[粘贴事件] 处理出错: %s", e)

    def save_as_attachment(self, content, source="用户输入"):
        """将长内容保存为临时附件"""
        try:
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"copilot_attachment_{len(self.temp_attachments)}_{id(content)}_{source.replace(' ', '_')}.txt")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.temp_attachments.append({"file_path": temp_file, "source": source, "length": len(content)})
            logging.info("[附件保存] 已保存内容到临时文件: %s, 来源: %s, 长度: %d", temp_file, source, len(content))
            # 在UI中显示附件信息
            self.controller.display_message("user", f"已保存附件（来源：{source}，长度：{len(content)}字符）")
        except Exception as e:
            logging.error("[附件保存] 保存临时文件出错: %s", e)
            messagebox.showerror("处理错误", f"无法保存附件：{e}")

    def handle_send_message(self, event=None):
        """处理发送消息的事件，调用 message_handler"""
        if self.controller.is_streaming:
            logging.warning("正在处理上一条消息，请稍候...")
            messagebox.showwarning("请稍候", "正在处理上一条消息，请等待完成后再发送。")
            return

        if not self.controller.selected_backend_config or self.controller.selected_backend_config['type'] == 'Error':
            messagebox.showerror("无可用后端", "请先在设置中配置并选择一个有效的 API 后端。")
            logging.error("尝试发送消息但无有效后端选中")
            return

        # 获取输入内容
        user_input = self.input_entry.get("1.0", tk.END).strip()
        final_input = user_input if user_input else ""
        display_text = final_input

        # 检查输入长度是否超过阈值（例如500字符），如果超过则转为附件
        input_length_threshold = 500
        if len(final_input) > input_length_threshold:
            logging.info("[输入处理] 输入内容长度 %d 超过阈值 %d，自动转为附件", len(final_input), input_length_threshold)
            self.save_as_attachment(final_input, source="用户输入")
            # 清空输入框并显示提示
            self.input_entry.delete("1.0", tk.END)
            self.input_entry.insert("1.0", f"已将输入内容（{len(final_input)}字符）保存为附件，继续输入...")
            display_text = f"已将输入内容（{len(final_input)}字符）保存为附件"

        # 检查是否有附件
        if self.temp_attachments:
            attachments_info = "\n".join([f"附件 {i+1}: 来源 {att['source']}, 长度 {att['length']} 字符" for i, att in enumerate(self.temp_attachments)])
            if final_input and len(final_input) <= input_length_threshold:
                display_text = f"最终输入: {final_input}\n已上传附件:\n{attachments_info}"
            else:
                display_text = f"已上传附件:\n{attachments_info}"
            logging.info("检测到 %d 个附件，将与最终输入一起发送", len(self.temp_attachments))

        if not final_input and not self.temp_attachments:
            logging.info("用户输入为空且无附件，已忽略")
            return

        self.input_entry.delete("1.0", tk.END)
        self.controller.display_message("user", display_text)
        logging.info("[处理流程] 添加用户消息到 ChatManager")

        # 构建完整用户输入（包括附件内容）
        full_content_parts = []
        if self.temp_attachments:
            for i, att in enumerate(self.temp_attachments):
                try:
                    with open(att['file_path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                    full_content_parts.append(f"附件 {i+1} (来源: {att['source']}, 长度: {att['length']} 字符):\n{content}")
                except Exception as e:
                    logging.error("[读取附件] 读取附件 %s 出错: %s", att['file_path'], e)
                    full_content_parts.append(f"附件 {i+1} (来源: {att['source']}, 长度: {att['length']} 字符): 读取失败，无法包含内容")
        if final_input and len(final_input) <= input_length_threshold:
            full_content_parts.append(f"最终输入:\n{final_input}")

        full_content = "\n\n---\n\n".join(full_content_parts) if full_content_parts else ""
        self.chat_manager.add_message_to_current_chat("user", full_content if full_content else final_input)
        self.controller.display_thinking_message()

        self.controller.is_streaming = True
        if self.input_entry: self.input_entry.configure(state="disabled")
        if self.status_label: self.status_label.configure(text="正在处理输入...")

        # 显示取消按钮
        cancel_button = self.ui.get('cancel_button')
        if cancel_button:
            cancel_button.pack(side="right", padx=(5, 5))
            logging.info("[UI响应性] 显示取消按钮")

        backend_type = self.controller.selected_backend_config['type']
        provider = self.controller.selected_backend_config['provider']
        thread = None

        try:
            logging.info("[处理流程] 获取包含最新用户消息的历史记录副本")
            message_history_copy = self.chat_manager.get_current_history()

            if backend_type == "API":
                if provider == "DeepSeek":
                    if not api_client.client:
                        self.app.after(0, self.handle_stream_end, ConnectionError("DeepSeek API 未初始化"), display_text, None, "DeepSeek")
                        return
                    thread = threading.Thread(target=self.send_deepseek_message_thread, args=(display_text, message_history_copy), daemon=True)
                elif provider == "Grok":
                    if not grok_client.grok_client:
                        self.app.after(0, self.handle_stream_end, ConnectionError("Grok API 未初始化"), display_text, None, "Grok")
                        return
                    model = self.controller.selected_backend_config.get('model', grok_client.DEFAULT_GROK_MODEL)
                    if model == "grok-2-image-latest":
                        from image_handler import ImageHandler
                        image_handler = ImageHandler(self.controller, self.app, self.ui)
                        thread = threading.Thread(target=image_handler.send_grok_image_message_thread, args=(display_text, message_history_copy, model), daemon=True)
                    else:
                        thread = threading.Thread(target=self.send_grok_message_thread, args=(display_text, message_history_copy, model), daemon=True)
                else:
                    self.app.after(0, self.handle_stream_end, ValueError(f"未知 API Provider: {provider}"), display_text, None, "未知API")
                    return
            else:
                self.app.after(0, self.handle_stream_end, ValueError(f"不支持的后端类型: {backend_type}"), display_text, None, "系统错误")
                return

            if thread:
                logging.info("[处理流程] 准备启动 %s 处理线程", provider)
                thread.start()
            else:
                self.app.after(0, self.handle_stream_end, RuntimeError("未能创建处理线程"), display_text, None, "系统错误")

            # 发送后清理临时附件
            self.cleanup_attachments()

        except Exception as e_start_thread:
            logging.error("启动消息处理线程时出错: %s", e_start_thread)
            self.app.after(0, self.handle_stream_end, e_start_thread, display_text, None, "系统错误")
            self.cleanup_attachments()

    def cleanup_attachments(self):
        """清理临时附件文件"""
        for att in self.temp_attachments:
            try:
                if os.path.exists(att['file_path']):
                    os.remove(att['file_path'])
                    logging.info("[清理附件] 已删除临时文件: %s", att['file_path'])
            except Exception as e:
                logging.error("[清理附件] 删除临时文件 %s 出错: %s", att['file_path'], e)
        self.temp_attachments = []
        logging.info("[清理附件] 已清理所有临时附件")

    def handle_stream_chunk(self, chunk):
        """处理流式响应的数据块，累积一定量后再更新UI以避免卡顿，检查并暂时隐藏Artifacts指令"""
        if not self.controller.is_streaming:
            logging.info("[主线程] 接收到流块，但 is_streaming 为 False，忽略")
            return False

        try:
            # 累积数据到缓冲区
            self.stream_buffer += chunk
            self.controller.accumulated_stream_text += chunk  # 仍然累积到总文本中，用于最终保存
            current_time = int(datetime.datetime.now().timestamp() * 1000)  # 当前时间戳（毫秒）

            # 检查是否包含Artifacts指令，如果包含则暂时不更新UI
            if "ARTIFACT::" in chunk:
                logging.info("[流块处理] 检测到Artifacts指令，暂时不更新UI，等待最终处理")
                return True

            # 检查是否需要清空缓冲区（基于大小或时间）
            if (len(self.stream_buffer) >= self.buffer_size_limit or 
                current_time - self.last_buffer_flush >= self.buffer_time_limit):
                # --- 修改点：在处理第一个块之前强行插入换行并移除思考中消息 ---
                if not self.has_displayed_streaming_content:  # 检查是否是第一次显示流式内容
                    removed_thinking = self.controller._remove_thinking_message()
                    logging.info("[流块处理] 是第一次显示流式内容 (移除了思考中: %s)。准备强行插入换行...", removed_thinking)
                    try:
                        if self.chat_display:
                            self.chat_display.configure(state="normal")
                            self.chat_display.insert("end", "AI:\n")  # 插入 AI 标题和换行
                            logging.info("[流块处理] 已强行插入 AI 标题和换行符")
                            self.has_displayed_streaming_content = True  # 标记已显示流式内容
                    except Exception as insert_err:
                        logging.error("[流块处理] 强行插入换行符时出错: %s", insert_err)

                # 清空缓冲区并更新UI
                if self.chat_display and self.stream_buffer:
                    self.chat_display.configure(state="normal")
                    self.chat_display.insert("end", self.stream_buffer)
                    self.chat_display.see("end")  # 确保滚动到底部
                    self.chat_display.configure(state="disabled")  # 插入后禁用
                    logging.info("[性能优化] 缓冲区已更新UI (累积长度: %d)，当前总累积长度: %d", len(self.stream_buffer), len(self.controller.accumulated_stream_text))
                    self.stream_buffer = ""  # 清空缓冲区
                    self.last_buffer_flush = current_time  # 更新上次清空时间
            else:
                logging.info("[性能优化] 缓冲区未达到更新条件 (当前长度: %d)，继续累积", len(self.stream_buffer))

        except Exception as e:
            logging.error("[主线程] 处理流块时出错: %s", e)
            if self.chat_display:
                try:
                    self.chat_display.configure(state="disabled")  # 出错时确保禁用
                except:
                    pass
        return True

    def process_chunk_queue(self):
        """处理文本块队列，分批更新UI"""
        if not self.chunk_queue or not self.controller.is_streaming:
            self.is_processing_queue = False
            logging.info("[性能优化] 队列为空或流式传输已停止，结束队列处理")
            return

        self.is_processing_queue = True
        chunk = self.chunk_queue.pop(0)  # 取出第一个块

        try:
            if self.chat_display:
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", chunk)
                self.chat_display.see("end")  # 确保滚动到底部
                self.chat_display.configure(state="disabled")  # 插入后禁用
                logging.info("[性能优化] 从队列插入文本块 (长度: %d)，剩余队列长度: %d", len(chunk), len(self.chunk_queue))
        except Exception as e:
            logging.error("[性能优化] 从队列插入文本块时出错: %s", e)
            if self.chat_display:
                try:
                    self.chat_display.configure(state="disabled")  # 出错时确保禁用
                except:
                    pass

        # 安排下一个块的处理，延迟20ms以避免UI卡顿（从10ms增加到20ms）
        if self.chunk_queue:
            self.app.after(20, self.process_chunk_queue)
        else:
            self.is_processing_queue = False
            logging.info("[性能优化] 队列处理完成")

    def handle_stream_end(self, error=None, user_input=None, full_response=None, backend_name="未知"):
        """流式传输结束后的处理，过滤Artifacts指令内容，并限制输出长度，避免重复显示"""
        logging.info("[主线程] 流结束处理开始 (来自 %s)", backend_name)
        logging.debug("[主线程 Debug] 原始 AI 响应: %s", full_response if full_response else self.controller.accumulated_stream_text)
        # --- 添加 print 语句以强制输出到终端 ---
        print("--- [强制调试] 流结束处理开始 (来自 %s)" % backend_name)
        print("--- [强制调试] 原始 AI 响应: %s" % (full_response if full_response else self.controller.accumulated_stream_text))
        # --- 结束 print 语句 ---
        self.controller.is_streaming = False
        final_response_to_save = self.controller.accumulated_stream_text if not error else None  # 使用累积文本
        logging.info("[主线程 Debug] 最终累积文本长度: %d, error: %s", len(self.controller.accumulated_stream_text), error)
        self.controller.accumulated_stream_text = ""  # 清空

        # 确保缓冲区内容被更新到UI，但只在非Artifacts模式下更新
        if self.stream_buffer and self.chat_display:
            if "ARTIFACT::" not in self.stream_buffer:
                try:
                    self.chat_display.configure(state="normal")
                    self.chat_display.insert("end", self.stream_buffer)
                    self.chat_display.see("end")
                    self.chat_display.configure(state="disabled")
                    logging.info("[性能优化] 流结束时更新剩余缓冲区内容 (长度: %d)", len(self.stream_buffer))
                except Exception as e:
                    logging.error("[性能优化] 更新剩余缓冲区内容时出错: %s", e)
            else:
                logging.info("[性能优化] 缓冲区包含Artifacts指令，不更新UI，等待最终处理")
            self.stream_buffer = ""  # 清空缓冲区

        # 确保队列处理停止
        self.chunk_queue.clear()
        self.is_processing_queue = False
        logging.info("[性能优化] 流结束，清除文本块队列并停止处理")

        if error:
            error_message = str(error)
            # 根据错误内容提供更友好的提示
            if "限流" in error_message or "Rate Limit" in error_message:
                display_message = f"抱歉，{backend_name} API 请求频率过高，已被限流。请稍后再试，或检查您的API配额。"
            elif "认证失败" in error_message or "Authentication" in error_message:
                display_message = f"抱歉，{backend_name} API 认证失败。请检查您的API密钥是否正确。"
            elif "连接错误" in error_message or "Connection" in error_message:
                display_message = f"抱歉，无法连接到 {backend_name} API 服务器。请检查网络连接或API密钥是否有效。"
            elif "用户取消" in error_message:
                display_message = "流式传输已由用户取消。"
            else:
                display_message = f"抱歉，处理时遇到错误：\n{error_message}"
            logging.error("[主线程] 流结束 (错误): %s", error_message)
            # 直接使用 display_message 显示错误
            self.controller.display_message("assistant", display_message)
        else:
            logging.info("[主线程] 流式响应处理完毕 (来自 %s)", backend_name)
            # 确保末尾有足够换行
            if self.chat_display:
                try:
                    self.chat_display.configure(state="normal")
                    if not self.chat_display.get("end-2c", "end") == "\n\n":
                        if not self.chat_display.get("end-1c", "end") == "\n":
                            self.chat_display.insert("end", "\n")  # 添加一个换行
                        self.chat_display.insert("end", "\n")  # 再添加一个换行
                    self.chat_display.configure(state="disabled")
                except Exception as e:
                    logging.error("[主线程] 添加末尾换行时出错: %s", e)

            # 新增：检查输出长度是否过长，限制显示内容
            max_display_length = 5000  # 最大显示字符数
            if final_response_to_save and len(final_response_to_save) > max_display_length:
                logging.info("[性能优化] 输出内容过长 (%d 字符)，截断显示并保存完整内容到临时文件", len(final_response_to_save))
                # 截断显示内容
                truncated_response = final_response_to_save[:max_display_length] + "\n\n[内容过长，已截断。完整内容已保存到临时文件，请查看。]"
                # 保存完整内容到临时文件
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"full_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                try:
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(final_response_to_save)
                    logging.info("[性能优化] 完整内容已保存到临时文件: %s", temp_file)
                    truncated_response += f"\n完整内容路径：{temp_file}"
                except Exception as e:
                    logging.error("[性能优化] 保存完整内容到临时文件出错: %s", e)
                    truncated_response += f"\n保存完整内容失败，无法提供路径。"
                final_response_to_display = truncated_response
            else:
                final_response_to_display = final_response_to_save

            # 新增：检查是否为Artifacts模式，并处理特定格式内容
            if self.controller.chat_manager.is_artifacts_mode_enabled():
                if final_response_to_save:  # 处理文本、图表、表格、HTML
                    import re
                    # 查找ARTIFACT::CHART格式
                    chart_pattern = r"ARTIFACT::CHART::\{(.+?)\}::END_ARTIFACT"
                    chart_match = re.search(chart_pattern, final_response_to_save, re.DOTALL)
                    if chart_match:
                        chart_data_str = "{" + chart_match.group(1) + "}"
                        logging.info("[Artifacts] 检测到图表指令，数据: %s...", chart_data_str[:100])
                        # 移除聊天区中的指令部分
                        instruction_start = final_response_to_save.find("ARTIFACT::CHART::")
                        instruction_end = final_response_to_save.find("::END_ARTIFACT") + len("::END_ARTIFACT")
                        if instruction_start >= 0 and instruction_end > instruction_start:
                            filtered_response = final_response_to_save[:instruction_start] + final_response_to_save[instruction_end:]
                            # 修改：不清除聊天记录，直接追加提示信息
                            if not self.has_displayed_streaming_content or not filtered_response.strip():
                                self.controller.display_message("assistant", filtered_response.strip() if filtered_response.strip() else "已生成图表，请查看浏览器。")
                            else:
                                logging.info("[重复修复] 流式内容已显示，不重复显示过滤后的响应，只追加提示信息")
                                if not filtered_response.strip():
                                    self.controller.display_message("assistant", "已生成图表，请查看浏览器。")
                        self.controller.render_artifacts_chart(chart_data_str)
                    else:
                        # 查找ARTIFACT::TABLE格式
                        table_pattern = r"ARTIFACT::TABLE::\{(.+?)\}::END_ARTIFACT"
                        table_match = re.search(table_pattern, final_response_to_save, re.DOTALL)
                        if table_match:
                            table_data_str = "{" + table_match.group(1) + "}"
                            logging.info("[Artifacts] 检测到表格指令，数据: %s...", table_data_str[:100])
                            # 移除聊天区中的指令部分
                            instruction_start = final_response_to_save.find("ARTIFACT::TABLE::")
                            instruction_end = final_response_to_save.find("::END_ARTIFACT") + len("::END_ARTIFACT")
                            if instruction_start >= 0 and instruction_end > instruction_start:
                                filtered_response = final_response_to_save[:instruction_start] + final_response_to_save[instruction_end:]
                                # 修改：不清除聊天记录，直接追加提示信息
                                if not self.has_displayed_streaming_content or not filtered_response.strip():
                                    self.controller.display_message("assistant", filtered_response.strip() if filtered_response.strip() else "已生成表格，请查看浏览器。")
                                else:
                                    logging.info("[重复修复] 流式内容已显示，不重复显示过滤后的响应，只追加提示信息")
                                    if not filtered_response.strip():
                                        self.controller.display_message("assistant", "已生成表格，请查看浏览器。")
                            self.controller.render_artifacts_table(table_data_str)
                        else:
                            # 查找ARTIFACT::HTML_CONTENT格式
                            html_pattern = r"ARTIFACT::HTML_CONTENT::\{(.+?)\}::END_ARTIFACT"
                            html_match = re.search(html_pattern, final_response_to_save, re.DOTALL)
                            if html_match:
                                html_data_str = "{" + html_match.group(1) + "}"
                                logging.info("[Artifacts] 检测到网页内容指令，数据: %s...", html_data_str[:100])
                                instruction_start = final_response_to_save.find("ARTIFACT::HTML_CONTENT::")
                                instruction_end = final_response_to_save.find("::END_ARTIFACT") + len("::END_ARTIFACT")
                                if instruction_start >= 0 and instruction_end > instruction_start:
                                    filtered_response = final_response_to_save[:instruction_start] + final_response_to_save[instruction_end:]
                                    # 修改：不清除聊天记录，直接追加提示信息
                                    if not self.has_displayed_streaming_content or not filtered_response.strip():
                                        self.controller.display_message("assistant", filtered_response.strip() if filtered_response.strip() else "已生成网页内容，请查看浏览器。")
                                    else:
                                        logging.info("[重复修复] 流式内容已显示，不重复显示过滤后的响应，只追加提示信息")
                                        if not filtered_response.strip():
                                            self.controller.display_message("assistant", "已生成网页内容，请查看浏览器。")
                                self.controller.render_artifacts_html(html_data_str)
                            else:
                                # 如果不是图表、表格或网页内容指令，直接显示在Artifacts编辑区域
                                logging.info("[Artifacts] 未检测到图表、表格或网页内容指令，将内容显示在浏览器中")
                                self.controller.handle_artifacts_content(final_response_to_save)
                elif backend_name == "Grok" and self.controller.selected_backend_config.get('model') == "grok-2-image-latest":
                    # 处理图片路径 (full_response 在这种情况下是路径或错误信息)
                    if full_response and os.path.exists(full_response):  # 检查是否是有效路径
                        logging.info("[Artifacts] 检测到图片路径，准备渲染到浏览器: %s", full_response)
                        self.controller.render_artifacts_image(full_response)
                    elif full_response:  # 如果不是有效路径，可能是错误信息
                        logging.warning("[Artifacts] 收到非图片路径的响应: %s", full_response)
                        self.controller.handle_artifacts_content(f"图片生成失败或未返回有效路径:\n{full_response}")
                    else:  # 如果 full_response 为 None (可能下载失败)
                        logging.warning("[Artifacts] 图片生成后未收到有效路径或响应")
                        self.controller.handle_artifacts_content("图片生成成功，但未能获取图片路径。")
            else:
                # 非Artifacts模式，直接显示完整响应（可能已截断）
                if final_response_to_display and not self.has_displayed_streaming_content:
                    self.controller.display_message("assistant", final_response_to_display)
                else:
                    logging.info("[重复修复] 流式内容已显示，不重复显示完整响应")

            # 重置流式内容显示标志
            self.has_displayed_streaming_content = False

        if final_response_to_save:
            self.controller.save_chat_after_stream(final_response_to_save, user_input)  # 使用累积文本保存

        # UI 状态恢复
        if self.status_label:
            default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
            status_text = ""  # 初始为空，不显示对勾图标
            if error:
                status_text = f"错误 ({backend_name})"
                default_text_color = ("#FF0000", "#FF6666")
            self.status_label.configure(text=status_text, text_color=default_text_color)

        if self.input_entry:
            try:
                self.input_entry.configure(state="normal")
            except tk.TclError:
                logging.warning("尝试恢复输入框状态时出错 (可能窗口已关闭)")
            else:
                logging.info("[UI响应性] 输入框状态已恢复为可输入")

        # 隐藏取消按钮
        cancel_button = self.ui.get('cancel_button')
        if cancel_button:
            cancel_button.pack_forget()
            logging.info("[UI响应性] 隐藏取消按钮")

        logging.info("[主线程] 流结束处理完成 (来自 %s)", backend_name)

    def send_deepseek_message_thread(self, user_input, message_history):
        try:
            if not self.controller.is_streaming:
                logging.info("[DeepSeek 线程] 开始时 is_streaming 为 False，中止。")
                return

            logging.info("[DeepSeek 线程] 开始调用 API")
            def deepseek_chunk_callback(chunk):
                if not self.controller.is_streaming:
                    logging.info("[DeepSeek 回调] is_streaming 为 False，请求停止。")
                    return False
                # 回调返回 handle_stream_chunk 的结果 (通常是 True)
                return self.app.after(0, self.handle_stream_chunk, chunk)

            api_client.get_deepseek_response_stream(message_history, deepseek_chunk_callback)
            logging.info("[DeepSeek 线程] API 调用完成 (累积文本在主线程处理)")

            if self.controller.is_streaming:
                self.app.after(0, self.handle_stream_end, None, user_input, None, "DeepSeek")  # 传 None
            else:
                logging.info("[DeepSeek 线程] API 调用完成，但 is_streaming 已为 False，不调用 handle_stream_end")

        except ConnectionError as conn_err:
            logging.error("[DeepSeek 线程] API 连接错误: %s", conn_err)
            if self.controller.is_streaming: self.app.after(0, self.handle_stream_end, conn_err, user_input, None, "DeepSeek")
        except Exception as e:
            logging.error("[DeepSeek 线程] 发送消息线程出错: %s", e)
            if self.controller.is_streaming: self.app.after(0, self.handle_stream_end, e, user_input, None, "DeepSeek")

    def send_grok_message_thread(self, user_input, message_history, model):
        processed_history = message_history
        try:
            if not self.controller.is_streaming:
                logging.info("[Grok 线程] 开始时 is_streaming 为 False，中止。")
                return

            logging.info("[Grok 线程] 开始处理历史记录和可能的搜索")
            if self.chat_manager.is_search_mode_enabled():
                # ... (搜索逻辑保持不变) ...
                search_results_text = "搜索失败或未找到结果。"
                try:
                    logging.info("[搜索] [Grok 线程] 正在进行网络搜索: '%s...'", user_input[:50])
                    if not os.getenv("TAVILY_API_KEY"):
                        logging.warning("[搜索] [Grok 线程] 警告: 未找到 TAVILY_API_KEY，跳过网络搜索")
                        search_results_text = "由于缺少 TAVILY API Key，未执行网络搜索。"
                    else:
                        search_results = web_search.perform_search(user_input)
                        if search_results:
                            search_results_text = search_results
                            logging.info("[搜索] [Grok 线程] 成功获取搜索结果 (%d 字符)", len(search_results))
                        else:
                            logging.info("[搜索] [Grok 线程] 未找到相关搜索结果")
                            search_results_text = "未找到相关的网络搜索结果。"
                except Exception as search_err:
                    logging.error("[搜索] [Grok 线程] 网络搜索过程中出错: %s", search_err)
                    search_results_text = f"尝试进行网络搜索时出错: {search_err}."

                formatted_prompt = PROMPT_NETWORKING.format(search_results_placeholder=search_results_text)
                processed_history = [msg.copy() for msg in message_history]
                if processed_history:
                    found_system = False
                    for i, msg in enumerate(processed_history):
                        if msg.get("role") == "system":
                            logging.info("[搜索] [Grok 线程] 找到原始系统提示，内容: '%s...' 将联网提示追加到现有提示中。", msg.get('content', '')[:50])
                            processed_history[i]["content"] = processed_history[i]["content"] + "\n\n--- 分隔线 ---\n\n" + formatted_prompt
                            found_system = True
                            break
                    if not found_system:
                        logging.info("[搜索] [Grok 线程] 原始历史无系统提示，在开头插入联网搜索提示")
                        processed_history.insert(0, {"role": "system", "content": formatted_prompt})
                else:
                    logging.warning("[搜索] [Grok 线程] 警告：消息历史为空，无法替换/插入系统消息")
                    processed_history = [{"role": "system", "content": formatted_prompt}]
                # --- 结束搜索逻辑 ---

            logging.info("[Grok 线程] 准备调用 Grok API (模型: %s)", model)
            def grok_chunk_callback(chunk):
                if not self.controller.is_streaming:
                    logging.info("[Grok 回调] is_streaming 为 False，请求停止。")
                    return False
                # 回调返回 handle_stream_chunk 的结果
                return self.app.after(0, self.handle_stream_chunk, chunk)

            grok_client.get_grok_response_stream(processed_history, grok_chunk_callback, model=model)
            logging.info("[Grok 线程] API 调用完成 (累积文本在主线程处理)")

            if self.controller.is_streaming:
                self.app.after(0, self.handle_stream_end, None, user_input, None, "Grok")  # 传 None
            else:
                logging.info("[Grok 线程] API 调用完成，但 is_streaming 已为 False，不调用 handle_stream_end")

        except ConnectionError as conn_err:
            logging.error("[Grok 线程] API 连接错误: %s", conn_err)
            if self.controller.is_streaming: self.app.after(0, self.handle_stream_end, conn_err, user_input, None, "Grok")
        except Exception as e:
            logging.error("[Grok 线程] 发送消息线程出错: %s", e)
            if self.controller.is_streaming: self.app.after(0, self.handle_stream_end, e, user_input, None, "Grok")
