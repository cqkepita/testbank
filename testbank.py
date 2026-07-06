# -*- coding: utf-8 -*-
"""
教学练习小程序 - testbank.py
功能：
1. 根据章节/知识点随机出题（选择题）
2. 答题后自动评分，显示正误
3. 错题自动记录
4. 错题本：点击可查看正确答案和解析
5. 错题重练：根据错题指向的知识点重新随机出题

运行方法：
1. 打开终端（Anaconda Prompt 或命令行）
2. 安装 streamlit：pip install streamlit
3. 进入代码所在目录，执行：streamlit run testbank.py
4. 浏览器会自动打开，开始使用
"""

import streamlit as st
import random

# ---------- 题库（内置示例） ----------
# 每道题：章节、知识点、题目、选项（列表）、正确答案索引（0开始）、解析（可选）
QUESTION_BANK = [
    {
        "chapter": "第1章 基础",
        "knowledge": "变量",
        "question": "在Python中，以下哪个是合法的变量名？",
        "options": ["1var", "var_name", "var-name", "var name"],
        "answer": 1,  # 索引从0开始，对应 "var_name"
        "explanation": "变量名只能包含字母、数字和下划线，且不能以数字开头，不能有空格或横线。"
    },
    {
        "chapter": "第1章 基础",
        "knowledge": "数据类型",
        "question": "以下哪个是整数类型？",
        "options": ["3.14", "3", "'3'", "True"],
        "answer": 1,
        "explanation": "整数是不带小数点的数字，3 是 int 类型。"
    },
    {
        "chapter": "第1章 基础",
        "knowledge": "条件语句",
        "question": "Python中，判断 a 是否大于 5 的正确写法是？",
        "options": ["a > 5", "a >= 5", "a > 5?", "if a > 5"],
        "answer": 0,
        "explanation": "比较运算符 > 用于判断大于。"
    },
    {
        "chapter": "第2章 数据结构",
        "knowledge": "列表",
        "question": "以下哪个是创建空列表的正确方式？",
        "options": ["list()", "[]", "{}", "()"],
        "answer": 1,
        "explanation": "[] 直接创建空列表，list() 也可以但 [] 更常用。"
    },
    {
        "chapter": "第2章 数据结构",
        "knowledge": "字典",
        "question": "字典中，通过键获取值的正确方法是？",
        "options": ["dict[key]", "dict(key)", "dict.get(key)", "B 和 C 都可以"],
        "answer": 3,
        "explanation": "dict[key] 和 dict.get(key) 都可以，但 get 在键不存在时返回 None 而不报错。"
    },
    {
        "chapter": "第2章 数据结构",
        "knowledge": "列表",
        "question": "列表 [1,2,3] 添加元素 4 后，长度变为？",
        "options": ["3", "4", "5", "报错"],
        "answer": 1,
        "explanation": "append 后列表长度 +1，变成 4。"
    },
    {
        "chapter": "第3章 函数",
        "knowledge": "函数定义",
        "question": "定义函数的正确关键字是？",
        "options": ["function", "def", "define", "func"],
        "answer": 1,
        "explanation": "Python 使用 def 关键字定义函数。"
    },
    {
        "chapter": "第3章 函数",
        "knowledge": "返回值",
        "question": "函数中使用哪个关键字返回结果？",
        "options": ["return", "print", "yield", "返回"],
        "answer": 0,
        "explanation": "return 用于从函数中返回一个值。"
    },
    {
        "chapter": "第3章 函数",
        "knowledge": "参数",
        "question": "以下哪种是默认参数的正确写法？",
        "options": ["def func(a=1):", "def func(a=1, b):", "def func(a, b=1):", "def func(a=1, b=2):"],
        "answer": 0,
        "explanation": "默认参数必须放在非默认参数之后，但选项 A 是单独一个默认参数，合法。"
    },
    {
        "chapter": "第1章 基础",
        "knowledge": "循环",
        "question": "以下哪个循环可以遍历列表中的每个元素？",
        "options": ["for i in range(len(list)):", "for item in list:", "while i < len(list):", "以上都可以"],
        "answer": 3,
        "explanation": "三种方式都可以遍历列表，但 for item in list 更简洁。"
    }
]

# ---------- 辅助函数 ----------
def filter_questions(chapter=None, knowledge=None):
    """根据章节和知识点过滤题库"""
    filtered = QUESTION_BANK
    if chapter and chapter != "全部":
        filtered = [q for q in filtered if q["chapter"] == chapter]
    if knowledge and knowledge != "全部":
        filtered = [q for q in filtered if q["knowledge"] == knowledge]
    return filtered

