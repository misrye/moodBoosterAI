from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import google.generativeai as genai
import subprocess
import re
import urllib.parse
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "rahasia"

# Folder upload untuk gambar dari browser
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Konfigurasi Gemini
genai.configure(api_key="AIzaSyBv-nA5plt5RElcYw6uKYYs7Ko1eHPn0Ok")
model = genai.GenerativeModel("gemini-1.5-pro")

SYSTEM_PROMPT = (
    "Kamu adalah chatbot mood booster. "
    "Tugasmu hanya menjawab pertanyaan seputar memperbaiki mood. "
    "Jika pengguna menanyakan hal di luar topik tersebut, tolak dengan sopan dan arahkan kembali ke topik memperbaiki mood.\n\n"
)

# Variabel global
chat_sessions = []
current_session = []

# Menyimpan sesi global
chat_sessions = {}

@app.route("/")
def landing_page():
    return render_template("index.html")

@app.route("/moodDetection")
def mood_detection_page():
    return render_template("moodDetection.html")

@app.route("/detect", methods=["POST"])
def detect_mood():
    try:
        image = request.files['image']
        filename = f"capture_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        image.save(filepath)

        result = subprocess.run(["python", "detector.py", filepath],
                                capture_output=True, text=True, encoding="utf-8")
        mood = result.stdout.strip()

        if "bukan wajah" in mood.lower() or "gagal" in mood.lower():
            return jsonify({"mood": mood})

        return jsonify({
            "redirect": url_for("result_page", mood=mood, img=os.path.basename(filepath))
        })
    except Exception:
        return jsonify({"mood": "Gagal mendeteksi mood."})

@app.route("/result", methods=["GET"])
def result_page():
    mood = request.args.get("mood", "").strip()
    img = request.args.get("img", "")
    recommendations = []
    raw_text = ""

    is_invalid_mood = (
        not mood or
        "gagal" in mood.lower() or
        "tidak bisa" in mood.lower() or
        "bukan wajah" in mood.lower()
    )

    if not is_invalid_mood:
        try:
            prompt = (
                f"Saya sedang merasa {mood}. "
                f"Berikan 3 lagu yang cocok dengan mood ini dan jelaskan alasannya secara singkat. "
                f"Tulis jawabannya dengan format:\n"
                f"1. *Judul oleh Artis* - alasan\n"
                f"2. *Judul oleh Artis* - alasan\n"
                f"3. *Judul oleh Artis* - alasan"
            )

            response = model.generate_content(prompt)
            raw_text = response.text.strip()

            matches = re.findall(r"\*([^*]+)\*", raw_text)

            for match in matches:
                parts = match.split(" oleh ")
                if len(parts) == 2:
                    title, artist = parts
                else:
                    title = match
                    artist = "Tidak diketahui"

                query = f"{title} {artist}"
                encoded_query = urllib.parse.quote(query)
                spotify_link = f"https://open.spotify.com/search/{encoded_query}"

                pattern = rf"\*\s*{re.escape(match)}\s*\*\s*-\s*(.+?)(?=\n|$)"
                alasan_match = re.search(pattern, raw_text)
                reason = alasan_match.group(1).strip() if alasan_match else ""

                recommendations.append({
                    "title": title.strip(),
                    "artist": artist.strip(),
                    "spotify_link": spotify_link,
                    "reason": reason
                })

        except Exception:
            raw_text = "Gagal mendapatkan rekomendasi lagu dari AI."

    # 🔥 Mood mapping & emoticon logic
    mood_mapping = {
        "happy": "senang",
        "sad": "sedih",
        "angry": "marah",
        "fear": "takut",
        "surprise": "terkejut",
        "neutral": "netral",
        "disgust": "muak"
    }

    mood_emoticons = {
        "senang": "😄",
        "sedih": "😢",
        "marah": "😠",
        "takut": "😨",
        "terkejut": "😲",
        "netral": "😐",
        "muak": "😒",
        "bahagia": "😊"
    }

    mood_id = mood.lower()
    translated_mood = mood_mapping.get(mood_id, mood_id)
    emot = mood_emoticons.get(translated_mood, "🙂")

    return render_template(
        "result.html",
        mood=translated_mood,
        img=img,
        ai_rekomendasi=raw_text,
        recommendations=recommendations,
        emot=emot
    )

