import datetime
from datetime import datetime, timedelta, UTC, timezone  
from email.quoprimime import unquote
import os
import random
import re, bson, bcrypt
import logging
from flask import Flask, current_app, make_response, request, jsonify, send_from_directory
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from pymongo import ASCENDING, MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
from functools import wraps
from flask_jwt_extended import JWTManager, create_access_token, decode_token, get_jwt_identity, jwt_required
from flask_cors import CORS
from werkzeug.security import generate_password_hash
from urllib.parse import unquote

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'COM668'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=12) 

logging.basicConfig(level=logging.DEBUG)

# MongoDB connection settings
# client = MongoClient("mongodb://localhost:27017")
client = MongoClient("mongodb+srv://wilsonw12:14Ts5mW4bs7H6dWO@com668class.nre7q.mongodb.net/?retryWrites=true&w=majority&appName=Com668CLASS&tls=true")
db = client["COM668Coursework"]
teacher_collection = db["teachers"]
student_collection = db["students"]
class_collection = db["classes"]

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'class.business.com668@gmail.com' 
app.config['MAIL_PASSWORD'] = 'blpp xgdn vvpt qrnx'  
app.config['MAIL_DEFAULT_SENDER'] = 'class.business.com668@gmail.com'

mail = Mail(app)

bcrypt_flask = Bcrypt(app)

# Memory store for verification codes
verification_codes = {}

jwt = JWTManager(app)

# ----------- Global error handlers ------------

@app.errorhandler(401)
def missing_authorization_header():
    return jsonify({"error": "Not Logged In", "message": "Please log in"}), 401

@app.errorhandler(422)
def handle_jwt_errors(error):
    return jsonify({"error": "Please log in"}), 401  

@app.errorhandler(403)
def handle_forbidden_error(error):
    return jsonify({"error": "Forbidden: Insufficient permissions"}), 403


# ----------- Decorators ------------

# Teacher verification
def teacher_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        current_teacher_id = get_jwt_identity()
        teacher = teacher_collection.find_one({"_id": ObjectId(current_teacher_id)})
        if not teacher:
            return jsonify({"error": "Teacher not found"}), 404
        return func(*args, **kwargs)
    return wrapper

# Is self or admin
def admin_or_self_required(func):
    @wraps(func)
    def wrapper(teacher_id, *args, **kwargs):
        current_user_id = get_jwt_identity()
        current_user = db.teachers.find_one({"_id": ObjectId(current_user_id)})

        if not current_user:
            return jsonify({"error": "User not found"}), 404

        # is_admin = current_user.get("role") == "admin"
        is_admin = current_user.get("role") == "admin"
        is_same_teacher = teacher_id == current_user_id

        if not (is_admin or is_same_teacher):
            return jsonify({"error": "Unauthorized to update this teacher"}), 403

        return func(teacher_id, *args, **kwargs)

    return wrapper

# ----------- Login Endpoints ------------

# Login 
@app.route('/api/login', methods=['POST'])
def login():
    app.logger.debug('Login request received')  
    # Get email and password
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return make_response('Details incorrect', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})
    
    # Check user exists 
    teacher = db.teachers.find_one({"email": email})
    if teacher and bcrypt.checkpw(password.encode('utf-8'), teacher['password'].encode('utf-8')):
        # Is user admin
        is_admin = teacher.get('role') == 'admin'  
        token = create_access_token(identity=str(teacher['_id']), fresh=True)

        return jsonify({
            'message': 'Login successful',
            'token': token,
            'isAdmin': is_admin 
        })
    
    return make_response('Invalid email or password', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})



# Validate token
@app.route('/api/validate-token', methods=['POST'])
def validate_token():
    token = request.json.get("token", None)
    try:
        decoded = decode_token(token)
        return jsonify(valid=True), 200
    except Exception as e:
        return jsonify(valid=False, error=str(e)), 401
    
# ----------- Flask Mail ------------

# Request password reset
@app.route('/api/request-password-reset', methods=['POST'])
def request_password_reset():
    email = request.json.get('email')
    # Check if teacher exists 
    teacher = teacher_collection.find_one({"email": email})
    if not teacher:
        return jsonify({"message": "Email not found"}), 404

    # Generate verification code
    verification_code = random.randint(100000, 999999)
    
    # Store verification code in MongoDB with 15 min expiration
    verification_codes[email] = {
        'code': verification_code,
        'expires_at': datetime.now(UTC) + timedelta(minutes=15) 
    }

    # Send email verification code 
    msg = Message(
        subject='Password Reset Verification Code',
        sender=app.config['MAIL_DEFAULT_SENDER'], 
        recipients=[email],
        body=f'Your verification code is {verification_code}. It expires in 15 minutes.'
    )
    mail.send(msg)

    return jsonify({"message": "Verification code sent to your email."}), 200

# ----------- Teachers Endpoints ------------

# Add teacher
@app.route('/api/teachers', methods=['POST'])  
@jwt_required()
def add_teacher():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['firstName', 'lastName', 'gender', 'email', 'phone', 'password', 'confirmPassword', 'subjects', 'classes']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Check passwords match
    if data['password'] != data['confirmPassword']:
        return jsonify({"error": "Passwords do not match"}), 400

    # Prepare new teacher object
    new_teacher = {
        "title": data.get('title', ''),  
        "first_name": data['firstName'],
        "last_name": data['lastName'],
        "gender": data['gender'],
        "email": data['email'],
        "phone": data['phone'],
        "password": bcrypt.hashpw((data['password']).encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),  
        "subjects": data['subjects'],
        "role": "teacher"
    }

    # Insert teacher 
    result = teacher_collection.insert_one(new_teacher)
    teacher_id = str(result.inserted_id)

    # Update specified classes with new teacher ID
    for class_info in data['classes']:
        # Match class by subject, year, and set 
        class_filter = {
            "subject": class_info['subject'],
            "year": class_info['year'],
            "set": class_info['set']
        }

        class_update = {
            "$addToSet": {
                "teacher_ids": teacher_id  # Add teacher_id to teacher_ids (prevents duplicates)
            }
        }
        
        # Find matching class for subject, year, and set
        result = class_collection.update_one(class_filter, class_update)
        # If no class
        if result.matched_count == 0:
            return jsonify({"error": f"Class with subject {class_info['subject']}, year {class_info['year']}, and set {class_info['set']} not found."}), 404

    return jsonify({"message": "Teacher added and assigned to classes", "teacherId": teacher_id}), 201

# Get teacher's details
@app.route('/api/teachers/<teacher_id>', methods=['GET'])
@jwt_required()
def get_teacher(teacher_id):
    teacher = db.teachers.find_one({"_id": ObjectId(teacher_id)}, {"password": 0})  # Exclude password
    if not teacher:
        return jsonify({"error": "Teacher not found"}), 404
    teacher["_id"] = str(teacher["_id"])
    return jsonify(teacher), 200

# Get all teachers with optional subject filter
@app.route('/api/teachers', methods=['GET'])
@jwt_required()  
def get_all_teachers():
    try:
        # Get optional subject filter
        subject_filter = request.args.get('subject')

        # Get teachers with filter
        teacher_query = {}  
        if subject_filter:
            teacher_query["subjects"] = subject_filter  
        teachers_cursor = teacher_collection.find(teacher_query)

        teachers = []
        for teacher in teachers_cursor:
            teacher["_id"] = str(teacher["_id"])
            teacher_data = {
                "_id": teacher["_id"],
                "title": teacher["title"],
                "first_name": teacher["first_name"],
                "last_name": teacher["last_name"],
                "email": teacher["email"],
                "phone": teacher.get("phone", ""),
                "subjects": teacher["subjects"],
                "classes": []  
            }

            # Get classes for teacher
            class_query = {"teacher_ids": teacher["_id"]}
            classes_cursor = class_collection.find(class_query).sort([("year", 1), ("set", 1)])
            for class_data in classes_cursor:
                teacher_data["classes"].append({
                    "subject": class_data["subject"],
                    "year": class_data["year"],
                    "set": class_data["set"]
                })
            teachers.append(teacher_data)

        return jsonify({"teachers": teachers}), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch teachers", "details": str(e)}), 500

