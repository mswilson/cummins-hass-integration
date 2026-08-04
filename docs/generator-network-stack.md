# Notes on the Generator's Network Stack

Field-collected notes on why the generator's embedded web server
becomes unresponsive under otherwise reasonable HTTP polling, and the
constraints that shape this integration's polling strategy. Written
for developers who want to change how the integration talks to the
generator without regressing stability.

## TL;DR

The generator runs **InterNiche Technologies TCP/IP 2.0** (circa
2004). It has a small fixed pool of packet buffers, closes every
HTTP connection with `Connection: Close`, and holds each closed TCB
in `TIME_WAIT` for 60 seconds. Under our old polling pattern (four
back-to-back requests every 30 s at 500 ms spacing) it took roughly
20 minutes for the TCB / packet-buffer pool to deplete, at which
point body sends silently fail (client sees a read timeout), then
new SYNs are silently dropped (client sees connect-refuse), and the
box wedges indefinitely. Recovery requires a power cycle.

This is not a known CVE. It is straightforward resource
under-provisioning in the 2.x stack combined with a client that was
firing requests faster than the stack could recycle state.

## The concrete hang, from a real capture

On 2026-08-01 15:23:42, in the middle of a 20-minute run of clean
30 s polling with debug logging on:

1. `/exercise.html` fetch times out after 10 s. Traceback bottoms
   in `aiohttp/streams.py: _wait("readany")` — the TCP connection
   is established, the request was accepted, but the body never
   arrived.
2. Over the next ~8 minutes, some fetches succeed (slowly, 10–20 s),
   most fail on body read.
3. From roughly 15:32 onward, every request completes in ~3.6 s with
   `CancelledError` raised inside `session.get()`'s context enter.
   That's the signature of TCP connect never completing — no SYN/ACK.
4. The controller stays wedged. An HA restart at 00:09 fails to
   connect at all. First successful request is at 09:54 the next
   morning after a power cycle.

Two-phase failure — body-read timeouts, then connect refuse — is the
key signal. It tells us the stack is running out of TX-side buffers
first, then losing the ability to accept new connections at all.

## What we found in the InterNiche 2.0 source

We pulled a mirror of the InterNiche 2.0 tree (paths cited below are
relative to that tree) and confirmed the resource constraints:

| Resource | Value | Location |
|---|---:|---|
| Big packet buffers (1536 B) | 30 | `src/h/nios2/ipport.h` (`NUMBIGBUFS`) |
| Little packet buffers (200 B) | 30 | `src/h/nios2/ipport.h` (`NUMLILBUFS`) |
| mbuf pool (`mfreeq`) | `(30 + 30) × 2 + 3 = 123` | `src/tcp/nptcp.c` (see `tcpinit`) |
| Listen backlog per socket | `SOMAXCONN = 5`, effective cap `⌊3 × qlimit / 2⌋ = 7` | `src/h/socket.h`, `src/tcp/socket2.c` (`sonewconn`) |
| `TCPTV_MSL` (default) | 30 × `PR_SLOWHZ` = 15 s → `2 × MSL = 60 s` TIME_WAIT | `src/tcp/nptcp.c` |
| `PR_SLOWHZ` | 2 ticks/s | `src/h/nptcp.h` |
| FIN_WAIT_2 timeout | `tcp_maxidle = TCPTV_KEEPCNT × tcp_keepintvl = 8 × 75 × 0.5 s = 300 s` | `src/tcp/tcp_timr.c` |
| Send/receive window per TCB | 8 KB / 8 KB | `src/tcp/tcp_usr.c` (`tcp_sendspace`, `tcp_recvspace`) |
| PCB/TCB allocation | Heap via `calloc` + mutex (`npalloc`), no fixed pool | `src/nios2/targnios.c` |

Two silent-failure paths matter for us:

- `pk_alloc(len)` returns **NULL** when both `bigfreeq` and
  `lilfreeq` are empty. Callers include `tcp_pktalloc()`, which is
  used to build outgoing TCP segments. On NULL, the segment is
  simply not built. The response body never leaves the box.
  Comment from the stack's own source (paraphrasing
  `src/tcp/tcp_out.c` around the `ENOBUFS` return): *"this can
  happen when we run out of mbufs or pkt buffers … One solution is
  to increase them."*
- `sonewconn(head)` silently rejects new SYNs when
  `head->so_qlen + head->so_q0len > 3 × head->so_qlimit / 2`. With
  `SOMAXCONN = 5` that cap is 7. Rejection is a bare drop, not a
  RST — the client just retransmits SYN until it gives up.

Neither failure surfaces at the HTTP layer. The client sees only
"timeout" or "connection refused."

## How our old traffic pattern interacted with those limits

Wire capture (see `tcpdump` output from an earlier debugging pass)
shows every request cycle looks like:

```
client -> generator  SYN
generator -> client  SYN/ACK
client -> generator  ACK, GET /path HTTP/1.1  (with keep-alive implicit)
generator -> client  HTTP/1.1 200 OK, Connection: Close, ... body ...
generator -> client  FIN            <-- server initiates close
client -> generator  ACK, FIN
generator -> client  ACK
```

The generator responds with `Connection: Close` on every request and
initiates the FIN. Consequences:

- **The generator's TCB, not the client's, holds the state.** Its
  TCB goes `ESTABLISHED → FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT` and
  stays in TIME_WAIT for **60 seconds**.
- **HTTP keep-alive doesn't happen.** The server is closing anyway,
  so aiohttp's connection pool never reuses anything for this host.
  Each fetch is a fresh three-way handshake and a fresh
  server-side TCB.

