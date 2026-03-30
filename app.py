import os
from flask import Flask, render_template, request, jsonify, session
from engine import load_data, save_data, calculate_pressure, load_users, save_users
from datetime import datetime, timedelta
import re, time as _time, copy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'cmd-center-dev-secret-2024'
if app.secret_key == 'cmd-center-dev-secret-2024':
    import warnings
    warnings.warn("SECRET_KEY 使用預設值，請在 production 設定環境變數 SECRET_KEY", stacklevel=2)

def uid():
    return session.get('user_id', 'default')

def current_user_info():
    users = load_users()
    u = next((u for u in users if u['id'] == uid()), None)
    return u or {'id': 'default', 'name': '我', 'avatar': '😊'}

@app.route('/')
def dashboard():
    data = load_data(uid())
    total_debt, pressure, color_status = calculate_pressure(data)

    today_obj = datetime.now()
    current_date = today_obj.strftime("%Y-%m-%d")

    # 所有里程碑
    milestones_display = {}
    days_left = 365
    for key, ml in data.get("milestones", {}).items():
        try:
            ml_date = datetime.strptime(ml["deadline"], "%Y-%m-%d")
        except (ValueError, KeyError):
            continue
        ml_days = (ml_date - today_obj).days
        total = ml.get("total_chapters", 1)
        finished = ml.get("finished_chapters", 0)
        ml_pct = round(finished / total * 100) if total > 0 else 0
        milestones_display[key] = {**ml, "days_left": ml_days, "pct": ml_pct}
        if key == "cs_grad_exam":
            days_left = ml_days

    today_schedule = data["schedule"].get(current_date, [])

    if pressure >= 4.0:
        alert_bg, dot_color = "bg-red-900/40 border-red-500/50 text-red-400", "bg-red-500"
    elif pressure >= 2.0:
        alert_bg, dot_color = "bg-yellow-900/40 border-yellow-500/50 text-yellow-400", "bg-yellow-500"
    else:
        alert_bg, dot_color = "bg-green-900/40 border-green-500/50 text-green-400", "bg-green-500"

    deadlines_with_days = []
    for dl in data.get("deadlines", []):
        try:
            dl_date = datetime.strptime(dl["date"], "%Y-%m-%d")
        except (ValueError, KeyError):
            continue
        dl_days = (dl_date - today_obj).days
        deadlines_with_days.append({**dl, "days_left": dl_days})

    study_plan_pct = {}
    for subject, progress in data.get("study_plan", {}).items():
        pct = round(progress["finished"] / progress["total"] * 100) if progress["total"] > 0 else 0
        remaining = progress["total"] - progress["finished"]
        est_finish = "已完成 ✓" if remaining <= 0 else (
            today_obj + timedelta(days=int(remaining * 3 / 2))).strftime("%Y-%m-%d")
        study_plan_pct[subject] = {**progress, "pct": pct, "est_finish": est_finish}

    habit_defs   = data.get("habit_defs", [])
    habit_today  = data.get("habit_logs", {}).get(current_date, [])
    habit_logs_all = data.get("habit_logs", {})
    habit_streaks  = {}
    for habit in habit_defs:
        streak = 0
        for offset in range(1, 366):
            ds = (today_obj - timedelta(days=offset)).strftime("%Y-%m-%d")
            if habit in habit_logs_all.get(ds, []):
                streak += 1
            else:
                break
        habit_streaks[habit] = streak

    suggestions = []
    upcoming_dls = []
    for dl in data.get("deadlines", []):
        try:
            d = datetime.strptime(dl["date"], "%Y-%m-%d")
            diff = (d - today_obj).days
            if 0 <= diff <= 30:
                upcoming_dls.append((dl, diff))
        except (ValueError, KeyError):
            continue
    upcoming_dls.sort(key=lambda x: x[1])
    if upcoming_dls:
        dl, dl_days = upcoming_dls[0]
        color = "red" if dl_days <= 3 else "yellow" if dl_days <= 7 else "blue"
        suggestions.append({"icon": "⚑", "label": dl["name"],
                             "detail": f"還剩 {dl_days} 天 · {dl.get('note', '')}", "color": color})
    debt_items = sorted([(k, v) for k, v in data.get("time_debt", {}).items() if v > 0], key=lambda x: -x[1])
    if debt_items:
        k, v = debt_items[0]
        suggestions.append({"icon": "⏳", "label": k, "detail": f"積欠 {v}h 待補", "color": "orange"})
    study_behind = [(s, p) for s, p in data.get("study_plan", {}).items() if p["total"] > p["finished"]]
    if study_behind:
        worst = min(study_behind, key=lambda x: x[1]["finished"] / max(x[1]["total"], 1))
        sn, sp = worst
        pct_done = round(sp["finished"] / sp["total"] * 100)
        suggestions.append({"icon": "📖", "label": sn,
                             "detail": f"完成 {pct_done}% · 剩 {sp['total'] - sp['finished']} 章", "color": "cyan"})

    fixed_schedule = data.get("fixed_schedule", {})
    js_dow = str((today_obj.weekday() + 1) % 7)
    fixed_today = fixed_schedule.get(js_dow, [])
    current_time = today_obj.strftime("%H:%M")

    dow_names = ['日','一','二','三','四','五','六']
    today_dow = dow_names[(today_obj.weekday() + 1) % 7]


    # 番茄鐘
    pomodoro_logs = data.get('pomodoro_logs', {})
    pomodoro_today = pomodoro_logs.get(current_date, 0)
    pomodoro_week  = sum(pomodoro_logs.get(
        (today_obj - timedelta(days=i)).strftime('%Y-%m-%d'), 0) for i in range(7))



    # 週報 (7天)
    week_stats = []
    for i in range(6, -1, -1):
        d = (today_obj - timedelta(days=i)).strftime('%Y-%m-%d')
        sched  = data['schedule'].get(d, [])
        h_done = len(data.get('habit_logs', {}).get(d, []))
        pomo   = pomodoro_logs.get(d, 0)
        week_stats.append({
            'date': d,
            'task_done': sum(1 for t in sched if t.get('completed')),
            'task_total': len(sched),
            'habit_done': h_done,
            'habit_total': len(habit_defs),
            'pomo': pomo
        })

    # 讀書建議 (最落後科目)
    subjects_behind = [(s, p) for s, p in data.get('study_plan', {}).items()
                       if p['total'] > p['finished']]
    study_worst = min(subjects_behind, key=lambda x: x[1]['finished']/max(x[1]['total'],1))[0] \
                  if subjects_behind else None

    return render_template('index.html',
                           data=data, total_debt=total_debt, pressure=pressure,
                           status_msg=color_status, alert_bg=alert_bg, dot_color=dot_color,
                           current_date=current_date, days_left=days_left,
                           today_schedule=today_schedule, today_dow=today_dow,
                           deadlines=deadlines_with_days, study_plan=study_plan_pct,
                           fixed_schedule=fixed_schedule, fixed_today=fixed_today,
                           current_time=current_time, milestones=milestones_display,
                           habit_defs=habit_defs, habit_today=habit_today,
                           habit_streaks=habit_streaks, suggestions=suggestions,

                           pomodoro_today=pomodoro_today, pomodoro_week=pomodoro_week,
                           week_stats=week_stats,
                           study_worst=study_worst,
                           users=load_users(), current_user=current_user_info())

