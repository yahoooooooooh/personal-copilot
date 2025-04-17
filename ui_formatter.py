# ui_formatter.py (v1.6 - 简化 apply_simple_formatting)
import customtkinter as ctk
import tkinter as tk
import re

def configure_basic_tags(textbox: ctk.CTkTextbox):
    """
    配置 Textbox 的基本格式标签。
    由于 CTkTextbox 不支持 tag_configure 的高级选项，此函数现在仅用于记录。
    """
    print("--- [格式化] configure_basic_tags: 由于 CTkTextbox 限制，跳过 tag_configure 调用。---")

def remove_markdown_tags(text: str) -> str:
    """
    移除文本中的 Markdown 标记。
    参数:
        text (str): 待处理的文本
    返回:
        str: 处理后的文本
    """
    processed_text = text
    # 移除标题标记 (如果它们出现在块的开头) - 注意这可能不完美
    processed_text = re.sub(r"^(#+)\s+", "", processed_text)
    # 移除列表标记 (如果它们出现在块的开头)
    processed_text = re.sub(r"^(\*|-|\d+\.)\s+", "", processed_text)
    # 移除行内代码 ``
    processed_text = re.sub(r"`(.+?)`", r"\1", processed_text)
    # 移除加粗 ** **
    processed_text = re.sub(r"\*\*(.*?)\*\*", r"\1", processed_text)
    # 移除斜体 * * (避免匹配 ***)
    processed_text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", processed_text)
    return processed_text

def apply_simple_formatting(textbox: ctk.CTkTextbox, text: str, start_index: str):
    """
    对文本应用简单的 Markdown 处理：
    - 移除 Markdown 标记 (##, **, *, `)。
    - 不再尝试按行处理或添加额外换行。
    - 直接插入处理后的文本块。
    参数:
        textbox (ctk.CTkTextbox): 文本框对象
        text (str): 待处理的文本
        start_index (str): 插入的起始索引
    """
    if not text: return

    try:
        textbox.configure(state="normal")

        # --- 移除块内的 Markdown 标记 ---
        processed_text = remove_markdown_tags(text)

        # --- 直接插入处理后的文本块 ---
        # 使用 start_index (通常是 "end") 来插入
        textbox.insert(start_index, processed_text)

    except Exception as e:
        print(f"!!! 应用简单格式化（简化版）时出错: {e} !!!")
        # 插入原始文本，避免因格式化失败丢失内容
        try:
            textbox.configure(state="normal")
            textbox.insert(start_index, text) # 插入原始未处理文本
        except Exception as insert_e:
            print(f"!!! 格式化失败后尝试插入原始文本也出错: {insert_e} !!!")
    finally:
        try:
            textbox.configure(state="disabled") # 最终确保禁用
        except Exception as final_e:
            print(f"!!! 最终设置 textbox 为 disabled 时出错: {final_e} !!!")