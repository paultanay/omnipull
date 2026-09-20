import sys, os
sys.path.insert(0, "C:/Users/pault/Desktop/Projects/OmniPull/backend")
from utils import _get_cookie_opts
opts = _get_cookie_opts()
print("Cookie opts:", opts)
if "cookiesfrombrowser" in opts:
    print("SUCCESS: Will use browser:", opts["cookiesfrombrowser"][0])
elif "cookiefile" in opts:
    print("SUCCESS: Will use cookie file:", opts["cookiefile"])
else:
    print("INFO: No cookies found yet - run start.ps1 after logging into YouTube in your browser")