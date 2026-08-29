import asyncio
import socket  # noqa: F401


async def handle_client(loop, conn):
    with conn:
        while True:
            data = await loop.sock_recv(conn, 1024)
            if not data:
                break
            await loop.sock_sendall(b"+PONG\r\n")

async def main():
    print("Starting BYO Redis Server...")
    server_socket = socket.create_server(("localhost", 6379), reuse_port=True)
    server_socket.setblocking(False)
    loop = asyncio.get_running_loop()
    while True:
        connection, _ = await loop.sock_accept(server_socket)
        asyncio.create_task(handle_client(loop, connection))

if __name__ == "__main__":
    asyncio.run(main())