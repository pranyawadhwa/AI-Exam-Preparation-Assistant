
# ==========================================================
# AI EXAM PREPARATION ASSISTANT  —  Day 20
# Final polish, bug fixes, usability improvements
# ==========================================================

# ==========================================================
# IMPORTS
# ==========================================================

# import streamlit as st
# import streamlit.components.v1 as components
# from pypdf import PdfReader
# from sentence_transformers import SentenceTransformer
# import chromadb
# import google.generativeai as genai
# import os, io, re, time
# from datetime import datetime
# from dotenv import load_dotenv

# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import mm
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_LEFT, TA_CENTER

# load_dotenv()


# # ==========================================================
# # CONFIGURATION
# # ==========================================================

# CHROMA_PATH  = "./chroma_db"
# CHUNK_SIZE   = 1000
# N_RESULTS    = 3
# GEMINI_MODEL = "gemini-2.5-flash"
# EMBED_MODEL  = "all-MiniLM-L6-v2"

# st.set_page_config(
#     page_title="AI Exam Preparation Assistant",
#     page_icon="📘",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# gemini_model = genai.GenerativeModel(GEMINI_MODEL)


# # ==========================================================
# # CACHED RESOURCES
# # ==========================================================

# @st.cache_resource
# def load_embed_model():
#     return SentenceTransformer(EMBED_MODEL)

# @st.cache_resource
# def get_chroma_collection():
#     client = chromadb.PersistentClient(path=CHROMA_PATH)
#     return client.get_or_create_collection(name="notes")

# embed_model = load_embed_model()
# collection  = get_chroma_collection()


# # ==========================================================
# # SESSION STATE
# # ==========================================================

# _DEFAULTS = {
#     # Documents (never cleared by history operations)
#     "documents":          {},
#     "collection_ready":   False,
#     # Workspace
#     "workspace_cards":    [],
#     "highlighted_card":   None,
#     "confirm_clear_all":  False,
#     # History
#     "study_history":      [],
#     "show_history":       False,
#     # Statistics
#     "searches_done":      0,
#     "summaries_done":     0,
#     "questions_done":     0,
#     "mcqs_done":          0,
#     "memory_tricks_done": 0,
#     "ai_responses":       0,
#     # Search / UI
#     "search_scope":       "All Notes",
#     "pending_delete":     None,
#     "focus_section":      None,
#     "duplicate_notice":   None,
#     # Day 20: generation timing
#     "last_gen_time":      {},   # {card_id: seconds}
# }

# for _k, _v in _DEFAULTS.items():
#     if _k not in st.session_state:
#         st.session_state[_k] = _v


# # ==========================================================
# # PDF PROCESSING
# # ==========================================================

# def _chunk_text(text):
#     return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

# @st.cache_data(show_spinner=False)
# def _extract_chunks(file_bytes: bytes, file_name: str):
#     try:
#         reader = PdfReader(io.BytesIO(file_bytes))
#         text   = "".join(p.extract_text() or "" for p in reader.pages)
#         if not text.strip():
#             return [], 0, "empty"
#         return _chunk_text(text), len(reader.pages), "ok"
#     except Exception as e:
#         return [], 0, str(e)

# @st.cache_data(show_spinner=False)
# def _embed_chunks(chunks_tuple: tuple, _file_name: str):
#     return embed_model.encode(list(chunks_tuple)).tolist()

# def _add_to_chroma(chunks, embeddings, fname):
#     existing = collection.get(where={"source": fname})
#     if existing["ids"]:
#         collection.delete(ids=existing["ids"])
#     collection.add(
#         documents=chunks,
#         embeddings=embeddings,
#         metadatas=[{"source": fname} for _ in chunks],
#         ids=[f"{fname}_{i}" for i in range(len(chunks))],
#     )


# # ==========================================================
# # HELPER — Gemini call
# # ==========================================================

# def _call_gemini(prompt: str):
#     """Returns (text, elapsed_seconds) or (None, 0) on error."""
#     try:
#         t0   = time.time()
#         resp = gemini_model.generate_content(prompt)
#         return resp.text, round(time.time() - t0, 1)
#     except Exception as e:
#         _handle_gemini_error(e)
#         return None, 0

# def _handle_gemini_error(e):
#     err = str(e).lower()
#     if "quota" in err or "429" in err or "rate" in err:
#         st.error("⚠️ The AI service is temporarily busy. Please wait a minute and try again.")
#     elif "api_key" in err or "credential" in err or "401" in err:
#         st.error("🔑 API key issue detected. Please check your configuration.")
#     else:
#         st.error("❌ The AI couldn't complete the request. Please try again.")


# # ==========================================================
# # HELPER — Workspace cards
# # ==========================================================

# def _add_card(card_type, title, content, color, elapsed=0.0) -> str:
#     card_id = f"{card_type}_{int(time.time()*1000)}"
#     st.session_state.workspace_cards.append({
#         "id": card_id, "type": card_type, "title": title,
#         "content": content, "color": color,
#         "time": datetime.now().strftime("%H:%M"), "collapsed": False,
#         "elapsed": elapsed,   # Day 20: generation time
#     })
#     st.session_state.ai_responses += 1
#     return card_id

# def _log_history(response_type: str, card_id: str):
#     st.session_state.study_history.append({
#         "time": datetime.now().strftime("%H:%M"),
#         "type": response_type,
#         "pdf_name": st.session_state.search_scope,
#         "card_id": card_id,
#     })

# def _card_exists(card_id: str) -> bool:
#     return any(c["id"] == card_id for c in st.session_state.workspace_cards)

# def _get_active_chunks() -> dict:
#     scope = st.session_state.search_scope
#     if scope == "All Notes":
#         return {n: d["chunks"] for n, d in st.session_state.documents.items()}
#     doc = st.session_state.documents.get(scope)
#     return {scope: doc["chunks"]} if doc else {}


# # ==========================================================
# # HELPER — Session management
# # ==========================================================

# # PRIORITY 1 FIX: dedicated history-only clear — never touches documents
# def _clear_history_only():
#     """
#     Clear ONLY generated response history and workspace cards.
#     Uploaded PDFs, ChromaDB, embeddings, and document data are NEVER touched.
#     """
#     st.session_state.study_history    = []
#     st.session_state.workspace_cards  = []
#     st.session_state.highlighted_card = None
#     st.session_state.searches_done    = 0
#     st.session_state.summaries_done   = 0
#     st.session_state.questions_done   = 0
#     st.session_state.mcqs_done        = 0
#     st.session_state.memory_tricks_done = 0
#     st.session_state.ai_responses     = 0
#     st.session_state.last_gen_time    = {}

# def _full_reset():
#     """Complete session reset — wipes everything including documents."""
#     try:
#         existing = collection.get()
#         if existing["ids"]:
#             collection.delete(ids=existing["ids"])
#     except Exception:
#         pass
#     _extract_chunks.clear()
#     _embed_chunks.clear()
#     for k in list(_DEFAULTS.keys()):
#         if k in st.session_state:
#             del st.session_state[k]
#     for widget in ("pdf_uploader", "question_input"):
#         st.session_state.pop(widget, None)

# def _delete_document(fname: str):
#     try:
#         existing = collection.get(where={"source": fname})
#         if existing["ids"]:
#             collection.delete(ids=existing["ids"])
#     except Exception:
#         pass
#     st.session_state.documents.pop(fname, None)
#     _extract_chunks.clear()
#     _embed_chunks.clear()
#     if st.session_state.search_scope == fname:
#         st.session_state.search_scope = "All Notes"
#     st.session_state.pop("pdf_uploader", None)
#     if not st.session_state.documents:
#         st.session_state.collection_ready = False


# # ==========================================================
# # HELPER — Utilities
# # ==========================================================

# def _time_ago(ts: str) -> str:
#     if not ts:
#         return ""
#     try:
#         now  = datetime.now()
#         then = datetime.strptime(ts, "%H:%M")
#         diff = (now.hour * 60 + now.minute) - (then.hour * 60 + then.minute)
#         if diff <= 0: return "just now"
#         if diff == 1: return "1 min ago"
#         return f"{diff} min ago"
#     except Exception:
#         return ""

# def _safe_filename(title: str) -> str:
#     stem = re.sub(r'[^\w\s-]', '', title).strip()
#     return re.sub(r'\s+', '_', stem) or "export"


# # ==========================================================
# # HELPER — Generic generator  (shared by all 4 study tools)
# # ==========================================================

# def _run_generator(spinner_text, card_type, card_title, card_color,
#                    history_label, stat_key, build_prompt_fn):
#     active = _get_active_chunks()
#     if not active:
#         st.error("📂 Please upload at least one PDF before using this feature.")
#         return

#     with st.spinner(spinner_text):
#         parts   = []
#         elapsed = 0.0
#         for doc_name, doc_chunks in active.items():
#             prompt      = build_prompt_fn(doc_name, doc_chunks)
#             text, secs  = _call_gemini(prompt)
#             if text is None:
#                 return
#             elapsed += secs
#             parts.append(
#                 f"### 📘 {doc_name}\n\n{text}\n\n---\n\n"
#                 if len(active) > 1 else text
#             )

#     content = "".join(parts)
#     cid     = _add_card(card_type, card_title, content, card_color, round(elapsed, 1))
#     _log_history(history_label, cid)
#     st.session_state[stat_key] += 1
#     st.rerun()


# # ==========================================================
# # PDF EXPORT HELPERS
# # ==========================================================

# def _clean_inline(text: str) -> str:
#     text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
#     text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
#     text = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', text)
#     text = re.sub(r'`(.+?)`',       r'\1',         text)
#     text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1',      text)
#     return text.strip()

# @st.cache_data(show_spinner=False)
# def _get_pdf_styles():
#     base = getSampleStyleSheet()
#     mk   = lambda name, **kw: ParagraphStyle(name, parent=base["Normal"], **kw)
#     return {
#         "app_title":  mk("AT", fontSize=16, leading=22, fontName="Helvetica-Bold",
#                           textColor=colors.HexColor("#1246CC"), spaceAfter=2),
#         "card_title": mk("CT", fontSize=13, leading=18, fontName="Helvetica-Bold",
#                           textColor=colors.HexColor("#1E3A5F"), spaceBefore=6, spaceAfter=3),
#         "meta":       mk("ME", fontSize=9,  leading=13, fontName="Helvetica",
#                           textColor=colors.HexColor("#6B7280"), spaceAfter=2),
#         "section":    mk("SE", fontSize=12, leading=17, fontName="Helvetica-Bold",
#                           textColor=colors.HexColor("#1E3A5F"), spaceBefore=8, spaceAfter=3),
#         "heading":    mk("HE", fontSize=11, leading=15, fontName="Helvetica-Bold",
#                           textColor=colors.HexColor("#1F2937"), spaceBefore=5, spaceAfter=2),
#         "body":       mk("BO", fontSize=10, leading=15, fontName="Helvetica",
#                           textColor=colors.HexColor("#1F2937"), spaceAfter=3, wordWrap="CJK"),
#         "bullet":     mk("BU", fontSize=10, leading=15, fontName="Helvetica",
#                           textColor=colors.HexColor("#1F2937"),
#                           leftIndent=16, bulletIndent=6, spaceAfter=2, wordWrap="CJK"),
#         "footer":     mk("FO", fontSize=8,  leading=11, fontName="Helvetica-Oblique",
#                           textColor=colors.HexColor("#9CA3AF"), alignment=TA_CENTER),
#     }

# def _md_to_flowables(text: str, styles: dict) -> list:
#     out = []
#     for line in text.split("\n"):
#         if m := re.match(r'^(#{1,6})\s+(.*)', line):
#             s = styles["section"] if len(m.group(1)) <= 2 else styles["heading"]
#             out.append(Paragraph(_clean_inline(m.group(2)), s)); continue
#         if re.match(r'^[-=]{3,}$', line.strip()):
#             out += [Spacer(1,2*mm), HRFlowable(width="100%", thickness=0.5,
#                     color=colors.HexColor("#CBD5E1")), Spacer(1,2*mm)]; continue
#         if m := re.match(r'^[\*\-•]\s+(.*)', line):
#             out.append(Paragraph(f"• {_clean_inline(m.group(1))}", styles["bullet"])); continue
#         if m := re.match(r'^(\d+)\.\s+(.*)', line):
#             out.append(Paragraph(f"{m.group(1)}. {_clean_inline(m.group(2))}", styles["bullet"])); continue
#         if not line.strip():
#             out.append(Spacer(1,3*mm)); continue
#         if c := _clean_inline(line):
#             out.append(Paragraph(c, styles["body"]))
#     return out

