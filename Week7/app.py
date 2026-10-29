import os
import csv
import json
import re
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr

# ----------------------------------------------------------------------
# 1. 讀取環境變數與 API 設定
# ----------------------------------------------------------------------
load_dotenv()
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("LLM_API_URL"),
    timeout=60.0
)
ai_model = os.getenv("MODEL_NAME")

# ----------------------------------------------------------------------
# 2. 初始化 SQLite 資料庫 (rooms.csv & bnb_info.csv)
# ----------------------------------------------------------------------
connection = sqlite3.connect("bnb.db", check_same_thread=False)
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

cursor.execute("DROP TABLE IF EXISTS bnb_info")
cursor.execute("CREATE TABLE bnb_info (topic TEXT PRIMARY KEY, content TEXT NOT NULL)")

cursor.execute("DROP TABLE IF EXISTS rooms")
cursor.execute("""
CREATE TABLE rooms (
    room_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    max_occupancy INTEGER NOT NULL,
    is_available INTEGER NOT NULL,
    description TEXT
)
""")

with open("bnb_info.csv", newline="", encoding="utf-8") as f:
    cursor.executemany(
        "INSERT INTO bnb_info VALUES (?, ?)",
        [(r["topic"], r["content"]) for r in csv.DictReader(f)]
    )

with open("rooms.csv", newline="", encoding="utf-8") as f:
    cursor.executemany(
        "INSERT INTO rooms VALUES (?, ?, ?, ?, ?, ?)",
        [(r["room_id"], r["name"], int(r["price"]), int(r["max_occupancy"]),
          1 if str(r["is_available"]).lower() == "true" else 0, r["description"])
         for r in csv.DictReader(f)]
    )
connection.commit()

BNB_TOPICS = [r["topic"] for r in cursor.execute("SELECT topic FROM bnb_info")]

# ----------------------------------------------------------------------
# 3. 載入 RAG 文件 (rules.md)
# ----------------------------------------------------------------------
RULES_FILE = "rules.md"
RULES_LIST = []
if os.path.exists(RULES_FILE):
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        RULES_LIST = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

# ----------------------------------------------------------------------
# 4. 定義核心工具函式 (Tool Calling + RAG)
# ----------------------------------------------------------------------
def search_rules(query: str):
    """【RAG 工具】檢索白海民宿的詳細住宿守則、禁菸罰額、延遲退房費、潛水裝備等規定"""
    if not RULES_LIST:
        return {"found": False, "message": "目前未載入詳細住宿守則。"}
    
    # 簡易關鍵字相似度比對 (RAG 檢索)
    keywords = [k for k in re.split(r"\s+|，|。|？|\?", query) if k]
    matched = []
    for rule in RULES_LIST:
        score = sum(1 for kw in keywords if kw in rule)
        if score > 0 or any(kw in query for kw in ["菸", "延遲", "退房", "毛巾", "寵物", "潛水", "吵", "安寧", "環保", "洗腳"]):
            matched.append(rule)
    
    if not matched:
        matched = RULES_LIST  # 全量參考
        
    return {"found": True, "relevant_rules": matched[:5]}

def get_bnb_info(topic: str):
    """查詢民宿基本資訊（如入住時間、地址、停車等）"""
    row = cursor.execute("SELECT content FROM bnb_info WHERE topic = ?", (topic,)).fetchone()
    if row is None:
        return {"found": False, "topics_available": BNB_TOPICS}
    return {"found": True, "topic": topic, "content": row["content"]}

def search_rooms(keyword: str):
    """搜尋房型名稱、價格與供應狀態"""
    like = f"%{keyword.strip()}%"
    rows = cursor.execute(
        "SELECT room_id, name, price, max_occupancy, is_available, description FROM rooms "
        "WHERE name LIKE ? OR description LIKE ?", (like, like)
    ).fetchall()
    
    if not rows:
        return {"found": False, "note": f"找不到名稱包含 '{keyword}' 的房型或服務。"}
    
    return {
        "found": True,
        "rooms": [{
            "room_id": r["room_id"], "name": r["name"], "price": r["price"], 
            "max_occupancy": r["max_occupancy"], "is_available": bool(r["is_available"])
        } for r in rows]
    }

