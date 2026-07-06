# -*- coding: utf-8 -*-
"""
教学练习小程序 - 从外部JSON文件读取题库
支持选择题、判断题、填空题
题库文件：questions.json（放在同一目录下）
"""

import streamlit as st
import random
import json
import os
import glob

# ---------- 读取外部JSON题库 ----------
@st.cache_data(ttl=600)  # 缓存10分钟，修改题库后等待生效

def load_questions():
    """从所有 chapter*.json 文件中加载题目，合并成一个题库"""
    base_dir = os.path.dirname(__file__)
    # 查找所有以 chapter 开头、.json 结尾的文件
    pattern = os.path.join(base_dir, "chapter*.json")
    file_list = glob.glob(pattern)
    
    if not file_list:
        st.error("❌ 未找到任何 chapter*.json 文件，请确保文件命名正确。")
        return []
    
    all_questions = []
    error_files = []
    
    for file_path in sorted(file_list):  # 排序保证加载顺序一致
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 确保是列表
                if isinstance(data, list):
                    all_questions.extend(data)
                else:
                    error_files.append(f"{os.path.basename(file_path)} (不是数组)")
        except json.JSONDecodeError as e:
            error_files.append(f"{os.path.basename(file_path)} (JSON格式错误: {e})")
        except Exception as e:
            error_files.append(f"{os.path.basename(file_path)} (读取错误: {e})")
    
    if error_files:
        st.error(f"⚠️ 以下文件加载失败，请检查：{', '.join(error_files)}")
        # 如果全部失败，返回空列表
        if not all_questions:
            return []
    
    st.success(f"✅ 成功加载 {len(all_questions)} 道题目，来自 {len(file_list)} 个文件。")
    return all_questions

QUESTION_BANK = load_questions()

# ---------- 辅助函数 ----------
def filter_questions(chapter=None, knowledge=None):
    if not QUESTION_BANK:
        return []
    filtered = QUESTION_BANK
    if chapter and chapter != "全部":
        filtered = [q for q in filtered if q["chapter"] == chapter]
    if knowledge and knowledge != "全部":
        filtered = [q for q in filtered if q["knowledge"] == knowledge]
    return filtered

def get_available_knowledge(chapter=None):
    if not QUESTION_BANK:
        return []
    if chapter is None or chapter == "全部":
        return sorted(set(q["knowledge"] for q in QUESTION_BANK))
    else:
        return sorted(set(q["knowledge"] for q in QUESTION_BANK if q["chapter"] == chapter))

def pick_questions(chapter, knowledge, count=5):
    pool = filter_questions(chapter, knowledge)
    if not pool:
        return []
    if len(pool) <= count:
        return pool[:]
    return random.sample(pool, count)

def init_session_state():
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

# ---------- 页面布局 ----------
st.set_page_config(page_title="智能练习 · 多题型", page_icon="📚", layout="centered")
st.title("📖 智能练习 · 多题型")

init_session_state()

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("🎯 控制面板")
    
    # 检查题库是否加载成功
    if not QUESTION_BANK:
        st.warning("⚠️ 题库为空，请检查 questions.json 文件。")
    else:
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

# ---------- 主区域 ----------
if st.session_state.questions and not st.session_state.quiz_finished:
    idx = st.session_state.current_idx
    total = len(st.session_state.questions)
    q = st.session_state.questions[idx]
    
    st.subheader(f"📝 第 {idx+1} / {total} 题")
    st.markdown(f"**{q['question']}**")
    st.caption(f"📂 {q['chapter']}  ·  🏷️ {q['knowledge']}  ·  📌 {q['type']}")
    
    # 根据题型显示输入
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
            
            if correct:
                st.session_state.feedback = "🎉 回答正确！"
            else:
                st.session_state.feedback = "❌ 回答错误"
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
    st.write("**支持题型**：选择题、判断题、填空题。")
    st.write("点击「开始练习」随机抽取5道题，答错自动收入错题本。")
    st.write("「错题重练」会根据错题知识点生成新题目，针对性巩固。")

st.divider()
st.caption("教学练习小程序 · 多题型版 · 题库独立为 questions.json")
