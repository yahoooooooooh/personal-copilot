# main.py (v4.19 - 修复变量引用错误并支持运行时输入API密钥，支持cefpython3清理，新增置顶切换功能)
import customtkinter as ctk
import os
import tkinter as tk
from tkinter import messagebox
import threading
import time
import re
from pathlib import Path
import sys
import ctypes  # 用于设置线程模式
import logging  # 引入 logging 模块
import traceback

# 设置日志配置
def setup_logging():
    """设置日志配置，输出到终端和文件"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # 输出到控制台
            logging.FileHandler('app.log')  # 输出到文件
        ]
    )
    logging.info("日志系统初始化完成，输出到终端和文件")

# 设置 STA 线程模式以支持 WebView2
def set_sta_mode():
    try:
        # 设置线程模式为 STA (Single-Threaded Apartment)
        ctypes.windll.ole32.CoInitialize(0)
        logging.info("已设置线程模式为 STA")
    except Exception as e:
        logging.warning("设置 STA 线程模式时出错: %s", e)

# 在程序启动时调用
set_sta_mode()
setup_logging()  # 初始化日志系统

# --- 导入自定义模块 ---
try:
    from utils import get_data_dir
except ImportError:
    logging.error("无法导入 utils.py, 请确保该文件存在且路径正确")
    # 提供备用函数
    def get_data_dir():
        return Path('.')

import api_client
import grok_client  # 替换 gemini_client 为 grok_client
from chat_manager import ChatManager
from ui_formatter import configure_basic_tags, apply_simple_formatting
from ui_components import SettingsWindow
from event_handlers import AppController
from config_manager import load_environment_variables, build_backend_configs, get_config_for_controller
from ui_builder import build_ui, get_theme_colors
from ui_builder import build_ui

# --- 全局变量定义 ---
app = None

# --- 初始化 ---
# 加载环境变量
load_environment_variables()

# 构建后端配置列表 & 获取显示名称
backend_display_names = build_backend_configs()

# Chat Manager 初始化
chat_manager = ChatManager()

# --- UI 设置 ---
app = ctk.CTk()

# 构建 UI 并获取 UI 元素
ui_elements = build_ui(app)  # 不传递 app_controller

# --- 创建 AppController 实例 ---
utils_functions = {}  # 移除对 ensure_prompt_file 的引用
config_for_controller = get_config_for_controller()
app_controller = AppController(app, ui_elements, chat_manager, utils_functions, config_for_controller)

# 确保 app_controller 绑定到 app 对象
app.app_controller = app_controller  # 新增：将 app_controller 绑定到 app 对象

# 更新 UI 控件的 command 和绑定
def bind_ui_events(ui_elements, app_controller):
    """绑定 UI 控件的事件和命令"""
    ui_elements['search_button'].configure(command=lambda: toggle_search_mode(ui_elements['search_var']))
    ui_elements['atri_button'].configure(command=lambda: toggle_atri_mode(ui_elements['atri_var']))
    ui_elements['artifacts_button'].configure(command=lambda: toggle_artifacts_mode(ui_elements['artifacts_var']))  # 新增
    ui_elements['translate_button'].configure(command=lambda: toggle_translate_mode(ui_elements['translate_var']))  # 新增翻译按钮绑定
    ui_elements['input_entry'].bind("<Return>", lambda event: app_controller.handle_send_message())
    ui_elements['settings_button'].configure(command=app_controller.open_settings_window)
    ui_elements['heart_new_chat_button'].configure(command=app_controller.handle_create_new_chat)
    # 新增取消按钮绑定
    ui_elements['cancel_button'].configure(command=app_controller.cancel_streaming)
    # 新增置顶按钮绑定
    ui_elements['topmost_button'].configure(command=app_controller.toggle_topmost_mode)
    # 确保上传按钮绑定已在 MessageHandler 中完成
    # 确保模型选择器绑定已在 AppController 中完成

# 调用事件绑定函数
bind_ui_events(ui_elements, app_controller)

def toggle_search_mode(search_var):
    """切换搜索模式状态"""
    search_var.set(1 if search_var.get() == 0 else 0)
    app_controller.toggle_search_mode()

def toggle_atri_mode(atri_var):
    """切换ATRI模式状态"""
    atri_var.set(1 if atri_var.get() == 0 else 0)
    app_controller.toggle_atri_mode()

def toggle_artifacts_mode(artifacts_var):
    """切换Artifacts模式状态"""
    artifacts_var.set(1 if artifacts_var.get() == 0 else 0)
    app_controller.toggle_artifacts_mode()

def toggle_translate_mode(translate_var):
    """切换翻译模式状态"""
    translate_var.set(1 if translate_var.get() == 0 else 0)
    app_controller.toggle_translate_mode()

# --- 重写销毁方法以清理未完成的 after 任务并强制关闭 ---
def cleanup_after_tasks():
    """清理所有未完成的 after 任务"""
    try:
        for task_id in app.tk.eval('after info').split():
            app.after_cancel(task_id)
        logging.info("已取消所有未完成的 after 任务")
    except Exception as e:
        logging.warning("取消 after 任务时出错: %s", e)

def on_closing():
    """窗口关闭时的清理逻辑"""
    logging.info("程序正在关闭，执行清理操作")
    # 停止任何正在进行的流式传输
    if app_controller.is_streaming:
        app_controller.is_streaming = False
        logging.info("已强制停止流式传输")
    
    # 清理所有未完成的 after 任务
    cleanup_after_tasks()
    
    # 尝试销毁所有子窗口和组件
    try:
        for widget in app.winfo_children()[:]:  # 使用副本以避免修改列表时的错误
            try:
                widget.destroy()
                logging.info("已销毁组件: %s", widget)
            except tk.TclError as tcl_err:
                logging.warning("销毁组件 %s 时遇到 TclError，已忽略: %s", widget, tcl_err)
            except Exception as e:
                logging.warning("销毁组件 %s 时出错: %s", widget, e)
    except Exception as e:
        logging.warning("获取子组件列表时出错: %s", e)
    
    # 强制销毁主窗口
    try:
        app.destroy()
        logging.info("主窗口已销毁")
    except tk.TclError as tcl_err:
        logging.warning("销毁主窗口时遇到 TclError，已忽略: %s", tcl_err)
    except Exception as e:
        logging.warning("销毁主窗口时出错: %s", e)
    
    # 确保日志被写入文件
    logging.info("正在关闭日志系统...")
    logging.shutdown()  # 添加这一行
    
    # 确保程序退出
    sys.exit(0)

app.protocol("WM_DELETE_WINDOW", on_closing)

def start_application():
    """启动应用程序，执行初始设置和检查"""
    def initial_switch():
        global app_controller
        try:
            current_choice = app_controller.selected_backend_config['display_name'] if app_controller.selected_backend_config else "未知"
            if current_choice == "未知" and app_controller.backend_configs:
                current_choice = app_controller.backend_configs[0]['display_name']

            logging.info("正在进行初始后端状态检查与设置: %s", current_choice)
            if current_choice != "未知" and current_choice != "无可用 API 配置":
                app_controller.switch_backend(current_choice)
            elif ui_elements['status_label']:
                ui_elements['status_label'].configure(text="❌", text_color=("red", "red"))

        except Exception as e:
            logging.error("初始后端设置时出错: %s", e)
            if ui_elements['status_label']:
                ui_elements['status_label'].configure(text=f"❌", text_color=("red", "red"))

    def check_missing_api_keys():
        """检查缺失的API密钥，并在必要时打开设置窗口"""
        missing_keys = config_for_controller.get('missing_keys', {})
        if missing_keys:
            logging.warning("检测到缺失的API密钥: %s", ", ".join(missing_keys.values()))
            messagebox.showwarning("缺失API密钥", f"以下API密钥未配置：{', '.join(missing_keys.values())}\n请在设置窗口中输入密钥。")
            app_controller.open_settings_window()
        else:
            logging.info("所有API密钥已配置，无需用户输入")

    app.after(150, initial_switch)
    app.after(500, check_missing_api_keys)  # 延迟到500ms以确保UI优先显示

def handle_global_exception(exc_type, exc_value, exc_traceback):
    logging.error("未处理的异常: %s", exc_value, exc_info=(exc_type, exc_value, exc_traceback))
    messagebox.showerror("错误", f"发生了一个未处理的错误: {str(exc_value)}")

sys.excepthook = handle_global_exception

# --- 启动应用 ---
if __name__ == "__main__":
    start_application()
    app.mainloop()