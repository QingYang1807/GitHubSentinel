import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from datetime import datetime
import ssl
import warnings
from urllib3.exceptions import InsecureRequestWarning
import os
from logger import LOG  # 假设有日志模块
from llm import LLM  # 假设你已经有 LLM 类
from config import Config  # 假设你有配置管理类
from report_generator import ReportGenerator

# 禁用 SSL 警告
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Hugging Face 模型页面 URL
url = "https://huggingface.co/models"

# 创建一个 Session 对象
session = requests.Session()

# 设置重试策略
retry = Retry(
    total=5,  # 最大重试次数
    backoff_factor=1,  # 重试的等待时间
    status_forcelist=[500, 502, 503, 504]  # 只在服务器错误时才重试
)
adapter = HTTPAdapter(max_retries=retry)

# 将适配器应用到 https 请求
session.mount('https://', adapter)

# 创建 SSL 上下文，禁用 SSL 验证（仅用于开发环境）
context = ssl.create_default_context()
context.set_ciphers('DEFAULT@SECLEVEL=1')  # 有时可以调整安全级别来兼容不同的协议

# 发送 GET 请求，禁用 SSL 验证
try:
    response = session.get(url, verify=False)
    response.raise_for_status()  # 确保请求成功
except requests.exceptions.RequestException as e:
    print(f"请求失败: {e}")
    exit(1)

# 解析 HTML 页面
soup = BeautifulSoup(response.text, "html.parser")

# 获取所有模型的链接和名称
models = soup.find_all("article", class_="overview-card-wrapper")

# 获取今天的日期
today_date = datetime.now().date()

# 过滤出当日新增的模型
new_models = []

for model in models:
    try:
        # 获取模型的名称
        model_name = model.find("h4", class_="text-md").text.strip()

        # 获取模型的更新时间
        time_tag = model.find("time")
        if time_tag:
            update_text = time_tag.text.strip()
        else:
            continue  # 跳过没有更新时间的模型

        # 检查文本中是否有“Updated xx days ago”，并判断是否是今天
        days_ago_text = update_text.split("Updated")[-1].strip()
        if "day" in days_ago_text:
            days_ago = int(days_ago_text.split(" ")[0])

            if days_ago == 1:  # 今天更新的模型
                model_url = "https://huggingface.co" + model.find("a")["href"]
                new_models.append({"name": model_name, "url": model_url, "days_ago": days_ago})

    except Exception as e:
        print(f"处理模型时发生错误: {e}")
        continue

# 确保 daily_report 目录存在
report_dir = os.path.join(os.getcwd(), "daily_report")
os.makedirs(report_dir, exist_ok=True)

# 打印今天新增的模型
if new_models:
    print("当日新增的模型：")
    for model in new_models:
        print(f"模型名称: {model['name']}, URL: {model['url']}, 更新天数: {model['days_ago']}天前")

    # 生成报告
    config = Config()  # 加载配置
    llm = LLM(config)  # 初始化 LLM 实例
    report_generator = ReportGenerator(llm, config.report_types)

    # 创建 markdown 内容
    markdown_content = "\n".join([f"### {model['name']}\n- [Link]({model['url']})" for model in new_models])

    # 将 markdown 内容写入 daily_report 目录中的报告文件
    report_file_path = os.path.join(report_dir, f"{today_date}_report.md")
    with open(report_file_path, 'w', encoding='utf-8') as report_file:
        report_file.write(markdown_content)

    LOG.debug(f"报告已保存到: {report_file_path}")

else:
    print("没有发现今天新增的模型。")