# Update teacher
@app.route('/api/teachers/<teacher_id>', methods=['PUT'])
@jwt_required()
@admin_or_self_required
def update_teacher(teacher_id):    
    update_data = request.json
    allowed_fields = {"title", "first_name", "last_name", "email", "phone", "subjects"}
    
    # Filter only allowed fields
    update_fields = {key: value for key, value in update_data.items() if key in allowed_fields}
    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    # Perform update
    result = db.teachers.update_one({"_id": teacher_id}, {"$set": update_fields})
    if result.modified_count == 0:
        return jsonify({"message": "No changes made or teacher not found"}), 200

    return jsonify({"message": "Teacher details updated successfully"}), 200

# Reset password
@app.route('/api/reset-password', methods=['PUT'])
@jwt_required()
def reset_password():
    data = request.json    
    email = data.get('email')
    teacherId = data.get('teacherId')
    verification_code = data.get('verification_code')
    new_password = data.get('new_password')

    # Check required fields present
    if not email or not verification_code or not new_password:
        return jsonify({"message": "Missing required fields"}), 400  

    # Check email exists
    teacher = teacher_collection.find_one({"email": email})
    if not teacher:
        return jsonify({"message": "Invalid email"}), 400

    # Ensure verification_codes exists
    global verification_codes
    if email not in verification_codes:
        return jsonify({"message": "Invalid email"}), 400

    stored_code = verification_codes[email]
    # Ensure verification_code is integer
    try:
        if int(stored_code['code']) != int(verification_code):
            return jsonify({"message": "Invalid or expired verification code"}), 400
    except ValueError:
        return jsonify({"message": "Invalid verification code format"}), 400

    # Hash new password
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # Update password in the database
    teacher_collection.update_one({"email": email}, {"$set": {"password": hashed_password}})
    # Remove used verification code
    del verification_codes[email]

    return jsonify({"message": "Password reset successful"}), 200

# Update teacher classes
@app.route('/api/update-teachers', methods=['PUT'])
@jwt_required()
def update_teachers():
    data = request.get_json()

    # Check classes exists
    if not data.get('classes'):
        return jsonify({"message": "No classes provided"}), 400

    updated_classes = data.get('classes', [])
    for class_data in updated_classes:
        class_id = class_data.get('class_id')
        selected_teacher_ids = class_data.get('selectedTeacherIds')

        # Check required fields present
        if not class_id or selected_teacher_ids is None:
            return jsonify({"message": "Missing class_id or selectedTeacherIds"}), 400

        class_doc = db.classes.find_one({"_id": class_id})
        if class_doc:
            db.classes.update_one(
                {"_id": class_id},
                {"$set": {"teacher_ids": selected_teacher_ids}}
            )
        else:
            return jsonify({"message": f"Class with ID {class_id} not found"}), 404

    return jsonify({"message": "Teachers updated successfully"})

# Delete teacher
@app.route('/api/teachers/<teacher_id>', methods=['DELETE'])
@jwt_required()
@admin_or_self_required
def delete_teacher(teacher_id):
    try:
        teacher_object_id = ObjectId(teacher_id)
        teacher = teacher_collection.find_one({"_id": teacher_object_id})
        if not teacher:
            return jsonify({"error": "Teacher not found"}), 404

        # Remove teacherfrom classes 
        class_collection.update_many(
            {"teacher_ids": teacher_object_id},
            {"$pull": {"teacher_ids": teacher_object_id}}
        )
        teacher_collection.delete_one({"_id": teacher_object_id})

        return jsonify({"message": "Teacher deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Teacher not found", "details": str(e)}), 500


# ----------- Students CRUD Endpoints ------------

# Add student
@app.route('/api/students', methods=['POST'])
@jwt_required()
def add_student():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['first_name', 'last_name', 'gender', 'year', 'set', 'target_grades']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Prepare the new student object
    new_student = {
        "first_name": data['first_name'],
        "last_name": data['last_name'],
        "gender": data['gender'],
        "year": int(data['year']),  
        "set": data['set'],
        "target_grades": data['target_grades'] 
    }
    
    # Insert student 
    result = student_collection.insert_one(new_student)
    student_id = str(result.inserted_id)
    if 'teachers' in data:
        class_ids = list(data['teachers'].values())
        # Update each class with new student ID
        for class_id in class_ids:
            class_collection.update_one(
                {"_id": class_id},
                {"$addToSet": {"student_ids": student_id}}  # Prevent duplicates
            )
    
    return jsonify({"message": "Student added and assigned to classes", "student_id": student_id}), 201

