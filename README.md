# rboz
Fast Multi-threaded python http/https stresser (flooder) (socks4/socks5/http/https proxies) 

Disclaimer:
- This is intended for educational purpose only.
- I'm not responsible for whatever might happen if you engage in any illegal activity.

## Features
- Multi-threaded request support http/https
- Support for multiple proxy types (HTTP, HTTPS, SOCKS4, SOCKS5)
- Direct connection mode without proxies
- GET and POST request support
- Real-time statistics on Ctrl+C
- Automatic proxy management with working proxy tracking
- Configurable request delays and connection timeouts

## Usage

### Basic Usage (Direct Connection)
```bash
python rboz.py <url> <threads> <http_mode>
```
Example:
```bash
python rboz.py http://example.com 10 get
```

### Using Proxies
```bash
python rboz.py <url> <threads> <http_mode> --proxy-type <type> --proxy-file <file>
```
Example:
```bash
python rboz.py http://example.com 10 get --proxy-type socks5 --proxy-file proxies.txt
```

### Arguments
- `url`: Target URL (required)
- `threads`: Number of threads to use (required)
- `http_mode`: Request method, either 'get' or 'post' (required)
- `--proxy-type`: Type of proxy to use (optional, default: direct)
  - Options: http, https, socks4, socks5, direct
- `--proxy-file`: Path to file containing proxies (required if using proxies)

### Proxy File Format
Each line should contain a proxy in the format:
```
ip:port
```

## Statistics
Press Ctrl+C to stop the flooder and display statistics:
- Total Requests
- Successful Requests
- Success Rate
- Requests per Second
- Total Runtime

## Performance Notes
- Direct mode has no delay between requests for maximum performance
- Proxy mode includes a small delay (0.05s) between requests
- Failed connections have a 0.5s retry delay
- Each connection handles up to 100 requests before recycling
