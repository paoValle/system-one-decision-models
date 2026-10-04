import json, time, urllib.request, statistics, threading

URL = "http://127.0.0.1:8009/v1/systemone"

def ask(state, questions):
    body = json.dumps({"state": state, "model": "kev-latest", "questions": questions}).encode()
    req = urllib.request.Request(URL, data=body, headers={"content-type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    return (time.perf_counter() - t0) * 1000, resp

topics = ["The return policy applies to all items purchased online or in store.",
          "Customers may return items within 90 days of purchase with a receipt.",
          "Items must be unused and in original packaging to qualify for a refund.",
          "Shipping costs are not refundable unless the error was ours.",
          "Refunds are issued to the original payment method within 5 business days.",
          "Exchanges are processed free of charge for defective items.",
          "Gift receipts allow store credit only and cannot be converted to cash.",
          "Items marked final sale cannot be returned or exchanged.",
          "International orders follow a separate policy described in section 12.",
          "We reserve the right to refuse returns that show signs of wear."]

def doc(iters):
    paras = []
    for i in range(iters):
        for j, t in enumerate(topics):
            paras.append(f"{i+1}.{j+1} {t} This clause has been reviewed by our legal team and applies unless otherwise noted in the order confirmation email sent at checkout.")
    return "\n".join(paras)

q = {"ok": {"type": "noul", "instructions": "Is a 60-day store return with receipt allowed?"}}

# 7k-token ceiling test, single shot
state7k = doc(18)
t0 = time.perf_counter()
try:
    _, r = ask(state7k, q)
    print(f"7k-token doc: {(time.perf_counter()-t0)*1000:.0f}ms tokens={r.get('usage')}")
except Exception as e:
    print(f"7k-token doc: FAILED ({e}) after {(time.perf_counter()-t0)*1000:.0f}ms")

# concurrency: 8 threads x 8 short requests
short_state = "Shoes arrived two weeks late and in the wrong size. Also I see two charges on my card."
short_q = {
    "department":  {"type": "choice", "instructions": "Which team should handle this?",
                    "criteria": {"returns": "Exchanges, refunds, wrong or damaged items",
                                 "shipping": "Delivery status, delays, lost packages",
                                 "billing": "Charges, invoices, payment problems"}},
    "escalate":    {"type": "noul",  "instructions": "Does this need urgent human attention?"},
}
times = []
lock = threading.Lock()
def worker():
    for _ in range(8):
        ms, _ = ask(short_state, short_q)
        with lock:
            times.append(ms)
t0 = time.perf_counter()
threads = [threading.Thread(target=worker) for _ in range(8)]
for t in threads: t.start()
for t in threads: t.join()
wall = time.perf_counter() - t0
n = len(times)
print(f"concurrency 8x8 short: {n} req in {wall:.1f}s = {n/wall:.1f} req/s, median {statistics.median(times):.0f}ms, p90 {sorted(times)[int(n*0.9)-1]:.0f}ms")