import os
import csv
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI

print("有沒有 .env 檔案？", os.path.exists(".env"))
print("目前的執行路徑：", os.getcwd())

# 1. 讀取環境變數與 API 設定
load_dotenv()
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("LLM_API_URL"),
    timeout=60.0
)
ai_model = os.getenv("MODEL_NAME")
print(f"準備就緒，使用的模型是: {ai_model}")

# 2. 建立並初始化 SQLite 資料庫
connection = sqlite3.connect("bnb.db", check_same_thread=False)
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

# 建立資訊表
cursor.execute("DROP TABLE IF EXISTS bnb_info")
cursor.execute("CREATE TABLE bnb_info (topic TEXT PRIMARY KEY, content TEXT NOT NULL)")

# 建立紀錄表 (房型資料)
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

# 從 CSV 讀取資料並寫入資料庫
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

# 準備供後續工具使用的清單
BNB_TOPICS = [r["topic"] for r in cursor.execute("SELECT topic FROM bnb_info")]

print("資料庫 bnb.db 建立完成！")
# ----------------------------------------------------------------------
# 3. 定義 4 個核心工具函式
# ----------------------------------------------------------------------

def get_bnb_info(topic):
    """查詢民宿基本資訊（如入住時間、地址、停車等）"""
    row = cursor.execute("SELECT content FROM bnb_info WHERE topic = ?", (topic,)).fetchone()
    if row is None:
        return {"found": False, "topics_available": BNB_TOPICS}
    return {"found": True, "topic": topic, "content": row["content"]}

def search_rooms(keyword):
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

def calculate_stay(room_name, nights):
    """計算特定房型的總住宿費用，由程式處理數學計算"""
    found = search_rooms(room_name)
    if not found["found"] or len(found["rooms"]) != 1:
        return {"total": None, "note": f"無法精確鎖定單一房型 '{room_name}'，請確認房型名稱後重新試算。"}
    
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
    """遇到客訴或資料庫查不到的問題時轉接真人"""
    return {
        "message": "請直接撥打民宿服務專線 0912-345-678，將有專人為您服務。",
        "note": "轉接指示已完成。請先用一句話向客人說明原因，再提供聯絡資訊，切勿重複呼叫此工具。"
    }

# ----------------------------------------------------------------------
# 4. 配置 Agent 角色、規則與工具規格 (JSON Schema)
# ----------------------------------------------------------------------
ROLE = "你是白海民宿的 AI 客服助理。所有價格均為新台幣。請以親切、專業的口吻回答顧客。"

RULES = [
    "只能根據工具呼叫傳回的結果來回答顧客。絕不憑記憶回答，也絕不編造任何資訊。",
    "如果工具查不到結果，請誠實告知顧客，不要進行猜測。",
    "只回答與白海民宿相關的問題。若顧客詢問其他無關話題，請禮貌婉拒。",
    "回答請保持簡短，盡量控制在三句話以內。",
    "詢問民宿基本規定（如入住時間、地址、停車、早餐）-> 使用 get_bnb_info。",
    "查詢房型名稱、房價、介紹或是否有空房 -> 使用 search_rooms。",
    "計算住宿總金額（入住幾晚）-> 必須使用 calculate_stay，絕不可以自己心算。",
    "遇到客訴、要求經理/真人服務，或任何工具無法回答的問題 -> 使用 transfer_to_human。"
]

TOOL_FUNCTIONS = {
    "get_bnb_info": get_bnb_info,
    "search_rooms": search_rooms,
    "calculate_stay": calculate_stay,
    "transfer_to_human": transfer_to_human
}

