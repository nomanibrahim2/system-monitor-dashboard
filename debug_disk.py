import psutil

print("Partitions:")
try:
    partitions = psutil.disk_partitions()
    for p in partitions:
        print(f"  Device: {p.device}, Mount: {p.mountpoint}, FSType: {p.fstype}")
        try:
            usage = psutil.disk_usage(p.mountpoint)
            print(f"    Total: {usage.total}, Used: {usage.used}, Free: {usage.free}, Percent: {usage.percent}")
        except Exception as e:
            print(f"    Error getting usage: {e}")
except Exception as e:
    print(f"Error getting partitions: {e}")
