# app.py
import streamlit as st
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from anthropic import Anthropic
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# Line Bot 設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Claude 設定
anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# 初始化聊天歷史
class ChatHistory:
    def __init__(self):
        self.history_file = "chat_history.json"
        self.load_history()
    
    def load_history(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
        except FileNotFoundError:
            self.history = []
    
    def save_history(self):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def add_message(self, user_id, message, is_user=True):
        self.history.append({
            "user_id": user_id,
            "message": message,
            "is_user": is_user,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_history()

chat_history = ChatHistory()

def get_claude_response(message):
    """使用 Claude API 獲取回應"""
    try:
        response = anthropic.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": message
            }]
        )
        return response.content
    except Exception as e:
        st.error(f"Claude API 錯誤: {str(e)}")
        return "抱歉，我現在無法回應，請稍後再試。"

def process_webhook():
    """處理 LINE Webhook"""
    try:
        # 取得請求相關資訊
        body = st.request.get_body().decode('utf-8')
        signature = st.request.headers.get('X-Line-Signature', '')

        # 處理 webhook 事件
        handler.handle(body, signature)
        
        # 解析訊息內容
        payload = json.loads(body)
        for event in payload.get('events', []):
            if event['type'] == 'message':
                user_id = event['source']['userId']
                message = event['message']['text']
                
                # 儲存用戶訊息
                chat_history.add_message(user_id, message)
                
                # 使用 Claude 產生回應
                bot_response = get_claude_response(message)
                chat_history.add_message(user_id, bot_response, is_user=False)
                
                # 回覆訊息給用戶
                line_bot_api.reply_message(
                    event['replyToken'],
                    TextSendMessage(text=bot_response)
                )
        
        # 回傳 200 狀態碼
        return {"statusCode": 200, "body": "OK"}
    
    except InvalidSignatureError:
        return {"statusCode": 400, "body": "Invalid signature"}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}

def main():
    st.title("Line Bot 管理介面")
    
    # 檢查是否為 webhook 請求
    if st.request.path == "/webhook":
        result = process_webhook()
        st.response = result
        return
    
    # 側邊欄選單
    menu = st.sidebar.selectbox(
        "選擇功能",
        ["對話測試", "對話紀錄", "系統設置"]
    )
    
    if menu == "對話測試":
        st.subheader("對話測試介面")
        user_input = st.chat_input("輸入訊息...")
        
        if user_input:
            test_user_id = "TEST_USER"
            
            # 儲存用戶訊息
            chat_history.add_message(test_user_id, user_input)
            
            # 使用 Claude 生成回應
            bot_response = get_claude_response(user_input)
            chat_history.add_message(test_user_id, bot_response, is_user=False)
            
            # 顯示對話
            st.write("User: " + user_input)
            st.write("Bot: " + bot_response)
    
    elif menu == "對話紀錄":
        st.subheader("對話紀錄")
        for msg in chat_history.history:
            st.write(f"[{msg['timestamp']}] {'User' if msg['is_user'] else 'Bot'}: {msg['message']}")
    
    elif menu == "系統設置":
        st.subheader("系統設置")
        if st.button("清除所有對話紀錄"):
            chat_history.history = []
            chat_history.save_history()
            st.success("已清除所有對話紀錄")

if __name__ == "__main__":
    main()