def get_available_knowledge(chapter=None):
    """获取某章节下的所有知识点（去重）"""
    if chapter is None or chapter == "全部":
        return sorted(set(q["knowledge"] for q in QUESTION_BANK))
    else:
        return sorted(set(q["knowledge"] for q in QUESTION_BANK if q["chapter"] == chapter))

def pick_questions(chapter, knowledge, count=5):
    """从指定章节/知识点中随机抽取 count 道题（若不足则全部返回）"""
    pool = filter_questions(chapter, knowledge)
    if not pool:
        return []
    if len(pool) <= count:
        return pool[:]  # 全部
    return random.sample(pool, count)

def init_session_state():
    """初始化 session 状态变量"""
    if "questions" not in st.session_state:
        st.session_state.questions = []          # 当前练习的题目列表
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0
    if "wrong_list" not in st.session_state:
        st.session_state.wrong_list = []         # 错题列表（存题目字典）
    if "selected_option" not in st.session_state:
        st.session_state.selected_option = None
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
    if "feedback" not in st.session_state:
        st.session_state.feedback = None
    if "quiz_finished" not in st.session_state:
        st.session_state.quiz_finished = False

# ---------- 页面布局 ----------
st.set_page_config(page_title="教学练习", page_icon="📚", layout="centered")
st.title("📖 智能练习 · 教学小程序")

init_session_state()

# ---------- 侧边栏：控制与统计 ----------
with st.sidebar:
    st.header("🎯 控制面板")
    
    # 选择章节和知识点
    chapters = ["全部"] + sorted(set(q["chapter"] for q in QUESTION_BANK))
    selected_chapter = st.selectbox("选择章节", chapters, key="chapter_select")
    
    # 根据章节更新知识点选项
    knowledges = get_available_knowledge(selected_chapter if selected_chapter != "全部" else None)
    knowledge_options = ["全部"] + knowledges
    selected_knowledge = st.selectbox("选择知识点", knowledge_options, key="knowledge_select")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 开始练习", use_container_width=True):
            # 随机抽取题目
            new_questions = pick_questions(selected_chapter, selected_knowledge, count=5)
            if not new_questions:
                st.warning("当前选择下没有题目，请调整筛选条件")
            else:
                st.session_state.questions = new_questions
                st.session_state.current_idx = 0
                st.session_state.selected_option = None
                st.session_state.submitted = False
                st.session_state.feedback = None
                st.session_state.quiz_finished = False
                st.rerun()
    
    with col2:
        if st.button("📕 错题重练", use_container_width=True):
            # 从错题中提取知识点
            if not st.session_state.wrong_list:
                st.info("错题本为空，无需重练")
            else:
                # 收集所有错题的知识点（去重）
                wrong_knowledges = set(q["knowledge"] for q in st.session_state.wrong_list)
                # 从题库中抽取这些知识点的题目（每个知识点抽2题，避免太多）
                new_questions = []
                for kw in wrong_knowledges:
                    pool = filter_questions(knowledge=kw)
                    if pool:
                        # 随机抽取最多2题
                        sample_size = min(2, len(pool))
                        new_questions.extend(random.sample(pool, sample_size))
                if not new_questions:
                    st.warning("找不到对应知识点的题目，无法重练")
                else:
                    # 打乱顺序
                    random.shuffle(new_questions)
                    st.session_state.questions = new_questions
                    st.session_state.current_idx = 0
                    st.session_state.selected_option = None
                    st.session_state.submitted = False
                    st.session_state.feedback = None
                    st.session_state.quiz_finished = False
                    st.rerun()
    
    st.divider()
    st.subheader("📊 统计")
    st.write(f"总题数: {len(QUESTION_BANK)}")
    st.write(f"错题数: {len(st.session_state.wrong_list)}")
    
    # 显示错题列表（折叠）
    with st.expander("📋 错题本", expanded=False):
        if not st.session_state.wrong_list:
            st.info("暂无错题，继续加油！")
        else:
            for i, wrong_q in enumerate(st.session_state.wrong_list):
                # 用 expander 显示每道错题，点击展开答案
                with st.expander(f"错题 {i+1}: {wrong_q['question'][:30]}..."):
                    st.write(f"**章节**: {wrong_q['chapter']}  |  **知识点**: {wrong_q['knowledge']}")
                    st.write(f"**你的选择**: {wrong_q['options'][wrong_q['user_answer']]}")
                    st.write(f"**正确答案**: {wrong_q['options'][wrong_q['answer']]}")
                    if wrong_q.get("explanation"):
                        st.info(f"💡 解析: {wrong_q['explanation']}")

