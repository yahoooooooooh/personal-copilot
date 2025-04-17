# ui_components.py (v3.4 - 支持运行时输入API密钥并移除对 prompt.txt 的依赖，支持主题切换，更新按钮颜色)
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from pathlib import Path
import logging
from config_manager import update_api_key, save_theme_preference
from prompts import PROMPT_ATRI

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, selected_config, all_backend_configs, chat_manager_ref, switch_backend_func, create_new_chat_func, ensure_prompt_func):
        """
        初始化设置窗口 (支持API密钥输入和主题切换)。
        Args:
            master: 父窗口 (主 App)。
            selected_config (dict): 当前选中的后端配置字典 (此处保留参数但不再使用)。
            all_backend_configs (list): 所有后端配置字典的列表 (此处保留参数但不再使用)。
            chat_manager_ref: ChatManager 实例引用。
            switch_backend_func: Controller 中的切换后端函数引用 (此处保留参数但不再使用)。
            create_new_chat_func: Controller 中的新建聊天函数引用。
            ensure_prompt_func: 获取 prompt 文件路径的函数引用（不再使用）。
        """
        super().__init__(master)
        self.title("设置 - 提示词与API密钥")
        self.geometry("500x600")  # 调整窗口大小以容纳API密钥输入和主题切换和模式选项和中转模型选项
        self.resizable(False, False)
        self.master_app = master  # 主程序引用，用于 after 调用回调
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 保存传入的引用和数据
        self.chat_manager = chat_manager_ref
        self.create_new_chat_callback = create_new_chat_func
        self.api_keys = {}  # 存储用户输入的API密钥
        self.use_intermediate_model = False  # 是否使用中转模型
        self.intermediate_model = "deepseek-chat"  # 默认中转模型

        # --- UI 布局 ---
        self.setup_ui()

        # 加载初始设置
        self.load_settings()
        self.load_selected_prompt("PROMPT_DEFAULT")

    def setup_ui(self):
        """设置 UI 控件和布局"""
        # 设置窗口背景色和透明度
        self.configure(fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
        try:
            self.attributes('-alpha', 0.95)
        except tk.TclError:
            logging.warning("当前系统可能不支持窗口透明度")

        # 创建顶部导航栏
        self.nav_frame = ctk.CTkFrame(self, fg_color=ctk.ThemeManager.theme["CTkToplevel"]["fg_color"], corner_radius=0)
        self.nav_frame.pack(fill="x", padx=0, pady=0)
        self.nav_label = ctk.CTkLabel(self.nav_frame, text="设置", font=ctk.CTkFont(size=20, weight="bold"))
        self.nav_label.pack(side="left", padx=20, pady=10)
        
        # 创建导航按钮
        self.nav_buttons = {}
        nav_items = [("提示词", "prompt"), ("模式", "mode"), ("API密钥", "api"), ("主题", "theme")]
        for i, (text, key) in enumerate(nav_items):
            btn = ctk.CTkButton(self.nav_frame, text=text, fg_color="transparent", hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"], command=lambda k=key: self.show_section(k))
            btn.pack(side="left", padx=10, pady=10)
            self.nav_buttons[key] = btn
        self.nav_buttons["prompt"].configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])  # 默认选中提示词

        # 创建内容区域
        self.content_frame = ctk.CTkFrame(self, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 创建各个部分的卡片
        self.sections = {}
        self.create_prompt_section()
        self.create_mode_section()
        self.create_api_section()
        self.create_theme_section()

        # 默认显示提示词部分
        self.show_section("prompt")

        # 底部按钮区域
        self.button_frame = ctk.CTkFrame(self, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
        self.button_frame.pack(fill="x", padx=20, pady=10)
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)
        self.button_frame.grid_columnconfigure(2, weight=1)

        self.save_button = ctk.CTkButton(self.button_frame, text="保存并应用", command=self.save_settings)
        self.save_button.grid(row=0, column=0, padx=10, pady=10)

        self.cancel_button = ctk.CTkButton(self.button_frame, text="取消", command=self.on_closing)
        self.cancel_button.grid(row=0, column=1, padx=10, pady=10)

        self.save_prompts_button = ctk.CTkButton(self.button_frame, text="保存所有提示词", command=self.save_all_prompts)
        self.save_prompts_button.grid(row=0, column=2, padx=10, pady=10)

    def create_prompt_section(self):
        """创建提示词设置卡片"""
        frame = ctk.CTkFrame(self.content_frame, fg_color=ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"], corner_radius=10)
        self.sections["prompt"] = frame
        
        self.prompt_select_label = ctk.CTkLabel(frame, text="选择要编辑的提示词:", font=ctk.CTkFont(size=16, weight="bold"))
        self.prompt_select_label.pack(padx=15, pady=(15, 5), anchor="w")
        self.prompt_select_var = ctk.StringVar(value="PROMPT_DEFAULT")
        self.prompt_select_menu = ctk.CTkOptionMenu(frame, values=["PROMPT_DEFAULT", "PROMPT_NETWORKING", "PROMPT_ARTIFACTS", "PROMPT_ATRI", "PROMPT_TRANSLATE"], variable=self.prompt_select_var, command=self.load_selected_prompt)
        self.prompt_select_menu.pack(padx=15, pady=5, fill="x")

        self.prompt_label = ctk.CTkLabel(frame, text="系统提示词 (修改后需保存并会自动新建对话):")
        self.prompt_label.pack(padx=15, pady=(10, 5), anchor="w")
        self.prompt_textbox = ctk.CTkTextbox(frame, wrap="word", height=250, corner_radius=8)
        self.prompt_textbox.pack(padx=15, pady=10, fill="both", expand=True)

    def create_mode_section(self):
        """创建模式设置卡片"""
        frame = ctk.CTkFrame(self.content_frame, fg_color=ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"], corner_radius=10)
        self.sections["mode"] = frame
        
        self.mode_label = ctk.CTkLabel(frame, text="模式设置 (选择后保存):", font=ctk.CTkFont(size=16, weight="bold"))
        self.mode_label.pack(padx=15, pady=(15, 10), anchor="w")
        
        # 获取当前模式的变量引用
        self.search_var = self.master_app.app_controller.ui.get('search_var')
        self.atri_var = self.master_app.app_controller.ui.get('atri_var')
        self.artifacts_var = self.master_app.app_controller.ui.get('artifacts_var')
        self.translate_var = self.master_app.app_controller.ui.get('translate_var')

        # 创建复选框
        self.search_check = ctk.CTkCheckBox(frame, text="搜索模式", variable=self.search_var)
        self.search_check.pack(padx=15, pady=5, anchor="w")
        
        self.atri_check = ctk.CTkCheckBox(frame, text="ATRI模式", variable=self.atri_var)
        self.atri_check.pack(padx=15, pady=5, anchor="w")
        
        self.artifacts_check = ctk.CTkCheckBox(frame, text="Artifacts模式", variable=self.artifacts_var)
        self.artifacts_check.pack(padx=15, pady=5, anchor="w")
        
        self.translate_check = ctk.CTkCheckBox(frame, text="翻译模式", variable=self.translate_var)
        self.translate_check.pack(padx=15, pady=5, anchor="w")

    def create_api_section(self):
        """创建API密钥设置卡片"""
        frame = ctk.CTkFrame(self.content_frame, fg_color=ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"], corner_radius=10)
        self.sections["api"] = frame
        
        self.api_key_label = ctk.CTkLabel(frame, text="API密钥设置 (输入后保存):", font=ctk.CTkFont(size=16, weight="bold"))
        self.api_key_label.pack(padx=15, pady=(15, 10), anchor="w")

        # 动态添加所有API密钥输入框
        self.api_key_entries = {}
        all_keys = {
            "DEEPSEEK_API_KEY": "DeepSeek API Key",
            "GROK_API_KEY": "Grok API Key",
            "TAVILY_API_KEY": "Tavily API Key"
        }
        for key_name, key_label in all_keys.items():
            entry_frame = ctk.CTkFrame(frame)
            entry_frame.pack(fill="x", padx=15, pady=5)
            label = ctk.CTkLabel(entry_frame, text=f"{key_label}:", width=150)
            label.pack(side="left", padx=(0, 10))
            entry = ctk.CTkEntry(entry_frame, placeholder_text=f"输入 {key_label}", show="*")
            entry.pack(side="left", fill="x", expand=True)
            self.api_key_entries[key_name] = entry
            # 如果已配置，显示部分密钥
            current_value = os.getenv(key_name, "")
            if current_value:
                entry.insert(0, current_value)
                logging.info("已加载API密钥: %s", key_name)
            else:
                logging.warning("未找到API密钥: %s", key_name)

    def create_theme_section(self):
        """创建主题设置卡片"""
        frame = ctk.CTkFrame(self.content_frame, fg_color=ctk.ThemeManager.theme["CTkFrame"]["top_fg_color"], corner_radius=10)
        self.sections["theme"] = frame
        
        self.theme_label = ctk.CTkLabel(frame, text="主题设置 (选择后保存):", font=ctk.CTkFont(size=16, weight="bold"))
        self.theme_label.pack(padx=15, pady=(15, 10), anchor="w")
        
        self.theme_var = ctk.StringVar(value="light")  # 默认明亮模式
        self.theme_menu = ctk.CTkOptionMenu(frame, values=["light", "dark"], variable=self.theme_var)
        self.theme_menu.pack(padx=15, pady=10, fill="x")

    def show_section(self, section_key):
        """显示选定的设置部分，隐藏其他部分"""
        for key, frame in self.sections.items():
            if key == section_key:
                frame.pack(fill="both", expand=True, padx=10, pady=10)
                self.nav_buttons[key].configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            else:
                frame.pack_forget()
                self.nav_buttons[key].configure(fg_color="transparent")

    def load_settings(self):
        """加载当前设置到 UI 控件"""
        # 加载主题设置
        try:
            current_mode = ctk.get_appearance_mode().lower()
            self.theme_var.set(current_mode)
        except Exception as e:
            logging.error("加载主题设置时出错: %s", e)
            self.theme_var.set("light")

    def load_selected_prompt(self, prompt_name):
        """加载选定的提示词到文本框"""
        try:
            prompt_content = self.chat_manager.get_prompt_by_name(prompt_name)
            self.prompt_textbox.delete("1.0", "end")
            self.prompt_textbox.insert("1.0", prompt_content)
            logging.info("已加载提示词: %s", prompt_name)
        except Exception as e:
            logging.error("加载提示词 %s 时出错: %s", prompt_name, e)
            self.prompt_textbox.delete("1.0", "end")
            self.prompt_textbox.insert("1.0", f"错误：加载失败\n{e}")

    def save_settings(self):
        """保存设置并应用更改"""
        logging.info("[Action] Saving settings...")
        prompt_changed = False
        original_prompt = self.chat_manager.get_custom_atri_prompt()

        # 1. 保存提示词 (如果更改)
        try:
            new_prompt_content = self.prompt_textbox.get("1.0", "end-1c").strip()  # 获取新内容
            # 只有当内容实际发生变化时才更新并标记
            if new_prompt_content and new_prompt_content != original_prompt:
                self.chat_manager.set_custom_atri_prompt(new_prompt_content)
                logging.info("提示词已更新并保存到内存")
                prompt_changed = True
            else:
                logging.info("提示词内容未更改")
        except Exception as e:
            logging.error("保存提示词时出错: %s", e)
            messagebox.showerror("保存错误", f"保存提示词时出错:\n{e}")

        # 2. 保存API密钥 (如果用户输入了)
        api_keys_updated = False
        for key_name, entry in self.api_key_entries.items():
            key_value = entry.get().strip()
            if key_value:
                update_api_key(key_name, key_value)
                api_keys_updated = True
                logging.info("用户输入了API密钥: %s", key_name)
            else:
                logging.warning("用户未输入API密钥: %s", key_name)

        # 3. 保存并应用主题设置
        theme_mode = self.theme_var.get()
        logging.info("用户选择了主题模式: %s", theme_mode)
        ctk.set_appearance_mode(theme_mode)
        save_theme_preference(theme_mode)  # 保存主题偏好
        logging.info("主题模式已应用并保存: %s", theme_mode)
        
        # 更新按钮颜色
        if hasattr(self.master_app, 'app_controller') and self.master_app.app_controller:
            self.master_app.app_controller.update_button_appearance()
            logging.info("主题切换后更新按钮颜色")

        # 4. 应用模式设置
        self.master_app.app_controller.toggle_search_mode()
        self.master_app.app_controller.toggle_atri_mode()
        self.master_app.app_controller.toggle_artifacts_mode()
        self.master_app.app_controller.toggle_translate_mode()

        # 5. 如果提示词被修改了，则调用新建对话的回调
        if prompt_changed:
            logging.info("应用提示词更改：新建对话")
            # 延迟调用，确保设置窗口关闭流程之后执行
            self.master_app.after(50, self.create_new_chat_callback)

        # 6. 如果API密钥被更新，可能需要重新初始化后端
        if api_keys_updated:
            logging.info("API密钥已更新，重新构建后端配置")
            # 可以触发一个后端重新扫描或初始化逻辑，这里假设控制器会处理
            self.master_app.after(50, lambda: self.master_app.app_controller.switch_backend(
                self.master_app.app_controller.selected_backend_config['display_name'] if self.master_app.app_controller.selected_backend_config else "无可用 API 配置"
            ))

        # 7. 关闭设置窗口
        self.on_closing()

    def on_closing(self):
        """关闭窗口时的清理"""
        logging.info("[Action] Closing SettingsWindow")
        self.grab_release()  # 释放 grab
        # 通知 Controller 窗口已关闭
        if hasattr(self.master_app, 'app_controller') and self.master_app.app_controller:
            self.master_app.app_controller.settings_window = None
        self.destroy()

    def save_all_prompts(self):
        """保存所有提示词到文件"""
        try:
            current_prompt_name = self.prompt_select_var.get()
            current_prompt_content = self.prompt_textbox.get("1.0", "end-1c").strip()
            if current_prompt_content:
                self.chat_manager.set_prompt_by_name(current_prompt_name, current_prompt_content)
                logging.info("已更新提示词: %s", current_prompt_name)

            all_prompts = self.chat_manager.get_all_prompts()
            # 保存到 prompts.py
            with open('prompts.py', 'w', encoding='utf-8') as f:
                for prompt_name, prompt_content in all_prompts.items():
                    f.write(f'{prompt_name} = """{prompt_content}"""\n\n')
            logging.info("所有提示词已硬编码到prompts.py")
            
            # 同时保存到 prompts.json
            import json
            with open('prompts.json', 'w', encoding='utf-8') as f:
                json.dump(all_prompts, f, ensure_ascii=False, indent=2)
            logging.info("所有提示词已保存到prompts.json")
            
            messagebox.showinfo("保存成功", "所有提示词已保存并硬编码到代码中，同时更新了配置文件。")
            self.master_app.after(50, self.create_new_chat_callback)
        except Exception as e:
            logging.error("保存提示词时出错: %s", e)
            messagebox.showerror("保存错误", f"保存提示词时出错:\n{e}")