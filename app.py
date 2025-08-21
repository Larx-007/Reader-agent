# 📚 AI Book Reader + Summarizer with TOC Navigation

import asyncio
import os
import uuid
import streamlit as st
import pymupdf
import edge_tts
from google import genai
from google.genai import types
import wave
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
CHUNK_CHAR_LIMIT = 3000
CACHE_DIR = "./cache"

# --- GLOBAL STATE ---
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
            summary = summarize_text(text)
            st.session_state["current_section"] = (node.title, node.page, text, summary)


def extract_pdf_toc(pdf_path):
    doc = pymupdf.open(pdf_path)
    toc = doc.get_toc()
    toc_tree = build_tree(toc)
    return toc_tree


def extract_text_from_page(pdf_path, page_number):
    doc = pymupdf.open(pdf_path)
    if page_number < len(doc):
        return doc[page_number].get_text()
    return "Page not found."


def chunk_text(text, limit=CHUNK_CHAR_LIMIT):
    return [text[i:i+limit] for i in range(0, len(text), limit)]


def get_voice_samples(voice):
    return os.path.join("utils/voice-samples", f"{voice}-intro.wav")


def get_cache_filename(text, voice):
    unique_id = uuid.uuid5(uuid.NAMESPACE_DNS, text + voice)
    return os.path.join(CACHE_DIR, f"{unique_id}_{voice}.wav")


def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


async def read_aloud(text, voice, filename):
    filename = get_cache_filename(text, voice)
    if not os.path.exists(filename):
        try:
            content = f"""
            Read in a bold, confident and a coorporate professional tone:

            {text} 
            """
            client = genai.Client()
            response = client.models.generate_content(
                model="gemini-2.5-pro-preview-tts",
                contents=content,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice
                            )
                        )
                    ),
                )
            )
            data = response.candidates[0].content.parts[0].inline_data.data
            wave_file(filename, data)
        except Exception as e:
            st.info(
                body="""
                Seems like your GOOGLE_API_KEY has expired or the rate limit exceeded. 
                Wait for the limit to reset or try creating a new api key to listen to google gemini voices.

                For now defaulting to edge-tts voice.
                """,
                icon="ℹ️"
            )
            filename = get_cache_filename(text, "en-US-GuyNeural")
            communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural")
            await communicate.save(filename)

    audio_file = open(filename, 'rb')
    st.audio(audio_file.read(), format='audio/wav')


def summarize_text(text):
    prompt = f"Summarize the following content by highlighting the key takeaways:\n\n{text}"
    response = OpenAI().chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def display_toc_navigation(toc, pdf_path):
    st.sidebar.title("🧾 Table of Contents")
    for chapter in toc:
        render_node(node=chapter, pdf_path=pdf_path)


def display_current_section():
    title, page, text, summary = st.session_state["current_section"]
    st.subheader(f"📖 {title} (Page {page})")
    st.text_area("Content", text, height=300)
    
    st.divider()

    # Voice selection placed near Read Aloud button
    available_voices = ["Zephyr", "Puck", "Leda", "Laomedeia", "Alnilam", "Sadaltager"]

    col1, col2 = st.columns(2, vertical_alignment="bottom")
    with col1: 
        selected_voice = st.selectbox("🎙 Choose Narration Voice", available_voices, key="voice_selector")
    with col2:
        with st.popover(label="🎙 Hear Voices", width="stretch"):
            for voice in available_voices:
                col1, col2 = st.columns([2,3], vertical_alignment="center")
                with col1:
                    st.markdown(f"**{voice}**")
                with col2:
                    filename = get_voice_samples(voice)
                    audio_file = open(filename, 'rb')
                    st.audio(audio_file.read(), format='audio/wav')

    with st.container(horizontal=True, horizontal_alignment="distribute"):
        if st.button("🔊 Read This Aloud"):
            filename = get_cache_filename(title, selected_voice)
            for chunk in chunk_text(text):
                with st.spinner("Wait for it...", show_time=True):
                    asyncio.run(read_aloud(text=chunk, voice=selected_voice, filename=filename))

    st.divider()

    with st.expander("📝 See summary"):
        st.markdown("### ✨ Summary")
        st.write(summary)
    
    with st.expander("❓ QnAs"):
        st.markdown("### QnAs")
        st.write("How can I help you?")


# --- UI ---
st.set_page_config(page_title="AI Book Narrator", page_icon="📚", layout="centered")
st.title("📚 AI Book Reader & Summarizer")
uploaded_pdf = st.file_uploader("Upload your Book (PDF)", type="pdf")

if uploaded_pdf:
    st.success("Book uploaded successfully!")
    filename = uploaded_pdf.name
    filepath = os.path.join(CACHE_DIR, filename)

    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(uploaded_pdf.getbuffer())

    if not st.session_state["toc"]:
        st.session_state["toc"] = extract_pdf_toc(filepath)

    display_toc_navigation(st.session_state["toc"], filepath)

    if st.session_state["current_section"]:
        display_current_section()
