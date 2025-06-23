async def diagnose_stream(self, chat_id: int):
    from pprint import pprint
    
    print(f"📋 [DIAGNOSE] Kiểm tra trạng thái phát nhạc của chat {chat_id}...\n")
    
    try:
        queue = db.get(chat_id)
        if not queue:
            print("❌ Queue rỗng hoặc không tồn tại.")
            return
        
        current = queue[0]
        print("🎵 Bài hát hiện tại:")
        pprint(current)
        
        start_time = current.get("start_time")
        seconds = current.get("seconds", 0)
        played = (datetime.now() - start_time).seconds if start_time else None
        
        print(f"\n⏱️ Tổng thời lượng: {seconds} giây")
        print(f"⏱️ Đã phát được: {played} giây" if played is not None else "⛔ start_time chưa được gán.")
        
        assistant = await group_assistant(self, chat_id)
        leaveable = False
        for method in ["leave_group_call", "leave_call", "stop", "disconnect"]:
            if hasattr(assistant, method):
                leaveable = True
                break
        print(f"🎧 Assistant hiện tại: {assistant.__class__.__name__}")
        print(f"✅ Có thể thoát call: {'Có' if leaveable else 'Không'}")
    
    except Exception as e:
        print(f"❌ Lỗi khi chạy diagnose: {e}")