# ── 使用者管理 ────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify(load_users())

@app.route('/api/users', methods=['POST'])
def create_user():
    req  = request.json
    name = req.get('name', '').strip()
    avatar = req.get('avatar', '👤')
    if not name:
        return jsonify({'status': 'error'}), 400
    users = load_users()
    user_id = re.sub(r'[^a-z0-9]', '', name.lower()) or f'user{int(_time.time())}'
    existing_ids = {u['id'] for u in users}
    if user_id in existing_ids:
        user_id = f'{user_id}{int(_time.time()) % 1000}'
    users.append({'id': user_id, 'name': name, 'avatar': avatar})
    save_users(users)
    save_data(copy.deepcopy({
        "notes": "", "milestones": {}, "time_debt": {}, "inbox": [],
        "schedule": {}, "study_plan": {},
        "habit_defs": ["運動 30min", "讀書自習 2h+", "吃早餐", "睡前複習"],
        "habit_logs": {}, "fixed_schedule": {}, "deadlines": []
    }), user_id)
    return jsonify({'status': 'success', 'id': user_id, 'name': name, 'avatar': avatar})

@app.route('/api/switch_user', methods=['POST'])
def switch_user():
    user_id = request.json.get('user_id', 'default')
    users = load_users()
    if any(u['id'] == user_id for u in users):
        session['user_id'] = user_id
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    user_id = request.json.get('user_id')
    if user_id == 'default':
        return jsonify({'status': 'error', 'msg': '無法刪除預設使用者'}), 400
    users = load_users()
    save_users([u for u in users if u['id'] != user_id])
    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'data_{user_id}.json')
    if os.path.exists(data_file):
        os.remove(data_file)
    if session.get('user_id') == user_id:
        session['user_id'] = 'default'
    return jsonify({'status': 'success'})

