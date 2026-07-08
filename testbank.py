# -*- coding: utf-8 -*-
"""
教学练习小程序 - 完整版（用户系统 + 班级/年份筛选 + 统计）
功能：
- 用户注册/登录（含班级、入学年份）
- 答题记录入库（含知识点字段）
- 教师看板：按班级、年份筛选高频错题和知识点正确率
- 错题重练（基于本地错题本）
题库：chapter*.json（需包含 id 字段）
"""

import streamlit as st
import random
import json
import os
import glob
import bcrypt
from supabase import create_client
import datetime
import time

# ---------- 配置 ----------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ 缺少 Supabase 凭证，请在 Railway 中设置环境变量 SUPABASE_URL 和 SUPABASE_KEY")
    st.stop()

ADMIN_PASSWORD = "admin123"  # 教师看板密码，可修改

# ---------- 初始化 Supabase ----------
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ---------- 数据库辅助函数 ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username: str, password: str, class_name: str, study_year: int) -> tuple[bool, str]:
    """注册用户，返回 (成功标志, 消息)"""
    if len(username) < 3:
        return False, "用户名至少3个字符"
    if len(password) < 6:
        return False, "密码至少6个字符"
    if not class_name:
        return False, "班级不能为空"
    if not study_year:
        return False, "入学年份不能为空"

    # 检查用户名是否已存在
    resp = supabase.table('users').select('id').eq('username', username).execute()
    if resp.data:
        return False, "用户名已被占用"

    hashed = hash_password(password)
    try:
        resp = supabase.table('users').insert({
            'username': username,
            'password_hash': hashed,
            'class_name': class_name,
            'study_year': study_year
        }).execute()
        if resp.data:
            # 更新总用户数统计（参数名 p_key 与数据库函数匹配）
            supabase.rpc('increment_site_stats', {'stat_key': 'total_users'}).execute()
            return True, "注册成功，请登录"
        else:
            return False, "注册失败，请重试"
    except Exception as e:
        return False, f"注册异常: {str(e)}"

