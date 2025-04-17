# config_manager.py (v1.2 - 支持运行时输入API密钥，支持保存主题偏好)
import os
from pathlib import Path
from dotenv import load_dotenv
from utils import get_data_dir
import logging

# --- 全局变量定义 ---
backend_configs = []  # 只包含 API 配置
missing_keys = {}  # 存储缺失的API密钥，供UI提示用户输入

def build_backend_configs():
    """(仅 API 版本) 从环境变量构建结构化的后端配置列表"""
    global backend_configs, missing_keys
    backend_configs.clear()
    logging.info("--- [扫描配置 (仅 API)] ---")

    deepseek_key_exists = bool(os.getenv("DEEPSEEK_API_KEY"))
    grok_key_exists = bool(os.getenv("GROK_API_KEY"))

    if deepseek_key_exists:
        config = {
            "display_name": "在线 API (DeepSeek)", "type": "API", "provider": "DeepSeek",
            "model_path": None, "config_key": "DEEPSEEK_API_KEY", "model": "deepseek-chat"
        }
        backend_configs.append(config)
        logging.info("--- [扫描] 发现 API 配置: %s", config['display_name'])
    else:
        logging.warning("--- [扫描] 未配置 DEEPSEEK_API_KEY，DeepSeek 选项未添加 ---")
        missing_keys["DEEPSEEK_API_KEY"] = "DeepSeek API Key"

    if grok_key_exists:
        # 添加 Grok-3-beta 模型
        config_grok_3 = {
            "display_name": "在线 API (Grok-3-beta)", "type": "API", "provider": "Grok",
            "model_path": None, "config_key": "GROK_API_KEY", "model": "grok-3-beta"
        }
        backend_configs.append(config_grok_3)
        logging.info("--- [扫描] 发现 API 配置: %s", config_grok_3['display_name'])

        # 添加 Grok-2-image-latest 模型
        config_grok_2_image = {
            "display_name": "在线 API (Grok-2-image-latest)", "type": "API", "provider": "Grok",
            "model_path": None, "config_key": "GROK_API_KEY", "model": "grok-2-image-latest"
        }
        backend_configs.append(config_grok_2_image)
        logging.info("--- [扫描] 发现 API 配置: %s", config_grok_2_image['display_name'])
    else:
        logging.warning("--- [扫描] 未配置 GROK_API_KEY，Grok 选项未添加 ---")
        missing_keys["GROK_API_KEY"] = "Grok API Key"

    if not backend_configs:
        logging.error("!!! [严重错误] 未能构建任何 API 后端配置！请检查 .env 文件或环境变量中的 API Keys。!!!")
        # 添加一个明确的错误状态
        backend_configs.append({"display_name": "无可用 API 配置", "type": "Error", "provider": "None", "model_path": None, "config_key": None, "model": ""})

    # 返回显示名称列表，供设置窗口使用
    return [cfg['display_name'] for cfg in backend_configs]

def load_environment_variables():
    """加载环境变量，并检查缺失的API密钥"""
    global missing_keys
    try:
        env_file_path = get_data_dir() / ".env"
        if env_file_path.exists():
            logging.info("--- 正在加载环境变量: %s ---", env_file_path)
            load_dotenv(dotenv_path=env_file_path, override=True)
            logging.info("--- [Debug] .env 加载后 GROK_API_KEY: ...%s", os.getenv('GROK_API_KEY')[-4:] if os.getenv('GROK_API_KEY') else 'Not Set')
            logging.info("--- [Debug] .env 加载后 TAVILY_API_KEY: %s", 'Set' if os.getenv('TAVILY_API_KEY') else 'Not Set')
        else:
            logging.warning("--- 警告: 未找到环境变量文件 %s ---", env_file_path)
            logging.info("--- [Debug] 未找到 .env 时 GROK_API_KEY: ...%s", os.getenv('GROK_API_KEY')[-4:] if os.getenv('GROK_API_KEY') else 'Not Set')
            logging.info("--- [Debug] 未找到 .env 时 TAVILY_API_KEY: %s", 'Set' if os.getenv('TAVILY_API_KEY') else 'Not Set')
    except Exception as e:
        logging.error("!!! 加载 .env 文件时发生错误: %s !!!", e)
        logging.info("--- [Debug] 加载 .env 出错时 GROK_API_KEY: ...%s", os.getenv('GROK_API_KEY')[-4:] if os.getenv('GROK_API_KEY') else 'Not Set')
        logging.info("--- [Debug] 加载 .env 出错时 TAVILY_API_KEY: %s", 'Set' if os.getenv('TAVILY_API_KEY') else 'Not Set')

    # 检查缺失的API密钥
    if not os.getenv("DEEPSEEK_API_KEY"):
        missing_keys["DEEPSEEK_API_KEY"] = "DeepSeek API Key"
    if not os.getenv("GROK_API_KEY"):
        missing_keys["GROK_API_KEY"] = "Grok API Key"
    if not os.getenv("TAVILY_API_KEY"):
        missing_keys["TAVILY_API_KEY"] = "Tavily API Key"
    if missing_keys:
        logging.warning("缺失的API密钥: %s", ", ".join(missing_keys.values()))

