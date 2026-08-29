# Stage 3: Handle concurrent clients

Two ways to handle concurrency here, threading or event loop (asyncio in Python).

Redis uses a single-threaded data manipulation loop, but offloads I/O and slow background operations to multi-threading (socket I/O and lazy frees like UNLINK — not slow commands, which still block the main thread)

Reasons being:
- CPU not being the bottleneck, the real limiting factors are network I/O and memory access speeds
- Complexity of multithreaded data structures, lots of locking will be required
- Cost of overheads for synchronizing, context switching, mutex locking and unlocking (see data structures above)
- Simplicity, easier to debug and reason a single event loop, which makes it easier to guarantee atomic operations (we decide when to hand over control)

## Threading

- With the GIL in Python, only one thread runs Python bytecode at a time
  - in 3.13 it is experimental, and in 3.14 it is officially supported, both in a separate binary with `t`
  - The GIL operates as a mutex
  - Note that when multiple threads are allowed to run at the same time free threaded, the chances of more errors happening can actually increase
  - Redis servers are I/O bound, not CPU bound, free-threading targets CPU-bound parallelism
- While threading, if users modify the same item at the same time, it is possible that the operations are not atomic. Locks are required to ensure that they are.
  - Implementing locks across all data structures effectively just slows down everything, especially with many operations running at the same time
- Threads have overheads
  - Context switching of registers, page tables, etc
  - With 10,000 threads, L2/L3 caches will miss most times
    - This 10,000 ceiling comes from context switching and cache thrashing, not RAM
  - Scheduler spends time deciding which thread should be running
- No control of when a thread should hand over control, which is why locks are required
  - Operating system/kernel decides when another thread should run

## Event loop

- Single thread, cooperative scheduling, control handled over using `await`, which we decide when to switch, not the kernel
- Handler runs atomically from one `await` to another
  - No locks needed for read-modify-write operations like INCR
  - Races can occur across `await` points, within a stretch of code with no awaits, we can guarantee no interleaving, and we can see where they may occur by going through the code
  - Any await operation counts: socket reads, queue gets, awaiting another coroutine
- Cheap switching
  - coroutine handoff is just a function return within a single process (<100 nanoseconds), compared to a thread context switch through the kernel (1-10 microseconds)
- Places we could fail, anything that does not yield blocks every other operation
  - Long CPU work (KEYS * over large keyspace)
  - Synchronous file reads, blocking library calls, `time.sleep`
- Single core required for processing, Redis scales out to more instances (a cluster) not up

## Debuggability

- Threads can cause issues that occur rarely, are silent, and wrong
  - e.g. a INCR operation when there are many clients using the same key
- Event loops cause issues that are visible, shared, and slow
  - e.g. a long-running operation blocks other processes and a response to a client is delayed, every client waiting shows a spike in the latency simultaneously
  - issues findable via asyncio debug mode, which logs slow callbacks
- Slow = performance problem, Wrong = correctness problem.

## Decision

Implement event loop with asyncio
- Connection count: while low during this testing, threads don't scale well. The context switching and cache cost increase too much before RAM runs out
- Shared mutable state: a single shared data structure, multithreaded data structures require locks almost everywhere
- Failure mode: latency vs wrong data