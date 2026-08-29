from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "online-exam-secret-key"

DATABASE = "online_exam.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db_connection()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student'
        )
    """)

    # Exams table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            duration INTEGER NOT NULL,
            total_questions INTEGER NOT NULL
        )
    """)

    # Questions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        )
    """)

    # Results table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            percentage REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        )
    """)

    # Answers table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_answer TEXT,
            FOREIGN KEY (result_id) REFERENCES results(id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    message = ""

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()

        try:
            conn.execute(
                """
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, password, "student")
            )

            conn.commit()
            message = "Registration successful!"

        except sqlite3.IntegrityError:
            message = "Email already registered."

        conn.close()

    return render_template("register.html", message=message)    

@app.route("/login", methods=["GET", "POST"])
def login():

    message = ""

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()

        user = conn.execute(
            """
            SELECT * FROM users
            WHERE email = ? AND password = ?
            """,
            (email, password)
        ).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]

            return redirect(url_for("dashboard"))

        else:
            message = "Invalid email or password."

    return render_template("login.html", message=message)

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    exams = conn.execute(
        "SELECT * FROM exams"
    ).fetchall()

    completed = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM results
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    conn.close()

    total_exams = len(exams)
    completed_exams = completed["count"]

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        exams=exams,
        total_exams=total_exams,
        completed_exams=completed_exams
    )    

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


def create_admin():
    conn = get_db_connection()

    admin = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        ("admin@example.com",)
    ).fetchone()

    if admin:
        # Make sure this account is an admin
        conn.execute(
            """
            UPDATE users
            SET name = ?, password = ?, role = ?
            WHERE email = ?
            """,
            (
                "Administrator",
                "admin123",
                "admin",
                "admin@example.com"
            )
        )
    else:
        # Create admin account
        conn.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Administrator",
                "admin@example.com",
                "admin123",
                "admin"
            )
        )

    conn.commit()
    conn.close()
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    message = ""

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()

        admin = conn.execute(
            """
            SELECT * FROM users
            WHERE email = ? AND password = ? AND role = 'admin'
            """,
            (email, password)
        ).fetchone()

        conn.close()

        if admin:

            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]

            return redirect(url_for("admin_dashboard"))

        else:
            message = "Invalid admin email or password."

    return render_template(
        "admin_login.html",
        message=message
    )

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    total_exams = conn.execute(
        "SELECT COUNT(*) AS count FROM exams"
    ).fetchone()["count"]

    total_questions = conn.execute(
        "SELECT COUNT(*) AS count FROM questions"
    ).fetchone()["count"]

    total_students = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        WHERE role = 'student'
        """
    ).fetchone()["count"]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        admin_name=session["admin_name"],
        total_exams=total_exams,
        total_questions=total_questions,
        total_students=total_students
    )

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_id", None)
    session.pop("admin_name", None)

    return redirect(url_for("admin_login"))

@app.route("/admin/exams", methods=["GET", "POST"])
def manage_exams():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    message = ""

    conn = get_db_connection()

    if request.method == "POST":

        title = request.form["title"]
        subject = request.form["subject"]
        duration = request.form["duration"]
        total_questions = request.form["total_questions"]

        conn.execute(
            """
            INSERT INTO exams
            (title, subject, duration, total_questions)
            VALUES (?, ?, ?, ?)
            """,
            (
                title,
                subject,
                duration,
                total_questions
            )
        )

        conn.commit()

        message = "Examination created successfully!"

    exams = conn.execute(
        "SELECT * FROM exams ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "manage_exams.html",
        exams=exams,
        message=message
    )