# 讓模型看懂工具怎麼用的說明書
TOOL_SPECS = [
    {"type": "function", "function": {"name": "get_bnb_info", "description": "查詢民宿的設施與規定", "parameters": {"type": "object", "properties": {"topic": {"type": "string", "enum": BNB_TOPICS}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "search_rooms", "description": "搜尋房型資訊、價格與預訂狀態", "parameters": {"type": "object", "properties": {"keyword": {"type": "string", "description": "搜尋關鍵字"}}, "required": ["keyword"]}}},
    {"type": "function", "function": {"name": "calculate_stay", "description": "【強制規定】只要顧客問到任何住宿總金額、住幾晚的費用、或者包含加床費用的計算，『絕對禁止』自行心算或僅用 search_rooms，必須立刻且強制呼叫此工具進行計算！", "parameters": {"type": "object", "properties": {"room_name": {"type": "string"}, "nights": {"type": "integer"}}, "required": ["room_name", "nights"]}}},
    {"type": "function", "function": {"name": "transfer_to_human", "description": "當顧客提出客訴、要求真人客服或遇到無法解答的問題時使用。", "parameters": {"type": "object", "properties": {}, "required": []}}}
]

print("工具與規則設定完成！")
import json
import time
import re

# ----------------------------------------------------------------------
# 5. Agent 核心驅動迴圈 (Agent Loop)
# ----------------------------------------------------------------------
def run_agent(question, max_steps=6):
    """執行對話迴圈，處理 Tool Calling 並回傳 (最終回答, 工具呼叫軌跡)"""
    system_prompt = ROLE + "\n\nRULES\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(RULES, 1))
    # 根據輸入是否包含中文決定回覆語言
    language = "Traditional Chinese" if re.search(r"[\u4e00-\u9fff]", question) else "English"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Reply in {language}."},
        {"role": "user", "content": question}
    ]
    tools = {"tools": TOOL_SPECS} if TOOL_SPECS else {}
    trace = []

    for step in range(max_steps):
        response = client.chat.completions.create(
            model=ai_model, messages=messages, temperature=0.2, **tools
        )
        message = response.choices[0].message

        # 若模型沒有要求呼叫工具，代表它已經準備好最終回答了
        if not message.tool_calls:
            return (message.content or "").strip(), trace

        # 若模型要求呼叫工具，將請求記錄到對話中
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

        # 逐一執行模型請求的工具
        for call in message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            tool_name = call.function.name
            
            if tool_name in TOOL_FUNCTIONS:
                result = TOOL_FUNCTIONS[tool_name](**args)
            else:
                result = {"error": f"Tool {tool_name} not found."}

            trace.append({"tool": tool_name, "arguments": args, "result": result})
            # 將工具執行的結果傳回給模型
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

    return "抱歉，目前系統忙碌中。請撥打專線 0912-345-678 聯繫客服人員。", trace

import gradio as gr

# ----------------------------------------------------------------------
# 6. 建立 Gradio 網頁對話介面
# ----------------------------------------------------------------------
def respond(message, chat_history):
    answer, trace = run_agent(message)
    
    # 完全依照錯誤訊息的要求，改用帶有 role 與 content 的字典格式
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": answer})
    
    # 整理右側的工具軌跡顯示
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
    gr.Markdown("# 🐬 白海民宿 AI 客服 (lunar B&B)")
    gr.Markdown("您可以詢問訂房資訊、設施、價格，或試算住宿費用。")
    
    with gr.Row():
        # 左側：對話區塊 (維持最簡化，不加 type 參數)
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="客服對話", height=500)
            msg = gr.Textbox(label="請輸入您的問題", placeholder="例如：請問幾點可以 Check-in？")
            clear = gr.ClearButton([msg, chatbot])
            
        # 右側：工具軌跡區塊
        with gr.Column(scale=1):
            trace_box = gr.Textbox(label="Tools used (工具軌跡)", lines=22, interactive=False)
            
    # 設定按下 Enter 的動作
    msg.submit(respond, [msg, chatbot], [msg, chatbot, trace_box])
    
    # 設定範例問題
    gr.Examples(
        examples=[
            "請問幾點可以 Check-in？附近好停車嗎？",
            "海藍雙人房一晚多少錢？",
            "兩個人住海藍雙人房 3 晚總共多少錢？",
            "房間有小蟲，我要找經理！"
        ],
        inputs=msg
    )

if __name__ == "__main__":
    print("\n啟動 Gradio 網頁介面...")
    demo.launch(share=False)