def calculate_stay(room_name: str, nights: int):
    """計算特定房型的總住宿費用，由程式處理數學計算"""
    found = search_rooms(room_name)
    if not found["found"] or len(found["rooms"]) != 1:
        return {"total": None, "note": f"無法精確鎖定單一房型 '{room_name}'，請確認房型名稱。"}
    
    room = found["rooms"][0]
    total = room["price"] * nights
    return {
        "room_name": room["name"],
        "price_per_night": room["price"],
        "nights": nights,
        "total_price": total,
        "summary": f"{room['name']} {nights} 晚 = 總計 NT${total}"
    }

def transfer_to_human():
    """遇到客訴或無法回答的問題時轉接真人"""
    return {
        "message": "請直接撥打民宿服務專線 0912-345-678，將有專人為您服務。",
        "note": "轉接指示已完成。請先以一句話說明原因並提供電話。"
    }

TOOL_FUNCTIONS = {
    "search_rules": search_rules,
    "get_bnb_info": get_bnb_info,
    "search_rooms": search_rooms,
    "calculate_stay": calculate_stay,
    "transfer_to_human": transfer_to_human
}

TOOL_SPECS = [
    {"type": "function", "function": {"name": "search_rules", "description": "【RAG 工具】檢索民宿詳細規範（如吸菸罰款、逾時退房費、毛巾換洗費、潛水裝備存放、寵物政策、夜間安寧等）", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "顧客詢問的規章關鍵字"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_bnb_info", "description": "查詢民宿基本資訊（ Check-in 時間、地址、停車、早餐、退訂條款）", "parameters": {"type": "object", "properties": {"topic": {"type": "string", "enum": BNB_TOPICS}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "search_rooms", "description": "搜尋房型名稱、房價、容納人數與空房狀態", "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}}},
    {"type": "function", "function": {"name": "calculate_stay", "description": "計算住宿總金額（入住幾晚之費用）。強制禁止自行心算！", "parameters": {"type": "object", "properties": {"room_name": {"type": "string"}, "nights": {"type": "integer"}}, "required": ["room_name", "nights"]}}},
    {"type": "function", "function": {"name": "transfer_to_human", "description": "遇到客訴、要求真人客服或任何系統資料庫無載明之特殊狀況時使用。", "parameters": {"type": "object", "properties": {}, "required": []}}}
]

# ----------------------------------------------------------------------
# 5. 五段式 System Prompt 結構
# ----------------------------------------------------------------------
SYSTEM_PROMPT = """
【角色與目標 Role & Goal】
你是小琉球「白海民宿 (lunar B&B)」的 AI 客服助理。你的目標是提供親切、準確且專業的諮詢，解答關於房型、價格、設施及入住守則等問題。所有價格均為新台幣 (NT$)。

【服務範疇 Scope】
1. 查詢房型資訊、價格、空房狀態及算房價總額。
2. 查詢民宿基礎設施（Check-in時間、地址、停車位、早餐、退訂規則）。
3. 查詢白海民宿的入住守則（包含超時退房費、吸菸罰鍰、寵物規定、環保備品、潛水裝備規範等）。
4. 處理客訴與真人轉接。

【互動規則 Interaction Rules】
1. 嚴格基於工具 (Tool) 傳回之資料進行回答。絕不憑記憶回答，絕不捏造或臆測數據。
2. 只要計算費用，必須且強制呼叫 calculate_stay 工具，禁止自行心算。
3. 只要詢問具體入住規範（如吸菸、退房加收費用、寵物、潛水等），請呼叫 search_rules 進行 RAG 檢索。
4. 回答請維持簡短親切，控制在 3 句內。

【拒絕與特殊狀況 Refusals & Special Cases】
1. 當問題超出「白海民宿」服務範疇（例如詢問天氣、小琉球景點推薦、外縣市飯店）時，必須固定回覆：「抱歉，我只能回答與白海民宿相關的訂房與入住資訊喔！」
2. 當工具搜尋無結果或資料庫查無紀錄時，請誠實告知找不到，絕不瞎編，並引導撥打專線 0912-345-678。
3. 若遇到客訴或要求找經理/真人服務，請呼叫 transfer_to_human。

【開場白 Opening Line】
您好！我是白海民宿的 AI 客服小幫手 🐬 請問今天想了解房型、預約試算還是查詢入住守則呢？
"""

