import json
import os
import sys

import truststore
truststore.inject_into_ssl()

import httpx
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# When running inside a PyInstaller exe, __file__ points to the temp
# extraction folder.  Use the exe's directory instead so .env and logs/
# are found next to the executable.
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

app = FastAPI(title="Voice Mode Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_DIR = _BASE
CONVERSATION_FILE = os.path.join(BACKEND_DIR, "logs", "last_conversation.json")

LANGUAGE_CONFIG = {
    "English": {
        "voice": "en-US-AvaMultilingualNeural",
        "speech_lang": "en-US",
        "instruction": (
            "LANGUAGE INSTRUCTION (NON-NEGOTIABLE): Conduct the ENTIRE conversation in English only. "
            "Do not switch to any other language under any circumstances.\n\n"
            "You are a woman. Always refer to yourself using feminine pronouns (I, me). "
            "Never use male language or male-gendered terms.\n"
            "Regardless of what the salesperson says first, your very first reply MUST be to ask them "
            "to tell you about their product. Example: 'Hello, what is the product?'\n"
            "NEVER offer help, ask how you can assist, or behave like a support agent.\n"
            "NEVER say things like 'How can I help you?' or 'What do you need?'\n"
            "You are a POTENTIAL CUSTOMER. A salesperson is trying to sell you something.\n"
            "Your job is to EVALUATE what they are selling, ask tough questions, and raise objections.\n\n"
            "CRITICAL ROLE RULES — never break these:\n"
            "- You are the CUSTOMER. The person talking to you is the SALESPERSON.\n"
            "- React only to what the salesperson tells you.\n"
            "- Ask tough, realistic follow-up questions.\n"
            "- Raise objections about price, ROI, competition, or implementation.\n"
            "- If they haven’t explained the product yet, ask them to pitch it.\n\n"
            "Your personality: Busy professional, slightly skeptical, evaluating multiple options.\n"
            "Keep responses concise (1–2 sentences max)."
        ),
    },

    "Hindi": {
        "voice": "hi-IN-SwaraNeural",
        "speech_lang": "hi-IN",
        "instruction": (
            "LANGUAGE INSTRUCTION (अनिवार्य): पूरी बातचीत केवल हिंदी में करें। "
            "किसी भी परिस्थिति में किसी अन्य भाषा में न बोलें।\n\n"
            "आप एक महिला हैं। हमेशा अपने लिए स्त्रीलिंग भाषा और सर्वनामों का प्रयोग करें। "
            "कभी भी पुरुष-संबंधित भाषा का उपयोग न करें।\n"
            "सेल्सपर्सन पहले कुछ भी कहे, आपका पहला जवाब अनिवार्य रूप से होना चाहिए: "
            "'नमस्ते, प्रोडक्ट क्या है?'\n"
            "कभी भी सहायता की पेशकश न करें या सपोर्ट एजेंट की तरह व्यवहार न करें।\n"
            "आप एक संभावित ग्राहक हैं और प्रोडक्ट का मूल्यांकन कर रही हैं।\n"
            "कीमत, ROI, प्रतियोगिता और इम्प्लीमेंटेशन पर कठिन सवाल पूछें।\n\n"
            "व्यक्तित्व: व्यस्त प्रोफेशनल, थोड़ा संदेहपूर्ण।\n"
            "उत्तर 1–2 वाक्यों में रखें।"
        ),
    },

    "French": {
        "voice": "fr-FR-DeniseNeural",
        "speech_lang": "fr-FR",
        "instruction": (
            "LANGUAGE INSTRUCTION (NON NÉGOCIABLE): Toute la conversation doit se faire uniquement en français.\n\n"
            "Vous êtes une femme et vous vous exprimez uniquement au féminin.\n"
            "Peu importe ce que dit le commercial en premier, votre toute première réponse doit être : "
            "'Bonjour, quel est le produit ?'\n"
            "N’offrez jamais votre aide et n’agissez jamais comme un agent de support.\n"
            "Vous êtes une cliente potentielle qui évalue une proposition commerciale.\n"
            "Posez des questions difficiles et exprimez des objections.\n\n"
            "Personnalité : professionnelle occupée, légèrement sceptique.\n"
            "Réponses courtes (1 à 2 phrases)."
        ),
    },

    "Polish": {
        "voice": "pl-PL-AgnieszkaNeural",
        "speech_lang": "pl-PL",
        "instruction": (
            "LANGUAGE INSTRUCTION (OBOWIĄZKOWE): Cała rozmowa musi odbywać się wyłącznie po polsku.\n\n"
            "Jesteś kobietą i zawsze używasz formy żeńskiej.\n"
            "Twoja pierwsza odpowiedź ZAWSZE brzmi: "
            "'Cześć, jaki jest produkt?'\n"
            "Nie oferuj pomocy ani wsparcia.\n"
            "Jesteś potencjalną klientką oceniającą ofertę sprzedażową.\n"
            "Zadawaj trudne pytania i zgłaszaj obiekcje.\n\n"
            "Osobowość: zapracowana, sceptyczna profesjonalistka.\n"
            "Odpowiedzi: 1–2 zdania."
        ),
    },

    "Norwegian": {
        "voice": "nb-NO-IselinNeural",
        "speech_lang": "nb-NO",
        "instruction": (
            "LANGUAGE INSTRUCTION (IKKE FORHANDLINGSBART): Hele samtalen skal foregå kun på norsk.\n\n"
            "Du er en kvinne og bruker alltid feminin form.\n"
            "Uansett hva selgeren sier først, må ditt første svar være: "
            "'Hei, hva er produktet?'\n"
            "Tilby aldri hjelp og opptre aldri som kundestøtte.\n"
            "Du er en potensiell kunde som vurderer et salgstilbud.\n"
            "Still kritiske spørsmål og kom med innvendinger.\n\n"
            "Personlighet: travel, profesjonell og litt skeptisk.\n"
            "Svar kort (1–2 setninger)."
        ),
    },
}

# ── Request models ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_message: str
    conversation_history: list[dict] = []
    system_prompt: str = ""
    language: str = "English"


class EvaluateRequest(BaseModel):
    transcript: list[dict]


class DealClinicEvaluateRequest(BaseModel):
    conversation_history: list[dict]
    opportunity_name: str = ""


class CustomerEvaluateRequest(BaseModel):
    transcript: list[dict]


class CustomerSessionIn(BaseModel):
    username: str
    report: dict


class FeedbackRequest(BaseModel):
    vote: str | None = None          # "up" | "down" | None
    comment: str = ""
    session_rating: float | None = None  # the AI-generated rating from the report
    source: str = "CustomerSessionReport"


class CustomerReportRequest(BaseModel):
    conversation_history: list[dict] = []


# ── GET /api/speech-token ───────────────────────────────────────────────

@app.get("/api/speech-token")
async def get_speech_token(language: str = "English"):
    """Exchange the Speech API key for a short-lived auth token and
    ICE relay credentials needed by the browser for WebRTC avatar."""
    speech_key = os.getenv("AZURE_SPEECH_KEY", "")
    speech_region = os.getenv("AZURE_SPEECH_REGION", "")

    if not speech_key or not speech_region:
        raise HTTPException(
            status_code=500,
            detail="AZURE_SPEECH_KEY and AZURE_SPEECH_REGION must be set in .env",
        )

    # 1) Speech authorization token (valid ~10 min)
    token_url = (
        f"https://{speech_region}.api.cognitive.microsoft.com"
        "/sts/v1.0/issueToken"
    )
    try:
        r = requests.post(
            token_url,
            headers={"Ocp-Apim-Subscription-Key": speech_key},
            timeout=10,
        )
        r.raise_for_status()
        speech_token = r.text
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token request failed: {exc}")

    # 2) ICE relay credentials for avatar WebRTC
    ice_url = (
        f"https://{speech_region}.tts.speech.microsoft.com"
        "/cognitiveservices/avatar/relay/token/v1"
    )
    try:
        r = requests.get(
            ice_url,
            headers={"Ocp-Apim-Subscription-Key": speech_key},
            timeout=10,
        )
        r.raise_for_status()
        ice_data = r.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ICE token request failed: {exc}")

    lang_cfg = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["English"])

    return {
        "token": speech_token,
        "region": speech_region,
        "iceServers": ice_data,
        "avatarCharacter": os.getenv("AZURE_AVATAR_CHARACTER", "lisa"),
        "avatarStyle": os.getenv("AZURE_AVATAR_STYLE", "casual-sitting"),
        "voiceName": lang_cfg["voice"],
        "speechLang": lang_cfg["speech_lang"],
    }


