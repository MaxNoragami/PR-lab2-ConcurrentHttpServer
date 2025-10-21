Hello World! =(^.^)=


Server listen(1)
-----------------
<img src="https://files.catbox.moe/vn6ujg.png" alt="Requests to server listen(1)" />

Server listen(10)
------------------
<img src="https://files.catbox.moe/waorkd.png" alt="Requests to server after changing to listen(10)" />

Server thread per request
--------------------------
<img src="https://files.catbox.moe/lai7gg.png" alt="Requests to server after implementing thread per request" />

Requests to increment hits, naive approach
-----------------------------------
<img src="https://files.catbox.moe/i9f1ix.png" alt="Requests, hits increment, naive, terminal" />
<img src="https://files.catbox.moe/oplxen.png" alt="Requests, hits increment, naive, browser" />

Requests to increment hits, thread safe approach
----------------------------------------
Even though I increased the 'processing time' to 0.1 seconds, the hits are incremented correctly without any race conditions.

<img src="https://files.catbox.moe/jemeek.png" alt="Requests, hits increment, thread-safe, terminal" />
<img src="https://files.catbox.moe/5zt6cw.png" alt="Requests, hits increment, thread-safe, browser" />