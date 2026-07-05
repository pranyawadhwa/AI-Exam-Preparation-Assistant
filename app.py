# # ==========================================================
# # IMPORTS
# # ==========================================================

# import streamlit as st
# import streamlit.components.v1 as components
# from pypdf import PdfReader
# from sentence_transformers import SentenceTransformer
# import chromadb
# import google.generativeai as genai
# import os
# import io
# import re
# import time
# from datetime import datetime
# from dotenv import load_dotenv

# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import mm
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_LEFT, TA_CENTER


# # ==========================================================
# # LOAD ENVIRONMENT VARIABLES
# # ==========================================================

# load_dotenv()


# # ==========================================================
# # PAGE CONFIGURATION
# # ==========================================================

# st.set_page_config(
#     page_title="AI Exam Preparation Assistant",
#     page_icon="📘",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )


# # ==========================================================
# # GEMINI CONFIGURATION
# # ==========================================================

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# gemini_model = genai.GenerativeModel("gemini-2.5-flash")


# # ==========================================================
# # LOAD EMBEDDING MODEL
# # ==========================================================

# @st.cache_resource
# def load_model():
#     return SentenceTransformer("all-MiniLM-L6-v2")

# model = load_model()


# # ==========================================================
# # SESSION STATE
# # ==========================================================

# default_states = {
#     "documents":           {},
#     "collection_ready":    False,
#     "ai_responses":        0,
#     "searches_done":       0,
#     "summaries_done":      0,
#     "questions_done":      0,   # Day 18: track questions
#     "mcqs_done":           0,   # Day 18: track MCQs
#     "memory_tricks_done":  0,   # Day 18: track memory tricks
#     "search_scope":        "All Notes",
#     "pending_delete":      None,
#     "workspace_cards":     [],
#     "focus_section":       None,
#     "duplicate_notice":    None,
#     # Day 18: History & Session Management
#     "study_history":       [],   # [{time, type, pdf_name, card_id}]
#     "show_history":        False,
#     "highlighted_card":    None, # card_id to highlight briefly
#     "confirm_clear_all":   False,
#     "session_start":       datetime.now().strftime("%H:%M"),
# }

# for key, value in default_states.items():
#     if key not in st.session_state:
#         st.session_state[key] = value


# # ==========================================================
# # HELPER FUNCTIONS
# # ==========================================================

# def chunk_text(text, chunk_size=1000):
#     chunks = []
#     for i in range(0, len(text), chunk_size):
#         chunks.append(text[i:i + chunk_size])
#     return chunks


# @st.cache_data
# def process_pdf(file_bytes, file_name):
#     import io as _io
#     reader = PdfReader(_io.BytesIO(file_bytes))
#     text = ""
#     for page in reader.pages:
#         extracted = page.extract_text()
#         if extracted:
#             text += extracted
#     chunks = chunk_text(text)
#     return chunks, len(reader.pages)


# @st.cache_data
# def generate_embeddings(chunks_tuple):
#     chunks = list(chunks_tuple)
#     embeddings = model.encode(chunks)
#     return embeddings


# def time_ago(timestamp_str):
#     if not timestamp_str:
#         return ""
#     try:
#         then = datetime.strptime(timestamp_str, "%H:%M")
#         now  = datetime.now()
#         diff = (now.hour * 60 + now.minute) - (then.hour * 60 + then.minute)
#         if diff <= 0:
#             return "just now"
#         if diff == 1:
#             return "1 min ago"
#         return f"{diff} min ago"
#     except Exception:
#         return ""


# def add_workspace_card(card_type, title, content, color):
#     card_id = f"{card_type}_{int(time.time()*1000)}"
#     st.session_state.workspace_cards.append({
#         "id":        card_id,
#         "type":      card_type,
#         "title":     title,
#         "content":   content,
#         "color":     color,
#         "time":      datetime.now().strftime("%H:%M"),
#         "collapsed": False,
#     })
#     st.session_state.ai_responses += 1
#     return card_id


# def log_history(response_type, card_id):
#     """Day 18: Append one history record after a successful AI generation."""
#     st.session_state.study_history.append({
#         "time":     datetime.now().strftime("%H:%M"),
#         "type":     response_type,
#         "pdf_name": st.session_state.search_scope,
#         "card_id":  card_id,
#     })


# def card_exists(card_id):
#     """Day 18: Check whether a workspace card is still present."""
#     return any(c["id"] == card_id for c in st.session_state.workspace_cards)


# def full_reset():
#     """
#     Day 18: Reset the entire session to first-launch state.
#     Clears ChromaDB, caches, all session state keys.
#     """
#     try:
#         client = chromadb.PersistentClient(path="./chroma_db")
#         collection = client.get_or_create_collection(name="notes")
#         existing = collection.get()
#         if existing["ids"]:
#             collection.delete(ids=existing["ids"])
#     except Exception:
#         pass

#     process_pdf.clear()
#     generate_embeddings.clear()

#     keys_to_reset = [
#         "documents", "collection_ready", "ai_responses",
#         "searches_done", "summaries_done", "questions_done",
#         "mcqs_done", "memory_tricks_done", "search_scope",
#         "pending_delete", "workspace_cards", "focus_section",
#         "duplicate_notice", "study_history", "show_history",
#         "highlighted_card", "confirm_clear_all",
#     ]
#     for k in keys_to_reset:
#         if k in st.session_state:
#             del st.session_state[k]

#     # Also clear uploader widget
#     st.session_state.pop("pdf_uploader", None)
#     st.session_state.pop("question_input", None)


# def show_error(error_type):
#     messages = {
#         "api_quota":      "⚠️ Gemini API quota exceeded. Please wait a few minutes and try again.",
#         "api_key":        "🔑 Invalid or missing API key. Please check your .env file.",
#         "no_answer":      "🔍 No relevant answer found in the uploaded notes.",
#         "empty_question": "✏️ Please enter a question before searching.",
#         "no_docs":        "📂 Please upload at least one PDF before using this feature.",
#         "general":        "❌ Something went wrong. Please try again.",
#     }
#     st.error(messages.get(error_type, messages["general"]))


# def handle_gemini_error(e):
#     err = str(e).lower()
#     if "quota" in err or "429" in err or "rate" in err:
#         show_error("api_quota")
#     elif "api_key" in err or "credential" in err or "401" in err:
#         show_error("api_key")
#     else:
#         st.error(f"❌ Unexpected error: {e}")


# def get_active_chunks():
#     if st.session_state.search_scope == "All Notes":
#         return {name: data["chunks"] for name, data in st.session_state.documents.items()}
#     else:
#         name = st.session_state.search_scope
#         if name in st.session_state.documents:
#             return {name: st.session_state.documents[name]["chunks"]}
#         return {}


# def delete_document(fname):
#     client = chromadb.PersistentClient(path="./chroma_db")
#     collection = client.get_or_create_collection(name="notes")
#     existing = collection.get(where={"source": fname})
#     if existing["ids"]:
#         collection.delete(ids=existing["ids"])
#     if fname in st.session_state.documents:
#         del st.session_state.documents[fname]
#     process_pdf.clear()
#     generate_embeddings.clear()
#     if st.session_state.search_scope == fname:
#         st.session_state.search_scope = "All Notes"
#     st.session_state.pop("pdf_uploader", None)
#     if len(st.session_state.documents) == 0:
#         st.session_state.collection_ready = False


# # ==========================================================
# # PDF EXPORT FUNCTIONS
# # ==========================================================

# def _clean_inline(text):
#     text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
#     text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
#     text = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', text)
#     text = re.sub(r'`(.+?)`',       r'\1',         text)
#     text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1',      text)
#     return text.strip()


# def _get_styles():
#     base = getSampleStyleSheet()
#     return {
#         "app_title": ParagraphStyle("AppTitle", parent=base["Normal"],
#             fontSize=16, leading=22, fontName="Helvetica-Bold",
#             textColor=colors.HexColor("#1246CC"), spaceAfter=2, alignment=TA_LEFT),
#         "card_title": ParagraphStyle("CardTitle", parent=base["Normal"],
#             fontSize=13, leading=18, fontName="Helvetica-Bold",
#             textColor=colors.HexColor("#1E3A5F"), spaceBefore=6, spaceAfter=3),
#         "meta": ParagraphStyle("Meta", parent=base["Normal"],
#             fontSize=9, leading=13, fontName="Helvetica",
#             textColor=colors.HexColor("#6B7280"), spaceAfter=2),
#         "section": ParagraphStyle("Section", parent=base["Normal"],
#             fontSize=12, leading=17, fontName="Helvetica-Bold",
#             textColor=colors.HexColor("#1E3A5F"), spaceBefore=8, spaceAfter=3),
#         "heading": ParagraphStyle("Heading", parent=base["Normal"],
#             fontSize=11, leading=15, fontName="Helvetica-Bold",
#             textColor=colors.HexColor("#1F2937"), spaceBefore=5, spaceAfter=2),
#         "body": ParagraphStyle("Body", parent=base["Normal"],
#             fontSize=10, leading=15, fontName="Helvetica",
#             textColor=colors.HexColor("#1F2937"), spaceAfter=3, wordWrap="CJK"),
#         "bullet": ParagraphStyle("Bullet", parent=base["Normal"],
#             fontSize=10, leading=15, fontName="Helvetica",
#             textColor=colors.HexColor("#1F2937"),
#             leftIndent=16, bulletIndent=6, spaceAfter=2, wordWrap="CJK"),
#         "footer": ParagraphStyle("Footer", parent=base["Normal"],
#             fontSize=8, leading=11, fontName="Helvetica-Oblique",
#             textColor=colors.HexColor("#9CA3AF"), alignment=TA_CENTER),
#     }


# def _markdown_to_flowables(text, styles):
#     flowables = []
#     for line in text.split("\n"):
#         h = re.match(r'^(#{1,6})\s+(.*)', line)
#         if h:
#             level = len(h.group(1))
#             flowables.append(Paragraph(_clean_inline(h.group(2)),
#                 styles["section"] if level <= 2 else styles["heading"]))
#             continue
#         if re.match(r'^[-=]{3,}$', line.strip()):
#             flowables += [Spacer(1, 2*mm),
#                           HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1")),
#                           Spacer(1, 2*mm)]
#             continue
#         b = re.match(r'^[\*\-•]\s+(.*)', line)
#         if b:
#             flowables.append(Paragraph(f"• {_clean_inline(b.group(1))}", styles["bullet"]))
#             continue
#         n = re.match(r'^(\d+)\.\s+(.*)', line)
#         if n:
#             flowables.append(Paragraph(f"{n.group(1)}. {_clean_inline(n.group(2))}", styles["bullet"]))
#             continue
#         if line.strip() == "":
#             flowables.append(Spacer(1, 3*mm))
#             continue
#         clean = _clean_inline(line)
#         if clean:
#             flowables.append(Paragraph(clean, styles["body"]))
#     return flowables


# def _build_header(styles, card_title, scope, generated_time):
#     today = datetime.now().strftime("%Y-%m-%d %H:%M")
#     return [
#         Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
#         Paragraph(card_title, styles["card_title"]),
#         Paragraph(f"Generated: {generated_time}  |  Exported: {today}", styles["meta"]),
#         Paragraph(f"Source: {scope}", styles["meta"]),
#         Spacer(1, 4*mm),
#         HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D74DA")),
#         Spacer(1, 5*mm),
#     ]


# def _build_footer(styles):
#     return [
#         Spacer(1, 8*mm),
#         HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1")),
#         Spacer(1, 2*mm),
#         Paragraph("Generated by AI Exam Preparation Assistant", styles["footer"]),
#     ]


# def build_pdf_single(card, scope):
#     buf = io.BytesIO()
#     doc = SimpleDocTemplate(buf, pagesize=A4,
#         leftMargin=20*mm, rightMargin=20*mm,
#         topMargin=20*mm, bottomMargin=20*mm,
#         title=card["title"])
#     styles = _get_styles()
#     story  = _build_header(styles, card["title"], scope, card["time"])
#     story += _markdown_to_flowables(card["content"], styles)
#     story += _build_footer(styles)
#     doc.build(story)
#     buf.seek(0)
#     return buf


# def build_pdf_all(cards, scope):
#     buf = io.BytesIO()
#     doc = SimpleDocTemplate(buf, pagesize=A4,
#         leftMargin=20*mm, rightMargin=20*mm,
#         topMargin=20*mm, bottomMargin=20*mm,
#         title="AI Exam Preparation Assistant — Full Export")
#     styles = _get_styles()
#     today  = datetime.now().strftime("%Y-%m-%d %H:%M")
#     story  = [
#         Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
#         Paragraph("Full Study Export", styles["card_title"]),
#         Paragraph(f"Exported: {today}  |  Source: {scope}", styles["meta"]),
#         Spacer(1, 4*mm),
#         HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D74DA")),
#         Spacer(1, 6*mm),
#     ]
#     for i, card in enumerate(cards):
#         if i > 0:
#             story += [Spacer(1, 6*mm),
#                       HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8")),
#                       Spacer(1, 4*mm)]
#         story.append(Paragraph(card["title"], styles["section"]))
#         story.append(Paragraph(f"Generated: {card['time']}", styles["meta"]))
#         story.append(Spacer(1, 3*mm))
#         story += _markdown_to_flowables(card["content"], styles)
#     story += _build_footer(styles)
#     doc.build(story)
#     buf.seek(0)
#     return buf


# def safe_filename(title):
#     stem = re.sub(r'[^\w\s-]', '', title).strip()
#     stem = re.sub(r'\s+', '_', stem)
#     return stem or "export"


# # ==========================================================
# # CUSTOM CSS
# # ==========================================================

# st.markdown("""
# <style>

# @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

# * { font-family: 'Inter', 'Segoe UI', sans-serif; box-sizing: border-box; }

# .stApp { background: #0B0E18; }