# ── GET /api/chat-stream (SSE) ─────────────────────────────────────────

@app.post("/api/chat-stream")
async def chat_stream(req: ChatRequest):
    """Stream Azure OpenAI tokens as SSE so the frontend can start avatar
    speech on the first sentence without waiting for the full response."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

    if not endpoint or not api_key:
        raise HTTPException(
            status_code=500, detail="Azure OpenAI credentials not configured"
        )

    lang_cfg = LANGUAGE_CONFIG.get(req.language, LANGUAGE_CONFIG["English"])
    system_prompt=lang_cfg['instruction']
    if req.system_prompt:
        system_prompt += f"\n\nAdditional customer context:\n{req.system_prompt}"

    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.conversation_history:
        messages.append(
            {
                "role": "assistant" if msg.get("role") == "assistant" else "user",
                "content": msg["text"],
            }
        )
    messages.append({"role": "user", "content": req.user_message})

    url = (
        f"{endpoint}/openai/deployments/{model}/chat/completions?api-version=2024-12-01-preview"
    )
    headers_oai = {"api-key": api_key, "Content-Type": "application/json"}
    body = {
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 200,
        "stream": True,
    }

    async def _generate():
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream(
                "POST", url, headers=headers_oai, json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        yield "data: [DONE]\n\n"
                        return
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        token = delta.get("content")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── Deal Clinic data helpers ────────────────────────────────────────────

_DATA_ROOT = os.path.dirname(BACKEND_DIR)  # workspace root
OPPORTUNITIES_FILE = os.path.join(_DATA_ROOT, "data", "opportunities.json")
DEAL_CLINIC_GUIDE_FILE = os.path.join(_DATA_ROOT, "data", "deal-clinic_guide.txt")


def _load_opportunities():
    with open(OPPORTUNITIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_deal_clinic_guide():
    if not os.path.exists(DEAL_CLINIC_GUIDE_FILE):
        return ""
    with open(DEAL_CLINIC_GUIDE_FILE, "r", encoding="utf-8") as f:
        return f.read()


# ── GET /api/opportunities ─────────────────────────────────────────────

@app.get("/api/opportunities")
async def get_opportunities():
    """Return the list of opportunities from the local JSON file."""
    if not os.path.exists(OPPORTUNITIES_FILE):
        raise HTTPException(status_code=404, detail="opportunities.json not found")
    return _load_opportunities()


# ── GET /api/voice/token ───────────────────────────────────────────────

VOICE_LANGUAGE_CONFIG = {
    "en": {
        "voice": "en-US-AndrewMultilingualNeural",
        "speech_lang": "en-US",
        "instruction": "Conduct the ENTIRE conversation in English only. Do not switch to any other language.",
    },
    "hi": {
        "voice": "hi-IN-SwaraNeural",
        "speech_lang": "hi-IN",
        "instruction": "पूरी बातचीत केवल हिंदी में करें। किसी भी अन्य भाषा में न बोलें।",
    },
    "de": {
        "voice": "de-DE-FlorianMultilingualNeural",
        "speech_lang": "de-DE",
        "instruction": "Führen Sie das GESAMTE Gespräch nur auf Deutsch. Wechseln Sie nicht zu einer anderen Sprache.",
    },
    "fr": {
        "voice": "fr-FR-RemyMultilingualNeural",
        "speech_lang": "fr-FR",
        "instruction": "Menez TOUTE la conversation uniquement en français. Ne passez pas à une autre langue.",
    },
    "nb": {
        "voice": "nb-NO-FinnNeural",
        "speech_lang": "nb-NO",
        "instruction": "Gjennomfør HELE samtalen kun på norsk. Ikke bytt til et annet språk.",
    },
    "pl": {
        "voice": "pl-PL-MarekNeural",
        "speech_lang": "pl-PL",
        "instruction": "Prowadź CAŁĄ rozmowę tylko po polsku. Nie przełączaj się na inny język.",
    },
    "mr": {
        "voice": "mr-IN-AarohiNeural",
        "speech_lang": "mr-IN",
        "instruction": "संपूर्ण संभाषण फक्त मराठीत करा. इतर कोणत्याही भाषेत बोलू नका.",
    },
}


@app.get("/api/voice/token")
async def get_voice_token(opportunity_name: str, language: str = "en"):
    """Return VoiceLive connection details and a tailored system prompt."""
    opportunities = _load_opportunities()
    guide = _load_deal_clinic_guide()

    opportunity = next(
        (op for op in opportunities if op.get("Name") == opportunity_name), {}
    )

    lang = VOICE_LANGUAGE_CONFIG.get(language, VOICE_LANGUAGE_CONFIG["en"])

    system_prompt = f"""You are an experienced SALES MANAGER conducting a deal review session.
