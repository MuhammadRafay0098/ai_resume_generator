import os
import re
import json
import warnings
import logging
import streamlit as st
from groq import Groq
from fpdf import FPDF

# Suppress warnings
warnings.filterwarnings('ignore')
logging.getLogger('streamlit').setLevel(logging.CRITICAL)

# Streamlit Page Config
st.set_page_config(
    page_title="AI Resume Generator",
    page_icon="📄",
    layout="wide"
)

# Initialize Groq Client using Streamlit Secrets or Environment Variables
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

class ResumeGenerator:
    def __init__(self):
        self.client = init_groq_client()
        self.model = "openai/gpt-oss-20b"
    
    def clean_json_response(self, content):
        if not content:
            return None
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json_match.group(0)
        return content.strip()
    
    def generate_resume_content(self, data):
        prompt = f"""
Create an ATS-optimized resume in JSON format based on the following candidate information:
- Name: {data.get('name', '')}
- Email: {data.get('email', '')}
- Phone: {data.get('phone', '')}
- LinkedIn: {data.get('linkedin', '')}
- Experience: {data.get('experience', '')}
- Education: {data.get('education', '')}
- Skills: {data.get('skills', '')}
- Projects: {data.get('projects', '')}

Return a valid JSON object matching this exact schema:
{{
    "summary": "Detailed 3-4 sentence professional summary focusing on candidate strengths.",
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "period": "Start Date - End Date",
            "responsibilities": [
                "Key achievement or action bullet point 1",
                "Key achievement or action bullet point 2"
            ]
        }}
    ],
    "education": [
        "Degree | University Name | Year"
    ],
    "skills": [
        "Skill 1", "Skill 2", "Skill 3"
    ],
    "projects": [
        {{
            "name": "Project Name",
            "description": "Brief project description",
            "technologies": ["Tech 1", "Tech 2"]
        }}
    ]
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional resume writer. Respond ONLY with a valid JSON object containing complete resume details."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            cleaned = self.clean_json_response(raw_content)
            
            if cleaned:
                parsed_data = json.loads(cleaned)
                return parsed_data
            
            return self.get_default_resume(data)
                
        except Exception as e:
            st.error(f"AI Generation Error: {str(e)}")
            return self.get_default_resume(data)
    
    def get_default_resume(self, data):
        return {
            "summary": f"Results-driven professional with hands-on experience in {data.get('skills', 'core technologies')}. Dedicated to delivering high-quality outcomes and collaborating effectively with cross-functional teams.",
            "experience": [
                {
                    "title": "Software Developer / Technical Specialist",
                    "company": "Professional Experience",
                    "period": "2022 - Present",
                    "responsibilities": [
                        data.get('experience', 'Developed and maintained key platform components.').split('\n')[0]
                    ]
                }
            ],
            "education": [data.get('education', 'Bachelor of Science')],
            "skills": [s.strip() for s in data.get('skills', '').split(',') if s.strip()] or ["Python", "Streamlit"],
            "projects": []
        }
        
class ResumePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)
    
    def clean_text(self, text):
        if not text:
            return ""
        return str(text).encode('latin-1', 'replace').decode('latin-1').strip()
    
    def create_resume(self, content, user_data):
        self.add_page()
        
        # Calculate available printable width
        effective_page_width = self.w - self.l_margin - self.r_margin
        
        # Name
        self.set_font('Helvetica', 'B', 22)
        self.set_text_color(30, 60, 90)
        self.cell(effective_page_width, 12, self.clean_text(user_data.get('name', '')), 0, 1, 'C')
        
        # Contact
        self.set_font('Helvetica', '', 10)
        self.set_text_color(80, 80, 80)
        contact = []
        if user_data.get('email'): contact.append(f"Email: {user_data['email']}")
        if user_data.get('phone'): contact.append(f"Phone: {user_data['phone']}")
        if user_data.get('linkedin'): contact.append(f"LinkedIn: {user_data['linkedin']}")
        if contact:
            self.cell(effective_page_width, 6, self.clean_text(' | '.join(contact)), 0, 1, 'C')
        self.ln(6)
        
        # Professional Summary
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(30, 60, 90)
        self.cell(effective_page_width, 8, "PROFESSIONAL SUMMARY", 0, 1)
        self.set_draw_color(52, 152, 219)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(3)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(effective_page_width, 5, self.clean_text(content.get('summary', '')))
        self.ln(4)
        
        # Work Experience
        if content.get('experience'):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(30, 60, 90)
            self.cell(effective_page_width, 8, "WORK EXPERIENCE", 0, 1)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            for exp in content['experience']:
                self.set_font('Helvetica', 'B', 11)
                self.set_text_color(0, 0, 0)
                title = self.clean_text(exp.get('title', ''))
                company = self.clean_text(exp.get('company', ''))
                self.cell(effective_page_width, 6, f"{title} - {company}" if company else title, 0, 1)
                
                if exp.get('period'):
                    self.set_font('Helvetica', 'I', 9)
                    self.set_text_color(100, 100, 100)
                    self.cell(effective_page_width, 5, self.clean_text(exp['period']), 0, 1)
                
                self.set_font('Helvetica', '', 10)
                self.set_text_color(0, 0, 0)
                for resp in exp.get('responsibilities', []):
                    clean_resp = self.clean_text(resp)
                    self.multi_cell(effective_page_width, 5, f"- {clean_resp}")
                self.ln(2)
        
        # Education
        if content.get('education'):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(30, 60, 90)
            self.cell(effective_page_width, 8, "EDUCATION", 0, 1)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            self.set_font('Helvetica', '', 10)
            self.set_text_color(0, 0, 0)
            for edu in content['education']:
                self.multi_cell(effective_page_width, 5, f"- {self.clean_text(edu)}")
            self.ln(2)
            
        # Skills
        if content.get('skills'):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(30, 60, 90)
            self.cell(effective_page_width, 8, "SKILLS", 0, 1)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            self.set_font('Helvetica', '', 10)
            self.set_text_color(0, 0, 0)
            skills_text = ', '.join([self.clean_text(s) for s in content['skills']])
            self.multi_cell(effective_page_width, 5, skills_text)
            
def main():
    st.title("📄 AI Resume Generator")
    
    with st.sidebar:
        st.markdown("### Model Active")
        st.info("GPT OSS 20B (Groq Free Tier)")
    
    with st.expander("Personal Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
        with col2:
            phone = st.text_input("Phone *")
            linkedin = st.text_input("LinkedIn")
    
    experience = st.text_area("Work Experience *", height=120)
    education = st.text_area("Education *", height=80)
    skills = st.text_area("Skills *", height=60)
    projects = st.text_area("Projects", height=80)
    
    if st.button("Generate Resume", type="primary", use_container_width=True):
        user_data = {
            'name': name, 'email': email, 'phone': phone,
            'linkedin': linkedin,
            'experience': experience, 'education': education,
            'skills': skills, 'projects': projects
        }
        
        missing = [k for k in ['name', 'email', 'phone', 'experience', 'education', 'skills'] if not user_data[k]]
        if missing:
            st.error(f"Please fill in required fields: {', '.join(missing)}")
            return
        
        with st.spinner("Generating ATS Resume..."):
            generator = ResumeGenerator()
            resume_data = generator.generate_resume_content(user_data)
            
            if resume_data:
                st.success("Resume Generated Successfully!")
                st.subheader("Preview Summary")
                st.info(resume_data.get('summary', ''))
                
                try:
                    pdf = ResumePDF()
                    pdf.create_resume(resume_data, user_data)
                    pdf_bytes = bytes(pdf.output())
                    
                    st.download_button(
                        label="📥 Download PDF Resume",
                        data=pdf_bytes,
                        file_name=f"resume_{name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"PDF Output Error: {str(e)}")

if __name__ == "__main__":
    main()
