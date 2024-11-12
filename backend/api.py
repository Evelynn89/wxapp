API_KEY = "j1r42Gy5IuoANzzCVPBJmESq"
SECRET_KEY = "GFJqpWxnPf95u45GajquuV22EacNFVit"


def get_access_token():
    """
    使用 API Key 和 Secret Key 获取 access_token
    """
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={API_KEY}&client_secret={SECRET_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        return None


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_question = data.get("question")
    access_token = get_access_token()

    if not access_token:
        return jsonify({"error": "Failed to obtain access token"}), 500

    # 百度对话接口 URL
    url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro?access_token={access_token}"

    payload = {
        "messages": [
            {"role": "user", "content": user_question}
        ],
        "max_tokens": 128,
        "temperature": 0.8
    }

    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        reply = response.json().get("result")
        return jsonify({"reply": reply})
    else:
        return jsonify({"error": response.text}), 500
