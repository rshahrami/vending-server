# main_asyncio.py
import os
import sys
import django
import asyncio
import time
from asgiref.sync import sync_to_async
from django.db import transaction, IntegrityError
from django.db.models import F

from datetime import datetime, timedelta, timezone

# --------- بارگذاری محیط Django ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "back"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "A.settings")
django.setup()

from home.models import Product, Device, RowData, TemproryData  # noqa

HOST = "0.0.0.0"
PORT = 9224
MAX_GIFT = 2          # حداکثر تعداد هدیه
CACHE_TTL = 24 * 3600 # ثانیه: 24 ساعت


ID_PING = "ping"
ID_GET = "1"
ID_POST = "2"

# ------------------ کش درون‌پروسه ------------------
DEVICE_IDS = set()
PRODUCT_IDS = set()
_CACHE_LOCK = asyncio.Lock()
_last_refresh = 0.0


IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def ts() -> str:
    # 
    return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

@sync_to_async
def _fetch_all_ids():
    device_ids = list(Device.objects.values_list('device_id', flat=True))
    product_ids = list(Product.objects.values_list('product_id', flat=True))
    return device_ids, product_ids

async def refresh_cache(force: bool = False):
    global _last_refresh
    now = time.time()
    if (not force) and (now - _last_refresh < CACHE_TTL):
        return
    async with _CACHE_LOCK:
        if (not force) and (time.time() - _last_refresh < CACHE_TTL):
            return
        try:
            devs, prods = await _fetch_all_ids()
            DEVICE_IDS.clear(); DEVICE_IDS.update(devs)
            PRODUCT_IDS.clear(); PRODUCT_IDS.update(prods)
            _last_refresh = time.time()
            print(f"[{ts()}] [CACHE] Refreshed: {len(DEVICE_IDS)} devices, {len(PRODUCT_IDS)} products")
        except Exception as e:
            print(f"[{ts()}] [CACHE] Refresh failed: {e}")

@sync_to_async
def _exists_device(device_id: int) -> bool:
    return Device.objects.filter(device_id=device_id).exists()

@sync_to_async
def _exists_product(product_id: int) -> bool:
    return Product.objects.filter(product_id=product_id).exists()

async def ensure_device_in_cache(device_id: int) -> bool:
    if device_id in DEVICE_IDS:
        return True
    await refresh_cache()
    if device_id in DEVICE_IDS:
        return True
    if await _exists_device(device_id):
        async with _CACHE_LOCK:
            DEVICE_IDS.add(device_id)
        return True
    return False

async def ensure_product_in_cache(product_id: int) -> bool:
    if product_id in PRODUCT_IDS:
        return True
    await refresh_cache()
    if product_id in PRODUCT_IDS:
        return True
    if await _exists_product(product_id):
        async with _CACHE_LOCK:
            PRODUCT_IDS.add(product_id)
        return True
    return False

# ------------------ Helper sync funcs (منطق شما + رفع ابهام) ------------------

def _get_temp(phone: str):
    return TemproryData.objects.get(phone_number=phone)

def _get_or_create_temp(phone: str):
    # همان منطق شما: created ⇒ gift_number = MAX_GIFT - 1
    return TemproryData.objects.get_or_create(
        phone_number=phone, defaults={'gift_number': MAX_GIFT - 1}
    )

def _consume_quota_atomic(temp_pk: int) -> tuple[bool, int]:
    """
    اتمی و ضد ریس:
    - اگر سهمیه <= 0 بود: مصرف نمی‌شود ⇒ (False, current)
    - اگر سهمیه > 0 بود: یک واحد کم می‌شود ⇒ (True, new_value)
      *ممکن است new_value == 0 باشد (مجاز!)*

    برمی‌گرداند: (consumed, remaining_after)
    """
    with transaction.atomic():
        t = TemproryData.objects.select_for_update().get(pk=temp_pk)
        if t.gift_number <= 0:
            return False, t.gift_number
        TemproryData.objects.filter(pk=t.pk).update(gift_number=F('gift_number') - 1)
        t.refresh_from_db(fields=['gift_number'])
        return True, t.gift_number

def _has_quota_sync(phone: str) -> bool:
    try:
        t = TemproryData.objects.get(phone_number=phone)
        return t.gift_number > 0
    except TemproryData.DoesNotExist:
        return True

