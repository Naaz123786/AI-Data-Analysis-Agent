from flask import Flask, render_template, request, session
from utils import preprocess_and_save
import pandas as pd
from groq import Groq
import os
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.environ.get("SECRET_KEY", "dev-only-secret"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_groq_key(form_key: str | None) -> str | None:
    if form_key and form_key.strip():
        session["groq_api_key"] = form_key.strip()
        return session["groq_api_key"]
    if session.get("groq_api_key"):
        return session["groq_api_key"]
    return os.environ.get("GROQ_API_KEY")


def _save_upload(file) -> str:
    filename = (file.filename or "").lower()
    ext = ".csv" if filename.endswith(".csv") else ".xlsx"
    path = os.path.join(UPLOAD_DIR, f"{uuid4().hex}{ext}")
    file.save(path)
    session["last_upload_path"] = path
    return path

@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    df = None
    df_html = ""
    df_preview_html = ""
    result_html = ""
    code_generated = ""
    query = ""
    has_cached_upload = bool(session.get("last_upload_path"))

    if request.method == "POST":
        file = request.files.get("file")
        query = request.form.get("query") or ""
        groq_key = _get_groq_key(request.form.get("api_key"))

        if not groq_key:
            message = "Please enter your Groq API key (or set GROQ_API_KEY in environment)."
        else:
            # If user didn't re-upload, reuse the last uploaded file for this session.
            upload_path = None
            if file and getattr(file, "filename", ""):
                upload_path = _save_upload(file)
            elif session.get("last_upload_path"):
                upload_path = session.get("last_upload_path")

            if not upload_path:
                message = "Please upload a file."
            else:
                # Re-open file for processing using the existing helper.
                try:
                    with open(upload_path, "rb") as f:
                        df, cols, df_html, err = preprocess_and_save(f)
                except Exception as e:
                    df, cols, df_html, err = None, None, None, str(e)

            if err:
                message = err
            else:
                # Show first 5 rows preview
                df_preview_html = df.head().to_html(classes="table-auto w-full") if df is not None else ""

                if query:
                    try:
                        prompt = f"""
You are a Python data analyst. Given a pandas DataFrame named `df`, write Python code using pandas to answer this question:

Question: {query}

Only return the Python code (no explanation). Use 'result' as the final output variable.
"""

                        client = Groq(api_key=groq_key)
                        chat_completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile"
                        )

                        code_generated = chat_completion.choices[0].message.content.strip("`python").strip("`")

                        local_vars = {"df": df}
                        exec(code_generated, {}, local_vars)

                        result = local_vars.get("result", "No result generated.")
                        if isinstance(result, pd.DataFrame):
                            result_html = result.to_html(classes="table-auto w-full")
                        else:
                            result_html = str(result)

                    except Exception as e:
                        # Keep the preview visible even if the model call fails.
                        message = f"Error running Groq code: {e}"

    return render_template(
        "index.html",
        message=message,
        df_html=df_html,
        df_preview_html=df_preview_html,
        code_generated=code_generated,
        result_html=result_html,
        query=query,
        has_cached_upload=has_cached_upload,
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    # In production, run via gunicorn and keep debug off.
    app.run(host="0.0.0.0", port=port, debug=False)
