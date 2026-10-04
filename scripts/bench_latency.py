import json, time, urllib.request, statistics

URL = "http://127.0.0.1:8009/v1/systemone"

def ask(state, questions):
    body = json.dumps({"state": state, "model": "kev-latest", "questions": questions}).encode()
    req = urllib.request.Request(URL, data=body, headers={"content-type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    return (time.perf_counter() - t0) * 1000, resp

def stats(name, times):
    print(f"{name}: n={len(times)} median={statistics.median(times):.0f}ms min={min(times):.0f}ms max={max(times):.0f}ms")

short_state = "Shoes arrived two weeks late and in the wrong size. Also I see two charges on my card."
short_q = {
    "department":  {"type": "choice", "instructions": "Which team should handle this?",
                    "criteria": {"returns": "Exchanges, refunds, wrong or damaged items",
                                 "shipping": "Delivery status, delays, lost packages",
                                 "billing": "Charges, invoices, payment problems"}},
    "escalate":    {"type": "noul",  "instructions": "Does this need urgent human attention?"},
    "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                    "criteria": ["Calm", "Frustrated", "Very angry"]},
}

# ~2.4k token document: a fictional company policy (60 paragraphs x 10 clauses)
paras = []
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
for i in range(6):
    for j, t in enumerate(topics):
        paras.append(f"{i+1}.{j+1} {t} This clause has been reviewed by our legal team and applies unless otherwise noted in the order confirmation email sent at checkout.")
long_state = "\n".join(paras)
long_q = {
    "refund_ok": {"type": "noul", "instructions": "Can a customer get a refund for an item bought in store 60 days ago with receipt?"},
    "final_sale": {"type": "noul", "instructions": "Are final sale items exchangeable?"},
    "class": {"type": "choice", "instructions": "Which type of document is this?",
              "criteria": {"contract": "A binding legal contract", "policy": "A company policy document", "invoice": "A billing document"}},
}

# warmup (first call loads + warms caches)
ask(short_state, short_q)

t_short = [ask(short_state, short_q)[0] for _ in range(6)]
stats("short state (3 domande)", t_short)

t_long = [ask(long_state, long_q)[0] for _ in range(4)]
stats("long state ~2.4k tok (3 domande)", t_long)

# cache test: same state, different question
t1, r1 = ask(long_state, {"only_q": {"type": "noul", "instructions": "Is a 30 day return possible?"}})
t2, r2 = ask(long_state, {"only_q": {"type": "noul", "instructions": "Are shipping costs refundable?"}})
print(f"cache test: first={t1:.0f}ms second={t2:.0f}ms (speedup {t1/t2:.1f}x)")
print("answer sample:", json.dumps(r1.get("answers", {}), ensure_ascii=False)[:200])
print("usage:", r1.get("usage"), "server latency_ms:", r1.get("latency_ms"))