You are preparing a salesperson for an upcoming customer meeting.

LANGUAGE INSTRUCTION: {lang["instruction"]}
This is non-negotiable — always respond in the selected language regardless of what language the salesperson uses.

OPPORTUNITY DETAILS:
- Deal Name: {opportunity.get("Name", "N/A")}
- Stage: {opportunity.get("StageName", "N/A")}
- Amount: {opportunity.get("CurrencyIsoCode", "")} {opportunity.get("Amount", "N/A")}
- Type: {opportunity.get("Type", "N/A")}
- Market Segment: {opportunity.get("MarketSegment__c", "N/A")}
- Contract Type: {opportunity.get("ContractType__c", "N/A")}
- Project Type: {opportunity.get("ProjectType__c", "N/A")}
- Close Date: {opportunity.get("CloseDate", "N/A")}
- Probability: {opportunity.get("Probability", "N/A")}%
- Customer Segment: {opportunity.get("UltimateCustomerSegmentation__c", "N/A")}
- Expected Revenue: {opportunity.get("CurrencyIsoCode", "")} {opportunity.get("ExpectedRevenue", "N/A")}
- Sales Channel: {opportunity.get("SalesChannel__c", "N/A")}

DEAL CLINIC GUIDE:
{guide}

RULES:
- You are the SALES MANAGER, the person talking to you is the SALESPERSON
- Ask ONE focused question at a time strictly based on the deal clinic guide
- Be direct, professional and constructive
- Challenge gaps in their thinking but stay supportive
- React to answers and dig deeper if vague or incomplete
- Keep responses concise since this is a voice conversation
- ONLY discuss this specific opportunity — do not go off topic
- Start by asking how the salesperson's day was — this should be your first question
"""

    return {
        "endpoint": os.getenv("AZURE_VOICELIVE_ENDPOINT"),
        "api_key": os.getenv("AZURE_VOICELIVE_API_KEY"),
        "model": os.getenv("AZURE_VOICELIVE_MODEL", "gpt-4.1-mini"),
        "api_version": os.getenv("AZURE_VOICELIVE_API_VERSION", "2025-10-01"),
        "voice": lang["voice"],
        "speech_lang": lang["speech_lang"],
        "system_prompt": system_prompt,
    }


# ── POST /api/deal-clinic/evaluate ─────────────────────────────────────────────

@app.post("/api/deal-clinic/evaluate")
async def deal_clinic_evaluate(req: DealClinicEvaluateRequest):
    """Evaluate a deal clinic voice session and return structured coaching feedback."""
    _save_conversation(req.conversation_history)
    return _generate_deal_clinic_evaluation(req.conversation_history, req.opportunity_name)


# ── POST /api/customer/evaluate ────────────────────────────────────────────

@app.post("/api/customer/evaluate")
async def customer_evaluate(req: CustomerEvaluateRequest):
    """Evaluate a customer meeting session using the Challenger framework."""
    _save_conversation(req.transcript)
    return _generate_customer_evaluation(req.transcript)


# ── Customer session persistence ───────────────────────────────────────────

CUSTOMER_SESSIONS_FILE = os.path.join(os.path.dirname(BACKEND_DIR), "data", "customer_sessions.json")


def _load_customer_sessions() -> list:
    if not os.path.exists(CUSTOMER_SESSIONS_FILE):
        return []
    try:
        with open(CUSTOMER_SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_customer_sessions(sessions: list) -> None:
    os.makedirs(os.path.dirname(CUSTOMER_SESSIONS_FILE), exist_ok=True)
    with open(CUSTOMER_SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)


@app.post("/api/customer/sessions")
async def save_customer_session(req: CustomerSessionIn):
    """Persist a customer meeting session result for a user."""
    from datetime import datetime as _dt
    sessions = _load_customer_sessions()
    sessions.append({
        "username": req.username,
        "timestamp": _dt.utcnow().isoformat() + "Z",
        "report": req.report,
    })
    _save_customer_sessions(sessions)
    return {"status": "ok"}


@app.get("/api/customer/sessions")
async def get_customer_sessions(username: str):
    """Return all customer meeting sessions for a user, oldest first."""
    sessions = _load_customer_sessions()
    return [s for s in sessions if s.get("username") == username]


# ── Deal Clinic session persistence ───────────────────────────────────────

class DealClinicSessionIn(BaseModel):
    username: str
    opportunity_name: str
    report: dict


SESSIONS_FILE = os.path.join(os.path.dirname(BACKEND_DIR), "data", "deal_clinic_sessions.json")


def _load_sessions() -> list:
    if not os.path.exists(SESSIONS_FILE):
        return []
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_sessions(sessions: list) -> None:
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)


@app.post("/api/deal-clinic/sessions")
async def save_deal_clinic_session(req: DealClinicSessionIn):
    """Persist a deal clinic session result for a user."""
    from datetime import datetime as _dt
    sessions = _load_sessions()
    sessions.append({
        "username": req.username,
        "opportunity_name": req.opportunity_name,
        "timestamp": _dt.utcnow().isoformat() + "Z",
        "report": req.report,
    })
    _save_sessions(sessions)
    return {"status": "ok"}


@app.get("/api/deal-clinic/sessions")
async def get_deal_clinic_sessions(username: str):
    """Return all deal clinic sessions for a user, oldest first."""
    sessions = _load_sessions()
    return [s for s in sessions if s.get("username") == username]


# ── POST /api/feedback ────────────────────────────────────────────────

DATA_DIR = os.path.join(BACKEND_DIR, "data")
FEEDBACK_FILE = os.path.join(DATA_DIR, "userfeedback.json")


@app.post("/api/feedback")
async def save_feedback(req: FeedbackRequest):
    """Append a feedback entry to data/userfeedback.json."""
    from datetime import datetime as _dt
    
    feedback_dir = os.path.join(DATA_DIR, "feedback")
    os.makedirs(feedback_dir, exist_ok=True)
    
    feedback_file = os.path.join(feedback_dir, "userfeedback.json")

    # Load existing entries (or start fresh)
    entries = []
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:   
                entries = json.load(f)
        except json.JSONDecodeError:
                entries = []

    entry = {
        "timestamp": _dt.utcnow().isoformat() + "Z",
        "source": req.source,
        "vote": req.vote,
        "session_rating": req.session_rating,
        "comment": req.comment,
    }
    entries.append(entry)

    with open(feedback_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    return {"status": "ok"}


# ── GET /api/evaluate ──────────────────────────────────────────────────

@app.post("/api/evaluate")
async def evaluate(req: EvaluateRequest):
    """Evaluate a sales conversation transcript and return structured feedback."""
    _save_conversation(req.transcript)
    return _generate_evaluation(req.transcript)


# ── POST /api/customer/report ───────────────────────────────────────────

@app.post("/api/customer/report")
async def customer_report(req: CustomerReportRequest):
    """Generate a Challenger-based performance report from conversation history."""
    _save_conversation(req.conversation_history)
    return _generate_challenger_report(req.conversation_history)


# ── Helpers ─────────────────────────────────────────────────────────────

def _save_conversation(transcript: list[dict]):
    os.makedirs(os.path.join(BACKEND_DIR, "logs"), exist_ok=True)
    with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)


def _generate_evaluation(conversation: list[dict]) -> dict:
    """Call Azure OpenAI to evaluate the sales conversation."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

    if not conversation:
        return {
            "strength": ["No conversation recorded."],
            "weakness": [],
            "rating": 0,
            "summary": "The session ended before any conversation took place.",
        }

    transcript_text = "\n".join(
        f"{m['role']}: {m['text']}" for m in conversation
    )

    url = (
        f"{endpoint}/openai/deployments/{model}"
        "/chat/completions?api-version=2024-12-01-preview"
    )
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert sales trainer. Evaluate the salesperson "
                    "based on the conversation transcript below. "
                    "The conversation may be in any language, but your evaluation "
                    "MUST be written entirely in English.\n\n"
                    "Respond ONLY in valid JSON format:\n"
                    "{\n"
                    '  "strength": ["point1", "point2", "point3"],\n'
                    '  "weakness": ["point1", "point2", "point3"],\n'
                    '  "rating": 7.5,\n'
                    '  "summary": "short paragraph"\n'
                    "}\n\n"
                    "IMPORTANT:\n"
                    "- strength and weakness MUST be arrays (bullet points)\n"
                    "- Do not return paragraphs inside them\n"
                    "- rating must be between 0 to 10"
                ),
            },
            {"role": "user", "content": transcript_text},
        ],
        "temperature": 0.6,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        ev = json.loads(raw)
        return {
            "strength": ev.get("strength", []),
            "weakness": ev.get("weakness", []),
            "rating": float(ev.get("rating", 0)),
            "summary": ev.get("summary", ""),
        }
    except Exception as exc:
        return {
            "strength": [],
            "weakness": [],
            "rating": 0,
            "summary": f"Could not generate evaluation: {exc}",
        }