# ── 任務 API ──────────────────────────────────────────────────

@app.route('/api/toggle', methods=['POST'])
def toggle_task():
    req = request.json
    date, index = req.get('date'), req.get('index')
    data = load_data(uid())
    if date in data["schedule"] and index < len(data["schedule"][date]):
        data["schedule"][date][index]["completed"] = not data["schedule"][date][index]["completed"]
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/edit_task', methods=['POST'])
def edit_task():
    req   = request.json
    date  = req.get('date')
    index = req.get('index')
    data  = load_data(uid())
    if date in data["schedule"] and 0 <= index < len(data["schedule"][date]):
        t = data["schedule"][date][index]
        if req.get('task'):     t['task']     = req['task']
        if req.get('time'):     t['time']     = req['time']
        if req.get('duration'): t['duration'] = int(req['duration'])
        if req.get('color') is not None: t['color'] = req['color']
        data["schedule"][date].sort(key=lambda x: x["time"])
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/add_task', methods=['POST'])
def add_task():
    req = request.json
    date, task_name = req.get('date'), req.get('task', '').strip()
    if not date or not task_name:
        return jsonify({"status": "error"}), 400
    data = load_data(uid())
    data["schedule"].setdefault(date, [])
    entry = {"time": req.get('time', '09:00'), "task": task_name,
             "duration": int(req.get('duration', 60)), "completed": False}
    if req.get('color'):
        entry["color"] = req['color']
    data["schedule"][date].append(entry)
    data["schedule"][date].sort(key=lambda x: x["time"])
    save_data(data, uid())
    return jsonify({"status": "success"})

@app.route('/api/delete_task', methods=['POST'])
def delete_task():
    req = request.json
    date, index = req.get('date'), req.get('index')
    data = load_data(uid())
    if date in data["schedule"] and 0 <= index < len(data["schedule"][date]):
        data["schedule"][date].pop(index)
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# ── 雜記 & Inbox ─────────────────────────────────────────────

@app.route('/api/save_notes', methods=['POST'])
def save_notes():
    data = load_data(uid())
    data["notes"] = request.json.get('content', '')
    save_data(data, uid())
    return jsonify({"status": "success"})

@app.route('/api/add_inbox', methods=['POST'])
def add_inbox():
    item = request.json.get('item', '').strip()
    if not item:
        return jsonify({"status": "error"}), 400
    data = load_data(uid())
    data.setdefault("inbox", []).append(item)
    save_data(data, uid())
    return jsonify({"status": "success"})

@app.route('/api/triage', methods=['POST'])
def triage_item():
    req    = request.json
    item_name = req.get('item')
    action    = req.get('action')
    if action not in ('debt', 'delete'):
        return jsonify({"status": "error", "msg": "invalid action"}), 400
    data = load_data(uid())
    if item_name in data["inbox"]:
        data["inbox"].remove(item_name)
        if action == 'debt':
            try:
                hours = float(req.get('hours', 1.0))
            except (ValueError, TypeError):
                hours = 1.0
            hours = max(0.1, hours)  # 不允許負數或零
            data["time_debt"][item_name] = data["time_debt"].get(item_name, 0) + hours
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/inbox_to_task', methods=['POST'])
def inbox_to_task():
    """Atomic: 從 inbox 移除並加入排程（避免兩步操作中間斷線造成資料遺失）"""
    req       = request.json
    item_name = req.get('item', '').strip()
    date      = req.get('date', '')
    if not item_name or not date:
        return jsonify({"status": "error"}), 400
    data = load_data(uid())
    if item_name not in data.get("inbox", []):
        return jsonify({"status": "error", "msg": "item not in inbox"}), 400
    entry = {
        "time":      req.get('time', '09:00'),
        "task":      item_name,
        "duration":  max(5, int(req.get('duration', 60))),
        "completed": False
    }
    data["inbox"].remove(item_name)
    data["schedule"].setdefault(date, []).append(entry)
    data["schedule"][date].sort(key=lambda x: x["time"])
    save_data(data, uid())
    return jsonify({"status": "success"})

