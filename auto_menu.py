#!/usr/bin/env python3
import yaml
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
import os
from datetime import datetime, timedelta
import json
from difflib import SequenceMatcher

# 加载配置
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

DOUBO_API_KEY = config["doubao_api_key"]
PUSH_TIME = config["push_time"]
DIET_PREFERENCE = config["diet_preference"]
# 历史记录文件
HISTORY_FILE = "menu_history.json"
# 相似度阈值，超过这个值就认为重复
SIMILAR_THRESHOLD = 0.6

def load_history():
    """加载历史生成的食谱"""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(menu):
    """保存新生成的食谱到历史"""
    history = load_history()
    history.append({"time": datetime.now().strftime("%Y-%m-%d"), "menu": menu})
    # 只保留最近90天的历史，足够用
    history = history[-90:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def is_duplicate(menu):
    """检查是否和历史重复"""
    history = load_history()
    for item in history:
        similarity = SequenceMatcher(None, menu, item["menu"]).ratio()
        if similarity > SIMILAR_THRESHOLD:
            return True
    return False

def generate_menu():
    """调用豆包API生成第二天的早午饭食谱，重复就重试3次"""
    for _ in range(3):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        # 加随机因子保证每次生成的不一样
        random_seed = f"本次生成加入随机变化，不要和之前的食谱重复，随机选择不同的食材组合：{os.urandom(4).hex()}"
        prompt = f"今天是{datetime.now().strftime('%Y-%m-%d')}，请生成{tomorrow}的早午饭食谱，符合以下要求：{DIET_PREFERENCE}，{random_seed}，直接输出食谱内容，不要多余内容。"
        
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DOUBO_API_KEY}"
        }
        data = {
            "model": "doubao-seed-2.0-pro",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.9 # 调高温度，增加随机性
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=30)
            menu = resp.json()["choices"][0]["message"]["content"]
            if not is_duplicate(menu):
                save_history(menu)
                return f"🍱 明天({tomorrow})的早午饭食谱：\n\n{menu}\n\n💡 提示：早餐在家5分钟搞定，午餐可以带便当或者公司点外卖~"
        except Exception as e:
            print(f"生成失败重试：{str(e)}")
    return "❌ 生成食谱失败，请稍后重试"

def push_message(content):
    """调用OpenClaw消息功能推送给你"""
    try:
        os.system(f'openclaw message action=send message="{content}"')
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 食谱推送成功")
    except Exception as e:
        print(f"推送失败：{str(e)}")

def job():
    """定时任务：生成食谱+推送"""
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始生成明天的食谱...")
    menu = generate_menu()
    push_message(menu)

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    # 每天指定时间执行
    hour, minute = PUSH_TIME.split(":")
    scheduler.add_job(job, 'cron', hour=int(hour), minute=int(minute))
    print(f"自动食谱服务已启动，每天{PUSH_TIME}推送第二天的早午饭食谱...")
    # 启动时先执行一次测试
    job()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
