# main.py
import socket
import threading
import os
import sys
import django



# phone,+989126672575,device_id,1,product_id,3
# set,+989126672575,1,2
# phone,+989126672575


# --------- بارگذاری محیط Django ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # /home/vend/vending-server/back-end
sys.path.append(os.path.join(BASE_DIR, "back"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "A.settings")
django.setup()

from home.models import Product, Device, RowData, TemproryData

HOST = "0.0.0.0"   # برای دسترسی از شبکه
PORT = 65432
MAX_GIFT = 2  # هدیه حداکثر که توی برنامه تعیین کردی



def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            parts = data.decode().strip().split(",")
            if not parts:
                continue

            command = parts[0].lower()

            # چک کردن شماره تلفن موقت
            if command == "phone" and len(parts) == 2:
                phone = parts[1]

                try:
                    temp_data = TemproryData.objects.get(phone_number=phone)
                    # اگر gift_number غیر صفر باشه یا رکورد موجود باشه
                    if temp_data.gift_number != 0:
                        conn.sendall("200,OK".encode())
                    else:
                        conn.sendall("200,OK".encode())  # رکورد وجود داره ولی gift_number صفر، باز هم 200 برگردون
                except TemproryData.DoesNotExist:
                    conn.sendall("204,Not Found".encode())

            # ثبت داده (شماره تلفن + دستگاه + محصول)
            elif command == "set" and len(parts) == 4:
                # داده: set,+989126672575,1,3
                phone = parts[1]
                try:
                    device_id = int(parts[2])
                    product_id = int(parts[3])
                except ValueError:
                    conn.sendall("400,Bad Request".encode())
                    continue

                # TemproryData
                temp_data, created = TemproryData.objects.get_or_create(
                    phone_number=phone,
                    defaults={'gift_number': MAX_GIFT - 1}
                )

                # اگر رکورد قبلا بوده و gift_number > 0
                if not created and temp_data.gift_number == 0:
                    # gift_number صفره → هیچ رکوردی ثبت نشود
                    conn.sendall("403,Gift Limit Reached".encode())
                    continue

                # کاهش gift_number و ذخیره
                if not created:
                    temp_data.gift_number = max(0, temp_data.gift_number - 1)
                    temp_data.save()

                # RowData فقط وقتی gift_number غیر صفره ساخته میشه
                try:
                    device = Device.objects.get(device_id=device_id)
                    product = Product.objects.get(product_id=product_id)

                    RowData.objects.create(
                        phone_number=phone,
                        device_id=device,
                        product_id=product
                    )
                    conn.sendall("200,OK".encode())

                except (Device.DoesNotExist, Product.DoesNotExist):
                    conn.sendall("404,Device/Product Not Found".encode())

            else:
                conn.sendall("400,Bad Request".encode())

    finally:
        conn.close()
        print(f"[CLOSED] Connection with {addr} closed.")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()


if __name__ == "__main__":
    start_server()
