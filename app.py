import os
from datetime import datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

# Use Render environment variable if available
app.secret_key = os.getenv(
    "SECRET_KEY",
    "online-exam-secret-key"
)


# =========================================================
# MONGODB ATLAS CONNECTION
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is not set.")

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000
)

# Database name
db = client["online_exam"]


# =========================================================
# COLLECTIONS
# =========================================================

users = db["users"]
exams = db["exams"]
questions = db["questions"]
results = db["results"]
answers = db["answers"]
counters = db["counters"]


# =========================================================
# MONGODB INDEXES
# =========================================================

def create_indexes():
    """
    Create useful indexes in MongoDB.
    """

    # Email must be unique
    users.create_index(
        "email",
        unique=True
    )

    # IDs should also be unique
    exams.create_index(
        "id",
        unique=True
    )

    questions.create_index(
        "id",
        unique=True
    )

    results.create_index(
        "id",
        unique=True
    )

    answers.create_index(
        "id",
        unique=True
    )


# =========================================================
# ID COUNTER
# =========================================================

def initialize_counter(name, collection):
    """
    Create a counter for a collection if it doesn't already exist.
    """

    existing_counter = counters.find_one({
        "_id": name
    })

    if existing_counter is None:

        last_document = collection.find_one(
            sort=[("id", -1)]
        )

        last_id = 0

        if last_document:
            last_id = last_document.get("id", 0)

        counters.insert_one({
            "_id": name,
            "seq": last_id
        })


def initialize_counters():

    initialize_counter("users", users)
    initialize_counter("exams", exams)
    initialize_counter("questions", questions)
    initialize_counter("results", results)
    initialize_counter("answers", answers)


def get_next_id(name):
    """
    Generate the next integer ID.

    We are using integer IDs instead of MongoDB ObjectIds
    so that the existing Flask routes such as:

        /exam/<int:exam_id>

    continue to work.
    """

    counter = counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    return counter["seq"]


# =========================================================
# CREATE DEFAULT ADMIN
# =========================================================

