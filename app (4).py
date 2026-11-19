import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM = (
    "Siz do'stona ovozli yordamchisiz. Faqat o'zbek tilida (lotin yozuvida) "
    "javob bering. Javoblar qisqa bo'lsin (1-3 gap), chunki ular ovozda o'qiladi. "
    "Emoji, ro'yxat va markdown ishlatmang."
)

HTML = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ovozli yordamchi</title>
<style>
  body{margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
       display:flex;flex-direction:column;height:100vh}
  #log{flex:1;overflow-y:auto;padding:16px}
  .m{max-width:85%;padding:10px 14px;margin:8px 0;border-radius:14px;line-height:1.4}
  .u{background:#2563eb;margin-left:auto}
  .a{background:#1e293b}
  #bar{display:flex;gap:8px;padding:12px;background:#111827}
  #txt{flex:1;padding:12px;border-radius:10px;border:0;font-size:16px}
  button{border:0;border-radius:10px;padding:12px 16px;font-size:16px;cursor:pointer}
  #mic{background:#16a34a;color:#fff}
  #mic.on{background:#dc2626}
  #send{background:#2563eb;color:#fff}
  #st{padding:4px 16px;font-size:13px;color:#94a3b8}
</style>
</head>
<body>
<div id="log"></div>
<div id="st">Mikrofon tugmasini bosing va gapiring</div>
<div id="bar">
  <button id="mic">🎤</button>
  <input id="txt" placeholder="Yoki shu yerga yozing...">
  <button id="send">➤</button>
</div>
<script>
const log = document.getElementById('log');
const st = document.getElementById('st');
const mic = document.getElementById('mic');
const txt = document.getElementById('txt');
let history = [];
let listening = false;

function add(role, text){
  const d = document.createElement('div');
  d.className = 'm ' + (role === 'user' ? 'u' : 'a');
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function speak(text){
  if(!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const voices = speechSynthesis.getVoices();
  const uz = voices.find(v => v.lang.toLowerCase().startsWith('uz'));
  const tr = voices.find(v => v.lang.toLowerCase().startsWith('tr'));
  const ru = voices.find(v => v.lang.toLowerCase().startsWith('ru'));
  const v = uz || tr || ru;
  if(v){ u.voice = v; u.lang = v.lang; } else { u.lang = 'uz-UZ'; }
  u.onend = () => { if(auto) startListen(); };
  speechSynthesis.speak(u);
}

async function ask(text){
  if(!text.trim()) return;
  add('user', text);
  history.push({role:'user', content:text});
  st.textContent = 'O\\'ylayapman...';
  try{
    const r = await fetch('/chat', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({messages: history})});
    const j = await r.json();
    const reply = j.reply || j.error || 'Xatolik';
    history.push({role:'assistant', content:reply});
    add('assistant', reply);
    st.textContent = 'Tayyor';
    speak(reply);
  }catch(e){
    st.textContent = 'Server bilan aloqa yo\\'q';
  }
}

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, auto = false;
if(SR){
  rec = new SR();
  rec.lang = 'uz-UZ';
  rec.interimResults = false;
  rec.onresult = e => { ask(e.results[0][0].transcript); };
  rec.onend = () => { listening = false; mic.classList.remove('on'); };
  rec.onerror = e => { st.textContent = 'Mikrofon xatosi: ' + e.error; };
} else {
  st.textContent = 'Bu brauzer ovozni tanimaydi. Chrome ishlating.';
}

function startListen(){
  if(!rec || listening) return;
  try{ rec.start(); listening = true; mic.classList.add('on'); st.textContent = 'Eshitaman...'; }catch(e){}
}

mic.onclick = () => {
  if(listening){ auto = false; rec.stop(); return; }
  auto = true;  // gaplashish rejimi: javobdan keyin yana eshitadi
  startListen();
};
document.getElementById('send').onclick = () => { ask(txt.value); txt.value=''; };
txt.addEventListener('keydown', e => { if(e.key==='Enter'){ ask(txt.value); txt.value=''; }});
speechSynthesis.onvoiceschanged = () => {};
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
def chat():
    messages = (request.get_json(silent=True) or {}).get("messages", [])[-20:]
    if not messages:
        return jsonify(error="Xabar yo'q"), 400
    if not API_KEY:
        # Kalit yo'q: faqat ovozni sinash uchun aks-sado
        return jsonify(reply="Siz dedingiz: " + messages[-1]["content"])
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": MODEL, "max_tokens": 300,
                  "system": SYSTEM, "messages": messages},
            timeout=30,
        )
        data = r.json()
        if r.status_code != 200:
            return jsonify(error="API xatosi: " + str(data.get("error", {}).get("message", r.status_code)))
        return jsonify(reply=data["content"][0]["text"])
    except Exception as e:
        return jsonify(error="Xatolik: " + str(e))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
