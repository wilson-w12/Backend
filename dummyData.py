import datetime
from bson import ObjectId
from pymongo import MongoClient
import random, bcrypt, json

# Load the JSON file for names
with open(r"C:\Users\willi\OneDrive - Ulster University\Ulster University\Ulster_Y3\COM668 Final Project\Coursework\Backend\names.json", "r") as f:
    names_data = json.load(f)

surnames = names_data["surnames_list"]
names = names_data["names_list"]
# Subjects list
subjects = ["Maths", "Physics", "Biology", "History", "Chemistry", "Geography", "English", "Art", "Music", "Computer Science"]
maths_topics = ["Algebraic Expressions and Equations", "Geometry: Shapes and Angles", "Trigonometry: Sine, Cosine, Tangent", "Probability and Statistics", "Calculus: Differentiation and Integration", "Linear and Quadratic Functions", "Sequences and Series", "Coordinate Geometry", "Matrices and Determinants", "Complex Numbers"]
physics_topics = ["Newton's Laws of Motion", "Thermodynamics: Heat and Energy", "Electromagnetic Waves", "Optics: Reflection and Refraction", "Quantum Mechanics: Wave-Particle Duality", "Electricity and Circuits", "Mechanics: Work, Energy, and Power", "Nuclear Physics: Fission and Fusion", "Fluid Dynamics", "Sound and Acoustics"]
biology_topics = ["Cell Structure and Function", "Genetics and Heredity", "Photosynthesis and Respiration", "Human Anatomy and Physiology", "Evolution and Natural Selection", "Ecosystems and Biodiversity", "Microbiology: Bacteria and Viruses", "Plant Biology: Growth and Development", "Hormonal and Nervous Systems", "Biotechnology and Genetic Engineering"]
history_topics = ["Ancient Civilizations: Egypt, Greece, Rome", "The Industrial Revolution", "World Wars I and II", "Renaissance and Enlightenment", "Colonialism and Imperialism", "The Cold War Era", "American Revolution and Civil War", "French Revolution", "The Middle Ages: Feudalism and Crusades", "Modern Globalization and Its Impact"]
chemistry_topics = ["Atomic Structure and Periodic Table", "Chemical Bonding and Molecular Geometry", "Thermodynamics: Enthalpy and Entropy", "Acid-Base Reactions and pH", "Organic Chemistry: Hydrocarbons and Functional Groups", "Electrochemistry: Redox Reactions", "Chemical Kinetics and Reaction Rates", "Stoichiometry and Balancing Equations", "Solutions and Solubility", "Industrial Chemistry and Applications"]
geography_topics = ["Plate Tectonics and Volcanoes", "Climate Change and Global Warming", "Population Growth and Urbanization", "Rivers and Hydrology", "Biomes: Deserts, Rainforests, and Tundras", "Agriculture and Food Security", "Economic Geography: Trade and Industry", "Natural Disasters: Earthquakes and Hurricanes", "Geopolitics and Borders", "Renewable and Non-Renewable Resources"]
english_topics = ["Shakespeare and His Works", "Romantic Poetry: Wordsworth and Keats", "Modernism in Literature", "Writing Essays and Arguments", "Grammar and Sentence Structure", "Analyzing Prose and Fiction", "Themes in Dystopian Literature", "Literary Devices: Metaphor, Simile, Irony", "Short Stories and Narrative Techniques", "Exploring Different Genres: Fantasy, Mystery, Historical Fiction"]
art_topics = ["Renaissance Art: Techniques and Artists", "Impressionism and Post-Impressionism", "Abstract Art: Cubism and Surrealism", "Sculpture: Materials and Methods", "Color Theory and Application", "Digital Art and Design", "Photography: Composition and Lighting", "Art in Different Cultures: African, Asian, Native American", "Modern Street Art and Graffiti", "Art Criticism and Analysis"]
music_topics = ["Music Theory: Scales and Chords", "Classical Composers: Mozart, Beethoven, Bach", "Jazz and Blues: Origins and Evolution", "Popular Music Genres: Rock, Pop, Hip-Hop", "Instruments: Strings, Percussion, Wind", "Reading and Writing Musical Notation", "The Science of Sound and Acoustics", "Film and Video Game Music", "World Music: Traditions and Instruments", "Composing and Arranging Songs"]
computer_science_topics = ["Algorithms and Data Structures", "Programming Languages: Python, Java, C++", "Databases and SQL", "Networking: Protocols and Security", "Artificial Intelligence and Machine Learning", "Operating Systems: Linux, Windows, MacOS", "Web Development: HTML, CSS, JavaScript", "Cybersecurity and Ethical Hacking", "Mobile App Development", "Cloud Computing and Virtualization"]

genders = ['Male', 'Female', 'Other']

grade_scale = ["A*", "A", "B", "C"]  

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")  
db = client["COM668Coursework"]  

# Drop collections 
db.teachers.drop()
db.students.drop()
db.classes.drop()

  
# Function to generate random UK phone numbers
def generate_phone_number():
    return f"07{random.randint(100000000, 999999999)}"