# def _pdf_header(styles, title, scope, gen_time) -> list:
#     now = datetime.now().strftime("%Y-%m-%d %H:%M")
#     return [
#         Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
#         Paragraph(title, styles["card_title"]),
#         Paragraph(f"Generated: {gen_time}  |  Exported: {now}", styles["meta"]),
#         Paragraph(f"Source: {scope}", styles["meta"]),
#         Spacer(1,4*mm),
#         HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D74DA")),
#         Spacer(1,5*mm),
#     ]

# def _pdf_footer(styles) -> list:
#     return [
#         Spacer(1,8*mm),
#         HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1")),
#         Spacer(1,2*mm),
#         Paragraph("Generated by AI Exam Preparation Assistant", styles["footer"]),
#     ]

# def build_pdf_single(card: dict, scope: str) -> io.BytesIO:
#     buf    = io.BytesIO()
#     styles = _get_pdf_styles()
#     story  = _pdf_header(styles, card["title"], scope, card["time"])
#     story += _md_to_flowables(card["content"], styles)
#     story += _pdf_footer(styles)
#     doc = SimpleDocTemplate(buf, pagesize=A4,
#         leftMargin=20*mm, rightMargin=20*mm,
#         topMargin=20*mm, bottomMargin=20*mm, title=card["title"])
#     doc.build(story)
#     buf.seek(0); return buf

# def build_pdf_all(cards: list, scope: str) -> io.BytesIO:
#     buf    = io.BytesIO()
#     styles = _get_pdf_styles()
#     now    = datetime.now().strftime("%Y-%m-%d %H:%M")
#     story  = [
#         Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
#         Paragraph("Full Study Export", styles["card_title"]),
#         Paragraph(f"Exported: {now}  |  Source: {scope}", styles["meta"]),
#         Spacer(1,4*mm),
#         HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D74DA")),
#         Spacer(1,6*mm),
#     ]
#     for i, card in enumerate(cards):
#         if i:
#             story += [Spacer(1,6*mm),
#                       HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8")),
#                       Spacer(1,4*mm)]
#         story += [
#             Paragraph(card["title"], styles["section"]),
#             Paragraph(f"Generated: {card['time']}", styles["meta"]),
#             Spacer(1,3*mm),
#         ]
#         story += _md_to_flowables(card["content"], styles)
#     story += _pdf_footer(styles)
#     doc = SimpleDocTemplate(buf, pagesize=A4,
#         leftMargin=20*mm, rightMargin=20*mm,
#         topMargin=20*mm, bottomMargin=20*mm, title="Full Export")
#     doc.build(story)
#     buf.seek(0); return buf


# # ==========================================================
# # PROMPTS  (unchanged)
# # ==========================================================

# def _prompt_search(context, question):
#     return f"""You are an expert AI Exam Preparation Assistant.
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

# Answer:"""

# def _prompt_summary(doc_name, doc_chunks):
#     return f"""You are an AI Exam Preparation Assistant.
# Create a concise study summary from the notes.
# Focus on: Main concepts, Important ideas, Key points, Exam-relevant information.

# Notes:
# {chr(10).join(doc_chunks)}

# Summary:"""

# def _prompt_questions(doc_name, doc_chunks):
#     return f"""You are an AI Exam Preparation Assistant.
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
# {chr(10).join(doc_chunks)}

# Questions:"""

# def _prompt_mcqs(doc_name, doc_chunks):
#     return f"""You are an AI Exam Preparation Assistant.
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
# {chr(10).join(doc_chunks)}

# MCQs:"""

# def _prompt_memory(doc_name, doc_chunks):
#     return f"""You are an expert exam mentor helping university students remember topics quickly.
# Your task is to create highly memorable Memory Tricks from the provided notes.
# The goal is NOT to summarize the chapter.
# The goal is to help students remember difficult concepts during exams.
# Generate only information that actually exists in the notes.
# If a topic does not naturally support a mnemonic, create another memory technique instead.

# Use the following techniques wherever appropriate:

# 1. Acronyms — create memorable acronyms from important concepts.
# 2. Mnemonics — memorable word/phrase associations.
# 3. Memory Sentences — e.g. "Smart Workers Build Trust".
# 4. Number Tricks — highlight important years, percentages, values.
# 5. Compare Similar Concepts — brief side-by-side comparison.
# 6. Exam Keywords — list only words students must remember.
# 7. Frequently Confused Concepts — one-line differentiators.
# 8. Must Remember Before Exam — 5-10 critical facts.

# Requirements:
# - Generate between 8 and 15 memory tricks.
# - Make every trick different.
# - Use headings and bullet points.
# - Keep every trick short.
# - Everything must come only from the provided notes.
# - Do not generate questions or flashcards.

# Notes:
# {chr(10).join(doc_chunks)}

# Memory Tricks:"""


# # ==========================================================
# # CSS  (unchanged + Day 20 polish additions)
# # ==========================================================

# st.markdown("""
# <style>
# @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
# * { font-family:'Inter','Segoe UI',sans-serif; box-sizing:border-box; }
# .stApp { background:#0B0E18; }

# section[data-testid="stSidebar"] {
#     background:#10141F; border-right:1px solid #1E2438; width:240px !important;
# }
# section[data-testid="stSidebar"] * { color:#8A94A8 !important; }
# section[data-testid="stSidebar"] h2,
# section[data-testid="stSidebar"] h3 { color:#FFFFFF !important; font-weight:700; }
# section[data-testid="stSidebar"] hr { border-color:#1E2438 !important; margin:10px 0; }
# section[data-testid="stSidebar"] .stAlert {
#     background:#161B2C !important; border:1px solid #1E2438 !important; border-radius:10px;
# }
# section[data-testid="stSidebar"] .stButton > button {
#     background:transparent !important; border:none !important; color:#8A94A8 !important;
#     text-align:left !important; justify-content:flex-start !important; padding:8px 10px !important;
#     height:auto !important; font-size:13px !important; font-weight:500 !important;
#     border-radius:8px !important; box-shadow:none !important;
# }
# section[data-testid="stSidebar"] .stButton > button:hover {
#     background:rgba(45,116,218,0.12) !important; color:#5B9BF8 !important; transform:none !important;
# }

# .block-container { padding:1.2rem 2rem 2rem 2rem; max-width:1400px; }
# .stApp,.stApp p,.stApp label { color:#CBD5E1; }

# .app-header {
#     background:linear-gradient(130deg,#1246CC 0%,#2D74DA 55%,#5B9BF8 100%);
#     padding:28px 40px; border-radius:18px; margin-bottom:14px;
#     box-shadow:0 6px 40px rgba(18,70,204,0.4); position:relative; overflow:hidden;
# }
# .app-header::after {
#     content:'📘'; position:absolute; right:40px; top:50%;
#     transform:translateY(-50%); font-size:72px; opacity:0.12;
# }
# .app-header-greeting { font-size:13px; font-weight:600; color:#A8C8FF; letter-spacing:1.2px; text-transform:uppercase; margin-bottom:4px; }
# .app-header h1 { margin:0 0 6px 0; font-size:28px; font-weight:800; color:#FFFFFF; letter-spacing:-0.5px; }
# .app-header p  { margin:0; font-size:15px; color:#C8DEFF; max-width:560px; line-height:1.55; }

# .card { background:#131826; border:1px solid #1E2438; border-radius:16px; padding:22px; height:100%; }
# .card-title { font-size:15px; font-weight:700; color:#FFFFFF; margin-bottom:16px; letter-spacing:-0.1px; }

# .empty-state { text-align:center; padding:28px 16px; }
# .empty-state-icon { font-size:36px; margin-bottom:10px; }
# .empty-state-text { font-size:13px; color:#4A5578; line-height:1.6; }

# .note-item { background:#0A1F14; border:1px solid #1A5C38; border-radius:12px; padding:12px 14px; margin-bottom:8px; }
# .note-item-name { font-size:13px; font-weight:600; color:#4ADE80; margin-bottom:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
# .note-item-meta { font-size:11px; color:#5A7A60; }

# /* Day 20: instant-load badge */
# .note-item-cached { font-size:10px; color:#3B82F6; margin-top:2px; }

# .compact-notice { background:#161B2C; border:1px solid #2A3555; border-radius:8px; padding:6px 12px; font-size:12px; color:#7B88A0; margin-top:6px; }

# .history-panel { background:#131826; border:1px solid #1E2438; border-radius:16px; padding:20px; margin-bottom:16px; }
# .history-entry { background:#0B0E18; border:1px solid #1E2438; border-radius:10px; padding:10px 14px; margin-bottom:8px; }
# .history-time  { font-size:11px; color:#4A5578; margin-bottom:2px; }
# .history-type  { font-size:13px; font-weight:600; color:#E2E8F0; }
# .history-pdf   { font-size:11px; color:#7B88A0; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

# .welcome-card { background:#131826; border:1px solid #1E2438; border-left:3px solid #2D74DA; border-radius:12px; padding:14px 18px; margin-bottom:14px; }
# .welcome-title { font-size:14px; font-weight:700; color:#FFFFFF; margin-bottom:4px; }
# .welcome-sub   { font-size:12px; color:#6B7280; }
# .welcome-last  { font-size:12px; color:#7B88A0; margin-top:6px; }

# .confirm-box   { background:#1A0A0A; border:1px solid #5C2626; border-radius:14px; padding:20px; margin-bottom:14px; }
# .confirm-title { font-size:15px; font-weight:700; color:#F87171; margin-bottom:8px; }
# .confirm-list  { font-size:13px; color:#9CA3AF; line-height:1.8; }

# .stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
# .stat-box  { background:#0B0E18; border:1px solid #1E2438; border-radius:10px; padding:12px 10px; text-align:center; transition:border-color 0.2s; }
# .stat-box:hover { border-color:#2D74DA; }
# .stat-val  { font-size:22px; font-weight:700; color:#4F8EF7; line-height:1; }
# .stat-lbl  { font-size:11px; color:#5A6880; margin-top:3px; font-weight:500; }

# .badge         { display:inline-block; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; }
# .badge-ready   { background:#0A1F14; color:#4ADE80; border:1px solid #1A5C38; }
# .badge-waiting { background:#1A140A; color:#FBBF24; border:1px solid #5C4010; }

# .section-heading { font-size:19px; font-weight:700; color:#FFFFFF; margin:14px 0 10px 0; letter-spacing:-0.3px; display:flex; align-items:center; gap:8px; }

# .ask-bar-card { background:#131826; border:1px solid #1E2438; border-radius:16px; padding:22px; margin-bottom:16px; }

# .tool-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; }
# .tool-card { background:#131826; border:1px solid #1E2438; border-radius:14px; padding:18px 16px; transition:border-color 0.2s,background 0.2s; cursor:pointer; }
# .tool-card:hover { border-color:#2D74DA; background:#161D30; }
# .tool-card-icon  { font-size:22px; margin-bottom:8px; }
# .tool-card-title { font-size:14px; font-weight:700; color:#FFFFFF; margin-bottom:3px; }
# .tool-card-desc  { font-size:12px; color:#5A6880; line-height:1.4; }

# .stButton > button { width:100%; height:44px; border-radius:10px; background:#1A56DB; color:#FFFFFF !important; font-size:14px; font-weight:600; border:none; transition:background 0.2s,transform 0.1s; }
# .stButton > button:hover  { background:#1446BF; transform:translateY(-1px); }
# .stButton > button:active { transform:translateY(0); }

# .clear-all-btn > button  { background:transparent !important; border:1px solid #2A1A1A !important; color:#F87171 !important; height:36px !important; font-size:13px !important; }
# .clear-all-btn > button:hover { background:#1A0A0A !important; }

# .delete-note-btn > button { background:transparent !important; border:1px solid #2A1A1A !important; color:#F87171 !important; height:32px !important; font-size:12px !important; }
# .delete-note-btn > button:hover { background:#1A0A0A !important; }

# .stDownloadButton > button { width:100%; height:44px; border-radius:10px; background:#1E2438 !important; color:#A0AABB !important; font-size:14px !important; font-weight:600 !important; border:1px solid #2A3555 !important; transition:background 0.2s,color 0.2s !important; }
# .stDownloadButton > button:hover  { background:#2A3555 !important; color:#E2E8F0 !important; transform:translateY(-1px) !important; }
# .stDownloadButton > button:active { transform:translateY(0) !important; }

# .stTextInput > div > div > input { border-radius:10px; background:#0B0E18 !important; border:1px solid #1E2438 !important; color:#E2E8F0 !important; font-size:15px; padding:10px 14px; }
# .stTextInput > div > div > input::placeholder { color:#3A4560 !important; }
# .stTextInput > div > div > input:focus { border-color:#2D74DA !important; box-shadow:0 0 0 2px rgba(45,116,218,0.2) !important; }

# .stSelectbox > div > div { background:#0B0E18 !important; border:1px solid #1E2438 !important; border-radius:10px !important; color:#E2E8F0 !important; }