# Edit student 
@app.route('/api/students/<student_id>', methods=['PUT'])
@jwt_required()
def edit_student(student_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Remove _id  
    data.pop('_id', None)

    student_object_id = ObjectId(student_id)

    student = student_collection.find_one({"_id": student_object_id})
    if not student:
        return jsonify({"error": "Student not found"}), 404

    student_collection.update_one({"_id": student_object_id}, {"$set": data})

    return jsonify({"message": "Student updated successfully"}), 200

# Edit student classes
@app.route('/api/students/<student_id>/classes', methods=['PUT'])
@jwt_required()
def edit_student_classes(student_id):
    data = request.get_json()
    if not data or "classes" not in data:
        return jsonify({"error": "Invalid request. 'classes' field is required."}), 400

    print("Received data:", data)

    student_object_id = ObjectId(student_id)
    student = student_collection.find_one({"_id": student_object_id})
    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Get student's current class IDs
    existing_classes = class_collection.find({"student_ids": student_object_id}, {"_id": 1})
    existing_class_ids = {str(cls["_id"]) for cls in existing_classes}

    # Get classes to add and remove
    new_class_ids = set(data["classes"].values())
    classes_to_add = new_class_ids - existing_class_ids
    classes_to_remove = existing_class_ids - new_class_ids
    if classes_to_remove:
        result = class_collection.update_many(
            {"_id": {"$in": [cls_id for cls_id in classes_to_remove]}}, 
            {"$pull": {"student_ids": student_object_id}}  
        )
        
    # Add student to new classes
    if classes_to_add:
        class_collection.update_many(
            {"_id": {"$in": [cls_id for cls_id in classes_to_add]}},
            {"$addToSet": {"student_ids": student_object_id}}
        )

    return jsonify({"message": "Student classes updated successfully"}), 200

# Delete student
@app.route('/api/students/<student_id>', methods=['DELETE'])
@jwt_required()
def delete_student(student_id):
    student = student_collection.find_one({"_id": ObjectId(student_id)})
    if not student:
        return jsonify({"error": "Student not found"}), 404
    student_collection.delete_one({"_id": ObjectId(student_id)})
    return jsonify({"message": "Student deleted successfully"}), 200

# Get all students details for a class
@app.route('/api/classes/<class_id>/students', methods=['GET'])
@jwt_required()
@teacher_required
def get_students_in_class(class_id):
    try:
        # Get class
        class_record = db.classes.find_one({"_id": class_id})
        if not class_record:
            return jsonify({"message": f"No class found with id {class_id}"}), 404

        # Get subject
        class_subject = class_record.get("subject", "")
        if not class_subject:
            return jsonify({"message": f"No subject found for class {class_id}"}), 404

        # Get student ids
        student_ids = class_record.get("student_ids", [])
        if not student_ids:
            return jsonify({"message": f"No students found for class {class_id}"}), 404
        
        # Get student details
        students = list(db.students.find({"_id": {"$in": student_ids}}))
        if not students:
            return jsonify({"message": f"No students found for class {class_id}"}), 404

        # Get target grades for each student
        for student in students:
            target_grade = student.get("target_grades", {}).get(class_subject, None)
            student["target_grade"] = target_grade if target_grade else "N/A"
            # Remove target_grades
            student.pop("target_grades", None)
            student["_id"] = str(student["_id"])  

        return jsonify({"students": students}), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch students", "details": str(e)}), 500

    
# Get all students with filters
@app.route('/api/students', methods=['GET'])
@jwt_required() 
@teacher_required 
def get_all_students():
    try:
        # Get parameters
        page = int(request.args.get('page', 1))
        page_size = request.args.get('page_size')  
        year = request.args.get('year')  
        student_set = request.args.get('set')
        search_query = request.args.get("search", "").strip()

        # Filter
        query_filter = {}
        if year:
            try:
                query_filter["year"] = int(year)
            except ValueError:
                return jsonify({"error": "Invalid year format"}), 400

        if student_set:
            query_filter["set"] = {"$regex": f"^{student_set}$", "$options": "i"}

        if search_query:
            search_terms = search_query.split()
            search_conditions = [{"first_name": {"$regex": term, "$options": "i"}} for term in search_terms] + \
                                [{"last_name": {"$regex": term, "$options": "i"}} for term in search_terms]
            query_filter["$or"] = search_conditions

        # Get total students
        total_students = student_collection.count_documents(query_filter)

        # Query and sort
        students_query = student_collection.find(query_filter)\
            .sort([("year", ASCENDING), ("set", ASCENDING), ("last_name", ASCENDING), ("first_name", ASCENDING)])

        # Pagination
        if page_size:
            try:
                page_size = int(page_size)
                if page_size > 0:  
                    skip_count = (page - 1) * page_size
                    students_query = students_query.skip(skip_count).limit(page_size)
            except ValueError:
                return jsonify({"error": "Invalid page_size format"}), 400

        # Convert cursor to list
        students = list(students_query)
        for student in students:
            student["_id"] = str(student["_id"])

        return jsonify({
            "students": students,
            "current_page": page if page_size else None,  
            "page_size": page_size if page_size else None,  
            "total_students": total_students
        }), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch students", "details": str(e)}), 500


# Get students filter options
@app.route('/api/students/students-filters', methods=['GET'])
@jwt_required()
@teacher_required
def get_students_filters():
    try:
        # Get unique years and sets
        years = class_collection.distinct("year")
        sets = class_collection.distinct("set")
        if not years or not sets:
            return jsonify({"message": "Class data not available", "Years": [], "Sets": []}), 200

        return jsonify({"years": years, "sets": sets}), 200    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Get student
@app.route('/api/students/<student_id>', methods=['GET'])
@jwt_required()
@teacher_required
def get_student(student_id):
    try:
        # Get student 
        student = db.students.find_one({"_id": ObjectId(student_id)})
        if not student:
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404
        return jsonify(convert_object_ids(student)), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch class details", "details": str(e)}), 500
    
# Get student classes
@app.route('/api/students/<student_id>/classes', methods=['GET'])
@jwt_required()
@teacher_required
def get_student_classes(student_id):
    try:
        # Get student
        student = db.students.find_one({"_id": ObjectId(student_id)})
        if not student:
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404

        # Get student classes 
        student_classes = list(db.classes.find({"student_ids": ObjectId(student_id)}))

        return jsonify({
            "student": convert_object_ids(student),
            "classes": [convert_object_ids(cls) for cls in student_classes]
        }), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch student details", "details": str(e)}), 500
    
# Get student-specific subjects
@app.route('/api/students/<student_id>/student-filters', methods=['GET'])
@jwt_required()
@teacher_required
def get_student_filters(student_id):
    try:
        # Check if student exists
        student = student_collection.find_one({"_id": ObjectId(student_id)})
        if not student:
            return jsonify({"error": f"Student with ID {student_id} not found"}), 404

        # Get enrolled subjects
        enrolled_classes = class_collection.find({"student_ids": ObjectId(student_id)}, {"subject": 1, "_id": 0})
        student_subjects = sorted({cls["subject"] for cls in enrolled_classes})  

        return jsonify({"subjects": student_subjects}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Helper function to convert object ids 
def convert_object_ids(data):
    """Recursively converts ObjectId fields to strings in a JSON-compatible format."""
    if isinstance(data, list):
        return [convert_object_ids(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_object_ids(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)  
    else:
        return data


# ----------- Classes CRUD Endpoints ------------

# Add class
@app.route('/api/classes', methods=['POST'])
@jwt_required()
def add_class():
    data = request.get_json()
    new_class = {
        "_id": data['_id'],
        "subject": data['subject'],
        "year": data['year'],
        "set": data['set'],
        "teacher_ids": data['teacher_ids'],  
        "student_ids": data['student_ids']   
    }
    result = class_collection.insert_one(new_class)
    return jsonify({"message": "Class added", "class_id": str(result.inserted_id)}), 201

# Edit class 
@app.route('/api/classes/<class_id>', methods=['PUT'])
@jwt_required()
def edit_class(class_id):
    data = request.get_json()
    class_data = class_collection.find_one({"_id": class_id})
    if not class_data:
        return jsonify({"error": "Class not found"}), 404
    class_collection.update_one({"_id": class_id}, {"$set": data})
    return jsonify({"message": "Class updated successfully"}), 200

# Delete class
@app.route('/api/classes/<class_id>', methods=['DELETE'])
@jwt_required()
def delete_class(class_id):
    class_data = class_collection.find_one({"_id": class_id})
    if not class_data:
        return jsonify({"error": "Class not found"}), 404
    class_collection.delete_one({"_id": class_id})
    return jsonify({"message": "Class deleted successfully"}), 200


# Get classes with optional filters
@app.route('/api/classes', methods=['GET'])
@jwt_required()
@teacher_required
def get_all_classes():
    try:
        # Query parameters
        page = int(request.args.get('page', 1))  
        page_size = request.args.get('page_size', None) 
        subject = request.args.get('subject')
        year = request.args.get('year')
        set_value = request.args.get('set')  
        teacher_id = request.args.get('teacher')  
        search_terms = request.args.getlist('search_terms[]') 
        my_classes = request.args.get('my_classes', 'false').lower() == 'true'  

        # Convert teacher_id to ObjectId
        if teacher_id:
            try:
                teacher_id = ObjectId(teacher_id)
            except Exception as e:
                return jsonify({"error": "Invalid teacher ID format"}), 400

        # Build the query filter 
        query_filter = {}
        if my_classes:
            query_filter["teacher_ids"] = ObjectId(get_jwt_identity())  
        if teacher_id: 
            query_filter["teacher_ids"] = teacher_id
        if subject:
            query_filter["subject"] = subject
        if year:
            query_filter["year"] = int(year)
        if set_value:
            query_filter["set"] = set_value.capitalize()
        if search_terms:
            search_conditions = []
            for term in search_terms:
                term_conditions = [{"subject": {"$regex": term, "$options": "i"}}]
                if term.isdigit():
                    term_conditions.append({"year": int(term)})
                search_conditions.append({"$or": term_conditions})
            query_filter["$and"] = search_conditions

        # Get total classes matching filters
        total_classes_count = class_collection.count_documents(query_filter)

        # If page_size not provided, return all classes
        if page_size is None:
            classes_cursor = class_collection.find(query_filter)
            classes_data = []
            for c in classes_cursor:
                # Get teacher data
                teacher_ids = c.get("teacher_ids", [])
                teachers = list(teacher_collection.find({"_id": {"$in": teacher_ids}}, {"title": 1, "first_name": 1, "last_name": 1}))
                teacher_list = [{"id": str(t["_id"]), "name": f"{t.get('title')} {t.get('first_name')} {t.get('last_name')}"} for t in teachers]
                # Format response
                classes_data.append({
                    "class_id": str(c.get("_id")),
                    "subject": c.get("subject"),
                    "year": c.get("year"),
                    "set": c.get("set"),
                    "teachers": convert_object_ids(teacher_list)
                })
            return jsonify({
                "classes": classes_data,
                "total_classes": total_classes_count  
            }), 200

        # Handle pagination if page_size provided
        page_size = int(page_size)
        classes_cursor = class_collection.find(query_filter).skip((page - 1) * page_size).limit(page_size)
        classes_data = []
        for c in classes_cursor:
            # Get teacher data
            teacher_ids = c.get("teacher_ids", [])
            teachers = list(teacher_collection.find({"_id": {"$in": teacher_ids}}, {"title": 1, "first_name": 1, "last_name": 1}))
            teacher_list = [{"id": str(t["_id"]), "name": f"{t.get('title')} {t.get('first_name')} {t.get('last_name')}"} for t in teachers]
            # Format response
            classes_data.append({
                "class_id": str(c.get("_id")),
                "subject": c.get("subject"),
                "year": c.get("year"),
                "set": c.get("set"),
                "teachers": convert_object_ids(teacher_list)
            })
        return jsonify({
            "classes": classes_data,
            "total_classes": total_classes_count  
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get class, relevant teachers and students
@app.route('/api/classes/<class_id>', methods=['GET'])
@jwt_required()
@teacher_required
def get_class(class_id):
    try:
        # Fetch class 
        cls = db.classes.find_one({"_id": class_id})
        if not cls:
            return jsonify({"error": f"Class with ID {class_id} not found"}), 404
        student_ids = [ObjectId(student_id) for student_id in cls.get("student_ids", [])]

        # Fetch students
        students = db.students.find({"_id": {"$in": student_ids}})
        student_details = [{"_id": str(student["_id"]), "name": f"{student['first_name']} {student['last_name']}"} for student in students]

        # Fetch teachers
        teachers = db.teachers.find({"_id": {"$in": cls.get("teacher_ids", [])}})
        teacher_details = [{"_id": str(teacher["_id"]), "name": f"{teacher['title']} {teacher['first_name']} {teacher['last_name']}"} for teacher in teachers]

        # Format response
        response = {
            "class": {
                "_id": cls["_id"],  
                "subject": cls.get("subject"),
                "year": cls.get("year"),
                "set": cls.get("set"),
                "students": student_details,
                "teachers": teacher_details
            }
        }

        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch class details", "details": str(e)}), 500

# Get current teacher's classes
@app.route('/api/teacher/classes', methods=['GET'])
@jwt_required()
@teacher_required
def get_teachers_classes():
    try:
        # Get current teacher's classes
        current_teacher_id = get_jwt_identity()
        classes = list(class_collection.find({"teacher_ids": ObjectId(current_teacher_id)}))

        # Format response
        classes_data = [
            {
                "class_id": c.get("_id"),
                "subject": c.get("subject"),
                "year": c.get("year"),
                "set": c.get("set")
            }
            for c in classes
        ]

        return jsonify({"classes": classes_data}), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch classes", "details": str(e)}), 500


# Get total classes for logged-in teacher
@app.route('/api/teacher/classes/total', methods=['GET'])
@jwt_required()
@teacher_required
def get_total_classes():
    try:
        # Get classes for current teacher
        current_teacher_id = get_jwt_identity()
        classes = list(class_collection.find({"teacher_ids": current_teacher_id}))
        
        # Get total classes, class IDs
        total_classes = len(classes)
        class_ids = [cls["_id"] for cls in classes]

        return jsonify({"total_classes": total_classes, "class_ids": class_ids}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# Get total classes per subject for current teacher
@app.route('/api/teacher/classes/subjects/total', methods=['GET'])
@jwt_required()
@teacher_required
def get_classes_per_subject():
    try:
        # Get classes for current teacher
        current_teacher_id = get_jwt_identity()
        classes = list(class_collection.find({"teacher_ids": current_teacher_id}))
        
        if not classes:
            return jsonify({"message": "No classes assigned to this teacher", "subjects": {}}), 200

        # Group classes by subject
        subject_counts = {}
        for cls in classes:
            subject = cls.get("subject")
            if subject:
                subject_counts[subject] = subject_counts.get(subject, 0) + 1

        return jsonify({"subjects": subject_counts}), 200
    except bson.errors.InvalidId:
        return jsonify({"error": "Invalid teacher ID format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# Get class filter options
@app.route('/api/classes/classes-filters', methods=['GET'])
@jwt_required()
@teacher_required
def get_classes_filters():
    try:
        # Get unique teachers 
        teachers_cursor = teacher_collection.find({}, {"_id": 1, "title": 1, "first_name": 1, "last_name": 1})
        teachers = [
            {"id": teacher["_id"], "name": f"{teacher.get('title', '')} {teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()}
            for teacher in teachers_cursor
        ]

        # Get unique subjects, years, and sets
        subjects = class_collection.distinct("subject")
        years = class_collection.distinct("year")
        sets = class_collection.distinct("set")
        if not subjects and not years:
            return jsonify({"message": "No classes found for this teacher", "subjects": [], "years": [], "teachers": []}), 200

        return jsonify({
            "subjects": subjects,
            "years": years,
            "sets": sets,
            "teachers": convert_object_ids(teachers)
        }), 200
    except bson.errors.InvalidId:
        return jsonify({"error": "Invalid teacher ID format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# ----------- Assignments and Exams CRUD Endpoints ------------

# Add assignment 
@app.route('/api/classes/<class_id>/assignments', methods=['POST'])
@jwt_required()
@teacher_required
def add_assignment(class_id):
    try:
        print("Received a request to add an assignment.")
        data = request.json
        if not data:
            return jsonify({"message": "No data provided"}), 400

        # Get class 
        class_details = db.classes.find_one({"_id": class_id})
        if not class_details:
            return jsonify({"message": "Class not found"}), 404
        
        # Presence check necessary fields 
        required_fields = ["title", "topics", "due_date", "total_marks", "A*_grade", "A_grade", "B_grade", "C_grade", "F_grade", "results"]
        for field in required_fields:
            if field not in data:
                return jsonify({"message": f"{field} is required"}), 400

        # Include only necessary fields
        filtered_results = []
        for result in data["results"]:
            filtered_results.append({
                "student_id": ObjectId(result["student_id"]),
                "mark": result["mark"],
                "score": result["score"],
                "grade": result["grade"]
            })

        assignment_data = {
            "class_id": class_id,
            "title": data["title"],
            "topics": data["topics"],
            "due_date": data["due_date"],
            "total_marks": data["total_marks"],
            "A*_grade": data["A*_grade"],
            "A_grade": data["A_grade"],
            "B_grade": data["B_grade"],
            "C_grade": data["C_grade"],
            "F_grade": data["F_grade"],
            "results": filtered_results  
        }
        assignment = db.assignments.insert_one(assignment_data)
        print(f"Assignment added with ID: {assignment.inserted_id}") 

        return jsonify({"message": "Assignment added successfully", "assignment_id": str(assignment.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": "Unable to add assignment", "details": str(e)}), 500
    
# Add exam 
@app.route('/api/exams', methods=['POST'])
@jwt_required()
@teacher_required
def add_exam():
    try:
        print("Received a request to add an exam.")
        data = request.json
        if not data:
            return jsonify({"message": "No data provided"}), 400

        # Presence check necessary fields 
        required_fields = ["title", "year", "subject", "due_date", "total_marks", "A*_grade", "A_grade", "B_grade", "C_grade", "F_grade", "results"]
        for field in required_fields:
            if field not in data:
                return jsonify({"message": f"{field} is required"}), 400

        # Include only necessary fields
        filtered_results = []
        for result in data["results"]:
            filtered_results.append({
                "student_id": ObjectId(result["student_id"]),
                "mark": result["mark"],
                "score": result["score"],
                "grade": result["grade"]
            })

        exam_data = {
            "title": data["title"],
            "year": data["year"],
            "subject": data["subject"],
            "due_date": data["due_date"],
            "total_marks": data["total_marks"],
            "A*_grade": data["A*_grade"],
            "A_grade": data["A_grade"],
            "B_grade": data["B_grade"],
            "C_grade": data["C_grade"],
            "F_grade": data["F_grade"],
            "results": filtered_results  
        }
        exam = db.exams.insert_one(exam_data)
        print(f"Exam added with ID: {exam.inserted_id}") 

        return jsonify({"message": "Exam added successfully", "exam_id": str(exam.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": "Unable to add exam", "details": str(e)}), 500
    
# Delete assignment
@app.route('/api/classes/<class_id>/assignments/<assignment_id>', methods=['DELETE'])
@jwt_required()
@teacher_required
def delete_assignment(class_id, assignment_id):
    try:
        # Check assignment exists
        assignment = db.assignments.find_one({"_id": ObjectId(assignment_id), "class_id": class_id})
        if not assignment:
            return jsonify({"message": "Assignment not found"}), 404
        
        # Delete assignment
        db.assignments.delete_one({"_id": ObjectId(assignment_id), "class_id": class_id})

        return jsonify({"message": "Assignment deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Unable to delete assignment", "details": str(e)}), 500
    
# Delete exam
@app.route('/api/exams/<exam_id>', methods=['DELETE'])
@jwt_required()
@teacher_required
def delete_exam(exam_id):
    try:
        # Check exam exists
        exam = db.exams.find_one({"_id": ObjectId(exam_id)})
        if not exam:
            return jsonify({"message": "Exam not found"}), 404
        
        # Delete exam
        db.exams.delete_one({"_id": ObjectId(exam_id)})

        return jsonify({"message": "Exam deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Unable to delete exam", "details": str(e)}), 500

# Get assignments and exams due today
@app.route('/api/teacher/assignments-exams-due-today', methods=['GET'])
@jwt_required()
@teacher_required
def assignments_exams_due_today():
    try:
        today_date = datetime.now().strftime("%Y-%m-%d")

        # Get teacher's classes
        current_teacher_id = get_jwt_identity()
        classes = list(db.classes.find({"teacher_ids": ObjectId(current_teacher_id)}))

        if not classes:
            return jsonify({"assignments_due_today": [], "exams_due_today": []}), 200

        # Extract class details and map by class_id
        class_ids = [cls["_id"] for cls in classes]
        
        # Get assignments due today
        assignments = list(db.assignments.find({"class_id": {"$in": class_ids}, "due_date": today_date}))
        for assignment in assignments:
            class_id = assignment.get("class_id")
            # Find matching class info for the assignment
            class_info = next(cls for cls in classes if cls["_id"] == class_id)
            # Add class_info to assignment
            assignment["class_info"] = {
                "subject": class_info["subject"],
                "year": class_info["year"],
                "set": class_info["set"],
                "student_ids": class_info.get("student_ids", [])
            }
            # Calculate handed in and awaiting counts for assignments
            class_student_ids = class_info.get("student_ids", [])
            handed_in_count = sum(1 for student_id in class_student_ids if any(result["student_id"] == student_id and result.get("mark") is not None for result in assignment["results"]))
            awaiting_count = len(class_student_ids) - handed_in_count

            # Update assignment with counts
            assignment["handed_in_count"] = handed_in_count
            assignment["awaiting_count"] = awaiting_count

        # Get exams due today (year-wide), for teacher's class students
        exams = list(db.exams.find({"year": {"$in": [cls["year"] for cls in classes]}, "subject": {"$in": [cls["subject"] for cls in classes]}, "due_date": today_date}))
        for exam in exams:
            # Find classes related to this exam's year and subject
            matching_classes = [cls for cls in classes if cls["year"] == exam["year"] and cls["subject"] == exam["subject"]]
            class_student_ids = []
            for cls in matching_classes:
                class_student_ids.extend(cls.get("student_ids", []))

            # Add class_info to exam
            exam["class_info"] = {
                "subject": exam["subject"],
                "year": exam["year"],
                "student_ids": class_student_ids
            }

            # Count student's that have handed in their exam (valid mark exists for student)
            handed_in_count = sum(1 for student_id in class_student_ids if any(result["student_id"] == student_id and result.get("mark") is not None for result in exam["results"]))
            awaiting_count = len(class_student_ids) - handed_in_count

            # Update exam with counts
            exam["handed_in_count"] = handed_in_count
            exam["awaiting_count"] = awaiting_count

        # Format response
        result = {
            "assignments_due_today": convert_object_ids(assignments),
            "exams_due_today": convert_object_ids(exams)
        }

        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500




# Get assignments for class id
@app.route('/api/classes/<class_id>/assignments', methods=['GET'])
@jwt_required()
@teacher_required
def get_class_assignments(class_id):
    try:
        # Get class info using class_id
        class_info = db.classes.find_one({"_id": class_id})
        if not class_info:
            return jsonify({"message": f"Class {class_id} not found"}), 404
        class_info = convert_object_ids(class_info)

        # Get assignments for class
        assignments = list(db.assignments.find({"class_id": class_id}))
        if not assignments:
            return jsonify({"message": f"No assignments found for class {class_id}"}), 404

        assignments = [convert_object_ids(assignment) for assignment in assignments]

        # Get total students
        total_students = len(class_info.get("student_ids", []))

        # Calculate submission rate for each assignment
        for assignment in assignments:
            # Get total students with valid mark
            submitted_students = sum(1 for result in assignment.get("results", []) if result.get("mark") is not None)

            # Calculate submission rate
            submission_rate = (submitted_students / total_students) * 100 if total_students > 0 else 0
            
            assignment["_id"] = str(assignment["_id"])
            assignment["submission_rate"] = round(submission_rate, 2)

        return jsonify({
            "assignments": assignments
        }), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch assignments", "details": str(e)}), 500
    
# Get assignment details for a specific assignment ID
@app.route('/api/classes/<class_id>/assignments/<assignment_id>', methods=['GET'])
@jwt_required()
@teacher_required
def get_assignment(class_id, assignment_id):
    try:
        # Get class info using class_id
        class_info = db.classes.find_one({"_id": class_id})
        if not class_info:
            return jsonify({"message": f"Class {class_id} not found"}), 404

        class_info = convert_object_ids(class_info)

        # Get assignment
        assignment = db.assignments.find_one({"_id": ObjectId(assignment_id), "class_id": class_id})
        if not assignment:
            return jsonify({"message": f"Assignment {assignment_id} not found for class {class_id}"}), 404
        
        assignment = convert_object_ids(assignment)
        assignment["_id"] = str(assignment["_id"])

        # Get student IDs for class
        student_ids = class_info.get("student_ids", [])
        
        # Get student details
        students = db.students.find({"_id": {"$in": [ObjectId(student_id) for student_id in student_ids]}})

        # Dictionary of students
        student_dict = {str(student["_id"]): student for student in students}
        
        # Update results with student names and submission status
        updated_results = []
        for student_id in student_ids:
            student = student_dict.get(str(student_id))  
            if student:
                student_name = f"{student['first_name']} {student['last_name']}"
                # Check student exists in assignment results
                result = next((result for result in assignment.get("results", []) if str(result["student_id"]) == str(student_id)), None)
                if result:
                    updated_results.append({
                        "student_id": str(student_id),
                        "name": student_name,
                        "mark": result["mark"],
                        "score": result["score"],
                        "grade": result["grade"]
                    })
                else:
                    updated_results.append({
                        "student_id": str(student_id),
                        "name": student_name,
                        "mark": None,  # No mark if not submitted
                        "grade": "Not Submitted"
                    })

        # Calculate submission rate
        submitted_students = len([r for r in assignment.get("results", []) if str(r["student_id"]) in student_ids])
        submission_rate = (submitted_students / len(student_ids)) * 100 if len(student_ids) > 0 else 0

        # Format response
        assignment["results"] = updated_results
        assignment["submission_rate"] = round(submission_rate, 2)

        return jsonify(assignment), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch assignment", "details": str(e)}), 500
    
# Update assignment details and student marks
@app.route('/api/classes/<class_id>/assignments/<assignment_id>', methods=['PUT'])
@jwt_required()
@teacher_required
def update_assignment(class_id, assignment_id):
    try:
        data = request.json

        if not data:
            return jsonify({"message": "No data provided"}), 400

        # Get assignment
        assignment = db.assignments.find_one({"_id": ObjectId(assignment_id), "class_id": class_id})
        if not assignment:
            return jsonify({"message": "Assignment not found"}), 404

        # Fields to update 
        updatable_fields = ["title", "topics", "due_date", "total_marks", "A*_grade", "A_grade", "B_grade", "C_grade", "F_grade"]
        updated_fields = {key: data[key] for key in updatable_fields if key in data}

        # Check grade boundaries have changed
        grade_keys = ["A*_grade", "A_grade", "B_grade", "C_grade", "F_grade"]
        grade_boundaries_changed = any(key in data and data[key] != assignment.get(key) for key in grade_keys)

        # Update total marks
        total_marks = data.get("total_marks", assignment.get("total_marks"))

        # Update student results and recalculate grades
        if "results" in data and isinstance(data["results"], list):
            updated_results = []
            total_score_sum = 0
            num_students = 0

            for result in data["results"]:
                student_id = result.get("student_id")
                mark = result.get("mark")

                if mark is not None:
                    student_id = ObjectId(student_id) if isinstance(student_id, str) else student_id
                    
                    # Calculate results
                    score = round((mark / total_marks) * 100, 2)
                    grade = calculate_grade(mark, total_marks, data) if grade_boundaries_changed else result.get("grade", "Not Submitted")
                    result.update({"score": score, "grade": grade})

                    total_score_sum += score
                    num_students += 1

                updated_results.append(result)

            updated_fields["results"] = updated_results

            # Recalculate average score
            updated_fields["average_score"] = round(total_score_sum / num_students, 2) if num_students > 0 else 0

        db.assignments.update_one(
            {"_id": ObjectId(assignment_id), "class_id": class_id},
            {"$set": updated_fields}
        )

        return jsonify({"message": "Assignment updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Unable to update assignment", "details": str(e)}), 500

# Calculate grade based on percentage and updated grade boundaries
def calculate_grade(mark, total_marks, updated_fields):
    # Calculate percentage
    percentage = (mark / total_marks) * 100

    # Get grade boundaries
    A_star_grade = updated_fields.get("A*_grade")
    A_grade = updated_fields.get("A_grade")
    B_grade = updated_fields.get("B_grade")
    C_grade = updated_fields.get("C_grade")
    F_grade = updated_fields.get("F_grade")

    # Get grade
    if A_star_grade is not None and percentage >= A_star_grade:
        return "A*"
    elif A_grade is not None and percentage >= A_grade:
        return "A"
    elif B_grade is not None and percentage >= B_grade:
        return "B"
    elif C_grade is not None and percentage >= C_grade:
        return "C"
    elif F_grade is not None and percentage < F_grade:
        return "F"
    else:
        return "F"  

# Get exams for class
@app.route('/api/classes/<class_id>/exams', methods=['GET'])
@jwt_required()
@teacher_required
def get_class_exams(class_id):
    try:
        # Get class info using class_id
        class_info = db.classes.find_one({"_id": class_id})
        if not class_info:
            return jsonify({"message": f"Class {class_id} not found"}), 404
        
        # Get class subject and year
        class_subject = class_info.get("subject")
        class_year = class_info.get("year")
        student_ids = set(class_info.get("student_ids", []))
        if not class_subject or class_year is None:
            return jsonify({"message": f"Invalid class data for {class_id}"}), 400

        # Get exams for subject and year
        exams = list(db.exams.find({"subject": class_subject, "year": class_year}))

        # Filter exams for class
        relevant_exams = []
        for exam in exams:
            # Filter results for students in class
            class_results = [result for result in exam.get("results", []) if result["student_id"] in [student_id for student_id in student_ids]]
            submitted_students = len(class_results)
            total_students = len(student_ids)

            # Calculate submission rate
            submission_rate = (submitted_students / total_students) * 100 if total_students > 0 else 0

            exam = convert_object_ids(exam)  
            exam["_id"] = str(exam["_id"])  
            exam["submission_rate"] = round(submission_rate, 2)
            exam["results"] = convert_object_ids(class_results)  
            relevant_exams.append(exam)

        if not relevant_exams:
            return jsonify({"message": f"No exams found for class {class_id}"}), 404

        # Sort exams by due_date
        relevant_exams.sort(key=lambda x: x["due_date"], reverse=True)

        return jsonify({"exams": relevant_exams}), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch exams", "details": str(e)}), 500
    
# Get exam details for a specific exam ID with optional year and set filters
@app.route('/api/exams/<exam_id>', methods=['GET'])
@jwt_required()
@teacher_required
def get_exam(exam_id):
    try:
        # Get query parameters
        year = request.args.get('year')
        set_name = request.args.get('set')
        year = int(year) if year else None

        # Get exam
        exam = db.exams.find_one({"_id": ObjectId(exam_id)})
        if not exam:
            return jsonify({"message": f"Exam {exam_id} not found"}), 404

        # Get student IDs for the exam results
        student_ids = [result["student_id"] for result in exam.get("results", [])]
        students = db.students.find({"_id": {"$in": student_ids}})
        student_dict = {str(student["_id"]): student for student in students}  

        # Add student names and target grades to results
        for result in exam.get("results", []):
            student_id = str(result["student_id"])  
            student = student_dict.get(student_id)
            
            # Add student name and target grade
            if student:
                result["name"] = f"{student['first_name']} {student['last_name']}"
                # Get student's target grade for exam's subject
                target_grade = student["target_grades"].get(exam["subject"], "Not Available")
                result["target_grade"] = target_grade
            else:
                result["name"] = "Unknown Student"
                result["target_grade"] = "Not Available"

        # If no filters, return all results
        if not year and not set_name:
            exam["_id"] = str(exam["_id"])
            exam = convert_object_ids(exam)  
            return jsonify(exam), 200

        # Fetch matching classes
        class_filter = {"subject": exam["subject"]}
        if year:
            class_filter["year"] = year
        if set_name:
            class_filter["set"] = set_name.strip()
        matching_classes = list(db.classes.find(class_filter)) 
        if not matching_classes:
            return jsonify({"message": "No classes found matching the specified filters"}), 404

        # Merge student IDs from matching classes
        all_student_ids = set()
        for class_info in matching_classes:
            all_student_ids.update(class_info.get("student_ids", []))

        # Filter exam results for students in matching classes
        updated_results = [
            {
                "student_id": str(result["student_id"]),  
                "name": result["name"],
                "target_grade": result["target_grade"],
                "mark": result.get("mark"),
                "score": result.get("score"),
                "grade": result.get("grade")
            }
            for result in exam.get("results", []) if str(result["student_id"]) in [str(student_id) for student_id in all_student_ids]
        ]

        # Calculate submission rate
        submitted_students = len(updated_results)
        total_students = len(all_student_ids)
        submission_rate = (submitted_students / total_students) * 100 if total_students > 0 else 0

        # Format response
        exam["_id"] = str(exam["_id"])
        exam["results"] = convert_object_ids(updated_results)  
        exam["submission_rate"] = round(submission_rate, 2)

        return jsonify(exam), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch exam details", "details": str(e)}), 500
    
# Get unique years and sets for students who have results in the specified exam
@app.route('/api/exams/<exam_id>/exam-filters', methods=['GET'])
@jwt_required()
@teacher_required
def get_exam_filters(exam_id):
    try:
        # Convert exam_id to ObjectId
        try:
            exam_id = ObjectId(exam_id)
        except bson.errors.InvalidId:
            return jsonify({"error": "Invalid exam ID format"}), 400

        # Get exam
        exam = db.exams.find_one({"_id": exam_id})
        if not exam:
            return jsonify({"message": f"Exam {exam_id} not found"}), 404

        # Get student IDs with exam result
        student_ids = {result["student_id"] for result in exam.get("results", [])}
        if not student_ids:
            return jsonify({"message": "No results found for this exam", "years": [], "sets": []}), 200

        # Get unique years and sets for students
        years = db.students.distinct("year", {"_id": {"$in": list(student_ids)}})
        sets = db.students.distinct("set", {"_id": {"$in": list(student_ids)}})

        return jsonify({"years": years, "sets": sets}), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch exam filters", "details": str(e)}), 500

# Get the most recent exam with grade distribution for a class
@app.route('/api/classes/<class_id>/recent-exam', methods=['GET'])
@jwt_required()
@teacher_required
def get_recent_exam(class_id):
    try:
        # Get class
        class_info = db.classes.find_one({"_id": class_id})
        if not class_info:
            return jsonify({"message": f"Class {class_id} not found"}), 404

        # Get subject and student IDs for class
        class_subject = class_info.get("subject")
        student_ids = set(class_info.get("student_ids", []))
        if not class_subject or not student_ids:
            return jsonify({"message": f"Invalid class data for {class_id}"}), 400

        current_date = datetime.now().strftime("%Y-%m-%d")

        # Get most recent exam for subject
        exams = list(db.exams.find(
            {
                "subject": class_subject,
                "due_date": {"$lt": current_date}  # Only past exams
            },
            sort=[("due_date", -1)]  # Sort by due_date 
        ))

        # Filter exams results for class
        recent_exam = None
        for exam in exams:
            # Filter results for current class' students
            class_results = [result for result in exam.get("results", []) if result["student_id"] in student_ids]
            if class_results:
                recent_exam = exam
                break  # Stop at first matching exam

        if not recent_exam:
            return jsonify({"message": f"No recent exams found for class {class_id}"}), 404

        # Calculate grade distribution 
        grade_distribution = {grade: 0 for grade in ["A*", "A", "B", "C", "F"]}

        for result in recent_exam.get("results", []):
            grade = result.get("grade")
            if grade in grade_distribution:
                grade_distribution[grade] += 1

        recent_exam["_id"] = str(recent_exam["_id"])

        # Format response
        exam_data = {
            "_id": recent_exam["_id"],
            "title": recent_exam["title"],
            "subject": class_subject,
            "due_date": recent_exam["due_date"],
            "total_marks": recent_exam.get("total_marks", 0),
            "average_score": round(recent_exam.get("average_score", 0), 2),
            "grade_distribution": grade_distribution,
            "submission_count": len(recent_exam.get("results", [])),  
            "total_students": len(student_ids)  
        }

        return jsonify({"exam": exam_data}), 200
    except Exception as e:
        return jsonify({"error": "Unable to fetch recent exam", "details": str(e)}), 500
    
# Get student exam scores, class exam averages, year exam averages
@app.route('/api/students/<student_id>/exams-chart', methods=['GET'])
@jwt_required()
@teacher_required
def get_exams_chart(student_id):
    student_object_id = ObjectId(student_id)  

    # Get subject filter
    subject_filter = request.args.get('subject', '').strip()
    # Get student
    student = db.students.find_one({"_id": student_object_id})
    if not student:
        return jsonify({"error": "Student not found"}), 404
    student_year = student.get("year")
    if not student_year:
        return jsonify({"error": "Student year not found"}), 500

    student_scores = []
    year_averages = []
    class_averages = []

    if subject_filter:
        # Get student class for subject
        student_class = db.classes.find_one(
            {"subject": subject_filter, "student_ids": student_object_id},
            {"_id": 1, "student_ids": 1}
        )
        if not student_class:
            return jsonify({"error": f"Student is not enrolled in {subject_filter}"}), 400
        class_student_ids = student_class.get("student_ids", [])

        # Fetch student scores
        student_scores_query = [
            {"$match": {"subject": subject_filter, "year": student_year}},
            {"$unwind": "$results"},
            {"$match": {"results.student_id": student_object_id}},  
            {"$sort": {"due_date": -1}},
            {"$project": {
                "_id": 0,
                "exam_id": {"$toString": "$_id"},
                "title": 1,
                "subject": 1,
                "due_date": 1,
                "mark": "$results.mark",
                "score": "$results.score",
                "grade": "$results.grade"
            }}
        ]
        student_scores = list(db.exams.aggregate(student_scores_query))

        # Get year averages
        year_avg_query = [
            {"$match": {"subject": subject_filter, "year": student_year}},
            {"$sort": {"due_date": -1}},
            {"$project": {
                "exam_id": {"$toString": "$_id"},
                "title": "$title",
                "subject": "$subject",
                "due_date": "$due_date",
                "year_avg": "$average_score"
            }}
        ]
        year_averages = list(db.exams.aggregate(year_avg_query))

        # Get class averages 
        class_avg_query = [
            {"$match": {"subject": subject_filter, "year": student_year}},  # Filter exams by subject, year
            {"$sort": {"due_date": -1}},  # Sort exams
            {"$lookup": {
                "from": "classes",
                "let": {"subject": "$subject", "year": "$year"},
                "pipeline": [
                    {"$match": {
                        "$expr": {
                            "$and": [
                                {"$eq": ["$subject", "$$subject"]},
                                {"$eq": ["$year", "$$year"]},
                                {"$in": [student_object_id, "$student_ids"]} 
                            ]
                        }
                    }},
                    {"$project": {"student_ids": 1, "_id": 0}}  # Keep only student_ids
                ],
                "as": "student_class"
            }},
            {"$unwind": "$student_class"},  # Only one class
            {"$project": {
                "exam_id": {"$toString": "$_id"},  
                "title": 1,
                "subject": 1,
                "due_date": 1,
                "class_avg": {
                    "$let": {
                        "vars": {"valid_results": {
                            "$filter": {
                                "input": "$results",
                                "as": "res",
                                "cond": {
                                    "$and": [
                                        {"$in": ["$$res.student_id", "$student_class.student_ids"]},  # Only class students
                                        {"$ne": ["$$res.score", None]}  # Exclude null scores
                                    ]
                                }
                            }
                        }},
                        "in": {
                            "$cond": {
                                "if": {"$gt": [{"$size": "$$valid_results"}, 0]},
                                "then": {"$round": [{"$avg": "$$valid_results.score"}, 2]},  # Round to 2dp
                                "else": None  # No valid scores, return null
                            }
                        }
                    }
                }
            }}
        ]

        class_averages = list(db.exams.aggregate(class_avg_query))
    else:
        student_scores_query = [
            {"$match": {"year": student_year}},
            {"$unwind": "$results"},
            {"$match": {"results.student_id": student_object_id}},  
            {"$sort": {"due_date": -1}},
            {"$group": {
                "_id": "$subject",
                "exam_id": {"$first": {"$toString": "$_id"}},
                "title": {"$first": "$title"},
                "subject": {"$first": "$subject"},
                "due_date": {"$first": "$due_date"},
                "mark": {"$first": "$results.mark"},
                "score": {"$first": "$results.score"},
                "grade": {"$first": "$results.grade"}
            }}
        ]
        student_scores = list(db.exams.aggregate(student_scores_query))
        today = datetime.now(timezone.utc)
        year_avg_query = [
            {"$addFields": {  # Convert due_date to date
                "parsed_due_date": {"$toDate": "$due_date"}
            }},
            {"$match": {
                "year": student_year,
                "parsed_due_date": {"$lt": today}  # Exams before current date
            }},
            {"$sort": {"parsed_due_date": -1}},  # Sort by most recent date
            {"$group": {
                "_id": "$subject",
                "exam_id": {"$first": {"$toString": "$_id"}},
                "title": {"$first": "$title"},
                "subject": {"$first": "$subject"},
                "due_date": {"$first": "$parsed_due_date"},
                "year_avg": {"$first": {"$ifNull": ["$average_score", 0]}}
            }}
        ]
        year_averages = list(db.exams.aggregate(year_avg_query))

        student_classes = list(db.classes.find({"student_ids": student_object_id}, {"_id": 1, "subject": 1, "student_ids": 1}))
        subject_class_map = {cls["subject"]: [sid for sid in cls["student_ids"]] for cls in student_classes}

        class_avg_query = [
            {"$addFields": {  # Convert due_date to date
                "parsed_due_date": {"$toDate": "$due_date"}
            }},
            {"$match": {"year": student_year,
                "parsed_due_date": {"$lt": today} # Exams before current date
            }},
            {"$sort": {"parsed_due_date": -1}},  # Sort by most recent date
            {"$group": {
                "_id": "$subject",
                "exam_doc": {"$first": "$$ROOT"}
            }}
        ]

        exams_grouped = list(db.exams.aggregate(class_avg_query))
        class_averages = []

        for exam in exams_grouped:
            subj = exam["_id"]
            exam_doc = exam["exam_doc"]
            class_student_ids = subject_class_map.get(subj, [])
            if not class_student_ids:
                continue
            results = [
                res for res in exam_doc.get("results", []) if res.get("student_id") in class_student_ids and res.get("mark") is not None
            ]
            class_avg = round(sum(res["score"] for res in results) / len(results), 2) if results else None
            class_averages.append({
                "exam_id": str(exam_doc["_id"]),
                "title": exam_doc["title"],
                "subject": subj,
                "due_date": exam_doc["parsed_due_date"],  
                "class_avg": class_avg
            })

    response_data = {
        "student_scores": convert_object_ids(student_scores),
        "year_averages": convert_object_ids(year_averages),
        "class_averages": convert_object_ids(class_averages)
    }

    return jsonify(response_data)

@app.route('/api/students/<student_id>/assignments-chart', methods=['GET'])
@jwt_required()
@teacher_required
def get_assignments_chart(student_id):
    student_object_id = ObjectId(student_id)  

    # Get student
    student = db.students.find_one({"_id": student_object_id})
    if not student:
        return jsonify({"error": "Student not found"}), 404
    student_year = student.get("year")
    if not student_year:
        return jsonify({"error": "Student year not found"}), 500

    student_scores = []
    class_averages = []

    # Get student classes
    student_classes = list(db.classes.find({"student_ids": student_object_id}, {"_id": 1, "subject": 1, "student_ids": 1}))
    if not student_classes:
        return jsonify({"error": "No classes found for student"}), 404

    # Get subject filter  
    subject_filter = request.args.get('subject')
    if subject_filter:
        # Get class ids for subject
        filtered_class_ids = [str(cls["_id"]) for cls in student_classes if cls["subject"] == subject_filter]

        # Get student scores for class ids
        student_scores_query = [
            {"$unwind": "$results"},
            {"$match": {"results.student_id": student_object_id, "class_id": {"$in": filtered_class_ids}}}, 

            # Get subject
            {"$lookup": {
                "from": "classes",
                "localField": "class_id",
                "foreignField": "_id",
                "as": "class_details"
            }},            
            {"$unwind": {"path": "$class_details", "preserveNullAndEmptyArrays": True}},
            
            # Project required fields
            {"$project": {
                "_id": 0,
                "assignment_id": {"$toString": "$_id"},
                "title": 1,
                "due_date": 1,
                "mark": "$results.mark",
                "score": "$results.score",
                "student_id": "$results.student_id",
                "class_id": {"$toString": "$class_id"},
                "topics": 1,
                "subject": "$class_details.subject",
                "grade": "$results.grade"
            }}
        ]
    else:
        # Get all class ids for student
        filtered_class_ids = [str(cls["_id"]) for cls in student_classes]

        # Get student scores for most recent assignment for each class
        student_scores_query = [
            {"$unwind": "$results"},
            {"$match": {"results.student_id": student_object_id, "class_id": {"$in": filtered_class_ids}}},
            {"$sort": {"due_date": -1}},  # Sort by due_date
            {"$group": {
                "_id": "$class_id",  # Group by class_id 
                "assignment_id": {"$first": {"$toString": "$_id"}},  # Keep most recent assignment
                "title": {"$first": "$title"},
                "due_date": {"$first": "$due_date"},
                "mark": {"$first": "$results.mark"},  # Get most recent score for each class
                "score": {"$first": "$results.score"},
                "topics": {"$first": "$topics"},
                "subject": {"$first": "$subject"},
                "grade": {"$first": "$results.grade"}
            }},
            {"$lookup": {
                "from": "classes",
                "localField": "_id",
                "foreignField": "_id",
                "as": "class_details"
            }},
            {"$unwind": {"path": "$class_details", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0,
                "class_id": {"$toString": "$_id"},  
                "assignment_id": 1,
                "title": 1,
                "due_date": 1,
                "mark": 1,
                "score": 1,
                "topics": 1,
                "subject": "$class_details.subject",  
                "grade": 1
            }}
        ]

    # Get student's assignment scores
    student_scores = list(db.assignments.aggregate(student_scores_query))

    # Get class averages
    if subject_filter:
        # Get all assignments for filtered classes
        class_avg_query = [
            {"$unwind": "$results"},  # Individual student results
            {"$match": {"class_id": {"$in": filtered_class_ids}}},  # Match filtered class ids
            {"$group": {
                "_id": {"class_id": "$class_id", "assignment_id": "$_id"},  # Group by class_id and assignment_id
                "class_avg": {"$avg": "$results.score"},  # Calculate class average score
                "title": {"$first": "$title"},  
                "due_date": {"$first": "$due_date"}  
            }},
            {"$lookup": {
                "from": "classes",
                "localField": "_id.class_id",
                "foreignField": "_id",
                "as": "class_details"
            }},
            {"$unwind": {"path": "$class_details", "preserveNullAndEmptyArrays": True}},  
            {"$project": {
                "_id": 0,  
                "class_id": {"$toString": "$_id.class_id"},  
                "assignment_id": {"$toString": "$_id.assignment_id"},  
                "class_avg": {"$round": ["$class_avg", 2]}, 
                "title": 1,  
                "due_date": 1,  
                "subject": "$class_details.subject" 
            }}
        ]
    else:
        # Group by class_id, get most recent assignment average
        class_avg_query = [
            {"$unwind": "$results"},  # Unwind for individual student results
            {"$match": {"results.student_id": student_object_id, "class_id": {"$in": filtered_class_ids}}},  # Match class ids for student
            {"$match": {"results.mark": {"$ne": None}}},  # Filter out null mark values
            {"$sort": {"due_date": -1}},  # Sort by due_date
            {"$group": {
                "_id": "$class_id",  # Group by class_id
                "assignment_id": {"$first": {"$toString": "$_id"}},
                "class_avg": {"$avg": "$results.score"},  
                "title": {"$first": "$title"},  
                "due_date": {"$first": "$due_date"},  
                "subject": {"$first": "$subject"}  
            }},
            {"$lookup": {
                "from": "classes",
                "localField": "_id",
                "foreignField": "_id",
                "as": "class_details"
            }},
            {"$unwind": {"path": "$class_details", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0,
                "class_id": {"$toString": "$_id"},  
                "assignment_id": 1,
                "class_avg": {"$round": ["$class_avg", 2]},
                "title": 1,
                "due_date": 1,
                "subject": "$class_details.subject"
            }}
        ]
    class_averages = list(db.assignments.aggregate(class_avg_query))

    # Format response
    response_data = {
        "student_scores": convert_object_ids(student_scores),
        "class_averages": convert_object_ids(class_averages)
    }

    return jsonify(response_data)

# Update exam details and student marks
@app.route('/api/exams/<exam_id>', methods=['PUT'])
@jwt_required()
@teacher_required
def update_exam_details(exam_id):
    try:
        data = request.json
        if not data:
            return jsonify({"message": "No data provided"}), 400

        # Get exam
        exam = db.exams.find_one({"_id": ObjectId(exam_id)})
        if not exam:
            return jsonify({"message": "Exam not found"}), 404

        # Exam fields
        updatable_fields = ["title", "year", "subject", "due_date", "total_marks", "A*_grade", "A_grade", "B_grade", "C_grade", "F_grade"]
        updated_fields = {key: data[key] for key in updatable_fields if key in data}

        # Check if grade boundaries have changed
        grade_keys = ["A*_grade", "A_grade", "B_grade", "C_grade", "F_grade"]
        grade_boundaries_changed = any(key in data and data[key] != exam.get(key) for key in grade_keys)

        # Update total marks
        total_marks = data.get("total_marks", exam.get("total_marks"))

        # Update student results
        if "results" in data and isinstance(data["results"], list):
            updated_results = []
            total_score_sum = 0
            num_students = 0

            for result in data["results"]:
                student_id = result.get("student_id")
                mark = result.get("mark")

                if mark is not None:
                    student_id = ObjectId(student_id) if isinstance(student_id, str) else student_id
                    
                    # Calculate results
                    score = round((mark / total_marks) * 100, 2)
                    grade = calculate_grade(mark, total_marks, data) if grade_boundaries_changed else result.get("grade", "Not Submitted")
                    result.update({"score": score, "grade": grade})
                    total_score_sum += score
                    num_students += 1
                    db.exams.update_one(
                        {"_id": ObjectId(exam_id), "results.student_id": student_id},
                        {"$set": {"results.$.mark": mark, "results.$.score": score, "results.$.grade": grade}},
                        upsert=True
                    )
                updated_results.append(result)
            updated_fields["results"] = updated_results

            # Calculate average score
            updated_fields["average_score"] = round(total_score_sum / num_students, 2) if num_students > 0 else 0

        # If grade boundaries changed, recalculate grades
        if grade_boundaries_changed:
            all_results = exam.get('results', [])
            for result in all_results:
                student_id = result.get("student_id")
                mark = result.get("mark")
                if mark is not None:
                    grade = calculate_grade(mark, total_marks, data)
                    db.exams.update_one(
                        {"_id": ObjectId(exam_id), "results.student_id": student_id},
                        {"$set": {"results.$.grade": grade}}
                    )

        db.exams.update_one(
            {"_id": ObjectId(exam_id)},
            {"$set": updated_fields}
        )

        return jsonify({"message": "Exam updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Unable to update exam", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))