@app.route("/chatFromMood")
def chat_from_mood():
    mood = request.args.get("mood", "").lower()
    if not mood:
        return redirect(url_for("chatbot"))

    prompt = (
        f"Saya sedang merasa {mood}. "
        f"Rekomendasikan lagu yang cocok dengan mood tersebut dan jelaskan kenapa lagu itu cocok."
    )

    try:
        response = model.generate_content(prompt)
        bot_answer = response.text.strip()

        current_session.append({"role": "user", "message": prompt})
        current_session.append({"role": "bot", "message": bot_answer})

        return render_template("chatbot.html",
                               chat_history=current_session,
                               chat_sessions=chat_sessions,
                               active_session=None,
                               error_message="")
    except Exception:
        return render_template("chatbot.html",
                               chat_history=current_session,
                               chat_sessions=chat_sessions,
                               active_session=None,
                               error_message="Gagal mendapatkan respon dari AI.")

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if "active_session" not in session:
        session["active_session"] = str(uuid.uuid4())

    session_id = session["active_session"]

    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    # ✅ Simulasi tahap pertama: render "typing..." sebelum kirim ke AI
    if request.method == "POST":
        user_input = request.form["message"]
        chat_sessions[session_id].append({"role": "user", "content": user_input})

        # Mulai obrolan dengan AI dan ambil jawaban langsung
        chat = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]}
        ] + [
            {"role": msg["role"], "parts": [msg["content"]]} for msg in chat_sessions[session_id]
        ])
        response = chat.send_message(user_input).text
        chat_sessions[session_id].append({"role": "model", "content": response})

        # Render langsung hasilnya TANPA redirect dan tanpa render typing
        all_sessions = [
            {
                "id": sid,
                "title": sess[0]["content"][:30] + "..." if sess else "Obrolan Baru"
            }
            for sid, sess in chat_sessions.items()
        ]

        return render_template("chatbot.html",
                            chat_history=chat_sessions[session_id],
                            chat_sessions=all_sessions,
                            active_session=session_id,
                            typing=False)


    # ✅ Tahap kedua: lanjutkan proses kalau sudah ada user input terakhir
    if chat_sessions[session_id] and chat_sessions[session_id][-1]["role"] == "user" and \
       (len(chat_sessions[session_id]) < 2 or chat_sessions[session_id][-2]["role"] != "model"):

        chat = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]}
        ] + [
            {"role": msg["role"], "parts": [msg["content"]]} for msg in chat_sessions[session_id]
        ])
        response = chat.send_message(chat_sessions[session_id][-1]["content"]).text
        chat_sessions[session_id].append({"role": "model", "content": response})

    # ✅ Render final setelah jawaban AI
    all_sessions = [
        {
            "id": sid,
            "title": sess[0]["content"][:30] + "..." if sess else "Obrolan Baru"
        }
        for sid, sess in chat_sessions.items()
    ]

    return render_template("chatbot.html",
                           chat_history=chat_sessions[session_id],
                           chat_sessions=all_sessions,
                           active_session=session_id,
                           typing=False)

from flask import jsonify

@app.route("/chatbot/message", methods=["POST"])
def chatbot_message():
    data = request.get_json()
    user_input = data["message"]

    session_id = session.get("active_session")
    if not session_id:
        session_id = str(uuid.uuid4())
        session["active_session"] = session_id

    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    chat_sessions[session_id].append({"role": "user", "content": user_input})

    chat = model.start_chat(history=[
        {"role": "user", "parts": [SYSTEM_PROMPT]}
    ] + [
        {"role": msg["role"], "parts": [msg["content"]]} for msg in chat_sessions[session_id]
    ])
    response = chat.send_message(user_input).text

    chat_sessions[session_id].append({"role": "model", "content": response})

    return jsonify({"reply": response})


@app.route("/chatbot/switch/<session_id>")
def switch_session(session_id):
    if session_id not in chat_sessions:
        # Jika sesi tidak ditemukan, buat sesi baru agar tidak error
        chat_sessions[session_id] = []
    session["active_session"] = session_id
    return redirect(url_for("chatbot"))


@app.route("/chatbot/new")
def new_session():
    new_id = str(uuid.uuid4())
    session["active_session"] = new_id
    chat_sessions[new_id] = []
    return redirect(url_for("chatbot"))


if __name__ == "__main__":
    app.run(debug=True)