# section[data-testid="stSidebar"] {
#     background: #10141F;
#     border-right: 1px solid #1E2438;
#     width: 240px !important;
# }
# section[data-testid="stSidebar"] * { color: #8A94A8 !important; }
# section[data-testid="stSidebar"] h2,
# section[data-testid="stSidebar"] h3 { color: #FFFFFF !important; font-weight: 700; }
# section[data-testid="stSidebar"] hr { border-color: #1E2438 !important; margin: 10px 0; }
# section[data-testid="stSidebar"] .stAlert {
#     background: #161B2C !important;
#     border: 1px solid #1E2438 !important;
#     border-radius: 10px;
# }
# section[data-testid="stSidebar"] .stButton > button {
#     background: transparent !important;
#     border: none !important;
#     color: #8A94A8 !important;
#     text-align: left !important;
#     justify-content: flex-start !important;
#     padding: 8px 10px !important;
#     height: auto !important;
#     font-size: 13px !important;
#     font-weight: 500 !important;
#     border-radius: 8px !important;
#     box-shadow: none !important;
# }
# section[data-testid="stSidebar"] .stButton > button:hover {
#     background: rgba(45,116,218,0.12) !important;
#     color: #5B9BF8 !important;
#     transform: none !important;
# }

# .block-container { padding: 1.2rem 2rem 2rem 2rem; max-width: 1400px; }
# .stApp, .stApp p, .stApp label { color: #CBD5E1; }

# .app-header {
#     background: linear-gradient(130deg, #1246CC 0%, #2D74DA 55%, #5B9BF8 100%);
#     padding: 28px 40px;
#     border-radius: 18px;
#     margin-bottom: 14px;
#     box-shadow: 0 6px 40px rgba(18,70,204,0.4);
#     position: relative;
#     overflow: hidden;
# }
# .app-header::after {
#     content: '📘';
#     position: absolute;
#     right: 40px; top: 50%;
#     transform: translateY(-50%);
#     font-size: 72px;
#     opacity: 0.12;
# }
# .app-header-greeting {
#     font-size: 13px; font-weight: 600; color: #A8C8FF;
#     letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px;
# }
# .app-header h1 {
#     margin: 0 0 6px 0; font-size: 28px; font-weight: 800;
#     color: #FFFFFF; letter-spacing: -0.5px;
# }
# .app-header p { margin: 0; font-size: 15px; color: #C8DEFF; max-width: 560px; line-height: 1.55; }

# .card {
#     background: #131826; border: 1px solid #1E2438;
#     border-radius: 16px; padding: 22px; height: 100%;
# }
# .card-title {
#     font-size: 15px; font-weight: 700; color: #FFFFFF;
#     margin-bottom: 16px; letter-spacing: -0.1px;
# }

# .empty-state { text-align: center; padding: 28px 16px; color: #3A4560; }
# .empty-state-icon { font-size: 36px; margin-bottom: 10px; }
# .empty-state-text { font-size: 13px; color: #4A5578; line-height: 1.5; }

# .note-item {
#     background: #0A1F14; border: 1px solid #1A5C38;
#     border-radius: 12px; padding: 12px 14px; margin-bottom: 8px;
# }
# .note-item-name {
#     font-size: 13px; font-weight: 600; color: #4ADE80; margin-bottom: 3px;
#     white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
# }
# .note-item-meta { font-size: 11px; color: #5A7A60; }

# .compact-notice {
#     background: #161B2C; border: 1px solid #2A3555;
#     border-radius: 8px; padding: 6px 12px;
#     font-size: 12px; color: #7B88A0; margin-top: 6px;
# }

# /* Day 18: History panel */
# .history-panel {
#     background: #131826;
#     border: 1px solid #1E2438;
#     border-radius: 16px;
#     padding: 20px;
#     margin-bottom: 16px;
# }
# .history-entry {
#     background: #0B0E18;
#     border: 1px solid #1E2438;
#     border-radius: 10px;
#     padding: 10px 14px;
#     margin-bottom: 8px;
#     display: flex;
#     align-items: center;
#     justify-content: space-between;
# }
# .history-entry-info { flex: 1; }
# .history-time { font-size: 11px; color: #4A5578; margin-bottom: 2px; }
# .history-type { font-size: 13px; font-weight: 600; color: #E2E8F0; }
# .history-pdf  { font-size: 11px; color: #7B88A0; margin-top: 2px;
#     white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }

# /* Day 18: Welcome card */
# .welcome-card {
#     background: #131826;
#     border: 1px solid #1E2438;
#     border-left: 3px solid #2D74DA;
#     border-radius: 12px;
#     padding: 14px 18px;
#     margin-bottom: 14px;
# }
# .welcome-title { font-size: 14px; font-weight: 700; color: #FFFFFF; margin-bottom: 4px; }
# .welcome-sub   { font-size: 12px; color: #6B7280; }
# .welcome-last  { font-size: 12px; color: #7B88A0; margin-top: 6px; }

# /* Day 18: Confirmation dialog */
# .confirm-box {
#     background: #1A0A0A;
#     border: 1px solid #5C2626;
#     border-radius: 14px;
#     padding: 20px;
#     margin-bottom: 14px;
# }
# .confirm-title { font-size: 15px; font-weight: 700; color: #F87171; margin-bottom: 8px; }
# .confirm-list  { font-size: 13px; color: #9CA3AF; line-height: 1.8; }

# /* Day 18: Highlighted card pulse */
# .study-card-highlight {
#     box-shadow: 0 0 0 2px #4F8EF7, 0 0 16px rgba(79,142,247,0.4) !important;
#     transition: box-shadow 0.3s ease;
# }

# .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
# .stat-box {
#     background: #0B0E18; border: 1px solid #1E2438;
#     border-radius: 10px; padding: 12px 10px; text-align: center; transition: border-color 0.2s;
# }
# .stat-box:hover { border-color: #2D74DA; }
# .stat-val { font-size: 22px; font-weight: 700; color: #4F8EF7; line-height: 1; }
# .stat-lbl { font-size: 11px; color: #5A6880; margin-top: 3px; font-weight: 500; }

# .badge { display: inline-block; border-radius: 20px; padding: 2px 10px; font-size: 11px; font-weight: 600; }
# .badge-ready  { background:#0A1F14; color:#4ADE80; border:1px solid #1A5C38; }
# .badge-waiting{ background:#1A140A; color:#FBBF24; border:1px solid #5C4010; }

# .section-heading {
#     font-size: 19px; font-weight: 700; color: #FFFFFF;
#     margin: 14px 0 10px 0; letter-spacing: -0.3px;
#     display: flex; align-items: center; gap: 8px;
# }

# .ask-bar-card {
#     background: #131826; border: 1px solid #1E2438;
#     border-radius: 16px; padding: 22px; margin-bottom: 16px;
# }

# .tool-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
# .tool-card {
#     background: #131826; border: 1px solid #1E2438;
#     border-radius: 14px; padding: 18px 16px;
#     transition: border-color 0.2s, background 0.2s; cursor: pointer;
# }
# .tool-card:hover { border-color: #2D74DA; background: #161D30; }
# .tool-card-icon  { font-size: 22px; margin-bottom: 8px; }
# .tool-card-title { font-size: 14px; font-weight: 700; color: #FFFFFF; margin-bottom: 3px; }
# .tool-card-desc  { font-size: 12px; color: #5A6880; line-height: 1.4; }

# .stButton > button {
#     width: 100%; height: 44px; border-radius: 10px;
#     background: #1A56DB; color: #FFFFFF !important;
#     font-size: 14px; font-weight: 600; border: none;
#     transition: background 0.2s, transform 0.1s;
# }
# .stButton > button:hover { background: #1446BF; transform: translateY(-1px); }
# .stButton > button:active { transform: translateY(0); }

# .clear-all-btn > button {
#     background: transparent !important; border: 1px solid #2A1A1A !important;
#     color: #F87171 !important; height: 36px !important; font-size: 13px !important;
# }
# .clear-all-btn > button:hover { background: #1A0A0A !important; }

# .delete-note-btn > button {
#     background: transparent !important; border: 1px solid #2A1A1A !important;
#     color: #F87171 !important; height: 32px !important; font-size: 12px !important;
# }
# .delete-note-btn > button:hover { background: #1A0A0A !important; }

# .stDownloadButton > button {
#     width: 100%; height: 44px; border-radius: 10px;
#     background: #1E2438 !important; color: #A0AABB !important;
#     font-size: 14px !important; font-weight: 600 !important;
#     border: 1px solid #2A3555 !important;
#     transition: background 0.2s, color 0.2s !important;
# }
# .stDownloadButton > button:hover {
#     background: #2A3555 !important; color: #E2E8F0 !important;
#     transform: translateY(-1px) !important;
# }
# .stDownloadButton > button:active { transform: translateY(0) !important; }

# .stTextInput > div > div > input {
#     border-radius: 10px; background: #0B0E18 !important;
#     border: 1px solid #1E2438 !important; color: #E2E8F0 !important;
#     font-size: 15px; padding: 10px 14px;
# }
# .stTextInput > div > div > input::placeholder { color: #3A4560 !important; }
# .stTextInput > div > div > input:focus {
#     border-color: #2D74DA !important;
#     box-shadow: 0 0 0 2px rgba(45,116,218,0.2) !important;
# }

# .stSelectbox > div > div {
#     background: #0B0E18 !important; border: 1px solid #1E2438 !important;
#     border-radius: 10px !important; color: #E2E8F0 !important;
# }

# [data-testid="stFileUploader"] {
#     background: #0B0E18; border: 2px dashed #1E2438;
#     border-radius: 12px; padding: 6px; transition: border-color 0.2s;
# }
# [data-testid="stFileUploader"]:hover { border-color: #2D74DA; }
# [data-testid="stFileUploader"] * { color: #4A5578 !important; }

# .workspace-title { font-size: 17px; font-weight: 700; color: #FFFFFF; }
# .workspace-sub   { font-size: 12px; color: #4A5578; margin-top: 2px; }

# .study-card {
#     border-radius: 14px;
#     border-left-width: 3px; border-left-style: solid;
#     border-top: 1px solid #1E2438; border-right: 1px solid #1E2438;
#     border-bottom: 1px solid #1E2438;
#     background: #131826; margin-bottom: 14px; overflow: hidden;
# }
# .study-card-header {
#     display: flex; align-items: center;
#     justify-content: space-between; padding: 14px 18px;
# }
# .study-card-left { display: flex; align-items: center; gap: 10px; }
# .study-card-title{ font-size: 14px; font-weight: 700; color: #FFFFFF; }
# .study-card-time { font-size: 11px; color: #3A4560; margin-top: 2px; }
# .study-card-body { padding: 0 18px 18px 18px; color: #C9D1E0; font-size: 14px; line-height: 1.7; }
# .study-card-divider { height: 1px; background: #1E2438; margin: 0 18px; }

# .card-answer       { border-left-color: #2D74DA; }
# .card-summary      { border-left-color: #10B981; }
# .card-questions    { border-left-color: #F59E0B; }
# .card-mcqs         { border-left-color: #8B5CF6; }
# .card-memorytricks { border-left-color: #F43F5E; }

# .copy-toast {
#     background: #0A1F14; border: 1px solid #1A5C38; color: #4ADE80;
#     border-radius: 8px; padding: 6px 12px; font-size: 12px;
#     text-align: center; margin-bottom: 8px;
# }

# .nav-section {
#     font-size: 10px; font-weight: 700; color: #2A3555 !important;
#     letter-spacing: 1.2px; text-transform: uppercase; padding: 6px 0 4px 0;
# }
# .nav-item {
#     padding: 8px 10px; border-radius: 8px; margin-bottom: 2px;
#     font-size: 13px; font-weight: 500; color: #8A94A8 !important;
#     display: flex; align-items: center; gap: 8px;
# }
# .nav-active {
#     background: rgba(45,116,218,0.15) !important;
#     color: #5B9BF8 !important;
#     border-left: 2px solid #2D74DA; padding-left: 8px;
# }
# .nav-disabled { color: #2A3555 !important; cursor: not-allowed; }
# .soon-badge {
#     font-size: 9px; background: #161B2C; color: #3A4560 !important;
#     border: 1px solid #1E2438; border-radius: 20px;
#     padding: 1px 6px; margin-left: auto;
# }
# .version-box {
#     background: #0B0E18; border: 1px solid #1E2438;
#     border-radius: 10px; padding: 12px 14px; margin-top: 6px;
# }
# .version-row { display: flex; justify-content: space-between; font-size: 11px; color: #3A4560; margin-bottom: 3px; }
# .version-val { color: #6A7A98 !important; }

# [data-testid="stExpander"] {
#     background: #131826 !important; border: 1px solid #1E2438 !important; border-radius: 10px !important;
# }
# .streamlit-expanderHeader { color: #CBD5E1 !important; background: #131826 !important; }

# [data-testid="metric-container"] {
#     background: #0B0E18; border-radius: 10px; padding: 12px; border: 1px solid #1E2438;
# }
# [data-testid="metric-container"] label { color: #4A5578 !important; font-size: 12px; }
# [data-testid="stMetricValue"] { color: #4F8EF7 !important; font-weight: 700; }

# .stSpinner > div { border-top-color: #2D74DA !important; }
# hr { border-color: #1E2438 !important; margin: 12px 0; }
# h2, h3 { color: #FFFFFF !important; }
# .stAlert { border-radius: 10px; }

# ::-webkit-scrollbar { width: 5px; height: 5px; }
# ::-webkit-scrollbar-track { background: #0B0E18; }
# ::-webkit-scrollbar-thumb { background: #1E2438; border-radius: 4px; }
# ::-webkit-scrollbar-thumb:hover { background: #2A3450; }

# .app-footer {
#     text-align: center; padding: 16px 0 8px 0;
#     border-top: 1px solid #1E2438; margin-top: 16px;
#     font-size: 12px; color: #2A3555;
# }

# </style>
# """, unsafe_allow_html=True)


# # ==========================================================
# # SIDEBAR
# # ==========================================================

# with st.sidebar:
#     st.markdown("## 📘 Exam Assistant")
#     st.caption("Your personal study companion")
#     st.divider()

#     st.markdown('<div class="nav-section">Notes</div>', unsafe_allow_html=True)
#     st.markdown('<div class="nav-item nav-active">📂 Upload Notes</div>', unsafe_allow_html=True)
#     st.markdown('<div class="nav-item nav-disabled">📚 Notes Library <span class="soon-badge">Soon</span></div>', unsafe_allow_html=True)