def create_admin():

    admin_email = "admin@example.com"

    existing_admin = users.find_one({
        "email": admin_email
    })

    if existing_admin is None:

        users.insert_one({
            "id": get_next_id("users"),
            "name": "Administrator",
            "email": admin_email,
            "password": "admin123",
            "role": "admin"
        })

        print("Default admin created.")

    else:

        # Make sure this account remains an admin
        users.update_one(
            {"email": admin_email},
            {
                "$set": {
                    "role": "admin"
                }
            }
        )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# STUDENT REGISTRATION
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("fullname")
        email = request.form.get("email")
        rollno = request.form.get("rollno")
        password = request.form.get("password")

        # Check whether email already exists
        existing_user = users.find_one({
            "email": email
        })

        if existing_user:

            return render_template(
                "register.html",
                error="Email already registered."
            )

        try:

            users.insert_one({
                "id": get_next_id("users"),
                "name": name,
                "email": email,
                "rollno": rollno,
                "password": password,
                "role": "student"
            })

            return redirect(
                url_for("login")
            )

        except DuplicateKeyError:

            return render_template(
                "register.html",
                error="Email already registered."
            )

    return render_template(
        "register.html"
    )


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = users.find_one({
            "email": email,
            "password": password
        })

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["role"] = user.get("role", "student")

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template(
        "login.html"
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # Get all exams
    all_exams = list(
        exams.find().sort("id", 1)
    )

    # Get completed exams for current user
    completed_count = results.count_documents({
        "user_id": session["user_id"]
    })

    return render_template(
        "dashboard.html",
        exams=all_exams,
        completed_count=completed_count
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        admin = users.find_one({
            "email": email,
            "password": password,
            "role": "admin"
        })

        if admin:

            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            session["admin_email"] = admin["email"]
            session["role"] = "admin"

            return redirect(
                url_for("admin_dashboard")
            )

        return render_template(
            "admin_login.html",
            error="Invalid admin email or password."
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if session.get("role") != "admin":

        return redirect(
            url_for("admin_login")
        )

    total_users = users.count_documents({
        "role": "student"
    })

    total_exams = exams.count_documents({})

    total_questions = questions.count_documents({})

    total_results = results.count_documents({})

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_exams=total_exams,
        total_questions=total_questions,
        total_results=total_results
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# ADMIN - CREATE EXAM
# =========================================================

@app.route("/admin/exams", methods=["GET", "POST"])
def admin_exams():

    if session.get("role") != "admin":

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        title = request.form.get("title")
        subject = request.form.get("subject")

        try:

            duration = int(
                request.form.get("duration", 0)
            )

            total_questions = int(
                request.form.get(
                    "total_questions",
                    0
                )
            )

        except ValueError:

            return render_template(
                "admin_exams.html",
                exams=list(
                    exams.find().sort("id", 1)
                ),
                error="Please enter valid numbers."
            )

        exams.insert_one({
            "id": get_next_id("exams"),
            "title": title,
            "subject": subject,
            "duration": duration,
            "total_questions": total_questions
        })

        return redirect(
            url_for("admin_exams")
        )

    all_exams = list(
        exams.find().sort("id", 1)
    )

    return render_template(
        "admin_exams.html",
        exams=all_exams
    )


# =========================================================
# ADMIN - ADD QUESTIONS
# =========================================================

@app.route("/admin/questions", methods=["GET", "POST"])
def admin_questions():

    if session.get("role") != "admin":

        return redirect(
            url_for("admin_login")
        )

    all_exams = list(
        exams.find().sort("id", 1)
    )

    if request.method == "POST":

        try:

            exam_id = int(
                request.form.get("exam_id")
            )

        except (ValueError, TypeError):

            return render_template(
                "admin_questions.html",
                exams=all_exams,
                error="Invalid exam selected."
            )

        question_text = request.form.get(
            "question"
        )

        option_a = request.form.get(
            "option_a"
        )

        option_b = request.form.get(
            "option_b"
        )

        option_c = request.form.get(
            "option_c"
        )

        option_d = request.form.get(
            "option_d"
        )

        correct_answer = request.form.get(
            "correct_answer"
        )

        # Check exam exists
        selected_exam = exams.find_one({
            "id": exam_id
        })

        if selected_exam is None:

            return render_template(
                "admin_questions.html",
                exams=all_exams,
                error="Exam not found."
            )

        questions.insert_one({
            "id": get_next_id("questions"),
            "exam_id": exam_id,
            "question": question_text,
            "option_a": option_a,
            "option_b": option_b,
            "option_c": option_c,
            "option_d": option_d,
            "correct_answer": correct_answer
        })

        return redirect(
            url_for("admin_questions")
        )

    return render_template(
        "admin_questions.html",
        exams=all_exams
    )


# =========================================================
# EXAM INSTRUCTIONS
# =========================================================

@app.route("/instructions/<int:exam_id>")
def instructions(exam_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    exam = exams.find_one({
        "id": exam_id
    })

    if exam is None:

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "instructions.html",
        exam=exam
    )


# =========================================================
# START EXAM
# =========================================================

@app.route("/exam/<int:exam_id>")
def exam(exam_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    exam_data = exams.find_one({
        "id": exam_id
    })

    if exam_data is None:

        return redirect(
            url_for("dashboard")
        )

    exam_questions = list(
        questions.find({
            "exam_id": exam_id
        }).sort("id", 1)
    )

    return render_template(
        "exam.html",
        exam=exam_data,
        questions=exam_questions
    )


# =========================================================
# SUBMIT EXAM
# =========================================================

@app.route(
    "/submit-exam/<int:exam_id>",
    methods=["POST"]
)
def submit_exam(exam_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    exam_data = exams.find_one({
        "id": exam_id
    })

    if exam_data is None:

        return redirect(
            url_for("dashboard")
        )

    exam_questions = list(
        questions.find({
            "exam_id": exam_id
        }).sort("id", 1)
    )

    score = 0

    # =====================================================
    # CHECK ANSWERS
    # =====================================================

    for question in exam_questions:

        question_id = question["id"]

        selected_answer = request.form.get(
            f"question_{question_id}"
        )

        correct_answer = question[
            "correct_answer"
        ]

        if selected_answer == correct_answer:

            score += 1

    # =====================================================
    # TOTAL QUESTIONS
    # =====================================================

    total_questions = len(
        exam_questions
    )

    # Avoid division by zero
    if total_questions > 0:

        percentage = (
            score / total_questions
        ) * 100

    else:

        percentage = 0

    # =====================================================
    # CREATE RESULT
    # =====================================================

    result_id = get_next_id(
        "results"
    )

    results.insert_one({
        "id": result_id,
        "user_id": session["user_id"],
        "exam_id": exam_id,
        "score": score,
        "total_questions": total_questions,
        "percentage": round(
            percentage,
            2
        ),
        "date": datetime.now(
            timezone.utc
        )
    })

    # =====================================================
    # SAVE EACH ANSWER
    # =====================================================

    for question in exam_questions:

        question_id = question["id"]

        selected_answer = request.form.get(
            f"question_{question_id}"
        )

        answers.insert_one({
            "id": get_next_id("answers"),
            "result_id": result_id,
            "question_id": question_id,
            "selected_answer": selected_answer
        })

    # =====================================================
    # SHOW RESULT
    # =====================================================

    return redirect(
        url_for(
            "result",
            result_id=result_id
        )
    )


# =========================================================
# EXAM HISTORY
# =========================================================

@app.route("/history")
def history():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_results = list(
        results.find({
            "user_id": session["user_id"]
        }).sort("date", -1)
    )

    # Add exam information to every result
    for result in user_results:

        exam_data = exams.find_one({
            "id": result["exam_id"]
        })

        if exam_data:

            result["exam_title"] = exam_data.get(
                "title",
                "Unknown Exam"
            )

            result["subject"] = exam_data.get(
                "subject",
                ""
            )

        else:

            result["exam_title"] = "Unknown Exam"
            result["subject"] = ""

    return render_template(
        "history.html",
        results=user_results
    )


# =========================================================
# RESULT PAGE
# =========================================================

@app.route("/result/<int:result_id>")
def result(result_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    result_data = results.find_one({
        "id": result_id
    })

    if result_data is None:

        return redirect(
            url_for("dashboard")
        )

    # Security:
    # Student can only see their own result
    if result_data["user_id"] != session["user_id"]:

        return redirect(
            url_for("dashboard")
        )

    exam_data = exams.find_one({
        "id": result_data["exam_id"]
    })

    return render_template(
        "result.html",
        result=result_data,
        exam=exam_data
    )


# =========================================================
# INITIALIZE MONGODB
# =========================================================

create_indexes()
initialize_counters()
create_admin()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
