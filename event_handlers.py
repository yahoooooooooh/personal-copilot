# event_handlers.py (v3.46 - 修正 SettingsWindow 调用参数)
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import os
import sys
from pathlib import Path
import webbrowser
import requests
import tempfile
import datetime
from PIL import Image, ImageTk
import json
import logging
import urllib.parse

# 导入其他需要的模块 (从项目中)
import api_client
import grok_client
import web_search
from ui_components import SettingsWindow
from ui_formatter import apply_simple_formatting
from ui_builder import get_theme_colors
from message_handler import MessageHandler
from image_handler import ImageHandler
from prompts import PROMPT_DEFAULT

class AppController:
    def __init__(self, app_instance, ui_elements, chat_manager_instance, utils_functions, config):
        """
        初始化 Controller。
        参数:
            app_instance: 主应用程序实例
            ui_elements: UI 元素字典
            chat_manager_instance: ChatManager 实例
            utils_functions: 工具函数字典
            config: 配置字典，包含 API Keys 和 backend_configs 等
        """
        self.app = app_instance
        self.ui = ui_elements
        self.chat_manager = chat_manager_instance
        self.utils = utils_functions
        self.config = config  # 包含 API Keys, backend_configs 等

        # --- 内部状态变量 ---
        self.is_streaming = False
        self.accumulated_stream_text = ""
        self.settings_window = None
        self.image_references = []  # 存储图像引用以防止垃圾回收
        self.current_image_label = None  # 存储当前显示的图像标签引用

        # --- 获取后端配置列表 ---
        self.backend_configs = config.get('backend_configs', [])  # 只包含 API

        # --- 确定并存储初始后端配置 ---
        initial_backend_display_name = config.get('initial_backend_display_name', None)
        self.selected_backend_config = None
        if initial_backend_display_name and initial_backend_display_name != "无可用 API 配置":
            for cfg in self.backend_configs:
                if cfg['display_name'] == initial_backend_display_name:
                    self.selected_backend_config = cfg
                    break
        # 如果找不到或未指定，选第一个可用的 API
        if not self.selected_backend_config and self.backend_configs:
            for cfg in self.backend_configs:
                if cfg.get('type') == 'API':  # 确保是 API 类型
                    self.selected_backend_config = cfg
                    logging.warning("未找到初始 API 后端 '%s' 或未提供，使用默认 API: %s", initial_backend_display_name, self.selected_backend_config['display_name'])
                    break
        elif not self.backend_configs or not self.selected_backend_config:
            logging.error("未提供任何有效 API 后端配置!")
            self.selected_backend_config = {"display_name": "无可用 API 配置", "type": "Error", "provider": "None", "model": ""}  # 错误状态

        # --- 获取 UI 控件的引用 ---
        self.setup_ui_references()

        # --- 设置初始模式状态 ---
        self.initialize_mode_states()

        # --- 初始化模型选择器 ---
        self.initialize_model_selector()

        # --- 初始化新拆分的处理器 ---
        self.message_handler = MessageHandler(self, self.chat_manager, self.app, self.ui)
        self.image_handler = ImageHandler(self, self.app, self.ui)

        # --- 绑定取消按钮和置顶按钮 ---
        self.bind_control_buttons()

        # --- 初始化按钮状态外观 ---
        self.update_button_appearance()

    def setup_ui_references(self):
        """设置 UI 控件的引用"""
        self.status_label = self.ui.get('status_label')
        self.chat_display = self.ui.get('chat_display')  # 使用固定的 Textbox
        self.input_entry = self.ui.get('input_entry')
        self.search_button = self.ui.get('search_button')
        self.search_var = self.ui.get('search_var')
        self.atri_button = self.ui.get('atri_button')
        self.atri_var = self.ui.get('atri_var')
        self.artifacts_button = self.ui.get('artifacts_button')  # 新增
        self.artifacts_var = self.ui.get('artifacts_var')  # 新增
        self.translate_button = self.ui.get('translate_button')  # 新增翻译按钮
        self.translate_var = self.ui.get('translate_var')  # 新增翻译变量
        self.model_optionmenu = self.ui.get('model_optionmenu')  # 新增模型选择器
        self.model_optionmenu_var = self.ui.get('model_optionmenu_var')  # 新增模型选择器变量
        self.cancel_button = self.ui.get('cancel_button')  # 新增取消按钮
        # 新增置顶按钮引用
        self.topmost_button = self.ui.get('topmost_button')
        self.topmost_var = self.ui.get('topmost_var')

    def initialize_mode_states(self):
        """设置初始模式状态"""
        self.search_var.set(1 if self.chat_manager.is_search_mode_enabled() else 0)
        self.atri_var.set(1 if self.chat_manager.is_atri_mode_enabled() else 0)
        self.artifacts_var.set(1 if self.chat_manager.is_artifacts_mode_enabled() else 0)
        self.translate_var.set(1 if self.chat_manager.is_translate_mode_enabled() else 0)
        # 初始置顶状态
        if self.topmost_var:
            self.app.attributes('-topmost', bool(self.topmost_var.get()))
            logging.info("[置顶] 初始置顶状态: %s", '启用' if bool(self.topmost_var.get()) else '禁用')

    def bind_control_buttons(self):
        """绑定控制按钮的事件"""
        if self.cancel_button:
            self.cancel_button.configure(command=self.cancel_streaming)
        if self.topmost_button:
            self.topmost_button.configure(command=self.toggle_topmost_mode)
            logging.info("[置顶] 置顶按钮已绑定")

    def initialize_model_selector(self):
        """初始化模型选择器，填充可用模型选项"""
        model_names = [cfg['display_name'] for cfg in self.backend_configs]
        if model_names:
            self.model_optionmenu.configure(values=model_names)
            # 设置初始值为当前选中的模型
            if self.selected_backend_config and self.selected_backend_config.get('display_name') in model_names:
                self.model_optionmenu_var.set(self.selected_backend_config['display_name'])
            else:
                self.model_optionmenu_var.set(model_names[0])
            # 绑定选择事件
            self.model_optionmenu.configure(command=self.on_model_select)
        else:
            self.model_optionmenu.configure(values=["无可用模型"])
            self.model_optionmenu_var.set("无可用模型")
        logging.info("[模型选择器] 初始化完成，可用模型: %s", model_names)

    def on_model_select(self, selected_model_name):
        """模型选择器回调函数，切换模型"""
        logging.info("[模型选择] 用户选择了模型: %s", selected_model_name)
        self.switch_backend(selected_model_name)

    # --- 打开设置窗口 ---
    def open_settings_window(self):
        """打开设置窗口"""
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            logging.info("设置窗口已打开，重新聚焦")
            return

        logging.info("打开设置窗口")
        self.settings_window = SettingsWindow(
            master=self.app,
            selected_config=self.selected_backend_config,
            all_backend_configs=self.backend_configs,
            chat_manager_ref=self.chat_manager,
            switch_backend_func=self.switch_backend,
            create_new_chat_func=self.handle_create_new_chat,
            ensure_prompt_func=lambda: None  # 提供一个空函数作为占位符
        )
        # 新增：传递中转模型相关设置
        if hasattr(self.image_handler, 'use_intermediate_model'):
            self.settings_window.set_intermediate_model_usage(self.image_handler.use_intermediate_model)
        if hasattr(self.image_handler, 'intermediate_model'):
            self.settings_window.set_intermediate_model(self.image_handler.intermediate_model)
        self.settings_window.grab_set()

    # --- 新增函数：更新所有按钮的外观 ---
    def update_button_appearance(self):
        """根据当前模式状态更新所有按钮的外观"""
        current_mode = ctk.get_appearance_mode().lower()
        colors = get_theme_colors(current_mode)

        # 更新搜索按钮
        search_enabled = bool(self.search_var.get())
        self.search_button.configure(fg_color=colors["button_active"] if search_enabled else colors["button_inactive"])
        logging.info("[调试] 更新搜索按钮颜色: %s, fg_color=%s", '激活' if search_enabled else '非激活', colors["button_active"] if search_enabled else colors["button_inactive"])

        # 更新ATRI按钮
        atri_enabled = bool(self.atri_var.get())
        self.atri_button.configure(fg_color=colors["button_active"] if atri_enabled else colors["button_inactive"])
        logging.info("[调试] 更新ATRI按钮颜色: %s, fg_color=%s", '激活' if atri_enabled else '非激活', colors["button_active"] if atri_enabled else colors["button_inactive"])

        # 更新Artifacts按钮
        artifacts_enabled = bool(self.artifacts_var.get())
        self.artifacts_button.configure(fg_color=colors["button_active"] if artifacts_enabled else colors["button_inactive"])
        logging.info("[调试] 更新Artifacts按钮颜色: %s, fg_color=%s", '激活' if artifacts_enabled else '非激活', colors["button_active"] if artifacts_enabled else colors["button_inactive"])

        # 更新翻译按钮
        translate_enabled = bool(self.translate_var.get())
        self.translate_button.configure(fg_color=colors["button_active"] if translate_enabled else colors["button_inactive"])
        logging.info("[调试] 更新翻译按钮颜色: %s, fg_color=%s", '激活' if translate_enabled else '非激活', colors["button_active"] if translate_enabled else colors["button_inactive"])

        # 更新置顶按钮
        if self.topmost_var:
            topmost_enabled = bool(self.topmost_var.get())
            self.topmost_button.configure(fg_color=colors["button_active"] if topmost_enabled else colors["button_inactive"])
            logging.info("[调试] 更新置顶按钮颜色: %s, fg_color=%s", '激活' if topmost_enabled else '非激活', colors["button_active"] if topmost_enabled else colors["button_inactive"])

    # --- 搜索和ATRI模式切换函数 (更新按钮外观) ---
    def toggle_search_mode(self):
        """切换搜索模式状态"""
        if self.search_var:
            is_enabled = bool(self.search_var.get())
            self.chat_manager.set_search_mode(is_enabled)
            # 更新按钮外观
            current_mode = ctk.get_appearance_mode().lower()
            colors = get_theme_colors(current_mode)
            self.search_button.configure(fg_color=colors["button_active"] if is_enabled else colors["button_inactive"])
            logging.info("[调试] 搜索模式切换: %s, fg_color=%s", '启用' if is_enabled else '禁用', colors["button_active"] if is_enabled else colors["button_inactive"])

    def toggle_atri_mode(self):
        """切换ATRI模式状态"""
        if self.atri_var:
            is_enabled = bool(self.atri_var.get())
            self.chat_manager.set_atri_mode(is_enabled)
            # 更新按钮外观
            current_mode = ctk.get_appearance_mode().lower()
            colors = get_theme_colors(current_mode)
            self.atri_button.configure(fg_color=colors["button_active"] if is_enabled else colors["button_inactive"])
            logging.info("[调试] ATRI模式切换: %s, fg_color=%s", '启用' if is_enabled else '禁用', colors["button_active"] if is_enabled else colors["button_inactive"])

    # --- 新增Artifacts模式切换函数 (动态显示/隐藏Artifacts区域并调整列权重，更新按钮外观) ---
    def toggle_artifacts_mode(self):
        """切换Artifacts模式状态"""
        if self.artifacts_var:
            is_enabled = bool(self.artifacts_var.get())
            self.chat_manager.set_artifacts_mode(is_enabled)
            # 更新按钮外观
            current_mode = ctk.get_appearance_mode().lower()
            colors = get_theme_colors(current_mode)
            self.artifacts_button.configure(fg_color=colors["button_active"] if is_enabled else colors["button_inactive"])
            logging.info("[调试] Artifacts模式切换: %s, fg_color=%s", '启用' if is_enabled else '禁用', colors["button_active"] if is_enabled else colors["button_inactive"])
            logging.info("Artifacts模式已%s", '启用' if is_enabled else '禁用')

    # --- 新增置顶模式切换函数 ---
    def toggle_topmost_mode(self):
        """切换窗口置顶状态"""
        if self.topmost_var:
            is_enabled = bool(self.topmost_var.get())
            self.topmost_var.set(1 if is_enabled == 0 else 0)
            is_enabled = bool(self.topmost_var.get())
            self.app.attributes('-topmost', is_enabled)
            # 更新按钮外观
            current_mode = ctk.get_appearance_mode().lower()
            colors = get_theme_colors(current_mode)
            self.topmost_button.configure(fg_color=colors["button_active"] if is_enabled else colors["button_inactive"])
            logging.info("[置顶] 置顶模式切换: %s, fg_color=%s", '启用' if is_enabled else '禁用', colors["button_active"] if is_enabled else colors["button_inactive"])

    # --- 新增翻译模式切换函数 ---
    def toggle_translate_mode(self):
        """切换翻译模式状态"""
        if self.translate_var:
            is_enabled = bool(self.translate_var.get())
            self.chat_manager.set_translate_mode(is_enabled)
            # 更新按钮外观
            current_mode = ctk.get_appearance_mode().lower()
            colors = get_theme_colors(current_mode)
            self.translate_button.configure(fg_color=colors["button_active"] if is_enabled else colors["button_inactive"])
            logging.info("[调试] 翻译模式切换: %s, fg_color=%s", '启用' if is_enabled else '禁用', colors["button_active"] if is_enabled else colors["button_inactive"])

    # --- Backend Switching ---
    def switch_backend(self, choice_display_name):
        logging.info("请求切换后端至: %s", choice_display_name)
        new_config = None
        for cfg in self.backend_configs:  # 只会遍历 API 配置
            if cfg['display_name'] == choice_display_name:
                new_config = cfg
                break

        if not new_config:
            logging.error("无法找到与 '%s' 匹配的 API 后端配置", choice_display_name)
            if self.status_label: self.status_label.configure(text=f"错误", text_color=("red", "red"))
            return

        if self.is_streaming:
            logging.warning("正在切换后端，将中断当前流式响应")
            self.is_streaming = False
            self.app.after(0, self.message_handler.handle_stream_end, InterruptedError("用户切换后端"), None, None, "系统")

        if self.status_label:
            default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
            self.status_label.configure(text=f"切换中...", text_color=default_text_color)

        try:
            backend_type = new_config['type']  # 必然是 'API' 或 'Error'
            provider = new_config['provider']

            if backend_type == "API":
                logging.info("准备切换到在线 API: %s", choice_display_name)
                if self.status_label: self.status_label.configure(text=f"初始化中...", text_color=default_text_color)
                success = False

                if provider == "DeepSeek":
                    api_key = self.config.get('DEEPSEEK_API_KEY')
                    success = bool(api_client.initialize_api_client(api_key))
                elif provider == "Grok":
                    success = bool(grok_client.initialize_grok_client())
                else:
                    logging.error("未知的 API Provider: %s", provider)
                    if self.status_label: self.status_label.configure(text=f"错误 ({provider})", text_color=("red", "red"))

                if success:
                    logging.info("成功切换到 %s API (模型: %s)", provider, new_config.get('model', '默认'))
                    self.selected_backend_config = new_config  # 更新配置
                    if self.status_label: self.status_label.configure(text=f"", text_color=default_text_color)  # 成功后清空状态
                    # 更新模型选择器显示
                    if self.model_optionmenu_var:
                        self.model_optionmenu_var.set(choice_display_name)
                else:
                    logging.error("%s API 初始化失败", provider)
                    if self.status_label: self.status_label.configure(text=f"错误 ({provider})", text_color=("red", "red"))

            elif backend_type == "Error":
                logging.error("无法切换到错误状态的后端: %s", choice_display_name)
                if self.status_label: self.status_label.configure(text=f"错误", text_color=("red", "red"))
            else:  # 不应该执行到这里
                logging.error("未知的后端类型: %s", backend_type)
                if self.status_label: self.status_label.configure(text=f"错误 ({backend_type})", text_color=("red", "red"))

        except Exception as e:
            logging.error("切换后端时发生错误: %s", e)
            if self.status_label: self.status_label.configure(text=f"错误", text_color=("red", "red"))

    # --- 核心消息处理逻辑 (调用 message_handler) ---
    def handle_send_message(self, event=None):
        """处理发送消息的事件，调用 message_handler"""
        # 显示取消按钮
        if self.cancel_button:
            self.cancel_button.pack(side="right", padx=(5, 5))
            logging.info("[UI响应性] 显示取消按钮")
        return self.message_handler.handle_send_message(event)

    def cancel_streaming(self):
        """处理取消流式传输的操作"""
        if self.is_streaming:
            logging.info("[用户操作] 用户点击取消按钮，中断流式传输")
            self.is_streaming = False
            # 调用 handle_stream_end，传递一个自定义错误
            self.app.after(0, self.message_handler.handle_stream_end, InterruptedError("用户取消了流式传输"), None, None, "系统")
            # 隐藏取消按钮
            if self.cancel_button:
                self.cancel_button.pack_forget()
            # 更新状态标签
            if self.status_label:
                default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
                self.status_label.configure(text="已取消", text_color=default_text_color)
        else:
            logging.warning("[警告] 用户点击取消按钮，但当前未在流式传输中")

    # --- display_message (调整为使用固定 chat_display) ---
    def display_message(self, role, content):
        """显示消息在聊天框，使用固定 chat_display"""
        try:
            if not self.chat_display:
                logging.error("[错误] chat_display 未初始化，无法显示消息")
                return

            self.chat_display.configure(state="normal")
            if role == "user":
                # 用户消息格式不变
                self.chat_display.insert("end", "你: \n", "user")
                self.chat_display.insert("end", content + "\n\n")
            elif role == "assistant":
                # AI 消息格式
                self.chat_display.insert("end", "AI: \n", "assistant")
                self.chat_display.insert("end", content + "\n\n")
            elif role == "thinking":  # 处理 "思考中..."
                self.chat_display.insert("end", "AI: ", "assistant")  # 插入 "AI:" 标题
                self.chat_display.insert("end", "思考中...\n\n")  # 插入思考文本和间隔
            else:  # "system"
                # 系统消息格式不变
                self.chat_display.insert("end", f"[{role.upper()}]: \n{content}\n\n", "system")

            self.chat_display.see("end")  # 自动滚动到底部
        finally:
            # 确保最后禁用文本框
            try:
                self.chat_display.configure(state="disabled")
            except tk.TclError:
                pass  # 忽略 TclError
            except Exception as e:
                logging.error("设置 chat_display 为 disabled 时出错: %s", e)

    # --- display_full_history (调整为使用固定 chat_display) ---
    def display_full_history(self):
        """显示完整的聊天历史"""
        if not self.chat_display:
            logging.error("[错误] chat_display 未初始化，无法显示历史")
            return

        # 清除之前的图像控件
        if self.current_image_label:
            self.current_image_label.destroy()
            self.current_image_label = None
            self.image_references.clear()
            logging.info("[新建对话] 已清除之前的图像控件")

        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        history = self.chat_manager.get_current_history()
        logging.info("[显示历史] 共 %d 条消息", len(history))
        for msg in history:
            if msg['role'] != 'system':  # 系统消息不显示在UI中
                self.display_message(msg['role'], msg['content'])
        self.chat_display.configure(state="disabled")

    # --- save_chat_after_stream ---
    def save_chat_after_stream(self, ai_response, user_input):
        """流结束后保存聊天记录"""
        if ai_response:
            logging.info("[保存] AI 响应已添加到历史 (长度: %d)", len(ai_response))
            self.chat_manager.add_message_to_current_chat("assistant", ai_response)
        elif user_input:
            logging.info("[保存] AI 响应为空，未添加到历史 (用户输入: '%s...')", user_input[:30] if user_input else "")

    # --- handle_create_new_chat ---
    def handle_create_new_chat(self):
        """处理新建对话的事件"""
        if self.is_streaming:
            messagebox.showwarning("操作冲突", "正在处理消息，请等待完成后再新建对话。")
            return
        logging.info("用户请求新对话")
        if self.chat_manager.create_new_chat():
            self.display_full_history()
            logging.info("成功创建新对话")
        else:
            logging.error("创建新对话失败")
            messagebox.showerror("错误", "创建新对话失败。")

    # --- display_thinking_message (修改版) ---
    def display_thinking_message(self):
        """显示"思考中..."消息，只显示标题"""
        self.display_message("thinking", "")  # thinking role 会处理

    # --- _remove_thinking_message (改进版，增强鲁棒性) ---
    def _remove_thinking_message(self):
        """移除"思考中..."消息 (包括标题)"""
        logging.info("[内部] _remove_thinking_message 调用")
        try:
            if not self.chat_display:
                logging.error("[错误] chat_display 未初始化，无法移除思考中消息")
                return False

            full_text = self.chat_display.get("1.0", "end-1c").strip()
            if not full_text:
                logging.info("[内部 Debug] 聊天内容为空，无需移除")
                return False

            # 尝试检查最后几行是否包含 "AI:" 和 "思考中"
            last_lines = self.chat_display.get("end-3l", "end-1c").strip() if self.chat_display.get("1.0", "end-1c").strip() else ""
            if last_lines and "AI:" in last_lines and "思考中" in last_lines:
                logging.info("[内部 Debug] 匹配成功，尝试移除最后几行")
                self.chat_display.configure(state="normal")
                self.chat_display.delete("end-3l", "end")
                self.chat_display.configure(state="disabled")
                logging.info("[内部 Debug] 最后几行已移除 (宽松匹配)")
                return True
            else:
                logging.warning("[内部 Debug 警告] 未找到包含 'AI:' 和 '思考中' 的内容")
                return False
        except Exception as e:
            logging.error("移除 'AI: 思考中...' 消息时出错: %s", e)
            try:
                self.chat_display.configure(state="disabled")
            except:
                pass
            return False

    # --- 新增处理Artifacts内容函数 ---
    def handle_artifacts_content(self, content):
        """将AI生成的纯文本内容保存为HTML文件并在浏览器中打开"""
        try:
            # 生成包含纯文本的HTML文件，使用<pre>标签保留格式
            html_content = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Artifacts 内容</title>
            </head>
            <body>
                <h1>Artifacts 内容</h1>
                <pre>{content}</pre>
            </body>
            </html>
            """
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"artifacts_text_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info("[Artifacts] 纯文本内容已保存到临时文件: %s", temp_file)
            
            # --- 修改后的打开逻辑 ---
            success = False
            logging.info("[Artifacts] 尝试自动打开文件: %s", temp_file)
            print("--- [强制调试] 尝试自动打开文件: %s" % temp_file)

            # 方法1 (Windows 优先): 使用 os.startfile()
            if sys.platform.startswith('win'):
                try:
                    os.startfile(temp_file)
                    logging.info("[Artifacts] 文件已通过 os.startfile() 打开")
                    print("--- [强制调试] 文件已通过 os.startfile() 打开")
                    self.display_message("assistant", f"已生成内容，并在默认应用中打开。")
                    success = True
                except Exception as os_err:
                    logging.error("[Artifacts] 使用 os.startfile 打开文件时出错: %s", os_err)
                    print("--- [强制调试] 使用 os.startfile 打开文件时出错: %s" % os_err)

            # 方法2 (Windows 次选): 使用 subprocess Popen start
            # 注意：Popen会立即返回，不会等待进程结束
            if not success and sys.platform.startswith('win'):
                try:
                    import subprocess
                    subprocess.Popen(['start', '', temp_file], shell=True)
                    logging.info("[Artifacts] 文件已通过 subprocess Popen start 打开")
                    print("--- [强制调试] 文件已通过 subprocess Popen start 打开")
                    self.display_message("assistant", f"已生成内容，并在默认应用中打开。")
                    success = True
                except Exception as sub_err:
                    logging.error("[Artifacts] 使用 subprocess Popen start 打开文件时出错: %s", sub_err)
                    print("--- [强制调试] 使用 subprocess Popen start 打开文件时出错: %s" % sub_err)

            # 方法3 (备选/跨平台): 使用 webbrowser.open()
            # 放在最后，因为在当前系统上行为异常
            if not success:
                try:
                    file_url = Path(temp_file).as_uri()
                    webbrowser.open(file_url)
                    logging.info("[Artifacts] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    print("--- [强制调试] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    # 即使可能被重定向，也告知用户尝试了
                    self.display_message("assistant", f"已生成内容，尝试在默认浏览器中打开。")
                    success = True # 标记为尝试过
                except Exception as wb_err:
                    logging.error("[Artifacts] 使用 webbrowser 打开文件时出错: %s", wb_err)
                    print("--- [强制调试] 使用 webbrowser 打开文件时出错: %s" % wb_err)

            # 如果所有方法都失败，显示文件路径供手动打开
            if not success:
                logging.info("[Artifacts] 所有自动打开方法均失败，直接显示文件路径: %s", temp_file)
                print("--- [强制调试] 所有自动打开方法均失败，直接显示文件路径: %s" % temp_file)
                self.display_message("assistant", f"已生成内容，但自动打开浏览器/应用失败。请手动打开以下文件查看：\n{temp_file}")
            # --- 结束修改后的打开逻辑 ---
        except Exception as e:
            logging.error("[Artifacts] 处理纯文本内容时出错: %s", e)
            self.display_message("assistant", f"抱歉，处理内容时遇到错误：{e}")

    # --- 新增处理Artifacts图表渲染函数 (修改版) ---
    def render_artifacts_chart(self, chart_data):
        """将图表数据转换为HTML文件并在浏览器中渲染 (使用在线 Chart.js CDN)"""
        try:
            import json
            if isinstance(chart_data, str):
                # 提取JSON部分
                start_idx = chart_data.find("{")
                end_idx = chart_data.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    chart_data = chart_data[start_idx:end_idx+1]
                    try:
                        chart_data = json.loads(chart_data)
                    except json.JSONDecodeError as json_err:
                        logging.error("[Artifacts] 解析图表 JSON 数据时出错: %s", json_err)
                        logging.error("[Artifacts] 原始数据: %s", chart_data)
                        self.display_message("assistant", f"抱歉，解析图表数据时出错: {json_err}")
                        return # 解析失败则不继续
                else:
                    logging.error("[Artifacts] 无法从字符串中提取有效的JSON图表数据: %s", chart_data[:100])
                    self.display_message("assistant", "抱歉，无法从AI响应中提取有效的图表数据。")
                    return

            chart_type = chart_data.get("type", "bar")
            chart_title = chart_data.get("title", "图表")
            labels = chart_data.get("data", {}).get("labels", [])
            datasets = chart_data.get("data", {}).get("datasets", [])
            options = chart_data.get("options", {})
            xlabel = options.get("xlabel", "X轴")
            ylabel = options.get("ylabel", "Y轴")

            # 构建datasets的JavaScript代码 (确保标签是字符串)
            datasets_js = []
            for ds in datasets:
                label = str(ds.get("label", "数据集")).replace("'", "\\'") # 转义单引号
                values = ds.get("values", [])
                # 确保 labels 和 values 是有效的 JSON 格式列表
                datasets_js.append(f"{{ label: '{label}', data: {json.dumps(values)} }}")
            datasets_str = ", ".join(datasets_js)
            labels_str = json.dumps(labels) # 确保 labels 是有效的 JSON 数组字符串

            # 使用在线 Chart.js CDN 而不是本地文件
            chart_js_url = "https://cdn.jsdelivr.net/npm/chart.js"
            logging.info("[Artifacts] 使用在线 Chart.js CDN: %s", chart_js_url)
            print("--- [强制调试] 使用在线 Chart.js CDN: %s" % chart_js_url)

            # 生成包含Chart.js的HTML文件 (使用在线 CDN)
            html_content = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <title>{chart_title}</title>
                <!-- 使用在线 Chart.js CDN -->
                <script src="{chart_js_url}"></script>
                <style>
                    body {{ font-family: sans-serif; margin: 20px; }}
                    canvas {{ max-width: 100%; height: auto; border: 1px solid #ccc; margin-top: 10px; }}
                    #errorMessage {{ color: red; font-weight: bold; border: 1px solid red; padding: 10px; margin-bottom: 10px; display: none; }}
                </style>
            </head>
            <body>
                <h1>{chart_title}</h1>
                <!-- 用于显示错误的 Div -->
                <div id="errorMessage"></div>
                <canvas id="myChart"></canvas>
                <script>
                    // 使用 try-catch 块捕获错误
                    try {{
                        const ctx = document.getElementById('myChart').getContext('2d');
                        // 确保 labels 和 datasets 数据是有效的
                        const chartLabels = {labels_str};
                        const chartDatasets = [{datasets_str}];

                        console.log("Chart Labels:", chartLabels);
                        console.log("Chart Datasets:", chartDatasets);

                        if (!Array.isArray(chartLabels) || chartDatasets.some(ds => !Array.isArray(ds.data))) {{
                            throw new Error("图表数据格式无效 (标签或数据集数据不是数组)");
                        }}

                        const myChart = new Chart(ctx, {{
                            type: '{chart_type}',
                            data: {{
                                labels: chartLabels,
                                datasets: chartDatasets
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: true, // 可以尝试设为 false 看看效果
                                scales: {{
                                    x: {{
                                        title: {{ display: true, text: '{xlabel}' }}
                                    }},
                                    y: {{
                                        title: {{ display: true, text: '{ylabel}' }},
                                        beginAtZero: true // 通常 Y 轴从 0 开始
                                    }}
                                }},
                                plugins: {{
                                    title: {{ // 添加图表标题插件
                                        display: true,
                                        text: '{chart_title}'
                                    }}
                                }}
                            }}
                        }});
                        console.log("图表已成功创建");
                    }} catch (error) {{
                        // 如果发生错误，显示错误信息
                        console.error('图表渲染错误:', error);
                        const errorDiv = document.getElementById('errorMessage');
                        errorDiv.style.display = 'block'; // 显示错误区域
                        errorDiv.innerText = '图表渲染失败: ' + error.message + '\\n请检查控制台获取详细信息。';
                        // 可以在这里添加更多调试信息
                        errorDiv.innerText += '\\n\\n原始数据 (部分):\\nLabels: ' + JSON.stringify({labels_str}).substring(0, 200) + '...\\nDatasets: ' + JSON.stringify([{datasets_str}]).substring(0, 300) + '...';
                    }}
                </script>
            </body>
            </html>
            """
            temp_dir = tempfile.gettempdir()
            # 文件名中避免特殊字符
            safe_title = "".join(c if c.isalnum() else "_" for c in chart_title)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_file_name = f"artifacts_chart_{safe_title}_{timestamp}.html"
            temp_file = os.path.join(temp_dir, temp_file_name)

            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info("[Artifacts] 图表HTML页面已保存到临时文件: %s", temp_file)

            # --- 修改后的打开逻辑 ---
            success = False
            logging.info("[Artifacts] 尝试自动打开文件: %s", temp_file)
            print("--- [强制调试] 尝试自动打开文件: %s" % temp_file)

            # 方法1 (Windows 优先): 使用 os.startfile()
            if sys.platform.startswith('win'):
                try:
                    os.startfile(temp_file)
                    logging.info("[Artifacts] 文件已通过 os.startfile() 打开")
                    print("--- [强制调试] 文件已通过 os.startfile() 打开")
                    self.display_message("assistant", f"已生成图表，并在默认应用中打开。")
                    success = True
                except Exception as os_err:
                    logging.error("[Artifacts] 使用 os.startfile 打开文件时出错: %s", os_err)
                    print("--- [强制调试] 使用 os.startfile 打开文件时出错: %s" % os_err)

            # 方法2 (Windows 次选): 使用 subprocess Popen start
            # 注意：Popen会立即返回，不会等待进程结束
            if not success and sys.platform.startswith('win'):
                try:
                    import subprocess
                    subprocess.Popen(['start', '', temp_file], shell=True)
                    logging.info("[Artifacts] 文件已通过 subprocess Popen start 打开")
                    print("--- [强制调试] 文件已通过 subprocess Popen start 打开")
                    self.display_message("assistant", f"已生成图表，并在默认应用中打开。")
                    success = True
                except Exception as sub_err:
                    logging.error("[Artifacts] 使用 subprocess Popen start 打开文件时出错: %s", sub_err)
                    print("--- [强制调试] 使用 subprocess Popen start 打开文件时出错: %s" % sub_err)

            # 方法3 (备选/跨平台): 使用 webbrowser.open()
            # 放在最后，因为在当前系统上行为异常
            if not success:
                try:
                    file_url = Path(temp_file).as_uri()
                    webbrowser.open(file_url)
                    logging.info("[Artifacts] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    print("--- [强制调试] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    # 即使可能被重定向，也告知用户尝试了
                    self.display_message("assistant", f"已生成图表，尝试在默认浏览器中打开。")
                    success = True # 标记为尝试过
                except Exception as wb_err:
                    logging.error("[Artifacts] 使用 webbrowser 打开文件时出错: %s", wb_err)
                    print("--- [强制调试] 使用 webbrowser 打开文件时出错: %s" % wb_err)

            # 如果所有方法都失败，显示文件路径供手动打开
            if not success:
                logging.info("[Artifacts] 所有自动打开方法均失败，直接显示文件路径: %s", temp_file)
                print("--- [强制调试] 所有自动打开方法均失败，直接显示文件路径: %s" % temp_file)
                self.display_message("assistant", f"已生成图表，但自动打开浏览器/应用失败。请手动打开以下文件查看：\n{temp_file}")
            # --- 结束修改后的打开逻辑 ---

        except Exception as e:
            logging.exception("[Artifacts] 渲染图表时发生未预料的错误") # 使用 exception 记录完整回溯
            self.display_message("assistant", f"抱歉，渲染图表时遇到严重错误：{e}")

    # --- 新增处理Artifacts表格渲染函数 ---
    def render_artifacts_table(self, table_data):
        """将表格数据转换为HTML文件并在浏览器中渲染"""
        try:
            import json
            if isinstance(table_data, str):
                # 提取JSON部分，假设table_data是字符串格式
                start_idx = table_data.find("{")
                end_idx = table_data.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    table_data = table_data[start_idx:end_idx+1]
                    table_data = json.loads(table_data)
                else:
                    raise ValueError("无法从字符串中提取有效的JSON表格数据")
            
            table_title = table_data.get("title", "表格")
            headers = table_data.get("data", {}).get("headers", [])
            rows = table_data.get("data", {}).get("rows", [])
            
            # 构建表头HTML
            headers_html = "".join(f"<th>{header}</th>" for header in headers)
            headers_row = f"<tr>{headers_html}</tr>"
            
            # 构建数据行HTML
            rows_html = []
            for row in rows:
                cells_html = "".join(f"<td>{cell}</td>" for cell in row)
                rows_html.append(f"<tr>{cells_html}</tr>")
            rows_str = "\n".join(rows_html)
            
            # 生成包含表格的HTML文件
            html_content = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <title>{table_title}</title>
                <style>
                    table {{ border-collapse: collapse; width: 100%; max-width: 800px; margin: 20px 0; font-family: Arial, sans-serif; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                </style>
            </head>
            <body>
                <h1>{table_title}</h1>
                <table>
                    {headers_row}
                    {rows_str}
                </table>
            </body>
            </html>
            """
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"artifacts_table_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info("[Artifacts] 表格HTML页面已保存到临时文件: %s", temp_file)
            
            # --- 修改后的打开逻辑 ---
            success = False
            logging.info("[Artifacts] 尝试自动打开文件: %s", temp_file)
            print("--- [强制调试] 尝试自动打开文件: %s" % temp_file)

            # 方法1 (Windows 优先): 使用 os.startfile()
            if sys.platform.startswith('win'):
                try:
                    os.startfile(temp_file)
                    logging.info("[Artifacts] 文件已通过 os.startfile() 打开")
                    print("--- [强制调试] 文件已通过 os.startfile() 打开")
                    self.display_message("assistant", f"已生成表格，并在默认应用中打开。")
                    success = True
                except Exception as os_err:
                    logging.error("[Artifacts] 使用 os.startfile 打开文件时出错: %s", os_err)
                    print("--- [强制调试] 使用 os.startfile 打开文件时出错: %s" % os_err)

            # 方法2 (Windows 次选): 使用 subprocess Popen start
            # 注意：Popen会立即返回，不会等待进程结束
            if not success and sys.platform.startswith('win'):
                try:
                    import subprocess
                    subprocess.Popen(['start', '', temp_file], shell=True)
                    logging.info("[Artifacts] 文件已通过 subprocess Popen start 打开")
                    print("--- [强制调试] 文件已通过 subprocess Popen start 打开")
                    self.display_message("assistant", f"已生成表格，并在默认应用中打开。")
                    success = True
                except Exception as sub_err:
                    logging.error("[Artifacts] 使用 subprocess Popen start 打开文件时出错: %s", sub_err)
                    print("--- [强制调试] 使用 subprocess Popen start 打开文件时出错: %s" % sub_err)

            # 方法3 (备选/跨平台): 使用 webbrowser.open()
            # 放在最后，因为在当前系统上行为异常
            if not success:
                try:
                    file_url = Path(temp_file).as_uri()
                    webbrowser.open(file_url)
                    logging.info("[Artifacts] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    print("--- [强制调试] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    # 即使可能被重定向，也告知用户尝试了
                    self.display_message("assistant", f"已生成表格，尝试在默认浏览器中打开。")
                    success = True # 标记为尝试过
                except Exception as wb_err:
                    logging.error("[Artifacts] 使用 webbrowser 打开文件时出错: %s", wb_err)
                    print("--- [强制调试] 使用 webbrowser 打开文件时出错: %s" % wb_err)

            # 如果所有方法都失败，显示文件路径供手动打开
            if not success:
                logging.info("[Artifacts] 所有自动打开方法均失败，直接显示文件路径: %s", temp_file)
                print("--- [强制调试] 所有自动打开方法均失败，直接显示文件路径: %s" % temp_file)
                self.display_message("assistant", f"已生成表格，但自动打开浏览器/应用失败。请手动打开以下文件查看：\n{temp_file}")
            # --- 结束修改后的打开逻辑 ---
        except Exception as e:
            logging.error("[Artifacts] 渲染表格时出错: %s", e)
            self.display_message("assistant", f"抱歉，渲染表格时遇到错误：{e}")

    # --- 新增渲染网页内容函数 ---
    def render_artifacts_html(self, html_data):
        """将HTML内容保存为临时文件并在浏览器中打开"""
        try:
            import json
            if isinstance(html_data, str):
                # 提取JSON部分，假设html_data是字符串格式
                start_idx = html_data.find("{")
                end_idx = html_data.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    html_data = html_data[start_idx:end_idx+1]
                    html_data = json.loads(html_data)
                else:
                    raise ValueError("无法从字符串中提取有效的JSON HTML数据")
            
            html_content = html_data.get("html", "<h1>错误</h1><p>无网页内容</p>")

            logging.info("[Artifacts] 开始处理HTML内容，内容长度: %d", len(html_content))
            
            # 保存HTML内容到临时文件
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"artifacts_html_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info("[Artifacts] HTML内容已保存到临时文件: %s", temp_file)
            
            # --- 修改后的打开逻辑 ---
            success = False
            logging.info("[Artifacts] 尝试自动打开文件: %s", temp_file)
            print("--- [强制调试] 尝试自动打开文件: %s" % temp_file)

            # 方法1 (Windows 优先): 使用 os.startfile()
            if sys.platform.startswith('win'):
                try:
                    os.startfile(temp_file)
                    logging.info("[Artifacts] 文件已通过 os.startfile() 打开")
                    print("--- [强制调试] 文件已通过 os.startfile() 打开")
                    self.display_message("assistant", f"已生成网页内容，并在默认应用中打开。")
                    success = True
                except Exception as os_err:
                    logging.error("[Artifacts] 使用 os.startfile 打开文件时出错: %s", os_err)
                    print("--- [强制调试] 使用 os.startfile 打开文件时出错: %s" % os_err)

            # 方法2 (Windows 次选): 使用 subprocess Popen start
            # 注意：Popen会立即返回，不会等待进程结束
            if not success and sys.platform.startswith('win'):
                try:
                    import subprocess
                    subprocess.Popen(['start', '', temp_file], shell=True)
                    logging.info("[Artifacts] 文件已通过 subprocess Popen start 打开")
                    print("--- [强制调试] 文件已通过 subprocess Popen start 打开")
                    self.display_message("assistant", f"已生成网页内容，并在默认应用中打开。")
                    success = True
                except Exception as sub_err:
                    logging.error("[Artifacts] 使用 subprocess Popen start 打开文件时出错: %s", sub_err)
                    print("--- [强制调试] 使用 subprocess Popen start 打开文件时出错: %s" % sub_err)

            # 方法3 (备选/跨平台): 使用 webbrowser.open()
            # 放在最后，因为在当前系统上行为异常
            if not success:
                try:
                    file_url = Path(temp_file).as_uri()
                    webbrowser.open(file_url)
                    logging.info("[Artifacts] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    print("--- [强制调试] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    # 即使可能被重定向，也告知用户尝试了
                    self.display_message("assistant", f"已生成网页内容，尝试在默认浏览器中打开。")
                    success = True # 标记为尝试过
                except Exception as wb_err:
                    logging.error("[Artifacts] 使用 webbrowser 打开文件时出错: %s", wb_err)
                    print("--- [强制调试] 使用 webbrowser 打开文件时出错: %s" % wb_err)

            # 如果所有方法都失败，显示文件路径供手动打开
            if not success:
                logging.info("[Artifacts] 所有自动打开方法均失败，直接显示文件路径: %s", temp_file)
                print("--- [强制调试] 所有自动打开方法均失败，直接显示文件路径: %s" % temp_file)
                self.display_message("assistant", f"已生成网页内容，但自动打开浏览器/应用失败。请手动打开以下文件查看：\n{temp_file}")
            # --- 结束修改后的打开逻辑 ---
        except Exception as e:
            logging.error("[Artifacts] 处理网页内容时出错: %s", e)
            self.display_message("assistant", f"抱歉，处理网页内容时遇到错误：{e}")

    # --- 新增渲染图片到Artifacts区域函数 ---
    def render_artifacts_image(self, image_path):
        """将图片路径嵌入HTML文件并在浏览器中打开"""
        try:
            # 生成简单的HTML文件显示图片
            html_content = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <title>生成的图片</title>
                <style>
                    img {{ max-width: 100%; height: auto; }}
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                </style>
            </head>
            <body>
                <h1>生成的图片</h1>
                <img src="file://{image_path}" alt="Generated Image">
                <p>图片路径: {image_path}</p>
            </body>
            </html>
            """
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"artifacts_image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info("[Artifacts] 图片HTML页面已保存到临时文件: %s", temp_file)
            
            # --- 修改后的打开逻辑 ---
            success = False
            logging.info("[Artifacts] 尝试自动打开文件: %s", temp_file)
            print("--- [强制调试] 尝试自动打开文件: %s" % temp_file)

            # 方法1 (Windows 优先): 使用 os.startfile()
            if sys.platform.startswith('win'):
                try:
                    os.startfile(temp_file)
                    logging.info("[Artifacts] 文件已通过 os.startfile() 打开")
                    print("--- [强制调试] 文件已通过 os.startfile() 打开")
                    self.display_message("assistant", f"已生成图片，并在默认应用中打开。")
                    success = True
                except Exception as os_err:
                    logging.error("[Artifacts] 使用 os.startfile 打开文件时出错: %s", os_err)
                    print("--- [强制调试] 使用 os.startfile 打开文件时出错: %s" % os_err)

            # 方法2 (Windows 次选): 使用 subprocess Popen start
            # 注意：Popen会立即返回，不会等待进程结束
            if not success and sys.platform.startswith('win'):
                try:
                    import subprocess
                    subprocess.Popen(['start', '', temp_file], shell=True)
                    logging.info("[Artifacts] 文件已通过 subprocess Popen start 打开")
                    print("--- [强制调试] 文件已通过 subprocess Popen start 打开")
                    self.display_message("assistant", f"已生成图片，并在默认应用中打开。")
                    success = True
                except Exception as sub_err:
                    logging.error("[Artifacts] 使用 subprocess Popen start 打开文件时出错: %s", sub_err)
                    print("--- [强制调试] 使用 subprocess Popen start 打开文件时出错: %s" % sub_err)

            # 方法3 (备选/跨平台): 使用 webbrowser.open()
            # 放在最后，因为在当前系统上行为异常
            if not success:
                try:
                    file_url = Path(temp_file).as_uri()
                    webbrowser.open(file_url)
                    logging.info("[Artifacts] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    print("--- [强制调试] 文件已通过 webbrowser.open() 打开 (可能被重定向)")
                    # 即使可能被重定向，也告知用户尝试了
                    self.display_message("assistant", f"已生成图片，尝试在默认浏览器中打开。")
                    success = True # 标记为尝试过
                except Exception as wb_err:
                    logging.error("[Artifacts] 使用 webbrowser 打开文件时出错: %s", wb_err)
                    print("--- [强制调试] 使用 webbrowser 打开文件时出错: %s" % wb_err)

            # 如果所有方法都失败，显示文件路径供手动打开
            if not success:
                logging.info("[Artifacts] 所有自动打开方法均失败，直接显示文件路径: %s", temp_file)
                print("--- [强制调试] 所有自动打开方法均失败，直接显示文件路径: %s" % temp_file)
                self.display_message("assistant", f"已生成图片，但自动打开浏览器/应用失败。请手动打开以下文件查看：\n{temp_file}")
            # --- 结束修改后的打开逻辑 ---
        except Exception as e:
            logging.error("[Artifacts] 渲染图片时出错: %s", e)
            self.display_message("assistant", f"抱歉，渲染图片时遇到错误：{e}")