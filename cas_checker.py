import requests
import json
from config import CAS_API_URL

class CASChecker:
    @staticmethod
    def is_banned(user_id):
        """
        Check if a user is banned in the CAS database
        
        Args:
            user_id (int): Telegram user ID
            
        Returns:
            bool: True if user is banned, False otherwise
        """
        try:
            print(f"Checking CAS for user {user_id}...")
            response = requests.get(f"{CAS_API_URL}{user_id}")
            print(f"CAS API response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"CAS API response: {data}")
                    
                    # Если API вернул ok=true, пользователь в черном списке CAS
                    if data.get('ok', False):
                        print(f"User {user_id} IS banned in CAS")
                        return True
                    else:
                        # Если API вернул ошибку "Record not found", пользователь не в черном списке
                        if data.get('error', '') == 'Record not found.':
                            print(f"User {user_id} is NOT banned in CAS (record not found)")
                        else:
                            print(f"User {user_id} not in CAS. API returned: {data}")
                        return False
                except json.JSONDecodeError:
                    print(f"Invalid JSON response from CAS API: {response.text}")
                    return False
            else:
                print(f"CAS API error: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            print(f"Error checking CAS for user {user_id}: {e}")
            return False  # Default to not banned in case of errors 