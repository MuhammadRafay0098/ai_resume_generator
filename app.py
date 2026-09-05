import os
import json
import warnings
import logging
import streamlit as st
from groq import Groq
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
warnings.filterwarnings('ignore')
logging.getLogger('streamlit').setLevel(logging.CRITICAL)

st.set_page_config(
    page_title="AI Resume Generator",
    page_icon="📄",
    layout="wide"
)

ACCENT = (26, 82, 118)
DARK = (33, 47, 60)
BODY = (44, 62, 80)
MUTED = (110, 120, 130)
LINE = (214, 219, 223)


@st.cache_resource
def init_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("❌ GROQ_API_KEY not found! Please add it to Streamlit Secrets.")
        st.stop()
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Failed to initialize Groq: {str(e)}")
        st.stop()


# ---------------------------------------------------------------------------
# PDF Builder
# ---------------------------------------------------------------------------
class ResumePDF(FPDF):
    def __init__(self):
        super().__init__(format='A4')
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(16, 14, 16)
        self.set_title("Resume")

    # -- helpers -------------------------------------------------------
    def clean_text(self, text):
        if text is None:
            return ""
        text = str(text)
        replacements = {
            "•": "-", "–": "-", "—": "-", "’": "'", "‘": "'",
            "“": '"', "”": '"', "…": "...", "\u2022": "-", "\xa0": " ",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.encode('latin-1', 'replace').decode('latin-1').strip()

    def eff_width(self):
        return self.w - self.l_margin - self.r_margin

    def add_section_header(self, title):
        if not title:
            return
        eff_width = self.eff_width()
        # Avoid an orphaned header at the bottom of a page
        if self.get_y() > self.h - self.b_margin - 20:
            self.add_page()
        self.ln(2)
        self.set_font('Helvetica', 'B', 11.5)
        self.set_text_color(*ACCENT)
        self.cell(eff_width, 6.5, self.clean_text(title).upper(), 0, 1, 'L')
        self.set_draw_color(*LINE)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2.5)

    def bullet(self, text, indent=5):
        clean = self.clean_text(text)
        if not clean:
            return
        eff_width = self.eff_width()
        self.set_x(self.l_margin)
        self.set_font('Helvetica', '', 9.5)
        self.set_text_color(*BODY)
        start_y = self.get_y()
        self.cell(indent, 4.6, "-", 0, 0, 'L')
        self.set_xy(self.l_margin + indent, start_y)
        self.multi_cell(eff_width - indent, 4.6, clean)

    # -- main layout -----------------------------------------------------
    def create_resume(self, content, user_data):
        self.add_page()
        eff_width = self.eff_width()

        # ---------- Header ----------
        self.set_font('Helvetica', 'B', 21)
        self.set_text_color(*DARK)
        name = self.clean_text(user_data.get('name', ''))
        self.cell(eff_width, 10, name, 0, 1, 'C')

        self.set_font('Helvetica', '', 9.5)
        self.set_text_color(*MUTED)
        contact_items = []
        for key in ('email', 'phone', 'linkedin'):
            val = user_data.get(key)
            if val:
                contact_items.append(self.clean_text(val))
        if contact_items:
            self.cell(eff_width, 5, '   |   '.join(contact_items), 0, 1, 'C')

        self.set_draw_color(*ACCENT)
        self.set_line_width(0.7)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(5)

        # ---------- Professional Summary ----------
        summary_text = self.clean_text(content.get('summary', ''))
        if summary_text:
            self.add_section_header("Professional Summary")
            self.set_font('Helvetica', '', 9.8)
            self.set_text_color(*BODY)
            self.set_x(self.l_margin)
            self.multi_cell(eff_width, 4.8, summary_text)

        # ---------- Skills (placed early for ATS scanning) ----------
        skills = [s for s in content.get('skills', []) if s]
        if skills:
            self.add_section_header("Core Skills")
            self.set_font('Helvetica', '', 9.5)
            self.set_text_color(*BODY)
            skills_text = '   •   '.join(self.clean_text(s) for s in skills)
            self.set_x(self.l_margin)
            self.multi_cell(eff_width, 4.8, skills_text)

        # ---------- Work Experience ----------
        experience = content.get('experience', [])
        if experience:
            self.add_section_header("Work Experience")
            for i, exp in enumerate(experience):
                title = self.clean_text(exp.get('title', ''))
                company = self.clean_text(exp.get('company', ''))
                period = self.clean_text(exp.get('period', ''))

                header_title = f"{title} - {company}" if (title and company) else (title or company)
                date_width = 48 if period else 0
                title_width = eff_width - date_width

                self.set_font('Helvetica', 'B', 10)
                self.set_text_color(*DARK)
                self.set_x(self.l_margin)
                self.cell(title_width, 5.2, header_title, 0, 0, 'L')

                if period:
                    self.set_font('Helvetica', 'I', 9)
                    self.set_text_color(*MUTED)
                    self.cell(date_width, 5.2, period, 0, 1, 'R')
                else:
                    self.ln(5.2)

                for resp in exp.get('responsibilities', []):
                    self.bullet(resp)

                if i != len(experience) - 1:
                    self.ln(2)
            self.ln(1)

        # ---------- Projects ----------
        projects = content.get('projects', [])
        if projects:
            self.add_section_header("Projects")
            for i, proj in enumerate(projects):
                if isinstance(proj, dict):
                    p_name = self.clean_text(proj.get('name', ''))
                    p_desc = self.clean_text(proj.get('description', ''))
                    p_tech = self.clean_text(proj.get('technologies', ''))

                    self.set_font('Helvetica', 'B', 10)
                    self.set_text_color(*DARK)
                    self.set_x(self.l_margin)
                    self.cell(eff_width, 5.2, p_name, 0, 1, 'L')

                    if p_desc:
                        self.set_font('Helvetica', '', 9.5)
                        self.set_text_color(*BODY)
                        self.set_x(self.l_margin)
                        self.multi_cell(eff_width, 4.6, p_desc)

                    if p_tech:
                        self.set_font('Helvetica', 'I', 9)
                        self.set_text_color(*MUTED)
                        self.set_x(self.l_margin)
                        self.multi_cell(eff_width, 4.6, f"Technologies: {p_tech}")
                else:
                    self.bullet(proj)

                if i != len(projects) - 1:
                    self.ln(1.5)
            self.ln(1)

        # ---------- Education ----------
        education = content.get('education', [])
        if education:
            self.add_section_header("Education")
            for edu in education:
                self.bullet(edu)
            self.ln(1)

        # ---------- Certifications (optional, AI-generated if relevant) ----------
        certifications = content.get('certifications', [])
        if certifications:
            self.add_section_header("Certifications")
            for cert in certifications:
                self.bullet(cert)