# ------------------ Async TCP Server ------------------

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    print(f"[{ts()}] [NEW CONNECTION] {addr} connected.")

    try:
        while True:
            data = await reader.readline()
            if not data:
                break

            message = data.decode(errors='ignore').strip()
            if not message:
                continue

            parts = message.split(",")
            command = parts[0].lower()

            
            # --- PING ---
            if command == "ping" and len(parts) == 2:
                dev_id_str = parts[1].strip()     # اگر "ping, 5" بود
                print(f"[{ts()}] [INFO] [PING] from {addr} ")
                try:
                    dev_id = int(dev_id_str)
                except ValueError:
                    # فرمت اشتباه => طبق خواسته‌ات هیچ پاسخی نده
                    continue

                valid = await ensure_device_in_cache(dev_id)
                if valid:
                    writer.write(b"pong\r\n")      # بهتره CRLF برای کلاینت‌های سریالی
                    await writer.drain()
                # اگر معتبر نبود، عمداً هیچ پاسخی نده
                continue

            # --- GET-like ---
            if command == ID_GET and len(parts) == 2:
                phone = parts[1]
                print(f"[{ts()}] [INFO] [GET] {phone} from {addr} ")
                try:
                    ok = await sync_to_async(_has_quota_sync)(phone)
                    writer.write(b"200\n" if ok else b"403\n")
                    # print(f"[{ts()}] [INFO] [GET] {phone} from {addr} -status 200 ")
                    await writer.drain()
                except Exception:
                    writer.write(b"400\n")
                    print(f"[{ts()}] [INFO] [GET] {phone} from {addr} -status 400 ")
                    await writer.drain()

            # --- POST-like ---
            elif command == ID_POST and len(parts) == 4:
                phone = parts[1]
                print(f"[{ts()}] [INFO] [POST] {phone} from {addr} ")
                try:
                    device_id = int(parts[2])
                    product_id = int(parts[3])
                except ValueError:
                    writer.write(b"400\n")
                    print(f"[{ts()}] [INFO] [POST] {phone} from {addr} -status 400 ")
                    await writer.drain()
                    continue

                # TemproryData: عین منطق شما
                try:
                    temp_data, created = await sync_to_async(_get_or_create_temp)(phone)
                except IntegrityError:
                    temp_data = await sync_to_async(_get_temp)(phone)
                    created = False

                if created:
                    # created ⇒ gift_number = MAX_GIFT - 1 (بدون کم‌کردن)
                    dev_ok = await ensure_device_in_cache(device_id)
                    prod_ok = await ensure_product_in_cache(product_id)
                    if not (dev_ok and prod_ok):
                        writer.write(b"404\n")
                        print(f"[{ts()}] [INFO] [POST] {phone} from {addr} -status 404 ")
                        await writer.drain()
                        continue

                    try:
                        await sync_to_async(RowData.objects.create)(
                            phone_number=phone,
                            device_id_id=device_id,
                            product_id_id=product_id,
                        )
                        writer.write(b"200\n")
                        print(f"[{ts()}] [INFO] [POST] {phone} from {addr} -status 200 ")
                        await writer.drain()
                    except Exception:
                        writer.write(b"400\n")
                        print(f"[{ts()}] [INFO] [POST] {phone} from {addr} -status 400 ")
                        await writer.drain()
                    continue

                # existing ⇒ باید یک واحد مصرف کنیم؛
                # توجه: دیگر از temp_data.gift_number برای تصمیم نهایی استفاده نمی‌کنیم
                # چون مبهم و ریس‌پذیر است. فقط به نتیجه‌ی اتمی تکیه می‌کنیم.
                try:
                    consumed, remaining = await sync_to_async(_consume_quota_atomic)(temp_data.pk)
                except Exception:
                    writer.write(b"400\n")
                    await writer.drain()
                    continue

                if not consumed:
                    # سهمیه از قبل صفر بوده
                    writer.write(b"403\n")
                    await writer.drain()
                    continue

                # اینجا حتی اگر remaining == 0 باشد، یعنی همین درخواست مجاز بوده و مصرف شده
                dev_ok = await ensure_device_in_cache(device_id)
                prod_ok = await ensure_product_in_cache(product_id)
                if not (dev_ok and prod_ok):
                    # طبق منطق شما: جبران نمی‌کنیم
                    writer.write(b"404\n")
                    await writer.drain()
                    continue

                try:
                    await sync_to_async(RowData.objects.create)(
                        phone_number=phone,
                        device_id_id=device_id,
                        product_id_id=product_id,
                    )
                    writer.write(b"200\n")
                    await writer.drain()
                except Exception:
                    writer.write(b"400\n")
                    await writer.drain()

            else:
                writer.write(b"400\n")
                await writer.drain()

    except Exception as e:
        print(f"[{ts()}] [ERROR] {addr} -> {e}")

    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionResetError, OSError):
            print(f"[{ts()}] [WARN] Connection with {addr} closed unexpectedly.")
        print(f"[{ts()}] [CLOSED] Connection with {addr} closed.")

# ریفرش خودکار کش هر 24 ساعت
async def _cache_refresher():
    await refresh_cache(force=True)
    while True:
        await asyncio.sleep(CACHE_TTL)
        await refresh_cache(force=True)

async def main():
    asyncio.create_task(_cache_refresher())
    #server = await asyncio.start_server(handle_client, HOST, PORT)
    server = await asyncio.start_server(handle_client, HOST, PORT, backlog=512)
    addr = server.sockets[0].getsockname()
    print(f"[{ts()}] [LISTENING] Server is listening on {addr}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
