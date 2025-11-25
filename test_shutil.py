import shutil

try:
    usage = shutil.disk_usage("C:\\")
    print(f"Total: {usage.total}, Used: {usage.used}, Free: {usage.free}")
except Exception as e:
    print(f"Error: {e}")
