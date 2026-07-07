# -*- coding: utf-8 -*-
"""
教学练习小程序 - 完整版（带用户系统 + 数据统计）
功能：
- 用户注册/登录（密码加密）
- 答题记录入库（练习日志、题目错误统计、知识点掌握度）
- 教师看板（总用户数、高频错题、知识点正确率）
- 错题重练（基于本地错题本）
题库：chapter*.json（需包含 id 字段，数字全局唯一）
"""

import streamlit as st
import random
import json
import os
import glob
import bcrypt
from supabase import create_client, Client
import datetime
import time

# ---------- 配置 ----------
# 尝试从环境变量读取，否则从 st.secrets 读取
SUPABASE_URL = os.getenv("SUPABASE_URL", st.secrets.get("SUPABASE_URL"))
SUPABASE_KEY = os.getenv("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY"))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ 缺少 Supabase 凭证，请检查环境变量或 secrets.toml")
    st.stop()

# 管理员密码（用于教师看板）- 可在此修改
ADMIN_PASSWORD = "admin123"  # 建议改为强密码

# ---------- 初始化 Supabase 客户端 ----------
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ---------- 数据库辅助函数 ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username: str, password: str) -> tuple[bool, str]:
    """注册用户，返回 (成功标志, 消息)"""
    if len(username) < 3:
        return False, "用户名至少3个字符"
    if len(password) < 6:
        return False, "密码至少6个字符"
    # 检查用户名是否已存在
    resp = supabase.table('users').select('id').eq('username', username).execute()
    if resp.data:
        return False, "用户名已被占用"
    # 插入新用户
    hashed = hash_password(password)
    try:
        resp = supabase.table('users').insert({
            'username': username,
            'password_hash': hashed
        }).execute()
        if resp.data:
            # 更新站点统计总用户数
            supabase.rpc('increment_site_stats', {'stat_key': 'total_users'}).execute()
            return True, "注册成功，请登录"
        else:
            return False, "注册失败，请重试"
    except Exception as e:
        return False, f"注册异常: {str(e)}"

def login_user(username: str, password: str) -> tuple[bool, str, dict]:
    """登录，返回 (成功标志, 消息, 用户数据)"""
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

