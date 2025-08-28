# owner @zproject2
# channel @zproject3

import requests
from datetime import datetime
from rich.console import Console
import sys
import concurrent.futures
import threading

console = Console()

APIBYZPROJECTX = "https://zpxdev.site/config.php"

ZPXDEVSITE = "login"
ANHYEUEM = "get_friends"
ANHNHOEMQUA = "delete_friend"

TOITHIEU = 20
TOIDA = 500

TIMEOUTT = 120 

UIDOKNHA = 300 

def log(message: str, level: str = "info"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{now}] "
    console.print(prefix + message)

def make_api_request(action: str, params: dict) -> dict:
    full_params = {"action": action, **params}
    try:
        if action == ZPXDEVSITE or action == ANHNHOEMQUA:
            response = requests.post(APIBYZPROJECTX, params=full_params, timeout=TIMEOUTT)
        else:
            response = requests.get(APIBYZPROJECTX, params=full_params, timeout=TIMEOUTT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        log(f"Lỗi timeout khi gọi API '{action}': Yêu cầu không phản hồi trong {REQUEST_TIMEOUT_TIMEOUT_SECONDS} giây.")
        return {"error": f"Request to {action} timed out after {TIMEOUTT} seconds."}
    except requests.exceptions.RequestException as e:
        log(f"Lỗi khi gọi API '{action}': {e}")
        return {"error": str(e)}

def login(email: str, password: str) -> tuple[str | None, str | None]:
    log("Login..")
    data = make_api_request(ZPXDEVSITE, {"email": email, "password": password})

    if "result" in data and "idToken" in data["result"]:
        user = data["result"]
        log("Login Account Success")
        log(f"Name: {user.get('displayName', 'N/A')}")
        log(f"Email: {user.get('email', 'N/A')}")
        log(f"Local ID: {user.get('localId', 'N/A')}")
        return user["idToken"], user["localId"]
    else:
        log(f"Login thất bại: {data.get('error', data)}")
        return None, None

def get_friends(id_token: str, local_id: str) -> list[str]:
    log("Đang lấy danh sách bạn bè...")
    all_unique_uids = set() 
    page = 1
    
    while True:
        params = {
            "id_token": id_token,
            "local_id": local_id,
            "page": page,   
            "limit": UIDOKNHA 
        }
        data = make_api_request(ANHYEUEM, params)
        
        if "result" in data and "uids" in data["result"]:
            current_page_uids = data["result"]["uids"]
            
            if not current_page_uids:
                log(f"Không còn UID nào từ trang {page}. Dừng lấy.")
                break 
            
            previous_unique_count = len(all_unique_uids)
            all_unique_uids.update(current_page_uids) 

            if len(current_page_uids) < UIDOKNHA:
                log(f"Page {page}  Có ít {UIDOKNHA} nên dừng .")
                break

            if len(all_unique_uids) == previous_unique_count:
                log(f"Trang {page} đầy đủ ({UIDOKNHA} UID) nhưng không có UID mới nào được phát hiện. Dừng lấy để tránh lặp vô hạn.")
                break
            
            page += 1
        else:
            log(f"Không thể lấy danh sách bạn bè từ trang {page}: {data.get('error', data)}. Dừng lấy.")
            break 
            
    return list(all_unique_uids)

def delete_single_friend(id_token: str, uid: str) -> dict:
    return make_api_request(ANHNHOEMQUA, {"id_token": id_token, "uid": uid})

def delete_single_friend_threaded(id_token: str, uid: str) -> tuple[str, bool, dict]:
    res = make_api_request(ANHNHOEMQUA, {"id_token": id_token, "uid": uid})
    
    is_success = res.get("success") == True or \
                 res.get("message") == "Friend deleted successfully" or \
                 (res.get("owner") == "@zproject2" and res.get("result", {}).get("data") is None)
    
    return uid, is_success, res

def display_menu() -> str:
    print("\n--- MENU ---")
    print("1. Xóa tất cả")
    print("2. Xóa theo số lượng")
    print("3. Xóa 1 UID cụ thể")
    print("4. Thoát")
    choice = input("Chọn chức năng (1/2/3/4): ").strip()
    return choice

def get_num_threads_from_user() -> int:
    while True:
        try:
            num_threads_str = input(f"Nhập số luồng cần dùng (tối thiểu {TOITHIEU}, tối đa {TOIDA}): ").strip()
            num_threads = int(num_threads_str)
            if TOITHIEU <= num_threads <= TOIDA:
                return num_threads
            else:
                log(f"Số luồng không hợp lệ. Vui lòng nhập số từ {TOITHIEU} đến {TOIDA}.")
        except ValueError:
            log("Số Không Hợp Lệ Ạ.")
            return 0 

def handle_multi_threaded_deletion(id_token: str, uids_to_delete: list[str]) -> int:
    deleted_count = 0
    num_threads = get_num_threads_from_user()
    
    if num_threads == 0: 
        return 0

    log(f"Bắt đầu xóa {len(uids_to_delete)} UID với {num_threads} luồng")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_uid = {
            executor.submit(delete_single_friend_threaded, id_token, uid): uid
            for uid in uids_to_delete
        }

        for future in concurrent.futures.as_completed(future_to_uid):
            uid = future_to_uid[future]
            try:
                deleted_uid, is_success, res = future.result()
                if is_success:
                    log(f"Xóa {deleted_uid} thành công.")
                    deleted_count += 1
                else:
                    log(f"Không thể xóa {deleted_uid}: {res.get('error', res)}")
            except Exception as exc:
                log(f"UID {uid} gặp lỗi khi xóa: {exc}")
    
    return deleted_count

def handle_delete_all_friends(id_token: str, uids: list[str]) -> int:
    return handle_multi_threaded_deletion(id_token, uids)

def handle_delete_n_friends(id_token: str, uids: list[str]) -> int:
    try:
        n_str = input(f"Nhập số lượng UID cần xóa (tối đa {len(uids)}): ").strip()
        n = int(n_str)
        
        if not 0 < n <= len(uids):
            log(f"Số lượng không hợp lệ. Vui lòng nhập số từ 1 đến {len(uids)}.")
            return 0
        
        uids_to_delete = uids[:n]
        return handle_multi_threaded_deletion(id_token, uids_to_delete)
    except ValueError:
        log("Số Không Hợp Lệ Ạ.")
        return 0

def handle_delete_specific_friend(id_token: str, uids: list[str]) -> int:
    deleted_count = 0
    uid_to_delete = input("Nhập UID cụ thể cần xóa: ").strip()
    if not uid_to_delete:
        log("UID không được để trống.")
        return 0

    if uid_to_delete in uids:
        log(f"Đang xóa UID {uid_to_delete}")
        res = delete_single_friend(id_token, uid_to_delete)
        if res.get("success") == True or \
           res.get("message") == "Friend deleted successfully" or \
           (res.get("owner") == "@zproject2" and res.get("result", {}).get("data") is None):
            log(f"Xóa {uid_to_delete} thành công")
            deleted_count += 1
        else:
            log(f"Không thể xóa {uid_to_delete}: {res.get('error', res)}")
    else:
        log(f"UID '{uid_to_delete}' không có trong danh sách bạn bè hiện tại hoặc không hợp lệ")
    return deleted_count

def main():
    log("Tool Xoa Kb Locket | Owner @zproject2 ")
    
    if len(sys.argv) != 3:
        script_name = sys.argv[0].split('/')[-1].split('\\')[-1]
        print(f"Cách dùng: python {script_name} <email> <mật_khẩu>")
        print(f"Ví dụ: python {script_name} zproject.vn@gmail.com 12345678")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    log(f"Đang Login Vào Acc : Email={email}, Mật khẩu=******")

    id_token, local_id = login(email, password)
    if not id_token:
        sys.exit(1)

    uids = get_friends(id_token, local_id)
    if not uids:
        log("Không có yêu cầu kết bạn nào.")
        sys.exit(0)

    log(f"List Friend ({len(uids)}): {uids}")
    
    while True:
        choice = display_menu()
        deleted_count = 0

        if choice == "1":
            deleted_count = handle_delete_all_friends(id_token, uids)
        elif choice == "2":
            deleted_count = handle_delete_n_friends(id_token, uids)
        elif choice == "3":
            deleted_count = handle_delete_specific_friend(id_token, uids)
        elif choice == "4":
            log("Stop!")
            break
        else:
            log("Lựa chọn không hợp lệ. Vui lòng chọn lại.")

        if deleted_count > 0:
            log(f"Tổng UID đã xóa: {deleted_count}")
            log("Thao tác xóa hoàn tất. Tự động thoát công cụ.")
            sys.exit(0) 
        elif choice in ["1", "2", "3"]:
            log("Không có UID nào được xóa.")

if __name__ == "__main__":
    main()