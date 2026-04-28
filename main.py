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
try:
    API_KEY = st.secrets["GROQ_API_KEY"]
except:
    API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=API_KEY)

# ==========================
# PDF TEXT EXTRACTION (AI-friendly)
# ==========================
def pdf_to_text(path):
    text = ""
    try:
        # extract_text handles opening the file and looping through pages for you
        text = extract_text(path)
    except Exception as e:
        print(f"Error: {e}")
        pass
    
    print(text)
    return text
    

# ==========================
# CLEAN COLUMN NAME
# ==========================
def clean_col(role):
    return role.lower().replace(" ", "_").replace("/", "_")

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

- github
- linkedin
- portfolio

Rules:
- If any field is missing → return null
- Do NOT guess randomly

=========================
JOB ROLE RULE
=========================
- If job role is mentioned → extract it
- If NOT mentioned:
  - Infer from internship, training, projects, and skills
  

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
LINK EXTRACTION RULE
=========================
- Extract:
  - GitHub profile URL
  - LinkedIn profile URL
  - Portfolio / personal website

- If not present → return null

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
  "skills": [],
  "github": null,
  "linkedin": null,
  "portfolio": null
}}

Resume Text:
{text[:4000]}
"""

# ==========================
# LLM EXTRACTION
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
        st.error(f"LLM Error: {e}")
        return None

# ==========================
# STREAMLIT UI
# ==========================
st.set_page_config(page_title="Resume Parser", layout="wide")

st.title("📂 AI Resume Parser → Multi Role Excel Generator")

job_roles = [
    "Data Scientist", "Machine Learning Engineer", "AI Engineer",
    "Software Engineer", "Backend Developer", "Frontend Developer",
    "Full Stack Developer", "Web Developer",
    "DevOps Engineer", "Cloud Engineer",
    "Cybersecurity Analyst",
    "System Administrator", "Network Engineer",
    "Product Manager", "UI/UX Designer",
    "Accountant", "Business Analyst",
    "Digital Marketing Specialist",
    "HR Manager",
    "Teacher",
    "Content Writer",
    "Mechanical Engineer", "Civil Engineer", "Electrical Engineer",
    "Student", "Intern", "Other"
]

# Multi-select roles
selected_roles = st.multiselect("🎯 Select Target Job Profiles", job_roles)

# Custom roles
custom_roles = st.text_input("✍️ Add Custom Roles (comma separated)")

if custom_roles:
    custom_list = [r.strip() for r in custom_roles.split(",") if r.strip()]
    selected_roles.extend(custom_list)

target_roles = list(set(selected_roles))

st.write("✅ Selected Roles:", target_roles)

# Upload ZIP
zip_file = st.file_uploader("📁 Upload ZIP Folder of Resumes", type=["zip"])

# ==========================
# PROCESS
# ==========================
if st.button("🚀 Process Resumes"):

    if not target_roles:
        st.warning("Please select at least one job role")
        st.stop()

    if not zip_file:
        st.warning("Please upload ZIP file")
        st.stop()

    temp_dir = tempfile.mkdtemp()

    zip_path = os.path.join(temp_dir, zip_file.name)
    with open(zip_path, "wb") as f:
        f.write(zip_file.read())

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    folder_name = os.path.splitext(zip_file.name)[0]

    all_data = []
    pdf_files = []

    for root, _, files in os.walk(temp_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))

    if not pdf_files:
        st.error("No PDF files found")
        st.stop()

    progress = st.progress(0)

    # ==========================
    # PROCESS EACH PDF
    # ==========================
    for i, pdf_path in enumerate(pdf_files):

        st.write(f"📄 Processing: {os.path.basename(pdf_path)}")

        text = pdf_to_text(pdf_path)
        if not text.strip():
            continue

        extracted = extract_with_llm(text)
        if not extracted:
            continue

        # Skills formatting
        extracted["skills"] = ", ".join(extracted.get("skills") or [])

        # ✅ Add selected roles in every row
        extracted["target_roles"] = ", ".join(target_roles)

        # ✅ Expand job roles into columns
        for role in target_roles:
            col_name = f"job_role_{clean_col(role)}"
            extracted[col_name] = role

        # Remove raw dict
        extracted.pop("job_roles", None)

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

        st.dataframe(df)

        with open(output_file, "rb") as f:
            st.download_button(
                "📥 Download Excel",
                f,
                file_name=output_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("No data extracted")