def _generate_deal_clinic_evaluation(conversation: list[dict], opportunity_name: str = "") -> dict:
    """Call Azure OpenAI to evaluate a deal clinic session."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

    _fallback = {
        "overall_score": 0,
        "summary": "The session ended before any conversation took place.",
        "tone": {"score": 0, "feedback": ""},
        "objection_handling": {"score": 0, "feedback": ""},
        "product_knowledge": {"score": 0, "feedback": ""},
        "closing_skills": {"score": 0, "feedback": ""},
        "deal_clinic_adherence": {"score": 0, "feedback": ""},
        "strengths": [],
        "improvements": [],
    }

    if not conversation:
        return _fallback

    # Accept both {text} (TalkCustomer) and {content} (VoiceSession) field formats
    transcript_text = "\n".join(
        f"{m['role']}: {m.get('text', m.get('content', ''))}" for m in conversation
    )
    if opportunity_name:
        transcript_text = f"Opportunity: {opportunity_name}\n\n" + transcript_text

    url = (
        f"{endpoint}/openai/deployments/{model}"
        "/chat/completions?api-version=2024-12-01-preview"
    )
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert sales coach evaluating a Deal Clinic session. "
                    "A sales manager reviewed an opportunity with a salesperson. "
                    "The conversation may be in any language, but your evaluation "
                    "MUST be written entirely in English.\n\n"
                    "Respond ONLY in valid JSON with this exact structure:\n"
                    "{\n"
                    '  "overall_score": 7,\n'
                    '  "summary": "short paragraph overview",\n'
                    '  "tone": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "objection_handling": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "product_knowledge": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "closing_skills": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "deal_clinic_adherence": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "strengths": ["point1", "point2", "point3"],\n'
                    '  "improvements": ["point1", "point2", "point3"]\n'
                    "}\n\n"
                    "IMPORTANT: All scores must be integers between 0 and 10."
                ),
            },
            {"role": "user", "content": transcript_text},
        ],
        "temperature": 0.6,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        ev = json.loads(raw)
        return {
            "overall_score": int(ev.get("overall_score", 0)),
            "summary": ev.get("summary", ""),
            "tone": ev.get("tone", {"score": 0, "feedback": ""}),
            "objection_handling": ev.get("objection_handling", {"score": 0, "feedback": ""}),
            "product_knowledge": ev.get("product_knowledge", {"score": 0, "feedback": ""}),
            "closing_skills": ev.get("closing_skills", {"score": 0, "feedback": ""}),
            "deal_clinic_adherence": ev.get("deal_clinic_adherence", {"score": 0, "feedback": ""}),
            "strengths": ev.get("strengths", []),
            "improvements": ev.get("improvements", []),
        }
    except Exception as exc:
        _fallback["summary"] = f"Could not generate evaluation: {exc}"
        return _fallback


def _generate_customer_evaluation(conversation: list[dict]) -> dict:
    """Evaluate a customer meeting using the DNV Challenger framework."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

    _fallback = {
        "overall_score": 0,
        "summary": "The session ended before any conversation took place.",
        "conversation_summary": "",
        "next_focus": "",
        "strengths": [],
        "weaknesses": [],
        "improvements": [],
        "commercial_insight": {"score": 0, "feedback": ""},
        "tailoring": {"score": 0, "feedback": ""},
        "constructive_tension": {"score": 0, "feedback": ""},
        "taking_control": {"score": 0, "feedback": ""},
        "stakeholder_navigation": {"score": 0, "feedback": ""},
        "two_way_dialogue": {"score": 0, "feedback": ""},
    }

    if not conversation:
        return _fallback

    transcript_text = "\n".join(
        f"{m['role']}: {m.get('text', m.get('content', ''))}" for m in conversation
    )

    url = (
        f"{endpoint}/openai/deployments/{model}"
        "/chat/completions?api-version=2024-12-01-preview"
    )
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert sales coach evaluating a salesperson using the DNV Challenger framework. "
                    "The conversation may be in any language, but your evaluation MUST be written entirely in English.\n\n"
                    "Respond ONLY in valid JSON with this exact structure:\n"
                    "{\n"
                    '  "overall_score": 7,\n'
                    '  "summary": "One paragraph coach summary",\n'
                    '  "conversation_summary": "Brief neutral description of what was discussed",\n'
                    '  "next_focus": "Single most important improvement to focus on next session",\n'
                    '  "strengths": ["point1", "point2", "point3"],\n'
                    '  "weaknesses": ["point1", "point2"],\n'
                    '  "improvements": ["action1", "action2"],\n'
                    '  "commercial_insight": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "tailoring": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "constructive_tension": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "taking_control": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "stakeholder_navigation": {"score": 7, "feedback": "specific feedback"},\n'
                    '  "two_way_dialogue": {"score": 7, "feedback": "specific feedback"}\n'
                    "}\n\n"
                    "IMPORTANT: All scores must be integers 0-10. strengths/weaknesses/improvements must be arrays."
                ),
            },
            {"role": "user", "content": transcript_text},
        ],
        "temperature": 0.6,
        "max_tokens": 900,
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        ev = json.loads(raw)

        def _cat(key):
            d = ev.get(key, {})
            return {"score": int(d.get("score", 0)), "feedback": d.get("feedback", "")}

        return {
            "overall_score": int(ev.get("overall_score", 0)),
            "summary": ev.get("summary", ""),
            "conversation_summary": ev.get("conversation_summary", ""),
            "next_focus": ev.get("next_focus", ""),
            "strengths": ev.get("strengths", []),
            "weaknesses": ev.get("weaknesses", []),
            "improvements": ev.get("improvements", []),
            "commercial_insight": _cat("commercial_insight"),
            "tailoring": _cat("tailoring"),
            "constructive_tension": _cat("constructive_tension"),
            "taking_control": _cat("taking_control"),
            "stakeholder_navigation": _cat("stakeholder_navigation"),
            "two_way_dialogue": _cat("two_way_dialogue"),
        }
    except Exception as exc:
        _fallback["summary"] = f"Could not generate evaluation: {exc}"
        return _fallback
