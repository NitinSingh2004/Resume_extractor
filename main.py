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
# CONFIG
# ==========================
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
def build_prompt(text):
    return f"""
You are a resume parser.

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
- Do NOT guess any information

Work Status Rules:
- If candidate has full-time job experience → "experience"
- If only internships → "internship"
- If no work experience → "fresher"

Other Rules:
- Normalize names, cities, states
- Skills → remove versions (Python 3 → Python)
- Experience:
  - Convert years → months
  - Return integer only
- Address:
  - Only street/locality (no pincode/country)
- current_company:
  - Most recent company
- job_role:
  - Most recent role/title

STRICT OUTPUT FORMAT:

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
# LLM
# ==========================
def extract_with_llm(text):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[
                {"role": "system", "content": "Return raw JSON only."},
                {"role": "user", "content": build_prompt(text)}
            ]
        )

        content = response.choices[0].message.content.strip()
        content = re.sub(r"```json|```", "", content).strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None

        return json.loads(match.group())

    except Exception as e:
        st.error(e)
        return None

# ==========================
# UI
# ==========================
st.title("📂 Resume Folder Upload → Excel")

zip_file = st.file_uploader("Upload ZIP Folder of Resumes", type=["zip"])

# ==========================
# PROCESS
# ==========================
if st.button("🚀 Process Folder"):

    if not zip_file:
        st.warning("Upload ZIP file")
        st.stop()

    # Create temp dir
    temp_dir = tempfile.mkdtemp()

    # Save zip
    zip_path = os.path.join(temp_dir, zip_file.name)
    with open(zip_path, "wb") as f:
        f.write(zip_file.read())

    # Extract
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Folder name = zip name
    folder_name = os.path.splitext(zip_file.name)[0]

    all_data = []
    pdf_files = []

    # Find all PDFs
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if file.endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))

    progress = st.progress(0)

    for i, pdf_path in enumerate(pdf_files):
        st.write(f"Processing: {os.path.basename(pdf_path)}")

        text = pdf_to_text(pdf_path)
        if not text.strip():
            continue

        extracted = extract_with_llm(text)
        if not extracted:
            continue

        extracted["skills"] = ", ".join(extracted.get("skills", []))
        all_data.append(extracted)

        progress.progress((i + 1) / len(pdf_files))

    # ==========================
    # SAVE EXCEL
    # ==========================
    if all_data:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
        df = pd.DataFrame(all_data)

        output_file = f"{folder_name}.xlsx"
        df.to_excel(output_file, index=False)

        st.success("✅ Done!")

        with open(output_file, "rb") as f:
            st.download_button(
                "📥 Download Excel",
                f,
                file_name=output_file
            )
    else:
        st.error("No data extracted")