# [data-testid="stFileUploader"] { background:#0B0E18; border:2px dashed #1E2438; border-radius:12px; padding:6px; transition:border-color 0.2s; }
# [data-testid="stFileUploader"]:hover { border-color:#2D74DA; }
# [data-testid="stFileUploader"] * { color:#4A5578 !important; }

# .workspace-title { font-size:17px; font-weight:700; color:#FFFFFF; }
# .workspace-sub   { font-size:12px; color:#4A5578; margin-top:2px; }

# .study-card { border-radius:14px; border-left-width:3px; border-left-style:solid; border-top:1px solid #1E2438; border-right:1px solid #1E2438; border-bottom:1px solid #1E2438; background:#131826; margin-bottom:14px; overflow:hidden; }
# .study-card-header  { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; }
# .study-card-left    { display:flex; align-items:center; gap:10px; }
# .study-card-title   { font-size:14px; font-weight:700; color:#FFFFFF; }
# .study-card-time    { font-size:11px; color:#3A4560; margin-top:2px; }
# /* Day 20: generation time badge */
# .study-card-elapsed { font-size:10px; color:#3A4560; margin-top:1px; }
# .study-card-body    { padding:0 18px 18px 18px; color:#C9D1E0; font-size:14px; line-height:1.7; }
# .study-card-divider { height:1px; background:#1E2438; margin:0 18px; }
# .study-card-highlight { box-shadow:0 0 0 2px #4F8EF7,0 0 16px rgba(79,142,247,0.4) !important; }

# .card-answer       { border-left-color:#2D74DA; }
# .card-summary      { border-left-color:#10B981; }
# .card-questions    { border-left-color:#F59E0B; }
# .card-mcqs         { border-left-color:#8B5CF6; }
# .card-memorytricks { border-left-color:#F43F5E; }

# .copy-toast { background:#0A1F14; border:1px solid #1A5C38; color:#4ADE80; border-radius:8px; padding:6px 12px; font-size:12px; text-align:center; margin-bottom:8px; }

# .nav-section  { font-size:10px; font-weight:700; color:#2A3555 !important; letter-spacing:1.2px; text-transform:uppercase; padding:6px 0 4px 0; }
# .nav-item     { padding:8px 10px; border-radius:8px; margin-bottom:2px; font-size:13px; font-weight:500; color:#8A94A8 !important; display:flex; align-items:center; gap:8px; }
# .nav-active   { background:rgba(45,116,218,0.15) !important; color:#5B9BF8 !important; border-left:2px solid #2D74DA; padding-left:8px; }
# .nav-disabled { color:#2A3555 !important; cursor:not-allowed; }
# .soon-badge   { font-size:9px; background:#161B2C; color:#3A4560 !important; border:1px solid #1E2438; border-radius:20px; padding:1px 6px; margin-left:auto; }

# .version-box { background:#0B0E18; border:1px solid #1E2438; border-radius:10px; padding:12px 14px; margin-top:6px; }
# .version-row { display:flex; justify-content:space-between; font-size:11px; color:#3A4560; margin-bottom:3px; }
# .version-val { color:#6A7A98 !important; }

# [data-testid="stExpander"] { background:#131826 !important; border:1px solid #1E2438 !important; border-radius:10px !important; }
# .streamlit-expanderHeader { color:#CBD5E1 !important; background:#131826 !important; }

# [data-testid="metric-container"] { background:#0B0E18; border-radius:10px; padding:12px; border:1px solid #1E2438; }
# [data-testid="metric-container"] label { color:#4A5578 !important; font-size:12px; }
# [data-testid="stMetricValue"] { color:#4F8EF7 !important; font-weight:700; }

# .stSpinner > div { border-top-color:#2D74DA !important; }
# hr { border-color:#1E2438 !important; margin:12px 0; }
# h2,h3 { color:#FFFFFF !important; }
# .stAlert { border-radius:10px; }

# ::-webkit-scrollbar { width:5px; height:5px; }
# ::-webkit-scrollbar-track { background:#0B0E18; }
# ::-webkit-scrollbar-thumb { background:#1E2438; border-radius:4px; }
# ::-webkit-scrollbar-thumb:hover { background:#2A3450; }

# .app-footer { text-align:center; padding:16px 0 8px 0; border-top:1px solid #1E2438; margin-top:16px; font-size:12px; color:#2A3555; }
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
#     for _label, _key, _sec in [
#         ("❓ Ask Questions",  "nav_ask",           "ask"),
#         ("📝 Summary",         "nav_summary",       "summary"),
#         ("🎯 MCQs",            "nav_mcqs",          "mcqs"),
#         ("🧠 Memory Tricks",   "nav_memory_tricks", "memory_tricks"),
#     ]:
#         if st.button(_label, key=_key, use_container_width=True):
#             st.session_state.focus_section = _sec; st.rerun()

#     st.markdown('<div class="nav-item nav-disabled">📅 Study Planner <span class="soon-badge">Soon</span></div>', unsafe_allow_html=True)
#     st.markdown('<div class="nav-item nav-disabled">🗺️ Mind Map <span class="soon-badge">Soon</span></div>',      unsafe_allow_html=True)

#     st.markdown('<div class="nav-section" style="margin-top:8px">Activity</div>', unsafe_allow_html=True)
#     if st.button("🕐 History",  key="nav_history",  use_container_width=True):
#         st.session_state.show_history = not st.session_state.show_history; st.rerun()
#     if st.button("⚙️ Settings", key="nav_settings", use_container_width=True):
#         st.session_state.focus_section = "settings"; st.rerun()

#     st.divider()
#     st.markdown("### Project Info")
#     st.markdown("""
#     <div class="version-box">
#         <div class="version-row">Version <span class="version-val">2.0.0</span></div>
#         <div class="version-row">Day     <span class="version-val">20 / 30</span></div>
#         <div class="version-row">Status  <span style="color:#4ADE80 !important">● Ready</span></div>
#     </div>""", unsafe_allow_html=True)
#     st.write("")
#     st.info("Upload your notes and let AI help you study smarter.")


# # ==========================================================
# # HEADER
# # ==========================================================

# _hour     = datetime.now().hour
# _greeting = "Good morning" if _hour < 12 else ("Good afternoon" if _hour < 17 else "Good evening")

# st.markdown(f"""
# <div class="app-header">
#     <div class="app-header-greeting">{_greeting}, Student</div>
#     <h1>Ready to Study?</h1>
#     <p>Upload your notes, ask questions, generate summaries, practice questions and MCQs — all powered by AI.</p>
# </div>""", unsafe_allow_html=True)


# # ==========================================================
# # WELCOME CARD
# # ==========================================================

# if st.session_state.study_history:
#     _last = st.session_state.study_history[-1]
#     st.markdown(f"""
#     <div class="welcome-card">
#         <div class="welcome-title">👋 Welcome back!</div>
#         <div class="welcome-sub">Continue studying from where you left off.</div>
#         <div class="welcome-last">🕒 Last: <b>{_last['type']}</b> — {_last['pdf_name']} — {_time_ago(_last['time'])}</div>
#     </div>""", unsafe_allow_html=True)
# else:
#     st.markdown("""
#     <div class="welcome-card">
#         <div class="welcome-title">👋 Welcome!</div>
#         <div class="welcome-sub">Upload a PDF to begin your study session.</div>
#     </div>""", unsafe_allow_html=True)


# # ==========================================================
# # TOP CARDS ROW
# # ==========================================================

# col_upload, col_recent, col_stats = st.columns([1.4, 1.3, 1])

# # ── Upload ──
# with col_upload:
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     st.markdown('<div class="card-title">📂 Upload Notes</div>', unsafe_allow_html=True)

#     uploaded_files = st.file_uploader(
#         "Upload PDFs", type=["pdf"], label_visibility="collapsed",
#         accept_multiple_files=True, key="pdf_uploader"
#     )

#     if not uploaded_files:
#         st.markdown("""<div class="empty-state">
#             <div class="empty-state-icon">📄</div>
#             <div class="empty-state-text">Drag your PDFs here or click Browse Files<br><br>
#             Supported: PDF &nbsp;•&nbsp; Max 200 MB each</div>
#         </div>""", unsafe_allow_html=True)

#     if st.session_state.duplicate_notice:
#         st.markdown(
#             f'<div class="compact-notice">ℹ️ <b>{st.session_state.duplicate_notice}</b> is already in your study library.</div>',
#             unsafe_allow_html=True
#         )
#         st.session_state.duplicate_notice = None

#     st.markdown("</div>", unsafe_allow_html=True)

# # ── Uploaded notes ──
# with col_recent:
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     st.markdown('<div class="card-title">📄 Your Study Notes</div>', unsafe_allow_html=True)

#     if st.session_state.documents:
#         for fname, data in list(st.session_state.documents.items()):
#             if st.session_state.pending_delete == fname:
#                 st.markdown(f"""<div class="note-item" style="border-color:#5C2626;background:#1A0A0A;">
#                     <div class="note-item-name" style="color:#F87171;">⚠️ Remove {fname}?</div>
#                     <div class="note-item-meta">This will remove the file and all indexed content.</div>
#                 </div>""", unsafe_allow_html=True)
#                 d1, d2 = st.columns(2)
#                 with d1:
#                     if st.button("✅ Yes, Remove", key=f"confirm_{fname}", use_container_width=True):
#                         _delete_document(fname); st.session_state.pending_delete = None; st.rerun()
#                 with d2:
#                     if st.button("✖ Keep It", key=f"cancel_{fname}", use_container_width=True):
#                         st.session_state.pending_delete = None; st.rerun()
#             else:
#                 n1, n2 = st.columns([4, 1])
#                 with n1:
#                     # Priority 9: show instant-load indicator for cached PDFs
#                     _cached_label = '<div class="note-item-cached">⚡ Loaded instantly from previous session</div>'
#                     st.markdown(f"""<div class="note-item">
#                         <div class="note-item-name" title="{fname}">✅ {fname}</div>
#                         <div class="note-item-meta">{data['pages']} pages &nbsp;•&nbsp; {data['file_size']} KB &nbsp;•&nbsp; {_time_ago(data['upload_time'])}</div>
#                         {_cached_label}
#                     </div>""", unsafe_allow_html=True)
#                 with n2:
#                     st.markdown('<div class="delete-note-btn">', unsafe_allow_html=True)
#                     if st.button("🗑", key=f"delnote_{fname}", use_container_width=True,
#                                  help=f"Remove {fname} from your study library"):
#                         st.session_state.pending_delete = fname; st.rerun()
#                     st.markdown("</div>", unsafe_allow_html=True)
#     else:
#         st.markdown("""<div class="empty-state">
#             <div class="empty-state-icon">📭</div>
#             <div class="empty-state-text">No study notes uploaded yet.<br>
#             Upload a PDF to get started — the AI will read and index it automatically.</div>
#         </div>""", unsafe_allow_html=True)

#     st.markdown("</div>", unsafe_allow_html=True)

# # ── Statistics ──
# with col_stats:
#     st.markdown('<div class="card">', unsafe_allow_html=True)
#     st.markdown('<div class="card-title">📊 Study Progress</div>', unsafe_allow_html=True)

#     _rdy  = st.session_state.collection_ready
#     _badge = f'<span class="badge badge-{"ready" if _rdy else "waiting"}">{"● Notes Ready" if _rdy else "○ Waiting for Notes"}</span>'
#     _tp   = sum(d["pages"] for d in st.session_state.documents.values())
#     _ss   = st.session_state

#     st.markdown(f"""<div class="stat-grid">
#         <div class="stat-box"><div class="stat-val">{len(_ss.documents)}</div><div class="stat-lbl">Notes Uploaded</div></div>
#         <div class="stat-box"><div class="stat-val">{_tp}</div><div class="stat-lbl">Pages Studied</div></div>
#         <div class="stat-box"><div class="stat-val">{_ss.searches_done}</div><div class="stat-lbl">Questions Asked</div></div>
#         <div class="stat-box"><div class="stat-val">{_ss.summaries_done}</div><div class="stat-lbl">Summaries Made</div></div>
#         <div class="stat-box"><div class="stat-val">{_ss.questions_done}</div><div class="stat-lbl">Practice Sets</div></div>
#         <div class="stat-box"><div class="stat-val">{_ss.mcqs_done}</div><div class="stat-lbl">MCQ Sets</div></div>
#         <div class="stat-box"><div class="stat-val">{_ss.memory_tricks_done}</div><div class="stat-lbl">Memory Sets</div></div>
#         <div class="stat-box"><div class="stat-val">{len(_ss.study_history)}</div><div class="stat-lbl">Study Sessions</div></div>
#     </div>
#     <div style="text-align:center;margin-top:8px;font-size:12px;color:#4A5578;">{_badge}</div>
#     """, unsafe_allow_html=True)

#     st.markdown("</div>", unsafe_allow_html=True)


# # ==========================================================
# # PDF PROCESSING
# # ==========================================================

