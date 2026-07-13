# -*- coding: utf-8 -*-
"""
教学练习小程序 - V1.1 多课程支持（完整版）+ 知识图谱点击交互
"""
from streamlit_echarts import st_echarts
import json
import streamlit as st
import random
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
    st.error("❌ 缺少 Supabase 凭证，请在 Railway 中设置环境变量")
    st.stop()

ADMIN_PASSWORD = "admin123"

# ---------- 初始化 ----------
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ---------- 辅助函数 ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username: str, password: str, class_name: str, study_year: int, major: str, student_id: str) -> tuple[bool, str]:
    if len(username) < 2:
        return False, "用户名至少2个字符"
    if len(password) < 6:
        return False, "密码至少6个字符"
    if not class_name:
        return False, "班级不能为空"
    if not study_year:
        return False, "入学年份不能为空"
    if not major:
        return False, "专业不能为空"
    if not student_id:
        return False, "学号不能为空"

    resp = supabase.table('users').select('id').eq('student_id', student_id).execute()
    if resp.data:
        return False, "该学号已被注册"

    hashed = hash_password(password)
    try:
        resp = supabase.table('users').insert({
            'username': username,
            'password_hash': hashed,
            'class_name': class_name,
            'study_year': study_year,
            'major': major,
            'student_id': student_id
        }).execute()
        if resp.data:
            supabase.rpc('increment_site_stats', {'p_key': 'total_users'}).execute()
            return True, "注册成功，请登录"
        else:
            return False, "注册失败，请重试"
    except Exception as e:
        return False, f"注册异常: {str(e)}"