def record_practice(user_id: str, question_id: int, is_correct: bool, time_spent: int = None):
    """记录一次练习"""
    try:
        # 插入练习日志
        data = {
            'user_id': user_id,
            'question_id': question_id,
            'is_correct': is_correct,
            'answered_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if time_spent:
            data['time_spent'] = time_spent
        supabase.table('practice_logs').insert(data).execute()

        # 更新题目统计
        # 先获取当前统计
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
            # 首次记录
            supabase.table('question_stats').insert({
                'question_id': question_id,
                'total_attempts': 1,
                'wrong_attempts': 0 if is_correct else 1,
                'last_updated': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()

        # 更新用户知识点掌握度（需获取题目对应的知识点）
        # 从题库中查找知识点
        question = next((q for q in QUESTION_BANK if q['id'] == question_id), None)
        if question:
            knowledge = question['knowledge']
            # 获取该用户该知识点历史数据
            resp = supabase.table('user_progress').select('*').eq('user_id', user_id).eq('knowledge_point', knowledge).execute()
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
                # 新增
                supabase.table('user_progress').insert({
                    'user_id': user_id,
                    'knowledge_point': knowledge,
                    'correct_rate': 1.0 if is_correct else 0.0,
                    'total_attempts': 1,
                    'last_practiced': datetime.datetime.now(datetime.timezone.utc).isoformat()
                }).execute()
    except Exception as e:
        st.error(f"记录数据失败: {str(e)}")
        # 不影响主流程

def get_site_stats():
    """获取总用户数"""
    try:
        resp = supabase.table('site_stats').select('stat_value').eq('stat_key', 'total_users').execute()
        if resp.data:
            return resp.data[0]['stat_value']
        return 0
    except:
        return 0

def get_top_wrong_questions(limit=10):
    """获取错误次数最多的题目（高频错题）"""
    try:
        resp = supabase.table('question_stats').select('question_id, wrong_attempts').order('wrong_attempts', desc=True).limit(limit).execute()
        return resp.data
    except:
        return []

def get_all_knowledge_accuracy():
    """获取所有知识点的平均正确率（基于所有用户）"""
    try:
        resp = supabase.table('user_progress').select('knowledge_point, correct_rate').execute()
        if not resp.data:
            return {}
        # 按知识点汇总
        agg = {}
        for row in resp.data:
            kp = row['knowledge_point']
            rate = row['correct_rate']
            if kp not in agg:
                agg[kp] = []
            agg[kp].append(rate)
        # 计算平均
        avg = {}
        for kp, rates in agg.items():
            avg[kp] = sum(rates) / len(rates)
        return avg
    except:
        return {}

# ---------- 加载题库 ----------
@st.cache_data(ttl=600)
def load_questions():
    """从所有 chapter*.json 加载题目，必须包含 id 字段"""
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
                        st.error(f"❌ 题目缺少 'id' 字段：{q.get('question', '未知题目')[:30]}... 请添加数字 id")
                        continue
                    # 检查 ID 是否重复
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

# ---------- 主页面 ----------
st.set_page_config(page_title="智能练习 · 教学平台", page_icon="📚", layout="centered")
st.title("📖 智能练习 · 教学平台")

init_session_state()

# 侧边栏 - 用户信息/登录/注册
with st.sidebar:
    if st.session_state.user:
        st.write(f"👤 欢迎，**{st.session_state.user['username']}**")
        if st.button("🚪 退出登录"):
            st.session_state.user = None
            st.session_state.questions = []
            st.session_state.wrong_list = []
            st.rerun()
    else:
        st.subheader("🔐 登录 / 注册")
        # 使用 tabs 切换
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
                reg_submit = st.form_submit_button("注册")
                if reg_submit:
                    if reg_username and reg_password:
                        ok, msg = register_user(reg_username, reg_password)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("请填写完整")

# ---------- 主逻辑 ----------
if not st.session_state.user:
    st.info("👆 请先在左侧登录或注册，以便记录学习数据")
    st.stop()

# 已登录用户
user_id = st.session_state.user['id']

# 侧边栏导航（仅登录后）
with st.sidebar:
    st.divider()
    st.subheader("📊 统计")
    st.write(f"总注册用户: {get_site_stats()}")
    st.write(f"错题数: {len(st.session_state.wrong_list)}")
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

# 教师看板入口
with st.sidebar:
    st.divider()
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
        total_users = get_site_stats()
        top_wrong = get_top_wrong_questions(10)
        knowledge_acc = get_all_knowledge_accuracy()
        st.metric("总注册用户", total_users)
        st.subheader("🔝 高频错题 TOP 10")
        if top_wrong:
            # 获取题目内容
            id_to_question = {q['id']: q for q in QUESTION_BANK}
            for item in top_wrong:
                qid = item['question_id']
                wrongs = item['wrong_attempts']
                q = id_to_question.get(qid)
                if q:
                    st.write(f"**ID {qid}**: {q['question'][:50]}... (错误 {wrongs} 次)")
                else:
                    st.write(f"**ID {qid}**: 题目已删除 (错误 {wrongs} 次)")
        else:
            st.info("暂无数据")
        st.subheader("📈 知识点平均正确率")
        if knowledge_acc:
            for kp, rate in sorted(knowledge_acc.items(), key=lambda x: x[1]):
                st.write(f"- {kp}: {rate:.1%}")
        else:
            st.info("暂无数据")
    st.stop()  # 看板独占页面

# ---------- 练习主界面 ----------
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 练习控制")
chapters = ["全部"] + sorted(set(q["chapter"] for q in QUESTION_BANK))
selected_chapter = st.sidebar.selectbox("选择章节", chapters, key="chapter_select")
knowledge_options = get_available_knowledge(selected_chapter if selected_chapter != "全部" else None)
selected_knowledge = st.sidebar.selectbox("选择知识点", knowledge_options, key="knowledge_select")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("🔄 开始练习", use_container_width=True):
        kw = None if selected_knowledge == "全部" else selected_knowledge
        new_questions = pick_questions(selected_chapter, kw, count=None)  # 全部
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

# ---------- 主区域答题 ----------
if st.session_state.questions and not st.session_state.quiz_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    # 检查题目是否有 id
    if 'id' not in q:
        st.error(f"题目缺少 id 字段，请修正 JSON: {q.get('question', '未知')}")
        st.stop()
    question_id = q['id']

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
            # 计算用时
            if st.session_state.start_time:
                elapsed = int(time.time() - st.session_state.start_time)
            else:
                elapsed = None
            # 验证答案
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

            # 记录数据库
            record_practice(user_id, question_id, correct, elapsed)

            if correct:
                st.session_state.feedback = "🎉 回答正确！"
            else:
                st.session_state.feedback = "❌ 回答错误"
                wrong_q = q.copy()
                wrong_q["user_answer"] = st.session_state.user_answer
                st.session_state.wrong_list.append(wrong_q)

            st.session_state.submitted = True
            st.session_state.start_time = time.time()  # 重置计时器
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