def determine_initial_backend():
    """确定初始默认后端 (优先 Grok-3-beta, 然后 Grok-2-image-latest, 再 DeepSeek)"""
    default_backend_display = "无可用 API 配置"  # 默认错误状态
    initial_backend_found = False

    # 检查 Grok-3-beta 是否可用
    grok_3_config = next((cfg for cfg in backend_configs if cfg['provider'] == 'Grok' and cfg['model'] == 'grok-3-beta'), None)
    if grok_3_config:
        default_backend_display = grok_3_config['display_name']
        initial_backend_found = True
        logging.info("--- 确认初始后端为 (优先 Grok-3-beta): %s ---", default_backend_display)
    else:
        # 如果 Grok-3-beta 不可用，检查 Grok-2-image-latest
        grok_2_image_config = next((cfg for cfg in backend_configs if cfg['provider'] == 'Grok' and cfg['model'] == 'grok-2-image-latest'), None)
        if grok_2_image_config:
            default_backend_display = grok_2_image_config['display_name']
            initial_backend_found = True
            logging.info("--- Grok-3-beta 不可用，使用 Grok-2-image-latest 作为初始后端: %s ---", default_backend_display)
        else:
            # 如果 Grok 模型都不可用，检查 DeepSeek
            deepseek_config = next((cfg for cfg in backend_configs if cfg['provider'] == 'DeepSeek'), None)
            if deepseek_config:
                default_backend_display = deepseek_config['display_name']
                initial_backend_found = True
                logging.info("--- Grok 模型不可用，使用 DeepSeek 作为初始后端: %s ---", default_backend_display)
            else:
                # 如果都没有可用
                logging.error("!!! [错误] 没有可用的 API 后端选项！!!!")
                # default_backend_display 保持 "无可用 API 配置"

    logging.info("--- 最终确定的 *初始* 后端: %s ---", default_backend_display)
    return default_backend_display

def get_config_for_controller():
    """为控制器准备配置字典"""
    return {
        'DEEPSEEK_API_KEY': os.getenv("DEEPSEEK_API_KEY", ""),
        'GROK_API_KEY': os.getenv("GROK_API_KEY", ""),
        'TAVILY_API_KEY': os.getenv("TAVILY_API_KEY", ""),
        'backend_configs': backend_configs,  # 只包含 API 配置
        'initial_backend_display_name': determine_initial_backend(),
        'missing_keys': missing_keys  # 新增：传递缺失的API密钥信息
    }

def update_api_key(key_name, key_value):
    """更新API密钥并保存到环境变量和 .env 文件"""
    os.environ[key_name] = key_value
    try:
        env_file_path = get_data_dir() / ".env"
        with open(env_file_path, 'a' if env_file_path.exists() else 'w', encoding='utf-8') as f:
            f.write(f"{key_name}={key_value}\n")
        logging.info("已更新API密钥 %s 并保存到 .env 文件", key_name)
    except Exception as e:
        logging.error("保存API密钥到 .env 文件时出错: %s", e)
    # 重新构建后端配置
    build_backend_configs()

def save_theme_preference(theme_mode):
    """保存主题偏好到环境变量和 .env 文件"""
    os.environ["THEME_MODE"] = theme_mode
    try:
        env_file_path = get_data_dir() / ".env"
        with open(env_file_path, 'a' if env_file_path.exists() else 'w', encoding='utf-8') as f:
            f.write(f"THEME_MODE={theme_mode}\n")
        logging.info("已保存主题偏好 %s 到 .env 文件", theme_mode)
    except Exception as e:
        logging.error("保存主题偏好到 .env 文件时出错: %s", e)

def load_theme_preference():
    """加载主题偏好"""
    theme_mode = os.getenv("THEME_MODE", "light")  # 默认明亮模式
    logging.info("加载主题偏好: %s", theme_mode)
    return theme_mode