import urllib.request

html = urllib.request.urlopen("http://127.0.0.1:8000/").read().decode("utf-8")
if "ai-sidebar" in html:
    print("Found ai-sidebar in home")
else:
    print("No ai-sidebar in home")
