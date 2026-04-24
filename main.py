import os
import json
import pandas as pd
import streamlit as st
import zipfile
import tempfile
from pdfminer.high_level import extract_text
from groq import Groq
import re

# ==========================
# CONFIG (LOCAL + CLOUD)
# ==========================
try:
    API_KEY = st.secrets["GROQ_API_KEY"]
except:
    API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=API_KEY)

# ==========================
# PDF TEXT EXTRACTION
# ==========================
def pdf_to_text(path):
    try:
        return extract_text(path)
    except:
        return ""

# ==========================
# PROMPT
# ==========================
def build_prompt(text, target_role):
    return f"""
You are a resume parser.

Target Job Profile: {target_role}

Return ONLY valid JSON. No markdown. No explanation.

Fields (ALL must be present):
- name
- phone
- email
- address
- city
- state
- gender
- marital_status
- current_company
- job_role
- work_status (experience | fresher | internship)
- experience (total experience in months as an integer)
- qualification
- skills (array of skill names only)

Rules:
- If any field is missing → return null
- Do NOT guess randomly

=========================
JOB ROLE RULE
=========================
- If job role is mentioned → extract it
- If NOT mentioned:
  - Infer from internship, training, projects, and skills
  - Align with Target Job Profile: {target_role}

=========================
EXPERIENCE RULE (CRITICAL)
=========================
- INCLUDE ONLY:
  - Full-time job experience

- DO NOT INCLUDE:
  - Internship duration
  - Training programs
  - School/college duration
  - Academic projects

- If candidate has ONLY internship:
  - experience = 0
  - work_status = "internship"

- If candidate has full-time job:
  - experience = total months (job only)
  - work_status = "experience"

- If no job or internship:
  - experience = 0
  - work_status = "fresher"

=========================
OTHER RULES
=========================
- Normalize names, cities, states
- Skills → remove versions (Python 3 → Python)
- Address → only locality
- current_company → most recent company
- job_role → most relevant role

=========================
STRICT OUTPUT FORMAT
=========================

{{
  "name": "",
  "phone": "",
  "email": "",
  "address": "",
  "city": "",
  "state": "",
  "gender": null,
  "marital_status": null,
  "current_company": null,
  "job_role": null,
  "work_status": null,
  "experience": 0,
  "qualification": "",
  "skills": []
}}

Resume Text:
{text[:4000]}
"""


# ==========================
# LLM EXTRACTION
# ==========================
def extract_with_llm(text, target_role):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[
                {"role": "system", "content": "Return raw JSON only."},
                {"role": "user", "content": build_prompt(text, target_role)}
            ]
        )

        content = response.choices[0].message.content.strip()

        # Remove markdown if present
        content = re.sub(r"```json|```", "", content).strip()

        # Extract JSON safely
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None

        return json.loads(match.group())

    except Exception as e:
        st.error(f"LLM Error: {e}")
        return None

# ==========================
# UI
# ==========================
st.set_page_config(page_title="Resume Parser", layout="wide")

st.title("📂 Resume Folder Upload → Excel Parser")

# 🔥 NEW: User input for job profile
target_role = st.text_input("🎯 Enter Target Job Profile (e.g., Data Scientist, Accountant)")

zip_file = st.file_uploader("📁 Upload ZIP Folder of Resumes", type=["zip"])

# ==========================
# PROCESS
# ==========================
if st.button("🚀 Process Resumes"):

    if not target_role:
        st.warning("Please enter target job profile")
        st.stop()

    if not zip_file:
        st.warning("Please upload ZIP file")
        st.stop()

    temp_dir = tempfile.mkdtemp()

    zip_path = os.path.join(temp_dir, zip_file.name)
    with open(zip_path, "wb") as f:
        f.write(zip_file.read())

    # Extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    folder_name = os.path.splitext(zip_file.name)[0]

    all_data = []
    pdf_files = []

    # Collect PDFs
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))

    if not pdf_files:
        st.error("No PDF files found in ZIP")
        st.stop()

    progress = st.progress(0)

    # Process each PDF
    for i, pdf_path in enumerate(pdf_files):
        st.write(f"📄 Processing: {os.path.basename(pdf_path)}")

        text = pdf_to_text(pdf_path)
        if not text.strip():
            continue

        extracted = extract_with_llm(text, target_role)
        if not extracted:
            continue

        # Convert skills list to string
        extracted["skills"] = ", ".join(extracted.get("skills") or [])

        # 🔥 Add target profile column (useful for filtering later)
        extracted["target_role"] = target_role

        all_data.append(extracted)

        progress.progress((i + 1) / len(pdf_files))

    # ==========================
    # SAVE EXCEL
    # ==========================
    if all_data:
        df = pd.DataFrame(all_data)

        output_file = f"{folder_name}.xlsx"
        df.to_excel(output_file, index=False)

        st.success("✅ Processing Complete!")

        # Preview table
        st.dataframe(df)

        # Download button
        with open(output_file, "rb") as f:
            st.download_button(
                "📥 Download Excel",
                f,
                file_name=output_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("No data extracted from resumes")