# if uploaded_files:
#     _new = False
#     for uf in uploaded_files:
#         if uf.name in st.session_state.documents:
#             st.session_state.duplicate_notice = uf.name
#             continue

#         _bytes = uf.read()
#         _kb    = round(len(_bytes) / 1024, 1)

#         with st.status(f"📖 Reading {uf.name}...", expanded=True) as _status:
#             st.write("📖 Extracting text from your notes...")
#             _chunks, _pages, _err = _extract_chunks(_bytes, uf.name)

#             if _err != "ok":
#                 _msg = "This PDF appears to be empty or contains no readable text." \
#                        if _err == "empty" else \
#                        "This PDF could not be read. It may be corrupted or password-protected."
#                 st.error(f"⚠️ {_msg}")
#                 _status.update(label=f"❌ Could not read {uf.name}", state="error", expanded=False)
#                 continue

#             st.write("🧠 Analysing and preparing your study material...")
#             _embeds = _embed_chunks(tuple(_chunks), uf.name)

#             st.write("🗄️ Indexing notes for instant search...")
#             try:
#                 _add_to_chroma(_chunks, _embeds, uf.name)
#             except Exception:
#                 st.error("❌ Could not index this file. Please try uploading again.")
#                 _status.update(label=f"❌ Indexing failed for {uf.name}", state="error", expanded=False)
#                 continue

#             st.session_state.documents[uf.name] = {
#                 "chunks":      _chunks,
#                 "pages":       _pages,
#                 "file_size":   _kb,
#                 "upload_time": datetime.now().strftime("%H:%M"),
#             }
#             st.session_state.collection_ready = True
#             _new = True
#             _status.update(label=f"✅ {uf.name} is ready to study!", state="complete", expanded=False)

#     if _new:
#         st.rerun()


# # ==========================================================
# # SETTINGS PLACEHOLDER
# # ==========================================================

# if st.session_state.focus_section == "settings":
#     st.info("⚙️ Settings will be available in a future update.")
#     st.session_state.focus_section = None


# # ==========================================================
# # MAIN WORKSPACE
# # ==========================================================

# if st.session_state.documents:

#     st.markdown('<div class="section-heading">⚙️ Study Workspace</div>', unsafe_allow_html=True)

#     left_panel, right_panel = st.columns([0.62, 1.0])

#     # ── LEFT PANEL ──
#     with left_panel:

#         if st.session_state.focus_section in ("ask","summary","mcqs","memory_tricks"):
#             _fl = {"ask":"👆 Scroll down to ask a question","summary":"👆 Click Generate Summary below",
#                    "mcqs":"👆 Click Generate MCQs below","memory_tricks":"👆 Click Memory Tricks below"}
#             st.markdown(f'<div style="color:#4F8EF7;font-size:12px;margin-bottom:4px;">'
#                         f'{_fl[st.session_state.focus_section]}</div>', unsafe_allow_html=True)
#             st.session_state.focus_section = None

#         # Ask bar
#         st.markdown('<div class="ask-bar-card">', unsafe_allow_html=True)
#         st.markdown('<div class="card-title">💬 Ask a Question</div>', unsafe_allow_html=True)

#         _scope_opts = ["All Notes"] + list(st.session_state.documents.keys())
#         if st.session_state.search_scope not in _scope_opts:
#             st.session_state.search_scope = "All Notes"

#         st.session_state.search_scope = st.selectbox(
#             "Search In", options=_scope_opts,
#             index=_scope_opts.index(st.session_state.search_scope),
#             help="Choose which notes to search, or search across all uploaded PDFs."
#         )
#         question = st.text_input(
#             "", placeholder="Type your exam question here...",
#             key="question_input"
#         )
#         search_clicked = st.button("🔍 Search My Notes", use_container_width=True)
#         st.markdown("</div>", unsafe_allow_html=True)

#         # Tool cards
#         st.markdown("""<div class="tool-grid">
#             <div class="tool-card"><div class="tool-card-icon">📝</div>
#                 <div class="tool-card-title">Study Summary</div>
#                 <div class="tool-card-desc">Key concepts from your notes</div></div>
#             <div class="tool-card"><div class="tool-card-icon">❓</div>
#                 <div class="tool-card-title">Practice Questions</div>
#                 <div class="tool-card-desc">Short & long answer questions</div></div>
#             <div class="tool-card"><div class="tool-card-icon">🎯</div>
#                 <div class="tool-card-title">MCQ Practice</div>
#                 <div class="tool-card-desc">10 multiple choice questions</div></div>
#             <div class="tool-card"><div class="tool-card-icon">🧠</div>
#                 <div class="tool-card-title">Memory Tricks</div>
#                 <div class="tool-card-desc">Mnemonics & exam shortcuts</div></div>
#         </div>""", unsafe_allow_html=True)

#         t1, t2 = st.columns(2)
#         with t1: summary_clicked   = st.button("📝 Generate Summary",   use_container_width=True)
#         with t2: questions_clicked = st.button("❓ Practice Questions", use_container_width=True)
#         t3, t4 = st.columns(2)
#         with t3: mcq_clicked           = st.button("🎯 Generate MCQs",    use_container_width=True)
#         with t4: memory_tricks_clicked = st.button("🧠 Memory Tricks",    use_container_width=True)

#     # ── RIGHT PANEL ──
#     with right_panel:

#         # ── History panel ──
#         if st.session_state.show_history:
#             st.markdown('<div class="history-panel">', unsafe_allow_html=True)
#             hc1, hc2 = st.columns([2, 1])
#             with hc1:
#                 st.markdown('<div class="card-title">🕐 Recent Activity</div>', unsafe_allow_html=True)
#             with hc2:
#                 # PRIORITY 1 FIX: uses _clear_history_only(), never full_reset()
#                 if st.button("🗑 Clear History", key="clear_history", use_container_width=True):
#                     _clear_history_only(); st.rerun()

#             if not st.session_state.study_history:
#                 st.markdown("""<div class="empty-state" style="padding:20px;">
#                     <div class="empty-state-icon">📭</div>
#                     <div class="empty-state-text">No study activity yet.<br>
#                     Generate a summary or ask a question to see your history here.</div>
#                 </div>""", unsafe_allow_html=True)
#             else:
#                 for idx, entry in enumerate(reversed(st.session_state.study_history)):
#                     _exists = _card_exists(entry["card_id"])
#                     _pdf    = entry["pdf_name"]
#                     if len(_pdf) > 28:
#                         _pdf = _pdf[:25] + "..."
#                     e1, e2 = st.columns([3, 1])
#                     with e1:
#                         st.markdown(f"""<div class="history-entry">
#                             <div class="history-time">🕒 {entry['time']} &nbsp;•&nbsp; {_time_ago(entry['time'])}</div>
#                             <div class="history-type">{entry['type']}</div>
#                             <div class="history-pdf">{_pdf}</div>
#                         </div>""", unsafe_allow_html=True)
#                     with e2:
#                         if _exists:
#                             if st.button("Open", key=f"hist_open_{idx}", use_container_width=True):
#                                 st.session_state.highlighted_card = entry["card_id"]
#                                 st.session_state.show_history     = False; st.rerun()
#                         else:
#                             st.markdown('<div style="font-size:11px;color:#4A5578;padding:8px 0;text-align:center;">Deleted</div>',
#                                         unsafe_allow_html=True)

#             st.markdown("</div>", unsafe_allow_html=True)

#         # Workspace toolbar
#         wc1, wc2, wc3 = st.columns([2, 1, 0.7])
#         with wc1:
#             st.markdown('<div class="workspace-title">🗂️ Study Workspace</div>'
#                         '<div class="workspace-sub">Your generated study material appears here.</div>',
#                         unsafe_allow_html=True)
#         with wc2:
#             if st.session_state.workspace_cards:
#                 _today = datetime.now().strftime("%Y-%m-%d")
#                 st.download_button(
#                     label="📦 Export All (PDF)",
#                     data=build_pdf_all(st.session_state.workspace_cards, st.session_state.search_scope),
#                     file_name=f"Study_Export_{_today}.pdf", mime="application/pdf",
#                     use_container_width=True, key="export_all_pdf",
#                     help="Download all responses as a single PDF"
#                 )
#             else:
#                 st.button("📦 Export All", disabled=True, use_container_width=True,
#                           key="export_all_disabled",
#                           help="Generate at least one response to enable export.")
#         with wc3:
#             if not st.session_state.confirm_clear_all:
#                 st.markdown('<div class="clear-all-btn">', unsafe_allow_html=True)
#                 if st.button("🗑️ Clear All", use_container_width=True, key="clear_all_trigger",
#                              help="Remove all responses and reset the workspace"):
#                     st.session_state.confirm_clear_all = True; st.rerun()
#                 st.markdown("</div>", unsafe_allow_html=True)
#             else:
#                 st.markdown('<div class="clear-all-btn">', unsafe_allow_html=True)
#                 if st.button("✖ Cancel", use_container_width=True, key="cancel_clear"):
#                     st.session_state.confirm_clear_all = False; st.rerun()
#                 st.markdown("</div>", unsafe_allow_html=True)

#         if st.session_state.confirm_clear_all:
#             st.markdown("""<div class="confirm-box">
#                 <div class="confirm-title">⚠️ Clear Everything?</div>
#                 <div class="confirm-list">
#                 This will permanently remove:<br>
#                 • All uploaded PDFs and indexed content<br>
#                 • All AI responses and workspace cards<br>
#                 • All summaries, MCQs, questions, memory tricks<br>
#                 • Study history and session data
#                 </div>
#             </div>""", unsafe_allow_html=True)
#             cc1, cc2 = st.columns(2)
#             with cc1:
#                 if st.button("🗑️ Yes, Clear Everything", key="confirm_clear_all_btn", use_container_width=True):
#                     _full_reset(); st.rerun()
#             with cc2:
#                 if st.button("Keep Studying", key="cancel_clear_all_btn", use_container_width=True):
#                     st.session_state.confirm_clear_all = False; st.rerun()

#         # ── Search ──
#         if search_clicked:
#             if not question.strip():
#                 st.error("✏️ Please type a question before searching.")
#             else:
#                 _qf = None if st.session_state.search_scope == "All Notes" \
#                       else {"source": st.session_state.search_scope}

#                 with st.spinner("🔍 Searching through your notes..."):
#                     _qemb = embed_model.encode(question).tolist()
#                     try:
#                         _res = collection.query(
#                             query_embeddings=[_qemb], n_results=N_RESULTS,
#                             include=["documents","distances","metadatas"],
#                             where=_qf
#                         )
#                     except Exception:
#                         st.error("❌ Search could not be completed. Please try again.")
#                         _res = None

#                 if _res and _res["documents"][0]:
#                     _ctx = "\n\n".join(_res["documents"][0])
#                     with st.spinner("🤖 Generating your answer..."):
#                         _ans, _secs = _call_gemini(_prompt_search(_ctx, question))
#                     if _ans:
#                         _src = "\n\n---\n**Sources used to answer your question:**\n"
#                         for i, (doc, dist, meta) in enumerate(zip(
#                                 _res["documents"][0], _res["distances"][0], _res["metadatas"][0])):
#                             _conf = "High" if dist < 0.5 else ("Medium" if dist < 1.0 else "Low")
#                             _src += f"\n**Source {i+1}** — {meta.get('source','?')} — Relevance: {_conf}\n> {doc[:200]}...\n"
#                         _cid = _add_card("answer", "💬 Answer", _ans + _src, "card-answer", _secs)
#                         _log_history("💬 Search Answer", _cid)
#                         st.session_state.searches_done += 1
#                         st.rerun()
#                 elif _res:
#                     st.error("🔍 No matching content found in your notes for that question. Try rephrasing.")

#         # ── Study tool generators ──
#         if summary_clicked:
#             _run_generator("📝 Analysing your notes and generating a summary...",
#                 "summary","📝 Study Summary","card-summary",
#                 "📝 Summary","summaries_done", _prompt_summary)

#         if questions_clicked:
#             _run_generator("❓ Preparing practice questions from your notes...",
#                 "questions","❓ Practice Questions","card-questions",
#                 "❓ Practice Questions","questions_done", _prompt_questions)

#         if mcq_clicked:
#             _run_generator("🎯 Creating MCQ practice set...",
#                 "mcqs","🎯 MCQ Practice","card-mcqs",
#                 "🎯 MCQs","mcqs_done", _prompt_mcqs)

#         if memory_tricks_clicked:
#             _run_generator("🧠 Generating memory tricks and mnemonics...",
#                 "memorytricks","🧠 Memory Tricks","card-memorytricks",
#                 "🧠 Memory Tricks","memory_tricks_done", _prompt_memory)

