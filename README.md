# Personal Copilot

Personal Copilot 是一个基于 AI 的个人助手应用程序，旨在通过自然语言处理和多种 AI 模型（如 DeepSeek 和 Grok）为用户提供帮助。它支持多种模式，包括搜索、翻译、图像生成和数据可视化等功能。

## 功能特点

- **多模型支持**：支持 DeepSeek 和 Grok 等多种 AI 模型，用户可以根据需求切换。
- **模式切换**：提供搜索模式、ATRI 模式、Artifacts 模式和翻译模式，满足不同场景需求。
- **图像生成**：通过 Grok 模型生成图像，并支持保存到本地。
- **数据可视化**：支持生成图表和表格，并通过浏览器展示。
- **自定义提示词**：用户可以自定义系统提示词，个性化 AI 交互体验。
- **主题切换**：支持明亮和暗黑主题，适应不同用户偏好。

## 安装与使用

### 前提条件

- Python 3.9 或更高版本
- 安装依赖项：`pip install -r requirements.txt`

### 安装步骤

1. 克隆仓库：
   ```
   git clone https://github.com/yahoooooooooh/personal-copilot.git
   cd PersonalCopilot
   ```

2. 创建并激活虚拟环境（可选但推荐）：
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   # 或
   source venv/bin/activate  # Linux/Mac
   ```

3. 安装依赖项：
   ```
   pip install -r requirements.txt
   ```

4. 配置 API 密钥：
   - 创建 `.env` 文件，添加您的 API 密钥：
     ```
     DEEPSEEK_API_KEY=your_deepseek_api_key
     GROK_API_KEY=your_grok_api_key
     TAVILY_API_KEY=your_tavily_api_key
     ```

5. 运行应用程序：
   ```
   python main.py
   ```

### 使用打包版本

如果您不希望手动安装依赖项，可以下载预打包的可执行文件（如果可用）：
- 下载最新版本的 `personal-copilot-v1.0.0.zip`（Windows）。
- 运行可执行文件，配置 API 密钥并开始使用。

## 版本信息

当前版本：**v1.0.0**

查看 [版本历史](#版本历史) 获取更多信息。

## 版本历史

- **v1.0.0** - 2025-04-17
  - 初始公开版本，包含多模型支持（DeepSeek 和 Grok）。
  - 支持搜索、翻译、图像生成和数据可视化功能。
  - 提供自定义提示词和主题切换功能。
  - 支持运行时输入 API 密钥。

## 贡献

欢迎提交问题和拉取请求！请遵循以下步骤：
1. Fork 仓库。
2. 创建您的功能分支（`git checkout -b feature/AmazingFeature`）。
3. 提交您的更改（`git commit -m 'Add some AmazingFeature'`）。
4. 推送到分支（`git push origin feature/AmazingFeature`）。
5. 打开一个拉取请求。

## 许可证

此项目根据 MIT 许可证发布 - 详情请见 [LICENSE.md](LICENSE.md) 文件。

## 联系方式

- 项目链接：https://github.com/yahoooooooooh/personal-copilot
- 电子邮件：yu5764247@gmail.com
