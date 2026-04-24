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
Extract the following fields from the resume text.
Return VALID JSON ONLY.

Fields:
- name
- phone
- address
- city
- state
- experience (total experience in months as an integer)
- qualification
- skills (array of skill names only, without version numbers or specifics)

Rules:
- If a field is missing, unclear, or not mentioned, return "Other".
- Correct spelling mistakes and incomplete words when clearly inferable.
- Normalize names, cities, states, and skills to their standard form.
- For experience: Calculate total work experience in months. If only years are given, convert to months (e.g., 2 years = 24 months).
- For skills: Extract only the core skill name without versions, numbers, or specifics (e.g., "Python 3.8" → "Python", "React 18" → "React").
- For address: Include only street/locality, exclude pincode, country code, or other extra details.
- Do NOT guess unknown information.
- Do NOT add explanations or extra text.
- JSON keys must always be present.

Resume Text:
{text[:4000]}  # truncate for safety
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