@app.route("/admin/questions", methods=["GET", "POST"])
def manage_questions():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    message = ""

    conn = get_db_connection()

    if request.method == "POST":

        exam_id = request.form["exam_id"]
        question = request.form["question"]
        option_a = request.form["option_a"]
        option_b = request.form["option_b"]
        option_c = request.form["option_c"]
        option_d = request.form["option_d"]
        correct_answer = request.form["correct_answer"]

        conn.execute(
            """
            INSERT INTO questions
            (
                exam_id,
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_id,
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer
            )
        )

        conn.commit()

        message = "Question added successfully!"

    exams = conn.execute(
        "SELECT * FROM exams ORDER BY id DESC"
    ).fetchall()

    questions = conn.execute(
        """
        SELECT questions.*, exams.title
        FROM questions
        JOIN exams
        ON questions.exam_id = exams.id
        ORDER BY questions.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "manage_questions.html",
        exams=exams,
        questions=questions,
        message=message
    )

@app.route("/instructions/<int:exam_id>")
def instructions(exam_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    exam = conn.execute(
        "SELECT * FROM exams WHERE id = ?",
        (exam_id,)
    ).fetchone()

    conn.close()

    if not exam:
        return "Examination not found", 404

    return render_template(
        "instructions.html",
        exam=exam
    )

@app.route("/exam/<int:exam_id>")
def exam(exam_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    exam = conn.execute(
        """
        SELECT *
        FROM exams
        WHERE id = ?
        """,
        (exam_id,)
    ).fetchone()

    if not exam:
        conn.close()
        return "Examination not found", 404

    questions = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE exam_id = ?
        ORDER BY id
        """,
        (exam_id,)
    ).fetchall()

    conn.close()

    if not questions:
        return "No questions available for this examination.", 400

    return render_template(
        "exam.html",
        exam=exam,
        questions=questions
    )

@app.route("/submit-exam/<int:exam_id>", methods=["POST"])
def submit_exam(exam_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    exam = conn.execute(
        "SELECT * FROM exams WHERE id = ?",
        (exam_id,)
    ).fetchone()

    if not exam:
        conn.close()
        return "Examination not found", 404

    questions = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE exam_id = ?
        ORDER BY id
        """,
        (exam_id,)
    ).fetchall()

    score = 0

    for question in questions:

        selected_answer = request.form.get(
            f"question_{question['id']}"
        )

        if selected_answer == question["correct_answer"]:
            score += 1

    total_questions = len(questions)

    if total_questions > 0:
        percentage = (score / total_questions) * 100
    else:
        percentage = 0

    cursor = conn.execute(
        """
        INSERT INTO results
        (user_id, exam_id, score, total_questions, percentage)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            exam_id,
            score,
            total_questions,
            percentage
        )
    )

    result_id = cursor.lastrowid

    conn.commit()

    for question in questions:

        selected_answer = request.form.get(
            f"question_{question['id']}"
        )

        conn.execute(
            """
            INSERT INTO answers
            (result_id, question_id, selected_answer)
            VALUES (?, ?, ?)
            """,
            (
                result_id,
                question["id"],
                selected_answer
            )
        )

    conn.commit()
    conn.close()

    return redirect(
        url_for("result", result_id=result_id)
    )

@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    results = conn.execute(
        """
        SELECT results.*, exams.title, exams.subject
        FROM results
        JOIN exams ON results.exam_id = exams.id
        WHERE results.user_id = ?
        ORDER BY results.date DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "history.html",
        results=results
    )

@app.route("/result/<int:result_id>")
def result(result_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    result = conn.execute(
        """
        SELECT *
        FROM results
        WHERE id = ?
        AND user_id = ?
        """,
        (result_id, session["user_id"])
    ).fetchone()

    if not result:
        conn.close()
        return "Result not found", 404

    exam = conn.execute(
        """
        SELECT *
        FROM exams
        WHERE id = ?
        """,
        (result["exam_id"],)
    ).fetchone()

    conn.close()

    return render_template(
        "result.html",
        result=result,
        exam=exam,
        user_name=session["user_name"]
    )
     
if __name__ == "__main__":
    create_tables()
    create_admin()
    app.run(debug=True)