#     st.markdown('<div class="nav-section" style="margin-top:8px">Study Tools</div>', unsafe_allow_html=True)

#     if st.button("❓ Ask Questions",   key="nav_ask",           use_container_width=True):
#         st.session_state.focus_section = "ask";           st.rerun()
#     if st.button("📝 Summary",          key="nav_summary",       use_container_width=True):
#         st.session_state.focus_section = "summary";       st.rerun()
#     if st.button("🎯 MCQs",             key="nav_mcqs",          use_container_width=True):
#         st.session_state.focus_section = "mcqs";          st.rerun()
#     if st.button("🧠 Memory Tricks",    key="nav_memory_tricks", use_container_width=True):
#         st.session_state.focus_section = "memory_tricks"; st.rerun()

#     st.markdown('<div class="nav-item nav-disabled">📅 Study Planner <span class="soon-badge">Soon</span></div>', unsafe_allow_html=True)
#     st.markdown('<div class="nav-item nav-disabled">🗺️ Mind Map <span class="soon-badge">Soon</span></div>',      unsafe_allow_html=True)

#     st.markdown('<div class="nav-section" style="margin-top:8px">Activity</div>', unsafe_allow_html=True)

#     # Day 18: History button is now functional
#     if st.button("🕐 History", key="nav_history", use_container_width=True):
#         st.session_state.show_history = not st.session_state.show_history
#         st.rerun()

#     if st.button("⚙️ Settings", key="nav_settings", use_container_width=True):
#         st.session_state.focus_section = "settings"; st.rerun()

#     st.divider()
#     st.markdown("### Project Info")
#     st.markdown("""
#     <div class="version-box">
#         <div class="version-row">Version  <span class="version-val">1.4.0</span></div>
#         <div class="version-row">Day      <span class="version-val">18 / 30</span></div>
#         <div class="version-row">Status   <span style="color:#4ADE80 !important">● Active</span></div>
#     </div>
#     """, unsafe_allow_html=True)

#     st.write("")
#     st.info("Upload your notes and let AI help you study smarter.")


# # ==========================================================
# # HEADER
# # ==========================================================

# hour = datetime.now().hour
# greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")

# st.markdown(f"""
# <div class="app-header">
#     <div class="app-header-greeting">{greeting}, Student</div>
#     <h1>Ready to Study?</h1>
#     <p>Upload your notes, ask questions, generate summaries, practice questions and MCQs — all powered by AI.</p>
# </div>
# """, unsafe_allow_html=True)


# # ==========================================================
# # Day 18: SESSION WELCOME CARD
# # ==========================================================

# if st.session_state.study_history:
#     last = st.session_state.study_history[-1]
#     last_ago  = time_ago(last["time"])
#     last_text = f"🕒 Last activity: <b>{last['type']}</b> — {last['pdf_name']} — {last_ago}"
#     st.markdown(f"""
#     <div class="welcome-card">
#         <div class="welcome-title">👋 Welcome back!</div>
#         <div class="welcome-sub">Continue studying from where you left off.</div>
#         <div class="welcome-last">{last_text}</div>
#     </div>
#     """, unsafe_allow_html=True)
# else:
#     st.markdown("""
#     <div class="welcome-card">
#         <div class="welcome-title">👋 Welcome!</div>
#         <div class="welcome-sub">Upload a PDF to begin your study session.</div>
#     </div>
#     """, unsafe_allow_html=True)


# # ==========================================================
# # TOP CARDS ROW
# # ==========================================================

# col_upload, col_recent, col_stats = st.columns([1.4, 1.3, 1])

# with col_upload:
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     st.markdown('<div class="card-title">📂 Upload Notes</div>', unsafe_allow_html=True)

#     uploaded_files = st.file_uploader(
#         "Upload PDFs", type=["pdf"],
#         label_visibility="collapsed",
#         accept_multiple_files=True,
#         key="pdf_uploader"
#     )

#     if not uploaded_files:
#         st.markdown("""
#         <div class="empty-state">
#             <div class="empty-state-icon">📄</div>
#             <div class="empty-state-text">Drag your PDFs here<br>or click Browse Files<br><br>Supported: PDF &nbsp;•&nbsp; Max 200 MB each</div>
#         </div>
#         """, unsafe_allow_html=True)

#     if st.session_state.duplicate_notice:
#         st.markdown(
#             f'<div class="compact-notice">ℹ️ {st.session_state.duplicate_notice} already exists</div>',
#             unsafe_allow_html=True
#         )
#         st.session_state.duplicate_notice = None

#     st.markdown("</div>", unsafe_allow_html=True)

# with col_recent:
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     st.markdown('<div class="card-title">📄 Uploaded Notes</div>', unsafe_allow_html=True)

#     if st.session_state.documents:
#         for fname, data in list(st.session_state.documents.items()):
#             if st.session_state.pending_delete == fname:
#                 st.markdown(f"""
#                 <div class="note-item" style="border-color:#5C2626; background:#1A0A0A;">
#                     <div class="note-item-name" style="color:#F87171;">⚠️ Delete {fname}?</div>
#                     <div class="note-item-meta">This will remove the file and its study material.</div>
#                 </div>
#                 """, unsafe_allow_html=True)
#                 dc1, dc2 = st.columns(2)
#                 with dc1:
#                     if st.button("✅ Yes, Delete", key=f"confirm_{fname}", use_container_width=True):
#                         delete_document(fname)
#                         st.session_state.pending_delete = None
#                         st.rerun()
#                 with dc2:
#                     if st.button("✖ Cancel", key=f"cancel_{fname}", use_container_width=True):
#                         st.session_state.pending_delete = None
#                         st.rerun()
#             else:
#                 nc1, nc2 = st.columns([4, 1])
#                 with nc1:
#                     st.markdown(f"""
#                     <div class="note-item">
#                         <div class="note-item-name" title="{fname}">✅ {fname}</div>
#                         <div class="note-item-meta">{data['pages']} pages &nbsp;•&nbsp; {data['file_size']} KB &nbsp;•&nbsp; {time_ago(data['upload_time'])}</div>
#                     </div>
#                     """, unsafe_allow_html=True)
#                 with nc2:
#                     st.markdown('<div class="delete-note-btn">', unsafe_allow_html=True)
#                     if st.button("🗑", key=f"delnote_{fname}", use_container_width=True):
#                         st.session_state.pending_delete = fname
#                         st.rerun()
#                     st.markdown("</div>", unsafe_allow_html=True)
#     else:
#         st.markdown("""
#         <div class="empty-state">
#             <div class="empty-state-icon">📭</div>
#             <div class="empty-state-text">No notes uploaded yet.<br>Upload your first PDF to begin studying.</div>
#         </div>
#         """, unsafe_allow_html=True)

#     st.markdown("</div>", unsafe_allow_html=True)

# # Day 18: Updated statistics — student-friendly labels, includes history count
# with col_stats:
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     st.markdown('<div class="card-title">📊 Statistics</div>', unsafe_allow_html=True)

#     db_badge = (
#         '<span class="badge badge-ready">● Ready</span>'
#         if st.session_state.collection_ready
#         else '<span class="badge badge-waiting">○ Waiting</span>'
#     )
#     total_pages = sum(d["pages"] for d in st.session_state.documents.values())

#     st.markdown(f"""
#     <div class="stat-grid">
#         <div class="stat-box"><div class="stat-val">{len(st.session_state.documents)}</div><div class="stat-lbl">Notes Uploaded</div></div>
#         <div class="stat-box"><div class="stat-val">{total_pages}</div><div class="stat-lbl">Pages Read</div></div>
#         <div class="stat-box"><div class="stat-val">{st.session_state.searches_done}</div><div class="stat-lbl">Questions Asked</div></div>
#         <div class="stat-box"><div class="stat-val">{st.session_state.summaries_done}</div><div class="stat-lbl">Summaries</div></div>
#         <div class="stat-box"><div class="stat-val">{st.session_state.questions_done}</div><div class="stat-lbl">Practice Sets</div></div>
#         <div class="stat-box"><div class="stat-val">{st.session_state.mcqs_done}</div><div class="stat-lbl">MCQ Sets</div></div>
#         <div class="stat-box"><div class="stat-val">{st.session_state.memory_tricks_done}</div><div class="stat-lbl">Memory Sets</div></div>
#         <div class="stat-box"><div class="stat-val">{len(st.session_state.study_history)}</div><div class="stat-lbl">History Entries</div></div>
#     </div>
#     <div style="text-align:center; margin-top:8px; font-size:12px; color:#4A5578;">Study Material &nbsp;{db_badge}</div>
#     """, unsafe_allow_html=True)

#     st.markdown("</div>", unsafe_allow_html=True)


# # ==========================================================
# # PDF PROCESSING
# # ==========================================================

# if uploaded_files:
#     client     = chromadb.PersistentClient(path="./chroma_db")
#     collection = client.get_or_create_collection(name="notes")
#     new_files_processed = False

#     for uploaded_file in uploaded_files:
#         if uploaded_file.name in st.session_state.documents:
#             st.session_state.duplicate_notice = uploaded_file.name
#             continue

#         file_bytes   = uploaded_file.read()
#         file_size_kb = round(len(file_bytes) / 1024, 1)

#         with st.status(f"⚙️ Preparing {uploaded_file.name}...", expanded=True) as status:
#             st.write("📖 Reading PDF...")
#             chunks, num_pages = process_pdf(file_bytes, uploaded_file.name)
#             st.write("🧮 Processing content...")
#             embeddings = generate_embeddings(tuple(chunks))
#             st.write("🗄️ Adding to search index...")
#             collection.add(
#                 documents=chunks,
#                 embeddings=embeddings.tolist(),
#                 metadatas=[{"source": uploaded_file.name} for _ in chunks],
#                 ids=[f"{uploaded_file.name}_{i}" for i in range(len(chunks))]
#             )
#             st.session_state.documents[uploaded_file.name] = {
#                 "chunks":        chunks,
#                 "pages":         num_pages,
#                 "file_size":     file_size_kb,
#                 "upload_time":   datetime.now().strftime("%H:%M"),
#                 "embedding_dim": len(embeddings[0]),
#             }
#             st.session_state.collection_ready = True
#             new_files_processed = True
#             status.update(label=f"✅ {uploaded_file.name} ready!", state="complete", expanded=False)

#     if new_files_processed:
#         st.rerun()


# # ==========================================================
# # SETTINGS PLACEHOLDER
# # ==========================================================

# if st.session_state.focus_section == "settings":
#     st.info("⚙️ Settings page is coming soon.")
#     st.session_state.focus_section = None


# # ==========================================================
# # MAIN WORKSPACE
# # ==========================================================

# if st.session_state.documents:

#     st.markdown('<div class="section-heading">⚙️ Study Workspace</div>', unsafe_allow_html=True)

#     left_panel, right_panel = st.columns([0.62, 1.0])

#     # ── LEFT PANEL ──
#     with left_panel:

#         if st.session_state.focus_section in ("ask", "summary", "mcqs", "memory_tricks"):
#             labels = {
#                 "ask":           "👆 Ask Questions",
#                 "summary":       "👆 Summary",
#                 "mcqs":          "👆 MCQs",
#                 "memory_tricks": "👆 Memory Tricks",
#             }
#             st.markdown(
#                 f'<div style="color:#4F8EF7;font-size:12px;margin-bottom:4px;">'
#                 f'{labels[st.session_state.focus_section]}</div>',
#                 unsafe_allow_html=True
#             )
#             st.session_state.focus_section = None

#         st.markdown('<div class="ask-bar-card">', unsafe_allow_html=True)
#         st.markdown('<div class="card-title">💬 Ask a Question</div>', unsafe_allow_html=True)

#         scope_options = ["All Notes"] + list(st.session_state.documents.keys())
#         if st.session_state.search_scope not in scope_options:
#             st.session_state.search_scope = "All Notes"

#         st.session_state.search_scope = st.selectbox(
#             "Search In", options=scope_options,
#             index=scope_options.index(st.session_state.search_scope)
#         )

#         question     = st.text_input("", placeholder="Ask anything from your uploaded notes...", key="question_input")
#         search_clicked = st.button("🔍 Search Notes", use_container_width=True)
#         st.markdown("</div>", unsafe_allow_html=True)

#         st.markdown("""
#         <div class="tool-grid">
#             <div class="tool-card"><div class="tool-card-icon">📝</div><div class="tool-card-title">Study Summary</div><div class="tool-card-desc">Key concepts from your notes</div></div>
#             <div class="tool-card"><div class="tool-card-icon">❓</div><div class="tool-card-title">Practice Questions</div><div class="tool-card-desc">Short & long answer questions</div></div>
#             <div class="tool-card"><div class="tool-card-icon">🎯</div><div class="tool-card-title">MCQ Practice</div><div class="tool-card-desc">10 multiple choice questions</div></div>
#             <div class="tool-card"><div class="tool-card-icon">🧠</div><div class="tool-card-title">Memory Tricks</div><div class="tool-card-desc">Mnemonics & exam shortcuts</div></div>
#         </div>
#         """, unsafe_allow_html=True)

#         t1, t2 = st.columns(2)
#         with t1:
#             summary_clicked   = st.button("📝 Generate Summary",   use_container_width=True)
#         with t2:
#             questions_clicked = st.button("❓ Practice Questions", use_container_width=True)

#         t3, t4 = st.columns(2)
#         with t3:
#             mcq_clicked           = st.button("🎯 Generate MCQs",       use_container_width=True)
#         with t4:
#             memory_tricks_clicked = st.button("🧠 Memory Tricks",        use_container_width=True)


#     # ── RIGHT PANEL ──
#     with right_panel:

#         # ==========================================================
#         # Day 18: HISTORY PANEL (shown above workspace when toggled)
#         # ==========================================================

#         if st.session_state.show_history:
#             st.markdown('<div class="history-panel">', unsafe_allow_html=True)

#             h_col1, h_col2 = st.columns([2, 1])
#             with h_col1:
#                 st.markdown('<div class="card-title">🕐 Recent Activity</div>', unsafe_allow_html=True)
#             with h_col2:
#                 if st.button("✖ Clear History", key="clear_history", use_container_width=True):
#                     st.session_state.study_history = []
#                     st.rerun()

