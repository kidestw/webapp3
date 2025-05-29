import os
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text.models import InputTextItem
from azure.storage.blob import BlobServiceClient
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # for flashing messages

# Initialize Azure Translator client
translator = TextTranslationClient(
    endpoint=os.getenv("AZURE_TRANSLATOR_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("AZURE_TRANSLATOR_KEY"))
)

# Initialize Azure Blob Storage client
blob_service = BlobServiceClient(
    account_url=f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net",
    credential=os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
)

# Languages dictionary (add more if you want)
languages = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh-Hans": "Chinese Simplified",
    "zh-Hant": "Chinese Traditional"
}

@app.route("/", methods=["GET", "POST"])
def index():
    original_text = ""
    translated_text = ""
    selected_lang = "en"
    translated_filename = ""

    if request.method == "POST":
        selected_lang = request.form.get("language")
        uploaded_file = request.files.get("file")
        input_text = request.form.get("input_text", "")

        if uploaded_file and uploaded_file.filename != "":
            try:
                input_text = uploaded_file.read().decode("utf-8")
            except Exception:
                flash("Error reading uploaded file. Please upload a valid UTF-8 .txt file.", "error")
                return redirect(url_for("index"))

        original_text = input_text.strip()

        if not original_text:
            flash("Please enter text or upload a file to translate.", "error")
            return redirect(url_for("index"))

        try:
            # Translate the text
            result = translator.translate(
                body=[InputTextItem(text=original_text)],
                to_language=[selected_lang]
            )
            translated_text = result[0].translations[0].text
            translated_filename = f"translated_{selected_lang}.txt"

            # Upload original text to Azure Blob Storage container "input-requests"
            input_blob_name = f"original-{uploaded_file.filename if uploaded_file else 'input_text.txt'}"
            input_blob_client = blob_service.get_blob_client(container="input-requests", blob=input_blob_name)
            input_blob_client.upload_blob(original_text, overwrite=True)

            # Upload translated text to Azure Blob Storage container "output-results"
            output_blob_name = f"translated-{uploaded_file.filename if uploaded_file else 'input_text.txt'}"
            output_blob_client = blob_service.get_blob_client(container="output-results", blob=output_blob_name)
            output_blob_client.upload_blob(translated_text, overwrite=True)

        except Exception as e:
            flash("Translation error. Please check your Azure credentials and try again.", "error")
            print(f"Translation error: {e}")

    return render_template(
        "index.html",
        languages=languages,
        selected_lang=selected_lang,
        original_text=original_text,
        translated_text=translated_text,
        translated_filename=translated_filename
    )


@app.route("/download/<filename>")
def download_file(filename):
    text = request.args.get("text", "")
    if not text:
        flash("No translated text available for download.", "error")
        return redirect(url_for("index"))

    # Prepare the file in-memory
    file_io = BytesIO()
    file_io.write(text.encode("utf-8"))
    file_io.seek(0)

    return send_file(
        file_io,
        as_attachment=True,
        download_name=filename,
        mimetype="text/plain"
    )


if __name__ == "__main__":
    app.run(debug=True)
