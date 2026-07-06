# -*- coding: utf-8 -*-
"""
教学练习小程序 - 支持选择题、判断题、填空题
功能完整，可直接运行。
录入题库时，请在 QUESTION_BANK 中添加题目，按以下格式：

1. 选择题 (type: "choice")
   {
       "type": "choice",
       "chapter": "第1章",
       "knowledge": "变量",
       "question": "题目内容？",
       "options": ["A选项", "B选项", "C选项", "D选项"],
       "answer": 0,          # 正确选项索引（0开始）
       "explanation": "解析内容"
   }

2. 判断题 (type: "judge")
   {
       "type": "judge",
       "chapter": "第2章",
       "knowledge": "循环",
       "question": "判断题陈述？",
       "options": ["正确", "错误"],   # 也可自定义，但建议保持
       "answer": 0,                # 0代表正确，1代表错误
       "explanation": "解析内容"
   }

3. 填空题 (type: "fill")
   {
       "type": "fill",
       "chapter": "第3章",
       "knowledge": "函数",
       "question": "Python中定义函数的关键字是 ______。",
       "answer": "def",           # 正确答案（字符串）
       "explanation": "使用 def 关键字定义函数。"
   }

注意：所有标点符号必须为英文半角。
"""

import streamlit as st
import random

# ---------- 题库（内置示例） ----------
QUESTION_BANK = [
    # ----- 选择题示例 -----
    {
        "type": "choice",
        "chapter": "第1章 基础",
        "knowledge": "变量",
        "question": "在Python中，以下哪个是合法的变量名？",
        "options": ["1var", "var_name", "var-name", "var name"],
        "answer": 1,
        "explanation": "变量名只能包含字母、数字和下划线，且不能以数字开头。"
    },
    {
        "type": "choice",
        "chapter": "第1章 基础",
        "knowledge": "数据类型",
        "question": "以下哪个是整数类型？",
        "options": ["3.14", "3", "'3'", "True"],
        "answer": 1,
        "explanation": "整数是不带小数点的数字，3 是 int 类型。"
    },
    # ----- 判断题示例 -----
    {
        "type": "judge",
        "chapter": "第2章 循环",
        "knowledge": "for循环",
        "question": "Python中，for循环可以遍历列表中的每个元素。",
        "options": ["正确", "错误"],
        "answer": 0,
        "explanation": "for item in list: 可以遍历列表。"
    },
    {
        "type": "judge",
        "chapter": "第2章 循环",
        "knowledge": "while循环",
        "question": "while循环必须使用break语句才能退出。",
        "options": ["正确", "错误"],
        "answer": 1,
        "explanation": "while循环的条件为False时会自动退出，不一定需要break。"
    },
    # ----- 填空题示例 -----
    {
        "type": "fill",
        "chapter": "第3章 函数",
        "knowledge": "函数定义",
        "question": "Python中定义函数的关键字是 ______。",
        "answer": "def",
        "explanation": "使用 def 关键字定义函数。"
    },
    {
        "type": "fill",
        "chapter": "第3章 函数",
        "knowledge": "返回值",
        "question": "函数中使用 ______ 关键字返回结果。",
        "answer": "return",
        "explanation": "return 用于从函数中返回一个值。"
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
        return pool[:]
    return random.sample(pool, count)

def init_session_state():
    """初始化 session 状态变量"""
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
    # 存储当前题目的用户答案（不同题型用不同格式）
    if "user_answer" not in st.session_state:
        st.session_state.user_answer = None

# ---------- 页面布局 ----------
st.set_page_config(page_title="智能练习 · 多题型", page_icon="📚", layout="centered")
st.title("📖 智能练习 · 多题型")

init_session_state()

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("🎯 控制面板")
    
    chapters = ["全部"] + sorted(set(q["chapter"] for q in QUESTION_BANK))
    selected_chapter = st.selectbox("选择章节", chapters, key="chapter_select")
    
    knowledges = get_available_knowledge(selected_chapter if selected_chapter != "全部" else None)
    knowledge_options = ["全部"] + knowledges
    selected_knowledge = st.selectbox("选择知识点", knowledge_options, key="knowledge_select")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 开始练习", use_container_width=True):
            new_questions = pick_questions(selected_chapter, selected_knowledge, count=5)
            if not new_questions:
                st.warning("当前选择下没有题目，请调整筛选条件")
            else:
                st.session_state.questions = new_questions
                st.session_state.current_idx = 0
                st.session_state.user_answer = None
                st.session_state.submitted = False
                st.session_state.feedback = None
                st.session_state.quiz_finished = False
                st.rerun()
    
    with col2:
        if st.button("📕 错题重练", use_container_width=True):
            if not st.session_state.wrong_list:
                st.info("错题本为空，无需重练")
            else:
                wrong_knowledges = set(q["knowledge"] for q in st.session_state.wrong_list)
                new_questions = []
                for kw in wrong_knowledges:
                    pool = filter_questions(knowledge=kw)
                    if pool:
                        sample_size = min(2, len(pool))
                        new_questions.extend(random.sample(pool, sample_size))
                if not new_questions:
                    st.warning("找不到对应知识点的题目，无法重练")
                else:
                    random.shuffle(new_questions)
                    st.session_state.questions = new_questions
                    st.session_state.current_idx = 0
                    st.session_state.user_answer = None
                    st.session_state.submitted = False
                    st.session_state.feedback = None
                    st.session_state.quiz_finished = False
                    st.rerun()
    
    st.divider()
    st.subheader("📊 统计")
    st.write(f"总题数: {len(QUESTION_BANK)}")
    st.write(f"错题数: {len(st.session_state.wrong_list)}")
    
    with st.expander("📋 错题本", expanded=False):
        if not st.session_state.wrong_list:
            st.info("暂无错题，继续加油！")
        else:
            for i, wrong_q in enumerate(st.session_state.wrong_list):
                with st.expander(f"错题 {i+1}: {wrong_q['question'][:30]}..."):
                    st.write(f"**章节**: {wrong_q['chapter']}  |  **知识点**: {wrong_q['knowledge']}")
                    # 根据题型显示用户答案
                    if wrong_q["type"] == "fill":
                        user_ans = wrong_q.get("user_answer", "未作答")
                        st.write(f"**你的答案**: {user_ans}")
                    else:
                        user_idx = wrong_q.get("user_answer")
                        if user_idx is not None and isinstance(user_idx, int):
                            st.write(f"**你的选择**: {wrong_q['options'][user_idx]}")
                        else:
                            st.write("**你的选择**: 未作答")
                    # 显示正确答案
                    if wrong_q["type"] == "fill":
                        st.write(f"**正确答案**: {wrong_q['answer']}")
                    else:
                        st.write(f"**正确答案**: {wrong_q['options'][wrong_q['answer']]}")
                    if wrong_q.get("explanation"):
                        st.info(f"💡 解析: {wrong_q['explanation']}")

# ---------- 主区域 ----------
if st.session_state.questions and not st.session_state.quiz_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    
    st.subheader(f"📝 第 {idx+1} / {total} 题")
    st.markdown(f"**{q['question']}**")
    st.caption(f"📂 {q['chapter']}  ·  🏷️ {q['knowledge']}  ·  📌 {q['type']}")
    
    # ---------- 根据题型显示不同输入组件 ----------
    # 重置用户答案（如果未提交且未设置）
    if not st.session_state.submitted and st.session_state.user_answer is None:
        # 不重置，保留上次选择
        pass
    
    # 选择题和判断题用 radio
    if q["type"] in ["choice", "judge"]:
        options = q["options"]
        # 确定当前选中的索引
        current_index = st.session_state.user_answer if isinstance(st.session_state.user_answer, int) else None
        # 显示 radio
        selected_label = st.radio(
            "选择答案",
            options,
            index=current_index,
            key=f"radio_{idx}",
            label_visibility="collapsed"
        )
        # 将选中的文本转为索引
        if selected_label:
            user_choice = options.index(selected_label)
        else:
            user_choice = None
        # 存储到 session（未提交时更新）
        if not st.session_state.submitted:
            st.session_state.user_answer = user_choice
    
    # 填空题用 text_input
    elif q["type"] == "fill":
        # 获取已有输入（如果已提交则显示不可编辑，否则可编辑）
        if st.session_state.submitted:
            # 已提交，显示只读文本框
            st.text_input("你的答案", value=st.session_state.user_answer or "", disabled=True, key=f"fill_{idx}")
        else:
            user_input = st.text_input("输入答案", value=st.session_state.user_answer or "", key=f"fill_{idx}")
            st.session_state.user_answer = user_input.strip() if user_input else ""
    
    # ---------- 按钮 ----------
    col_sub, col_next = st.columns(2)
    with col_sub:
        if st.button("✅ 提交答案", use_container_width=True, disabled=st.session_state.submitted):
            # 检查是否已选/输入
            if q["type"] == "fill":
                if not st.session_state.user_answer:
                    st.warning("请先输入答案！")
                    st.stop()
            else:
                if st.session_state.user_answer is None:
                    st.warning("请先选择一个选项！")
                    st.stop()
            
            # 判断对错
            correct = False
            if q["type"] == "fill":
                # 忽略大小写和首尾空格
                if st.session_state.user_answer.strip().lower() == q["answer"].strip().lower():
                    correct = True
            else:
                if st.session_state.user_answer == q["answer"]:
                    correct = True
            
            if correct:
                st.session_state.feedback = "🎉 回答正确！"
            else:
                st.session_state.feedback = "❌ 回答错误"
                # 记录错题（深拷贝并保存用户答案）
                wrong_q = q.copy()
                wrong_q["user_answer"] = st.session_state.user_answer
                st.session_state.wrong_list.append(wrong_q)
            
            st.session_state.submitted = True
            st.rerun()
    
    with col_next:
        if st.button("⏩ 下一题", use_container_width=True):
            if idx + 1 < total:
                st.session_state.current_idx += 1
                st.session_state.user_answer = None
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
    st.write("**支持题型**：选择题、判断题、填空题。")
    st.write("点击「开始练习」随机抽取5道题，答错自动收入错题本。")
    st.write("「错题重练」会根据错题知识点生成新题目，针对性巩固。")

st.divider()
st.caption("教学练习小程序 · 多题型版 · 使用 Streamlit 构建")