# ----------------------------------------------------------------------
# 6. Agent 核心驅動迴圈
# ----------------------------------------------------------------------
def run_agent(question: str, history=None, max_steps=6):
    language = "Traditional Chinese" if re.search(r"[\u4e00-\u9fff]", question) else "English"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "system", "content": f"Reply in {language}."},
        {"role": "user", "content": question}
    ]
    
    trace = []
    tools = {"tools": TOOL_SPECS} if TOOL_SPECS else {}

    for step in range(max_steps):
        response = client.chat.completions.create(
            model=ai_model, messages=messages, temperature=0.2, **tools
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return (message.content or "").strip(), trace

        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments}
                } for c in message.tool_calls
            ]
        })

        for call in message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            tool_name = call.function.name
            
            if tool_name in TOOL_FUNCTIONS:
                result = TOOL_FUNCTIONS[tool_name](**args)
            else:
                result = {"error": f"Tool {tool_name} not found."}

            trace.append({"tool": tool_name, "arguments": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

    return "抱歉，目前系統忙碌中。請撥打專線 0912-345-678 聯繫專人服務。", trace

# ----------------------------------------------------------------------
# 7. Gradio UI 介面
# ----------------------------------------------------------------------
def respond(message, chat_history):
    answer, trace = run_agent(message)
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": answer})
    
    trace_text = ""
    for t in trace:
        trace_text += f"🔧 工具: {t['tool']}\n"
        trace_text += f"📥 參數: {t['arguments']}\n"
        trace_text += f"📤 結果: {json.dumps(t['result'], ensure_ascii=False)}\n"
        trace_text += "-" * 30 + "\n"
        
    if not trace:
        trace_text = "(未使用工具)"
        
    return "", chat_history, trace_text

with gr.Blocks(title="白海民宿 AI 客服") as demo:
    gr.Markdown("# 🐬 小琉球白海民宿 (lunar B&B) AI 客服")
    gr.Markdown("歡迎詢問房型價格、空房試算、入住規範與民宿設施！")
    
    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="客服對話", 
                height=480,
                value=[{"role": "assistant", "content": "您好！我是白海民宿的 AI 客服小幫手 🐬 請問今天想了解房型、預約試算還是查詢入住守則呢？"}]
            )
            msg = gr.Textbox(label="請輸入您的問題", placeholder="例如：逾時退房怎麼算費用？或者 房間可以吸菸嗎？")
            clear = gr.ClearButton([msg, chatbot])
            
        with gr.Column(scale=1):
            trace_box = gr.Textbox(label="Tools Used (工具與 RAG 軌跡)", lines=22, interactive=False)
            
    msg.submit(respond, [msg, chatbot], [msg, chatbot, trace_box])
    
    gr.Examples(
        examples=[
            "請問海藍雙人房住 3 晚總共多少錢？",
            "房間裡面可以抽菸嗎？如果抽菸會怎樣？",
            "我們潛水回來的裝備可以放房間裡面嗎？",
            "請問明天高雄的天氣怎麼樣？"  # 防越獄/防範疇外測試範例
        ],
        inputs=msg
    )

if __name__ == "__main__":
    demo.launch(share=False)
