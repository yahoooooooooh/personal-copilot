# ui_builder.py (v2.19 - 添加动态颜色计算，支持基于主题色生成UI颜色)
import customtkinter as ctk
import tkinter as tk
from pathlib import Path
import logging  # 添加logging模块导入
from config_manager import load_theme_preference
import colorsys
import sys

# --- UI Theme Settings ---
ctk.set_appearance_mode(load_theme_preference())  # 加载用户保存的主题偏好
if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
else:
    base_path = Path(__file__).resolve().parent
theme_path = base_path / "yellow_theme.json"
logging.info(f"尝试加载主题文件，路径: {theme_path}")
if theme_path.exists():
    try:
        ctk.set_default_color_theme(str(theme_path))
        logging.info(f"已加载自定义主题: {theme_path}")
    except Exception as e:
        logging.error(f"加载自定义主题时出错: {e}, 使用默认 'blue' 主题")
        ctk.set_default_color_theme("blue")
else:
    logging.warning(f"警告: 未找到主题文件 {theme_path}, 使用默认 'blue' 主题")
    ctk.set_default_color_theme("blue")

WINDOW_TRANSPARENCY = 0.95

# 定义基础主题色 (RGB格式，范围0-255)
BASE_COLOR_LIGHT = (224, 169, 143)  # 浅橙红色 - 明亮模式
BASE_COLOR_DARK = (100, 100, 100)   # 中灰色 - 暗黑模式

def rgb_to_hex(rgb):
    """将RGB颜色转换为十六进制格式"""
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])

def adjust_color(rgb, value_adjust=0.0, sat_adjust=0.0):
    """调整颜色的明度和饱和度，返回新的RGB颜色"""
    # 将RGB转换为HSV
    r, g, b = [x / 255.0 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    # 调整明度(Value)和饱和度(Saturation)
    v = max(0.0, min(1.0, v + value_adjust))
    s = max(0.0, min(1.0, s + sat_adjust))
    # 转换回RGB
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))

def get_theme_colors(mode):
    """根据主题模式生成颜色方案"""
    base_color = BASE_COLOR_DARK if mode == "dark" else BASE_COLOR_LIGHT
    return {
        "button_active": rgb_to_hex(adjust_color(base_color, value_adjust=0.1, sat_adjust=0.1)),  # 激活按钮：明度+10%，饱和度+10%
        "button_inactive": rgb_to_hex(adjust_color(base_color, value_adjust=-0.1, sat_adjust=-0.1)),  # 非激活按钮：明度-10%，饱和度-10%
    }

def initialize_function_buttons(functions_frame, colors):
    """初始化功能按钮并返回相关变量和按钮对象"""
    search_var = ctk.IntVar(value=0)
    search_button = ctk.CTkButton(functions_frame, text="🌐", width=30, height=30, font=ctk.CTkFont(size=16), fg_color=colors["button_inactive"])
    search_button.pack(side="left", padx=(5, 10))
    print(f"--- [调试] 搜索按钮初始化，fg_color={colors['button_inactive']} ---")

    atri_var = ctk.IntVar(value=0)
    atri_button = ctk.CTkButton(functions_frame, text="💖", width=30, height=30, font=ctk.CTkFont(size=16), fg_color=colors["button_inactive"])
    atri_button.pack(side="left", padx=(5, 10))
    print(f"--- [调试] ATRI按钮初始化，fg_color={colors['button_inactive']} ---")

    artifacts_var = ctk.IntVar(value=0)
    artifacts_button = ctk.CTkButton(functions_frame, text="📊", width=30, height=30, font=ctk.CTkFont(size=16), fg_color=colors["button_inactive"])
    artifacts_button.pack(side="left", padx=(5, 10))
    print(f"--- [调试] Artifacts按钮初始化，fg_color={colors['button_inactive']} ---")

    translate_var = ctk.IntVar(value=0)
    translate_button = ctk.CTkButton(functions_frame, text="🌍", width=30, height=30, font=ctk.CTkFont(size=16), fg_color=colors["button_inactive"])
    translate_button.pack(side="left", padx=(5, 10))
    print(f"--- [调试] 翻译按钮初始化，fg_color={colors['button_inactive']} ---")

    upload_button = ctk.CTkButton(functions_frame, text="📁", width=30, height=30, font=ctk.CTkFont(size=16))
    upload_button.pack(side="left", padx=(5, 10))

    topmost_var = ctk.IntVar(value=1)  # 初始状态为置顶
    topmost_button = ctk.CTkButton(functions_frame, text="📌", width=30, height=30, font=ctk.CTkFont(size=16), fg_color=colors["button_active"])
    topmost_button.pack(side="left", padx=(5, 10))
    print(f"--- [调试] 置顶按钮初始化，fg_color={colors['button_active']} ---")

    model_optionmenu_var = ctk.StringVar(value="选择模型")
    model_optionmenu = ctk.CTkOptionMenu(functions_frame, values=["选择模型"], variable=model_optionmenu_var, width=150)
    model_optionmenu.pack(side="left", padx=(5, 10))

    return {
        'search_var': search_var, 'search_button': search_button,
        'atri_var': atri_var, 'atri_button': atri_button,
        'artifacts_var': artifacts_var, 'artifacts_button': artifacts_button,
        'translate_var': translate_var, 'translate_button': translate_button,
        'upload_button': upload_button,
        'topmost_var': topmost_var, 'topmost_button': topmost_button,
        'model_optionmenu_var': model_optionmenu_var, 'model_optionmenu': model_optionmenu
    }