# ---------------------------------------------------------------------------
# Resume Content Generator (Groq)
# ---------------------------------------------------------------------------
class ResumeGenerator:
    def __init__(self):
        self.client = init_groq_client()
        self.model = "openai/gpt-oss-20b"  # kept as-is per requirements

    def generate_resume_content(self, data):
        prompt = f"""
You are an expert resume writer and ATS (Applicant Tracking System) optimization specialist.
Rewrite and enhance the candidate's raw details below into a polished, professional, ATS-friendly resume.

Rules:
- Use strong action verbs and quantify achievements wherever plausible (numbers, %, scale).
- Keep the professional summary to 2-3 concise, impactful sentences.
- Each experience entry should have 2-4 concise, high-impact responsibility bullet points.
- Rewrite raw/informal input into clean, professional resume language. Do not invent employers,
  dates, or credentials that are not implied by the input - only rephrase and enhance what is given.
- If projects are provided, summarize each into a short description plus a technologies list.
- If skills are provided, deduplicate and organize them cleanly (avoid repeating full sentences).
- Return ONLY a single valid JSON object, no commentary, no markdown fences, no extra text.

Candidate details:
- Name: {data.get('name', '')}
- Email: {data.get('email', '')}
- Phone: {data.get('phone', '')}
- LinkedIn: {data.get('linkedin', '')}
- Experience: {data.get('experience', '')}
- Education: {data.get('education', '')}
- Skills: {data.get('skills', '')}
- Projects: {data.get('projects', '')}

Required JSON structure (all fields required, use empty list [] or "" when not applicable):
{{
    "summary": "Professional summary paragraph.",
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "period": "Start - End Date",
            "responsibilities": ["Responsibility bullet 1", "Responsibility bullet 2"]
        }}
    ],
    "projects": [
        {{
            "name": "Project Name",
            "description": "One or two sentence description of the project and impact.",
            "technologies": "Comma separated technologies used"
        }}
    ],
    "education": ["Degree, Institution, Year"],
    "skills": ["Skill 1", "Skill 2"],
    "certifications": ["Certification name, Issuer, Year"]
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a specialized JSON resume builder. You always respond with a "
                            "single valid JSON object containing summary, experience, projects, "
                            "education, skills, and certifications."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2500,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            parsed = json.loads(raw_content)
            return self._normalize(parsed, data)
        except Exception as e:
            st.warning(f"⚠️ AI generation failed, using fallback resume. ({str(e)})")
            return self.get_default_resume(data)

    def _normalize(self, parsed, data):
        """Ensure all expected keys exist with the correct types, no matter what the model returns."""
        normalized = {
            "summary": "",
            "experience": [],
            "projects": [],
            "education": [],
            "skills": [],
            "certifications": [],
        }
        if not isinstance(parsed, dict):
            return self.get_default_resume(data)

        normalized["summary"] = str(parsed.get("summary") or "").strip()

        experience = parsed.get("experience")
        if isinstance(experience, list):
            clean_exp = []
            for exp in experience:
                if not isinstance(exp, dict):
                    continue
                resp = exp.get("responsibilities")
                if not isinstance(resp, list):
                    resp = [str(resp)] if resp else []
                clean_exp.append({
                    "title": str(exp.get("title") or "").strip(),
                    "company": str(exp.get("company") or "").strip(),
                    "period": str(exp.get("period") or "").strip(),
                    "responsibilities": [str(r).strip() for r in resp if str(r).strip()],
                })
            normalized["experience"] = clean_exp

        projects = parsed.get("projects")
        if isinstance(projects, list):
            clean_proj = []
            for proj in projects:
                if isinstance(proj, dict):
                    clean_proj.append({
                        "name": str(proj.get("name") or "").strip(),
                        "description": str(proj.get("description") or "").strip(),
                        "technologies": str(proj.get("technologies") or "").strip(),
                    })
                elif proj:
                    clean_proj.append(str(proj).strip())
            normalized["projects"] = clean_proj

        education = parsed.get("education")
        if isinstance(education, list):
            normalized["education"] = [str(e).strip() for e in education if str(e).strip()]
        elif education:
            normalized["education"] = [str(education).strip()]

        skills = parsed.get("skills")
        if isinstance(skills, list):
            normalized["skills"] = [str(s).strip() for s in skills if str(s).strip()]
        elif skills:
            normalized["skills"] = [s.strip() for s in str(skills).split(',') if s.strip()]

        certifications = parsed.get("certifications")
        if isinstance(certifications, list):
            normalized["certifications"] = [str(c).strip() for c in certifications if str(c).strip()]
        elif certifications:
            normalized["certifications"] = [str(certifications).strip()]

        # Guarantee a non-empty summary
        if not normalized["summary"]:
            normalized["summary"] = self.get_default_resume(data)["summary"]

        return normalized

    def get_default_resume(self, data):
        skills_raw = data.get('skills', '') or ''
        return {
            "summary": (
                f"Results-driven professional with hands-on experience in "
                f"{skills_raw or 'core domain skills'}, focused on delivering measurable impact."
            ),
            "experience": [
                {
                    "title": "Professional Role",
                    "company": "Organization",
                    "period": "Recent",
                    "responsibilities": [data.get('experience', 'Managed core operations.') or "Managed core operations."]
                }
            ],
            "projects": (
                [{"name": "Project", "description": data.get('projects', ''), "technologies": ""}]
                if data.get('projects') else []
            ),
            "education": [data.get('education', 'Academic Qualification') or "Academic Qualification"],
            "skills": [s.strip() for s in skills_raw.split(',') if s.strip()] or ["General Skills"],
            "certifications": [],
        }


# ---------------------------------------------------------------------------
# Streamlit App
# ---------------------------------------------------------------------------
def main():
    st.title("📄 AI Resume Generator")
    st.caption("Generate a polished, ATS-friendly resume in seconds — powered by Groq AI.")

    with st.sidebar:
        st.markdown("### Model Active")
        st.info("GPT OSS 20B (Groq Free Tier)")
        st.markdown("---")
        st.markdown(
            "**Tips**\n"
            "- Write your experience/education in plain language — the AI will polish it.\n"
            "- Separate skills with commas.\n"
            "- Fields marked with * are required."
        )

    with st.expander("Personal Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
        with col2:
            phone = st.text_input("Phone *")
            linkedin = st.text_input("LinkedIn (optional)")

    experience = st.text_area("Work Experience *", height=120, placeholder="e.g. Software Engineer at XYZ Corp (2021-2023): built REST APIs, led a team of 3...")
    education = st.text_area("Education *", height=80, placeholder="e.g. BSc Computer Science, ABC University, 2022")
    skills = st.text_area("Skills *", height=60, placeholder="e.g. Python, React, SQL, Team Leadership")
    projects = st.text_area("Projects (optional)", height=80, placeholder="e.g. Built a task management app using React and Firebase")

    generate_clicked = st.button("Generate Resume", type="primary", use_container_width=True)

    if generate_clicked:
        user_data = {
            'name': name.strip(), 'email': email.strip(), 'phone': phone.strip(),
            'linkedin': linkedin.strip(),
            'experience': experience.strip(), 'education': education.strip(),
            'skills': skills.strip(), 'projects': projects.strip()
        }

        required = ['name', 'email', 'phone', 'experience', 'education', 'skills']
        missing = [k for k in required if not user_data[k]]
        if missing:
            st.error(f"Please fill in required fields: {', '.join(missing)}")
            return

        with st.spinner("Generating your AI-enhanced resume..."):
            generator = ResumeGenerator()
            resume_data = generator.generate_resume_content(user_data)

        if resume_data:
            st.success("✅ Resume generated successfully!")
            st.subheader("Preview: Professional Summary")
            st.info(resume_data.get('summary', ''))

            with st.expander("Full Content Preview", expanded=False):
                st.json(resume_data)

            try:
                pdf = ResumePDF()
                pdf.create_resume(resume_data, user_data)
                pdf_bytes = bytes(pdf.output())

                safe_name = "_".join(name.split()) or "resume"
                st.download_button(
                    label="📥 Download PDF Resume",
                    data=pdf_bytes,
                    file_name=f"resume_{safe_name}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF generation error: {str(e)}")


if __name__ == "__main__":
    main()
