import sys
import logging
sys.path.insert(0, '.')
logging.basicConfig(level=logging.INFO)

from modules.proxy_manager import get_working_proxy

print("Calling get_working_proxy()...")
res = get_working_proxy()
print("Final Result:", res)
