"""将 User ORM 转成可供 LLM 使用的档案字典。"""


def user_profile_dict(user) -> dict:
    return {
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "location": user.location,
        "target_position": user.target_position,
        "educations": [
            {
                "school": e.school, "major": e.major, "degree": e.degree,
                "start_date": e.start_date, "end_date": e.end_date,
                "courses": e.courses, "gpa": e.gpa, "rank": e.rank,
            }
            for e in user.educations
        ],
        "skills": [
            {"category": s.category, "name": s.name, "proficiency": s.proficiency}
            for s in user.skills
        ],
        "projects": [
            {
                "title": p.title, "role": p.role, "tech_stack": p.tech_stack,
                "start_date": p.start_date, "end_date": p.end_date,
                "description": p.description, "result": p.result,
            }
            for p in user.projects
        ],
        "internships": [
            {
                "company": i.company, "position": i.position,
                "start_date": i.start_date, "end_date": i.end_date,
                "description": i.description, "achievement": i.achievement,
            }
            for i in user.internships
        ],
        "certificates": [
            {"name": c.name, "date": c.date, "description": c.description}
            for c in user.certificates
        ],
    }