# ---------- 主区域：练习模式 ----------
if st.session_state.questions and not st.session_state.quiz_finished:
    # 当前题目
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    
    st.subheader(f"📝 第 {idx+1} / {total} 题")
    st.markdown(f"**{q['question']}**")
    st.caption(f"📂 {q['chapter']}  ·  🏷️ {q['knowledge']}")
    
    # 选项（使用 radio，但需要处理状态）
    options = q['options']
    # 为了保留选中状态，用 session_state 存储
    if st.session_state.selected_option is None:
        # 默认未选
        pass
    
    # 使用 radio 并绑定 session_state
    def on_option_change():
        # 当选择改变时，重置提交状态（但不要自动提交）
        pass
    
    selected = st.radio(
        "请选择答案（单选）",
        options,
        index=None,
        key=f"radio_{idx}",  # 每个题目独立key，但切换题目会重新创建
        on_change=on_option_change
    )
    # 由于 radio 的 index 参数需要整数，但我们要用 session_state 存储选择，所以采用另一种方式：使用 st.radio 的 index 参数，并手动更新
    # 但为了简单，我们使用 st.radio 的 key 来保存选择，但切换题目时，key 不变导致状态残留，所以每次用 idx 作为 key 的一部分
    # 但更好的办法：使用 session_state 存储当前选择
    # 这里使用 st.radio 并获取其值
    # 但 radio 没有直接的 value 参数，我们通过 index 控制
    # 重写：使用 options 列表，用 session_state.selected_option 存储选项索引，用 radio 的 index 参数
    
    # 更稳健：每次渲染时，用 session_state.selected_option 设置 index
    selected_index = st.session_state.selected_option
    # 确保 index 在有效范围
    if selected_index is not None and (selected_index < 0 or selected_index >= len(options)):
        selected_index = None
    
    # 显示选项（用 radio）
    selected_idx = st.radio(
        "选择答案",
        options,
        index=selected_index,
        key=f"radio_{idx}",
        label_visibility="collapsed"
    )
    # 因为 radio 返回的是选项的文本，我们需要找到索引
    if selected_idx is not None:
        # 获取选择的索引
        user_choice = options.index(selected_idx) if selected_idx in options else None
    else:
        user_choice = None
    
    # 更新 session_state 中的选中项
    if user_choice is not None:
        st.session_state.selected_option = user_choice
    
    # 按钮组
    col_sub, col_next = st.columns(2)
    with col_sub:
        if st.button("✅ 提交答案", use_container_width=True, disabled=st.session_state.submitted):
            if st.session_state.selected_option is None:
                st.warning("请先选择一个选项！")
            else:
                # 判断对错
                correct = (st.session_state.selected_option == q["answer"])
                if correct:
                    st.session_state.feedback = "🎉 回答正确！"
                else:
                    st.session_state.feedback = "❌ 回答错误"
                    # 将错题加入错题本（包含用户答案）
                    wrong_q = q.copy()
                    wrong_q["user_answer"] = st.session_state.selected_option
                    # 避免重复添加同一道题（可以简单去重，但为了演示，允许重复）
                    st.session_state.wrong_list.append(wrong_q)
                st.session_state.submitted = True
                st.rerun()
    
    with col_next:
        if st.button("⏩ 下一题", use_container_width=True):
            if idx + 1 < total:
                st.session_state.current_idx += 1
                st.session_state.selected_option = None
                st.session_state.submitted = False
                st.session_state.feedback = None
                st.rerun()
            else:
                st.session_state.quiz_finished = True
                st.rerun()
    
    # 显示反馈
    if st.session_state.submitted and st.session_state.feedback:
        if "正确" in st.session_state.feedback:
            st.success(st.session_state.feedback)
        else:
            st.error(st.session_state.feedback)
            # 显示正确答案
            st.info(f"正确答案是: {q['options'][q['answer']]}")
            if q.get("explanation"):
                st.caption(f"解析: {q['explanation']}")

elif st.session_state.quiz_finished:
    # 练习结束
    st.success("🎊 恭喜你完成全部题目！")
    st.balloons()
    # 显示本次练习的统计（可选）
    st.write("你可以继续选择新的练习或查看错题本。")
    if st.button("🔄 重新开始"):
        st.session_state.questions = []
        st.session_state.current_idx = 0
        st.session_state.selected_option = None
        st.session_state.submitted = False
        st.session_state.feedback = None
        st.session_state.quiz_finished = False
        st.rerun()

else:
    # 初始状态，无题目
    st.info("👆 请先在左侧选择章节和知识点，然后点击「开始练习」或「错题重练」")
    st.write("**提示**：点击「开始练习」会随机生成5道题，答错自动收入错题本。")
    st.write("**错题重练**：会根据错题的知识点生成新题目，针对性巩固。")

# ---------- 页脚 ----------
st.divider()
st.caption("教学练习小程序 · 使用 Streamlit 构建")