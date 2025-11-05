# main_asyncio.py
import os
import sys
import django
import asyncio
from asgiref.sync import sync_to_async

# --------- بارگذاری محیط Django ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "back"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "A.settings")
django.setup()

from home.models import Product, Device, RowData, TemproryData

HOST = "0.0.0.0"
PORT = 65432
MAX_GIFT = 2  # حداکثر تعداد هدیه
# phone,+989126672575,device_id,1,product_id,3
# set,+989126672575,1,2
# phone,+989126672575

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[NEW CONNECTION] {addr} connected.")

    try:
        while True:
            data = await reader.readline()
            if not data:
                break

            message = data.decode().strip()
            if not message:
                continue

            parts = message.split(",")
            command = parts[0].lower()

            # --- phone ---
            if command == "phone" and len(parts) == 2:
                phone = parts[1]
                try:
                    temp_data = await sync_to_async(TemproryData.objects.get)(phone_number=phone)
                    if temp_data.gift_number > 0:
                        writer.write(b"200,OK\n")
                    else:
                        writer.write(b"403,Gift Limit Reached\n")
                    await writer.drain()
                except TemproryData.DoesNotExist:
                    # رکورد وجود ندارد → 200
                    writer.write(b"200,OK\n")
                    await writer.drain()

            # --- set ---
            elif command == "set" and len(parts) == 4:
                phone = parts[1]
                try:
                    device_id = int(parts[2])
                    product_id = int(parts[3])
                except ValueError:
                    writer.write(b"400,Bad Request\n")
                    await writer.drain()
                    continue

                # TemproryData
                temp_data, created = await sync_to_async(
                    TemproryData.objects.get_or_create
                )(phone_number=phone, defaults={'gift_number': MAX_GIFT - 1})

                if created:
                    # رکورد جدید → gift_number = MAX_GIFT -1 و ثبت RowData
                    try:
                        device = await sync_to_async(Device.objects.get)(device_id=device_id)
                        product = await sync_to_async(Product.objects.get)(product_id=product_id)
                        await sync_to_async(RowData.objects.create)(
                            phone_number=phone,
                            device_id=device,
                            product_id=product
                        )
                        writer.write(b"200,OK\n")
                        await writer.drain()
                    except (Device.DoesNotExist, Product.DoesNotExist):
                        writer.write(b"404,Device/Product Not Found\n")
                        await writer.drain()
                    continue

                # رکورد موجود
                if temp_data.gift_number == 0:
                    # gift_number صفر → RowData ثبت نشود
                    writer.write(b"403,Gift Limit Reached\n")
                    await writer.drain()
                    continue

                # gift_number > 0 → کاهش و ثبت RowData
                temp_data.gift_number = max(0, temp_data.gift_number - 1)
                await sync_to_async(temp_data.save)()

                try:
                    device = await sync_to_async(Device.objects.get)(device_id=device_id)
                    product = await sync_to_async(Product.objects.get)(product_id=product_id)
                    await sync_to_async(RowData.objects.create)(
                        phone_number=phone,
                        device_id=device,
                        product_id=product
                    )
                    writer.write(b"200,OK\n")
                    await writer.drain()
                except (Device.DoesNotExist, Product.DoesNotExist):
                    writer.write(b"404,Device/Product Not Found\n")
                    await writer.drain()

            else:
                writer.write(b"400,Bad Request\n")
                await writer.drain()

    except Exception as e:
        print(f"[ERROR] {addr} -> {e}")

    finally:
        writer.close()
        await writer.wait_closed()
        print(f"[CLOSED] Connection with {addr} closed.")


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addr = server.sockets[0].getsockname()
    print(f"[LISTENING] Server is listening on {addr}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