def login_user(login_id: str, password: str) -> tuple[bool, str, dict]:
    resp = supabase.table('users').select('*').eq('student_id', login_id).execute()
    if not resp.data:
        resp = supabase.table('users').select('*').eq('username', login_id).execute()
    if not resp.data:
        return False, "学号或用户名不存在", {}

    user = resp.data[0]
    if verify_password(password, user['password_hash']):
        supabase.table('users').update({
            'last_login': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).eq('id', user['id']).execute()
        return True, "登录成功", user
    else:
        return False, "密码错误", {}

# ===================== 升级后的 record_practice（支持课程） =====================
def record_practice(user_id: str, question_id: int, is_correct: bool, knowledge_point: str, chapter: str, course: str, time_spent: int = None):
    """
    记录练习数据（V2.0 版本：支持课程字段，知识点带课程前缀）
    """
    try:
        # 1. 记录到练习日志（新增 course 字段）
        data = {
            'user_id': user_id,
            'question_id': question_id,
            'is_correct': is_correct,
            'answered_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'knowledge_point': knowledge_point,
            'chapter': chapter,
            'course': course   # 新增课程字段
        }
        if time_spent:
            data['time_spent'] = time_spent
        supabase.table('practice_logs').insert(data).execute()

        # 2. 更新题目统计（不变）
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

        # 3. 更新用户知识点进度（关键改动：知识点加课程前缀，防止两门课互相覆盖）
        full_knowledge = f"{course}|{knowledge_point}"   # 例：管理学（马工程）|计划

        resp = supabase.table('user_progress').select('*').eq('user_id', user_id).eq('knowledge_point', full_knowledge).execute()
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
                'knowledge_point': full_knowledge,
                'correct_rate': 1.0 if is_correct else 0.0,
                'total_attempts': 1,
                'last_practiced': datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()
    except Exception as e:
        st.error(f"记录数据失败: {str(e)}")

def get_site_stats():
    try:
        resp = supabase.table('site_stats').select('stat_value').eq('stat_key', 'total_users').execute()
        return resp.data[0]['stat_value'] if resp.data else 0
    except:
        return 0

# ===================== 统计函数（已适配 V2.0 课程参数） =====================
def get_top_wrong_questions_filtered(class_name=None, study_year=None, major=None, chapter=None, course=None, limit=10):
    try:
        result = supabase.rpc('get_top_wrong_questions_v2', {
            'p_class_name': class_name,
            'p_study_year': study_year,
            'p_major': major,
            'p_chapter': chapter,
            'p_course': course,    # 课程筛选
            'p_limit': limit
        }).execute()
        return result.data
    except Exception as e:
        st.error(f"获取高频错题失败: {e}")
        return []

def get_knowledge_accuracy_filtered(class_name=None, study_year=None, major=None, chapter=None, course=None):
    try:
        result = supabase.rpc('get_knowledge_accuracy_v2', {
            'p_class_name': class_name,
            'p_study_year': study_year,
            'p_major': major,
            'p_chapter': chapter,
            'p_course': course     # 课程筛选
        }).execute()
        return result.data
    except Exception as e:
        st.error(f"获取知识点正确率失败: {e}")
        return []

def reset_user_password(admin_pw: str, student_id: str, new_password: str) -> tuple[bool, str]:
    if admin_pw != ADMIN_PASSWORD:
        return False, "管理员密码错误"
    if not student_id:
        return False, "学号不能为空"
    if len(new_password) < 6:
        return False, "新密码至少6个字符"

    resp = supabase.table('users').select('id').eq('student_id', student_id).execute()
    if not resp.data:
        return False, "未找到该学号对应的用户"
    user_id = resp.data[0]['id']
    hashed = hash_password(new_password)
    try:
        supabase.table('users').update({'password_hash': hashed}).eq('id', user_id).execute()
        return True, "密码重置成功"
    except Exception as e:
        return False, f"重置失败: {str(e)}"

# ---------- 知识图谱加载 ----------
@st.cache_data(ttl=600)
def load_knowledge_graph():
    """加载知识图谱 JSON 文件"""
    graph_path = os.path.join(os.path.dirname(__file__), "knowledge_graph.json")
    if not os.path.exists(graph_path):
        return None
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载知识图谱失败: {e}")
        return None

def get_graph_data(course: str, view_type: str = "core", chapter: str = None):
    """
    获取知识图谱的 ECharts 格式数据
    view_type: "core" 总图谱 或 "chapter" 章节图谱
    """
    graph_data = load_knowledge_graph()
    if not graph_data:
        return None
    
    courses = graph_data.get("courses", {})
    if course not in courses:
        return None
    
    course_data = courses[course]
    
    if view_type == "core":
        # 总图谱：使用 core_map
        core_map = course_data.get("core_map", {})
        nodes = core_map.get("nodes", [])
        links = core_map.get("links", [])
        title = f"{course} · 核心知识图谱"
    else:
        # 章节图谱
        chapters = course_data.get("chapters", {})
        if chapter not in chapters:
            return None
        chapter_data = chapters[chapter]
        nodes = chapter_data.get("nodes", [])
        links = chapter_data.get("links", [])
        title = f"{course} · {chapter}"
    
    # 转换为 ECharts 格式
    echarts_nodes = []
    for node in nodes:
        echarts_nodes.append({
            "id": node["id"],
            "name": node["name"],
            "symbolSize": 40,
            "itemStyle": {
                "color": "#4A90D9"
            },
            "label": {
                "fontSize": 12,
                "fontWeight": "bold"
            }
        })
    
    echarts_links = []
    for link in links:
        echarts_links.append({
            "source": link["source"],
            "target": link["target"],
            "label": {
                "show": True,
                "formatter": link.get("relation", "")
            }
        })
    
    return {
        "title": title,
        "nodes": echarts_nodes,
        "links": echarts_links,
        "raw_nodes": nodes  # 保存原始数据，用于查询详情
    }

# ---------- 知识图谱交互函数 ----------
def show_knowledge_detail(node_id: str, graph_data: dict):
    """显示知识点的详情弹窗"""
    if not node_id:
        return
    
    # 在所有节点中查找
    all_nodes = []
    courses = graph_data.get("courses", {})
    for course_name, course_data in courses.items():
        # 从章节中查找
        chapters = course_data.get("chapters", {})
        for chapter_name, chapter_data in chapters.items():
            for node in chapter_data.get("nodes", []):
                node_copy = node.copy()
                node_copy["chapter"] = chapter_name
                all_nodes.append(node_copy)
        # 从总图谱中查找
        core_nodes = course_data.get("core_map", {}).get("nodes", [])
        for node in core_nodes:
            node_copy = node.copy()
            if "chapter" not in node_copy:
                node_copy["chapter"] = "核心知识点"
            all_nodes.append(node_copy)
    
    # 去重（按 id）
    seen = set()
    unique_nodes = []
    for node in all_nodes:
        if node["id"] not in seen:
            seen.add(node["id"])
            unique_nodes.append(node)
    
    # 查找目标节点
    target = None
    for node in unique_nodes:
        if node["id"] == node_id:
            target = node
            break
    
    if not target:
        st.warning(f"未找到该知识点（ID: {node_id}）")
        return
    
    # 获取当前课程名称
    current_course = st.session_state.get("course", "管理学（马工程）")
    
    # 计算掌握度（从 user_progress 查询）
    accuracy = None
    if st.session_state.user:
        full_knowledge = f"{current_course}|{target['name']}"
        try:
            resp = supabase.table('user_progress').select('correct_rate').eq('user_id', st.session_state.user['id']).eq('knowledge_point', full_knowledge).execute()
            if resp.data:
                accuracy = resp.data[0]['correct_rate']
        except:
            pass
    
    # 使用 st.dialog 显示详情
    with st.dialog("📖 " + target["name"], width="large"):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**所属章节**：{target.get('chapter', '未标注')}")
            st.markdown(f"**题目数量**：{target.get('question_count', '未知')} 道")
            if accuracy is not None:
                color = "🟢" if accuracy >= 0.8 else "🟡" if accuracy >= 0.6 else "🔴"
                st.markdown(f"**掌握度**：{color} {accuracy:.1%}")
            else:
                st.markdown("**掌握度**：暂无数据")
            st.divider()
            st.markdown("**📝 详细描述**")
            st.markdown(target.get("description", "暂无描述"))
        
        with col2:
            st.caption("操作")
            if st.button("📖 查看完整内容", use_container_width=True):
                st.info("✅ 知识点详情已展示在左侧")
            
            if st.button("🎯 开始练习", use_container_width=True, type="primary"):
                # 跳转到练习控制台，自动选中该知识点
                st.session_state.knowledge_target = target["name"]
                st.session_state.knowledge_chapter = target.get("chapter", "")
                st.session_state.pending_knowledge = True
                st.rerun()

# ---------- 题库加载（支持多课程） ----------
@st.cache_data(ttl=600)
def load_questions(course: str):
    base_dir = os.path.dirname(__file__)
    if course == "管理学（英文）":
        prefix = "en_chapter"
    else:
        prefix = "chapter"
    pattern = os.path.join(base_dir, f"{prefix}*.json")
    file_list = glob.glob(pattern)
    all_questions = []
    if not file_list:
        st.warning(f"⚠️ 未找到课程 '{course}' 的题库文件（{prefix}*.json）")
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
    return all_questions

def get_current_question_bank():
    course = st.session_state.get("course", "管理学（马工程）")
    return load_questions(course)

def filter_questions(chapter=None, knowledge=None):
    bank = get_current_question_bank()
    if not bank:
        return []
    filtered = bank
    if chapter and chapter != "全部":
        filtered = [q for q in filtered if q["chapter"] == chapter]
    if knowledge and knowledge != "全部" and knowledge is not None:
        filtered = [q for q in filtered if q["knowledge"] == knowledge]
    return filtered

def get_available_knowledge(chapter=None):
    bank = get_current_question_bank()
    if not bank:
        return []
    if chapter is None or chapter == "全部":
        knowledges = sorted(set(q["knowledge"] for q in bank))
    else:
        knowledges = sorted(set(q["knowledge"] for q in bank if q["chapter"] == chapter))
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
    if "course" not in st.session_state:
        st.session_state.course = "管理学（马工程）"
    if "clicked_node_data" not in st.session_state:
        st.session_state.clicked_node_data = None
    if "show_graph" not in st.session_state:
        st.session_state.show_graph = False
    if "pending_knowledge" not in st.session_state:
        st.session_state.pending_knowledge = False
    if "knowledge_target" not in st.session_state:
        st.session_state.knowledge_target = None
    if "knowledge_chapter" not in st.session_state:
        st.session_state.knowledge_chapter = None
    if "graph_click_trigger" not in st.session_state:
        st.session_state.graph_click_trigger = 0

# ---------- 主页面 ----------
st.set_page_config(page_title="管理学 · 智能练习平台", page_icon="📚", layout="centered")
st.title("📖 管理学 · 智能练习平台")

init_session_state()

# ===================== 处理知识图谱点击事件 =====================
# 放在页面顶部，确保能捕获点击事件
graph_data = load_knowledge_graph()

if st.session_state.get("clicked_node_data"):
    clicked = st.session_state.clicked_node_data
    if clicked and clicked.get("id"):
        show_knowledge_detail(clicked["id"], graph_data)
    st.session_state.clicked_node_data = None

# 处理从知识图谱跳转过来的练习请求
if st.session_state.get("pending_knowledge", False):
    target_name = st.session_state.get("knowledge_target", "")
    target_chapter = st.session_state.get("knowledge_chapter", "")
    if target_name:
        st.success(f"🎯 已选中知识点：{target_name}")
        # 自动设置练习控制台的知识点筛选
        # 尝试在知识点列表中找到匹配的
        knowledge_options = get_available_knowledge(None)
        if target_name in knowledge_options:
            # 更新 session_state 中的知识点选择
            st.session_state.knowledge_select = target_name
        # 如果有章节信息，尝试自动选中章节
        if target_chapter:
            chapters = ["全部"] + sorted(set(q["chapter"] for q in get_current_question_bank()))
            if target_chapter in chapters:
                st.session_state.chapter_select = target_chapter
        # 自动勾选显示知识图谱（方便看到关联）
        st.session_state.show_graph = True
    st.session_state.pending_knowledge = False
    st.rerun()

# ---------- 侧边栏 ----------
with st.sidebar:
    # 1. 用户信息
    if st.session_state.user:
        st.write(f"👤 欢迎，**{st.session_state.user['username']}**")
        st.caption(f"学号：{st.session_state.user.get('student_id', '未设置')}  |  班级：{st.session_state.user.get('class_name', '未设置')}  |  专业：{st.session_state.user.get('major', '未设置')}")
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
                login_id = st.text_input("学号或用户名")
                login_password = st.text_input("密码", type="password")
                login_submit = st.form_submit_button("登录")
                if login_submit:
                    if login_id and login_password:
                        ok, msg, user = login_user(login_id, login_password)
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
                reg_username = st.text_input("姓名 (请填写真实姓名)")
                reg_password = st.text_input("密码 (至少6字符)", type="password")
                reg_class = st.text_input("班级 (如：1)")
                reg_year = st.number_input("入学年份", min_value=2000, max_value=2100, step=1, value=2026)
                reg_major = st.text_input("专业 (如：工商管理)")
                reg_student_id = st.text_input("学号 (请正确填写)")
                reg_submit = st.form_submit_button("注册")
                if reg_submit:
                    if reg_username and reg_password and reg_class and reg_year and reg_major and reg_student_id:
                        ok, msg = register_user(reg_username, reg_password, reg_class, int(reg_year), reg_major, reg_student_id)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("请填写完整信息")

    # ================== 2. 选择课程 ==================
    st.markdown("---")
    st.subheader("📚 选择课程")
    course_options = ["管理学（马工程）", "管理学（英文）"]
    current_course = st.session_state.get("course", "管理学（马工程）")
    selected_course = st.selectbox(
        "课程",
        course_options,
        index=course_options.index(current_course) if current_course in course_options else 0,
        key="course_select"
    )
    if selected_course != st.session_state.get("course"):
        st.session_state.course = selected_course
        st.session_state.questions = []
        st.session_state.wrong_list = []
        st.session_state.current_idx = 0
        st.session_state.quiz_finished = False
        st.rerun()

    # 3. 练习控制台
    st.markdown("---")
    st.subheader("🎯 练习控制台")
    current_bank = get_current_question_bank()
    chapters = ["全部"] + sorted(set(q["chapter"] for q in current_bank))
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
                wrong_questions = st.session_state.wrong_list[:]
                random.shuffle(wrong_questions)
                st.session_state.questions = wrong_questions
                st.session_state.current_idx = 0
                st.session_state.user_answer = None
                st.session_state.submitted = False
                st.session_state.feedback = None
                st.session_state.quiz_finished = False
                st.session_state.start_time = time.time()
                st.rerun()

    # 4. 统计与错题本
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

    # 5. 教师看板
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

# ---------- 知识图谱区域（主区域） ----------
# 获取当前课程
current_course = st.session_state.get("course", "管理学（马工程）")

# 布局：知识图谱开关
show_graph = st.checkbox("📊 显示知识图谱", value=st.session_state.get("show_graph", False))
st.session_state.show_graph = show_graph

if show_graph and graph_data:
    # 选择视图类型
    view_type = st.radio(
        "图谱视图",
        ["📈 总图谱", "📚 章节图谱"],
        horizontal=True,
        key="graph_view_type"
    )
    
    # ================== 总图谱 ==================
    if view_type == "📈 总图谱":
        chart_data = get_graph_data(current_course, "core")
        if chart_data:
            st.subheader("📊 核心知识图谱")
            st.caption("💡 点击任意知识点节点，查看详情")
            
            # 构建 ECharts 配置
            option = {
                "title": {
                    "text": chart_data["title"],
                    "textStyle": {"fontSize": 14, "fontWeight": "normal"},
                    "left": "center"
                },
                "tooltip": {
                    "formatter": "{b}",
                    "trigger": "item"
                },
                "series": [{
                    "type": "graph",
                    "layout": "force",
                    "force": {
                        "repulsion": 500,
                        "edgeLength": [150, 300],
                        "gravity": 0.1
                    },
                    "draggable": True,
                    "data": chart_data["nodes"],
                    "links": chart_data["links"],
                    "label": {
                        "show": True,
                        "position": "bottom",
                        "fontSize": 12,
                        "fontWeight": "bold"
                    },
                    "lineStyle": {
                        "color": "source",
                        "curveness": 0.3
                    },
                    "emphasis": {
                        "focus": "adjacency",
                        "lineStyle": {
                            "width": 3
                        }
                    },
                    "itemStyle": {
                        "borderColor": "#4A90D9",
                        "borderWidth": 2
                    }
                }]
            }
            
            # ========== 使用 st_echarts 渲染，捕获点击事件 ==========
            click_result = st_echarts(
                option,
                height="550px",
                key=f"graph_core_{current_course}_{st.session_state.graph_click_trigger}",
                events={
                    "click": """
                        function(params) {
                            if (params.dataType === 'node' && params.data) {
                                return params.data;
                            }
                            return null;
                        }
                    """
                }
            )
            
            # 如果有点击事件返回，保存到 session_state
            if click_result:
                st.session_state.clicked_node_data = click_result
                st.session_state.graph_click_trigger += 1
                st.rerun()
            
            # ========== 备选方案：下拉框选择 ==========
            st.divider()
            st.caption("🔽 或从下方列表中选择知识点")
            # 从原始数据中构建名称列表
            node_options = [""] + [f"{node['name']} ({node.get('chapter', '')})" for node in chart_data["raw_nodes"]]
            selected_name = st.selectbox("选择知识点查看详情", node_options, key="graph_select_core")
            if selected_name:
                # 提取知识点名称
                display_name = selected_name.split(" (")[0]
                for node in chart_data["raw_nodes"]:
                    if node["name"] == display_name:
                        show_knowledge_detail(node["id"], graph_data)
                        break
    
    # ================== 章节图谱 ==================
    else:
        courses = graph_data.get("courses", {})
        course_data = courses.get(current_course, {})
        chapters = list(course_data.get("chapters", {}).keys())
        
        if chapters:
            selected_chapter = st.selectbox("选择章节", chapters, key="graph_chapter_select")
            chart_data = get_graph_data(current_course, "chapter", selected_chapter)
            
            if chart_data:
                st.subheader(f"📚 {selected_chapter}")
                st.caption("💡 点击任意知识点节点，查看详情")
                
                option = {
                    "title": {
                        "text": chart_data["title"],
                        "textStyle": {"fontSize": 14, "fontWeight": "normal"},
                        "left": "center"
                    },
                    "tooltip": {
                        "formatter": "{b}",
                        "trigger": "item"
                    },
                    "series": [{
                        "type": "graph",
                        "layout": "force",
                        "force": {
                            "repulsion": 300,
                            "edgeLength": [100, 200],
                            "gravity": 0.1
                        },
                        "draggable": True,
                        "data": chart_data["nodes"],
                        "links": chart_data["links"],
                        "label": {
                            "show": True,
                            "position": "bottom",
                            "fontSize": 11,
                            "fontWeight": "bold"
                        },
                        "lineStyle": {
                            "color": "source",
                            "curveness": 0.3
                        },
                        "emphasis": {
                            "focus": "adjacency"
                        },
                        "itemStyle": {
                            "borderColor": "#4A90D9",
                            "borderWidth": 2
                        }
                    }]
                }
                
                # ========== 捕获章节图谱的点击事件 ==========
                click_result = st_echarts(
                    option,
                    height="550px",
                    key=f"graph_chapter_{current_course}_{selected_chapter}_{st.session_state.graph_click_trigger}",
                    events={
                        "click": """
                            function(params) {
                                if (params.dataType === 'node' && params.data) {
                                    return params.data;
                                }
                                return null;
                            }
                        """
                    }
                )
                
                if click_result:
                    st.session_state.clicked_node_data = click_result
                    st.session_state.graph_click_trigger += 1
                    st.rerun()
                
                # ========== 备选方案：下拉框选择 ==========
                st.divider()
                st.caption("🔽 或从下方列表中选择知识点")
                node_options = [""] + [f"{node['name']} ({node.get('chapter', '')})" for node in chart_data["raw_nodes"]]
                selected_name = st.selectbox("选择知识点查看详情", node_options, key="graph_select_chapter")
                if selected_name:
                    display_name = selected_name.split(" (")[0]
                    for node in chart_data["raw_nodes"]:
                        if node["name"] == display_name:
                            show_knowledge_detail(node["id"], graph_data)
                            break
        else:
            st.info("当前课程暂无章节数据")

elif show_graph and not graph_data:
    st.warning("⚠️ 未找到 knowledge_graph.json 文件，请确认文件已放置在项目根目录")

else:
    # 不显示知识图谱时，显示原有的练习提示
    pass

# ---------- 教师看板页面 ----------
if st.session_state.get("show_dashboard", False):
    st.header("📊 教师看板")
    with st.expander("🔑 重置学生密码 (教师专用)"):
        with st.form("reset_password_form"):
            reset_student_id = st.text_input("学生学号")
            reset_new_pw = st.text_input("新密码 (至少6字符)", type="password")
            reset_admin_pw = st.text_input("管理员密码", type="password")
            reset_submit = st.form_submit_button("重置密码")
            if reset_submit:
                if reset_student_id and reset_new_pw and reset_admin_pw:
                    ok, msg = reset_user_password(reset_admin_pw, reset_student_id, reset_new_pw)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("请填写完整")

    with st.spinner("加载数据..."):
        # 获取筛选选项
        try:
            course_options = ["全部", "管理学（马工程）", "管理学（英文）"]
            classes_resp = supabase.table('users').select('class_name').execute()
            classes = sorted(set([row['class_name'] for row in classes_resp.data if row['class_name']]))
            years_resp = supabase.table('users').select('study_year').execute()
            years = sorted(set([row['study_year'] for row in years_resp.data if row['study_year']]), reverse=True)
            majors_resp = supabase.table('users').select('major').execute()
            majors = sorted(set([row['major'] for row in majors_resp.data if row['major']]))
            current_bank = get_current_question_bank()
            all_chapters = sorted(set(q['chapter'] for q in current_bank))
        except Exception as e:
            course_options = ["全部", "管理学（马工程）", "管理学（英文）"]
            classes, years, majors, all_chapters = [], [], [], []
            st.error(f"获取筛选选项失败: {e}")

        # ================== 筛选器布局（顺序：课程 → 章节 → 年份 → 专业 → 班级） ==================
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
        with col_f1:
            selected_course_filter = st.selectbox("课程", course_options, key="course_filter")
        with col_f2:
            selected_chapter_filter = st.selectbox("章节", ["全部"] + all_chapters, key="chapter_filter")
        with col_f3:
            selected_year_filter = st.selectbox("年份", ["全部"] + [str(y) for y in years], key="year_filter")
        with col_f4:
            selected_major_filter = st.selectbox("专业", ["全部"] + majors, key="major_filter")
        with col_f5:
            selected_class_filter = st.selectbox("班级", ["全部"] + classes, key="class_filter")

        # 处理筛选值
        course_filter = None if selected_course_filter == "全部" else selected_course_filter
        class_filter = None if selected_class_filter == "全部" else selected_class_filter
        year_filter = None if selected_year_filter == "全部" else int(selected_year_filter)
        major_filter = None if selected_major_filter == "全部" else selected_major_filter
        chapter_filter = None if selected_chapter_filter == "全部" else selected_chapter_filter

        total_users = get_site_stats()
        top_wrong = get_top_wrong_questions_filtered(
            class_name=class_filter,
            study_year=year_filter,
            major=major_filter,
            chapter=chapter_filter,
            course=course_filter,
            limit=10
        )
        knowledge_acc = get_knowledge_accuracy_filtered(
            class_name=class_filter,
            study_year=year_filter,
            major=major_filter,
            chapter=chapter_filter,
            course=course_filter
        )

        st.metric("总注册用户", total_users)
        st.subheader("🔝 高频错题 TOP 10")
        if top_wrong:
            id_to_question = {q['id']: q for q in get_current_question_bank()}
            for item in top_wrong:
                qid = item['question_id']
                wrongs = item['wrong_count']
                kp = item['knowledge_point']
                q = id_to_question.get(qid)
                if q:
                    st.write(f"**ID {qid}** ({kp}): {q['question'][:50]}... (错误 {wrongs} 次)")
                else:
                    st.write(f"**ID {qid}** ({kp}): 题目已删除或不在当前课程中 (错误 {wrongs} 次)")
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
    st.stop()

# ---------- 主区域答题 ----------
if st.session_state.questions and not st.session_state.quiz_finished:
    if st.session_state.user is None:
        st.warning("⚠️ 请登录后进行练习")
        st.session_state.questions = []
        st.stop()

    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    if 'id' not in q:
        st.error(f"题目缺少 id 字段: {q.get('question', '未知')}")
        st.stop()
    question_id = q['id']
    knowledge_point = q['knowledge']
    chapter = q['chapter']
    current_course = st.session_state.get("course", "管理学（马工程）")

    st.subheader(f"📝 第 {idx+1} / {total} 题")
    st.markdown(f"**{q['question']}**")
    st.caption(f"📂 {q['chapter']}  ·  🏷️ {q['knowledge']}  ·  📌 {q['type']}")

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

    col_sub, col_next = st.columns(2)
    with col_sub:
        if st.button("✅ 提交答案", use_container_width=True, disabled=st.session_state.submitted):
            if st.session_state.user is None:
                st.error("❌ 请登录后再答题")
                st.stop()

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

            # ========== 调用升级后的 record_practice（传入 course） ==========
            record_practice(
                st.session_state.user['id'],
                question_id,
                correct,
                knowledge_point,
                chapter,
                current_course,   # 传入课程
                elapsed
            )

            if correct:
                st.session_state.feedback = "🎉 回答正确！"
                st.session_state.wrong_list = [w for w in st.session_state.wrong_list if w['id'] != q['id']]
            else:
                st.session_state.feedback = "❌ 回答错误"
                existing = any(w['id'] == q['id'] for w in st.session_state.wrong_list)
                if not existing:
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
st.caption("教学练习平台 · V1.1 · 支持多课程 & 看板课程筛选 & 知识图谱")