@app.route('/api/inbox_to_deadline', methods=['POST'])
def inbox_to_deadline():
    """Atomic: 從 inbox 移除並加入截止日"""
    req       = request.json
    item_name = req.get('item', '').strip()
    date_str  = req.get('date', '')
    if not item_name or not date_str:
        return jsonify({"status": "error"}), 400
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"status": "error", "msg": "invalid date"}), 400
    data = load_data(uid())
    if item_name not in data.get("inbox", []):
        return jsonify({"status": "error", "msg": "item not in inbox"}), 400
    data["inbox"].remove(item_name)
    data.setdefault("deadlines", []).append({
        "name": item_name, "date": date_str, "note": req.get('note', '')
    })
    save_data(data, uid())
    return jsonify({"status": "success"})

# ── Deadline API ──────────────────────────────────────────────

@app.route('/api/edit_deadline', methods=['POST'])
def edit_deadline():
    req   = request.json
    index = req.get('index')
    data  = load_data(uid())
    dls   = data.get("deadlines", [])
    if 0 <= index < len(dls):
        if req.get('name'): dls[index]['name'] = req['name']
        if req.get('date'): dls[index]['date'] = req['date']
        if req.get('note') is not None: dls[index]['note'] = req['note']
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/delete_deadline', methods=['POST'])
def delete_deadline():
    index = request.json.get('index')
    data  = load_data(uid())
    dls   = data.get("deadlines", [])
    if 0 <= index < len(dls):
        dls.pop(index)
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# ── Debt API ──────────────────────────────────────────────────

@app.route('/api/delete_debt', methods=['POST'])
def delete_debt():
    key  = request.json.get('key')
    data = load_data(uid())
    if key in data.get("time_debt", {}):
        del data["time_debt"][key]
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# ── Study Plan API ────────────────────────────────────────────

@app.route('/api/update_study', methods=['POST'])
def update_study():
    req = request.json
    subject, delta = req.get('subject'), int(req.get('delta', 0))
    data = load_data(uid())
    if subject in data.get("study_plan", {}):
        prog = data["study_plan"][subject]
        prog["finished"] = max(0, min(prog["finished"] + delta, prog["total"]))
        save_data(data, uid())
        return jsonify({"status": "success", "finished": prog["finished"]})
    return jsonify({"status": "error"}), 400

@app.route('/api/delete_subject', methods=['POST'])
def delete_subject():
    name = request.json.get('name')
    data = load_data(uid())
    if name in data.get('study_plan', {}):
        del data['study_plan'][name]
        save_data(data, uid())
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

@app.route('/api/add_subject', methods=['POST'])
def add_subject():
    req = request.json
    name, total = req.get('name', '').strip(), int(req.get('total', 10))
    if not name:
        return jsonify({"status": "error"}), 400
    data = load_data(uid())
    data.setdefault("study_plan", {})[name] = {"finished": 0, "total": total}
    save_data(data, uid())
    return jsonify({"status": "success"})

@app.route('/api/update_study_notes', methods=['POST'])
def update_study_notes():
    req = request.json
    subject, notes = req.get('subject'), req.get('notes', '')
    data = load_data(uid())
    if subject in data.get("study_plan", {}):
        data["study_plan"][subject]["notes"] = notes
        save_data(data, uid())
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/schedule_study', methods=['POST'])
def schedule_study():
    req = request.json
    date, subject = req.get('date'), req.get('subject', '').strip()
    chapter = req.get('chapter', '').strip()
    if not date or not subject:
        return jsonify({"status": "error"}), 400
    task_name = f"{subject} {chapter}".strip() if chapter else subject
    data = load_data(uid())
    data["schedule"].setdefault(date, []).append({
        "time": req.get('time', '09:00'), "task": task_name,
        "duration": int(req.get('duration', 120)), "completed": False
    })
    data["schedule"][date].sort(key=lambda x: x["time"])
    save_data(data, uid())
    return jsonify({"status": "success"})

# ── 習慣 API ──────────────────────────────────────────────────

