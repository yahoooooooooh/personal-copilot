# chat_manager.py
import threading
from pathlib import Path
from utils import get_data_dir
import json
import logging

# 导入硬编码的提示词
from prompts import PROMPT_DEFAULT, PROMPT_NETWORKING, PROMPT_ARTIFACTS, PROMPT_ATRI, PROMPT_TRANSLATE

def load_prompts_from_config():
    try:
        with open('prompts.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning("未找到 prompts.json 文件，回退到硬编码的提示词")
        return {
            "PROMPT_DEFAULT": PROMPT_DEFAULT,
            "PROMPT_NETWORKING": PROMPT_NETWORKING,
            "PROMPT_ARTIFACTS": PROMPT_ARTIFACTS,
            "PROMPT_ATRI": PROMPT_ATRI,
            "PROMPT_TRANSLATE": PROMPT_TRANSLATE
        }

class ChatManager:
    def __init__(self):
        self.current_history = []
        self.search_mode = False   # 搜索模式状态
        self.atri_mode = False     # ATRI模式状态
        self.artifacts_mode = False  # 新增Artifacts模式状态
        self.translate_mode = False  # 新增翻译模式状态
        self.custom_atri_prompt = None  # 存储用户自定义的ATRI提示词
        self.custom_prompts = load_prompts_from_config()  # 从配置文件加载提示词
        self._lock = threading.Lock() # 使用实例锁
        self._initialize_history()
        print("--- ChatManager 初始化完成 ---")

    def _load_system_prompt(self):
        """
        根据当前启用的模式组合系统提示词，按优先级顺序：ATRI > Artifacts > 联网 > 翻译 > 默认。
        如果多个模式启用，则组合多个提示词内容；如果无模式启用，则使用默认提示词。
        """
        try:
            prompt_parts = []
            
            # 优先级 1: ATRI 模式（角色扮演）
            if self.atri_mode:
                if self.custom_atri_prompt:
                    prompt_parts.append(self.custom_atri_prompt)
                    print("=== 加载用户自定义的 ATRI 提示词 ===")
                else:
                    prompt_parts.append(PROMPT_ATRI)
                    print("=== 加载默认的 ATRI 提示词 ===")
            
            # 优先级 2: Artifacts 模式
            if self.artifacts_mode:
                prompt_parts.append(PROMPT_ARTIFACTS)
                print("--- 添加 Artifacts 模式提示词 ---")
            
            # 优先级 3: 联网模式（注意：联网提示词在发送消息时动态处理，此处仅占位）
            if self.search_mode:
                print("--- 联网模式已启用，提示词将在消息发送时动态添加 ---")
                # 联网提示词 PROMPT_NETWORKING 会在 message_handler.py 中动态格式化并插入，此处不添加
            
            # 优先级 4: 翻译模式
            if self.translate_mode:
                prompt_parts.append(PROMPT_TRANSLATE)
                print("--- 添加翻译模式提示词 ---")
            
            # 如果有模式启用，组合提示词；否则使用默认提示词
            if prompt_parts:
                combined_prompt = "\n\n--- 分隔线 ---\n\n".join(prompt_parts)
                print(f"--- 组合了 {len(prompt_parts)} 个模式的提示词 ---")
                return combined_prompt
            else:
                print("--- 无模式启用，使用默认提示词 ---")
                return PROMPT_DEFAULT
                
        except Exception as e:
            print(f"!!! 组合提示词时出错: {e} !!!")
            return PROMPT_DEFAULT  # 出错时返回默认提示词

    def _initialize_history(self):
        """初始化对话历史（带系统提示词）"""
        system_prompt = self._load_system_prompt()
        with self._lock:
            self.current_history = [{"role": "system", "content": system_prompt}]

    def get_current_history(self):
        """获取当前对话历史的副本"""
        with self._lock:
            # 返回副本以防止外部修改影响内部状态
            return [msg.copy() for msg in self.current_history]

    def create_new_chat(self):
        """新建对话（重新加载提示词）"""
        print("--- 新建对话 ---")
        self._initialize_history() # 会根据当前 atri_mode 或 artifacts_mode 加载正确的 prompt
        return True

    def add_message_to_current_chat(self, role, content):
        """添加消息到当前对话"""
        if not content or not role:
            print(f"--- [ChatManager] 尝试添加空消息 ({role})，已忽略 ---")
            return
        # 确保内容是字符串
        content_str = str(content).strip() # 转为字符串并去除首尾空白
        if not content_str:
             print(f"--- [ChatManager] 尝试添加空白消息 ({role})，已忽略 ---")
             return

        with self._lock:
            self.current_history.append({"role": role, "content": content_str})

    # --- 模式切换方法 ---
    def set_search_mode(self, enabled):
        """设置搜索模式状态"""
        if self.search_mode != enabled:
            self.search_mode = enabled
            print(f"--- 搜索模式已{'启用' if enabled else '禁用'} ---")

    def set_atri_mode(self, enabled):
        """设置ATRI模式状态"""
        if self.atri_mode != enabled:
            previously_enabled = self.atri_mode
            self.atri_mode = enabled
            print(f"--- ATRI模式已{'启用' if enabled else '禁用'} ---")

            # 更新系统提示词，但保留聊天历史
            system_prompt = self._load_system_prompt()
            with self._lock:
                # 检查历史中是否有系统消息，如果有则更新，否则添加
                found_system = False
                for i, msg in enumerate(self.current_history):
                    if msg.get("role") == "system":
                        self.current_history[i]["content"] = system_prompt
                        found_system = True
                        break
                if not found_system:
                    self.current_history.insert(0, {"role": "system", "content": system_prompt})
                print("--- 由于 ATRI 模式更改，已更新系统提示词，但保留聊天历史 ---")

    def set_artifacts_mode(self, enabled):
        """设置Artifacts模式状态"""
        if self.artifacts_mode != enabled:
            previously_enabled = self.artifacts_mode
            self.artifacts_mode = enabled
            print(f"--- Artifacts模式已{'启用' if enabled else '禁用'} ---")

            # 更新系统提示词，但保留聊天历史
            system_prompt = self._load_system_prompt()
            with self._lock:
                found_system = False
                for i, msg in enumerate(self.current_history):
                    if msg.get("role") == "system":
                        self.current_history[i]["content"] = system_prompt
                        found_system = True
                        break
                if not found_system:
                    self.current_history.insert(0, {"role": "system", "content": system_prompt})
                print("--- 由于 Artifacts 模式更改，已更新系统提示词，但保留聊天历史 ---")

    def set_translate_mode(self, enabled):
        """设置翻译模式状态"""
        if self.translate_mode != enabled:
            previously_enabled = self.translate_mode
            self.translate_mode = enabled
            print(f"--- 翻译模式已{'启用' if enabled else '禁用'} ---")

            # 更新系统提示词，但保留聊天历史
            system_prompt = self._load_system_prompt()
            with self._lock:
                found_system = False
                for i, msg in enumerate(self.current_history):
                    if msg.get("role") == "system":
                        self.current_history[i]["content"] = system_prompt
                        found_system = True
                        break
                if not found_system:
                    self.current_history.insert(0, {"role": "system", "content": system_prompt})
                print("--- 由于翻译模式更改，已更新系统提示词，但保留聊天历史 ---")

    def is_search_mode_enabled(self):
        """返回搜索模式状态"""
        return self.search_mode

    def is_atri_mode_enabled(self):
        """返回ATRI模式状态"""
        return self.atri_mode

    def is_artifacts_mode_enabled(self):
        """返回Artifacts模式状态"""
        return self.artifacts_mode

    def is_translate_mode_enabled(self):
        """返回翻译模式状态"""
        return self.translate_mode

    def set_custom_atri_prompt(self, custom_prompt):
        """设置用户自定义的ATRI提示词"""
        self.custom_atri_prompt = custom_prompt
        print("--- 已设置用户自定义的 ATRI 提示词 ---")
        # 更新系统提示词
        system_prompt = self._load_system_prompt()
        with self._lock:
            found_system = False
            for i, msg in enumerate(self.current_history):
                if msg.get("role") == "system":
                    self.current_history[i]["content"] = system_prompt
                    found_system = True
                    break
            if not found_system:
                self.current_history.insert(0, {"role": "system", "content": system_prompt})
            print("--- 由于自定义 ATRI 提示词更改，已更新系统提示词，但保留聊天历史 ---")

    def get_custom_atri_prompt(self):
        """获取用户自定义的ATRI提示词，如果没有则返回默认值"""
        return self.custom_atri_prompt if self.custom_atri_prompt else PROMPT_ATRI

    def get_prompt_by_name(self, prompt_name):
        """获取指定名称的提示词内容"""
        return self.custom_prompts.get(prompt_name, "")

    def set_prompt_by_name(self, prompt_name, content):
        """设置指定名称的提示词内容"""
        if prompt_name in self.custom_prompts:
            self.custom_prompts[prompt_name] = content
            print(f"--- 已设置提示词 {prompt_name} ---")
            # 更新系统提示词
            system_prompt = self._load_system_prompt()
            with self._lock:
                found_system = False
                for i, msg in enumerate(self.current_history):
                    if msg.get("role") == "system":
                        self.current_history[i]["content"] = system_prompt
                        found_system = True
                        break
                if not found_system:
                    self.current_history.insert(0, {"role": "system", "content": system_prompt})
                print("--- 由于提示词更改，已更新系统提示词，但保留聊天历史 ---")

    def get_all_prompts(self):
        """获取所有提示词的字典"""
        return self.custom_prompts.copy()