#             if not st.session_state.study_history:
#                 st.markdown("""
#                 <div class="empty-state" style="padding:20px;">
#                     <div class="empty-state-icon">📭</div>
#                     <div class="empty-state-text">No study activity yet.<br>Generate a response to see history.</div>
#                 </div>
#                 """, unsafe_allow_html=True)
#             else:
#                 # Show most recent first
#                 for idx, entry in enumerate(reversed(st.session_state.study_history)):
#                     ago        = time_ago(entry["time"])
#                     exists     = card_exists(entry["card_id"])
#                     pdf_display = entry["pdf_name"]
#                     if len(pdf_display) > 30:
#                         pdf_display = pdf_display[:27] + "..."

#                     h1, h2 = st.columns([3, 1])
#                     with h1:
#                         st.markdown(f"""
#                         <div class="history-entry">
#                             <div class="history-entry-info">
#                                 <div class="history-time">🕒 {entry['time']} &nbsp;•&nbsp; {ago}</div>
#                                 <div class="history-type">{entry['type']}</div>
#                                 <div class="history-pdf">{pdf_display}</div>
#                             </div>
#                         </div>
#                         """, unsafe_allow_html=True)
#                     with h2:
#                         if exists:
#                             if st.button("Open", key=f"hist_open_{idx}", use_container_width=True):
#                                 # Highlight the card and close history panel
#                                 st.session_state.highlighted_card = entry["card_id"]
#                                 st.session_state.show_history     = False
#                                 st.rerun()
#                         else:
#                             st.markdown(
#                                 '<div style="font-size:11px; color:#4A5578; padding:8px 0; text-align:center;">Deleted</div>',
#                                 unsafe_allow_html=True
#                             )

#             st.markdown("</div>", unsafe_allow_html=True)

#         # Workspace toolbar
#         ws_c1, ws_c2, ws_c3 = st.columns([2, 1, 0.7])

#         with ws_c1:
#             st.markdown("""
#             <div class="workspace-title">🗂️ Study Workspace</div>
#             <div class="workspace-sub">Generated study material appears here as cards.</div>
#             """, unsafe_allow_html=True)

#         with ws_c2:
#             if st.session_state.workspace_cards:
#                 today_str   = datetime.now().strftime("%Y-%m-%d")
#                 all_pdf_buf = build_pdf_all(
#                     st.session_state.workspace_cards,
#                     st.session_state.search_scope
#                 )
#                 st.download_button(
#                     label="📦 Export All (PDF)",
#                     data=all_pdf_buf,
#                     file_name=f"Export_All_{today_str}.pdf",
#                     mime="application/pdf",
#                     use_container_width=True,
#                     key="export_all_pdf"
#                 )
#             else:
#                 st.button("📦 Export All (PDF)", disabled=True,
#                           use_container_width=True, key="export_all_disabled",
#                           help="Generate at least one response before exporting.")

#         with ws_c3:
#             # Day 18: Clear All now shows confirmation
#             if not st.session_state.confirm_clear_all:
#                 st.markdown('<div class="clear-all-btn">', unsafe_allow_html=True)
#                 if st.button("🗑️ Clear All", use_container_width=True, key="clear_all_trigger"):
#                     st.session_state.confirm_clear_all = True
#                     st.rerun()
#                 st.markdown("</div>", unsafe_allow_html=True)
#             else:
#                 st.markdown('<div class="clear-all-btn">', unsafe_allow_html=True)
#                 if st.button("✖ Cancel", use_container_width=True, key="cancel_clear"):
#                     st.session_state.confirm_clear_all = False
#                     st.rerun()
#                 st.markdown("</div>", unsafe_allow_html=True)

#         # Day 18: Confirmation box for Clear Everything
#         if st.session_state.confirm_clear_all:
#             st.markdown("""
#             <div class="confirm-box">
#                 <div class="confirm-title">⚠️ Clear Everything?</div>
#                 <div class="confirm-list">
#                 This will permanently remove:<br>
#                 • All uploaded PDFs<br>
#                 • All AI responses and workspace cards<br>
#                 • All summaries, MCQs, questions, memory tricks<br>
#                 • Study history<br>
#                 • Vector database cache<br>
#                 • All session data
#                 </div>
#             </div>
#             """, unsafe_allow_html=True)

#             conf1, conf2 = st.columns(2)
#             with conf1:
#                 if st.button("🗑️ Clear Everything", key="confirm_clear_all_btn", use_container_width=True):
#                     full_reset()
#                     st.rerun()
#             with conf2:
#                 if st.button("Keep Studying", key="cancel_clear_all_btn", use_container_width=True):
#                     st.session_state.confirm_clear_all = False
#                     st.rerun()

#         # ── Search ──
#         if search_clicked:
#             if not question.strip():
#                 show_error("empty_question")
#             else:
#                 client     = chromadb.PersistentClient(path="./chroma_db")
#                 collection = client.get_or_create_collection(name="notes")

#                 query_filter = None
#                 if st.session_state.search_scope != "All Notes":
#                     query_filter = {"source": st.session_state.search_scope}

#                 with st.spinner("🔍 Searching your notes..."):
#                     query_embedding = model.encode(question)
#                     results = collection.query(
#                         query_embeddings=[query_embedding.tolist()],
#                         n_results=3,
#                         include=["documents", "distances", "metadatas"],
#                         where=query_filter
#                     )

#                 if not results["documents"][0]:
#                     show_error("no_answer")
#                 else:
#                     context = "\n\n".join(results["documents"][0])
#                     prompt = f"""
# You are an expert AI Exam Preparation Assistant.
# Answer the student's question using ONLY the provided notes.
# Rules:
# - Read all retrieved notes carefully before answering.
# - The answer may require combining information from multiple sections.
# - Do not rely on exact keyword matching.
# - Infer the correct answer whenever it is clearly supported by the notes.
# - Never use outside knowledge.
# - If multiple important points exist, present them as bullet points.
# - Keep the explanation clear, structured, and exam-oriented.
# - If the notes do not contain enough information to answer confidently, reply exactly:
# "The answer is not available in the uploaded notes."

# Retrieved Notes:
# {context}

# Question:
# {question}

# Answer:
# """
#                     try:
#                         with st.spinner("🤖 Generating answer..."):
#                             response = gemini_model.generate_content(prompt)

#                         answer_text = response.text + "\n\n---\n**Sources:**\n"
#                         for i, (doc, dist, meta) in enumerate(zip(
#                             results["documents"][0],
#                             results["distances"][0],
#                             results["metadatas"][0]
#                         )):
#                             confidence  = "High" if dist < 0.5 else ("Medium" if dist < 1.0 else "Low")
#                             source_name = meta.get("source", "Unknown")
#                             answer_text += f"\n**Source {i+1}** — {source_name} — Confidence: {confidence}\n> {doc[:200]}...\n"

#                         cid = add_workspace_card("answer", "💬 Answer", answer_text, "card-answer")
#                         log_history("💬 Search Answer", cid)
#                         st.session_state.searches_done += 1
#                         st.rerun()
#                     except Exception as e:
#                         handle_gemini_error(e)

#         # ── Summary ──
#         if summary_clicked:
#             active_chunks = get_active_chunks()
#             if not active_chunks:
#                 show_error("no_docs")
#             else:
#                 try:
#                     with st.spinner("📝 Generating study summary..."):
#                         full_summary = ""
#                         for doc_name, doc_chunks in active_chunks.items():
#                             summary_context = "\n\n".join(doc_chunks)
#                             summary_prompt = f"""
# You are an AI Exam Preparation Assistant.
# Create a concise study summary from the notes.
# Focus on: Main concepts, Important ideas, Key points, Exam-relevant information.

# Notes:
# {summary_context}

# Summary:
# """
#                             resp = gemini_model.generate_content(summary_prompt)
#                             if len(active_chunks) > 1:
#                                 full_summary += f"### 📘 {doc_name}\n\n{resp.text}\n\n---\n\n"
#                             else:
#                                 full_summary += resp.text

#                     cid = add_workspace_card("summary", "📝 Study Summary", full_summary, "card-summary")
#                     log_history("📝 Summary", cid)
#                     st.session_state.summaries_done += 1
#                     st.rerun()
#                 except Exception as e:
#                     handle_gemini_error(e)

#         # ── Questions ──
#         if questions_clicked:
#             active_chunks = get_active_chunks()
#             if not active_chunks:
#                 show_error("no_docs")
#             else:
#                 try:
#                     with st.spinner("❓ Generating practice questions..."):
#                         full_questions = ""
#                         for doc_name, doc_chunks in active_chunks.items():
#                             questions_context = "\n\n".join(doc_chunks)
#                             questions_prompt = f"""
# You are an AI Exam Preparation Assistant.
# Generate important exam-oriented questions from the provided notes.
# Requirements:
# - Generate exactly 5 Short Answer Questions.
# - Generate exactly 5 Long Answer Questions.
# - Do not provide answers.
# - Questions should be based only on the notes.
# - Focus on concepts important for university exams.

# Output Format:
# SHORT ANSWER QUESTIONS
# 1. ...
# 2. ...
# 3. ...
# 4. ...
# 5. ...

# LONG ANSWER QUESTIONS
# 1. ...
# 2. ...
# 3. ...
# 4. ...
# 5. ...

# Notes:
# {questions_context}

# Questions:
# """
#                             resp = gemini_model.generate_content(questions_prompt)
#                             if len(active_chunks) > 1:
#                                 full_questions += f"### 📘 {doc_name}\n\n{resp.text}\n\n---\n\n"
#                             else:
#                                 full_questions += resp.text

#                     cid = add_workspace_card("questions", "❓ Practice Questions", full_questions, "card-questions")
#                     log_history("❓ Practice Questions", cid)
#                     st.session_state.questions_done += 1
#                     st.rerun()
#                 except Exception as e:
#                     handle_gemini_error(e)

#         # ── MCQs ──
#         if mcq_clicked:
#             active_chunks = get_active_chunks()
#             if not active_chunks:
#                 show_error("no_docs")
#             else:
#                 try:
#                     with st.spinner("🎯 Generating MCQs..."):
#                         full_mcqs = ""
#                         for doc_name, doc_chunks in active_chunks.items():
#                             mcq_context = "\n\n".join(doc_chunks)
#                             mcq_prompt = f"""
# You are an AI Exam Preparation Assistant.
# Generate exactly 10 multiple-choice questions from the provided notes.
# Requirements:
# - Questions must be based only on the notes.
# - Generate exactly 10 MCQs.
# - Each question must have exactly 4 options labeled A. B. C. D.
# - Put every option on a separate line.
# - Leave one blank line after each option.
# - After options write: Answer: X

# Example:
# Q1. Question

# A. Option 1

# B. Option 2

# C. Option 3

# D. Option 4

# Answer: B

# Notes:
# {mcq_context}

# MCQs:
# """
#                             resp = gemini_model.generate_content(mcq_prompt)
#                             if len(active_chunks) > 1:
#                                 full_mcqs += f"### 📘 {doc_name}\n\n{resp.text}\n\n---\n\n"
#                             else:
#                                 full_mcqs += resp.text

#                     cid = add_workspace_card("mcqs", "🎯 MCQ Practice", full_mcqs, "card-mcqs")
#                     log_history("🎯 MCQs", cid)
#                     st.session_state.mcqs_done += 1
#                     st.rerun()
#                 except Exception as e:
#                     handle_gemini_error(e)

#         # ── Memory Tricks ──
#         if memory_tricks_clicked:
#             active_chunks = get_active_chunks()
#             if not active_chunks:
#                 show_error("no_docs")
#             else:
#                 try:
#                     with st.spinner("🧠 Generating Memory Tricks..."):
#                         full_memory_tricks = ""
#                         for doc_name, doc_chunks in active_chunks.items():
#                             memory_context = "\n\n".join(doc_chunks)
#                             memory_prompt = f"""
# You are an expert exam mentor helping university students remember topics quickly.
# Your task is to create highly memorable Memory Tricks from the provided notes.
# The goal is NOT to summarize the chapter.
# The goal is to help students remember difficult concepts during exams.
# Generate only information that actually exists in the notes.
# If a topic does not naturally support a mnemonic, create another memory technique instead.

# Use the following techniques wherever appropriate:

# 1. Acronyms
# Create memorable acronyms from important concepts.
# Example:
# SMART
# S – Smart Contracts
# M – Market Access
# A – Automation
# R – Reputation
# T – Transparency

# 2. Mnemonics
# Example:
# Remember "SCALE"
# S → SAR
# C → CNN
# A → Adam Optimizer
# L → Lee Filter
# E → Evaluation Metrics

# 3. Memory Sentences
# Example:
# "Smart Workers Build Trust"
# Smart → Smart Contracts
# Workers → Work Ledger
# Build → Blockchain
# Trust → Transparency

# 4. Number Tricks
# Highlight important years, percentages and values.
# Example:
# 80% → Informal Workforce
# 400 Million → Workers
# 455 Billion → Gig Economy

# 5. Compare Similar Concepts
# Example:
# Blockchain
# ✓ Stores work history
# ✓ Cannot be changed
# Traditional Database
# ✓ Centralized
# ✓ Can be modified

# 6. Exam Keywords
# List only the words students should remember.
# Example:
# Immutable Ledger
# Digital Identity
# Smart Contracts
# Portable Reputation
# Transparency

# 7. Frequently Confused Concepts
# If two concepts are similar, explain how to differentiate them in one line.

# 8. Must Remember Before Exam
# Generate 5–10 extremely important facts that students should remember just before entering the exam hall.

# Requirements:
# - Generate between 8 and 15 memory tricks.
# - Make every trick different.
# - Use headings.
# - Use bullet points.
# - Make the output attractive and easy to revise.
# - Do not generate questions.
# - Do not generate flashcards.
# - Do not explain every topic in detail.
# - Keep every trick short.
# - Everything must come only from the provided notes.

# Notes:
# {memory_context}

# Memory Tricks:
# """
#                             resp = gemini_model.generate_content(memory_prompt)
#                             if len(active_chunks) > 1:
#                                 full_memory_tricks += f"### 📘 {doc_name}\n\n{resp.text}\n\n---\n\n"
#                             else:
#                                 full_memory_tricks += resp.text