def setup_input_area(chat_frame, app):
    """设置输入区域和相关按钮，返回输入框和按钮对象"""
    input_area_container = ctk.CTkFrame(chat_frame, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
    input_area_container.pack(pady=(5, 10), padx=10, fill="x")

    functions_and_status_frame = ctk.CTkFrame(input_area_container, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
    functions_and_status_frame.pack(fill="x", pady=(0, 5))

    functions_frame = ctk.CTkFrame(functions_and_status_frame, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
    functions_frame.pack(side="left", padx=(0, 10))

    status_label = ctk.CTkLabel(functions_and_status_frame, text="", width=30, anchor="w")
    status_label.pack(side="left", padx=(10, 0), fill="x", expand=True)

    current_mode = ctk.get_appearance_mode().lower()
    colors = get_theme_colors(current_mode)
    button_elements = initialize_function_buttons(functions_frame, colors)

    input_frame = ctk.CTkFrame(input_area_container, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
    input_frame.pack(fill="x", pady=(5, 0))

    input_entry = ctk.CTkTextbox(input_frame, wrap="word", height=30, border_width=1)  # 初始高度为一行
    input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    # 绑定事件以动态调整输入框高度，添加防抖逻辑
    height_adjust_pending = None
    def adjust_input_height(event=None):
        """
        动态调整输入框高度根据内容行数，添加防抖逻辑以避免频繁调整
        参数:
            event: 触发事件对象，通常为按键释放事件
        """
        nonlocal height_adjust_pending
        if height_adjust_pending is not None:
            app.after_cancel(height_adjust_pending)  # 取消之前的待处理任务
        
        def do_adjust():
            nonlocal height_adjust_pending
            try:
                content = input_entry.get("1.0", "end-1c")
                lines = content.count('\n') + 1  # 计算行数
                if lines > 3:
                    lines = 3  # 最多三行
                new_height = lines * 30  # 每行约30像素
                current_height = input_entry.cget("height")
                if new_height != current_height:  # 只有高度变化时才更新
                    input_entry.configure(height=new_height)
                    logging.info("[输入框高度调整] 调整输入框高度为 %d 像素（%d 行）", new_height, lines)
            except Exception as e:
                logging.error("[输入框高度调整] 调整高度时出错: %s", e)
            finally:
                height_adjust_pending = None
        
        height_adjust_pending = app.after(100, do_adjust)  # 延迟100ms执行调整
    
    input_entry.bind("<KeyRelease>", adjust_input_height)  # 每次按键释放后调整高度

    heart_hover_color = "#FFA500"
    heart_new_chat_button = ctk.CTkButton(input_frame, text="❤", width=35, height=30, font=ctk.CTkFont(size=16), fg_color="transparent", border_width=0, hover_color=heart_hover_color)
    heart_new_chat_button.pack(side="right", padx=(0, 0))

    cancel_button = ctk.CTkButton(input_frame, text="取消", width=60, height=30, fg_color="#FF6347", hover_color="#FF4500")
    cancel_button.pack(side="right", padx=(5, 5))
    cancel_button.pack_forget()  # 初始隐藏，直到流式传输开始

    return input_entry, status_label, heart_new_chat_button, cancel_button, button_elements

def build_ui(app, app_controller=None):
    """构建 UI 组件并返回 UI 元素字典"""
    app.title("Personal Copilot v4.6 (API Only)")
    app.geometry("600x600")  # 初始宽度较小，因为Artifacts区域默认隐藏
    try:
        app.attributes('-alpha', WINDOW_TRANSPARENCY)
    except tk.TclError:
        print("--- 警告: 当前系统可能不支持窗口透明度 ('-alpha') ---")

    # 主框架，分为左右两部分
    main_frame = ctk.CTkFrame(app, corner_radius=0, fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
    main_frame.pack(fill="both", expand=True)
    main_frame.grid_columnconfigure(0, weight=1)  # 聊天区域占满宽度
    main_frame.grid_columnconfigure(1, weight=0)  # Artifacts区域权重为0
    main_frame.grid_rowconfigure(0, weight=1)  # 确保主框架垂直扩展

    # 左侧聊天区域
    chat_frame = ctk.CTkFrame(main_frame, corner_radius=0)
    chat_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    chat_frame.grid_rowconfigure(0, weight=1)  # 确保聊天区域垂直扩展
    chat_display = ctk.CTkTextbox(chat_frame, state="disabled", wrap="word", border_width=1)
    chat_display.pack(pady=(10, 0), padx=10, fill="both", expand=True)

    # 设置输入区域和按钮
    input_entry, status_label, heart_new_chat_button, cancel_button, button_elements = setup_input_area(chat_frame, app)

    # 设置按钮
    settings_button = ctk.CTkButton(chat_frame, text="⚙️", width=30)
    settings_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")

    # 返回 UI 元素字典
    return {
        'chat_display': chat_display,
        'input_entry': input_entry,
        'status_label': status_label,
        'search_button': button_elements['search_button'], 'search_var': button_elements['search_var'],
        'atri_button': button_elements['atri_button'], 'atri_var': button_elements['atri_var'],
        'artifacts_button': button_elements['artifacts_button'], 'artifacts_var': button_elements['artifacts_var'],
        'chat_elements': [],
        'settings_button': settings_button,
        'heart_new_chat_button': heart_new_chat_button,
        'upload_button': button_elements['upload_button'],
        'model_optionmenu': button_elements['model_optionmenu'], 'model_optionmenu_var': button_elements['model_optionmenu_var'],
        'cancel_button': cancel_button,
        'topmost_button': button_elements['topmost_button'], 'topmost_var': button_elements['topmost_var'],
        'translate_button': button_elements['translate_button'], 'translate_var': button_elements['translate_var'],
        'chat_container': None,
        'canvas': None
    }