#         # ── Render workspace cards ──
#         if not st.session_state.workspace_cards:
#             st.markdown("""<div class="empty-state" style="padding:40px 20px;background:#131826;border:1px solid #1E2438;border-radius:14px;margin-top:8px;">
#                 <div class="empty-state-icon">🗂️</div>
#                 <div class="empty-state-text">Your study workspace is empty.<br>
#                 Ask a question or use the tools on the left to generate study material.</div>
#             </div>""", unsafe_allow_html=True)
#         else:
#             _today = datetime.now().strftime("%Y-%m-%d")
#             for card in list(st.session_state.workspace_cards):
#                 _cid  = card["id"]
#                 _coll = card.get("collapsed", False)
#                 _ago  = _time_ago(card["time"])
#                 _el   = card.get("elapsed", 0.0)
#                 _hl   = "study-card-highlight" if st.session_state.highlighted_card == _cid else ""
#                 if _hl:
#                     st.session_state.highlighted_card = None

#                 # Day 20: show generation time in card header
#                 _elapsed_html = f'<div class="study-card-elapsed">⏱ Generated in {_el}s</div>' if _el else ""

#                 st.markdown(f"""<div class="study-card {card['color']} {_hl}" id="card_{_cid}">
#                     <div class="study-card-header"><div class="study-card-left"><div>
#                         <div class="study-card-title">{card['title']}</div>
#                         <div class="study-card-time">{card['time']} &nbsp;•&nbsp; {_ago}</div>
#                         {_elapsed_html}
#                     </div></div></div>
#                     <div class="study-card-divider"></div>
#                 </div>""", unsafe_allow_html=True)

#                 if st.session_state.get(f"copied_{_cid}"):
#                     st.markdown('<div class="copy-toast">✅ Copied to clipboard!</div>', unsafe_allow_html=True)
#                     if time.time() - st.session_state.get(f"copied_at_{_cid}", 0) > 2:
#                         del st.session_state[f"copied_{_cid}"]

#                 b1, b2, b3, b4 = st.columns([1, 1, 1, 1.2])

#                 with b1:
#                     if st.button("▶ Expand" if _coll else "▼ Collapse",
#                                  key=f"col_{_cid}", use_container_width=True):
#                         for c in st.session_state.workspace_cards:
#                             if c["id"] == _cid:
#                                 c["collapsed"] = not c["collapsed"]
#                         st.rerun()

#                 with b2:
#                     if st.button("📋 Copy", key=f"copy_{_cid}", use_container_width=True,
#                                  help="Copy this response to clipboard"):
#                         _safe = card["content"].replace("`", "\\`")
#                         components.html(f"""<script>(function(){{
#                             var txt=`{_safe}`;
#                             if(navigator.clipboard&&window.isSecureContext){{
#                                 navigator.clipboard.writeText(txt).catch(fb);
#                             }}else{{fb();}}
#                             function fb(){{var t=document.createElement("textarea");
#                                 t.value=txt;t.style.position="fixed";t.style.left="-9999px";
#                                 document.body.appendChild(t);t.focus();t.select();
#                                 document.execCommand("copy");document.body.removeChild(t);}}
#                         }})();</script>""", height=0)
#                         st.session_state[f"copied_{_cid}"]    = True
#                         st.session_state[f"copied_at_{_cid}"] = time.time()
#                         st.rerun()

#                 with b3:
#                     if st.button("🗑 Delete", key=f"del_{_cid}", use_container_width=True,
#                                  help="Remove this response from the workspace"):
#                         st.session_state.workspace_cards = [
#                             c for c in st.session_state.workspace_cards if c["id"] != _cid
#                         ]
#                         st.session_state.pop(f"copied_{_cid}", None)
#                         st.session_state.pop(f"copied_at_{_cid}", None)
#                         st.rerun()

#                 with b4:
#                     st.download_button(
#                         label="📥 Download PDF",
#                         data=build_pdf_single(card, st.session_state.search_scope),
#                         file_name=f"{_safe_filename(card['title'])}_{_today}.pdf",
#                         mime="application/pdf",
#                         use_container_width=True,
#                         key=f"dl_pdf_{_cid}",
#                         help="Download this response as a PDF"
#                     )

#                 if not _coll:
#                     st.markdown('<div class="study-card-body">', unsafe_allow_html=True)
#                     st.markdown(card["content"])
#                     st.markdown("</div>", unsafe_allow_html=True)

#                 st.write("")


# # ==========================================================
# # EMPTY STATE (no documents uploaded)
# # ==========================================================

# else:
#     st.markdown("""
#     <div style="text-align:center;padding:50px 20px;background:#131826;
#         border:1px dashed #1E2438;border-radius:18px;margin-top:14px;">
#         <div style="font-size:52px;margin-bottom:16px;">📘</div>
#         <div style="font-size:20px;font-weight:700;color:#FFFFFF;margin-bottom:8px;">
#             Ready when you are!</div>
#         <div style="font-size:14px;color:#4A5578;line-height:1.8;max-width:420px;margin:0 auto;">
#             Upload your study notes above to get started.<br>
#             The AI will read your PDFs and help you study smarter —<br>
#             summaries, practice questions, MCQs, memory tricks and more.
#         </div>
#     </div>""", unsafe_allow_html=True)


# # ==========================================================
# # FOOTER
# # ==========================================================

# st.markdown("""
# <div class="app-footer">
#     📘 AI Exam Preparation Assistant &nbsp;•&nbsp; Version 2.0 &nbsp;•&nbsp; Built for Students &nbsp;•&nbsp; Day 20 / 30
# </div>""", unsafe_allow_html=True)




# ==========================================================
# AI EXAM PREPARATION ASSISTANT — Production Ready
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

CHROMA_PATH  = "./chroma_db"
CHUNK_SIZE   = 1000
N_RESULTS    = 3
GEMINI_MODEL = "gemini-2.5-flash"
EMBED_MODEL  = "all-MiniLM-L6-v2"