#                     cid = add_workspace_card("memorytricks", "🧠 Memory Tricks", full_memory_tricks, "card-memorytricks")
#                     log_history("🧠 Memory Tricks", cid)
#                     st.session_state.memory_tricks_done += 1
#                     st.rerun()
#                 except Exception as e:
#                     handle_gemini_error(e)


#         # ==========================================================
#         # RENDER WORKSPACE CARDS
#         # ==========================================================

#         if not st.session_state.workspace_cards:
#             st.markdown("""
#             <div class="empty-state" style="padding:40px 20px; background:#131826;
#                 border:1px solid #1E2438; border-radius:14px;">
#                 <div class="empty-state-icon">🗂️</div>
#                 <div class="empty-state-text">
#                     Generate your first AI response.<br>
#                     Ask a question or use the tools above.
#                 </div>
#             </div>
#             """, unsafe_allow_html=True)

#         else:
#             today_str = datetime.now().strftime("%Y-%m-%d")

#             for card in list(st.session_state.workspace_cards):
#                 card_id   = card["id"]
#                 collapsed = card.get("collapsed", False)
#                 ago       = time_ago(card["time"])

#                 # Day 18: Add highlight class if this card was opened from history
#                 highlight_class = ""
#                 if st.session_state.highlighted_card == card_id:
#                     highlight_class = "study-card-highlight"
#                     # Auto-clear highlight after one render
#                     st.session_state.highlighted_card = None

#                 st.markdown(f"""
#                 <div class="study-card {card['color']} {highlight_class}" id="card_{card_id}">
#                     <div class="study-card-header">
#                         <div class="study-card-left">
#                             <div>
#                                 <div class="study-card-title">{card['title']}</div>
#                                 <div class="study-card-time">Generated {ago}</div>
#                             </div>
#                         </div>
#                     </div>
#                     <div class="study-card-divider"></div>
#                 </div>
#                 """, unsafe_allow_html=True)

#                 if st.session_state.get(f"copied_{card_id}"):
#                     st.markdown('<div class="copy-toast">✅ Copied Successfully</div>', unsafe_allow_html=True)
#                     if time.time() - st.session_state.get(f"copied_at_{card_id}", 0) > 2:
#                         del st.session_state[f"copied_{card_id}"]

#                 b1, b2, b3, b4 = st.columns([1, 1, 1, 1.2])

#                 with b1:
#                     label = "▶ Expand" if collapsed else "▼ Collapse"
#                     if st.button(label, key=f"col_{card_id}", use_container_width=True):
#                         for c in st.session_state.workspace_cards:
#                             if c["id"] == card_id:
#                                 c["collapsed"] = not c["collapsed"]
#                         st.rerun()

#                 with b2:
#                     if st.button("📋 Copy", key=f"copy_{card_id}", use_container_width=True):
#                         safe_content = card["content"].replace("`", "\\`")
#                         copy_js = f"""
#                         <script>
#                         (function() {{
#                             if (navigator.clipboard && window.isSecureContext) {{
#                                 navigator.clipboard.writeText(`{safe_content}`).catch(function() {{ fallbackCopy(); }});
#                             }} else {{ fallbackCopy(); }}
#                             function fallbackCopy() {{
#                                 var ta = document.createElement("textarea");
#                                 ta.value = `{safe_content}`;
#                                 ta.style.position = "fixed"; ta.style.left = "-9999px";
#                                 document.body.appendChild(ta); ta.focus(); ta.select();
#                                 document.execCommand("copy"); document.body.removeChild(ta);
#                             }}
#                         }})();
#                         </script>
#                         """
#                         components.html(copy_js, height=0)
#                         st.session_state[f"copied_{card_id}"]    = True
#                         st.session_state[f"copied_at_{card_id}"] = time.time()
#                         st.rerun()

#                 with b3:
#                     if st.button("🗑 Delete", key=f"del_{card_id}", use_container_width=True):
#                         st.session_state.workspace_cards = [
#                             c for c in st.session_state.workspace_cards
#                             if c["id"] != card_id
#                         ]
#                         st.session_state.pop(f"copied_{card_id}", None)
#                         st.session_state.pop(f"copied_at_{card_id}", None)
#                         st.rerun()

#                 with b4:
#                     fname_stem = safe_filename(card["title"])
#                     pdf_buf    = build_pdf_single(card, st.session_state.search_scope)
#                     st.download_button(
#                         label="📥 Download PDF",
#                         data=pdf_buf,
#                         file_name=f"{fname_stem}_{today_str}.pdf",
#                         mime="application/pdf",
#                         use_container_width=True,
#                         key=f"dl_pdf_{card_id}"
#                     )

#                 if not collapsed:
#                     st.markdown('<div class="study-card-body">', unsafe_allow_html=True)
#                     st.markdown(card["content"])
#                     st.markdown("</div>", unsafe_allow_html=True)

#                 st.write("")


# # ==========================================================
# # EMPTY STATE (no documents uploaded)
# # ==========================================================

# else:
#     st.markdown("""
#     <div style="text-align:center; padding:50px 20px; background:#131826;
#         border:1px dashed #1E2438; border-radius:18px; margin-top:14px;">
#         <div style="font-size:52px; margin-bottom:16px;">📘</div>
#         <div style="font-size:20px; font-weight:700; color:#FFFFFF; margin-bottom:8px;">
#             Upload your first notes to begin
#         </div>
#         <div style="font-size:14px; color:#4A5578; line-height:1.7; max-width:420px; margin:0 auto;">
#             Drag PDFs into the upload card above.<br>
#             The AI will read your notes and help you study smarter —<br>
#             summaries, questions, MCQs, memory tricks and more.
#         </div>
#     </div>
#     """, unsafe_allow_html=True)


# # ==========================================================
# # FOOTER
# # ==========================================================

# st.markdown("""
# <div class="app-footer">
#     📘 AI Exam Preparation Assistant &nbsp;•&nbsp; Version 1.4 &nbsp;•&nbsp; Built for Students &nbsp;•&nbsp; Day 18 / 30
# </div>
# """, unsafe_allow_html=True)


# ==========================================================
# AI EXAM PREPARATION ASSISTANT  —  Day 19
# Performance optimization, code cleanup, stability
# ==========================================================

# ==========================================================
# IMPORTS
# ==========================================================

import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb
import google.generativeai as genai
import os, io, re, time
from datetime import datetime
from dotenv import load_dotenv

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER

load_dotenv()


# ==========================================================
# CONFIGURATION
# ==========================================================

CHROMA_PATH   = "./chroma_db"
CHUNK_SIZE    = 1000
N_RESULTS     = 3
GEMINI_MODEL  = "gemini-2.5-flash"
EMBED_MODEL   = "all-MiniLM-L6-v2"

st.set_page_config(
    page_title="AI Exam Preparation Assistant",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded"
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel(GEMINI_MODEL)


# ==========================================================
# CACHED RESOURCES  (loaded once per session)
# ==========================================================

@st.cache_resource
def load_embed_model():
    return SentenceTransformer(EMBED_MODEL)

@st.cache_resource
def get_chroma_collection():
    """Single ChromaDB client + collection — reused across all reruns."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name="notes")

embed_model = load_embed_model()
collection  = get_chroma_collection()


# ==========================================================
# SESSION STATE  (grouped logically)
# ==========================================================

_DEFAULTS = {
    # Documents
    "documents":          {},   # {fname: {chunks, pages, file_size, upload_time}}
    "collection_ready":   False,
    # Workspace
    "workspace_cards":    [],   # [{id, type, title, content, color, time, collapsed}]
    "highlighted_card":   None,
    "confirm_clear_all":  False,
    # History
    "study_history":      [],   # [{time, type, pdf_name, card_id}]
    "show_history":       False,
    # Statistics
    "searches_done":      0,
    "summaries_done":     0,
    "questions_done":     0,
    "mcqs_done":          0,
    "memory_tricks_done": 0,
    "ai_responses":       0,
    # Search / UI
    "search_scope":       "All Notes",
    "pending_delete":     None,
    "focus_section":      None,
    "duplicate_notice":   None,
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ==========================================================
# PDF PROCESSING  (cached by content hash — never re-processes)
# ==========================================================

def _chunk_text(text):
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]


@st.cache_data(show_spinner=False)
def _extract_chunks(file_bytes: bytes, file_name: str):
    """Extract text + chunk a PDF. Cached by (bytes, name) — runs once per unique file."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text   = "".join(p.extract_text() or "" for p in reader.pages)
        if not text.strip():
            return [], 0, "empty"
        return _chunk_text(text), len(reader.pages), "ok"
    except Exception as e:
        return [], 0, str(e)


@st.cache_data(show_spinner=False)
def _embed_chunks(chunks_tuple: tuple, _file_name: str):
    """Generate embeddings. Cached by chunk content — runs once per unique chunk set."""
    return embed_model.encode(list(chunks_tuple)).tolist()


def _add_to_chroma(chunks, embeddings, fname):
    """Store chunks in ChromaDB. Deletes existing entries for fname first."""
    existing = collection.get(where={"source": fname})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
    collection.add(
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"source": fname} for _ in chunks],
        ids=[f"{fname}_{i}" for i in range(len(chunks))],
    )


# ==========================================================
# HELPER — Gemini call (shared by all generators)
# ==========================================================

def _call_gemini(prompt: str) -> str | None:
    """Single Gemini call with unified error handling. Returns text or None."""
    try:
        resp = gemini_model.generate_content(prompt)
        return resp.text
    except Exception as e:
        _handle_gemini_error(e)
        return None


def _handle_gemini_error(e):
    err = str(e).lower()
    if "quota" in err or "429" in err or "rate" in err:
        st.error("⚠️ Gemini API quota exceeded. Please wait a few minutes and try again.")
    elif "api_key" in err or "credential" in err or "401" in err:
        st.error("🔑 Invalid or missing API key. Please check your .env file.")
    else:
        st.error("❌ Something went wrong with the AI. Please try again.")


# ==========================================================
# HELPER — Workspace cards
# ==========================================================

def _add_card(card_type, title, content, color) -> str:
    """Append a workspace card and return its id."""
    card_id = f"{card_type}_{int(time.time()*1000)}"
    st.session_state.workspace_cards.append({
        "id": card_id, "type": card_type, "title": title,
        "content": content, "color": color,
        "time": datetime.now().strftime("%H:%M"), "collapsed": False,
    })
    st.session_state.ai_responses += 1
    return card_id


def _log_history(response_type: str, card_id: str):
    st.session_state.study_history.append({
        "time": datetime.now().strftime("%H:%M"),
        "type": response_type,
        "pdf_name": st.session_state.search_scope,
        "card_id": card_id,
    })


def _card_exists(card_id: str) -> bool:
    return any(c["id"] == card_id for c in st.session_state.workspace_cards)


def _get_active_chunks() -> dict:
    scope = st.session_state.search_scope
    if scope == "All Notes":
        return {n: d["chunks"] for n, d in st.session_state.documents.items()}
    doc = st.session_state.documents.get(scope)
    return {scope: doc["chunks"]} if doc else {}


# ==========================================================
# HELPER — Session reset
# ==========================================================

def _full_reset():
    """Wipe everything — equivalent to fresh app launch."""
    try:
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass
    _extract_chunks.clear()
    _embed_chunks.clear()
    for k in list(_DEFAULTS.keys()):
        if k in st.session_state:
            del st.session_state[k]
    for widget in ("pdf_uploader", "question_input"):
        st.session_state.pop(widget, None)


# ==========================================================
# HELPER — Document deletion
# ==========================================================

def _delete_document(fname: str):
    try:
        existing = collection.get(where={"source": fname})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass
    st.session_state.documents.pop(fname, None)
    _extract_chunks.clear()
    _embed_chunks.clear()
    if st.session_state.search_scope == fname:
        st.session_state.search_scope = "All Notes"
    st.session_state.pop("pdf_uploader", None)
    if not st.session_state.documents:
        st.session_state.collection_ready = False


# ==========================================================
# HELPER — time_ago
# ==========================================================

def _time_ago(ts: str) -> str:
    if not ts:
        return ""
    try:
        diff = (datetime.now().hour * 60 + datetime.now().minute) - \
               (datetime.strptime(ts, "%H:%M").hour * 60 + datetime.strptime(ts, "%H:%M").minute)
        if diff <= 0: return "just now"
        if diff == 1: return "1 min ago"
        return f"{diff} min ago"
    except Exception:
        return ""


# ==========================================================
# HELPER — Generator  (shared logic for Summary/Questions/MCQs/Memory)
# ==========================================================

def _run_generator(spinner_text, card_type, card_title, card_color,
                   history_label, stat_key, build_prompt_fn):
    """
    Generic generator:  builds prompt per doc, calls Gemini, creates card.
    build_prompt_fn(doc_name, doc_chunks) -> prompt string
    """
    active = _get_active_chunks()
    if not active:
        st.error("📂 Please upload at least one PDF before using this feature.")
        return

    with st.spinner(spinner_text):
        parts = []
        for doc_name, doc_chunks in active.items():
            prompt = build_prompt_fn(doc_name, doc_chunks)
            text   = _call_gemini(prompt)
            if text is None:
                return   # error already shown
            parts.append(f"### 📘 {doc_name}\n\n{text}\n\n---\n\n" if len(active) > 1 else text)

    content = "".join(parts)
    cid     = _add_card(card_type, card_title, content, card_color)
    _log_history(history_label, cid)
    st.session_state[stat_key] += 1
    st.rerun()


# ==========================================================
# PDF EXPORT HELPERS
# ==========================================================

