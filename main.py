import asyncio
import os
import edge_tts
import fitz
import re

async def read_aloud_edge(text, filename="chapter_audio.mp3"):
    communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural")
    await communicate.save(filename)
    os.system(f"start {filename}")




def extract_chapters(pdf_path):
    doc = fitz.open(pdf_path)
    text = "\n".join([page.get_text() for page in doc])

    # Simple regex for chapters (you can improve it)
    chapters = re.split(r'(Chapter\s+\d+)', text)
    
    combined = []
    for i in range(1, len(chapters), 2):
        chapter_title = chapters[i].strip()
        chapter_text = chapters[i+1].strip()
        combined.append((chapter_title, chapter_text))
    return dict(combined)
