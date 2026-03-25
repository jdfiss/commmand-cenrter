import json
import os
import copy
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DATA = {
    "notes": "",
    "milestones": {},
    "time_debt": {},
    "inbox": [],
    "schedule": {},
    "study_plan": {},
    "habit_defs": ["運動 30min", "讀書自習 2h+", "吃早餐", "睡前複習"],
    "habit_logs": {},
    "fixed_schedule": {},
    "deadlines": [],
    "mood_logs": {},
    "pomodoro_logs": {},
    "health_logs": {}
}

# ── 使用者管理 ────────────────────────────────────────────────

def _users_path():
    return os.path.join(BASE_DIR, 'users.json')

def load_users():
    path = _users_path()
    if not os.path.exists(path):
        users = [{'id': 'default', 'name': '我', 'avatar': '😊'}]
        save_users(users)
        return users
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(_users_path(), 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

# ── 資料讀寫 ──────────────────────────────────────────────────

def _data_path(user_id='default'):
    return os.path.join(BASE_DIR, f'data_{user_id}.json')

def load_data(user_id='default'):
    path = _data_path(user_id)
    if not os.path.exists(path):
        # 自動遷移舊的 data.json 給 default 用戶
        legacy = os.path.join(BASE_DIR, 'data.json')
        if user_id == 'default' and os.path.exists(legacy):
            with open(legacy, 'r', encoding='utf-8') as f:
                data = json.load(f)
            save_data(data, user_id)
            return data
        return copy.deepcopy(DEFAULT_DATA)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data, user_id='default'):
    with open(_data_path(user_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── 壓力計算 ──────────────────────────────────────────────────

def calculate_pressure(data):
    total_debt = sum(data.get("time_debt", {}).values())

    milestones = data.get("milestones", {})
    if not milestones:
        return total_debt, 0.0, "🟢 GREEN (安全：按部就班)"

    exam = list(milestones.values())[0]
    remaining_chapters = exam["total_chapters"] - exam["finished_chapters"]
    remaining_hours = remaining_chapters * exam["hours_per_chapter"]

    deadline_date = datetime.strptime(exam["deadline"], "%Y-%m-%d")
    today = datetime.now()
    days_left = (deadline_date - today).days

    if days_left <= 0:
        return total_debt, float('inf'), "🔴 FATAL (Deadline Passed)"

    daily_pressure = (total_debt + remaining_hours) / (days_left * 0.8)

    if daily_pressure >= 4.0:
        color = "🔴 RED (高壓：必須清債，停止娛樂)"
    elif daily_pressure >= 2.0:
        color = "🟡 YELLOW (警告：進度緊繃)"
    else:
        color = "🟢 GREEN (安全：按部就班)"

    return total_debt, daily_pressure, color

def check_inbox(data):
    inbox_count = len(data.get("inbox", []))
    if inbox_count > 0:
        return f"⚠️ 警告：Inbox 內有 {inbox_count} 筆雜事未歸類！"
    return "✅ Inbox 已清空。"

def print_dashboard():
    data = load_data()
    total_debt, pressure, color_status = calculate_pressure(data)
    print("="*40)
    print(" 🚀 超強計畫儀表板 (Command Center)")
    print("="*40)
    print(check_inbox(data))
    print(f"📊 累積時間債務 : {total_debt:.1f} 小時")
    print(f"🔥 每日最低要求 : {pressure:.2f} 小時/天")
    print(f"🚦 當前系統狀態 : {color_status}")
    print("="*40)

if __name__ == "__main__":
    print_dashboard()
