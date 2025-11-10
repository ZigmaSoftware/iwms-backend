import time
import random

def generate_unique_id(prefix: str = "") -> str:
    """
    Mimics PHP's uniqid() . rand(10000, 99999)
    Example: '652b8df64c6b310345' or with prefix 'EMP652b8df64c6b310345'
    """
    # PHP uniqid() uses current time in microseconds, hex-encoded
    unique_part = hex(int(time.time() * 1000000))[2:]  # strip '0x'
    random_part = str(random.randint(10000, 99999))
    return f"{prefix}{unique_part}{random_part}"
