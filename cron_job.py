"""
cron_job.py — 每日午夜執行的換日腳本
功能：
  1. 將昨天未完成的任務，按預估時間換算成小時，累積進 time_debt
  2. 清除昨天的 schedule（今天那筆保留）
  3. 輸出結算報告（所有使用者）

執行方式：
  python cron_job.py

排程方式（Windows 工作排程器 / Linux crontab）：
  Windows: 在「工作排程器」新增每天 00:01 執行此腳本
  Linux:   0 0 * * * /usr/bin/python3 /path/to/cron_job.py
"""

from engine import load_data, save_data, load_users
from datetime import datetime, timedelta


def rollover_user(user_id):
    data = load_data(user_id)
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    added_debt = {}

    if yesterday in data["schedule"]:
        for task in data["schedule"][yesterday]:
            if not task["completed"]:
                hours = round(task["duration"] / 60, 2)
                key   = task["task"]
                data["time_debt"][key] = data["time_debt"].get(key, 0) + hours
                added_debt[key] = hours
        del data["schedule"][yesterday]

    if today not in data["schedule"]:
        data["schedule"][today] = []

    # 清除值為 0 的時間債項目
    data["time_debt"] = {k: v for k, v in data["time_debt"].items() if v > 0}

    save_data(data, user_id)
    return added_debt, sum(data["time_debt"].values())


def rollover():
    users = load_users()
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print("=" * 46)
    print(f"  換日結算完成 — {yesterday}")
    print("=" * 46)

    for user in users:
        uid  = user["id"]
        name = user.get("name", uid)
        added_debt, total = rollover_user(uid)

        print(f"\n  【{name}】")
        if added_debt:
            print("  未完成任務已轉入時間債務池：")
            for task, h in added_debt.items():
                print(f"    + {task}：{h} hrs")
        else:
            print("  昨日任務全數完成，無新增債務。")
        print(f"  當前總債務：{total:.1f} hrs")

    print("=" * 46)


if __name__ == "__main__":
    rollover()
