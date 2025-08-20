# 📚 AI Book Reader + Summarizer with TOC Navigation

import os
import streamlit as st
import fitz  # PyMuPDF
import asyncio
import edge_tts
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# --- CONFIG ---
CHUNK_CHAR_LIMIT = 3000
FILE_DIR = "./temp"

# --- GLOBAL STATE ---
st.session_state.setdefault("bookmarks", [])
st.session_state.setdefault("toc", [])
st.session_state.setdefault("current_section", None)

# --- CLASS ---


class TOCNode:
    def __init__(self, level, title, page):
        self.level = level
        self.title = title
        self.page = page
        self.children = []


# --- FUNCTIONS ---
def build_tree(flat_toc):
    root = TOCNode(0, "root", None)
    stack = [root]

    for level, title, page in flat_toc:
        node = TOCNode(level, title, page)

        # Maintain hierarchy using stack
        while stack and stack[-1].level >= level:
            stack.pop()
        stack[-1].children.append(node)
        stack.append(node)

    return root.children


def render_node(node, pdf_path):
    """Render the tree recursively in sidebar"""
    if node.children:
        with st.sidebar.expander(f"**{node.title}**"):
            for child in node.children:
                render_node(node=child, pdf_path=pdf_path)
    else:
        if st.button(f"{node.title} (Pg {node.page})", icon=":material/bookmark:"):
            text = extract_text_from_page(pdf_path, node.page - 1)
            st.session_state["current_section"] = (node.title, node.page, text)


def extract_pdf_toc(pdf_path):
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    toc_tree = build_tree(toc)
    return toc_tree


def extract_text_from_page(pdf_path, page_number):
    doc = fitz.open(pdf_path)
    if page_number < len(doc):
        return doc[page_number].get_text()
    return "Page not found."


def chunk_text(text, limit=CHUNK_CHAR_LIMIT):
    return [text[i:i+limit] for i in range(0, len(text), limit)]


async def read_aloud(text, filename="tts_output.mp3"):
    tts_filepath = os.path.join(FILE_DIR, filename)
    if not os.path.exists(tts_filepath):
        communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural")
        await communicate.save(tts_filepath)
    audio_file = open(tts_filepath, 'rb')
    st.audio(audio_file.read(), format='audio/mp3')


def summarize_text(text):
    prompt = f"Summarize the following content:\n\n{text}"
    response = OpenAI().chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def display_toc_navigation(toc, pdf_path):
    st.sidebar.title("📚 Table of Contents")
    for chapter in toc:
        render_node(node=chapter, pdf_path=pdf_path)
    # for entry in toc:
    #     level, title, page = entry
    #     if st.sidebar.button(f"{title} (Pg {page})"):
    #         text = extract_text_from_page(pdf_path, page - 1)
    #         st.session_state["current_section"] = (title, page, text)


def display_current_section():
    title, page, text = st.session_state["current_section"]
    st.subheader(f"📖 {title} (Page {page})")
    st.text_area("Content", text, height=300)

    if st.button("🔊 Read This Aloud"):
        filename = f"{title}.mp3"
        for chunk in chunk_text(text):
            asyncio.run(read_aloud(chunk, filename))

    if st.button("📝 Summarize This Section"):
        summary = summarize_text(text)
        st.markdown("### ✨ Summary")
        st.write(summary)

    # if st.button("📍 Bookmark This Section"):
    #     st.session_state["bookmarks"].append({"title": title, "page": page})

    if st.session_state["bookmarks"]:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔖 Bookmarks")
        for bm in st.session_state["bookmarks"]:
            if st.sidebar.button(f"{bm['title']} (Pg {bm['page']})", key=f"bm_{bm['page']}"):
                text = extract_text_from_page(uploaded_pdf, bm['page'] - 1)
                st.session_state["current_section"] = (
                    bm['title'], bm['page'], text)


# --- UI ---
st.title("📚 AI Book Reader & Summarizer")
uploaded_pdf = st.file_uploader("Upload your Book (PDF)", type="pdf")

if uploaded_pdf:
    st.success("Book uploaded successfully!")
    filename = uploaded_pdf.name
    filepath = os.path.join(FILE_DIR, filename)

    if not os.path.exists(FILE_DIR):
        os.makedirs(FILE_DIR, exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(uploaded_pdf.getbuffer())

    if not st.session_state["toc"]:
        st.session_state["toc"] = extract_pdf_toc(filepath)

    display_toc_navigation(st.session_state["toc"], filepath)

    if st.session_state["current_section"]:
        display_current_section()
