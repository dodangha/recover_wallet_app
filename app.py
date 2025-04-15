from flask import Flask, request, render_template, Response, stream_with_context, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import itertools
import requests
from mnemonic import Mnemonic
from eth_account import Account

app = Flask(__name__)
app.secret_key = "random_secret_key"  # cần cho session nếu dùng thêm
Account.enable_unaudited_hdwallet_features()

# ⚙️ Limit mỗi IP 5 lượt
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["5 per day"]
)

ETHERSCAN_API_KEY = "YOUR_API_KEY"

TOKENS = {
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991C6218B36c1d19D4a2e9Eb0cE3606EB48",
    "BNB":  "0xb8c77482e45f1f44de1745f52c74426c631bdd52",
    "DAI":  "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA"
}

def get_eth_balance(address):
    try:
        r = requests.get("https://api.etherscan.io/api", params={
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": ETHERSCAN_API_KEY
        })
        return int(r.json()["result"]) / 1e18
    except:
        return None

def get_token_balance(address, token_address):
    try:
        r = requests.get("https://api.etherscan.io/api", params={
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": token_address,
            "address": address,
            "tag": "latest",
            "apikey": ETHERSCAN_API_KEY
        })
        return int(r.json()["result"]) / 1e18
    except:
        return None

def get_btc_balance(address):
    try:
        r = requests.get(f"https://blockchain.info/q/addressbalance/{address}")
        return int(r.text) / 1e8
    except:
        return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/recover", methods=["POST"])
@limiter.limit("5 per day")  # 🛡️ Giới hạn 5 lần mỗi IP mỗi ngày
def recover():
    data = request.get_json()
    known_words = data["seed"]

    mnemo = Mnemonic("english")
    wordlist = mnemo.wordlist
    missing_indexes = [i for i, word in enumerate(known_words) if word == ""]

    def generate():
        found = 0
        tried = 0

        for combo in itertools.permutations(wordlist, len(missing_indexes)):
            test_phrase = known_words[:]
            for idx, word in zip(missing_indexes, combo):
                test_phrase[idx] = word
            phrase = " ".join(test_phrase)
            tried += 1

            if mnemo.check(phrase):
                acct = Account.from_mnemonic(phrase)
                address = acct.address
                eth_balance = get_eth_balance(address)
                token_balances = {"ETH": eth_balance if eth_balance else 0.0}

                for token_name, contract in TOKENS.items():
                    bal = get_token_balance(address, contract)
                    token_balances[token_name] = bal if bal else 0.0

                btc_address = acct.address
                btc_balance = get_btc_balance(btc_address)

                yield f"\n✅ Wallet found:\n📥 Address: {address}\n🧠 Seed: {phrase}\n"
                yield f"💎 BTC: {btc_balance if btc_balance else 0.000000:.6f}\n"
                sorted_tokens = ["ETH", "USDT", "USDC", "DAI", "BNB", "LINK"]
                for token in sorted_tokens:
                    yield f"💎 {token}: {token_balances[token]:.6f}\n"

                yield "\n"
                found += 1

            if tried % 100 == 0:
                yield f"⏳ Đã thử {tried:,} tổ hợp...\n"

        if found == 0:
            yield "\n❌ Không tìm thấy ví hợp lệ nào.\n"
        else:
            yield f"\n🎉 Tổng cộng tìm được {found} ví hợp lệ.\n"

    return Response(stream_with_context(generate()), mimetype="text/plain")

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="🚫 Bạn đã vượt quá 5 lượt miễn phí hôm nay. Vui lòng nhập mã để tiếp tục."), 429

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
