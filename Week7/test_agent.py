from app import run_agent
import time

tool_test_set = [
    ("請問幾點可以 Check-in？", "get_bnb_info"),
    ("地址在哪裡？有停車位嗎？", "get_bnb_info"),
    ("可以帶寵物嗎？", "get_bnb_info"),
    ("海藍雙人房一晚多少錢？", "search_rooms"),
    ("你們有四人房嗎？", "search_rooms"),
    ("兩個人住海藍雙人房 3 晚總共多少錢？", "calculate_stay"),
    ("溫馨四人房住兩晚，加一床，多少錢？", "calculate_stay"),
    ("房間冷氣壞了，我要找經理！", "transfer_to_human"),
    ("我要客訴，服務態度很差", "transfer_to_human"),
    ("今天小琉球會下雨嗎？", "(no tool was used)")
]

correct = 0
print("\n開始執行工具選擇測試...\n")
for question, expected in tool_test_set:
    _, trace = run_agent(question)
    used = [t["tool"] for t in trace]

    if expected == "(no tool was used)" and not used:
        is_correct = True
    else:
        is_correct = expected in used

    correct += is_correct
    status = "OK  " if is_correct else "MISS"
    print(f"{status} {question:35s} expected {expected:20s} used {used}")
    time.sleep(1)

print(f"\ntool choice = {correct}/{len(tool_test_set)}")