st.set_page_config(
    page_title="AI Exam Preparation Assistant",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded"
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel(GEMINI_MODEL)

# ==========================================================
# CACHED RESOURCES
# ==========================================================

@st.cache_resource
def load_embed_model():
    return SentenceTransformer(EMBED_MODEL)

@st.cache_resource
def get_chroma_collection():
    return chromadb.PersistentClient(path=CHROMA_PATH).get_or_create_collection(name="notes")

embed_model = load_embed_model()
collection  = get_chroma_collection()

# ==========================================================
# SESSION STATE
# ==========================================================

_DEFAULTS = {
    "documents":          {},
    "collection_ready":   False,
    "workspace_cards":    [],
    "highlighted_card":   None,
    "confirm_clear_all":  False,
    "study_history":      [],
    "show_history":       False,
    "drawer_type":        "",
    "searches_done":      0,
    "summaries_done":     0,
    "questions_done":     0,
    "mcqs_done":          0,
    "memory_tricks_done": 0,
    "ai_responses":       0,
    "search_scope":       "All Notes",
    "pending_delete":     None,
    "focus_section":      None,
    "duplicate_notice":   None,
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ==========================================================
# PDF PROCESSING
# ==========================================================

def _chunk_text(text):
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

@st.cache_data(show_spinner=False)
def _extract_chunks(file_bytes: bytes, file_name: str):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text   = "".join(p.extract_text() or "" for p in reader.pages)
        if not text.strip():
            return [], 0, "empty"
        return _chunk_text(text), len(reader.pages), "ok"
    except Exception:
        return [], 0, "error"

@st.cache_data(show_spinner=False)
def _embed_chunks(chunks_tuple: tuple, _file_name: str):
    return embed_model.encode(list(chunks_tuple)).tolist()

def _add_to_chroma(chunks, embeddings, fname):
    existing = collection.get(where={"source": fname})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
    collection.add(
        documents=chunks, embeddings=embeddings,
        metadatas=[{"source": fname} for _ in chunks],
        ids=[f"{fname}_{i}" for i in range(len(chunks))],
    )

# ==========================================================
# GEMINI
# ==========================================================

def _call_gemini(prompt: str):
    try:
        t0   = time.time()
        resp = gemini_model.generate_content(prompt)
        return resp.text, round(time.time() - t0, 1)
    except Exception as e:
        err = str(e).lower()
        if "quota" in err or "429" in err or "rate" in err:
            st.error("The AI service is temporarily busy. Please wait a minute and try again.")
        elif "api_key" in err or "credential" in err or "401" in err:
            st.error("API key issue. Please check your .env file.")
        else:
            st.error("The AI could not complete this request. Please try again.")
        return None, 0

# ==========================================================
# WORKSPACE HELPERS
# ==========================================================

def _add_card(card_type, title, content, color, elapsed=0.0) -> str:
    card_id = f"{card_type}_{int(time.time()*1000)}"
    st.session_state.workspace_cards.append({
        "id": card_id, "type": card_type, "title": title,
        "content": content, "color": color,
        "time": datetime.now().strftime("%H:%M"),
        "collapsed": False, "elapsed": elapsed,
    })
    st.session_state.ai_responses += 1
    return card_id

def _log_history(response_type: str, card_id: str):
    st.session_state.study_history.append({
        "time":     datetime.now().strftime("%H:%M"),
        "type":     response_type,
        "pdf_name": st.session_state.search_scope,
        "card_id":  card_id,
    })

def _card_exists(card_id: str) -> bool:
    return any(c["id"] == card_id for c in st.session_state.workspace_cards)

def _cards_of_type(card_type: str) -> list:
    return [c for c in st.session_state.workspace_cards if c["type"] == card_type]

def _get_active_chunks() -> dict:
    scope = st.session_state.search_scope
    if scope == "All Notes":
        return {n: d["chunks"] for n, d in st.session_state.documents.items()}
    doc = st.session_state.documents.get(scope)
    return {scope: doc["chunks"]} if doc else {}

# ==========================================================
# SESSION MANAGEMENT
# ==========================================================

def _clear_history_only():
    """Clears responses and history ONLY. Documents are NEVER touched."""
    st.session_state.study_history      = []
    st.session_state.workspace_cards    = []
    st.session_state.highlighted_card   = None
    st.session_state.searches_done      = 0
    st.session_state.summaries_done     = 0
    st.session_state.questions_done     = 0
    st.session_state.mcqs_done          = 0
    st.session_state.memory_tricks_done = 0
    st.session_state.ai_responses       = 0

def _full_reset():
    try:
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass
    _extract_chunks.clear()
    _embed_chunks.clear()
    for k in list(_DEFAULTS.keys()):
        st.session_state.pop(k, None)
    for w in ("pdf_uploader", "question_input"):
        st.session_state.pop(w, None)

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
# UTILITIES
# ==========================================================

def _time_ago(ts: str) -> str:
    if not ts:
        return ""
    try:
        now  = datetime.now()
        then = datetime.strptime(ts, "%H:%M")
        diff = (now.hour * 60 + now.minute) - (then.hour * 60 + then.minute)
        if diff <= 0: return "just now"
        if diff == 1: return "1 min ago"
        return f"{diff} min ago"
    except Exception:
        return ""

def _safe_filename(title: str) -> str:
    stem = re.sub(r'[^\w\s-]', '', title).strip()
    return re.sub(r'\s+', '_', stem) or "export"

def _plain_text(md: str) -> str:
    t = re.sub(r'^#{1,6}\s+', '', md, flags=re.MULTILINE)
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t = re.sub(r'\*(.+?)\*',     r'\1', t)
    t = re.sub(r'`(.+?)`',       r'\1', t)
    t = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', t)
    return t.strip()

def _toggle_drawer(dtype: str):
    st.session_state.drawer_type  = "" if st.session_state.drawer_type == dtype else dtype
    st.session_state.show_history = False

# ==========================================================
# GENERIC GENERATOR
# ==========================================================

def _run_generator(spinner_text, card_type, card_title, card_color,
                   history_label, stat_key, build_prompt_fn):
    active = _get_active_chunks()
    if not active:
        st.error("Please upload at least one PDF before using this feature.")
        return
    with st.spinner(spinner_text):
        parts, elapsed = [], 0.0
        for doc_name, doc_chunks in active.items():
            text, secs = _call_gemini(build_prompt_fn(doc_name, doc_chunks))
            if text is None:
                return
            elapsed += secs
            parts.append(f"### {doc_name}\n\n{text}\n\n---\n\n" if len(active) > 1 else text)
    cid = _add_card(card_type, card_title, "".join(parts), card_color, round(elapsed, 1))
    _log_history(history_label, cid)
    st.session_state[stat_key] += 1
    st.rerun()

# ==========================================================
# PDF EXPORT
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
    mk = lambda name, **kw: ParagraphStyle(name, parent=base["Normal"], **kw)
    return {
        "app_title":  mk("AT", fontSize=16, leading=22, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1A56DB"), spaceAfter=2),
        "card_title": mk("CT", fontSize=13, leading=18, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1E3A5F"), spaceBefore=6, spaceAfter=3),
        "meta":       mk("ME", fontSize=9,  leading=13, fontName="Helvetica",
                          textColor=colors.HexColor("#6B7280"), spaceAfter=2),
        "section":    mk("SE", fontSize=12, leading=17, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1E3A5F"), spaceBefore=8, spaceAfter=3),
        "heading":    mk("HE", fontSize=11, leading=15, fontName="Helvetica-Bold",
                          textColor=colors.HexColor("#1F2937"), spaceBefore=5, spaceAfter=2),
        "body":       mk("BO", fontSize=10, leading=15, fontName="Helvetica",
                          textColor=colors.HexColor("#1F2937"), spaceAfter=3, wordWrap="CJK"),
        "bullet":     mk("BU", fontSize=10, leading=15, fontName="Helvetica",
                          textColor=colors.HexColor("#1F2937"),
                          leftIndent=16, bulletIndent=6, spaceAfter=2, wordWrap="CJK"),
        "footer":     mk("FO", fontSize=8,  leading=11, fontName="Helvetica-Oblique",
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

def _make_pdf(buf, title):
    return SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm, title=title)

def _pdf_header(styles, title, scope, gen_time) -> list:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return [
        Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
        Paragraph(title, styles["card_title"]),
        Paragraph(f"Generated: {gen_time}  |  Exported: {now}", styles["meta"]),
        Paragraph(f"Source: {scope}", styles["meta"]),
        Spacer(1,4*mm), HRFlowable(width="100%",thickness=1,color=colors.HexColor("#1A56DB")),
        Spacer(1,5*mm),
    ]

def _pdf_footer(styles) -> list:
    return [
        Spacer(1,8*mm),
        HRFlowable(width="100%",thickness=0.5,color=colors.HexColor("#CBD5E1")),
        Spacer(1,2*mm),
        Paragraph("Generated by AI Exam Preparation Assistant", styles["footer"]),
    ]

def build_pdf_single(card: dict, scope: str) -> io.BytesIO:
    buf, styles = io.BytesIO(), _get_pdf_styles()
    story = _pdf_header(styles, card["title"], scope, card["time"])
    story += _md_to_flowables(card["content"], styles) + _pdf_footer(styles)
    _make_pdf(buf, card["title"]).build(story)
    buf.seek(0); return buf

def build_pdf_all(cards: list, scope: str) -> io.BytesIO:
    buf, styles = io.BytesIO(), _get_pdf_styles()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    story = [
        Paragraph("AI Exam Preparation Assistant", styles["app_title"]),
        Paragraph("Full Study Export", styles["card_title"]),
        Paragraph(f"Exported: {now}  |  Source: {scope}", styles["meta"]),
        Spacer(1,4*mm), HRFlowable(width="100%",thickness=1,color=colors.HexColor("#1A56DB")),
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
    _make_pdf(buf, "Full Export").build(story)
    buf.seek(0); return buf

# ==========================================================
# PROMPTS  (unchanged)
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
    return f"""You are an AI Exam Preparation Assistant.
Create a concise study summary from the notes.
Focus on: Main concepts, Important ideas, Key points, Exam-relevant information.

Notes:
{chr(10).join(doc_chunks)}

Summary:"""

def _prompt_questions(doc_name, doc_chunks):
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
{chr(10).join(doc_chunks)}

Questions:"""

def _prompt_mcqs(doc_name, doc_chunks):
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
{chr(10).join(doc_chunks)}

MCQs:"""

def _prompt_memory(doc_name, doc_chunks):
    return f"""You are an expert exam mentor helping university students remember topics quickly.
Your task is to create highly memorable Memory Tricks from the provided notes.
The goal is NOT to summarize the chapter.
The goal is to help students remember difficult concepts during exams.
Generate only information that actually exists in the notes.

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
{chr(10).join(doc_chunks)}

Memory Tricks:"""

# ==========================================================
# CSS
# ==========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

*, *::before, *::after { font-family: 'Inter', 'Segoe UI', sans-serif; box-sizing: border-box; }

/* Base */
.stApp { background: #07090F; }
.stApp, .stApp p, .stApp label, .stApp span { color: #C8D3E8; }
.block-container { padding: 0.8rem 1.8rem 1.8rem 1.8rem; max-width: 1380px; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0C0F19; border-right: 1px solid #181F30; width: 228px !important;
}
section[data-testid="stSidebar"] * { color: #6B768A !important; }
section[data-testid="stSidebar"] h2 { color: #E8EDF8 !important; font-size: 14px !important; font-weight: 700 !important; }
section[data-testid="stSidebar"] hr { border-color: #181F30 !important; margin: 5px 0; }
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important; border: none !important; color: #6B768A !important;
    text-align: left !important; justify-content: flex-start !important;
    padding: 6px 10px !important; height: auto !important;
    font-size: 12px !important; font-weight: 500 !important;
    border-radius: 7px !important; box-shadow: none !important; width: 100%;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(26,86,219,0.12) !important; color: #5B9BFF !important; transform: none !important;
}

/* Hero */
.hero {
    background: linear-gradient(135deg, #0C1F55 0%, #1246CC 50%, #1A3A9E 100%);
    padding: 24px 32px 20px; border-radius: 14px; margin-bottom: 12px;
    position: relative; overflow: hidden;
    box-shadow: 0 6px 28px rgba(18,70,204,0.28);
}
.hero::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 80% 50%, rgba(250,204,21,0.1) 0%, transparent 55%);
}
.hero-badge {
    display: inline-block; background: rgba(250,204,21,0.12);
    border: 1px solid rgba(250,204,21,0.28); color: #FACC15;
    font-size: 9px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
    padding: 3px 9px; border-radius: 20px; margin-bottom: 8px;
}
.hero h1 { margin: 0 0 5px; font-size: 26px; font-weight: 800; color: #fff; letter-spacing: -0.4px; }
.hero-sub { font-size: 13px; color: rgba(255,255,255,0.65); margin: 0; }
.hero-sub b { color: #FACC15; font-weight: 600; }

/* Welcome strip */
.wstrip {
    background: #0C0F19; border: 1px solid #181F30; border-left: 3px solid #1246CC;
    border-radius: 9px; padding: 9px 14px; margin-bottom: 10px;
}
.wstrip-title { font-size: 12px; font-weight: 700; color: #E8EDF8; }
.wstrip-sub   { font-size: 11px; color: #4B5670; margin-top: 2px; }

/* Cards */
.card { background: #0C0F19; border: 1px solid #181F30; border-radius: 11px; padding: 14px 16px; height: 100%; }
.card-lbl { font-size: 9px; font-weight: 700; color: #2E3A55; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 9px; }

/* Note items */
.note-item { background: #08110A; border: 1px solid #143A1E; border-radius: 8px; padding: 8px 11px; margin-bottom: 5px; }
.note-name { font-size: 11px; font-weight: 600; color: #2ECC80; margin-bottom: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.note-meta { font-size: 9px; color: #3A6048; }
.dup-note  { background: #0C0F19; border: 1px solid #181F30; border-radius: 6px; padding: 4px 9px; font-size: 10px; color: #4B5670; margin-top: 4px; }

/* Stats */
.stat-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 4px; }
.stat-box  { background: #07090F; border: 1px solid #181F30; border-radius: 7px; padding: 8px 6px; text-align: center; }
.stat-val  { font-size: 19px; font-weight: 700; color: #4F8EF7; line-height: 1; }
.stat-lbl  { font-size: 8px; color: #2E3A55; margin-top: 2px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }

.badge { display: inline-block; border-radius: 20px; padding: 2px 8px; font-size: 9px; font-weight: 600; }
.badge-ok  { background: #08110A; color: #2ECC80; border: 1px solid #143A1E; }
.badge-wait{ background: #120E00; color: #FBBF24; border: 1px solid #4A3800; }

/* Section heading */
.ws-heading { font-size: 14px; font-weight: 700; color: #E8EDF8; margin: 12px 0 7px; padding-bottom: 5px; border-bottom: 1px solid #181F30; }

/* Ask card */
.ask-card { background: #0C0F19; border: 1px solid #181F30; border-radius: 11px; padding: 15px 16px; margin-bottom: 12px; }
.ask-lbl  { font-size: 12px; font-weight: 700; color: #E8EDF8; margin-bottom: 9px; }

/* Tool info cards — informational only, no click interaction */
.tool-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-bottom: 10px; }
.tool-card { background: #0C0F19; border: 1px solid #181F30; border-radius: 9px; padding: 12px 11px; }
.t-icon  { font-size: 17px; margin-bottom: 4px; }
.t-title { font-size: 11px; font-weight: 700; color: #C8D3E8; margin-bottom: 2px; }
.t-desc  { font-size: 9px; color: #2E3A55; line-height: 1.3; }

/* Generate buttons — the ONLY way to trigger generation */
.gen-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.gen-grid .stButton > button {
    height: 42px !important; border-radius: 9px !important;
    background: linear-gradient(135deg, #1246CC 0%, #1A3A9E 100%) !important;
    color: #fff !important; font-size: 11px !important; font-weight: 600 !important;
    border: 1px solid rgba(79,142,247,0.2) !important;
    box-shadow: 0 2px 8px rgba(18,70,204,0.22) !important;
    transition: all 0.17s ease !important; letter-spacing: 0.1px;
}
.gen-grid .stButton > button:hover {
    background: linear-gradient(135deg, #1A56DB 0%, #1246CC 100%) !important;
    box-shadow: 0 4px 14px rgba(18,70,204,0.38) !important;
    transform: translateY(-1px) !important;
}
.gen-grid .stButton > button:active { transform: translateY(0) !important; }
.gen-grid .stButton > button:disabled { background: #181F30 !important; color: #2E3A55 !important; box-shadow: none !important; border-color: #181F30 !important; }

/* Global button base */
.stButton > button {
    width: 100%; height: 38px; border-radius: 8px;
    background: #1246CC; color: #fff !important;
    font-size: 12px; font-weight: 600; border: none;
    transition: background 0.17s, transform 0.12s;
}
.stButton > button:hover  { background: #1A56DB; transform: translateY(-1px); }
.stButton > button:active { transform: translateY(0); }

/* Destructive variants */
.del-btn .stButton > button {
    background: transparent !important; border: 1px solid #2A1010 !important;
    color: #F87171 !important; height: 26px !important; font-size: 10px !important;
}
.del-btn .stButton > button:hover { background: #150808 !important; transform: none !important; }

.clr-btn .stButton > button {
    background: transparent !important; border: 1px solid #2A1010 !important;
    color: #F87171 !important; height: 32px !important; font-size: 11px !important;
}
.clr-btn .stButton > button:hover { background: #150808 !important; transform: none !important; }

/* Download */
.stDownloadButton > button {
    width: 100%; height: 38px; border-radius: 8px;
    background: #0C0F19 !important; color: #6B768A !important;
    font-size: 11px !important; font-weight: 600 !important;
    border: 1px solid #181F30 !important; transition: all 0.17s !important;
}
.stDownloadButton > button:hover { background: #181F30 !important; color: #E8EDF8 !important; transform: translateY(-1px) !important; }
.stDownloadButton > button:active { transform: translateY(0) !important; }

/* Search button */
.search-btn .stButton > button { background: #1246CC !important; height: 40px !important; }
.search-btn .stButton > button:hover { background: #1A56DB !important; }

/* Inputs */
.stTextInput > div > div > input {
    border-radius: 8px; background: #07090F !important;
    border: 1px solid #181F30 !important; color: #E8EDF8 !important;
    font-size: 13px; padding: 8px 12px;
}
.stTextInput > div > div > input::placeholder { color: #2E3A55 !important; }
.stTextInput > div > div > input:focus { border-color: #1246CC !important; box-shadow: 0 0 0 2px rgba(18,70,204,0.18) !important; }

.stSelectbox > div > div { background: #07090F !important; border: 1px solid #181F30 !important; border-radius: 8px !important; color: #E8EDF8 !important; }

/* File uploader compact */
[data-testid="stFileUploader"] { background: #07090F; border: 1.5px dashed #181F30; border-radius: 9px; padding: 3px; transition: border-color 0.2s; }
[data-testid="stFileUploader"]:hover { border-color: #1246CC; }
[data-testid="stFileUploader"] * { color: #2E3A55 !important; }
[data-testid="stFileUploader"] section { padding: 6px !important; min-height: unset !important; }

/* Workspace toolbar — aligned */
.ws-toolbar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }

/* Study response cards */
.study-card { border-radius: 11px; border-left: 3px solid; border-top: 1px solid #181F30; border-right: 1px solid #181F30; border-bottom: 1px solid #181F30; background: #0C0F19; margin-bottom: 9px; overflow: hidden; }
.sc-hdr  { padding: 10px 14px; }
.sc-ttl  { font-size: 12px; font-weight: 700; color: #E8EDF8; }
.sc-meta { font-size: 9px; color: #2E3A55; margin-top: 1px; }
.sc-body { padding: 0 14px 13px; color: #C8D3E8; font-size: 13px; line-height: 1.7; }
.sc-div  { height: 1px; background: #181F30; margin: 0 14px; }
.sc-hl   { box-shadow: 0 0 0 2px #1246CC, 0 0 14px rgba(18,70,204,0.28) !important; }

.c-answer  { border-left-color: #2563EB; }
.c-summary { border-left-color: #059669; }
.c-quest   { border-left-color: #D97706; }
.c-mcqs    { border-left-color: #7C3AED; }
.c-memory  { border-left-color: #DC2626; }

/* Copy toast */
.cp-toast { background: #08110A; border: 1px solid #143A1E; color: #2ECC80; border-radius: 6px; padding: 4px 10px; font-size: 10px; text-align: center; margin-bottom: 5px; }

/* Drawer */
.drawer { background: #0A0D17; border: 1px solid #1246CC; border-radius: 11px; padding: 13px; margin-bottom: 9px; box-shadow: 0 4px 18px rgba(18,70,204,0.14); }
.drawer-ttl  { font-size: 11px; font-weight: 700; color: #E8EDF8; margin-bottom: 7px; }
.drawer-empty{ font-size: 10px; color: #2E3A55; padding: 2px 0; }
.drawer-item .stButton > button {
    background: #0C0F19 !important; border: 1px solid #181F30 !important;
    color: #C8D3E8 !important; border-radius: 7px !important; height: auto !important;
    padding: 8px 11px !important; text-align: left !important; justify-content: flex-start !important;
    font-size: 10px !important; font-weight: 400 !important; line-height: 1.4 !important;
    white-space: normal !important; margin-bottom: 4px;
}
.drawer-item .stButton > button:hover { background: #0F1420 !important; border-color: #1246CC !important; color: #E8EDF8 !important; transform: none !important; }

/* History */
.hist { background: #0C0F19; border: 1px solid #181F30; border-radius: 11px; padding: 13px; margin-bottom: 9px; }
.hist-entry { background: #07090F; border: 1px solid #181F30; border-radius: 7px; padding: 7px 10px; margin-bottom: 5px; }
.hist-time  { font-size: 9px; color: #2E3A55; margin-bottom: 1px; }
.hist-type  { font-size: 11px; font-weight: 600; color: #E8EDF8; }
.hist-pdf   { font-size: 9px; color: #4B5670; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Confirm */
.confirm { background: #110808; border: 1px solid #4A1010; border-radius: 9px; padding: 13px; margin-bottom: 9px; }
.confirm-ttl  { font-size: 12px; font-weight: 700; color: #F87171; margin-bottom: 5px; }
.confirm-body { font-size: 10px; color: #6B768A; line-height: 1.6; }

/* Nav section label */
.nav-s { font-size: 8px; font-weight: 700; color: #181F30 !important; letter-spacing: 1.2px; text-transform: uppercase; padding: 5px 0 3px 2px; }

/* Misc */
.stAlert { border-radius: 8px; }
hr { border-color: #181F30 !important; margin: 7px 0; }
h2, h3 { color: #E8EDF8 !important; }
[data-testid="stExpander"] { background: #0C0F19 !important; border: 1px solid #181F30 !important; border-radius: 9px !important; }
.stSpinner > div { border-top-color: #1246CC !important; }

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #07090F; }
::-webkit-scrollbar-thumb { background: #181F30; border-radius: 4px; }

.app-footer { text-align: center; padding: 9px 0 5px; border-top: 1px solid #181F30; margin-top: 10px; font-size: 9px; color: #181F30; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SIDEBAR
# ==========================================================

_BROWSE = [
    ("Answers",        "answer"),
    ("Summaries",      "summary"),
    ("Practice Sets",  "questions"),
    ("MCQs",           "mcqs"),
    ("Memory Tricks",  "memorytricks"),
]

with st.sidebar:
    st.markdown("## AI Exam Assistant")
    st.caption("Smart Learning. Better Results.")
    st.divider()

    st.markdown('<p class="nav-s">Notes</p>', unsafe_allow_html=True)
    st.markdown('<p style="padding:6px 10px;font-size:12px;color:#5B9BFF!important;font-weight:600;">📄 Upload Notes</p>',
                unsafe_allow_html=True)

    st.markdown('<p class="nav-s" style="margin-top:4px">Browse Responses</p>', unsafe_allow_html=True)

    for _lbl, _dtype in _BROWSE:
        _cnt    = len(_cards_of_type(_dtype))
        _btn_lbl = f"{_lbl}  {_cnt}" if _cnt else _lbl
        if st.button(_btn_lbl, key=f"sb_{_dtype}", use_container_width=True):
            _toggle_drawer(_dtype); st.rerun()

    st.divider()
    st.markdown('<p class="nav-s">Activity</p>', unsafe_allow_html=True)

    if st.button("History", key="sb_hist", use_container_width=True):
        st.session_state.show_history = not st.session_state.show_history
        st.session_state.drawer_type  = ""
        st.rerun()

    if st.button("Settings", key="sb_set", use_container_width=True):
        st.session_state.focus_section = "settings"; st.rerun()

# ==========================================================
# HERO
# ==========================================================

st.markdown("""
<div class="hero">
    <div class="hero-badge">AI-Powered Study Assistant</div>
    <h1>AI Exam Preparation Assistant</h1>
    <p class="hero-sub"><b>Smart Learning.</b> Better Revision. Higher Scores.</p>
</div>""", unsafe_allow_html=True)

# ==========================================================
# WELCOME STRIP
# ==========================================================

if st.session_state.study_history:
    _l = st.session_state.study_history[-1]
    st.markdown(f"""<div class="wstrip">
        <div class="wstrip-title">Welcome back!</div>
        <div class="wstrip-sub">Last: {_l['type']} — {_l['pdf_name']} — {_time_ago(_l['time'])}</div>
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div class="wstrip">
        <div class="wstrip-title">Welcome!</div>
        <div class="wstrip-sub">Upload a PDF to begin your study session.</div>
    </div>""", unsafe_allow_html=True)

# ==========================================================
# TOP CARDS ROW
# ==========================================================

c1, c2, c3 = st.columns([1.35, 1.3, 1.0])

# Upload
with c1:
    st.markdown('<div class="card"><div class="card-lbl">Upload Notes</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "PDFs", type=["pdf"], label_visibility="collapsed",
        accept_multiple_files=True, key="pdf_uploader"
    )
    if not uploaded_files:
        st.markdown('<p style="font-size:10px;color:#2E3A55;margin:3px 0;">Drag PDFs here or Browse — max 200 MB</p>',
                    unsafe_allow_html=True)
    if st.session_state.duplicate_notice:
        st.markdown(f'<div class="dup-note">{st.session_state.duplicate_notice} is already in your library.</div>',
                    unsafe_allow_html=True)
        st.session_state.duplicate_notice = None
    st.markdown("</div>", unsafe_allow_html=True)

# Notes list
with c2:
    st.markdown('<div class="card"><div class="card-lbl">Your Notes</div>', unsafe_allow_html=True)
    if st.session_state.documents:
        for fname, data in list(st.session_state.documents.items()):
            if st.session_state.pending_delete == fname:
                st.markdown(f"""<div class="note-item" style="border-color:#4A1010;background:#110808;">
                    <div class="note-name" style="color:#F87171;">Remove {fname}?</div>
                    <div class="note-meta">Removes file and all indexed content.</div>
                </div>""", unsafe_allow_html=True)
                d1, d2 = st.columns(2)
                with d1:
                    if st.button("Yes", key=f"cy_{fname}", use_container_width=True):
                        _delete_document(fname); st.session_state.pending_delete = None; st.rerun()
                with d2:
                    if st.button("Keep", key=f"cn_{fname}", use_container_width=True):
                        st.session_state.pending_delete = None; st.rerun()
            else:
                n1, n2 = st.columns([5, 1])
                with n1:
                    st.markdown(f"""<div class="note-item">
                        <div class="note-name" title="{fname}">{fname}</div>
                        <div class="note-meta">{data['pages']} pages — {data['file_size']} KB — {_time_ago(data['upload_time'])}</div>
                    </div>""", unsafe_allow_html=True)
                with n2:
                    st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                    if st.button("✕", key=f"dn_{fname}", use_container_width=True):
                        st.session_state.pending_delete = fname; st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<p style="font-size:10px;color:#2E3A55;margin:3px 0;">No notes uploaded yet.</p>',
                    unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Stats
with c3:
    st.markdown('<div class="card"><div class="card-lbl">Progress</div>', unsafe_allow_html=True)
    _rdy   = st.session_state.collection_ready
    _badge = f'<span class="badge badge-{"ok" if _rdy else "wait"}">{"Ready" if _rdy else "Waiting"}</span>'
    _tp    = sum(d["pages"] for d in st.session_state.documents.values())
    _s     = st.session_state
    st.markdown(f"""<div class="stat-grid">
        <div class="stat-box"><div class="stat-val">{len(_s.documents)}</div><div class="stat-lbl">Notes</div></div>
        <div class="stat-box"><div class="stat-val">{_tp}</div><div class="stat-lbl">Pages</div></div>
        <div class="stat-box"><div class="stat-val">{_s.searches_done}</div><div class="stat-lbl">Searches</div></div>
        <div class="stat-box"><div class="stat-val">{_s.summaries_done}</div><div class="stat-lbl">Summaries</div></div>
        <div class="stat-box"><div class="stat-val">{_s.questions_done}</div><div class="stat-lbl">Practices</div></div>
        <div class="stat-box"><div class="stat-val">{_s.mcqs_done}</div><div class="stat-lbl">MCQs</div></div>
        <div class="stat-box"><div class="stat-val">{_s.memory_tricks_done}</div><div class="stat-lbl">Tricks</div></div>
        <div class="stat-box"><div class="stat-val">{len(_s.study_history)}</div><div class="stat-lbl">History</div></div>
    </div>
    <div style="text-align:center;margin-top:4px;">{_badge}</div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# PDF PROCESSING
# ==========================================================

if uploaded_files:
    _new = False
    for uf in uploaded_files:
        if uf.name in st.session_state.documents:
            st.session_state.duplicate_notice = uf.name; continue
        _bytes = uf.read()
        _kb    = round(len(_bytes) / 1024, 1)
        with st.status(f"Processing {uf.name}...", expanded=True) as _st:
            st.write("Extracting text...")
            _chunks, _pages, _err = _extract_chunks(_bytes, uf.name)
            if _err != "ok":
                st.error("This PDF could not be read. It may be empty or corrupted.")
                _st.update(label=f"Failed: {uf.name}", state="error", expanded=False); continue
            st.write("Generating embeddings...")
            _embeds = _embed_chunks(tuple(_chunks), uf.name)
            st.write("Indexing for search...")
            try:
                _add_to_chroma(_chunks, _embeds, uf.name)
            except Exception:
                st.error("Indexing failed. Please try again.")
                _st.update(label=f"Failed: {uf.name}", state="error", expanded=False); continue
            st.session_state.documents[uf.name] = {
                "chunks": _chunks, "pages": _pages,
                "file_size": _kb, "upload_time": datetime.now().strftime("%H:%M"),
            }
            st.session_state.collection_ready = True; _new = True
            _st.update(label=f"{uf.name} ready!", state="complete", expanded=False)
    if _new: st.rerun()

# Settings
if st.session_state.focus_section == "settings":
    st.info("Settings will be available in a future update.")
    st.session_state.focus_section = None

# ==========================================================
# MAIN WORKSPACE
# ==========================================================

if st.session_state.documents:

    st.markdown('<div class="ws-heading">Study Workspace</div>', unsafe_allow_html=True)

    lp, rp = st.columns([0.58, 1.0])

    # ── LEFT PANEL ────────────────────────────────────────
    with lp:

        # Ask card
        st.markdown('<div class="ask-card"><div class="ask-lbl">Ask a Question</div>', unsafe_allow_html=True)
        _sopts = ["All Notes"] + list(st.session_state.documents.keys())
        if st.session_state.search_scope not in _sopts:
            st.session_state.search_scope = "All Notes"
        st.session_state.search_scope = st.selectbox(
            "Scope", _sopts, index=_sopts.index(st.session_state.search_scope),
            label_visibility="collapsed"
        )
        question = st.text_input("", placeholder="Type your exam question here...", key="question_input")
        st.markdown('<div class="search-btn">', unsafe_allow_html=True)
        search_clicked = st.button("Search My Notes", use_container_width=True, key="search_btn")
        st.markdown("</div></div>", unsafe_allow_html=True)

        # Tool info cards (informational only — no click, no overlay, no JS)
        st.markdown("""<div class="tool-grid">
            <div class="tool-card"><div class="t-icon">📝</div><div class="t-title">Study Summary</div><div class="t-desc">Key concepts from your notes</div></div>
            <div class="tool-card"><div class="t-icon">❓</div><div class="t-title">Practice Questions</div><div class="t-desc">Short & long answer questions</div></div>
            <div class="tool-card"><div class="t-icon">🎯</div><div class="t-title">MCQ Practice</div><div class="t-desc">10 multiple choice questions</div></div>
            <div class="tool-card"><div class="t-icon">🧠</div><div class="t-title">Memory Tricks</div><div class="t-desc">Mnemonics & exam shortcuts</div></div>
        </div>""", unsafe_allow_html=True)

        # Generate buttons — the ONLY trigger for generation
        st.markdown('<div class="gen-grid">', unsafe_allow_html=True)
        ga, gb = st.columns(2)
        with ga: summary_clicked   = st.button("Generate Summary",   key="gs", use_container_width=True)
        with gb: questions_clicked = st.button("Generate Questions", key="gq", use_container_width=True)
        gc, gd = st.columns(2)
        with gc: mcq_clicked    = st.button("Generate MCQs",          key="gm", use_container_width=True)
        with gd: memory_clicked = st.button("Generate Memory Tricks", key="gt", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── RIGHT PANEL ───────────────────────────────────────
    with rp:

        # Drawer
        if st.session_state.drawer_type:
            _dt     = st.session_state.drawer_type
            _dlbl   = next((l for l, t in _BROWSE if t == _dt), _dt)
            _dcards = _cards_of_type(_dt)

            st.markdown('<div class="drawer">', unsafe_allow_html=True)
            dr1, dr2 = st.columns([3, 1])
            with dr1: st.markdown(f'<div class="drawer-ttl">{_dlbl}</div>', unsafe_allow_html=True)
            with dr2:
                if st.button("Close", key="close_drawer", use_container_width=True):
                    st.session_state.drawer_type = ""; st.rerun()

            if not _dcards:
                st.markdown(f'<div class="drawer-empty">No {_dlbl.lower()} yet.</div>', unsafe_allow_html=True)
            else:
                for _dc in _dcards:
                    _h   = next((h for h in reversed(st.session_state.study_history) if h["card_id"] == _dc["id"]), None)
                    _pdf = (_h["pdf_name"] if _h else st.session_state.search_scope)[:30]
                    _ago = _time_ago(_dc["time"])
                    st.markdown('<div class="drawer-item">', unsafe_allow_html=True)
                    if st.button(f"{_dc['title']}\n{_pdf}\n{_ago}", key=f"d_{_dc['id']}", use_container_width=True):
                        st.session_state.highlighted_card = _dc["id"]
                        st.session_state.drawer_type      = ""
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # History panel
        if st.session_state.show_history:
            st.markdown('<div class="hist">', unsafe_allow_html=True)
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown('<div style="font-size:12px;font-weight:700;color:#E8EDF8;margin-bottom:7px;">Recent Activity</div>', unsafe_allow_html=True)
            with h2:
                st.markdown('<div class="clr-btn">', unsafe_allow_html=True)
                if st.button("Clear", key="clr_h", use_container_width=True):
                    _clear_history_only(); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            if not st.session_state.study_history:
                st.markdown('<p style="font-size:10px;color:#2E3A55;">No activity yet.</p>', unsafe_allow_html=True)
            else:
                for idx, entry in enumerate(reversed(st.session_state.study_history)):
                    _ex  = _card_exists(entry["card_id"])
                    _pdf = entry["pdf_name"][:22] + "..." if len(entry["pdf_name"]) > 22 else entry["pdf_name"]
                    e1, e2 = st.columns([3, 1])
                    with e1:
                        st.markdown(f"""<div class="hist-entry">
                            <div class="hist-time">{entry['time']} — {_time_ago(entry['time'])}</div>
                            <div class="hist-type">{entry['type']}</div>
                            <div class="hist-pdf">{_pdf}</div>
                        </div>""", unsafe_allow_html=True)
                    with e2:
                        if _ex:
                            if st.button("Open", key=f"ho_{idx}", use_container_width=True):
                                st.session_state.highlighted_card = entry["card_id"]
                                st.session_state.show_history     = False; st.rerun()
                        else:
                            st.markdown('<p style="font-size:9px;color:#2E3A55;text-align:center;padding:5px 0;">Deleted</p>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Workspace toolbar — all three items aligned in one row
        wt1, wt2, wt3 = st.columns([2, 1, 0.7])
        with wt1:
            st.markdown('<div class="ws-heading" style="margin-top:0;border-bottom:none;">Study Workspace</div>'
                        '<p style="font-size:9px;color:#2E3A55;margin:-4px 0 4px;">Your generated study material</p>',
                        unsafe_allow_html=True)
        with wt2:
            if st.session_state.workspace_cards:
                _today = datetime.now().strftime("%Y-%m-%d")
                st.download_button("Export All (PDF)",
                    data=build_pdf_all(st.session_state.workspace_cards, st.session_state.search_scope),
                    file_name=f"Study_Export_{_today}.pdf", mime="application/pdf",
                    use_container_width=True, key="exp_all")
            else:
                st.button("Export All", disabled=True, use_container_width=True, key="exp_dis")
        with wt3:
            if not st.session_state.confirm_clear_all:
                st.markdown('<div class="clr-btn">', unsafe_allow_html=True)
                if st.button("Clear All", use_container_width=True, key="clr_trig"):
                    st.session_state.confirm_clear_all = True; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="clr-btn">', unsafe_allow_html=True)
                if st.button("Cancel", use_container_width=True, key="clr_can"):
                    st.session_state.confirm_clear_all = False; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.confirm_clear_all:
            st.markdown("""<div class="confirm">
                <div class="confirm-ttl">Clear Everything?</div>
                <div class="confirm-body">Removes all PDFs, responses, history and session data.</div>
            </div>""", unsafe_allow_html=True)
            ca1, ca2 = st.columns(2)
            with ca1:
                if st.button("Yes, Clear All", key="clr_yes", use_container_width=True):
                    _full_reset(); st.rerun()
            with ca2:
                if st.button("Keep Studying", key="clr_no", use_container_width=True):
                    st.session_state.confirm_clear_all = False; st.rerun()

        # Search
        if search_clicked:
            if not question.strip():
                st.error("Please type a question before searching.")
            else:
                _qf = None if st.session_state.search_scope == "All Notes" \
                      else {"source": st.session_state.search_scope}
                with st.spinner("Searching your notes..."):
                    try:
                        _res = collection.query(
                            query_embeddings=[embed_model.encode(question).tolist()],
                            n_results=N_RESULTS,
                            include=["documents","distances","metadatas"],
                            where=_qf
                        )
                    except Exception:
                        st.error("Search failed. Please try again."); _res = None

                if _res and _res["documents"][0]:
                    _ctx = "\n\n".join(_res["documents"][0])
                    with st.spinner("Generating answer..."):
                        _ans, _secs = _call_gemini(_prompt_search(_ctx, question))
                    if _ans:
                        _src = "\n\n---\n**Sources:**\n"
                        for i, (doc, dist, meta) in enumerate(zip(
                                _res["documents"][0], _res["distances"][0], _res["metadatas"][0])):
                            _conf = "High" if dist < 0.5 else ("Medium" if dist < 1.0 else "Low")
                            _src += f"\n**Source {i+1}** — {meta.get('source','?')} — Relevance: {_conf}\n> {doc[:200]}...\n"
                        _cid = _add_card("answer", "Answer", _ans + _src, "c-answer", _secs)
                        _log_history("Answer", _cid)
                        st.session_state.searches_done += 1; st.rerun()
                elif _res:
                    st.error("No matching content found. Try rephrasing your question.")

        # Generators
        if summary_clicked:
            _run_generator("Generating study summary...",
                "summary","Study Summary","c-summary","Summary","summaries_done",_prompt_summary)

        if questions_clicked:
            _run_generator("Generating practice questions...",
                "questions","Practice Questions","c-quest","Practice Questions","questions_done",_prompt_questions)

        if mcq_clicked:
            _run_generator("Generating MCQs...",
                "mcqs","MCQ Practice","c-mcqs","MCQs","mcqs_done",_prompt_mcqs)

        if memory_clicked:
            _run_generator("Generating memory tricks...",
                "memorytricks","Memory Tricks","c-memory","Memory Tricks","memory_tricks_done",_prompt_memory)

        # Workspace cards
        if not st.session_state.workspace_cards:
            st.markdown("""<div style="text-align:center;padding:28px 14px;background:#0C0F19;
                border:1px solid #181F30;border-radius:11px;margin-top:5px;">
                <div style="font-size:26px;margin-bottom:7px;">📚</div>
                <div style="font-size:11px;color:#2E3A55;">
                    Your workspace is empty.<br>Ask a question or generate study material above.
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            _today = datetime.now().strftime("%Y-%m-%d")
            for card in list(st.session_state.workspace_cards):
                _cid  = card["id"]
                _coll = card.get("collapsed", False)
                _ago  = _time_ago(card["time"])
                _el   = card.get("elapsed", 0.0)
                _hl   = "sc-hl" if st.session_state.highlighted_card == _cid else ""
                if _hl:
                    st.session_state.highlighted_card = None

                st.markdown(f"""<div class="study-card {card['color']} {_hl}" id="sc_{_cid}">
                    <div class="sc-hdr">
                        <div class="sc-ttl">{card['title']}</div>
                        <div class="sc-meta">{card['time']} — {_ago}{f'  ·  {_el}s' if _el else ''}</div>
                    </div>
                    <div class="sc-div"></div>
                </div>""", unsafe_allow_html=True)

                if st.session_state.get(f"cp_{_cid}"):
                    st.markdown('<div class="cp-toast">Copied to clipboard</div>', unsafe_allow_html=True)
                    if time.time() - st.session_state.get(f"cp_at_{_cid}", 0) > 2:
                        del st.session_state[f"cp_{_cid}"]

                b1, b2, b3, b4 = st.columns([1, 1, 1, 1.2])

                with b1:
                    if st.button("Expand" if _coll else "Collapse", key=f"co_{_cid}", use_container_width=True):
                        for c in st.session_state.workspace_cards:
                            if c["id"] == _cid:
                                c["collapsed"] = not c["collapsed"]
                        st.rerun()

                with b2:
                    if st.button("Copy", key=f"cp_{_cid}", use_container_width=True):
                        _pt = _plain_text(card["content"])
                        _js = _pt.replace("\\","\\\\").replace("`","\\`").replace("$","\\$")
                        components.html(f"""<script>
                        (function(){{var t=`{_js}`;
                            if(navigator.clipboard&&window.isSecureContext){{navigator.clipboard.writeText(t);}}
                            else{{var e=document.createElement('textarea');e.value=t;e.style.position='fixed';
                                e.style.opacity='0';document.body.appendChild(e);e.focus();e.select();
                                try{{document.execCommand('copy');}}catch(x){{}}document.body.removeChild(e);}}
                        }})();
                        </script>""", height=0, scrolling=False)
                        st.session_state[f"cp_{_cid}"]    = True
                        st.session_state[f"cp_at_{_cid}"] = time.time()
                        st.rerun()

                with b3:
                    if st.button("Delete", key=f"dc_{_cid}", use_container_width=True):
                        st.session_state.workspace_cards = [
                            c for c in st.session_state.workspace_cards if c["id"] != _cid
                        ]
                        st.session_state.pop(f"cp_{_cid}",    None)
                        st.session_state.pop(f"cp_at_{_cid}", None)
                        st.rerun()

                with b4:
                    st.download_button(
                        "Download PDF",
                        data=build_pdf_single(card, st.session_state.search_scope),
                        file_name=f"{_safe_filename(card['title'])}_{_today}.pdf",
                        mime="application/pdf",
                        use_container_width=True, key=f"dl_{_cid}"
                    )

                if not _coll:
                    st.markdown('<div class="sc-body">', unsafe_allow_html=True)
                    st.markdown(card["content"])
                    st.markdown("</div>", unsafe_allow_html=True)

                st.write("")

# ==========================================================
# EMPTY STATE
# ==========================================================

else:
    st.markdown("""
    <div style="text-align:center;padding:44px 18px;background:#0C0F19;
        border:1.5px dashed #181F30;border-radius:14px;margin-top:10px;">
        <div style="font-size:38px;margin-bottom:10px;">📘</div>
        <div style="font-size:18px;font-weight:700;color:#E8EDF8;margin-bottom:5px;">Ready when you are</div>
        <div style="font-size:12px;color:#2E3A55;line-height:1.6;max-width:320px;margin:0 auto;">
            Upload your study notes above to get started.<br>
            AI will read your PDFs and help you prepare smarter.
        </div>
    </div>""", unsafe_allow_html=True)

# ==========================================================
# FOOTER
# ==========================================================

st.markdown("""
<div class="app-footer">AI Exam Preparation Assistant — Production Ready</div>
""", unsafe_allow_html=True)