def _clean_inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`',       r'\1',         text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1',      text)
    return text.strip()


@st.cache_data(show_spinner=False)
def _get_pdf_styles():
    base = getSampleStyleSheet()
    mk   = lambda name, **kw: ParagraphStyle(name, parent=base["Normal"], **kw)
    return {
        "app_title":  mk("AT",  fontSize=16, leading=22, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1246CC"), spaceAfter=2),
        "card_title": mk("CT",  fontSize=13, leading=18, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1E3A5F"), spaceBefore=6, spaceAfter=3),
        "meta":       mk("ME",  fontSize=9,  leading=13, fontName="Helvetica",
                          textColor=colors.HexColor("#6B7280"), spaceAfter=2),
        "section":    mk("SE",  fontSize=12, leading=17, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1E3A5F"), spaceBefore=8, spaceAfter=3),
        "heading":    mk("HE",  fontSize=11, leading=15, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1F2937"), spaceBefore=5, spaceAfter=2),
        "body":       mk("BO",  fontSize=10, leading=15, fontName="Helvetica",
                          textColor=colors.HexColor("#1F2937"), spaceAfter=3, wordWrap="CJK"),
        "bullet":     mk("BU",  fontSize=10, leading=15, fontName="Helvetica",
                          textColor=colors.HexColor("#1F2937"),
                          leftIndent=16, bulletIndent=6, spaceAfter=2, wordWrap="CJK"),
        "footer":     mk("FO",  fontSize=8,  leading=11, fontName="Helvetica-Oblique",
                          textColor=colors.HexColor("#9CA3AF"), alignment=TA_CENTER),
    }


def _md_to_flowables(text: str, styles: dict) -> list:
    out = []
    for line in text.split("\n"):
        if m := re.match(r'^(#{1,6})\s+(.*)', line):
            s = styles["section"] if len(m.group(1)) <= 2 else styles["heading"]
            out.append(Paragraph(_clean_inline(m.group(2)), s)); continue
        if re.match(r'^[-=]{3,}$', line.strip()):
            out += [Spacer(1,2*mm), HRFlowable(width="100%",thickness=0.5,
                    color=colors.HexColor("#CBD5E1")), Spacer(1,2*mm)]; continue
        if m := re.match(r'^[\*\-•]\s+(.*)', line):
            out.append(Paragraph(f"• {_clean_inline(m.group(1))}", styles["bullet"])); continue
        if m := re.match(r'^(\d+)\.\s+(.*)', line):
            out.append(Paragraph(f"{m.group(1)}. {_clean_inline(m.group(2))}", styles["bullet"])); continue
        if not line.strip():
            out.append(Spacer(1,3*mm)); continue
        if c := _clean_inline(line):
            out.append(Paragraph(c, styles["body"]))
    return out


def _pdf_header(styles, title, scope, gen_time) -> list:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return [
        Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
        Paragraph(title, styles["card_title"]),
        Paragraph(f"Generated: {gen_time}  |  Exported: {now}", styles["meta"]),
        Paragraph(f"Source: {scope}", styles["meta"]),
        Spacer(1,4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D74DA")),
        Spacer(1,5*mm),
    ]


def _pdf_footer(styles) -> list:
    return [
        Spacer(1,8*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1")),
        Spacer(1,2*mm),
        Paragraph("Generated by AI Exam Preparation Assistant", styles["footer"]),
    ]


def _make_doc(buf, title) -> SimpleDocTemplate:
    return SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm, title=title)


def build_pdf_single(card: dict, scope: str) -> io.BytesIO:
    buf    = io.BytesIO()
    styles = _get_pdf_styles()
    story  = _pdf_header(styles, card["title"], scope, card["time"])
    story += _md_to_flowables(card["content"], styles)
    story += _pdf_footer(styles)
    _make_doc(buf, card["title"]).build(story)
    buf.seek(0); return buf


def build_pdf_all(cards: list, scope: str) -> io.BytesIO:
    buf    = io.BytesIO()
    styles = _get_pdf_styles()
    now    = datetime.now().strftime("%Y-%m-%d %H:%M")
    story  = [
        Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
        Paragraph("Full Study Export", styles["card_title"]),
        Paragraph(f"Exported: {now}  |  Source: {scope}", styles["meta"]),
        Spacer(1,4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D74DA")),
        Spacer(1,6*mm),
    ]
    for i, card in enumerate(cards):
        if i:
            story += [Spacer(1,6*mm),
                      HRFlowable(width="100%",thickness=1,color=colors.HexColor("#94A3B8")),
                      Spacer(1,4*mm)]
        story += [Paragraph(card["title"], styles["section"]),
                  Paragraph(f"Generated: {card['time']}", styles["meta"]),
                  Spacer(1,3*mm)]
        story += _md_to_flowables(card["content"], styles)
    story += _pdf_footer(styles)
    _make_doc(buf, "Full Export").build(story)
    buf.seek(0); return buf


def _safe_filename(title: str) -> str:
    stem = re.sub(r'[^\w\s-]', '', title).strip()
    return re.sub(r'\s+', '_', stem) or "export"


# ==========================================================
# PROMPTS  (unchanged from Day 18)
# ==========================================================

def _prompt_search(context, question):
    return f"""You are an expert AI Exam Preparation Assistant.
Answer the student's question using ONLY the provided notes.
Rules:
- Read all retrieved notes carefully before answering.
- The answer may require combining information from multiple sections.
- Do not rely on exact keyword matching.
- Infer the correct answer whenever it is clearly supported by the notes.
- Never use outside knowledge.
- If multiple important points exist, present them as bullet points.
- Keep the explanation clear, structured, and exam-oriented.
- If the notes do not contain enough information to answer confidently, reply exactly:
"The answer is not available in the uploaded notes."

Retrieved Notes:
{context}

Question:
{question}

Answer:"""


def _prompt_summary(doc_name, doc_chunks):
    context = "\n\n".join(doc_chunks)
    return f"""You are an AI Exam Preparation Assistant.
Create a concise study summary from the notes.
Focus on: Main concepts, Important ideas, Key points, Exam-relevant information.

Notes:
{context}

Summary:"""


def _prompt_questions(doc_name, doc_chunks):
    context = "\n\n".join(doc_chunks)
    return f"""You are an AI Exam Preparation Assistant.
Generate important exam-oriented questions from the provided notes.
Requirements:
- Generate exactly 5 Short Answer Questions.
- Generate exactly 5 Long Answer Questions.
- Do not provide answers.
- Questions should be based only on the notes.
- Focus on concepts important for university exams.

Output Format:
SHORT ANSWER QUESTIONS
1. ...
2. ...
3. ...
4. ...
5. ...

LONG ANSWER QUESTIONS
1. ...
2. ...
3. ...
4. ...
5. ...

Notes:
{context}

Questions:"""


def _prompt_mcqs(doc_name, doc_chunks):
    context = "\n\n".join(doc_chunks)
    return f"""You are an AI Exam Preparation Assistant.
Generate exactly 10 multiple-choice questions from the provided notes.
Requirements:
- Questions must be based only on the notes.
- Generate exactly 10 MCQs.
- Each question must have exactly 4 options labeled A. B. C. D.
- Put every option on a separate line.
- Leave one blank line after each option.
- After options write: Answer: X

Example:
Q1. Question

A. Option 1

B. Option 2

C. Option 3

D. Option 4

Answer: B

Notes:
{context}

MCQs:"""


def _prompt_memory(doc_name, doc_chunks):
    context = "\n\n".join(doc_chunks)
    return f"""You are an expert exam mentor helping university students remember topics quickly.
Your task is to create highly memorable Memory Tricks from the provided notes.
The goal is NOT to summarize the chapter.
The goal is to help students remember difficult concepts during exams.
Generate only information that actually exists in the notes.
If a topic does not naturally support a mnemonic, create another memory technique instead.

Use the following techniques wherever appropriate:

1. Acronyms — create memorable acronyms from important concepts.
2. Mnemonics — memorable word/phrase associations.
3. Memory Sentences — e.g. "Smart Workers Build Trust".
4. Number Tricks — highlight important years, percentages, values.
5. Compare Similar Concepts — brief side-by-side comparison.
6. Exam Keywords — list only words students must remember.
7. Frequently Confused Concepts — one-line differentiators.
8. Must Remember Before Exam — 5-10 critical facts.

Requirements:
- Generate between 8 and 15 memory tricks.
- Make every trick different.
- Use headings and bullet points.
- Keep every trick short.
- Everything must come only from the provided notes.
- Do not generate questions or flashcards.

Notes:
{context}

Memory Tricks:"""


# ==========================================================
# CSS  (unchanged)
# ==========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family:'Inter','Segoe UI',sans-serif; box-sizing:border-box; }
.stApp { background:#0B0E18; }

section[data-testid="stSidebar"] {
    background:#10141F; border-right:1px solid #1E2438; width:240px !important;
}
section[data-testid="stSidebar"] * { color:#8A94A8 !important; }
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color:#FFFFFF !important; font-weight:700; }
section[data-testid="stSidebar"] hr { border-color:#1E2438 !important; margin:10px 0; }
section[data-testid="stSidebar"] .stAlert {
    background:#161B2C !important; border:1px solid #1E2438 !important; border-radius:10px;
}
section[data-testid="stSidebar"] .stButton > button {
    background:transparent !important; border:none !important; color:#8A94A8 !important;
    text-align:left !important; justify-content:flex-start !important; padding:8px 10px !important;
    height:auto !important; font-size:13px !important; font-weight:500 !important;
    border-radius:8px !important; box-shadow:none !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background:rgba(45,116,218,0.12) !important; color:#5B9BF8 !important; transform:none !important;
}

.block-container { padding:1.2rem 2rem 2rem 2rem; max-width:1400px; }
.stApp,.stApp p,.stApp label { color:#CBD5E1; }

.app-header {
    background:linear-gradient(130deg,#1246CC 0%,#2D74DA 55%,#5B9BF8 100%);
    padding:28px 40px; border-radius:18px; margin-bottom:14px;
    box-shadow:0 6px 40px rgba(18,70,204,0.4); position:relative; overflow:hidden;
}
.app-header::after {
    content:'📘'; position:absolute; right:40px; top:50%;
    transform:translateY(-50%); font-size:72px; opacity:0.12;
}
.app-header-greeting { font-size:13px; font-weight:600; color:#A8C8FF; letter-spacing:1.2px; text-transform:uppercase; margin-bottom:4px; }
.app-header h1 { margin:0 0 6px 0; font-size:28px; font-weight:800; color:#FFFFFF; letter-spacing:-0.5px; }
.app-header p  { margin:0; font-size:15px; color:#C8DEFF; max-width:560px; line-height:1.55; }

.card { background:#131826; border:1px solid #1E2438; border-radius:16px; padding:22px; height:100%; }
.card-title { font-size:15px; font-weight:700; color:#FFFFFF; margin-bottom:16px; letter-spacing:-0.1px; }

.empty-state { text-align:center; padding:28px 16px; }
.empty-state-icon { font-size:36px; margin-bottom:10px; }
.empty-state-text { font-size:13px; color:#4A5578; line-height:1.5; }

.note-item { background:#0A1F14; border:1px solid #1A5C38; border-radius:12px; padding:12px 14px; margin-bottom:8px; }
.note-item-name { font-size:13px; font-weight:600; color:#4ADE80; margin-bottom:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.note-item-meta { font-size:11px; color:#5A7A60; }

.compact-notice { background:#161B2C; border:1px solid #2A3555; border-radius:8px; padding:6px 12px; font-size:12px; color:#7B88A0; margin-top:6px; }

.history-panel { background:#131826; border:1px solid #1E2438; border-radius:16px; padding:20px; margin-bottom:16px; }
.history-entry { background:#0B0E18; border:1px solid #1E2438; border-radius:10px; padding:10px 14px; margin-bottom:8px; }
.history-time  { font-size:11px; color:#4A5578; margin-bottom:2px; }
.history-type  { font-size:13px; font-weight:600; color:#E2E8F0; }
.history-pdf   { font-size:11px; color:#7B88A0; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:180px; }

.welcome-card { background:#131826; border:1px solid #1E2438; border-left:3px solid #2D74DA; border-radius:12px; padding:14px 18px; margin-bottom:14px; }
.welcome-title { font-size:14px; font-weight:700; color:#FFFFFF; margin-bottom:4px; }
.welcome-sub   { font-size:12px; color:#6B7280; }
.welcome-last  { font-size:12px; color:#7B88A0; margin-top:6px; }

.confirm-box   { background:#1A0A0A; border:1px solid #5C2626; border-radius:14px; padding:20px; margin-bottom:14px; }
.confirm-title { font-size:15px; font-weight:700; color:#F87171; margin-bottom:8px; }
.confirm-list  { font-size:13px; color:#9CA3AF; line-height:1.8; }

.stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.stat-box  { background:#0B0E18; border:1px solid #1E2438; border-radius:10px; padding:12px 10px; text-align:center; transition:border-color 0.2s; }
.stat-box:hover { border-color:#2D74DA; }
.stat-val  { font-size:22px; font-weight:700; color:#4F8EF7; line-height:1; }
.stat-lbl  { font-size:11px; color:#5A6880; margin-top:3px; font-weight:500; }

.badge         { display:inline-block; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; }
.badge-ready   { background:#0A1F14; color:#4ADE80; border:1px solid #1A5C38; }
.badge-waiting { background:#1A140A; color:#FBBF24; border:1px solid #5C4010; }

.section-heading { font-size:19px; font-weight:700; color:#FFFFFF; margin:14px 0 10px 0; letter-spacing:-0.3px; display:flex; align-items:center; gap:8px; }

.ask-bar-card { background:#131826; border:1px solid #1E2438; border-radius:16px; padding:22px; margin-bottom:16px; }

.tool-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; }
.tool-card { background:#131826; border:1px solid #1E2438; border-radius:14px; padding:18px 16px; transition:border-color 0.2s,background 0.2s; cursor:pointer; }
.tool-card:hover { border-color:#2D74DA; background:#161D30; }
.tool-card-icon  { font-size:22px; margin-bottom:8px; }
.tool-card-title { font-size:14px; font-weight:700; color:#FFFFFF; margin-bottom:3px; }
.tool-card-desc  { font-size:12px; color:#5A6880; line-height:1.4; }

.stButton > button { width:100%; height:44px; border-radius:10px; background:#1A56DB; color:#FFFFFF !important; font-size:14px; font-weight:600; border:none; transition:background 0.2s,transform 0.1s; }
.stButton > button:hover  { background:#1446BF; transform:translateY(-1px); }
.stButton > button:active { transform:translateY(0); }

.clear-all-btn > button  { background:transparent !important; border:1px solid #2A1A1A !important; color:#F87171 !important; height:36px !important; font-size:13px !important; }
.clear-all-btn > button:hover { background:#1A0A0A !important; }

.delete-note-btn > button { background:transparent !important; border:1px solid #2A1A1A !important; color:#F87171 !important; height:32px !important; font-size:12px !important; }
.delete-note-btn > button:hover { background:#1A0A0A !important; }

.stDownloadButton > button { width:100%; height:44px; border-radius:10px; background:#1E2438 !important; color:#A0AABB !important; font-size:14px !important; font-weight:600 !important; border:1px solid #2A3555 !important; transition:background 0.2s,color 0.2s !important; }
.stDownloadButton > button:hover  { background:#2A3555 !important; color:#E2E8F0 !important; transform:translateY(-1px) !important; }
.stDownloadButton > button:active { transform:translateY(0) !important; }

.stTextInput > div > div > input { border-radius:10px; background:#0B0E18 !important; border:1px solid #1E2438 !important; color:#E2E8F0 !important; font-size:15px; padding:10px 14px; }
.stTextInput > div > div > input::placeholder { color:#3A4560 !important; }
.stTextInput > div > div > input:focus { border-color:#2D74DA !important; box-shadow:0 0 0 2px rgba(45,116,218,0.2) !important; }

.stSelectbox > div > div { background:#0B0E18 !important; border:1px solid #1E2438 !important; border-radius:10px !important; color:#E2E8F0 !important; }

[data-testid="stFileUploader"] { background:#0B0E18; border:2px dashed #1E2438; border-radius:12px; padding:6px; transition:border-color 0.2s; }
[data-testid="stFileUploader"]:hover { border-color:#2D74DA; }
[data-testid="stFileUploader"] * { color:#4A5578 !important; }

.workspace-title { font-size:17px; font-weight:700; color:#FFFFFF; }
.workspace-sub   { font-size:12px; color:#4A5578; margin-top:2px; }

.study-card { border-radius:14px; border-left-width:3px; border-left-style:solid; border-top:1px solid #1E2438; border-right:1px solid #1E2438; border-bottom:1px solid #1E2438; background:#131826; margin-bottom:14px; overflow:hidden; }
.study-card-header  { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; }
.study-card-left    { display:flex; align-items:center; gap:10px; }
.study-card-title   { font-size:14px; font-weight:700; color:#FFFFFF; }
.study-card-time    { font-size:11px; color:#3A4560; margin-top:2px; }
.study-card-body    { padding:0 18px 18px 18px; color:#C9D1E0; font-size:14px; line-height:1.7; }
.study-card-divider { height:1px; background:#1E2438; margin:0 18px; }
.study-card-highlight { box-shadow:0 0 0 2px #4F8EF7,0 0 16px rgba(79,142,247,0.4) !important; }

.card-answer       { border-left-color:#2D74DA; }
.card-summary      { border-left-color:#10B981; }
.card-questions    { border-left-color:#F59E0B; }
.card-mcqs         { border-left-color:#8B5CF6; }
.card-memorytricks { border-left-color:#F43F5E; }

.copy-toast { background:#0A1F14; border:1px solid #1A5C38; color:#4ADE80; border-radius:8px; padding:6px 12px; font-size:12px; text-align:center; margin-bottom:8px; }

.nav-section { font-size:10px; font-weight:700; color:#2A3555 !important; letter-spacing:1.2px; text-transform:uppercase; padding:6px 0 4px 0; }
.nav-item    { padding:8px 10px; border-radius:8px; margin-bottom:2px; font-size:13px; font-weight:500; color:#8A94A8 !important; display:flex; align-items:center; gap:8px; }
.nav-active  { background:rgba(45,116,218,0.15) !important; color:#5B9BF8 !important; border-left:2px solid #2D74DA; padding-left:8px; }
.nav-disabled { color:#2A3555 !important; cursor:not-allowed; }
.soon-badge  { font-size:9px; background:#161B2C; color:#3A4560 !important; border:1px solid #1E2438; border-radius:20px; padding:1px 6px; margin-left:auto; }

.version-box { background:#0B0E18; border:1px solid #1E2438; border-radius:10px; padding:12px 14px; margin-top:6px; }
.version-row { display:flex; justify-content:space-between; font-size:11px; color:#3A4560; margin-bottom:3px; }
.version-val { color:#6A7A98 !important; }

[data-testid="stExpander"] { background:#131826 !important; border:1px solid #1E2438 !important; border-radius:10px !important; }
.streamlit-expanderHeader { color:#CBD5E1 !important; background:#131826 !important; }

[data-testid="metric-container"] { background:#0B0E18; border-radius:10px; padding:12px; border:1px solid #1E2438; }
[data-testid="metric-container"] label { color:#4A5578 !important; font-size:12px; }
[data-testid="stMetricValue"] { color:#4F8EF7 !important; font-weight:700; }

.stSpinner > div { border-top-color:#2D74DA !important; }
hr { border-color:#1E2438 !important; margin:12px 0; }
h2,h3 { color:#FFFFFF !important; }
.stAlert { border-radius:10px; }
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:#0B0E18; }
::-webkit-scrollbar-thumb { background:#1E2438; border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:#2A3450; }
.app-footer { text-align:center; padding:16px 0 8px 0; border-top:1px solid #1E2438; margin-top:16px; font-size:12px; color:#2A3555; }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:
    st.markdown("## 📘 Exam Assistant")
    st.caption("Your personal study companion")
    st.divider()

    st.markdown('<div class="nav-section">Notes</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item nav-active">📂 Upload Notes</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item nav-disabled">📚 Notes Library <span class="soon-badge">Soon</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="nav-section" style="margin-top:8px">Study Tools</div>', unsafe_allow_html=True)

    _nav_btns = [
        ("❓ Ask Questions",  "nav_ask",           "ask"),
        ("📝 Summary",         "nav_summary",       "summary"),
        ("🎯 MCQs",            "nav_mcqs",          "mcqs"),
        ("🧠 Memory Tricks",   "nav_memory_tricks", "memory_tricks"),
    ]
    for label, key, section in _nav_btns:
        if st.button(label, key=key, use_container_width=True):
            st.session_state.focus_section = section; st.rerun()

    st.markdown('<div class="nav-item nav-disabled">📅 Study Planner <span class="soon-badge">Soon</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-item nav-disabled">🗺️ Mind Map <span class="soon-badge">Soon</span></div>',      unsafe_allow_html=True)

    st.markdown('<div class="nav-section" style="margin-top:8px">Activity</div>', unsafe_allow_html=True)

    if st.button("🕐 History",  key="nav_history",  use_container_width=True):
        st.session_state.show_history = not st.session_state.show_history; st.rerun()
    if st.button("⚙️ Settings", key="nav_settings", use_container_width=True):
        st.session_state.focus_section = "settings"; st.rerun()

    st.divider()
    st.markdown("### Project Info")
    st.markdown("""
    <div class="version-box">
        <div class="version-row">Version <span class="version-val">1.5.0</span></div>
        <div class="version-row">Day     <span class="version-val">19 / 30</span></div>
        <div class="version-row">Status  <span style="color:#4ADE80 !important">● Active</span></div>
    </div>""", unsafe_allow_html=True)
    st.write("")
    st.info("Upload your notes and let AI help you study smarter.")


# ==========================================================
# HEADER
# ==========================================================

_hour     = datetime.now().hour
_greeting = "Good morning" if _hour < 12 else ("Good afternoon" if _hour < 17 else "Good evening")

st.markdown(f"""
<div class="app-header">
    <div class="app-header-greeting">{_greeting}, Student</div>
    <h1>Ready to Study?</h1>
    <p>Upload your notes, ask questions, generate summaries, practice questions and MCQs — all powered by AI.</p>
</div>""", unsafe_allow_html=True)


# ==========================================================
# WELCOME CARD
# ==========================================================

if st.session_state.study_history:
    last = st.session_state.study_history[-1]
    st.markdown(f"""
    <div class="welcome-card">
        <div class="welcome-title">👋 Welcome back!</div>
        <div class="welcome-sub">Continue studying from where you left off.</div>
        <div class="welcome-last">🕒 Last: <b>{last['type']}</b> — {last['pdf_name']} — {_time_ago(last['time'])}</div>
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="welcome-card">
        <div class="welcome-title">👋 Welcome!</div>
        <div class="welcome-sub">Upload a PDF to begin your study session.</div>
    </div>""", unsafe_allow_html=True)


# ==========================================================
# TOP CARDS ROW
# ==========================================================

col_upload, col_recent, col_stats = st.columns([1.4, 1.3, 1])

# ── Upload ──
with col_upload:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📂 Upload Notes</div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload PDFs", type=["pdf"], label_visibility="collapsed",
        accept_multiple_files=True, key="pdf_uploader"
    )

    if not uploaded_files:
        st.markdown("""<div class="empty-state">
            <div class="empty-state-icon">📄</div>
            <div class="empty-state-text">Drag your PDFs here<br>or click Browse Files<br><br>Supported: PDF &nbsp;•&nbsp; Max 200 MB each</div>
        </div>""", unsafe_allow_html=True)

    if st.session_state.duplicate_notice:
        st.markdown(f'<div class="compact-notice">ℹ️ {st.session_state.duplicate_notice} already exists</div>',
                    unsafe_allow_html=True)
        st.session_state.duplicate_notice = None

    st.markdown("</div>", unsafe_allow_html=True)

# ── Uploaded notes list ──
with col_recent:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📄 Uploaded Notes</div>', unsafe_allow_html=True)

    if st.session_state.documents:
        for fname, data in list(st.session_state.documents.items()):
            if st.session_state.pending_delete == fname:
                st.markdown(f"""<div class="note-item" style="border-color:#5C2626;background:#1A0A0A;">
                    <div class="note-item-name" style="color:#F87171;">⚠️ Delete {fname}?</div>
                    <div class="note-item-meta">This will remove the file and its study material.</div>
                </div>""", unsafe_allow_html=True)
                d1, d2 = st.columns(2)
                with d1:
                    if st.button("✅ Yes, Delete", key=f"confirm_{fname}", use_container_width=True):
                        _delete_document(fname); st.session_state.pending_delete = None; st.rerun()
                with d2:
                    if st.button("✖ Cancel", key=f"cancel_{fname}", use_container_width=True):
                        st.session_state.pending_delete = None; st.rerun()
            else:
                n1, n2 = st.columns([4, 1])
                with n1:
                    st.markdown(f"""<div class="note-item">
                        <div class="note-item-name" title="{fname}">✅ {fname}</div>
                        <div class="note-item-meta">{data['pages']} pages &nbsp;•&nbsp; {data['file_size']} KB &nbsp;•&nbsp; {_time_ago(data['upload_time'])}</div>
                    </div>""", unsafe_allow_html=True)
                with n2:
                    st.markdown('<div class="delete-note-btn">', unsafe_allow_html=True)
                    if st.button("🗑", key=f"delnote_{fname}", use_container_width=True):
                        st.session_state.pending_delete = fname; st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div class="empty-state-text">No notes uploaded yet.<br>Upload your first PDF to begin studying.</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── Statistics ──
with col_stats:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📊 Statistics</div>', unsafe_allow_html=True)

    _db_badge    = '<span class="badge badge-ready">● Ready</span>' if st.session_state.collection_ready \
                   else '<span class="badge badge-waiting">○ Waiting</span>'
    _total_pages = sum(d["pages"] for d in st.session_state.documents.values())
    _ss          = st.session_state

    st.markdown(f"""<div class="stat-grid">
        <div class="stat-box"><div class="stat-val">{len(_ss.documents)}</div><div class="stat-lbl">Notes Uploaded</div></div>
        <div class="stat-box"><div class="stat-val">{_total_pages}</div><div class="stat-lbl">Pages Read</div></div>
        <div class="stat-box"><div class="stat-val">{_ss.searches_done}</div><div class="stat-lbl">Questions Asked</div></div>
        <div class="stat-box"><div class="stat-val">{_ss.summaries_done}</div><div class="stat-lbl">Summaries</div></div>
        <div class="stat-box"><div class="stat-val">{_ss.questions_done}</div><div class="stat-lbl">Practice Sets</div></div>
        <div class="stat-box"><div class="stat-val">{_ss.mcqs_done}</div><div class="stat-lbl">MCQ Sets</div></div>
        <div class="stat-box"><div class="stat-val">{_ss.memory_tricks_done}</div><div class="stat-lbl">Memory Sets</div></div>
        <div class="stat-box"><div class="stat-val">{len(_ss.study_history)}</div><div class="stat-lbl">History Entries</div></div>
    </div>
    <div style="text-align:center;margin-top:8px;font-size:12px;color:#4A5578;">Study Material &nbsp;{_db_badge}</div>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================================
# PDF PROCESSING
# ==========================================================

if uploaded_files:
    _new = False
    for uf in uploaded_files:
        if uf.name in st.session_state.documents:
            st.session_state.duplicate_notice = uf.name
            continue

        _bytes = uf.read()
        _kb    = round(len(_bytes) / 1024, 1)

        with st.status(f"⚙️ Preparing {uf.name}...", expanded=True) as _status:
            st.write("📖 Reading PDF...")
            _chunks, _pages, _err = _extract_chunks(_bytes, uf.name)

            if _err != "ok":
                if _err == "empty":
                    st.error(f"⚠️ {uf.name} appears to be empty or has no readable text.")
                else:
                    st.error(f"❌ Could not read {uf.name}. The file may be corrupted.")
                _status.update(label=f"❌ Failed: {uf.name}", state="error", expanded=False)
                continue

            st.write("🧮 Processing content...")
            _embeds = _embed_chunks(tuple(_chunks), uf.name)

            st.write("🗄️ Adding to search index...")
            try:
                _add_to_chroma(_chunks, _embeds, uf.name)
            except Exception as _ce:
                st.error(f"❌ Could not index {uf.name}. Please try again.")
                _status.update(label=f"❌ Failed: {uf.name}", state="error", expanded=False)
                continue

            st.session_state.documents[uf.name] = {
                "chunks":      _chunks,
                "pages":       _pages,
                "file_size":   _kb,
                "upload_time": datetime.now().strftime("%H:%M"),
            }
            st.session_state.collection_ready = True
            _new = True
            _status.update(label=f"✅ {uf.name} ready!", state="complete", expanded=False)

    if _new:
        st.rerun()


# ==========================================================
# SETTINGS PLACEHOLDER
# ==========================================================

if st.session_state.focus_section == "settings":
    st.info("⚙️ Settings page is coming soon.")
    st.session_state.focus_section = None


# ==========================================================
# MAIN WORKSPACE
# ==========================================================

if st.session_state.documents:

    st.markdown('<div class="section-heading">⚙️ Study Workspace</div>', unsafe_allow_html=True)

    left_panel, right_panel = st.columns([0.62, 1.0])

    # ── LEFT PANEL ──
    with left_panel:

        if st.session_state.focus_section in ("ask","summary","mcqs","memory_tricks"):
            _focus_labels = {"ask":"👆 Ask Questions","summary":"👆 Summary",
                             "mcqs":"👆 MCQs","memory_tricks":"👆 Memory Tricks"}
            st.markdown(f'<div style="color:#4F8EF7;font-size:12px;margin-bottom:4px;">'
                        f'{_focus_labels[st.session_state.focus_section]}</div>', unsafe_allow_html=True)
            st.session_state.focus_section = None

        # Ask bar
        st.markdown('<div class="ask-bar-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">💬 Ask a Question</div>', unsafe_allow_html=True)

        _scope_opts = ["All Notes"] + list(st.session_state.documents.keys())
        if st.session_state.search_scope not in _scope_opts:
            st.session_state.search_scope = "All Notes"

        st.session_state.search_scope = st.selectbox(
            "Search In", options=_scope_opts,
            index=_scope_opts.index(st.session_state.search_scope)
        )
        question       = st.text_input("", placeholder="Ask anything from your uploaded notes...", key="question_input")
        search_clicked = st.button("🔍 Search Notes", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""<div class="tool-grid">
            <div class="tool-card"><div class="tool-card-icon">📝</div><div class="tool-card-title">Study Summary</div><div class="tool-card-desc">Key concepts from your notes</div></div>
            <div class="tool-card"><div class="tool-card-icon">❓</div><div class="tool-card-title">Practice Questions</div><div class="tool-card-desc">Short & long answer questions</div></div>
            <div class="tool-card"><div class="tool-card-icon">🎯</div><div class="tool-card-title">MCQ Practice</div><div class="tool-card-desc">10 multiple choice questions</div></div>
            <div class="tool-card"><div class="tool-card-icon">🧠</div><div class="tool-card-title">Memory Tricks</div><div class="tool-card-desc">Mnemonics & exam shortcuts</div></div>
        </div>""", unsafe_allow_html=True)

        t1, t2 = st.columns(2)
        with t1: summary_clicked   = st.button("📝 Generate Summary",   use_container_width=True)
        with t2: questions_clicked = st.button("❓ Practice Questions", use_container_width=True)
        t3, t4 = st.columns(2)
        with t3: mcq_clicked           = st.button("🎯 Generate MCQs",    use_container_width=True)
        with t4: memory_tricks_clicked = st.button("🧠 Memory Tricks",    use_container_width=True)

    # ── RIGHT PANEL ──
    with right_panel:

        # History panel
        if st.session_state.show_history:
            st.markdown('<div class="history-panel">', unsafe_allow_html=True)
            hc1, hc2 = st.columns([2, 1])
            with hc1:
                st.markdown('<div class="card-title">🕐 Recent Activity</div>', unsafe_allow_html=True)
            with hc2:
                if st.button("✖ Clear History", key="clear_history", use_container_width=True):
                    st.session_state.study_history = []; st.rerun()

            if not st.session_state.study_history:
                st.markdown("""<div class="empty-state" style="padding:20px;">
                    <div class="empty-state-icon">📭</div>
                    <div class="empty-state-text">No study activity yet.<br>Generate a response to see history.</div>
                </div>""", unsafe_allow_html=True)
            else:
                for idx, entry in enumerate(reversed(st.session_state.study_history)):
                    _exists = _card_exists(entry["card_id"])
                    _pdf    = entry["pdf_name"][:30] + "..." if len(entry["pdf_name"]) > 30 else entry["pdf_name"]
                    e1, e2  = st.columns([3, 1])
                    with e1:
                        st.markdown(f"""<div class="history-entry">
                            <div class="history-time">🕒 {entry['time']} &nbsp;•&nbsp; {_time_ago(entry['time'])}</div>
                            <div class="history-type">{entry['type']}</div>
                            <div class="history-pdf">{_pdf}</div>
                        </div>""", unsafe_allow_html=True)
                    with e2:
                        if _exists:
                            if st.button("Open", key=f"hist_open_{idx}", use_container_width=True):
                                st.session_state.highlighted_card = entry["card_id"]
                                st.session_state.show_history     = False; st.rerun()
                        else:
                            st.markdown('<div style="font-size:11px;color:#4A5578;padding:8px 0;text-align:center;">Deleted</div>',
                                        unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        # Workspace toolbar
        wc1, wc2, wc3 = st.columns([2, 1, 0.7])
        with wc1:
            st.markdown('<div class="workspace-title">🗂️ Study Workspace</div>'
                        '<div class="workspace-sub">Generated study material appears here as cards.</div>',
                        unsafe_allow_html=True)
        with wc2:
            if st.session_state.workspace_cards:
                _today = datetime.now().strftime("%Y-%m-%d")
                st.download_button(
                    label="📦 Export All (PDF)",
                    data=build_pdf_all(st.session_state.workspace_cards, st.session_state.search_scope),
                    file_name=f"Export_All_{_today}.pdf", mime="application/pdf",
                    use_container_width=True, key="export_all_pdf"
                )
            else:
                st.button("📦 Export All (PDF)", disabled=True, use_container_width=True,
                          key="export_all_disabled", help="Generate at least one response before exporting.")
        with wc3:
            if not st.session_state.confirm_clear_all:
                st.markdown('<div class="clear-all-btn">', unsafe_allow_html=True)
                if st.button("🗑️ Clear All", use_container_width=True, key="clear_all_trigger"):
                    st.session_state.confirm_clear_all = True; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="clear-all-btn">', unsafe_allow_html=True)
                if st.button("✖ Cancel", use_container_width=True, key="cancel_clear"):
                    st.session_state.confirm_clear_all = False; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.confirm_clear_all:
            st.markdown("""<div class="confirm-box">
                <div class="confirm-title">⚠️ Clear Everything?</div>
                <div class="confirm-list">
                This will permanently remove:<br>
                • All uploaded PDFs<br>• All AI responses and workspace cards<br>
                • All summaries, MCQs, questions, memory tricks<br>
                • Study history<br>• Vector database cache<br>• All session data
                </div>
            </div>""", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("🗑️ Clear Everything", key="confirm_clear_all_btn", use_container_width=True):
                    _full_reset(); st.rerun()
            with cc2:
                if st.button("Keep Studying", key="cancel_clear_all_btn", use_container_width=True):
                    st.session_state.confirm_clear_all = False; st.rerun()

        # ── Search ──
        if search_clicked:
            if not question.strip():
                st.error("✏️ Please enter a question before searching.")
            else:
                _qf = None if st.session_state.search_scope == "All Notes" \
                      else {"source": st.session_state.search_scope}
                with st.spinner("🔍 Searching your notes..."):
                    _qemb = embed_model.encode(question).tolist()
                    try:
                        _res = collection.query(
                            query_embeddings=[_qemb], n_results=N_RESULTS,
                            include=["documents","distances","metadatas"],
                            where=_qf
                        )
                    except Exception:
                        st.error("❌ Search failed. Please try again."); _res = None

                if _res and _res["documents"][0]:
                    _ctx = "\n\n".join(_res["documents"][0])
                    _ans = _call_gemini(_prompt_search(_ctx, question))
                    if _ans:
                        _src = "\n\n---\n**Sources:**\n"
                        for i, (doc, dist, meta) in enumerate(zip(
                                _res["documents"][0], _res["distances"][0], _res["metadatas"][0])):
                            _conf = "High" if dist < 0.5 else ("Medium" if dist < 1.0 else "Low")
                            _src += f"\n**Source {i+1}** — {meta.get('source','?')} — Confidence: {_conf}\n> {doc[:200]}...\n"
                        _cid = _add_card("answer", "💬 Answer", _ans + _src, "card-answer")
                        _log_history("💬 Search Answer", _cid)
                        st.session_state.searches_done += 1
                        st.rerun()
                elif _res:
                    st.error("🔍 No relevant answer found in the uploaded notes.")

        # ── Summary ──
        if summary_clicked:
            _run_generator(
                "📝 Generating study summary...",
                "summary", "📝 Study Summary", "card-summary",
                "📝 Summary", "summaries_done",
                _prompt_summary
            )

        # ── Questions ──
        if questions_clicked:
            _run_generator(
                "❓ Generating practice questions...",
                "questions", "❓ Practice Questions", "card-questions",
                "❓ Practice Questions", "questions_done",
                _prompt_questions
            )

        # ── MCQs ──
        if mcq_clicked:
            _run_generator(
                "🎯 Generating MCQs...",
                "mcqs", "🎯 MCQ Practice", "card-mcqs",
                "🎯 MCQs", "mcqs_done",
                _prompt_mcqs
            )

        # ── Memory Tricks ──
        if memory_tricks_clicked:
            _run_generator(
                "🧠 Generating Memory Tricks...",
                "memorytricks", "🧠 Memory Tricks", "card-memorytricks",
                "🧠 Memory Tricks", "memory_tricks_done",
                _prompt_memory
            )

        # ── Render workspace cards ──
        if not st.session_state.workspace_cards:
            st.markdown("""<div class="empty-state" style="padding:40px 20px;background:#131826;border:1px solid #1E2438;border-radius:14px;">
                <div class="empty-state-icon">🗂️</div>
                <div class="empty-state-text">Generate your first AI response.<br>Ask a question or use the tools above.</div>
            </div>""", unsafe_allow_html=True)
        else:
            _today = datetime.now().strftime("%Y-%m-%d")
            for card in list(st.session_state.workspace_cards):
                _cid  = card["id"]
                _coll = card.get("collapsed", False)
                _ago  = _time_ago(card["time"])
                _hl   = "study-card-highlight" if st.session_state.highlighted_card == _cid else ""
                if _hl:
                    st.session_state.highlighted_card = None

                st.markdown(f"""<div class="study-card {card['color']} {_hl}" id="card_{_cid}">
                    <div class="study-card-header"><div class="study-card-left"><div>
                        <div class="study-card-title">{card['title']}</div>
                        <div class="study-card-time">Generated {_ago}</div>
                    </div></div></div>
                    <div class="study-card-divider"></div>
                </div>""", unsafe_allow_html=True)

                if st.session_state.get(f"copied_{_cid}"):
                    st.markdown('<div class="copy-toast">✅ Copied Successfully</div>', unsafe_allow_html=True)
                    if time.time() - st.session_state.get(f"copied_at_{_cid}", 0) > 2:
                        del st.session_state[f"copied_{_cid}"]

                b1, b2, b3, b4 = st.columns([1, 1, 1, 1.2])

                with b1:
                    if st.button("▶ Expand" if _coll else "▼ Collapse", key=f"col_{_cid}", use_container_width=True):
                        for c in st.session_state.workspace_cards:
                            if c["id"] == _cid:
                                c["collapsed"] = not c["collapsed"]
                        st.rerun()

                with b2:
                    if st.button("📋 Copy", key=f"copy_{_cid}", use_container_width=True):
                        _safe = card["content"].replace("`", "\\`")
                        components.html(f"""<script>(function(){{
                            if(navigator.clipboard&&window.isSecureContext){{
                                navigator.clipboard.writeText(`{_safe}`).catch(fb);
                            }}else{{fb();}}
                            function fb(){{var t=document.createElement("textarea");
                                t.value=`{_safe}`;t.style.position="fixed";t.style.left="-9999px";
                                document.body.appendChild(t);t.focus();t.select();
                                document.execCommand("copy");document.body.removeChild(t);}}
                        }})();</script>""", height=0)
                        st.session_state[f"copied_{_cid}"]    = True
                        st.session_state[f"copied_at_{_cid}"] = time.time()
                        st.rerun()

                with b3:
                    if st.button("🗑 Delete", key=f"del_{_cid}", use_container_width=True):
                        st.session_state.workspace_cards = [c for c in st.session_state.workspace_cards if c["id"] != _cid]
                        st.session_state.pop(f"copied_{_cid}", None)
                        st.session_state.pop(f"copied_at_{_cid}", None)
                        st.rerun()

                with b4:
                    st.download_button(
                        label="📥 Download PDF",
                        data=build_pdf_single(card, st.session_state.search_scope),
                        file_name=f"{_safe_filename(card['title'])}_{_today}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_pdf_{_cid}"
                    )

                if not _coll:
                    st.markdown('<div class="study-card-body">', unsafe_allow_html=True)
                    st.markdown(card["content"])
                    st.markdown("</div>", unsafe_allow_html=True)

                st.write("")


# ==========================================================
# EMPTY STATE (no documents)
# ==========================================================

else:
    st.markdown("""
    <div style="text-align:center;padding:50px 20px;background:#131826;
        border:1px dashed #1E2438;border-radius:18px;margin-top:14px;">
        <div style="font-size:52px;margin-bottom:16px;">📘</div>
        <div style="font-size:20px;font-weight:700;color:#FFFFFF;margin-bottom:8px;">Upload your first notes to begin</div>
        <div style="font-size:14px;color:#4A5578;line-height:1.7;max-width:420px;margin:0 auto;">
            Drag PDFs into the upload card above.<br>
            The AI will read your notes and help you study smarter —<br>
            summaries, questions, MCQs, memory tricks and more.
        </div>
    </div>""", unsafe_allow_html=True)


# ==========================================================
# FOOTER
# ==========================================================

st.markdown("""
<div class="app-footer">
    📘 AI Exam Preparation Assistant &nbsp;•&nbsp; Version 1.5 &nbsp;•&nbsp; Built for Students &nbsp;•&nbsp; Day 19 / 30
</div>""", unsafe_allow_html=True)