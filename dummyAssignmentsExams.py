import datetime
from pymongo import MongoClient
import random

# Subjects list
subjects = ["Maths", "Physics", "Biology", "History", "Chemistry", "Geography", "English", "Art", "Music", "Computer Science"]
maths_topics = ["Algebraic Expressions and Equations", "Geometry: Shapes and Angles", "Trigonometry: Sine, Cosine, Tangent", "Probability and Statistics", "Calculus: Differentiation and Integration", "Linear and Quadratic Functions"]
physics_topics = ["Newton's Laws of Motion", "Thermodynamics: Heat and Energy", "Electromagnetic Waves", "Optics: Reflection and Refraction", "Quantum Mechanics: Wave-Particle Duality", "Electricity and Circuits"]
biology_topics = ["Cell Structure and Function", "Genetics and Heredity", "Photosynthesis and Respiration", "Human Anatomy and Physiology", "Evolution and Natural Selection", "Ecosystems and Biodiversity"]
history_topics = ["Ancient Civilizations: Egypt, Greece, Rome", "The Industrial Revolution", "World Wars I and II", "Renaissance and Enlightenment", "Colonialism and Imperialism", "The Cold War Era", "American Revolution and Civil War"]
chemistry_topics = ["Atomic Structure and Periodic Table", "Chemical Bonding and Molecular Geometry", "Thermodynamics: Enthalpy and Entropy", "Acid-Base Reactions and pH", "Organic Chemistry: Hydrocarbons and Functional Groups"]
geography_topics = ["Plate Tectonics and Volcanoes", "Climate Change and Global Warming", "Population Growth and Urbanization", "Rivers and Hydrology", "Biomes: Deserts, Rainforests, and Tundras", "Agriculture and Food Security"]
english_topics = ["Shakespeare and His Works", "Romantic Poetry: Wordsworth and Keats", "Modernism in Literature", "Writing Essays and Arguments", "Grammar and Sentence Structure", "Analyzing Prose and Fiction", "Themes in Dystopian Literature"]
art_topics = ["Renaissance Art: Techniques and Artists", "Impressionism and Post-Impressionism", "Abstract Art: Cubism and Surrealism", "Sculpture: Materials and Methods", "Color Theory and Application", "Digital Art and Design", "Photography: Composition and Lighting"]
music_topics = ["Music Theory: Scales and Chords", "Classical Composers: Mozart, Beethoven, Bach", "Jazz and Blues: Origins and Evolution", "Popular Music Genres: Rock, Pop, Hip-Hop", "Instruments: Strings, Percussion, Wind"]
computer_science_topics = ["Algorithms and Data Structures", "Programming Languages: Python, Java, C++", "Databases and SQL", "Networking: Protocols and Security", "Artificial Intelligence and Machine Learning"]

subject_topics = {
    "Maths": maths_topics,
    "Physics": physics_topics,
    "Biology": biology_topics,
    "History": history_topics,
    "Chemistry": chemistry_topics,
    "Geography": geography_topics,
    "English": english_topics,
    "Art": art_topics,
    "Music": music_topics,
    "Computer Science": computer_science_topics
}

# Connect to MongoDB
client = MongoClient("mongodb+srv://wilsonw12:14Ts5mW4bs7H6dWO@com668class.nre7q.mongodb.net/?retryWrites=true&w=majority&appName=Com668CLASS&tls=true")
db = client["COM668Coursework"]

# Drop collections if existing
db.assignments.drop()
db.exams.drop()

# Grade Boundaries
grade_boundaries = {
    "A*_grade": 90,
    "A_grade": 80,
    "B_grade": 70,
    "C_grade": 60,
    "F_grade": 0
}

# Grading system
def calculate_grade(mark, total_marks):
    if mark is None:  
        return {"score": None, "grade": "Not Submitted"}

    score = (mark / total_marks) * 100 
    if score >= 90:
        grade = "A*"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    else:
        grade = "F"

    return {"score": round(score, 2), "grade": grade}  # Round percentage to 2dp

# Generate past assignments
assignment_data = []
for cls in db.classes.find():
    subject = cls["subject"]
    student_ids = cls["student_ids"]
    
    for i in range(5):
        total_marks = random.randint(80, 100)
        due_date = datetime.datetime.now() - datetime.timedelta(random.randint(0, 90))

        # Generate results for students
        student_results = []
        total_score_sum = 0
        submitted_students = 0
        for student_id in student_ids:
            mark = random.randint(50, total_marks) 
            grade_data = calculate_grade(mark, total_marks)
            total_score_sum += grade_data["score"]
            submitted_students += 1
            student_results.append({
                "student_id": student_id,
                "mark": mark,
                "score": grade_data["score"],
                "grade": grade_data["grade"]
            })
        
        average_score = total_score_sum / max(1, submitted_students)  
        
        assignment_data.append({
            "class_id": cls["_id"],
            "title": f"{subject} Assignment {i+1}",
            "topics": random.choice(subject_topics.get(subject, ["General Topic"])),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "total_marks": total_marks,
            "average_score": round(average_score, 2), 
            "results": student_results,
            **grade_boundaries  
        })

# Generate future assignments (2-3 per class)
for cls in db.classes.find():
    subject = cls["subject"]
    for i in range(random.randint(2, 3)):
        due_date = datetime.datetime.now() + datetime.timedelta(random.randint(1, 30))
        
        assignment_data.append({
            "class_id": cls["_id"],
            "title": f"{subject} Future Assignment {i+1}",
            "topics": random.choice(subject_topics.get(subject, ["General Topic"])),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "total_marks": random.randint(80, 100),
            "average_score": None,
            "results": [],
            **grade_boundaries
        })

db.assignments.insert_many(assignment_data)


# Get all students for a year
def get_students_by_year(year):
    student_ids = set()
    for cls in db.classes.find({"year": year}, {"student_ids": 1}):
        student_ids.update(cls["student_ids"])  
    return list(student_ids)

# Generate past exams (5 per subject per year)
exam_data = []
for year in db.classes.distinct('year'):
    for subject in db.classes.distinct('subject'):
        students_in_year = get_students_by_year(year)  # Get all students in year

        for i in range(5):
            total_marks = random.randint(80, 100)
            due_date = datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 90))

            # Generate results for all students in  year
            student_results = []
            total_score_sum = 0
            submitted_students = 0

            for student_id in students_in_year:
                mark = random.randint(50, total_marks)  
                grade_data = calculate_grade(mark, total_marks)
                total_score_sum += grade_data["score"]
                submitted_students += 1
                student_results.append({
                    "student_id": student_id,
                    "mark": mark,
                    "score": grade_data["score"],
                    "grade": grade_data["grade"]
                })

            average_score = total_score_sum / max(1, submitted_students)  # No division by zero

            exam_data.append({
                "title": f"{subject} Exam {i+1}",
                "year": year,
                "subject": subject,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "total_marks": total_marks,
                "average_score": round(average_score, 2),
                "results": student_results,
                **grade_boundaries
            })

# Generate future exams (2-3 per subject/year combination)
for year in db.classes.distinct('year'):
    for subject in db.classes.distinct('subject'):
        for i in range(random.randint(2, 3)):
            due_date = datetime.datetime.now() + datetime.timedelta(days=random.randint(1, 30))

            exam_data.append({
                "title": f"{subject} Future Exam {i+1}",
                "year": year,
                "subject": subject,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "total_marks": random.randint(80, 100),
                "average_score": None,
                "results": [],
                **grade_boundaries
            })

db.exams.insert_many(exam_data)

print("Assignments collection:", db.assignments.count_documents({}))
print("Exams collection:", db.exams.count_documents({}))