def login_user(username: str, password: str) -> tuple[bool, str, dict]:
    resp = supabase.table('users').select('*').eq('username', username).execute()
    if not resp.data:
        return False, "用户名不存在", {}
    user = resp.data[0]
    if verify_password(password, user['password_hash']):
        # 更新最后登录时间
        supabase.table('users').update({
            'last_login': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).eq('id', user['id']).execute()
        return True, "登录成功", user
    else:
        return False, "密码错误", {}

def record_practice(user_id: str, question_id: int, is_correct: bool, knowledge_point: str, time_spent: int = None):
    """记录一次练习"""
    try:
        data = {
            'user_id': user_id,
            'question_id': question_id,
            'is_correct': is_correct,
            'answered_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'knowledge_point': knowledge_point
        }
        if time_spent:
            data['time_spent'] = time_spent
        supabase.table('practice_logs').insert(data).execute()

        # 更新题目统计
        resp = supabase.table('question_stats').select('*').eq('question_id', question_id).execute()
        if resp.data:
            stats = resp.data[0]
            new_total = stats['total_attempts'] + 1
            new_wrong = stats['wrong_attempts'] + (0 if is_correct else 1)
            supabase.table('question_stats').update({
                'total_attempts': new_total,
                'wrong_attempts': new_wrong,
                'last_updated': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).eq('question_id', question_id).execute()
        else:
            supabase.table('question_stats').insert({
                'question_id': question_id,
                'total_attempts': 1,
                'wrong_attempts': 0 if is_correct else 1,
                'last_updated': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()

        # 更新用户知识点掌握度
        resp = supabase.table('user_progress').select('*').eq('user_id', user_id).eq('knowledge_point', knowledge_point).execute()
        if resp.data:
            prog = resp.data[0]
            total = prog['total_attempts'] + 1
            correct = prog['correct_rate'] * prog['total_attempts'] + (1 if is_correct else 0)
            new_rate = correct / total
            supabase.table('user_progress').update({
                'total_attempts': total,
                'correct_rate': new_rate,
                'last_practiced': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).eq('id', prog['id']).execute()
        else:
            supabase.table('user_progress').insert({
                'user_id': user_id,
                'knowledge_point': knowledge_point,
                'correct_rate': 1.0 if is_correct else 0.0,
                'total_attempts': 1,
                'last_practiced': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()
    except Exception as e:
        st.error(f"记录数据失败: {str(e)}")

def get_site_stats():
    try:
        resp = supabase.table('site_stats').select('stat_value').eq('stat_key', 'total_users').execute()
        if resp.data:
            return resp.data[0]['stat_value']
        return 0
    except:
        return 0

# 新版统计函数（调用数据库函数）
def get_top_wrong_questions_filtered(class_name=None, study_year=None, limit=10):
    try:
        result = supabase.rpc('get_top_wrong_questions', {
            'p_class_name': class_name,
            'p_study_year': study_year,
            'p_limit': limit
        }).execute()
        return result.data
    except Exception as e:
        st.error(f"获取高频错题失败: {e}")
        return []

def get_knowledge_accuracy_filtered(class_name=None, study_year=None):
    try:
        result = supabase.rpc('get_knowledge_accuracy', {
            'p_class_name': class_name,
            'p_study_year': study_year
        }).execute()
        return result.data
    except Exception as e:
        st.error(f"获取知识点正确率失败: {e}")
        return []

# ---------- 题库加载 ----------
@st.cache_data(ttl=600)
def load_questions():
    base_dir = os.path.dirname(__file__)
    pattern = os.path.join(base_dir, "chapter*.json")
    file_list = glob.glob(pattern)
    all_questions = []
    if not file_list:
        st.error("❌ 未找到任何 chapter*.json 文件")
        return []

    for file_path in sorted(file_list):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    st.warning(f"⚠️ {file_path} 不是数组格式，跳过")
                    continue
                for q in data:
                    if 'id' not in q:
                        st.error(f"❌ 题目缺少 'id' 字段：{q.get('question', '未知')[:30]}...")
                        continue
                    if any(existing['id'] == q['id'] for existing in all_questions):
                        st.error(f"❌ 题目 ID 重复：{q['id']}，请修正")
                        continue
                    all_questions.append(q)
        except Exception as e:
            st.error(f"读取 {file_path} 失败：{e}")
    st.success(f"✅ 成功加载 {len(all_questions)} 道题目")
    return all_questions

QUESTION_BANK = load_questions()

# ---------- 辅助函数 ----------
def filter_questions(chapter=None, knowledge=None):
    if not QUESTION_BANK:
        return []
    filtered = QUESTION_BANK
    if chapter and chapter != "全部":
        filtered = [q for q in filtered if q["chapter"] == chapter]
    if knowledge and knowledge != "全部" and knowledge is not None:
        filtered = [q for q in filtered if q["knowledge"] == knowledge]
    return filtered

def get_available_knowledge(chapter=None):
    if not QUESTION_BANK:
        return []
    if chapter is None or chapter == "全部":
        knowledges = sorted(set(q["knowledge"] for q in QUESTION_BANK))
    else:
        knowledges = sorted(set(q["knowledge"] for q in QUESTION_BANK if q["chapter"] == chapter))
    return ["全部"] + knowledges

def pick_questions(chapter, knowledge, count=None):
    pool = filter_questions(chapter, knowledge)
    if not pool:
        return []
    if count is None:
        shuffled = pool[:]
        random.shuffle(shuffled)
        return shuffled
    else:
        if len(pool) <= count:
            return pool[:]
        return random.sample(pool, count)

def init_session_state():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0
    if "wrong_list" not in st.session_state:
        st.session_state.wrong_list = []
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
    if "feedback" not in st.session_state:
        st.session_state.feedback = None
    if "quiz_finished" not in st.session_state:
        st.session_state.quiz_finished = False
    if "user_answer" not in st.session_state:
        st.session_state.user_answer = None
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "show_dashboard" not in st.session_state:
        st.session_state.show_dashboard = False

# ---------- 主页面 ----------
st.set_page_config(page_title="智能练习 · 教学平台", page_icon="📚", layout="centered")
st.title("📖 智能练习 · 教学平台")

init_session_state()

# ---------- 侧边栏（顺序：登录/欢迎 → 练习控制 → 统计 → 教师看板）----------
with st.sidebar:
    # 1. 用户信息（登录/注册/欢迎）
    if st.session_state.user:
        st.write(f"👤 欢迎，**{st.session_state.user['username']}**")
        st.caption(f"班级：{st.session_state.user.get('class_name', '未设置')}  |  年份：{st.session_state.user.get('study_year', '未设置')}")
        if st.button("🚪 退出登录"):
            st.session_state.user = None
            st.session_state.questions = []
            st.session_state.wrong_list = []
            st.rerun()
    else:
        st.subheader("🔐 登录 / 注册")
        tab1, tab2 = st.tabs(["登录", "注册"])
        with tab1:
            with st.form("login_form"):
                login_username = st.text_input("用户名")
                login_password = st.text_input("密码", type="password")
                login_submit = st.form_submit_button("登录")
                if login_submit:
                    if login_username and login_password:
                        ok, msg, user = login_user(login_username, login_password)
                        if ok:
                            st.session_state.user = user
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("请填写完整")
        with tab2:
            with st.form("register_form"):
                reg_username = st.text_input("用户名 (至少3字符)")
                reg_password = st.text_input("密码 (至少6字符)", type="password")
                reg_class = st.text_input("班级 (如：2023级1班)")
                reg_year = st.number_input("入学年份", min_value=2000, max_value=2100, step=1, value=2026)
                reg_submit = st.form_submit_button("注册")
                if reg_submit:
                    if reg_username and reg_password and reg_class and reg_year:
                        ok, msg = register_user(reg_username, reg_password, reg_class, int(reg_year))
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("请填写完整信息")

    # 2. 练习控制
    st.markdown("---")
    st.subheader("🎯 练习控制")
    chapters = ["全部"] + sorted(set(q["chapter"] for q in QUESTION_BANK))
    selected_chapter = st.selectbox("选择章节", chapters, key="chapter_select")
    knowledge_options = get_available_knowledge(selected_chapter if selected_chapter != "全部" else None)
    selected_knowledge = st.selectbox("选择知识点", knowledge_options, key="knowledge_select")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 开始练习", use_container_width=True):
            kw = None if selected_knowledge == "全部" else selected_knowledge
            new_questions = pick_questions(selected_chapter, kw, count=None)
            if not new_questions:
                st.sidebar.warning("当前选择下没有题目")
            else:
                st.session_state.questions = new_questions
                st.session_state.current_idx = 0
                st.session_state.user_answer = None
                st.session_state.submitted = False
                st.session_state.feedback = None
                st.session_state.quiz_finished = False
                st.session_state.start_time = time.time()
                st.rerun()
    with col2:
        if st.button("📕 错题重练", use_container_width=True):
            if not st.session_state.wrong_list:
                st.sidebar.info("错题本为空")
            else:
                wrong_knowledges = set(q["knowledge"] for q in st.session_state.wrong_list)
                new_questions = []
                for kw in wrong_knowledges:
                    pool = filter_questions(knowledge=kw)
                    if pool:
                        sample_size = min(2, len(pool))
                        new_questions.extend(random.sample(pool, sample_size))
                if not new_questions:
                    st.sidebar.warning("找不到对应知识点的题目")
                else:
                    random.shuffle(new_questions)
                    st.session_state.questions = new_questions
                    st.session_state.current_idx = 0
                    st.session_state.user_answer = None
                    st.session_state.submitted = False
                    st.session_state.feedback = None
                    st.session_state.quiz_finished = False
                    st.session_state.start_time = time.time()
                    st.rerun()

    # 3. 统计与错题本
    st.markdown("---")
    st.subheader("📊 统计")
    if st.session_state.user:
        st.write(f"总注册用户: {get_site_stats()}")
        st.write(f"我的错题数: {len(st.session_state.wrong_list)}")
    with st.expander("📋 错题本", expanded=False):
        if not st.session_state.wrong_list:
            st.info("暂无错题，继续加油！")
        else:
            for i, wrong_q in enumerate(st.session_state.wrong_list):
                with st.expander(f"错题 {i+1}: {wrong_q['question'][:30]}..."):
                    st.write(f"**章节**: {wrong_q['chapter']}  |  **知识点**: {wrong_q['knowledge']}")
                    if wrong_q["type"] == "fill":
                        user_ans = wrong_q.get("user_answer", "未作答")
                        st.write(f"**你的答案**: {user_ans}")
                    else:
                        user_idx = wrong_q.get("user_answer")
                        if user_idx is not None and isinstance(user_idx, int):
                            st.write(f"**你的选择**: {wrong_q['options'][user_idx]}")
                        else:
                            st.write("**你的选择**: 未作答")
                    if wrong_q["type"] == "fill":
                        st.write(f"**正确答案**: {wrong_q['answer']}")
                    else:
                        st.write(f"**正确答案**: {wrong_q['options'][wrong_q['answer']]}")
                    if wrong_q.get("explanation"):
                        st.info(f"💡 解析: {wrong_q['explanation']}")

    # 4. 教师看板（放在最下方）
    st.markdown("---")
    with st.expander("🔐 教师看板 (需密码)"):
        admin_pw = st.text_input("管理员密码", type="password", key="admin_pw_input")
        if st.button("查看看板"):
            if admin_pw == ADMIN_PASSWORD:
                st.session_state.show_dashboard = True
            else:
                st.error("密码错误")
    if st.session_state.get("show_dashboard", False):
        st.success("已解锁看板")
        if st.button("关闭看板"):
            st.session_state.show_dashboard = False
            st.rerun()

# ---------- 教师看板页面 ----------
if st.session_state.get("show_dashboard", False):
    st.header("📊 教师看板")
    with st.spinner("加载数据..."):
        # 获取所有班级和年份（用于筛选）
        try:
            classes_resp = supabase.table('users').select('class_name').execute()
            classes = sorted(set([row['class_name'] for row in classes_resp.data if row['class_name']]))
            years_resp = supabase.table('users').select('study_year').execute()
            years = sorted(set([row['study_year'] for row in years_resp.data if row['study_year']]), reverse=True)
        except Exception as e:
            classes = []
            years = []
            st.error(f"获取筛选选项失败: {e}")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_class = st.selectbox("选择班级", ["全部"] + classes, key="class_filter")
        with col_f2:
            selected_year = st.selectbox("选择年份", ["全部"] + [str(y) for y in years], key="year_filter")

        class_filter = None if selected_class == "全部" else selected_class
        year_filter = None if selected_year == "全部" else int(selected_year)

        # 获取统计数据
        total_users = get_site_stats()
        top_wrong = get_top_wrong_questions_filtered(class_filter, year_filter, limit=10)
        knowledge_acc = get_knowledge_accuracy_filtered(class_filter, year_filter)

        st.metric("总注册用户", total_users)
        st.subheader("🔝 高频错题 TOP 10")
        if top_wrong:
            id_to_question = {q['id']: q for q in QUESTION_BANK}
            for item in top_wrong:
                qid = item['question_id']
                wrongs = item['wrong_count'] if 'wrong_count' in item else item.get('wrong_attempts', 0)
                kp = item.get('knowledge_point', '未知知识点')
                q = id_to_question.get(qid)
                if q:
                    st.write(f"**ID {qid}** ({kp}): {q['question'][:50]}... (错误 {wrongs} 次)")
                else:
                    st.write(f"**ID {qid}** ({kp}): 题目已删除 (错误 {wrongs} 次)")
        else:
            st.info("暂无数据")
        st.subheader("📈 知识点平均正确率")
        if knowledge_acc:
            for row in knowledge_acc:
                kp = row['knowledge_point']
                acc = row['accuracy']
                st.write(f"- {kp}: {acc:.1%}")
        else:
            st.info("暂无数据")
    st.stop()  # 看板独占页面

# ---------- 主区域答题 ----------
if st.session_state.questions and not st.session_state.quiz_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    if 'id' not in q:
        st.error(f"题目缺少 id 字段: {q.get('question', '未知')}")
        st.stop()
    question_id = q['id']
    knowledge_point = q['knowledge']

    st.subheader(f"📝 第 {idx+1} / {total} 题")
    st.markdown(f"**{q['question']}**")
    st.caption(f"📂 {q['chapter']}  ·  🏷️ {q['knowledge']}  ·  📌 {q['type']}")

    # 题型输入
    if q["type"] in ["choice", "judge"]:
        options = q["options"]
        current_index = st.session_state.user_answer if isinstance(st.session_state.user_answer, int) else None
        selected_label = st.radio(
            "选择答案",
            options,
            index=current_index,
            key=f"radio_{idx}",
            label_visibility="collapsed"
        )
        if selected_label:
            user_choice = options.index(selected_label)
        else:
            user_choice = None
        if not st.session_state.submitted:
            st.session_state.user_answer = user_choice

    elif q["type"] == "fill":
        if st.session_state.submitted:
            st.text_input("你的答案", value=st.session_state.user_answer or "", disabled=True, key=f"fill_{idx}")
        else:
            user_input = st.text_input("输入答案", value=st.session_state.user_answer or "", key=f"fill_{idx}")
            st.session_state.user_answer = user_input.strip() if user_input else ""

    # 按钮
    col_sub, col_next = st.columns(2)
    with col_sub:
        if st.button("✅ 提交答案", use_container_width=True, disabled=st.session_state.submitted):
            if st.session_state.start_time:
                elapsed = int(time.time() - st.session_state.start_time)
            else:
                elapsed = None

            if q["type"] == "fill":
                if not st.session_state.user_answer:
                    st.warning("请先输入答案！")
                    st.stop()
            else:
                if st.session_state.user_answer is None:
                    st.warning("请先选择一个选项！")
                    st.stop()

            correct = False
            if q["type"] == "fill":
                if st.session_state.user_answer.strip().lower() == q["answer"].strip().lower():
                    correct = True
            else:
                if st.session_state.user_answer == q["answer"]:
                    correct = True

            # 记录到数据库（传入知识点）
            record_practice(st.session_state.user['id'], question_id, correct, knowledge_point, elapsed)

            if correct:
                st.session_state.feedback = "🎉 回答正确！"
            else:
                st.session_state.feedback = "❌ 回答错误"
                wrong_q = q.copy()
                wrong_q["user_answer"] = st.session_state.user_answer
                st.session_state.wrong_list.append(wrong_q)

            st.session_state.submitted = True
            st.session_state.start_time = time.time()
            st.rerun()

    with col_next:
        if st.button("⏩ 下一题", use_container_width=True):
            if idx + 1 < total:
                st.session_state.current_idx += 1
                st.session_state.user_answer = None
                st.session_state.submitted = False
                st.session_state.feedback = None
                st.session_state.start_time = time.time()
                st.rerun()
            else:
                st.session_state.quiz_finished = True
                st.rerun()

    if st.session_state.submitted and st.session_state.feedback:
        if "正确" in st.session_state.feedback:
            st.success(st.session_state.feedback)
        else:
            st.error(st.session_state.feedback)
            if q["type"] == "fill":
                st.info(f"正确答案是: {q['answer']}")
            else:
                st.info(f"正确答案是: {q['options'][q['answer']]}")
            if q.get("explanation"):
                st.caption(f"解析: {q['explanation']}")

elif st.session_state.quiz_finished:
    st.success("🎊 恭喜你完成全部题目！")
    st.balloons()
    if st.button("🔄 重新开始"):
        st.session_state.questions = []
        st.session_state.current_idx = 0
        st.session_state.user_answer = None
        st.session_state.submitted = False
        st.session_state.feedback = None
        st.session_state.quiz_finished = False
        st.rerun()

else:
    st.info("👆 请先在左侧选择章节和知识点，然后点击「开始练习」或「错题重练」")
    st.write("**支持题型**：选择题、判断题、填空题")
    st.write("所有答题数据将自动记录，用于生成统计报告。")

st.divider()
st.caption("教学练习平台 · 完整版 · 数据驱动学习")