Old polling pattern:

- `sensor` coordinator: `/index_data.html` every 30 s (1 request)
- `select` coordinator: `/loads.html` + `/loads_data.html` +
  `/exercise.html` every 30 s (3 requests, 500 ms apart)

Total: **4 requests per 30 s**, i.e. one every ~7.5 seconds on
average. Each leaves one TCB in TIME_WAIT for 60 s.

Steady-state TCB count on the generator: **~8** in TIME_WAIT. The
listen-queue cap is **7**. We were living on the edge, and any
hiccup — a slow response that delayed the FIN, a retransmit, a
buffer temporarily held longer than expected — pushed us over.
Once we started dropping SYNs, request timeouts stacked further
buffer use, and the failure cascaded.

## What we changed, and why

### 1. Explicit connection close

We now send `Connection: close` on every request and configure
aiohttp with `TCPConnector(force_close=True)`. Rationale: the
generator was already closing every connection, but aiohttp was
silently maintaining a keep-alive pool that never got any reuse.
Being explicit removes any ambiguity in the client's connection
management and matches the server's actual behavior.

### 2. `Accept-Encoding: identity`

Old requests advertised `Accept-Encoding: gzip, deflate, br`. The
`br` (Brotli) token postdates the InterNiche 2.0 stack by roughly a
decade. `CVE-2021-27565` documents an infinite-loop trigger in the
NicheStack HTTP server when it receives valid-but-unrecognized
inputs (the reported example is `OPTIONS`). We haven't been able to
prove that an unknown `Accept-Encoding` token trips a similar hook,
but there's no upside to sending it — the generator has never
gzipped a response — and there's a plausible-enough downside to
sending it that we don't.

### 3. Round-robin the load coordinator

The `select` coordinator used to fetch three endpoints back-to-back
every 30 s. Now it fetches **one** endpoint per tick with a 100 s
interval, cycling through `loads_data.html → loads.html →
exercise.html`. Each endpoint sees a fresh read every ~5 min.
Writes still trigger a targeted refresh of the specific endpoint
that changed, so responsive UI is preserved on user action.

### 4. Default `min_request_gap_ms = 2000` (was 500)

At the network-stack level, 500 ms is well inside every relevant
timer (MSL, keep-interval, persist-min are all seconds). It only
serialized aiohttp's own send order. Bumping to 2 s gives the
stack time to complete the FIN handshake, drain TIME_WAIT of at
least one entry, and reclaim its buffers between the times we do
fire consecutive requests.

The setting remains user-tunable through the options flow.

### Result: steady-state pressure

| Metric | Before | After |
|---|---:|---:|
| Requests per 30 s cycle | 4 | 1 (sensor) + ≤0.3 (load, 1 per 100 s) |
| Total requests / minute | ~8 | ~2.6 |
| TCBs in TIME_WAIT (steady) | ~8 | ~2.6 |
| Listen-queue headroom (cap 7) | ~0 | ~4.4 |

## Things we ruled out along the way

- **INFRA:HALT (14 CVEs, Forescout 2021).** All 14 need a
  malformed packet. Our traffic is well-formed HTTP GET. The
  research targeted NicheStack 3.x/4.x; 2.0 wasn't audited.
- **CVE-2021-27565 (unexpected valid HTTP method → infinite loop).**
  Fires on the *first* offending request. We had 20+ minutes of
  clean polling before symptoms. aiohttp's default headers on a
  `GET` don't include `OPTIONS` or other unknown methods.
- **Malicious traffic or auth issues.** No 401s, no config changes,
  no writes from us in the pre-failure window.

## If you're changing this code, keep these in mind

- **Never fire concurrent requests to this generator.** The
  `GeneratorClient` uses a single `asyncio.Lock` around request
  send + wait so that only one request is ever in flight from us
  at a time. Both coordinators depend on this; don't work around it.
- **Assume every request holds a TCB on the generator for 60 s
  after it completes.** Design your polling budget with that in
  mind: at most `N` requests per 60 s, where `N` is comfortably
  below 7. This budget applies to startup bursts too. The load
  coordinator's startup hydration path (see
  `async_hydrate_remaining` in `select.py`) walks the round-robin
  once at setup to fill in all endpoints, but it goes through the
  client's serialized lock and 2 s min-gap just like steady-state
  traffic — no fan-out.
- **Assume `pk_alloc` failures are silent.** From your side, they
  manifest as either a body-read timeout or (later) a
  connection-refused. Log accordingly, but don't retry
  aggressively — retrying while the generator is out of buffers
  makes it worse.
- **Prefer expanding an endpoint's polling interval over adding a
  new endpoint.** If you must add a new endpoint, put it on the
  load coordinator's round-robin so total request rate stays flat.
- **Trust `Connection: close` on writes as much as on reads.** The
  generator's response to `/wr_logical.cgi` still comes back with
  `Connection: Close`. Don't attempt to reuse control connections
  either.
- **Do not enable HTTP compression** or advertise novel
  `Accept-Encoding` tokens. `identity` only.
- **Debugging hangs is expensive** — you'll need someone at the
  physical unit to power-cycle it. Please add a `_LOGGER.debug()`
  breadcrumb rather than shipping speculative retry logic.

## Source references

- InterNiche 2.0 source tree used for the buffer/limit numbers
  cited above (private mirror).
- Forescout, *INFRA:HALT: Discovering & Mitigating Large Scale OT
  Vulnerabilities in Operational Technology*, 2021.
- NVD, `CVE-2021-27565`.
- Field capture and HA debug log from the 2026-08-01 15:23:42
  failure (see git history around this document's introduction).