@app.route('/api/toggle_habit', methods=['POST'])
def toggle_habit():
    req = request.json
    date, habit = req.get('date'), req.get('habit')
    data = load_data(uid())
    day  = data.setdefault("habit_logs", {}).setdefault(date, [])
    if habit in day:
        day.remove(habit)
    else:
        day.append(habit)
    save_data(data, uid())
    return jsonify({"status": "success", "done": habit in day})

# ── 心情 / 番茄鐘 / 健康 API ──────────────────────────────────

@app.route('/api/save_mood', methods=['POST'])
def save_mood():
    req  = request.json
    date = req.get('date', datetime.now().strftime('%Y-%m-%d'))
    data = load_data(uid())
    data.setdefault('mood_logs', {})[date] = {
        'emoji': req.get('emoji', ''),
        'note':  req.get('note', '')
    }
    save_data(data, uid())
    return jsonify({'status': 'success'})

@app.route('/api/add_pomodoro', methods=['POST'])
def add_pomodoro():
    date = request.json.get('date', datetime.now().strftime('%Y-%m-%d'))
    data = load_data(uid())
    logs = data.setdefault('pomodoro_logs', {})
    logs[date] = logs.get(date, 0) + 1
    save_data(data, uid())
    return jsonify({'status': 'success', 'count': logs[date]})

@app.route('/api/save_health', methods=['POST'])
def save_health():
    req   = request.json
    date  = req.get('date', datetime.now().strftime('%Y-%m-%d'))
    field = req.get('field')
    value = float(req.get('value', 0))
    data  = load_data(uid())
    day   = data.setdefault('health_logs', {}).setdefault(date, {'water': 0, 'sleep': 0})
    day[field] = max(0, value)
    save_data(data, uid())
    return jsonify({'status': 'success', 'value': day[field]})

@app.route('/api/add_deadline', methods=['POST'])
def add_deadline():
    req      = request.json
    name     = req.get('name', '').strip()
    date_str = req.get('date', '')
    if not name or not date_str:
        return jsonify({'status': 'error'}), 400
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({'status': 'error', 'msg': 'invalid date'}), 400
    data = load_data(uid())
    data.setdefault('deadlines', []).append({
        'name': name, 'date': date_str, 'note': req.get('note', '')
    })
    save_data(data, uid())
    return jsonify({'status': 'success'})

@app.route('/api/edit_milestone', methods=['POST'])
def edit_milestone():
    req  = request.json
    key  = req.get('key')
    data = load_data(uid())
    if key not in data.get('milestones', {}):
        return jsonify({'status': 'error'}), 400
    ml = data['milestones'][key]
    if req.get('name')     is not None: ml['name'] = req['name']
    if req.get('deadline') is not None:
        try:
            datetime.strptime(req['deadline'], "%Y-%m-%d")
            ml['deadline'] = req['deadline']
        except ValueError:
            return jsonify({'status': 'error', 'msg': 'invalid date'}), 400
    if req.get('total_chapters')    is not None: ml['total_chapters']    = int(req['total_chapters'])
    if req.get('finished_chapters') is not None: ml['finished_chapters'] = int(req['finished_chapters'])
    if req.get('hours_per_chapter') is not None: ml['hours_per_chapter'] = float(req['hours_per_chapter'])
    save_data(data, uid())
    return jsonify({'status': 'success'})

@app.route('/api/move_task', methods=['POST'])
def move_task():
    req       = request.json
    date      = req.get('date')
    idx       = req.get('index')
    direction = req.get('direction')
    data  = load_data(uid())
    tasks = data['schedule'].get(date, [])
    new_idx = idx + (1 if direction == 'down' else -1)
    if 0 <= idx < len(tasks) and 0 <= new_idx < len(tasks):
        tasks[idx], tasks[new_idx] = tasks[new_idx], tasks[idx]
        save_data(data, uid())
    return jsonify({'status': 'success'})

@app.route('/api/save_fixed_schedule', methods=['POST'])
def save_fixed_schedule():
    fs = request.json.get('fixed_schedule', {})
    data = load_data(uid())
    data['fixed_schedule'] = fs
    save_data(data, uid())
    return jsonify({'status': 'success'})

@app.route('/api/update_chapter_names', methods=['POST'])
def update_chapter_names():
    subject = request.json.get('subject')
    names   = request.json.get('names', [])
    data = load_data(uid())
    if subject in data.get('study_plan', {}):
        data['study_plan'][subject]['chapter_names'] = names
        save_data(data, uid())
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