teacher_data = []
# Create between 5 to 8 teachers for each subject
for subject in subjects:
    num_teachers = random.randint(5, 8)  # Number of teachers per subject
    for i in range(num_teachers):
        teacher_data.append({
            "_id": ObjectId(),
            "title": random.choice(["Mr.", "Ms.", "Dr.", "Mrs."]),
            "first_name": random.choice(names),
            "last_name": random.choice(surnames),
            "gender": random.choice(genders),
            "email": f"{random.choice(names).lower()}{random.choice(surnames).lower()}@example.com",  # Email format
            "password": bcrypt.hashpw(f"password{len(teacher_data)+1}".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),  # Decode to string
            "phone": generate_phone_number(),  # Generate random phone number
            "subjects": random.sample(subjects, random.randint(1, 2))  # Assign 1 or 2 subjects
        })

# Insert teachers into the collection
db.teachers.insert_many(teacher_data)

# Update Test Teacher (T011)
test_teacher_update = {
    "_id": ObjectId(),
    "title": "Mr.",
    "first_name": "Test",
    "last_name": "User",
    "gender": random.choice(genders),
    "email": "williambrett418@gmail.com",  
    "password": bcrypt.hashpw("test".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),  
    "phone": "07123456789",  
    "subjects": subjects,
    "role": "teacher"
}
db.teachers.insert_one(test_teacher_update)

# Admin
admin_test_teacher_update = {
    "_id": ObjectId(),
    "title": "Mr.",
    "first_name": "Test",
    "last_name": "User",
    "gender": random.choice(genders),
    "email": "admin@admin.com",  
    "password": bcrypt.hashpw("test".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),  
    "phone": "07123456789",  
    "subjects": subjects,
    "role": "admin"
}
db.teachers.insert_one(admin_test_teacher_update)


# Generate Student Data
student_data = []
for year in range(8, 13):  # Years 8 to 12
    for set_letter in 'ABCDEFGHIJ':  # Sets a to j
        num_students = random.randint(20, 30)  # Number of students in this set
        for _ in range(num_students):
            # Generate random target grades for each student for each subject
            target_grades = {subject: random.choice(grade_scale) for subject in subjects}

            student_data.append({
                "_id": ObjectId(),  
                "first_name": random.choice(names),
                "last_name": random.choice(surnames),
                "gender": random.choice(genders),
                "year": year,  
                "set": set_letter.upper(),
                "target_grades": target_grades  # Assign target grades to the student
            })

db.students.insert_many(student_data)

# Create Index on Year and Set fields
db.students.create_index([("year", 1), ("set", 1)])


# Create Classes Collection and Assign Students
if db.classes.count_documents({}) == 0:
    class_data = []
    for year in range(8, 13):  # Years 8 to 12
        for set_letter in 'ABCDEFGHIJ':  # Sets a to j
            for subject in subjects:  # Create class for each subject
                class_id = f"C{len(class_data)+1:03}"  # Format ID as C001...
                
                # Find students for this year and set
                students_in_set = list(db.students.find({"year": year, "set": set_letter}))
                student_ids = [student["_id"] for student in students_in_set]
                
                class_data.append({
                    "_id": class_id,
                    "subject": subject,
                    "year": year,
                    "set": set_letter.upper(),
                    "teacher_ids": [],  
                    "student_ids": student_ids  
                })

    # Insert the class data into the database
    db.classes.insert_many(class_data)
    print(f"Classes created and students assigned.")

    
# Assign One Teacher to Each Class
for cls in db.classes.find():
    subject = cls["subject"]
    # Find teachers who teach this subject and are not assigned to this class
    available_teachers = list(db.teachers.find({"subjects": {"$regex": f"^{subject}$", "$options": "i"}, "class_ids": {"$ne": cls["_id"]}}))
    if available_teachers:
        # Randomly pick one teacher for this class
        selected_teacher = random.choice(available_teachers)
        db.classes.update_one({"_id": cls["_id"]}, {"$set": {"teacher_ids": [selected_teacher["_id"]]}})
    else:
        print(f"No available teacher found for class {cls['_id']} with subject {subject}")

# Get the test teacher accounts
test_teachers_emails = ["admin@admin.com", "williambrett418@gmail.com"]
test_teachers = list(db.teachers.find({"email": {"$in": test_teachers_emails}}))

# Ensure the teachers exist in the database
if len(test_teachers) != 2:
    print("Error: One or both test teacher accounts not found.")
else:
    # Assign these test teachers to 20 random classes each
    for test_teacher in test_teachers:
        assigned_classes = random.sample(list(db.classes.find()), 20)  # Randomly select 20 classes
        
        for cls in assigned_classes:
            # Ensure the teacher is added to the class
            db.classes.update_one(
                {"_id": cls["_id"]},
                {"$addToSet": {"teacher_ids": test_teacher["_id"]}}  # Use $addToSet to prevent duplicates
            )
# Print confirmation
print("Test teachers assigned to random classes successfully!")


# Print confirmation
print("Data inserted successfully!")
print("Teachers collection:", db.teachers.count_documents({}))
print("Students collection:", db.students.count_documents({}))
print("Classes collection:", db.classes.count_documents({}))